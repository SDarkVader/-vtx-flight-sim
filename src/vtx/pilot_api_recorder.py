"""Opt-in OpenAI pilot request/response recorder. Does not actuate the aircraft.

Use from a trusted server-side pilot process. Never send API credentials in prompts.
The recorder writes only under VTX_DATA_ROOT; it does not modify flight physics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, event: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")


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
    _append(path, _event(run_id, decision_id, "openai_request", request))
    try:
        response = transport(request)
    except Exception as exc:
        _append(path, _event(run_id, decision_id, "openai_error",
                             {"type": type(exc).__name__, "message": str(exc)[:500]}))
        raise
    _append(path, _event(run_id, decision_id, "openai_response", response))
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
