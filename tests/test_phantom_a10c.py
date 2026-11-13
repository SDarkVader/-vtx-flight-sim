"""Phantom A10-C (development): A10-B + turbojet boosters + take-off stance nose strut, for take-off without the lift fans."""
import math

import pytest

from vtx.aircraft import DT
from vtx.phantom import identity
from vtx.phantom.params import DEFAULT_VARIANT, Params
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld


def test_a10c_is_a10b_plus_turbojets_and_nose_strut_and_a10b_is_unchanged():
    b = Params('phantom-a10b'); c = Params('phantom-a10c')
    assert DEFAULT_VARIANT == 'phantom-a10b' and b.config_sha256.startswith('3ecae1a9')            # the canonical model is untouched
    assert identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road'))['verified']
    assert c.variant_info['release_stage'] == 'development_prototype' and c.config_sha256 != b.config_sha256
    assert c['proposals.p7_booster_engine'] == 1.0 and c['suspension.nose_lift_m'] == 0.2
    assert b.get('suspension.nose_lift_m', 0.0) == 0.0 and b['proposals.p7_booster_engine'] == 0.0
    assert c.label('suspension.nose_lift_force_n') == 'MANUFACTURER'
    a = PhantomAircraft(TestWorld(), 'phantom-a10c', start_configuration='road')
    assert identity.verify(a)['pinned'] is False                                                    # development variant: not pinned
    ids = {r['id'] for r in a.L.records()}
    assert {'nose_strut_actuator_left', 'nose_strut_actuator_right'} <= ids


def _roll(a, t):
    for _ in range(int(t / DT)):
        a.step()


def test_nose_strut_extends_only_in_takeoff_stance():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[1.0] * 4)); _roll(a, 2.0)
    level = math.degrees(a.attitude()['pitch_up'])
    assert a.nose_lift == 0.0 and abs(level) < 0.6                                                  # road stance: strut retracted
    a.set_command(dict(wing='deploy', canard_fold='deployed')); _roll(a, 7.0)
    assert a.nose_lift == 0.0 and abs(math.degrees(a.attitude()['pitch_up']) - level) < 0.3     # parked with wings out: nose stays level
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[0.2] * 4)); _roll(a, 5.0)                    # take-off roll: strut extends
    assert a.nose_lift == pytest.approx(0.2, abs=1e-6)
    raised = math.degrees(a.attitude()['pitch_up'])
    assert raised - level == pytest.approx(math.degrees(math.atan(0.2 / 3.13)), abs=0.7)            # 0.20 m over the wheelbase
    assert a.physical_snapshot()['phantom']['nose_lift_m'] == pytest.approx(0.2, abs=1e-6)
    # A10-B has no strut and stays level with its wings out
    b = PhantomAircraft(w, 'phantom-a10b', start_configuration='road'); b.spawn(0, 0, w.surface_z(0, 0))
    b.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); _roll(b, 7.0)
    assert b.nose_lift == 0.0 and abs(math.degrees(b.attitude()['pitch_up'])) < 0.6


def test_a10c_takes_off_and_climbs_with_the_fans_off():
    w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
    x0 = -3500.0 if w.half > 3600 else -900.0
    a.spawn(x0, 0, w.surface_z(x0, 0)); z0 = float(a.data.qpos[2])
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0], wing='deploy', canard_fold='deployed',
                       flap_deg=[30.0, 30.0], stability_mode='attitude', pitch=0.0, collective=0.0))
    rotated = False; off = None; peak = 0.0
    while a.data.time < 34.0 and not a.crashed:
        _roll(a, 0.05)
        u = float(a.vel_body()[0]); pitch = math.degrees(a.attitude()['pitch_up']); peak = max(peak, abs(pitch))
        if not rotated and u >= 55.0:
            rotated = True; a.set_command(dict(pitch=0.7))
        if off is None and a.support_count() == 0 and float(a.data.qpos[2]) - z0 > 0.5:
            off = (float(a.data.time), u, float(a.data.qpos[0]) - x0); a.set_command(dict(wheel_drive=[0.0] * 4))
    assert not a.crashed and off is not None
    assert off[1] < 85.0 and off[2] < 1300.0                                                        # lifts off inside the 1,432 m runway
    assert float(a.data.qpos[2]) - z0 > 8.0 and float(a.data.qvel[2]) > 1.0                         # climbing at the end
    assert peak < 11.9                                                                              # below the tail-strike angle
    assert max(float(s.get('thrust_n', 0.0)) for s in a.fan_state) < 1.0                            # lift fans never used
