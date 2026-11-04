"""Offline tests: no OpenAI credit, MuJoCo or live aircraft required."""
import json
from pathlib import Path

import pytest

from vtx.pilot_api_recorder import record_decision, simulated_transport, simulate_climb_record, get_recorder, AsyncFlightRecorder


def test_climb_command_records_exact_request_and_response(tmp_path):
    result = simulate_climb_record(tmp_path)
    get_recorder(tmp_path).drain()
    rows = [json.loads(line) for line in Path(result["audit_path"]).read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["openai_request", "openai_response"]
    assert all(r["run_id"] == "test-climb-10m" for r in rows)
    assert all(r["decision_id"] == "decision-0001" for r in rows)
    prompt = json.loads(rows[0]["payload"]["input"][1]["content"])
    assert prompt["instruction"] == "Climb to ten metres"
    assert rows[1]["payload"] == result["response"]
    assert rows[1]["payload"]["simulation"] is True


def test_error_is_recorded_and_propagated(tmp_path):
    def fail(_request):
        raise RuntimeError("mock API failure")
    with pytest.raises(RuntimeError, match="mock API failure"):
        record_decision(run_id="test-error", instruction="Climb to ten metres",
                        observation={}, model="mock", transport=fail, data_root=tmp_path)
    get_recorder(tmp_path).drain()
    path = tmp_path / "evidence/flights/test-error/pilot-api.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["openai_request", "openai_error"]


def test_invalid_run_id_rejected(tmp_path):
    with pytest.raises(ValueError):
        record_decision(run_id="../secret", instruction="Climb", observation={},
                        model="mock", transport=simulated_transport, data_root=tmp_path)

def test_audit_file_is_one_json_object_per_line(tmp_path):
    """Regression: records were joined with a literal backslash-n, putting every event on one line."""
    recorder = AsyncFlightRecorder(tmp_path)
    for i in range(3):
        assert recorder.emit({"run_id": "fmt", "kind": "example", "payload": {"i": i}})
    recorder.drain()
    recorder.close()
    text = (tmp_path / "evidence/flights/fmt/pilot-api.jsonl").read_text()
    assert text.endswith("\n") and "\\n" not in text          # real newlines, no literal backslash-n
    rows = [json.loads(line) for line in text.splitlines()]
    assert [r["payload"]["i"] for r in rows] == [0, 1, 2]


def test_background_writer_failure_does_not_raise(tmp_path):
    """A real I/O failure: a file sits where the evidence directory should be, so mkdir fails in the worker."""
    root = tmp_path / "blocked"
    root.mkdir()
    (root / "evidence").write_text("not a directory")
    recorder = AsyncFlightRecorder(root, capacity=2)
    assert recorder.emit({"run_id": "test", "kind": "example", "payload": {}})   # enqueue still succeeds
    recorder.drain()
    assert recorder.write_errors == 1                                           # failure counted, flight unaffected
    recorder.close()


def test_closed_recorder_drops_without_blocking(tmp_path):
    recorder = AsyncFlightRecorder(tmp_path)
    recorder.close()
    assert recorder.emit({"run_id": "test"}) is False
    assert recorder.dropped == 1
