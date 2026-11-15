"""Regression: A10-C must not lift its front wheels when wings are deployed."""
import math
import numpy as np
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.params import Params
from vtx.phantom import identity
from vtx.world import TestWorld


def test_a10c_wings_extend_without_nose_struts_or_loss_of_wheel_support():
    assert Params('phantom-a10c').get('suspension.nose_lift_m', 0.0) == 0.0
    assert Params('phantom-a10b').get('suspension.nose_lift_m', 0.0) == 0.0
    assert identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road'))['verified']
    w = TestWorld()
    a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
    assert not any('nose_strut_actuator' in c['id'] for c in a.L.records())
    a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[1.0] * 4, wheel_drive=[0.0] * 4,
                       wing='deploy', canard_fold='deployed'))
    samples = []
    for i in range(int(10 / DT)):
        a.step()
        if i % 40 == 0 and i * DT >= 7:
            obs = a.sensor_observation(np.random.default_rng(i))
            samples.append((obs['attitude_deg']['pitch'],
                            obs['tyre_contact'],
                            obs['wing_state']))
    print('FINAL', samples[-1])
    print('CONTACT_RATES', {k: sum(x[1][k] for x in samples) / len(samples)
                            for k in ('FL', 'FR', 'RL', 'RR')})
    assert samples[-1][2] == {'left': 'locked', 'right': 'locked'}
    assert max(abs(s[0]) for s in samples) < 0.6
    for corner in ('FL', 'FR', 'RL', 'RR'):
        assert sum(s[1][corner] for s in samples) / len(samples) >= 0.9
