"""Isolated R6, checkpoint, cloud-access and ground-contact regressions."""
import numpy as np
import pytest
import vtx.live_server as server
from vtx.aircraft import Aircraft
from vtx.world import TestWorld as World


def test_defaults_and_r6_identity_at_distinct_valid_departures(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.delenv('VTX_DATA_ROOT', raising=False)
    request = server.Mission()
    assert request.departure == [0, 0]
    assert (request.airframe_variant, request.gear_variant, request.reference_rpm,
            request.engine_power_limit_kw, request.fuel_kg) == ('r6', 'critical-damping-proposal', 1200, 300, 10)
    lab = server.Laboratory()
    assert lab.aircraft.provenance['revision'] == 'P0-V4A-assembly-r6'
    hashes = []
    for xy in ([0, 0], [13.7, -28.4]):
        lab.start(server.Mission(departure=xy, destination=[-45, 18]))
        assert lab.aircraft.provenance['revision'] == 'P0-V4A-assembly-r6'
        np.testing.assert_allclose(lab.aircraft.data.qpos[:2], xy)
        hashes.append(lab.aircraft.provenance['model_xml_sha256'])
        lab.stop('isolated test')
    assert hashes[0] == hashes[1]


def test_six_gear_contacts_support_r6_on_stand_one():
    world = World()
    assert world.surface_z(0, 0) == pytest.approx(0)
    aircraft = Aircraft(world, gear_variant='critical-damping-proposal', rpm=1200,
                        fuel_kg=10, airframe_variant='r6', engine_power_limit_kw=300)
    aircraft.spawn(0, 0, world.surface_z(0, 0))
    for _ in range(1200):
        aircraft.step()
    assert not aircraft.crashed
    assert aircraft.data.ncon >= 6
    assert all(aircraft.joint(f'gear{i}_stroke')[0] > .002 for i in range(1, 7))
    assert np.linalg.norm(aircraft.data.qvel[:3]) < .05


def test_cloud_access_credentials(monkeypatch):
    token = 'test-token-' + 'a' * 32
    monkeypatch.setattr(server, '_access_token', token)
    assert not server._authorized({}, {})
    assert not server._authorized({'authorization':'Bearer wrong'}, {})
    assert server._authorized({'authorization':'Bearer ' + token}, {})
    monkeypatch.setattr(server, '_access_token', '')
    assert server._authorized({}, {})  # Existing PC/LAN mode.


def test_unrecoverable_checkpoint_does_not_replace_or_archive_sortie(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.delenv('VTX_DATA_ROOT', raising=False)
    checkpoint = tmp_path / 'pilot/live-flight-checkpoint.json'
    checkpoint.parent.mkdir()
    checkpoint.write_text('{broken checkpoint')
    evidence = tmp_path / 'evidence/flights/unfinished'
    evidence.mkdir(parents=True)
    (evidence / 'metadata.json').write_text('{"run_id":"unfinished"}')
    lab = server.Laboratory()
    assert lab.recovery_blocked
    assert not (evidence / 'summary.json').exists()
    with pytest.raises(server.HTTPException) as exc:
        lab.start(server.Mission())
    assert exc.value.status_code == 409
    assert checkpoint.read_text() == '{broken checkpoint'
