"""Offline tests: no OpenAI credit, MuJoCo or live aircraft required."""
import json
from pathlib import Path

import pytest

from vtx.pilot_api_recorder import record_decision, simulated_transport, simulate_climb_record


def test_climb_command_records_exact_request_and_response(tmp_path):
    result = simulate_climb_record(tmp_path)
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
    path = tmp_path / "evidence/flights/test-error/pilot-api.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["openai_request", "openai_error"]


def test_invalid_run_id_rejected(tmp_path):
    with pytest.raises(ValueError):
        record_decision(run_id="../secret", instruction="Climb", observation={},
                        model="mock", transport=simulated_transport, data_root=tmp_path)
