"""Analytical screening and selectable-environment regressions, not flight tests."""
import asyncio
import math
import json
import numpy as np
import pytest
from fastapi import HTTPException
from vtx.aircraft import Aircraft
from vtx.atmosphere import standard_air_density
from vtx.ducted_fan_screen import annulus_area, hover_power_w, hover_thrust_n, ideal_duct_bound_power_w
import vtx.live_server as live_server
from vtx.live_server import Laboratory, Mission
from vtx.mission_selection import MapPoint
from vtx.phantom.plant import PhantomAircraft
from vtx.world import SandboxWorld, make_world, resolve_environment_key


def test_standard_atmosphere_and_range():
    assert standard_air_density(0) == pytest.approx(1.225, rel=1e-5)
    assert standard_air_density(5000) == pytest.approx(.7361, rel=1e-3)
    assert standard_air_density(11000) == pytest.approx(.3639, rel=1e-3)
    assert standard_air_density(11000.001) == pytest.approx(standard_air_density(11000), rel=1e-6)
    assert standard_air_density(20000) < standard_air_density(11000)
    with pytest.raises(ValueError):standard_air_density(20001)


def test_steady_wind_and_isa_affect_physical_plant():
    p=Aircraft(atmosphere_model='isa',wind_world_mps=[10,0,0])
    p.spawn(0,0,5000)
    p.step()
    rho=standard_air_density(p.data.xpos[p.bids['airframe'],2])
    assert p.data.xfrc_applied[p.bids['airframe'],0] == pytest.approx(.5*rho*1.65*100, rel=1e-4)
    assert p.aero.rho == pytest.approx(standard_air_density(p.data.xpos[p.bids['rotor4'],2]), rel=1e-4)
    assert p.physical_snapshot()['environment']['wind_world_mps'] == [10,0,0]
    actuator=p.physical_snapshot()['actuators']['nacelle'][0][0]
    assert {'request_n','applied_n','limit_n','saturated'} <= actuator.keys()
    assert abs(actuator['applied_n']) <= actuator['limit_n']
    json.dumps(p.physical_snapshot(),allow_nan=False)
    with pytest.raises(ValueError):p.set_wind([0,float('nan'),0])


def test_environment_survives_retry_and_checkpoint(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory()
    lab.start(Mission(atmosphere_model='isa',wind_world_mps=[3,-4,1],time_scale=.05))
    lab.checkpoint(force=True)
    lab.audit_file.close()
    restored=Laboratory()
    assert restored.aircraft.atmosphere_model == 'isa'
    np.testing.assert_allclose(restored.aircraft.wind,[3,-4,1])
    restored.stop('test')
    restored.retry({})
    assert restored.aircraft.atmosphere_model == 'isa'
    np.testing.assert_allclose(restored.aircraft.wind,[3,-4,1])
    assert restored.time_scale == .05
    restored.stop('test')


def test_hover_screen_is_reversible_and_separates_ideal_bound():
    area=annulus_area(.245,.110)
    assert area == pytest.approx(.151,abs=.001)
    thrust=1300*9.80665/4
    power=hover_power_w(thrust,area,.8)
    assert hover_thrust_n(power,area,.8) == pytest.approx(thrust)
    open_ideal=hover_power_w(thrust,area,1.)
    assert ideal_duct_bound_power_w(thrust,area,1.)/open_ideal == pytest.approx(1/math.sqrt(2))
    with pytest.raises(ValueError):annulus_area(.1,.2)
    with pytest.raises(ValueError):hover_power_w(thrust,area,0)


def test_airport_and_sandbox_worlds_change_physics_geometry_and_model_hash():
    from vtx.world import TestWorld
    airport = make_world('airport')
    sandbox = make_world('sandbox')
    assert isinstance(airport, TestWorld) and not isinstance(airport, SandboxWorld)
    assert isinstance(sandbox, SandboxWorld)
    assert airport.id == 'stage1-extended-airfield-recovery' and airport.version == '4'
    assert sandbox.id == 'stage1-valley' and sandbox.version == '2'
    assert airport.half == 4000. and airport.n == 401
    assert sandbox.half == 1000. and sandbox.n == 201
    assert airport.default_departure == [-700., 0.]
    assert sandbox.default_departure == [-700., 0.]

    # Both Airport and Sandbox have the flattened east/west takeoff strip at (400, 0) and (-700, 0)
    # aligned with the Phantom A10-B heading (+X); Sandbox is enclosed by valley hills off the strip
    # and rejects (-1500, 0) as out of its 1,000 m half-extent boundary.
    assert airport.terrain_z(400., 0.) == pytest.approx(0., abs=1e-6)
    assert sandbox.terrain_z(400., 0.) == pytest.approx(0., abs=1e-6)
    assert sandbox.terrain_z(400., 180.) > 20.
    assert airport.validate(MapPoint(-700., 0.), 'departure').valid
    assert sandbox.validate(MapPoint(-700., 0.), 'departure').valid
    assert airport.validate(MapPoint(-1500., 0.), 'departure').valid
    assert not sandbox.validate(MapPoint(-1500., 0.), 'departure').valid
    assert sandbox.validate(MapPoint(0., 0.), 'departure').valid

    # Both R6 and Phantom A10-B compile distinct MuJoCo XML models for Airport vs Sandbox.
    r6_airport = Aircraft(airport, airframe_variant='r6')
    r6_sandbox = Aircraft(sandbox, airframe_variant='r6')
    assert r6_airport.provenance['model_xml_sha256'] != r6_sandbox.provenance['model_xml_sha256']

    phantom_airport = PhantomAircraft(airport, 'phantom-a10b', start_configuration='road')
    phantom_sandbox = PhantomAircraft(sandbox, 'phantom-a10b', start_configuration='road')
    assert phantom_airport.provenance['model_xml_sha256'] != phantom_sandbox.provenance['model_xml_sha256']


def test_live_environment_switch_and_active_sortie_protection(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)

    # Switch to Test Sandbox while idle: updates world, view, model_xml_sha256, and places aircraft at [-700, 0] facing +X down the runway.
    res_sandbox = asyncio.run(live_server.set_environment({'environment': 'sandbox', 'airframe_variant': 'phantom-a10b', 'start_configuration': 'road'}))
    assert res_sandbox['ok'] is True
    assert res_sandbox['environment'] == 'sandbox'
    assert res_sandbox['world']['id'] == 'stage1-valley'
    assert res_sandbox['view']['environment']['key'] == 'sandbox'
    sandbox_pos = res_sandbox['view']['rendering_truth']['body_poses']['airframe']['position']
    assert sandbox_pos[0] == pytest.approx(-700., abs=0.05) and sandbox_pos[1] == pytest.approx(0., abs=0.05)
    assert res_sandbox['view']['rendering_truth']['phantom']['physics_data']['variant'] == 'phantom-a10b'
    sandbox_hash = res_sandbox['view']['rendering_truth']['provenance']['model_xml_sha256']

    # Switch to Main Airport while idle: updates world, view, model_xml_sha256, and places aircraft at [-700, 0].
    res_airport = asyncio.run(live_server.set_environment({'environment': 'airport', 'airframe_variant': 'phantom-a10b', 'start_configuration': 'road'}))
    assert res_airport['ok'] is True
    assert res_airport['environment'] == 'airport'
    assert res_airport['world']['id'] == 'stage1-extended-airfield-recovery'
    assert res_airport['view']['environment']['key'] == 'airport'
    airport_pos = res_airport['view']['rendering_truth']['body_poses']['airframe']['position']
    assert airport_pos[0] == pytest.approx(-700., abs=0.05) and airport_pos[1] == pytest.approx(0., abs=0.05)
    airport_hash = res_airport['view']['rendering_truth']['provenance']['model_xml_sha256']
    assert sandbox_hash != airport_hash

    # Start a live sortie in Test Sandbox with Colin authority.
    started = lab.start(Mission(environment='sandbox', departure=[0., 0.], destination=[-50., 20.], authority='colin', airframe_variant='r6', time_scale=0.05))
    assert lab.active is True
    assert lab.world.environment_key == 'sandbox'
    assert lab.mission['environment'] == 'stage1-valley'
    assert lab.mission['environment_key'] == 'sandbox'

    # Switching environment during an active sortie is refused with HTTP 409 without resetting the sortie.
    with pytest.raises(HTTPException) as exc:
        asyncio.run(live_server.set_environment({'environment': 'airport'}))
    assert exc.value.status_code == 409
    assert lab.active is True
    assert lab.run_id == started['run_id']
    assert lab.world.environment_key == 'sandbox'

    # Step live physics and verify checkpoint restoration preserves SandboxWorld.
    for _ in range(25):
        lab.integrate()
    lab.checkpoint(force=True)
    lab.audit_file.close()
    lab.audit_file = None

    restored = Laboratory(data_root=tmp_path)
    assert restored.active is True
    assert restored.world.environment_key == 'sandbox'
    assert restored.world.id == 'stage1-valley'
    assert restored.mission['environment_key'] == 'sandbox'
    restored.stop('sandbox checkpoint test complete')

    monkeypatch.setattr(live_server, 'lab', restored)
    recorded_runs = asyncio.run(live_server.runs())
    assert recorded_runs[0]['run_id'] == started['run_id']
    assert recorded_runs[0]['environment'] == 'stage1-valley'
    assert recorded_runs[0]['environment_key'] == 'sandbox'
    assert recorded_runs[0]['environment_label'] == 'Test Sandbox'
