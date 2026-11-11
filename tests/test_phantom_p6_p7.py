"""Proposals P6 (DRS flap as an all-moving stabilator) and P7 (turbine boosters from datasheets): both off by default."""
import math

import numpy as np
import pytest

from vtx.aircraft import DT
from vtx.phantom.params import Params
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.surface_aero import SurfaceAero
from vtx.world import TestWorld

P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}, 'p5_canard_area_scale': {'v': 0.5}}}
TJ150 = {'proposals': {'p7_booster_engine': {'v': 1.0}}}
FJ33 = {'proposals': {'p7_booster_engine': {'v': 2.0}}}


def cm_alpha(overrides):
    """whole-vehicle dCm/dalpha about the ledger CG (per rad), wings locked, flaps 0, canards deployed at 0, 60 m/s."""
    P = Params('phantom', overrides)
    a = PhantomAircraft(TestWorld(), 'phantom', overrides=overrides, start_configuration='road')
    cg = np.array(a.mass_properties()['cg_body_m'])
    SA = SurfaceAero(P); V = 60.0
    w = P.handover['aero_surfaces']['wing']; q = 0.5 * SA.rho * V * V
    cms = []
    for al in (0.0, 4.0):
        th = math.radians(al); vb = np.array([V * math.cos(th), 0.0, -V * math.sin(th)])
        st = dict(wing_frac=dict(left=1.0, right=1.0), wing_locked=dict(left=True, right=True), flap=dict(left=0.0, right=0.0),
                  aileron=dict(left=0.0, right=0.0), canard_pitch=dict(left=0.0, right=0.0), canard_deployed=dict(left=True, right=True),
                  stab_te_up=math.radians(P['proposals.p6_stab_rest_te_up_deg']))
        r = SA.compute(vb, np.zeros(3), np.zeros(3), st)
        M = r['moment_body'] - np.cross(cg, r['force_body'])
        cms.append(-M[1] / (q * w['S_ref_m2'] * w['mac_m']))        # +y moment is nose-down in this frame
    return (cms[1] - cms[0]) / math.radians(4.0)


def test_proposals_default_off():
    P = Params('phantom')
    assert P['proposals.p6_drs_stabilator'] == 0 and P['proposals.p7_booster_engine'] == 0
    assert not any(s.kind == 'stab' for s in SurfaceAero(P).surfaces)
    a = PhantomAircraft(TestWorld(), 'phantom')
    assert a.jet is None and not a.p6
    assert a.physical_snapshot()['phantom']['booster_engine'] == 'edf'


def test_p6_makes_the_airframe_statically_stable():
    base, prop = cm_alpha(None), cm_alpha(P6)
    assert base > 0.3            # as drawn: unstable (campaign: +0.72/rad with flaps 30)
    assert prop < 0.0            # stabilator + half canard area: stable


def test_p6_actuator_tracks_the_fbw_pitch_demand_at_its_rate():
    a = PhantomAircraft(TestWorld(), 'phantom', overrides=P6, start_configuration='road')
    a.spawn(0, 0, TestWorld().surface_z(0, 0))
    rest = a.P['proposals.p6_stab_rest_te_up_deg']
    assert math.isclose(math.degrees(a.stab_te_up), rest)
    a.set_command(dict(stability_mode='off', pitch=1.0, brake=[1.0] * 4))
    for _ in range(int(0.05 / DT)):
        a.step()
    moved = math.degrees(a.stab_te_up) - rest
    assert 0 < moved <= a.P['proposals.p6_stab_rate_deg_s'] * 0.05 + 1.0      # rate limited
    for _ in range(int(0.6 / DT)):
        a.step()
    assert math.isclose(math.degrees(a.stab_te_up), rest + 15.0, abs_tol=0.5)  # full demand = +15 deg
    assert a.physical_snapshot()['phantom']['drs_deg'] == pytest.approx(rest + 15.0, abs=0.5)


def test_p7_tj150_static_thrust_spool_fuel_and_no_electrical_draw():
    def run(throttle, seconds):
        a = PhantomAircraft(TestWorld(), 'phantom', overrides=TJ150, start_configuration='road')
        a.spawn(0, 0, TestWorld().surface_z(0, 0))
        a.set_command(dict(brake=[1.0] * 4, booster_throttle=[throttle, throttle]))
        f0 = a.fuel.sum(); trace = []
        for i in range(int(seconds / DT)):
            a.step()
            if i % 4 == 0:
                trace.append((i * DT, sum(s.get('thrust_n', 0.0) for s in a.booster_state)))
        return a, f0 - a.fuel.sum(), trace
    a, burned_on, tr = run(1.0, 12.0)
    _, burned_off, _ = run(0.0, 12.0)
    T = tr[-1][1]
    assert T == pytest.approx(4 * 1500.0, rel=0.02)                                 # datasheet: 4 x 1,500 N static
    t90 = next(t for t, x in tr if x >= 0.9 * T)
    assert t90 == pytest.approx(5.0, abs=0.3)                                        # t90 from the TJ80 anchor
    assert all(s.get('power_w', 0.0) == 0.0 for s in a.booster_state)               # no bus draw
    expected = sum(0.118 * x / 3600 * 4 * DT for _, x in tr)                         # SFC x thrust, integrated
    assert burned_on - burned_off == pytest.approx(expected, rel=0.05)
    assert a.mass_properties()['mass_kg'] > PhantomAircraft(TestWorld(), 'phantom').mass_properties()['mass_kg']


def test_p7_lapse_and_fj33_option():
    a = PhantomAircraft(TestWorld(), 'phantom', overrides=FJ33, start_configuration='road')
    j = a.jet
    assert j['kind'] == 'fj33' and j['t0_station_n'] == pytest.approx(4100.0)       # one 8.2 kN engine split over 2 stations
    assert j['tau_s'] * math.log(10) == pytest.approx(5.0)                         # 14 CFR 33.73(b) bound used as t90
    lapse95 = 1 - 95 / a.P['proposals.p7_fj33_jet_velocity_m_s']
    assert 0.70 < lapse95 < 0.80
