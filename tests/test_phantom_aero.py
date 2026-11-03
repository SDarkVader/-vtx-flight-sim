"""Phantom surface aero: quasi-steady per-surface model sign and scaling checks."""
import math
import numpy as np
import pytest
from vtx.phantom.params import Params
from vtx.phantom.surface_aero import SurfaceAero

A = SurfaceAero(Params('phantom'))


def state(frac=1.0, locked=True, flap=0.0, ail=(0.0, 0.0), canard=0.0, deployed=True):
    return dict(wing_frac=dict(left=frac, right=frac), wing_locked=dict(left=locked, right=locked), flap=dict(left=flap, right=flap),
                aileron=dict(left=ail[0], right=ail[1]), canard_pitch=dict(left=canard, right=canard), canard_deployed=dict(left=deployed, right=deployed))


def F(v, s, w=(0, 0, 0)):
    return A.compute(np.array(v, float), np.array(w, float), np.zeros(3), s)


def test_zero_force_at_zero_airspeed():
    r = F([0, 0, 0], state())
    assert np.allclose(r['force_body'], 0) and np.allclose(r['moment_body'], 0)


def test_pre_stall_force_scales_with_q():
    alpha = math.radians(3)
    f = [F([V * math.cos(alpha), 0, -V * math.sin(alpha)], state())['force_body'] for V in (50, 75, 89.4)]
    assert f[1][2] / f[0][2] == pytest.approx((75 / 50) ** 2, rel=1e-6)
    assert f[2][2] / f[0][2] == pytest.approx((89.4 / 50) ** 2, rel=1e-6)
    assert f[0][2] > 0


def test_stall_reduces_lift_slope():
    lift = [F([40 * math.cos(math.radians(a)), 0, -40 * math.sin(math.radians(a))], state(deployed=False))['force_body'][2] for a in (5, 10, 35)]
    assert lift[1] > lift[0] and lift[2] < 2 * lift[1] * 35 / 10


def test_stowed_wing_gives_no_lift():
    s = state(frac=0.0, deployed=False)
    r = F([40, 0, -4], s)
    assert all(not x.get('active', True) for x in r['surfaces'] if x['name'].startswith('wing'))


def test_unlocked_wing_no_flap_or_aileron_increment():
    a = F([40, 0, -2], state(locked=False, flap=math.radians(30)))['force_body']
    b = F([40, 0, -2], state(locked=False, flap=0.0))['force_body']
    assert np.allclose(a, b)
    c = F([40, 0, -2], state(locked=True, flap=math.radians(30)))['force_body']
    assert c[2] > b[2]


def test_aileron_roll_sign():
    # left (+Y) aileron trailing-edge down, right up -> more lift on the left -> +Mx about body X (fwd),
    # which rotates +Y toward +Z: left side up, right side down = roll right (sim convention roll + = right down)
    r = F([40, 0, -2], state(ail=(math.radians(10), math.radians(-10))))
    assert r['moment_body'][0] > 0


def test_canard_pitch_sign():
    up = F([40, 0, 0], state(canard=math.radians(10), frac=0.0))['moment_body'][1]
    dn = F([40, 0, 0], state(canard=math.radians(-10), frac=0.0))['moment_body'][1]
    assert up < dn     # canard ahead of the CG: leading-edge-up raises the nose (negative My, X fwd / Z up)
