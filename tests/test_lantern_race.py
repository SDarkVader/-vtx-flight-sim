"""Vaderland 33 Lantern Race: rapid physics, point-to-point lines, fleet clocks and layout.

Isolated harbours and offline worlds only; never a live Laboratory.
"""
import json
import math

import numpy as np
import pytest

from vtx.course_timing import CourseTiming
from vtx.water.rapids import G, rapids_overlay
from vtx.world import make_world


def straight_rapid(speed=4., half_width=50., rocks=()):
    return dict(id='test', name='Test', stations=[[x, 0., half_width, speed] for x in range(0, 401, 50)], margin_m=12.,
                eddy_fraction=.28, boil_amplitude_m=0., waves=dict(from_m=100., to_m=300., amplitude_m=.5),
                rocks=list(rocks))


def test_current_eddies_and_compact_support():
    rapid = straight_rapid()
    _, vel, _, _, _ = rapids_overlay(rapid, np.array([200., 200., 200., 200.]), np.array([0., 49.5, -49.5, 80.]), 0.)
    assert vel[0, 0] == pytest.approx(4., abs=1e-9) and abs(vel[0, 1]) < 1e-9     # jet on the centreline
    assert vel[1, 0] < -.8 and vel[2, 0] < -.8                                     # counter-current eddies by both banks
    assert np.all(vel[3] == 0)                                                     # nothing beyond the margin
    eta, vel, acc, sx, sy = rapids_overlay(rapid, np.array([-30., 440., 200.]), np.array([0., 0., 200.]), 3.)
    assert np.all(eta == 0) and np.all(vel == 0) and np.all(acc == 0) and np.all(sx == 0) and np.all(sy == 0)


def test_standing_waves_are_stationary_with_consistent_slope():
    rapid = straight_rapid()
    x = np.arange(150., 250., .05)
    eta, vel, _, sx, _ = rapids_overlay(rapid, x, np.zeros_like(x), 0.)
    later, *_ = rapids_overlay(rapid, x, np.zeros_like(x), 7.3)
    np.testing.assert_allclose(eta, later)                                         # fixed in the ground frame
    crossings = x[1:][np.diff(np.sign(eta)) != 0]
    wavelength = 2 * np.mean(np.diff(crossings))
    assert wavelength == pytest.approx(2 * math.pi * 4. ** 2 / G, rel=.01)         # k = g / u^2
    np.testing.assert_allclose(sx[1:-1], np.gradient(eta, x)[1:-1], atol=2e-3)
    np.testing.assert_allclose(vel[:, 2], vel[:, 0] * sx, atol=1e-12)            # flow follows the surface


def test_rock_pillow_deflection_and_wake():
    r = 3.
    rapid = straight_rapid(rocks=[dict(x=200., y=0., r_m=r)])
    clear = straight_rapid()
    pts = np.array([[200 - 1.3 * r, 0.], [200 + 2 * r, 0.], [200 - .5 * r, 1.2 * r], [200 - .5 * r, -1.2 * r]])
    eta, vel, *_ = rapids_overlay(rapid, pts[:, 0], pts[:, 1], 0.)
    eta0, vel0, *_ = rapids_overlay(clear, pts[:, 0], pts[:, 1], 0.)
    assert eta[0] - eta0[0] == pytest.approx(.8 * 16 / (2 * G), rel=.05)          # stagnation pillow ~ u^2 / 2g
    assert vel[1, 0] < .5 * vel0[1, 0]                                             # slack water behind the rock
    assert vel[2, 1] > .5 and vel[3, 1] < -.5                                      # flow parts around it


def test_sprint_course_finishes_at_its_last_gate():
    course = dict(name='Sprint', sprint=True, gates=[dict(center=[x, 0., 7.], normal=[1., 0.], width_m=10.)
                                                     for x in (0., 50., 100.)])
    timing = CourseTiming([course])
    t = 0.
    for x in np.arange(-5., 106., 1.):
        t += .05
        timing.sample(t, (x, 0., 7.))
    run = timing.runs['Sprint']
    assert run['laps'] == 1 and run['last'] == run['best'] and run['start'] is None and run['next'] == 0
    assert run['last'] == pytest.approx(5., abs=.06) and len(run['splits']) == 1


def isolated_race_world():
    from test_harbour_fleet import harbour_world
    world = harbour_world()
    level = 7.
    marks = {}

    def gate(key, x, y, width=12.):
        ids = []
        for side in (-1, 1):
            ident = f'{key}-{"a" if side < 0 else "b"}'
            marks[ident] = dict(id=ident, kind='cylinder', center=[x, y + side * (width / 2 + .8), level],
                                half=[.55, .55, 3.], role='race-mark', landable=False)
            ids.append(ident)
        return dict(center=[x, y, level], normal=[1., 0.], width_m=width, marks=ids)

    start, finish = gate('start', -60., 0., 40.), gate('finish', 60., 0., 40.)
    races = [dict(id='line-' + key, name='Line ' + key.upper(), sprint=True, position=[-80., y], heading_rad=0.,
                  gates=[start, gate(key + '-1', -20., y), gate(key + '-2', 20., y), finish])
             for key, y in (('a', 10.), ('b', -10.))]
    world.harbour['timeTrial'] = dict(id='loop', name='Loop', position=[-80., 40.], heading_rad=0.,
                                      gates=[gate('loop-1', -40., 40.), gate('loop-2', 40., 40.)])
    world.harbour['races'] = races
    world.harbour['rapids'] = [dict(id='r', name='R', stations=[[x, 0., 30., 3.] for x in (-90., 0., 90.)],
                                    margin_m=8., eddy_fraction=.25, boil_amplitude_m=0., rocks=[])]
    world.obstacles.extend(marks.values())
    world.obstacles.append(dict(id='slick-ramp', kind='mesh', center=[0., -60., 7.], half=[4., 2., .5],
                                vertices=[[x, y, z] for x in (-4., 4.) for y in (-2., 2.) for z in (-.5, .5)],
                                faces=[[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                                       [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]],
                                planes=[], friction=.22, role='ramp', landable=True))
    return world


def test_lines_commit_finish_and_survive_checkpoint():
    from vtx.harbour_trial import LanternTrialFleet, fleet_type
    world = isolated_race_world()
    fleet = fleet_type(world)(world)
    assert isinstance(fleet, LanternTrialFleet) and len(fleet.races) == 2
    boat = 'ricochet-marina'
    lines = fleet.race_lines[boat]
    t = 0.
    for _ in range(80):
        fleet.step()                                         # 0.8 s of fleet time; samples below stay within it
    for x in np.arange(-66., -10., 4.):                     # start, then line A's first gate
        t += .05
        lines.sample(t, (x, 10., 7.))
        fleet._commit_line(boat)
    a, b = lines.runs['Line A'], lines.runs['Line B']
    assert a['next'] == 2 and a['start'] is not None
    assert b['start'] is None and b['next'] == 0             # committed to line A
    restored = LanternTrialFleet.restore(world, json.loads(json.dumps(fleet.serialize())))
    assert restored.public()['lantern_races'] == fleet.public()['lantern_races']
    lines = restored.race_lines[boat]
    for x in np.arange(-10., 66., 4.):
        t += .05
        lines.sample(t, (x, 10., 7.))
        restored._commit_line(boat)
    a = lines.runs['Line A']
    assert a['laps'] == 1 and a['last'] == a['best'] and a['start'] is None
    restored.reset_trial(boat, 'Course marker contact')
    assert restored.public()['lantern_races']['fouls'][boat] == 'Course marker contact'
    assert restored.public()['lantern_races']['runs'][boat]['Line A']['laps'] == 1


def test_race_staging_rapid_current_and_slick_ramp():
    from vtx.harbour_session import _restart_boat
    from vtx.harbour_trial import fleet_type
    world = isolated_race_world()
    fleet = fleet_type(world)(world)
    boat = 'ricochet-marina'
    fleet.select(boat)
    staged = _restart_boat(world, fleet, {'boatId': boat, 'raceId': 'line-b'})
    assert staged.public()['boats'][1]['position'][:2] == pytest.approx([-80., -10.], abs=1e-6)
    with pytest.raises(ValueError):
        _restart_boat(world, fleet, {'boatId': boat, 'raceId': 'no-such-line'})
    with pytest.raises(ValueError):
        _restart_boat(world, fleet, {'boatId': boat, 'raceId': 'line-a', 'timeTrial': True})
    water = fleet.water
    inside = water.evaluate(np.array([0.]), np.array([0.])).velocity[0]
    outside = water.evaluate(np.array([0.]), np.array([60.])).velocity[0]
    water.reconfigure(dict(rapids_enabled=False))
    calm = water.evaluate(np.array([0.]), np.array([0.])).velocity[0]
    assert inside[0] - calm[0] == pytest.approx(3., abs=.05)
    assert abs(outside[0] - calm[0]) < 1e-9
    geom = fleet.model.geom('airport_slick-ramp')
    assert geom.friction[0] == pytest.approx(.22) and geom.priority[0] == 1
    mark = fleet.model.geom('airport_start-a')
    assert geom.id != mark.id and mark.priority[0] == 0


@pytest.fixture(scope='module')
def worlds():
    return make_world('vaderland-32'), make_world('vaderland-33')


def inside_hull(o, p, pad=0.):
    q = np.asarray(p, float) - np.asarray(o['center'])
    planes = np.asarray(o['planes'])
    return bool(np.all(q @ planes[:, :3].T + planes[:, 3] <= pad))


def test_v32_harbour_is_unchanged(worlds):
    old, new = worlds
    assert 'races' not in old.harbour and 'rapids' not in old.harbour
    assert {k: v for k, v in new.harbour.items() if k not in ('races', 'rapids')} == old.harbour


def test_race_solids_are_rocks_ramps_marks_trees_and_the_deck(worlds):
    old, new = worlds
    added = new.obstacles[len(old.obstacles):]
    race = [o for o in added if o['id'].startswith('lr-')]
    assert {o['role'] for o in race} == {'rock', 'ramp', 'race-mark', 'conifer', 'architecture'}
    built = {o['id'] for o in race if o['role'] == 'architecture'}
    assert built == {'lr-overlook', 'lr-beacon-mast'} | {f'lr-banner-pole-{k}' for k in range(4)}
    level = new.harbour['waterLevelM']
    for o in race:
        if o['role'] == 'rock':                                  # seated on the bed, not floating
            low = o['center'][2] + min(v[2] for v in o['vertices'])
            assert low <= new.terrain_z(*o['center'][:2]) + .05, o['id']
        if o['role'] == 'conifer':
            x, y = o['center'][:2]
            assert not new.harbour_water_mask(np.array([x]), np.array([y]))[0] and new.terrain_z(x, y) > level + 1.5
    floating = [o for o in race if o.get('ramp', {}).get('floating')]
    assert len(floating) == 3 and all(o['friction'] == .22 for o in floating)


def test_every_line_is_open_deep_water_between_its_gates(worlds):
    _, new = worlds
    level = new.harbour['waterLevelM']
    blockers = [o for o in new.obstacles if o['id'].startswith('lr-') and o['role'] in ('rock', 'race-mark')
                and o['center'][2] + o['half'][2] > level - .4]
    assert len(new.harbour['races']) == 3
    for race in new.harbour['races']:
        assert race['sprint'] and race['gates'][0] == new.harbour['races'][0]['gates'][0]
        for a, b in zip(race['gates'], race['gates'][1:]):
            for f in np.linspace(0, 1, 60):
                x, y = (np.asarray(a['center'][:2]) * (1 - f) + np.asarray(b['center'][:2]) * f)
                assert new.harbour_water_mask(np.array([x]), np.array([y]))[0], race['name']
                assert level - new.terrain_z(x, y) > 1.2, (race['name'], x, y)
                for o in blockers:
                    if abs(o['center'][0] - x) < o['half'][0] + 3 and abs(o['center'][1] - y) < o['half'][1] + 3:
                        assert o['kind'] != 'mesh' or not inside_hull(o, [x, y, level - .2], pad=2.), (race['name'], o['id'])
                        if o['kind'] == 'cylinder':
                            assert math.hypot(o['center'][0] - x, o['center'][1] - y) > o['half'][0] + 2, (race['name'], o['id'])
        for gate in race['gates']:
            for key in gate['marks']:
                mark = next(o for o in new.obstacles if o['id'] == key)
                assert mark['role'] == 'race-mark' and mark['center'][2] + mark['half'][2] > level + 3


def test_trail_slipway_and_overlook(worlds):
    from vtx.mission_selection import MapPoint
    _, new = worlds
    level = new.harbour['waterLevelM']
    race = new.vaderland['lantern_race']
    trail = np.asarray(race['trail']['points'])
    assert not new.harbour_water_mask(trail[:, 0], trail[:, 1]).any()
    trunks = [o for o in new.obstacles if o['id'].startswith('lr-fir-')]
    assert len(trunks) > 200
    xy = np.array([o['center'][:2] for o in trunks])
    gaps = np.min(np.hypot(*(trail[:, None, :] - xy[None, :, :]).transpose(2, 0, 1)), axis=0)
    assert gaps.min() > race['trail']['width_m'] / 2 + 2
    slip = next(o for o in new.obstacles if o['id'] == 'lr-slipway')
    top = [np.asarray(slip['center']) + v for v in slip['vertices']]
    top = sorted(top, key=lambda p: -p[2])[:4]
    assert max(p[2] for p in top) > level + .3 and min(p[2] for p in top) < level - 1   # dry land down into the pool
    deck = race['overlook']['center']
    decision = new.validate(MapPoint(*deck[:2]), 'destination')
    assert decision.valid and abs(decision.terrain_z_m - deck[2]) < .05
    low_line = next(m for m in new.vaderland['missions'] if m['name'].endswith('Low Line'))
    assert [s['type'] for s in low_line['steps']] == ['hoop'] * 5 + ['land', 'hoop']
    assert all(level + 10 <= s['center'][2] <= level + 20 for s in low_line['steps'][:5])


def test_rapid_runs_through_the_narrows(worlds):
    _, new = worlds
    rapid = new.harbour['rapids'][0]
    st = np.asarray(rapid['stations'])
    k = int(np.argmax(st[:, 3]))
    x, y = st[k, :2]
    _, vel, *_ = rapids_overlay(rapid, np.array([x]), np.array([y]), 0.)
    assert 3.5 < np.hypot(*vel[0, :2]) < 4.5
    for race in new.harbour['races']:
        px, py = race['position']
        _, vel, *_ = rapids_overlay(rapid, np.array([px]), np.array([py]), 0.)
        assert np.hypot(*vel[0, :2]) < 1.6                        # staged in slack water above the race
