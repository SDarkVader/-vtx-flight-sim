"""Automatic law selection by flight phase (stability_mode 'auto', the default): the FCC picks the law from sensed
state and logs phase and resolved law; on the ground the yaw-rate loop reaches the nosewheels."""
import math

import numpy as np

from vtx.aircraft import DT
from vtx.phantom import identity
from vtx.phantom.controls import MODES, PHASES, PHASE_LAW, default_command
from vtx.phantom.plant import GROUND_YAW_DAMPING_DEG_PER_RAD_S, PhantomAircraft
from vtx.world import TestWorld


def _run(a, t):
    for _ in range(int(t / DT)):
        a.step()


def test_auto_is_the_default_and_the_explicit_modes_remain():
    assert default_command()['stability_mode'] == 'auto' and default_command('road')['stability_mode'] == 'auto'
    assert MODES[0] == 'auto' and {'off', 'rate_damping', 'attitude', 'attitude_vs'} <= set(MODES)
    assert set(PHASE_LAW) == set(PHASES) and all(v in MODES and v != 'auto' for v in PHASE_LAW.values())
    # the pinned canonical aircraft is untouched by the law selection (code only; parameters and model unchanged)
    assert identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road'))['verified']


def test_phase_follows_the_sensed_state_on_the_a10c():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[1.0] * 4)); _run(a, 1.0)
    assert a.fcc.phase == 'ground' and a.fcc.mode_resolved == PHASE_LAW['ground'] and a.fcc.last['mode'] == 'auto'
    a.set_command(dict(wing='deploy', canard_fold='deployed')); _run(a, 8.0)
    assert a.fcc.phase == 'takeoff_roll'
    obs = a.sensor_observation(np.random.default_rng(0))
    assert obs['stability_mode'] == 'auto' and obs['flight_phase'] == 'takeoff_roll' and obs['stability_mode_resolved'] == PHASE_LAW['takeoff_roll']
    b = PhantomAircraft(w, 'phantom-a10c', start_configuration='vtol'); b.spawn(0, 0, w.surface_z(0, 0))
    b.set_command(dict(brake=[1.0] * 4)); _run(b, 0.5)
    assert b.fcc.phase == 'hover'                                   # pods in fan mode: hover law, on the ground or not
    b.set_command(dict(collective=0.9)); _run(b, 6.0)
    assert b.airborne and b.fcc.phase == 'hover'
    b.set_command(dict(pod_tilt_deg=[0.0] * 4)); _run(b, 0.9)                  # 72 deg/s tilt rate: about 25 deg here
    assert b.fcc.phase == 'transition'                              # pods mid-travel
    _run(b, 2.0)
    assert b.fcc.phase == 'wingborne'                               # pods road, airborne
    # an explicit mode is honoured as before and is reported as both commanded and resolved
    b.set_command(dict(stability_mode='rate_damping')); _run(b, 0.1)
    assert b.fcc.last['mode'] == 'rate_damping' and b.fcc.mode_resolved == 'rate_damping'


def test_ground_law_steers_the_nosewheels_against_a_yaw_rate_only_in_auto():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[0.5] * 4, wing='deploy', canard_fold='deployed')); _run(a, 6.0)
    assert a.fcc.phase == 'takeoff_roll' and a.support_count() > 0
    lock = a.P['effectors.steering.takeoff_lock_deg']
    for mode, expect_feedback in (('auto', True), ('attitude', False)):
        a.set_command(dict(stability_mode=mode, yaw=0.0)); _run(a, 0.05)
        a.fcc.last['yaw_rate_left'] = -0.2                           # sensed: nose swinging right at 0.2 rad/s
        for _ in range(50):
            a.effector_update(0.01, a.fcc.cmd, float(a.vel_body()[0]))
        tgt = math.degrees(a.targets['pod_FL_steer'])
        if expect_feedback:
            assert tgt > 0.5 and tgt <= lock + 1e-6                 # wheels steered LEFT to oppose the nose-right rate, inside the lock
            assert tgt == min(lock, GROUND_YAW_DAMPING_DEG_PER_RAD_S * 0.2) or tgt <= lock
        else:
            assert abs(tgt) < 0.05                                   # explicit mode: stick only, no feedback path
