"""Road wheel support and distinct current/flown A10-C spring-seat policies.

The take-off-stance overlay adds 0.20 m of available front spring-seat travel;
it does not remove the wheels or give every A10-C revision the same trigger.
"""
import math
import numpy as np
import pytest
from vtx.aircraft import DT
from vtx.phantom.flight_revisions import flight_revision
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.params import Params
from vtx.phantom import identity
from vtx.world import TestWorld


def test_current_a10c_wings_extend_at_rest_without_activating_nose_lift_or_losing_wheel_support():
    assert Params('phantom-a10c')['suspension.nose_lift_m'] == pytest.approx(0.20)
    assert Params('phantom-a10b').get('suspension.nose_lift_m', 0.0) == 0.0
    assert identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road'))['verified']
    w = TestWorld()
    a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
    assert {'nose_strut_actuator_left', 'nose_strut_actuator_right'} <= {c['id'] for c in a.L.records()}
    a.spawn(0, 0, w.surface_z(0, 0))
    a.set_command(dict(brake=[1.0] * 4, wheel_drive=[0.0] * 4,
                       wing='deploy', canard_fold='deployed'))
    samples = []
    for i in range(int(10 / DT)):
        a.step()
        if i % 40 == 0 and i * DT >= 7:
            assert a.nose_lift == 0.0
            # A vertical road wheel has a horizontal axle; wing deployment
            # must not rotate the four road-wheel pods into VTOL stance.
            for corner in ('FL', 'FR', 'RL', 'RR'):
                axis = a.data.geom_xmat[a.gid[f'tyre_{corner}']].reshape(3, 3)[:, 2]
                assert abs(axis[2]) < math.sin(math.radians(5))
            obs = a.sensor_observation(np.random.default_rng(i))
            samples.append((obs['attitude_deg']['pitch'],
                            obs['tyre_contact'],
                            obs['wing_state']))
    assert samples[-1][2] == {'left': 'locked', 'right': 'locked'}
    assert max(abs(s[0]) for s in samples) < 0.6
    for corner in ('FL', 'FR', 'RL', 'RR'):
        assert sum(s[1][corner] for s in samples) / len(samples) >= 0.9


@pytest.mark.parametrize('variant,speed,pod_degrees,wing_state,extends', [
    ('phantom-a10b', 75.0, 0.0, 'locked', False),
    ('phantom-a10c', 74.9, 0.0, 'locked', False),
    ('phantom-a10c', 75.0, 0.0, 'locked', True),
    ('phantom-a10c', 75.0, 90.0, 'locked', False),
    ('phantom-a10c', 75.0, 0.0, 'stowed', False),
    ('phantom-a10c-runway-20261112', 0.0, 0.0, 'locked', True),
    ('phantom-a10c-vtol-20261112', 0.0, 0.0, 'locked', True),
])
def test_front_spring_seat_uses_the_selected_revision_policy_without_moving_wheel_joints(
        variant, speed, pod_degrees, wing_state, extends):
    # Direct policy-state fixtures, not a scheduled take-off. The flown
    # registry intentionally preserves wing-triggered extension at rest;
    # current development adds the 75 m/s gate. B keeps its original zero lift.
    revision = flight_revision(variant)
    if revision:
        assert revision['nose_strut'] == 'deploy_with_wing_in_road_stance'
        assert revision['base_variant'] == 'phantom-a10c'
    a = PhantomAircraft(TestWorld(), variant, start_configuration='road')
    a.wing_state = dict(left=wing_state, right=wing_state)
    a.data.qvel[:3] = a.R() @ np.array([speed, 0.0, 0.0])
    for corner in ('FL', 'FR', 'RL', 'RR'):
        a.data.qpos[a.model.jnt_qposadr[a.jid[f'pod_{corner}']]] = math.radians(pod_degrees)
    positions = a.data.qpos.copy()
    springs = a.model.qpos_spring.copy()
    ranges = a.model.jnt_range.copy()
    dt = 0.1
    a.nose_strut_update(dt)
    expected = Params(variant).get('suspension.nose_lift_rate_m_s', 0.05) * dt if extends else 0.0
    assert a.nose_lift == pytest.approx(expected)
    np.testing.assert_array_equal(a.data.qpos, positions)
    for corner in ('FL', 'FR', 'RL', 'RR'):
        joint = a.jid[f'pod_{corner}_susp']
        qadr = a.model.jnt_qposadr[joint]
        shift = expected if corner in ('FL', 'FR') else 0.0
        assert a.model.qpos_spring[qadr] == pytest.approx(springs[qadr] - shift)
        np.testing.assert_allclose(a.model.jnt_range[joint], ranges[joint] - shift, atol=1e-12, rtol=0)
