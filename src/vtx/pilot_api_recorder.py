"""Opt-in OpenAI pilot request/response recorder. Does not actuate the aircraft.

Use from a trusted server-side pilot process. Never send API credentials in prompts.
The recorder writes only under VTX_DATA_ROOT; it does not modify flight physics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import queue
import threading
import atexit
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid


def _stamp():
    return datetime.now(timezone.utc).isoformat()


class AsyncFlightRecorder:
    """Bounded non-blocking enqueue; disk I/O happens on a daemon worker.

    On overflow or write failure, count lost events; never block a flight.
    close() is for shutdown/tests, not the flight-control loop.
    """
    def __init__(self, data_root, capacity=4096):
        self.root = Path(data_root)
        self.queue = queue.Queue(maxsize=capacity)
        self.dropped = 0
        self.write_errors = 0
        self._closed = False
        self._thread = threading.Thread(target=self._worker, name="vtx-pilot-recorder", daemon=True)
        self._thread.start()

    def emit(self, event):
        if self._closed:
            self.dropped += 1
            return False
        try:
            self.queue.put_nowait(event)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _worker(self):
        while True:
            event = self.queue.get()
            try:
                if event is None:
                    return
                path = self.root / "evidence" / "flights" / event["run_id"] / "pilot-api.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False,
                                            separators=(",", ":")) + "\\n")
            except (OSError, ValueError, TypeError, KeyError):
                self.write_errors += 1
            finally:
                self.queue.task_done()

    def drain(self):
        """Wait for queued writes; only use outside flight control."""
        self.queue.join()

    def close(self):
        if not self._closed:
            self._closed = True
            self.queue.put(None)
            self._thread.join(timeout=5)


_recorders = {}
_recorders_lock = threading.Lock()


def get_recorder(data_root):
    root = str(Path(data_root).resolve())
    with _recorders_lock:
        if root not in _recorders:
            _recorders[root] = AsyncFlightRecorder(root)
        return _recorders[root]


def close_recorders():
    with _recorders_lock:
        recorders = list(_recorders.values())
        _recorders.clear()
    for recorder in recorders:
        recorder.close()


atexit.register(close_recorders)

def _event(run_id, decision_id, kind, payload):
    return dict(schema_version=1, run_id=run_id, decision_id=decision_id,
                wall_utc=_stamp(), kind=kind, payload=payload)


def record_decision(*, run_id: str, instruction: str, observation: dict,
                    model: str, transport, data_root: str | Path,
                    decision_id: str | None = None):
    """Record exact API request and raw response; transport(request)->response.

    The caller supplies a transport, allowing offline tests without credentials.
    Returns the API response and decision ID. A model response is NOT a flight action.
    """
    if not run_id or not run_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid flight ID")
    if not instruction.strip():
        raise ValueError("Instruction is required")
    decision_id = decision_id or str(uuid.uuid4())
    if not decision_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid decision ID")
    request = {
        "model": model,
        "input": [
            {"role": "developer", "content": "You are Colin, a pilot in a physics-driven flight simulator. Report intended actions; do not claim controls were executed unless the simulator confirms them."},
            {"role": "user", "content": json.dumps({"instruction": instruction, "observation": observation}, allow_nan=False)}
        ],
    }
    path = Path(data_root) / "evidence" / "flights" / run_id / "pilot-api.jsonl"
    recorder = get_recorder(data_root)
    recorder.emit(_event(run_id, decision_id, "openai_request", request))
    try:
        response = transport(request)
    except Exception as exc:
        recorder.emit(_event(run_id, decision_id, "openai_error",
                             {"type": type(exc).__name__}))
        raise
    recorder.emit(_event(run_id, decision_id, "openai_response", response))
    return {"decision_id": decision_id, "response": response, "audit_path": str(path)}


def openai_transport(request: dict):
    """Call Responses API using the server's OPENAI_API_KEY environment variable."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    body = json.dumps(request).encode("utf-8")
    http_request = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(http_request, timeout=60) as response:
        return json.loads(response.read())


def simulated_transport(request: dict):
    """Deterministic fake model output for recorder testing; NOT a pilot or flight."""
    instruction = json.loads(request["input"][1]["content"])["instruction"]
    return {"id": "simulated-response", "object": "response",
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text",
                                     "text": "Acknowledged: " + instruction + ". Awaiting live telemetry before issuing controls."}]}],
            "simulation": True}


def simulate_climb_record(data_root: str | Path):
    return record_decision(run_id="test-climb-10m", decision_id="decision-0001",
                           instruction="Climb to ten metres", observation={"baro_m": 0.0, "radar_clearance_m": 0.0},
                           model="mock", transport=simulated_transport, data_root=data_root)
