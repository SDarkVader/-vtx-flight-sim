"""Physics and observation regressions; these benches are not flight validation."""
import math
import json
import os
from pathlib import Path
import subprocess
import sys

import mujoco as mj
import numpy as np
import pytest

from vtx.aircraft import Aircraft
from vtx.governor import ShaftGovernor
from vtx.live_server import Laboratory


@pytest.mark.parametrize('axis,expected', [(3, (1, 3)), (4, (2, 0))])
def test_assist_damps_the_correct_body_axis(axis, expected):
    p = Aircraft(rpm=1200, fuel_kg=10, airframe_variant='r6')
    p.spawn(0, 0, 20)
    p.stability_assist = 1
    p.command['collective_deg'] = [10.] * 4
    p.data.qvel[axis] = math.radians(10)
    mj.mj_forward(p.model, p.data)
    p.step()
    low, high = expected
    assert p.assisted_collective_deg[low] < 10 < p.assisted_collective_deg[high]
    assert all(p.assisted_collective_deg[i] == pytest.approx(10) for i in set(range(4)) - set(expected))


def test_fuel_draw_conserves_energy_after_one_tank_empties():
    p = Aircraft(rpm=1200, tank_fuel_kg=[.00001, 2, 2, 2], engine_power_limit_kw=300)
    p.spawn(0, 0, 20)
    p.command['engine'] = 1
    p.command['collective_deg'] = [12] * 4
    for _ in range(1800):
        p.step()
    assert p.fuel[0] == pytest.approx(0, abs=1e-12)
    assert (p.fuel_initial - p.fuel).sum() == pytest.approx(p.energy['engine_j'] * .4 / 3.6e6, abs=1e-9)


def test_exhaustion_stops_engine_and_bounds_final_timestep_energy():
    p = Aircraft(rpm=1200, tank_fuel_kg=[1e-7, 0, 0, 0])
    p.spawn(0, 0, 20)
    p.command['engine'] = 1
    p.engine_spool = 1
    p.data.qvel[p.vadr['rotor1_spin']] = 60
    mj.mj_forward(p.model, p.data)
    for _ in range(5):
        p.step()
    assert p.fuel.sum() == pytest.approx(0, abs=1e-12)
    assert p.power['engine_w'] == 0
    assert p.energy['engine_j'] * .4 / 3.6e6 == pytest.approx(1e-7, abs=1e-12)
    assert 'FUEL_EXHAUSTED' in p.flags


class ZeroNoise:
    def normal(self, mean, sigma, size=None):
        return np.zeros(size) if size is not None else 0.


@pytest.mark.parametrize('yaw', [0, 90, 180])
def test_body_rate_observation_is_independent_of_heading(tmp_path, monkeypatch, yaw):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory()
    p = lab.aircraft
    p.spawn(0, 0, 20)
    p.data.qpos[3:7] = [math.cos(math.radians(yaw)/2), 0, 0, math.sin(math.radians(yaw)/2)]
    p.data.qvel[3:6] = [.2, 0, 0]
    mj.mj_forward(p.model, p.data)
    lab.sensor_rng = ZeroNoise()
    obs = lab.sensor_observation()
    assert obs['gyro_body_deg_s'] == pytest.approx([math.degrees(.2), 0, 0], abs=.002)
    assert obs['attitude_xyz_deg'][:2] == pytest.approx([0, 0], abs=.001)


def test_cabin_heading_tracks_relative_gimbal_not_world_yaw(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab=Laboratory()
    p=lab.aircraft
    p.spawn(0,0,20)
    p.data.qpos[3:7]=[math.cos(math.pi/4),0,0,math.sin(math.pi/4)]
    p.data.qpos[p.qadr['cabin_z']]=math.pi/2
    mj.mj_forward(p.model,p.data)
    lab.sensor_rng=ZeroNoise()
    obs=lab.sensor_observation()
    assert obs['cabin_heading_body_deg'] == pytest.approx(90,abs=.01)
    assert abs(obs['cabin_attitude_xyz_deg'][2]) == pytest.approx(180,abs=.01)


def test_gear_clearance_detects_ground_and_tree(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory()
    p = lab.aircraft
    p.spawn(0, 0, 0)
    for _ in range(1600):
        p.step()
    assert p.ground_clearance() == pytest.approx(0, abs=.02)
    assert p.max_gear_load_n > 0
    assert p.max_nongear_impact_n == 0
    assert p.physical_snapshot()['command'] == p.command
    tree = next(o for o in lab.world.obstacles if o['id'].startswith('tree-'))
    x, y, z = tree['center']
    top = z + tree['half'][2]
    p.spawn(x, y, 20)
    assert p.ground_clearance() == pytest.approx(20-top+.01, abs=.05)


def test_governor_preserves_integral_during_overspeed():
    governor = ShaftGovernor()
    governor.integral_nm = 2000
    assert governor.update(100, 102, 3000, .1, True) == 0
    assert governor.integral_nm == 2000


def test_import_does_not_create_pilot_or_flight_evidence(tmp_path):
    env = dict(os.environ, VTX_DATA_ROOT=str(tmp_path), PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    subprocess.run([sys.executable, '-c', 'import vtx.live_server'], check=True, env=env)
    assert list(tmp_path.iterdir()) == []


def test_server_startup_exposes_corrected_observation(tmp_path, monkeypatch):
    import asyncio
    import vtx.live_server as server
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    monkeypatch.setattr(server, 'lab', None)
    async def check():
        async with server.lifespan(server.app):
            events = []
            sent_request = False
            async def receive():
                nonlocal sent_request
                if not sent_request:
                    sent_request = True
                    return {'type': 'http.request', 'body': b'', 'more_body': False}
                await asyncio.Event().wait()
            async def send(event):
                events.append(event)
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                     'method': 'GET', 'scheme': 'http', 'path': '/api/observe',
                     'raw_path': b'/api/observe', 'query_string': b'', 'headers': [],
                     'server': ('test', 80), 'client': ('test', 1234), 'root_path': ''}
            await asyncio.wait_for(server.app(scope, receive, send), 10)
            assert next(e for e in events if e['type'] == 'http.response.start')['status'] == 200
            obs = json.loads(b''.join(e.get('body', b'') for e in events if e['type'] == 'http.response.body'))
            assert len(obs['gyro_body_deg_s']) == len(obs['velocity_body_mps']) == 3
            assert obs['radar_clearance_m'] == pytest.approx(.01, abs=.04)
            view = await server.view()
            assert view['rendering_truth']['provenance']['physics_revision'] == 'audit-fixes-20261103-r3'
    asyncio.run(check())
