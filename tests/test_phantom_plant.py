"""Phantom MuJoCo plant: compiles, joint axes, gear stability, freefall, thrust/gyro, contact (canned inputs, not flights)."""
import math, sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'phantom'))
import phantom_bench as B
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS, SIDE


def test_compiles_and_all_bodies_positive_definite():
    a = PhantomAircraft(B.W, 'phantom')
    m = a.model
    assert m.nbody > 20 and m.nu > 10
    for i in range(1, m.nbody):
        if m.body_mass[i] > 0:
            assert (m.body_inertia[i] > 0).all(), m.body(i).name


def test_pod_hinges_about_body_x_and_fan_axis_follows_tilt():
    a = PhantomAircraft(B.W, 'phantom')
    for k in PODS:
        j = a.jid[f'pod_{k}']
        assert np.allclose(np.abs(a.model.jnt_axis[j]), [1, 0, 0])
    a.spawn(0, 0, 0)
    for k in PODS:   # VTOL stance: thrust axis vertical
        assert a.pod_axis(k)[2] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize('variant', ['phantom', 'phantom-fx'])
def test_zero_power_stays_on_gear(variant):
    r = B.zero_power(variant)
    assert r['vtol']['passed'] and r['road']['passed'], r


def test_fixture_freefall():
    assert B.freefall('phantom')['passed']


def test_thrust_direction_and_gyro_sign():
    r = B.thrust_and_gyro('phantom')
    assert r['thrust_direction']['passed'] and r['gyro_sign']['passed'], r


def test_leg_retract_and_roll_brake_without_pose_jumps():
    r = B.contact_jumps('phantom')
    assert r['passed'], r
    assert r['rolling_speed_m_s'] > 0.5 and r['after_brake_speed_m_s'] < 0.05
