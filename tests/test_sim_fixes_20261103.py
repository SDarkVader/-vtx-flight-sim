"""Regression tests for the 2026-11-03 simulator fixes.

Sources: research_notes/Phantom CG compensation and test flights/sim_fidelity_audit.md (F-items)
and flight_campaign.md (D-items). Isolated MuJoCo objects and temporary data roots only.
"""
import gzip
import json
import math
import os
import subprocess
import sys
import zlib
from pathlib import Path

import mujoco as mj
import numpy as np
import pytest

from vtx.aircraft import Aircraft, DT
from vtx.governor import ShaftGovernor

ROOT = Path(__file__).resolve().parents[1]
DEP = dict(departure=[13.7, -28.4], destination=[-45, 18])


def r6(**kw):
    return Aircraft(rpm=1200, fuel_kg=kw.pop('fuel_kg', 10), engine_power_limit_kw=300, airframe_variant='r6', **kw)


# ---------------------------------------------------------------- F1 assist frame
@pytest.mark.parametrize('axis,drop,rise', [(0, 1, 3), (1, 2, 0)])
def test_assist_reads_true_body_rates_and_moves_the_correct_pair(axis, drop, rise):
    p = r6(); p.spawn(0, 0, 20); p.stability_assist = 1.; p._bench_apply_experimental_assist = True
    p.set_command(dict(engine=1., collective_deg=[10.] * 4, tilt_deg=[[0., 0.]] * 4, cabin_deg=[0., 0., 0.], cabin_level=True))
    p.data.qvel[3 + axis] = math.radians(10)
    mj.mj_forward(p.model, p.data)
    p.step()
    a = p.assisted_collective_deg
    assert a[drop] < 10 < a[rise]
    others = [i for i in range(4) if i not in (drop, rise)]
    assert all(a[i] == pytest.approx(10, abs=1e-9) for i in others)


# ---------------------------------------------------------------- F3 fuel draw
def test_fuel_draw_conserves_mass_when_a_tank_is_empty():
    p = r6(tank_fuel_kg=[0.1, 2, 2, 2])
    drawn = p.draw_fuel(0.4)
    assert drawn == pytest.approx(0.4)
    assert p.fuel.sum() == pytest.approx(6.1 - 0.4, abs=1e-12)
    assert p.fuel[0] == 0.0
    p2 = r6(tank_fuel_kg=[0.01, 0.01, 0.01, 0.01])
    p2.draw_fuel(1.0)
    assert p2.fuel.sum() == 0 and 'FUEL_EXHAUSTED' in p2.flags


def test_unequal_tank_burn_matches_engine_energy():
    p = r6(tank_fuel_kg=[0.0005, 2, 2, 2])
    p.spawn(0, 0, 0); p.engine_spool = 1.
    p.set_command(dict(engine=1., collective_deg=[12.] * 4, tilt_deg=[[0., 0.]] * 4, cabin_deg=[0., 0., 0.], cabin_level=True))
    for _ in range(800):
        p.step()
    assert p.fuel[0] == 0.0
    used = float((p.fuel_initial - p.fuel).sum())
    assert used == pytest.approx(p.energy['engine_j'] / 3.6e6 * .4, rel=1e-9)


# ---------------------------------------------------------------- F8a governor
def test_governor_holds_integrator_through_overspeed():
    g = ShaftGovernor()
    for _ in range(4000):
        g.update(100., 99.5, 3000., .0025, True)
    before = g.integral_nm
    assert before > 0
    for _ in range(40):
        assert g.update(100., 102., 3000., .0025, True) == 0
    assert g.integral_nm == pytest.approx(before)


# ---------------------------------------------------------------- F11a integrator
def test_torque_free_spinning_rotor_conserves_angular_momentum():
    p = r6()
    m, d = p.model, p.data
    assert m.opt.integrator == mj.mjtIntegrator.mjINT_IMPLICIT
    m.opt.gravity[:] = 0
    p.spawn(0, 0, 50)
    for i, sign in enumerate([1, -1, 1, -1], 1):
        d.qvel[p.vadr[f'rotor{i}_spin']] = sign * 1200 * 2 * math.pi / 60
        d.qvel[p.vadr[f'shaft{i}_spin']] = sign * 6016 * 2 * math.pi / 60
    d.qvel[3:6] = [.05, -.03, .02]
    mj.mj_forward(m, d)
    h0 = d.sensor('total_H').data.copy()
    for _ in range(int(20 / DT)):
        mj.mj_step(m, d)
    h1 = d.sensor('total_H').data.copy()
    assert np.linalg.norm(h1 - h0) / np.linalg.norm(h0) < 1e-3


# ---------------------------------------------------------------- live packet (F2, F4)
@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.delenv('VTX_DATA_ROOT', raising=False)
    import vtx.live_server as server
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    return server.Laboratory()


@pytest.mark.parametrize('yaw', [0, 90, 180])
def test_packet_publishes_body_rates_and_heading_relative_attitude(lab, yaw):
    from scipy.spatial.transform import Rotation
    p = lab.aircraft; p.spawn(0, 0, 20)
    q = Rotation.from_euler('ZY', [yaw, 5], degrees=True).as_quat()
    p.data.qpos[3:7] = [q[3], q[0], q[1], q[2]]
    p.data.qvel[3] = .2          # free-joint angular velocity is body-local
    mj.mj_forward(p.model, p.data)
    obs = lab.sensor_observation()
    np.testing.assert_allclose(obs['gyro_body_deg_s'], [math.degrees(.2), 0, 0], atol=.05)
    assert obs['attitude_xyz_deg'][1] == pytest.approx(5, abs=.05)
    assert obs['attitude_xyz_deg'][0] == pytest.approx(0, abs=.05)


def test_body_channels_draw_no_extra_noise(lab):
    lab.sensor_observation()
    state = lab.sensor_rng.bit_generator.state
    ref = np.random.default_rng(); ref.bit_generator.state = state
    lab.last_obs = None; lab.aircraft.data.time += 1
    lab.sensor_observation()
    ref.normal(0, 1, 2 + 1 + 1 + 3 + 3 + 3)   # gnss2, baro, radar, attitude3, gyro3, velocity3
    assert lab.sensor_rng.bit_generator.state == ref.bit_generator.state


def test_radar_reads_foot_clearance_on_gear_in_air_and_over_a_tree(lab):
    from vtx.live_server import foot_clearance_m
    p = lab.aircraft
    p.spawn(0, 0, 0)
    for _ in range(800):
        p.step()
    assert foot_clearance_m(p) == pytest.approx(0, abs=.02)
    p.spawn(0, 0, 20)
    assert foot_clearance_m(p) == pytest.approx(20.01, abs=.02)
    tree = next(o for o in lab.world.obstacles if o['kind'] == 'cylinder')
    x, y = tree['center'][:2]; top = tree['center'][2] + tree['half'][2]
    ground = lab.world.terrain_z(x, y)
    p.spawn(x, y, ground + top + 5)
    assert foot_clearance_m(p) == pytest.approx(5.01, abs=.05)


# ---------------------------------------------------------------- F16 import side effect
def test_importing_live_server_writes_no_evidence(tmp_path):
    run = tmp_path / 'evidence/flights/20990101T000000-abcdef'
    run.mkdir(parents=True)
    (run / 'metadata.json').write_text(json.dumps(dict(run_id=run.name, mission={}, request={})))
    env = dict(os.environ, VTX_DATA_ROOT=str(tmp_path), PYTHONPATH=str(ROOT / 'src'))
    subprocess.run([sys.executable, '-c', 'import vtx.live_server'], check=True, env=env, cwd=str(tmp_path))
    assert not (run / 'summary.json').exists()
    assert not (tmp_path / 'pilot').exists()


# ---------------------------------------------------------------- Phantom (D-items)
def phantom_lab(tmp_path, monkeypatch, **mission):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    import vtx.live_server as server
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    lab = server.Laboratory()
    lab.start(server.Mission(**DEP, **mission))
    return lab


def test_phantom_does_not_inherit_legacy_fuel_default(tmp_path, monkeypatch):
    from vtx.live_server import Mission
    from vtx.phantom.live import make_aircraft
    from vtx.world import TestWorld
    w = TestWorld()
    assert make_aircraft(w, Mission(**DEP, airframe_variant='phantom')).fuel_initial.sum() == pytest.approx(110)
    assert make_aircraft(w, Mission(**DEP, airframe_variant='phantom', fuel_kg=50.)).fuel_initial.sum() == pytest.approx(50)
    assert make_aircraft(w, Mission(**DEP, airframe_variant='phantom-fx', phantom={'load_state': 'FX-C'})).fuel_initial.sum() == pytest.approx(60)
    lab = phantom_lab(tmp_path, monkeypatch, airframe_variant='phantom')
    assert lab.aircraft.fuel_initial.sum() == pytest.approx(110)
    lab.stop('end'); lab.retry({'authority': 'manual'})
    assert lab.aircraft.fuel_initial.sum() == pytest.approx(110)
    lab.stop('end retry')


def test_cg_gate_evaluated_after_settling_and_landing_needs_weight_on_gear(tmp_path, monkeypatch):
    from vtx.phantom import live as pl
    lab = phantom_lab(tmp_path, monkeypatch, airframe_variant='phantom-fx', phantom={'load_state': 'FX-C'})
    rows = [json.loads(l) for l in (lab.log_path / 'events.jsonl').read_text().splitlines()]
    assert next(r for r in rows if r['kind'] == 'phantom_run_keys')['payload']['cg_gate']['status'] == 'pending'
    while lab.aircraft.data.time < 1.6:
        lab.integrate()
    assert lab.phantom_cg_gate['status'] in ('GO', 'NO_GO'), lab.phantom_cg_gate
    assert lab.phantom_cg_gate['t_s'] >= pl.CG_GATE_SETTLE_S
    assert pl.gear_weight_fraction(lab.aircraft) > .9
    # Pretend a hop happened; with the fans carrying the weight there is no landing.
    lab.left_ground = True
    monkeypatch.setattr(pl, 'gear_weight_fraction', lambda p: .05)
    t0 = lab.aircraft.data.time
    while lab.aircraft.data.time < t0 + 2.3:
        lab.integrate()
    assert lab.active
    monkeypatch.undo()
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    while lab.aircraft.data.time < t0 + 5:
        lab.integrate()
    assert lab.active and lab.last_landing['physical'] == 'supported_stable'
    lab.stop('End landing assessment test')
    s = json.loads((lab.log_path / 'summary.json').read_text())
    assert s['outcome'] == 'landed_at_departure' and s['phantom']['cg_gate']['status'] in ('GO', 'NO_GO')


def test_touchdown_is_debounced_and_step_log_is_readable_mid_run(tmp_path, monkeypatch):
    lab = phantom_lab(tmp_path, monkeypatch, airframe_variant='phantom-fx', phantom={'load_state': 'FX-C'})
    p = lab.aircraft
    obs = lab.sensor_observation()
    ref = obs['radar_altimeter_ground_reference_m']
    assert ref is not None and obs['radar_altimeter_m'] == pytest.approx(ref, abs=.1)
    while p.data.time < 1.2:
        lab.integrate()
    raw = (lab.log_path / 'phantom_steps.csv.gz').read_bytes()
    text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw).decode()
    assert text.count('\n') >= 50
    # drop from 0.6 m: exactly one touchdown with a positive sink rate
    p.data.qpos[2] += .6; p.data.qvel[:] = 0; p.airborne = True; mj.mj_forward(p.model, p.data)
    n0 = len(p.events)
    while p.data.time < 4.5:
        lab.integrate()
    td = [e for e in p.events[n0:] if e['event'] == 'touchdown']
    assert len(td) == 1 and td[0]['sink_rate_m_s'] > 0
    lab.stop('end')


def test_gear_weight_fraction_is_low_when_fans_carry_the_weight():
    from vtx.phantom.live import gear_weight_fraction
    from vtx.phantom.plant import PhantomAircraft
    from vtx.world import TestWorld
    p = PhantomAircraft(TestWorld(), 'phantom-fx', load_state='FX-C'); p.spawn(0, 0, 0)
    W = float(sum(p.model.body_mass)) * p.P['atmosphere.gravity_m_s2']
    p.fan_state = [dict(thrust_n=.95 * W / 4) for _ in range(4)]
    assert gear_weight_fraction(p) == pytest.approx(.05, abs=1e-6)


def test_bench_reports_allocator_delivered_ceiling_for_as_drawn_phantom():
    sys.path.insert(0, str(ROOT / 'tools/phantom'))
    import phantom_bench as B
    r = B.allocator_ceiling('phantom', seconds=2.0)
    assert r['delivered_peak_w'] < 0.6 < r['ideal_w']   # campaign live ceiling 0.529 W; ideal 0.79 W
    assert not r['left_ground']
