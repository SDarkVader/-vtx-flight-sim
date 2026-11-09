"""Phantom A10-B: the canonical default Phantom (phantom-a10b = A10-A + model fixes + calibrated control effectors)."""
import math

import numpy as np
import pytest

from vtx.aircraft import DT
from vtx.phantom.controls import FlightControl
from vtx.phantom.params import DEFAULT_VARIANT, Params
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.surface_aero import SurfaceAero
from vtx.world import TestWorld

P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}


def test_a10b_is_the_default_phantom_and_a10a_stays_reproducible():
    assert DEFAULT_VARIANT == 'phantom-a10b'
    b = Params('phantom-a10b'); a = Params('phantom-fx')
    assert b.variant_info['release_stage'] == 'current_prototype' and a.variant_info['release_stage'] == 'previous_prototype'
    # A10-A as flown (66 of the 72 register runs) and its P6-off sibling keep their configuration identity
    assert Params('phantom-fx', P6).config_sha256.startswith('70089cca')
    assert a.config_sha256.startswith('b835295b')
    assert b.config_sha256 != Params('phantom-fx', P6).config_sha256


def test_a10b_composition():
    P = Params('phantom-a10b')
    assert P['proposals.p6_drs_stabilator'] == 1.0 and P['proposals.p8_wing_incidence_deg'] == 7.0
    for flag in ('aero.hull_lift.enabled', 'suspension.enabled', 'drive.limits_enabled', 'effectors.enabled', 'fbw_wingborne.enabled'):
        assert P[flag] == 1.0, flag
    assert P['effectors.canard_rate_deg_s'] == 70.0 and P.label('effectors.canard_rate_deg_s') == 'MANUFACTURER'   # Moog Model 965
    assert P['effectors.steering.rack_force_n'] == 11000.0 and P.label('effectors.steering.rack_force_n') == 'MANUFACTURER'
    a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road')
    assert {'pod_FL_steer', 'pod_FR_steer', 'pod_FL_susp', 'pod_RR_susp'} <= set(a.jid)
    added = sum(c['mass_kg'] for c in P['effectors.added_components'])
    base = PhantomAircraft(TestWorld(), 'phantom-fx', overrides=P6, start_configuration='road').mass_properties()['mass_kg']
    assert a.mass_properties()['mass_kg'] == pytest.approx(base + added, abs=0.05)
    assert a.provenance['revision'] == 'phantom-a10b'


def test_a10a_has_none_of_the_a10b_systems():
    a = PhantomAircraft(TestWorld(), 'phantom-fx', overrides=P6, start_configuration='road')
    assert not any(n.endswith(('_steer', '_susp')) for n in a.jid) and not a.eff
    assert SurfaceAero(a.P).rudder_tau == 0.0 and SurfaceAero(a.P).hull is None


def test_front_steering_turns_toward_the_yaw_stick():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10b', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4))
    while float(a.vel_body()[0]) < 8.0:
        a.step()
    a.set_command(dict(wheel_drive=[0.25] * 4, yaw=1.0))                   # yaw +1 = nose right
    psi0 = a.attitude()['yaw_left']
    for _ in range(int(2.0 / DT)):
        a.step()
    assert math.degrees(a.attitude()['yaw_left'] - psi0) < -30.0          # turned right (nose-left heading decreases)
    steer = math.degrees(a.joint('pod_FL_steer')[0])
    assert -a.P['effectors.steering.max_deg'] <= steer < -3.0              # wheels to the right, within the lock
    L = abs(a.L.bodies['pod_FL_wheel'].anchor[0] - a.L.bodies['pod_RL_wheel'].anchor[0]); u = float(a.vel_body()[0])
    assert abs(steer) <= math.degrees(math.atan(L * 0.8 * 9.80665 / (u * u))) + 1.0    # speed schedule: 0.8 g lateral limit


def test_rudder_and_booster_vectoring_push_the_right_way():
    a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road')
    a.fcc.last = dict(moment_demand=[0.0, 1.0, 1.0])                      # full nose-up and nose-right demand
    a.effector_update(1.0, a.fcc.cmd, 0.0)
    assert a.tvc[0] < 0 and a.tvc[1] > 0                                  # thrust tilted down (tail down = nose up), toward +y
    assert math.hypot(*a.tvc) <= math.radians(a.P['effectors.tvc.travel_deg']) + 1e-9
    assert a.rudder == pytest.approx(math.radians(a.P['effectors.rudder.travel_deg']))
    SA = SurfaceAero(a.P); V = 60.0
    st = dict(wing_frac=dict(left=1., right=1.), wing_locked=dict(left=True, right=True), flap=dict(left=0., right=0.), aileron=dict(left=0., right=0.),
              canard_pitch=dict(left=0., right=0.), canard_deployed=dict(left=True, right=True), stab_te_up=0.1)
    r0 = SA.compute(np.array([V, 0, 0]), np.zeros(3), np.zeros(3), dict(st, rudder=0.0))
    r1 = SA.compute(np.array([V, 0, 0]), np.zeros(3), np.zeros(3), dict(st, rudder=math.radians(20)))
    assert r1['force_body'][1] - r0['force_body'][1] > 0                   # + rudder -> side force +y at the tail
    assert r1['moment_body'][2] - r0['moment_body'][2] < 0                 # -> nose right


def test_wingborne_law_blends_in_with_dynamic_pressure():
    from vtx.phantom.propulsion import DuctedFan
    for v, expect in (('phantom-a10b', (0.0, 1.0)), ('phantom-fx', (0.0, 0.0))):
        P = Params(v); f = FlightControl(P, DuctedFan.pod(P), 0)
        assert (f.wingborne_blend(dict(qdyn=0.0)), f.wingborne_blend(dict(qdyn=3000.0))) == expect


def test_wing_deployment_guard():
    a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road'); hl = a.P.handover['control_limits']
    q20 = 0.5 * 1.225 * 20.0 ** 2
    a.accel_est = 4.0; assert not a.deploy_window_ok(q20, hl)          # 20 m/s + 4 m/s2 x 5.5 s -> lock above 31 m/s
    a.accel_est = 0.0; assert a.deploy_window_ok(q20, hl)              # coasting at 20 m/s: lock at 245 Pa
    a.wing_state = {'left': 'hatch_opening', 'right': 'hatch_opening'}
    a.fcc.cmd['wing'] = 'deploy'
    a.wing_sequencer(0.01, 700.0)                                       # blocked above the 600 Pa transit limit
    assert a.wing_state['left'] in ('hatch_closing', 'stowed')          # the hatch closes instead of staying open
    assert any(e.get('event') == 'wing_hatch_closed_by_q' for e in a.events)
    a.wing_sequencer(0.01, 700.0)                                       # the standing deploy request is then refused
    assert a.wing_state['left'] in ('hatch_closing', 'stowed') and 'deploy_inhibited_q' in a.flags


def test_steering_is_mechanical_tyre_forces_turn_the_car():
    """No scripted yaw: with the tyre friction removed, the same steering input does not turn the car."""
    def heading_change(friction):
        w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10b', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
        a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4))
        while float(a.vel_body()[0]) < 8.0:
            a.step()
        for g in [f'tyre_{k}' for k in ('FL', 'FR', 'RL', 'RR')] + ['terrain']:   # MuJoCo uses the larger of the pair
            a.model.geom_friction[a.gid[g]][0] = friction
        a.set_command(dict(wheel_drive=[0.0] * 4, yaw=1.0)); psi0 = a.attitude()['yaw_left']
        for _ in range(int(1.5 / DT)):
            a.step()
        return math.degrees(a.attitude()['yaw_left'] - psi0), math.degrees(a.joint('pod_FL_steer')[0])
    turned, steer_on = heading_change(1.0)
    slid, steer_off = heading_change(0.0)
    assert turned < -15.0 and abs(slid) < 2.0                              # the turn comes from tyre-road friction
    assert steer_on < -3.0 and steer_off < -3.0                            # the wheels are steered in both cases


def test_steering_stays_centred_in_vtol_and_locks_for_takeoff():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10b', start_configuration='vtol'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(stability_mode='attitude_vs', collective=1.0, vertical_speed_m_s=1.5, yaw=1.0, brake=[0.0] * 4))
    for _ in range(int(3.0 / DT)):
        a.step()
    assert all(abs(math.degrees(a.joint(f'pod_{k}_steer')[0])) < 0.5 for k in ('FL', 'FR'))
    r = PhantomAircraft(w, 'phantom-a10b', start_configuration='road'); r.spawn(0, 0, w.surface_z(0, 0))
    r.set_command(dict(wing='deploy', canard_fold='deployed', yaw=1.0, brake=[1.0] * 4))
    for _ in range(int(3.0 / DT)):
        r.step()
    assert r.wing_state['left'] != 'stowed'
    assert abs(math.degrees(r.joint('pod_FL_steer')[0])) <= r.P['effectors.steering.takeoff_lock_deg'] + 0.3
