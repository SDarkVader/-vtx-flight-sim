"""Bench operation contracts: retargeting is not a reset or a landing command."""
import numpy as np
import vtx.live_server as server
from vtx.live_server import Laboratory, Mission


def test_live_waypoint_preserves_physics_and_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory()
    lab.start(Mission(departure=[0, 0], destination=[-50, 20]))
    run = lab.run_id
    pose = lab.aircraft.data.qpos.copy()
    fuel = lab.aircraft.fuel.copy()
    assert lab.aircraft.command['engine'] == 1.0
    assert not lab.mission['landing_requested']
    result = lab.update_destination([115, 115])  # Tower: valid nav point, unsafe landing.
    assert not result['landing_valid']
    assert lab.run_id == run and lab.active
    np.testing.assert_array_equal(lab.aircraft.data.qpos, pose)
    np.testing.assert_array_equal(lab.aircraft.fuel, fuel)
    assert lab.mission['destination'] == [115, 115]
    lab.audit_file.close()
    lab.audit_file = None
    restored = Laboratory()
    assert restored.run_id == run and restored.paused
    assert restored.mission['destination'] == [115, 115]
    assert not restored.mission['landing_requested']
    restored.stop('isolated test completed')


def test_command_expiration_keeps_bench_engine_without_collective(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory()
    lab.start(Mission(departure=[0, 0], destination=[-50, 20]))
    lab.aircraft.set_command(dict(engine=1, collective_deg=[4]*4))
    lab.aircraft.data.time = 5.1
    lab.integrate()
    assert lab.lease_expired
    assert lab.aircraft.command['engine'] == 1
    assert lab.aircraft.command['collective_deg'] == [0]*4
    lab.stop('isolated test completed')
