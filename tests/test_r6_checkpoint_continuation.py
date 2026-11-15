"""Compare saved R6 dynamics against the uninterrupted physical plant."""
import json
import numpy as np
import pytest
from vtx.live_server import Action, Laboratory, Mission


@pytest.mark.parametrize(('steps', 'airborne'), [(1600, False), (1601, False), (1603, True)])
def test_r6_checkpoint_continues_same_solver_state(tmp_path, steps, airborne):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant='r6', environment='airport', departure=[-700, 0]))
    if airborne:
        original.aircraft.spawn(-700, 0, 300)
    original.accept_action(Action(authority='manual', reason='Isolated checkpoint comparison',
        engine=.7, collective_deg=[4, 5, 4, 5], tilt_deg=[[1, 0]] * 4))
    for _ in range(steps):
        original.integrate()
    original.checkpoint(force=True)
    original.audit_file.close(); original.audit_file = None
    original.checkpoint = lambda *args, **kwargs: None
    restored = Laboratory(data_root=tmp_path)
    assert restored.active and restored.paused, restored.error
    restored.checkpoint = lambda *args, **kwargs: None
    for _ in range(400):
        original.integrate()
        restored.integrate()
    np.testing.assert_allclose(restored.aircraft.data.qpos, original.aircraft.data.qpos, rtol=1e-9, atol=1e-8)
    np.testing.assert_allclose(restored.aircraft.data.qvel, original.aircraft.data.qvel, rtol=1e-9, atol=1e-8)
    np.testing.assert_allclose(restored.aircraft.fuel, original.aircraft.fuel, rtol=1e-10, atol=1e-10)
    if restored.audit_file:
        restored.audit_file.close()


def test_legacy_r6_checkpoint_is_preserved_for_inspection(tmp_path):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant='r6'))
    original.checkpoint(force=True)
    original.audit_file.close()
    state = json.loads(original.checkpoint_path.read_text(encoding='utf-8'))
    state['schema'] = 1
    original.checkpoint_path.write_text(json.dumps(state), encoding='utf-8')
    before = original.checkpoint_path.read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert 'lacks solver and actuator state' in recovered.error
    assert original.checkpoint_path.read_bytes() == before
