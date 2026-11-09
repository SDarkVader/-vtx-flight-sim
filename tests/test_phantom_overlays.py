"""Opt-in overlays: hull lift / Munk term (hull_lift_v1) and road suspension (road_suspension_v1)."""
import json, math
from pathlib import Path

import numpy as np
import pytest

from vtx.aircraft import DT
from vtx.phantom import overlays
from vtx.phantom.params import Params, ROOT
from vtx.phantom.plant import PhantomAircraft, suspension_design
from vtx.phantom.surface_aero import SurfaceAero
from vtx.world import TestWorld

P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
PODS = ('FL', 'FR', 'RL', 'RR')


def test_overlays_are_opt_in_and_leave_base_configs_alone():
    for v in ('phantom', 'phantom-fx'):
        base = Params(v, P6)
        assert 'hull_lift' not in base.tree['aero'] and 'suspension' not in base.tree
        assert base.get('aero.hull_lift.enabled', 0.0) == 0.0 and base.get('suspension.enabled', 0.0) == 0.0
        on = Params(v, overlays.load('hull_lift_v1', 'road_suspension_v1', extra=P6))
        assert on.config_sha256 != base.config_sha256                 # different physics, different identity
    a = PhantomAircraft(TestWorld(), 'phantom-fx', overrides=P6)
    assert 'pod_FL_susp' not in a.jid and SurfaceAero(a.P).hull is None
    with pytest.raises(ValueError):
        overlays.load('no_such_overlay')


def test_hull_lift_values_match_the_vortex_lattice_evidence():
    ev = json.loads((ROOT / 'evidence/phantom/hull_lift_vlm.json').read_text())
    P = Params('phantom-fx', overlays.load('hull_lift_v1'))
    assert P['aero.hull_lift.k_pitch_m2'] == pytest.approx(ev['pitch_forebody']['K_m2'], abs=1e-3)
    assert P['aero.hull_lift.x_cp_pitch_m'] == pytest.approx(ev['pitch_forebody']['x_cp_m'], abs=1e-3)
    assert P['aero.hull_lift.k_yaw_m2'] == pytest.approx(ev['yaw_side_profile_ahead_of_fins']['K_m2'], abs=1e-3)
    env = ev['envelope']                                             # CAD envelope agrees with the parameter file's projections
    assert env['plan_area_m2'] == pytest.approx(env['parameter_file_plan_m2'], rel=0.05)
    assert env['side_area_m2'] == pytest.approx(env['parameter_file_side_m2'], rel=0.05)
    # independent cross-check: Multhopp slender-body forebody moment within 15 % of the vortex lattice
    assert ev['multhopp_forebody_check']['dM_dalpha_m3'] == pytest.approx(ev['pitch_forebody']['dM_dalpha_about_cg_m3'], rel=0.15)


def _state(P):
    return dict(wing_frac=dict(left=1.0, right=1.0), wing_locked=dict(left=True, right=True), flap=dict(left=0.0, right=0.0),
                aileron=dict(left=0.0, right=0.0), canard_pitch=dict(left=0.0, right=0.0), canard_deployed=dict(left=True, right=True),
                stab_te_up=math.radians(P['proposals.p6_stab_rest_te_up_deg']))


def _moment_y(P, alpha_deg, beta_deg=0.0, V=60.0):
    SA = SurfaceAero(P); a, b = math.radians(alpha_deg), math.radians(beta_deg)
    v = V * np.array([math.cos(a) * math.cos(b), math.sin(b), -math.sin(a) * math.cos(b)])
    r = SA.compute(v, np.zeros(3), np.zeros(3), _state(P))
    return r, next((s for s in r['surfaces'] if s['name'] == 'hull_lift'), None)


def test_hull_lift_is_zero_at_zero_incidence_and_shifts_cm_alpha_by_the_vlm_value():
    P0 = Params('phantom-fx', P6); P1 = Params('phantom-fx', overlays.load('hull_lift_v1', extra=P6))
    _, h = _moment_y(P1, 0.0)
    assert np.allclose(h['force_n'], 0.0, atol=1e-9)
    xcg = -0.152; q = 0.5 * 1.225 * 60.0 ** 2
    def dM(P):
        m = [(_moment_y(P, a)[0]) for a in (0.0, 2.0)]
        M = [-(r['moment_body'] - np.cross([xcg, 0, 0.56], r['force_body']))[1] for r in m]   # nose-up about the CG
        return (M[1] - M[0]) / math.radians(2.0) / q
    shift = dM(P1) - dM(P0)
    expect = P1['aero.hull_lift.k_pitch_m2'] * (P1['aero.hull_lift.x_cp_pitch_m'] - xcg)
    assert shift == pytest.approx(expect, rel=0.03)                  # ~18.2 m^3: destabilising (nose-up with alpha)
    _, hs = _moment_y(P1, 0.0, beta_deg=5.0)
    assert hs['side_force_n'] < 0                                    # sideslip toward +y -> side force toward -y


def test_suspension_holds_ride_height_and_bounces_at_the_design_frequency():
    ov = overlays.load('road_suspension_v1', extra=P6)
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-fx', overrides=ov, start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    d = suspension_design(a.P, a.L, a.L.body_inertials())
    assert d['FL']['stiffness_n_m'] < d['RL']['stiffness_n_m']       # rear carries more: stiffer for equal frequency
    a.set_command(dict(brake=[1.0] * 4))
    for _ in range(int(2.5 / DT)):
        a.step()
    q = [a.joint(f'pod_{k}_susp')[0] for k in PODS]
    assert max(abs(x) for x in q) < 0.003                            # design ride height kept (preloaded springs)
    z0 = float(a.data.qpos[2]); a.data.qvel[2] = -0.4                # heave kick
    zs = []
    for _ in range(int(3.0 / DT)):
        a.step(); zs.append(float(a.data.qpos[2]) - z0)
    zs = np.array(zs); cross = np.where(np.diff(np.sign(zs)) != 0)[0]
    f = 1.0 / (2 * np.mean(np.diff(cross[:4])) * DT)
    assert 1.2 < f < 1.8                                             # 1.6 Hz spring-only, tyre in series lowers it a little
    assert abs(zs[-1]) < 0.15 * abs(zs).max()                        # damped


def test_suspension_lets_the_wheels_follow_an_unloading_body():
    """85 % of the weight taken off the body (as aero lift would): the springs extend ~8 cm and all four tyres stay on the road."""
    import mujoco as mj
    ov = overlays.load('road_suspension_v1', extra=P6)
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-fx', overrides=ov, start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[1.0] * 4))
    for _ in range(int(1.5 / DT)):
        a.step()
    z_rest = float(a.data.qpos[2]); W = a.mass_properties()['mass_kg'] * 9.80665
    base = a.apply_forces
    def lifted():
        base()
        cg = np.array(a.mass_properties()['cg_world_m'])
        mj.mj_applyFT(a.model, a.data, np.array([0, 0, 0.85 * W]), np.zeros(3), cg, a.bids['airframe'], a.data.qfrc_applied)
    a.apply_forces = lifted
    for _ in range(int(2.0 / DT)):
        a.step()
    q = [a.joint(f'pod_{k}_susp')[0] for k in PODS]
    assert a.support_count() == 4
    assert all(-0.10 < x < -0.06 for x in q)                         # ~ -0.0825 m: 0.85 x preload / spring rate
    assert float(a.data.qpos[2]) - z_rest == pytest.approx(-np.mean(q), abs=0.01)


def test_wheel_drive_limits_cap_power_and_stop_an_unloaded_wheel_overspinning():
    """Base plant: an unloaded wheel under full drive spins up without bound. With wheel_drive_limits_v1 the torque
    is capped at rated power / speed and traction control holds the slip near its limit."""
    import mujoco as mj
    def spin(ov):
        w = TestWorld(); a = PhantomAircraft(w, 'phantom-fx', overrides=ov, start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
        W = a.mass_properties()['mass_kg'] * 9.80665; base = a.apply_forces
        def lifted():
            base(); mj.mj_applyFT(a.model, a.data, np.array([0, 0, 1.3 * W]), np.zeros(3), np.array(a.mass_properties()['cg_world_m']),
                                  a.bids['airframe'], a.data.qfrc_applied)
        a.apply_forces = lifted
        a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4))
        for _ in range(int(1.5 / DT)):
            a.step()
        assert a.support_count() == 0
        return max(abs(a.joint(f'pod_{k}_wheel')[1]) for k in PODS), a
    free, _ = spin(P6)
    lim, a = spin(overlays.load('wheel_drive_limits_v1', extra=P6))
    r = a.P['pods.tyre_radius_m']
    assert free > 50.0                                               # base: overspins with nothing to push against
    assert lim * r < (1 + 2 * a.P['drive.traction_slip_max']) * a.P['drive.slip_reference_speed_min_m_s'] + 0.5
    a.data.qvel[a.model.jnt_dofadr[a.jid['pod_FL_wheel']]] = 300.0     # slip far above 2x the limit -> no drive torque
    assert a.wheel_drive_torque(dict(wheel_drive=[1.0] * 4))[0] == 0.0
    a.data.qvel[:3] = a.R() @ np.array([300.0 * r, 0, 0])             # wheel matched to road speed: power cap 60 kW / 300 rad/s
    assert abs(a.wheel_drive_torque(dict(wheel_drive=[1.0] * 4))[0]) == pytest.approx(a.P['pods.hub_motor_power_w'] / 300.0, rel=1e-6)
