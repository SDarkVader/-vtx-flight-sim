"""Check real solver continuation, including an interrupted control sequence."""
import gzip
import json

import numpy as np
import pytest
from vtx import live_server
from vtx.phantom.controls import PhantomAction
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld


@pytest.mark.parametrize(('start', 'command', 'steps'), [
    ('road', {'wing': 'deploy', 'canard_fold': 'deployed'}, 1200),
    ('road', {'wing': 'deploy', 'canard_fold': 'deployed'}, 1201),
    ('vtol', {'stability_mode': 'attitude', 'collective': .83}, 2000),
    ('vtol', {'stability_mode': 'attitude', 'collective': .83}, 2003),
])
def test_checkpoint_continues_the_same_physics(start, command, steps):
    world = TestWorld()
    original = PhantomAircraft(world, 'phantom-a10c-runway-20261112', start_configuration=start)
    original.spawn(0, 0, world.surface_z(0, 0))
    original.set_command(command)
    for _ in range(steps):
        original.step()
    snapshot = json.loads(json.dumps(original.checkpoint_state(), allow_nan=False))
    restored = PhantomAircraft(world, 'phantom-a10c-runway-20261112', start_configuration=start)
    # The server restores a freshly constructed plant without calling spawn.
    # Calling spawn here would conceal lost spawn-time sensor calibration.
    restored.restore_state(snapshot)
    assert restored.radar_ground_reference_m == original.radar_ground_reference_m
    original_observation = original.sensor_observation(np.random.default_rng(42))
    restored_observation = restored.sensor_observation(np.random.default_rng(42))
    for field in ('radar_altimeter_m', 'radar_altimeter_ground_reference_m'):
        assert restored_observation[field] == original_observation[field]
    assert restored.nose_lift == original.nose_lift
    assert restored.wing_timer == original.wing_timer
    assert restored.rng.bit_generator.state == original.rng.bit_generator.state
    for _ in range(400):
        original.step()
        restored.step()
    np.testing.assert_allclose(restored.data.qpos, original.data.qpos, rtol=1e-8, atol=1e-7)
    np.testing.assert_allclose(restored.data.qvel, original.data.qvel, rtol=1e-8, atol=1e-7)
    np.testing.assert_allclose(restored.fuel, original.fuel, rtol=1e-10, atol=1e-10)
    assert restored.bus.soc == pytest.approx(original.bus.soc, abs=1e-10)


def test_pending_controls_and_telemetry_continue_without_a_second_header(tmp_path):
    lab = live_server.Laboratory(data_root=tmp_path)
    lab.start(live_server.Mission(airframe_variant='phantom-a10c-runway-20261112',
                                  phantom={'start_configuration': 'road'}))
    for _ in range(20):
        lab.integrate()
    lab.accept_action(PhantomAction.model_validate({'schema': 'phantom-fbw-1', 'authority': 'manual',
                                                    'reason': 'Recorded test command', 'wing': 'deploy'}))
    lab.checkpoint(force=True)
    lab.aircraft.step_log.close()
    lab.audit_file.close()
    restored = live_server.Laboratory(data_root=tmp_path)
    assert restored.active and restored.paused
    assert restored.next_pending_action == 0 and not restored.action_log[0].get('cancelled')
    restored.paused = False
    for _ in range(30):
        restored.integrate()
    assert restored.aircraft.command['wing'] == 'deploy'
    path = restored.log_path / 'phantom_steps.csv.gz'
    restored.stop('End isolated continuation test')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        lines = stream.readlines()
    assert sum(line.startswith('t,x,y,z,') for line in lines) == 1
    assert len(lines) > 2


def test_legacy_phantom_checkpoint_is_retained_without_claiming_resume(tmp_path):
    lab = live_server.Laboratory(data_root=tmp_path)
    lab.start(live_server.Mission(airframe_variant='phantom-a10c'))
    lab.checkpoint(force=True)
    lab.aircraft.step_log.close()
    lab.audit_file.close()
    checkpoint = json.loads(lab.checkpoint_path.read_text(encoding='utf-8'))
    checkpoint['schema'] = 'phantom-1'
    lab.checkpoint_path.write_text(json.dumps(checkpoint), encoding='utf-8')
    before = lab.checkpoint_path.read_bytes()
    restored = live_server.Laboratory(data_root=tmp_path)
    assert restored.recovery_blocked and not restored.active
    assert 'lacks actuator and controller state' in restored.error
    assert lab.checkpoint_path.read_bytes() == before


@pytest.mark.parametrize('damage', ['old-format', 'missing', 'missing-reference', 'nonfinite', 'boolean'])
def test_checkpoint_without_valid_radar_calibration_cannot_claim_continuation(damage):
    world = TestWorld()
    original = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    original.spawn(0, 0, world.surface_z(0, 0))
    snapshot = original.checkpoint_state()
    if damage == 'old-format':
        snapshot['checkpoint_format'] = 2
    elif damage == 'missing':
        del snapshot['sensor_calibration']
    elif damage == 'missing-reference':
        del snapshot['sensor_calibration']['radar_ground_reference_m']
    else:
        snapshot['sensor_calibration']['radar_ground_reference_m'] = float('nan') if damage == 'nonfinite' else True
    restored = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    before = restored.data.qpos.copy()
    with pytest.raises(ValueError, match='radar sensor calibration'):
        restored.restore_state(snapshot)
    np.testing.assert_array_equal(restored.data.qpos, before)


def test_explicitly_unavailable_radar_calibration_remains_unavailable():
    world = TestWorld()
    original = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    original.spawn(0, 0, world.surface_z(0, 0))
    original.radar_ground_reference_m = None
    snapshot = original.checkpoint_state()
    restored = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    # A different fresh spawn calibration must not become a fallback.
    restored.spawn(0, 0, world.surface_z(0, 0))
    assert restored.radar_ground_reference_m is not None
    restored.restore_state(snapshot)
    assert restored.sensor_observation(np.random.default_rng(42))['radar_altimeter_ground_reference_m'] is None


def test_uncalibrated_checkpoint_is_retained_without_claiming_resume(tmp_path):
    lab = live_server.Laboratory(data_root=tmp_path)
    lab.start(live_server.Mission(airframe_variant='phantom-a10c'))
    lab.checkpoint(force=True)
    lab.aircraft.step_log.close()
    lab.audit_file.close()
    state = json.loads(lab.checkpoint_path.read_text(encoding='utf-8'))
    state['plant']['checkpoint_format'] = 2
    del state['plant']['sensor_calibration']
    lab.checkpoint_path.write_text(json.dumps(state), encoding='utf-8')
    before = lab.checkpoint_path.read_bytes()
    restored = live_server.Laboratory(data_root=tmp_path)
    assert restored.recovery_blocked and not restored.active
    assert 'radar sensor calibration' in restored.error
    assert lab.checkpoint_path.read_bytes() == before
