"""Vaderland 33: neighbourhood solids stay clear of the existing world; missions time correctly."""
import math

import numpy as np
import pytest

from vtx.mission_selection import MapPoint
from vtx.mission_timing import MissionTiming
from vtx.world import make_world


@pytest.fixture(scope='module')
def worlds():
    return make_world('vaderland-32'), make_world('vaderland-33')


def overlap(a, b, gap=0.):
    return all(abs(a['center'][i] - b['center'][i]) < a['half'][i] + b['half'][i] - gap for i in range(3))


def test_existing_world_is_unchanged_and_extended(worlds):
    old, new = worlds
    assert new.obstacles[:len(old.obstacles)] == old.obstacles
    assert np.array_equal(old.heights, new.heights)
    added = new.obstacles[len(old.obstacles):]
    assert len({o['id'] for o in new.obstacles}) == len(new.obstacles)
    assert all(o['id'].startswith(('nb-', 'nbt-', 'nbs-', 'nbr-')) for o in added)
    assert len(added) <= 6600


def test_new_solids_do_not_intersect_existing_scenery(worlds):
    old, new = worlds
    added = new.obstacles[len(old.obstacles):]
    cells = {}
    for o in old.obstacles:
        cells.setdefault((int(o['center'][0] // 200), int(o['center'][1] // 200)), []).append(o)
    for o in added:
        i, j = int(o['center'][0] // 200), int(o['center'][1] // 200)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for q in cells.get((i + di, j + dj), []):
                    assert not overlap(o, q, gap=.05), (o['id'], q['id'])


def test_ramps_are_closed_convex_hulls(worlds):
    _, new = worlds
    ramps = [o for o in new.obstacles if o.get('role') == 'ramp']
    assert ramps
    for o in ramps:
        v = np.asarray(o['vertices'])
        planes = np.asarray(o['planes'])
        assert (v @ planes[:, :3].T + planes[:, 3] <= 1e-6).all()
        assert o['landable'] and len(o['faces']) >= 4


def test_every_landing_zone_is_a_supported_roof(worlds):
    _, new = worlds
    pads = new.vaderland['neighbourhoods']['pads']
    assert {p['size'] for p in pads} == {'S', 'M', 'L', 'XL'}
    for p in pads:
        decision = new.validate(MapPoint(*p['center'][:2]), 'destination')
        assert decision.valid, (p['id'], decision.reason)
        assert abs(decision.terrain_z_m - p['center'][2]) < .05


def test_hoops_are_in_clear_air(worlds):
    _, new = worlds
    for m in new.vaderland['missions']:
        for s in m['steps']:
            if s['type'] != 'hoop':
                continue
            c, r = s['center'], s['radius_m']
            for o in new.obstacles:
                assert not all(abs(c[i] - o['center'][i]) < o['half'][i] + r for i in range(3)), (m['name'], o['id'])


def hold(timing, t, p, seconds, dt=.05):
    for _ in range(int(seconds / dt)):
        t += dt
        timing.sample(t, p, air_allowed=True, contact=True)
    return t


def mission_path(m):
    pts = [[m['spawn'][0], m['spawn'][1], 1.]]
    for s in m['steps']:
        c = s['center']
        if s['type'] == 'hoop':
            n = s['normal']
            pts += [[c[i] - n[i] * 30 for i in range(3)], [c[i] + n[i] * 30 for i in range(3)]]
        else:
            pts += [[c[0], c[1], c[2] + 25], [c[0] + .4, c[1] - .3, c[2] + 1.], 'hold', [c[0], c[1], c[2] + 25]]
    return pts


def run(timing, m):
    t = 0.
    path = mission_path(m)
    segment = []
    for p in path:
        if p == 'hold':
            t = fly_segment(timing, segment, t)
            t = hold(timing, t, segment[-1], 3.3)
            segment = [segment[-1]]
            continue
        segment.append(p)
    t = fly_segment(timing, segment, t)
    return timing.runs[m['name']]


def fly_segment(timing, pts, t, dt=.05, speed=25.):
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / speed / dt))
        for k in range(1, n + 1):
            p = [a[i] + (b[i] - a[i]) * k / n for i in range(3)]
            t += dt
            timing.sample(t, p, air_allowed=True, contact=False)
    return t


def test_a_flown_mission_completes_with_two_touchdowns(worlds):
    _, new = worlds
    m = new.vaderland['missions'][0]
    timing = MissionTiming([], [], [m])
    timing.sample(0., [m['spawn'][0], m['spawn'][1], 1.], contact=True)
    state = run(timing, m)
    assert state['laps'] == 1 and state['last'] is not None and state['best'] == state['last']
    assert state['landing_error_m'] == [0.5, 0.5]      # rooftop and runway touchdown scores, kept until the next start
    assert state['next'] == 0


def test_touchdown_outside_the_zone_ends_the_attempt(worlds):
    _, new = worlds
    m = new.vaderland['missions'][0]
    timing = MissionTiming([], [], [m])
    h = m['steps'][0]
    n = h['normal']
    fly_segment(timing, [[h['center'][i] - n[i] * 30 for i in range(3)], [h['center'][i] + n[i] * 30 for i in range(3)]], 0.)
    assert timing.runs[m['name']]['next'] == 1
    timing.sample(100., [h['center'][0] + 500, h['center'][1], 2.], contact=False)
    timing.sample(100.05, [h['center'][0] + 500, h['center'][1], 2.], contact=True)
    assert timing.runs[m['name']]['next'] == 0 and timing.runs[m['name']]['start'] is None


def test_mission_record_survives_checkpoint(worlds):
    _, new = worlds
    timing = new.timing
    saved = timing.save()
    timing.restore(saved)
    assert set(timing.runs) >= {m['name'] for m in new.vaderland['missions']}
