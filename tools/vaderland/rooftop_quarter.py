"""Vaderland 33: Meridian rooftop landing zones, missions and ward mini tracks.

Lights landing zones of several sizes on existing Meridian roofs, chains hoops and zones
into missions that end with a runway touchdown and a takeoff gate, and adds a few small
ward tracks with physical ramps. No buildings are added: an earlier box-house infill was
rejected by the owner (it read as blocks and departed from the baseline architecture), so
any future infill must reuse the baseline Meridian building vocabulary.

The only new solids are convex ramps. Tracks are surveyed routes on the existing terrain,
and the terrain heightfield is not changed.

    python tools/vaderland/rooftop_quarter.py [--out inputs/vaderland/rooftop-quarter-33.json.gz]
"""
import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.world import make_world, MapPoint  # noqa: E402

CELL = 4.0
X0, X1, Y0, Y1 = -3300., 3100., 680., 5800.
TILE = 96.
CENTRE = (-1090., 1090., 1390., 3570.)          # existing dense market district stays as built
PAD_CLASSES = [  # name, radius, colour, what the zone demands of a vehicle (the environment sets the challenge)
    ('S', 6.0, '#b46bff', 'footprint within 8 m; precise hover over a small high roof'),
    ('M', 10.0, '#36d6ff', 'footprint within 14 m; controlled vertical descent onto a mid-rise roof'),
    ('L', 15.0, '#ffb340', 'footprint within 22 m; heavier hover with clear approach column'),
    ('XL', 22.0, '#57e38b', 'footprint within 34 m; heavy-lift touchdown on a broad low roof'),
]
RAMPS = {  # length, height, top length (0 = kicker): the course sets the jump, vehicles are built to clear it
    'small': (10., 1.2, 0.), 'medium': (15., 2.4, 6.), 'large': (22., 3.8, 10.),
}


def r2(v):
    return round(float(v), 3)


class Survey:
    """4 m occupancy raster of what is already in the Meridian wards."""

    def __init__(self, world):
        self.w = world
        self.nx, self.ny = int((X1 - X0) / CELL), int((Y1 - Y0) / CELL)
        self.blocked = np.zeros((self.ny, self.nx), bool)
        n, half = world.n, world.half
        step = 2 * half / (n - 1)
        gy, gx = np.gradient(world.heights.astype(float), step)
        self.slope = np.hypot(gx, gy)
        self.step = step

    def index(self, x, y):
        return int((x - X0) // CELL), int((y - Y0) // CELL)

    def mark(self, x0, x1, y0, y1):
        i0, j0 = self.index(x0, y0)
        i1, j1 = self.index(x1, y1)
        i0, i1 = max(0, i0), min(self.nx, i1 + 1)
        j0, j1 = max(0, j0), min(self.ny, j1 + 1)
        if i0 < i1 and j0 < j1:
            self.blocked[j0:j1, i0:i1] = True

    def free_fraction(self, x0, x1, y0, y1):
        i0, j0 = self.index(x0, y0)
        i1, j1 = self.index(x1, y1)
        if i0 < 0 or j0 < 0 or i1 > self.nx or j1 > self.ny:
            return 0.
        return 1. - self.blocked[j0:j1, i0:i1].mean()

    def is_free(self, x0, x1, y0, y1):
        return self.free_fraction(x0, x1, y0, y1) >= 1.

    def slope_at(self, x, y):
        i = int(round((x + self.w.half) / self.step))
        j = int(round((y + self.w.half) / self.step))
        return float(self.slope[j, i])

    def ground(self, x, y, a, b):
        zs = [self.w.terrain_z(x + u * a, y + v * b) for u in (-1, 0, 1) for v in (-1, 0, 1)]
        return min(zs), max(zs)


def survey_existing(world):
    s = Survey(world)
    for o in world.obstacles:
        (x, y, _), (a, b, _) = o['center'], o['half']
        s.mark(x - a - 6, x + a + 6, y - b - 6, y + b + 6)
    for r in world.vaderland['routes']:
        reach = r['width_m'] / 2 + 6
        pts = r['points']
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            d = math.hypot(bx - ax, by - ay)
            for k in range(int(d // 2) + 1):
                f = min(1., k * 2 / max(d, 1e-6))
                x, y = ax + (bx - ax) * f, ay + (by - ay) * f
                s.mark(x - reach, x + reach, y - reach, y + reach)
    s.mark(*CENTRE[:2], *CENTRE[2:])
    wt = world.water
    s.mark(wt['x'] - wt['half_x'] - 20, wt['x'] + wt['half_x'] + 20, wt['y'] - wt['half_y'] - 20, wt['y'] + wt['half_y'] + 20)
    return s


class Builder:
    def __init__(self, world, survey, seed=3301):
        self.w, self.s = world, survey
        self.rng = np.random.default_rng(seed)
        self.solids, self.roads, self.circuits, self.tracks = [], [], [], []

    def ramp(self, ident, x, y, heading, kind, base):
        """Convex ramp or tabletop on a straight, aligned with travel along `heading`."""
        length, height, top = RAMPS[kind]
        width = 8.
        ca, sa = math.cos(heading), math.sin(heading)
        half_run = (length + top) / 2
        profile = [(-half_run, 0.), (-half_run + length / 2 if top else half_run, height), (half_run - length / 2 if top else half_run, height), (half_run, 0.)]
        if not top:   # kicker: rises over its full length, vertical drop at the lip
            profile = [(-half_run, 0.), (half_run, height), (half_run, 0.)]
        pts = []
        for u, z in profile:
            for v in (-width / 2, width / 2):
                pts.append((u * ca - v * sa, u * sa + v * ca, z))
        pts = np.unique(np.round(np.array(pts), 4), axis=0)
        lo, hi = pts.min(0), pts.max(0)
        centre = (lo + hi) / 2
        local = pts - centre
        hull = ConvexHull(local)
        faces = []
        for simplex, eq in zip(hull.simplices, hull.equations):
            a, b, c = local[simplex]
            if np.dot(np.cross(b - a, c - a), eq[:3]) < 0:
                simplex = simplex[[0, 2, 1]]
            faces.append([int(i) for i in simplex])
        planes = np.unique(np.round(hull.equations, 9), axis=0)
        world_centre = [x + centre[0], y + centre[1], base - .05 + centre[2]]
        o = dict(id=ident, kind='mesh', role='ramp', color='#f2a33a', finish='shell', skin='rampDeck', landable=True,
                 center=[r2(v) for v in world_centre], half=[r2(v) for v in (hi - lo) / 2],
                 vertices=[[r2(v) for v in p] for p in local], faces=faces, planes=[[float(v) for v in p] for p in planes],
                 ramp=dict(kind=kind, heading=r2(heading), length_m=length, height_m=height, top_m=top))
        self.solids.append(o)
        return o

    def track(self, name, ax, ay, index):
        """A short closed loop with kerbs, a tabletop and a kicker-and-landing on its straights."""
        S, w = TILE, 10.
        x0, x1, y0, y1 = ax + 12, ax + S - 12, ay + 20, ay + S - 20
        r = 14.
        pts = []
        corners = [(x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, math.pi / 2), (x0 + r, y0 + r, math.pi)]
        for cx, cy, a0 in corners:
            for k in range(7):
                a = a0 + k * (math.pi / 2) / 6
                pts.append([r2(cx + r * math.cos(a)), r2(cy + r * math.sin(a))])
        pts.append(pts[0])
        colour = ['#ff4fa3', '#ffb340', '#36d6ff', '#b46bff'][index % 4]
        self.roads.append(dict(name=name, kind='track', width_m=w, points=pts, edge_color=colour, mitre=True))
        self.s.mark(ax, ax + S, ay, ay + S)
        base_s = self.w.terrain_z((x0 + x1) / 2, y0)
        base_n = self.w.terrain_z((x0 + x1) / 2, y1)
        cls = ['small', 'medium', 'large'][index % 3]
        ramps = [self.ramp(f'nbr-{name}-table', (x0 + x1) / 2, y0, 0., 'medium' if cls != 'small' else 'small', base_s)]
        kick = 'small' if cls == 'small' else 'medium'
        kl, kh, _ = RAMPS[kick]
        gap = 7. + 3. * ['small', 'medium', 'large'].index(cls)
        kx = (x0 + x1) / 2 + (gap / 2 + kl / 2)
        ramps.append(self.ramp(f'nbr-{name}-kick', kx, y1, math.pi, kick, base_n))
        ramps.append(self.ramp(f'nbr-{name}-land', kx - gap - kl, y1, 0., kick, base_n))
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        gz = lambda x, y: r2(self.w.terrain_z(x, y) + 1.)
        gates = [dict(center=[r2(x1), r2((y0 + y1) / 2), gz(x1, (y0 + y1) / 2)], normal=[0., 1.], width_m=w + 4),
                 dict(center=[r2((x0 + x1) / 2 - 20), r2(y1), gz((x0 + x1) / 2 - 20, y1)], normal=[-1., 0.], width_m=w + 4),
                 dict(center=[r2(x0), r2((y0 + y1) / 2), gz(x0, (y0 + y1) / 2)], normal=[0., -1.], width_m=w + 4)]
        self.circuits.append(dict(name=name, length_m=r2(length), gates=gates))
        self.tracks.append(dict(name=name, ramps=[o['id'] for o in ramps], kerb=colour, spawn=[r2(x0 + 2), r2(y0 + r + 4)], ramp_class=cls))

    # -- the wards ---------------------------------------------------------------------------
    def fill(self):
        tiles = []
        for j in range(int((Y1 - Y0) // TILE)):
            for i in range(int((X1 - X0) // TILE)):
                ax, ay = X0 + i * TILE, Y0 + j * TILE
                if self.s.free_fraction(ax, ax + TILE, ay, ay + TILE) < .75:
                    continue
                if max(self.s.slope_at(ax + u, ay + v) for u in (8, TILE / 2, TILE - 8) for v in (8, TILE / 2, TILE - 8)) > .13:
                    continue
                tiles.append((i, j, ax, ay))
        order = self.rng.permutation(len(tiles))
        n_tracks = 0
        for idx in order:
            if n_tracks >= 14:
                break
            i, j, ax, ay = tiles[idx]
            if self.s.free_fraction(ax, ax + TILE, ay, ay + TILE) > .985:
                self.track(f'Ward Loop {n_tracks + 1}', ax, ay, n_tracks)
                n_tracks += 1
        return len(tiles)


def roof_tops(world, solids):
    obstacles = world.obstacles + solids
    tops = []
    for o in obstacles:
        if o['kind'] != 'box' or not o.get('landable'):
            continue
        (x, y, z), (a, b, c) = o['center'], o['half']
        if not (X0 < x < X1 and Y0 < y < Y1):
            continue
        top = z + c
        if top - world.terrain_z(x, y) < 9:
            continue
        tops.append((o, x, y, a, b, top))
    return tops


def choose_pads(world, solids):
    obstacles = world.obstacles + solids
    world.obstacles = obstacles        # validate() and surface_z() must see the new roofs
    pads, rng = [], np.random.default_rng(5101)
    tops = roof_tops(world, solids)
    rng.shuffle(tops)
    for cls, radius, colour, use in PAD_CLASSES:
        want = 9 if cls in ('M', 'S') else 7
        for o, x, y, a, b, top in tops:
            if sum(p['size'] == cls for p in pads) >= want:
                break
            if a < radius + 2.5 or b < radius + 2.5:
                continue
            if any(math.hypot(x - p['center'][0], y - p['center'][1]) < 280 for p in pads):
                continue
            blocked = False
            for q in obstacles:
                if q is o:
                    continue
                (qx, qy, qz), (qa, qb, qc) = q['center'], q['half']
                if qz + qc <= top + .2:
                    continue
                dx, dy = max(abs(x - qx) - qa, 0), max(abs(y - qy) - qb, 0)
                if math.hypot(dx, dy) < radius + 10:
                    blocked = True
                    break
            if blocked:
                continue
            decision = world.validate(MapPoint(x, y), 'destination')
            if not decision.valid or abs(decision.terrain_z_m - top) > .05:
                continue
            height = top - world.terrain_z(x, y)
            tier = 'gold' if height > 90 or cls == 'S' else 'silver' if height > 35 or cls == 'M' else 'bronze'
            pads.append(dict(id=f'pad-{cls}-{len(pads) + 1:02d}', size=cls, radius_m=radius, colour=colour, demands=use,
                             center=[r2(x), r2(y), r2(top)], height_m=r2(height), roof=o['id'], tier=tier))
    return pads


def hoop_clear(obstacles, centre, normal, radius):
    cx, cy, cz = centre
    for q in obstacles:
        (qx, qy, qz), (qa, qb, qc) = q['center'], q['half']
        if abs(qx - cx) > qa + radius + 12 or abs(qy - cy) > qb + radius + 12 or abs(qz - cz) > qc + radius + 12:
            continue
        return False
    return True


def hoop(obstacles, x, y, z, toward, radius, terrain):
    nx, ny = toward
    n = math.hypot(nx, ny)
    nx, ny = nx / n, ny / n
    for lift in range(0, 160, 12):
        c = [x, y, max(z, terrain(x, y) + radius + 18) + lift]
        if hoop_clear(obstacles, c, (nx, ny), radius):
            return dict(type='hoop', center=[r2(v) for v in c], normal=[r2(nx), r2(ny), 0.], right=[r2(-ny), r2(nx), 0.],
                        up=[0., 0., 1.], radius_m=radius)
    return None


def missions(world, pads):
    obstacles = world.obstacles
    terrain = world.terrain_z
    rw = world.runway
    out = []
    picks = []
    for cls, *_ in PAD_CLASSES[::-1]:            # XL (broad, low) first, S (small, high) last
        group = sorted((p for p in pads if p['size'] == cls), key=lambda p: p['height_m'])
        picks.extend(group[:1] + group[-1:] if len(group) > 1 else group)
    for k, pad in enumerate(picks):
        px, py, pz = pad['center']
        sx = float(np.clip(px, rw['x0'] + 900, rw['x1'] - 900))
        spawn = [r2(sx), 0.]
        h1 = hoop(obstacles, sx, 420., 60., (0., 1.), 18., terrain)
        mid = hoop(obstacles, (sx + px) / 2, (420 + py) / 2, (60 + pz) / 2 + 40, (px - sx, py - 420), 14. if pad['size'] in ('XL', 'L') else 10., terrain)
        dx, dy = px - (sx + px) / 2, py - (420 + py) / 2
        d = math.hypot(dx, dy)
        approach = hoop(obstacles, px - dx / d * 260, py - dy / d * 260, pz + 45, (dx, dy), 12. if pad['size'] in ('XL', 'L') else 8., terrain)
        if not (h1 and mid and approach):
            continue
        east = sx < 0
        rx = sx + (700 if east else -700)
        zone = dict(type='land', shape='box', center=[r2(rx), 0., r2(rw['elevation_m'])], half=[70., 13.], hold_s=2.0, max_speed_m_s=1.0,
                    label='Runway 08/26 touchdown zone')
        exit_gate = hoop(obstacles, rx + (900 if east else -900), 0., 30., (1. if east else -1., 0.), 25., terrain)
        if not exit_gate:
            continue
        steps = [h1, mid, approach,
                 dict(type='land', shape='circle', center=pad['center'], radius_m=pad['radius_m'], hold_s=3.0, max_speed_m_s=0.8, pad=pad['id']),
                 zone, exit_gate]
        name = f"Rooftop Run {k + 1} · {pad['size']} pad"
        length = 0.
        last = [sx, 0., 0.]
        for s in steps:
            length += math.dist(last[:2], s['center'][:2])
            last = s['center']
        out.append(dict(name=name, zone='Meridian Rooftops', spawn=spawn, length_m=r2(length), pad=pad['id'], size=pad['size'],
                        tier=pad['tier'], steps=steps,
                        brief='Take off, fly the hoops, brake into a hover and settle on the lit rooftop zone, '
                              'hover down to the runway touchdown zone, then take off through the exit hoop.'))
    return out


A10B_REPLAY = ROOT / 'evidence/phantom/a10c_airbrake_ecu_20261118/baseline/baseline_a10b.json'
BRAKE_GATES_T = [9.0, 10.5, 12.0, 13.5, 15.0, 17.0, 19.0, 21.5, 24.5, 28.0]


def a10b_path():
    """Ground track of the 9 November A10-B fan-assisted braking turn (turn_fan schedule replay).

    The replay logs forward speed, heading and height change at 20 Hz; integrating speed along
    heading recovers the track. Returns rows of (t, x, y, dz, speed, heading_rad).
    """
    import hashlib
    raw = A10B_REPLAY.read_bytes()
    log = json.loads(raw)['log']
    x = y = 0.
    rows = [(log[0]['t'], 0., 0., log[0]['z'], log[0]['u'], math.radians(log[0]['hdg']))]
    for a, b in zip(log, log[1:]):
        dt, h = b['t'] - a['t'], math.radians(a['hdg'])
        x += a['u'] * math.cos(h) * dt
        y += a['u'] * math.sin(h) * dt
        rows.append((b['t'], x, y, b['z'], b['u'], math.radians(b['hdg'])))
    return rows, hashlib.sha256(raw).hexdigest()


def brake_line(world):
    """The Brake Line: gates on the exact path of the A10-B's 9 November braking turn, ending in a hover."""
    rows, digest = a10b_path()
    obstacles, terrain = world.obstacles, world.terrain_z
    end = next(r for r in rows if r[4] < .6)                       # first moment the turn has bled off to a hover
    for sx, sy, heading in [(-3150., 3950., -.17), (-3150., 4350., -.17), (-3050., 3550., -.10), (-2950., 4750., -.20)]:
        c, s = math.cos(heading), math.sin(heading)
        place = lambda x, y: (sx + x * c - y * s, sy + x * s + y * c)
        ground = max(terrain(*place(r[1], r[2])) for r in rows[::10])
        z0 = round(ground + 150., 1)
        track = [(*place(r[1], r[2]), z0 + r[3]) for r in rows if r[0] <= end[0]]
        clear = all(not (abs(q['center'][0] - x) < q['half'][0] + 25 and abs(q['center'][1] - y) < q['half'][1] + 25
                         and abs(q['center'][2] - z) < q['half'][2] + 25) for x, y, z in track[::4] for q in obstacles)
        if not clear:
            continue
        steps = []
        for t in BRAKE_GATES_T:
            r = min(rows, key=lambda q: abs(q[0] - t))
            x, y = place(r[1], r[2])
            h = r[5] + heading
            radius = round(min(16., max(6., 4. + .12 * r[4])), 1)
            centre = [r2(x), r2(y), r2(z0 + r[3])]
            if not hoop_clear(obstacles, centre, None, radius):
                break
            steps.append(dict(type='hoop', center=centre, normal=[r2(math.cos(h)), r2(math.sin(h)), 0.],
                              right=[r2(-math.sin(h)), r2(math.cos(h)), 0.], up=[0., 0., 1.], radius_m=radius,
                              a10b_t_s=r2(r[0]), a10b_speed_m_s=r2(r[4])))
        else:
            hx, hy = place(end[1], end[2])
            steps.append(dict(type='hover', center=[r2(hx), r2(hy), r2(z0 + end[3])], radius_m=6., half_height_m=3.,
                              hold_s=4., max_speed_m_s=.6, a10b_t_s=r2(end[0])))
            back = [place(-30. * k, 0.) for k in range(1, 31)]             # 900 m approach line on the ground
            lights = [[r2(x), r2(y), r2(terrain(x, y) + .6), k] for k, (x, y) in enumerate(back)]
            ghost = [[r2(x), r2(y), r2(z)] for x, y, z in track[::4]]
            length = sum(math.dist(a[:2], b[:2]) for a, b in zip(track, track[1:]))
            mission = dict(name='The Brake Line \u00b7 9 November', zone='Meridian West Wards', spawn=[-3300., 0.],
                           length_m=r2(length), pad=None, size='M', tier='gold', steps=steps,
                           brief='Ten gates on the exact track of the Phantom A10-B\'s first fan-assisted braking turn, '
                                 'flown on 9 November 2026 by a scripted test pilot on the offline plant: 95 m/s to a '
                                 'hover in about 26 s. Enter the first gate near cruise, brake through the shrinking '
                                 'gates and hold the hover for 4 s without touching anything.',
                           provenance=dict(source=str(A10B_REPLAY.relative_to(ROOT)).replace('\\', '/'), sha256=digest,
                                           aircraft='phantom-a10b', schedule='turn_fan', start_s=rows[0][0], hover_s=end[0],
                                           placement=dict(origin=[sx, sy], heading_rad=heading, altitude_m=z0)))
            return mission, dict(lights=lights, ghost=ghost)
    raise RuntimeError('No clear placement for the Brake Line')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'inputs/vaderland/rooftop-quarter-33.json.gz')
    args = parser.parse_args()
    world = make_world('vaderland-32')
    survey = survey_existing(world)
    builder = Builder(world, survey)
    usable = builder.fill()
    pads = choose_pads(world, builder.solids)
    plan = missions(world, pads)
    brake, brake_marks = brake_line(world)
    plan.append(brake)
    for s in builder.solids:
        if s['kind'] == 'mesh':
            s['planes'] = [[float(v) for v in p] for p in s['planes']]
    design = dict(version='33', solids=builder.solids, roads=builder.roads, circuits=builder.circuits,
                  neighbourhoods=dict(tracks=builder.tracks, pads=pads, bounds=[X0, X1, Y0, Y1],
                                      pad_classes=[dict(size=c, radius_m=r, colour=col, demands=u) for c, r, col, u in PAD_CLASSES]),
                  missions=plan, brake_line=brake_marks)
    raw = json.dumps(design, separators=(',', ':'), allow_nan=False).encode()
    args.out.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    print(json.dumps(dict(usable_tiles=usable, solids=len(builder.solids),
                          tracks=len(builder.tracks), pads={c: sum(p['size'] == c for p in pads) for c, *_ in PAD_CLASSES},
                          missions=[m['name'] for m in plan], bytes=args.out.stat().st_size)))


if __name__ == '__main__':
    main()
