"""Unified port bridge must never send Phantom actions to R6 or override manual."""
import json
import sys
import pytest
from tools.phantom import phantom_persistent_pilot as bridge

@pytest.mark.parametrize(
    "variant, authority, expected_actions",
    [("r6", "colin", 0), ("phantom-fx", "manual", 0),
     ("phantom-fx", "colin", 1), (None, "colin", 0)],
)
def test_unified_port_8765_guard(tmp_path, monkeypatch, variant, authority, expected_actions):
    controls = tmp_path / "controls.json"
    controls.write_text(json.dumps({
        "armed": True, "arm_run_id": "test-run", "serial": 5,
        "reason": "Explicitly armed test command",
        "command": {"engine": 0.1, "collective": 0.0},
    }), encoding="utf-8")
    actions = []
    def fake_call(path, payload=None):
        if path == "/api/view":
            return {"run_id": "test-run", "active": True, "paused": False,
                    "authority": authority,
                    "observation": {"configuration": {"airframe_variant": variant}}}
        if path == "/api/observe":
            return {"observation_id": 42, "t_s": 4.2}
        if path == "/api/action":
            actions.append(payload)
            return {"sequence": len(actions)}
        raise AssertionError(path)
    monkeypatch.setattr(bridge, "URL", "http://127.0.0.1:8765")
    monkeypatch.setattr(bridge, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["phantom_persistent_pilot", "--controls", str(controls), "--once"])
    bridge.main()
    assert len(actions) == expected_actions
    if actions:
        assert actions[0]["expected_run_id"] == "test-run"
        assert actions[0]["observation_id"] == 42
        assert actions[0]["authority"] == "colin"

def test_unified_health_read_only(monkeypatch, capsys):
    seen = []
    def fake_call(path, payload=None):
        seen.append(path)
        assert payload is None
        return {"active": True, "authority": "manual",
                "observation": {"configuration": {"airframe_variant": "phantom-fx"}}}
    monkeypatch.setattr(bridge, "URL", "http://127.0.0.1:8765")
    monkeypatch.setattr(bridge, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["phantom_persistent_pilot", "--health"])
    bridge.main()
    result = json.loads(capsys.readouterr().out)
    assert result["phantom_bridge_compatible"] is True
    assert seen == ["/api/view"]
