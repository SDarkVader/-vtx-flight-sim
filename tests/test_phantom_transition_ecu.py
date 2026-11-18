"""Transition ECU (inputs/phantom_overlays/transition_ecu_v1.json): fan-assisted air-braking into hover.

The ECU is opt-in. Aircraft that do not load the overlay keep their configuration identity and behaviour; with the
overlay the pilot's 'airbrake' command hands the fans, pods, boosters, spoilerons, DRS stabilator and the attitude,
vertical-speed and turn loops to the ECU, while stick, pedal and vertical-speed inputs remain the pilot's."""
import json, math, sys

import numpy as np
import pytest

from vtx.phantom import overlays
from vtx.phantom.params import Params, ROOT
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld

sys.path.insert(0, str(ROOT / 'tools/phantom'))
import a10c_airbrake_test as manoeuvre   # noqa: E402  (the reproducible engineering test; reused for its set-up)

A10C_CONFIG = '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f'   # live A10-C identity (18 Nov 2026)
G = 9.80665


def ecu():
    return overlays.load('transition_ecu_v1')


def test_ecu_is_opt_in_and_leaves_the_a10c_identity_alone():
    base = Params('phantom-a10c')
    assert base.config_sha256 == A10C_CONFIG
    assert 'fbw_transition' not in base.tree and base.get('fbw_transition.enabled', 0.0) == 0.0
    fitted = Params('phantom-a10c', ecu())
    assert fitted.config_sha256 != A10C_CONFIG                     # a different control law is a different identity
    world = TestWorld()
    plain, with_ecu = PhantomAircraft(world, 'phantom-a10c'), PhantomAircraft(world, 'phantom-a10c', overrides=ecu())
    assert not plain.fcc.transition and with_ecu.fcc.transition
    assert plain.provenance['model_xml_sha256'] == with_ecu.provenance['model_xml_sha256']   # software only: same airframe


def test_airbrake_is_refused_and_reported_on_an_aircraft_without_the_ecu():
    a = PhantomAircraft(TestWorld(), 'phantom-a10c')
    before = json.loads(json.dumps(a.command))
    a.set_command(dict(airbrake='on'))
    assert a.events[-1]['event'] == 'airbrake_unavailable'
    assert 'airbrake' not in a.command and a.command == before          # nothing else is changed on its behalf
    assert 'transition_ecu' not in a.physical_snapshot()['phantom']


def test_airbrake_engagement_configures_the_transition_and_release_returns_control():
    a = PhantomAircraft(TestWorld(), 'phantom-a10c', overrides=ecu())
    a.set_command(dict(stability_mode='attitude', collective=0.1, booster_throttle=[0.8, 0.8], pod_tilt_deg=[0.0] * 4))
    a.set_command(dict(airbrake='on'))
    c = a.command
    assert c['airbrake'] == 'on' and c['pod_tilt_deg'] == [90.0] * 4 and c['booster_throttle'] == [0.0, 0.0]
    assert c['stability_mode'] == 'attitude_vs' and c['vertical_speed_m_s'] == 0.0 and c['collective'] >= 0.5
    assert a.events[-1] == dict(a.events[-1], event='airbrake', state='on')
    a.set_command(dict(airbrake='on', vertical_speed_m_s=-1.0, yaw=0.3))   # pilot inputs stay the pilot's
    assert a.command['vertical_speed_m_s'] == -1.0 and a.command['yaw'] == 0.3
    a.set_command(dict(airbrake='off'))
    assert a.command['airbrake'] == 'off' and a.command['pod_tilt_deg'] == [90.0] * 4   # release changes nothing else
    assert not a.fcc.airbrake_engaged()
    assert a.physical_snapshot()['phantom']['transition_ecu']['airbrake'] == 'off'


def test_a_dormant_ecu_does_not_change_the_physics_or_the_random_sequence():
    world = TestWorld(); runs = []
    for ov in (None, ecu()):
        a = PhantomAircraft(world, 'phantom-a10c', start_configuration='vtol', overrides=ov)
        a.spawn(0, 0, world.surface_z(0, 0)); a.set_command(dict(stability_mode='attitude', collective=0.3))
        for _ in range(800):
            a.step()
        runs.append(a)
    plain, fitted = runs
    np.testing.assert_array_equal(plain.data.qpos, fitted.data.qpos)
    np.testing.assert_array_equal(plain.data.qvel, fitted.data.qvel)
    assert plain.rng.bit_generator.state == fitted.rng.bit_generator.state


def braking(seconds):
    a = manoeuvre.build('on', 'reference'); d = a.data; t0 = float(d.time); z0 = float(d.qpos[2])
    a.set_command(dict(airbrake='on', pitch=0.0))
    log = []
    for i in range(int(round(seconds / manoeuvre.DT))):
        a.step()
        if i % 20 == 0:
            log.append(manoeuvre.row(a, t0, z0))
    return a, log


def test_checkpoint_continues_the_same_physics_with_the_ecu_engaged():
    original, _ = braking(1.0)
    snapshot = json.loads(json.dumps(original.checkpoint_state(), allow_nan=False))
    assert snapshot['evolving']['transition_ecu']['other_lift_est_n'] > 0
    restored = PhantomAircraft(manoeuvre.FlatWorld(), manoeuvre.VARIANT, start_configuration='road', overrides=ecu())
    restored.restore_state(snapshot)
    for k, v in original.fcc.ecu_state().items():
        assert restored.fcc.ecu_state()[k] == v
    for _ in range(400):
        original.step(); restored.step()
    np.testing.assert_allclose(restored.data.qpos, original.data.qpos, rtol=1e-8, atol=1e-7)
    np.testing.assert_allclose(restored.data.qvel, original.data.qvel, rtol=1e-8, atol=1e-7)


def test_braking_regression_against_the_9_nov_reference():
    """95 m/s, pods at 90 deg, boosters off: 9 Nov A10-B reference 51.1 m/s at 6 s, peak 0.81 g, nose about +4 deg."""
    a, L = braking(6.2)
    u6 = min(L, key=lambda r: abs(r['t'] - 6.0))['u']
    k = 20
    peak = max((L[i]['u'] - L[i + k]['u']) / (L[i + k]['t'] - L[i]['t']) / G for i in range(len(L) - k))
    late = [r for r in L if r['t'] >= 1.5]
    assert 44.0 < u6 < 52.0
    assert peak < 0.9
    assert all(2.0 < r['pitch'] < 5.5 for r in L if r['t'] >= 0.5)
    assert max(abs(r['alt']) for r in L) < 1.5
    assert all(min(r['tilt']) > 88.0 and max(r['booster_T']) == 0.0 for r in L)
    assert max(r['stab'] for r in late) > 40.0 and max(max(r['ail']) for r in late) < -8.0   # DRS airbrake and spoilerons out
    assert not any(r['saturated'] for r in L) and max((r['unmet_w'] or 0) for r in L) == 0
