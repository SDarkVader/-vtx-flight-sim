"""Vaderland 33: Meridian ward neighbourhoods, mini tracks, rooftop landing zones and missions.

Fills the empty Meridian ward lots with small neighbourhoods (terraces, odd houses, round
houses, towers, gardens, trees and lanes), gives some lots a mini track with physical
ramps, lights landing zones of several sizes on existing and new roofs, and chains hoops
and zones into missions that end with a runway touchdown and a takeoff gate.

Physical shapes are boxes, cylinders and convex ramps. Gardens, lawns, paths and crop
stripes are ground colour only; lanes and tracks are surveyed routes on the existing
terrain. The terrain heightfield is not changed.

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
GEOM_BUDGET = 6500

HOUSE_PALETTE = ['#c8553d', '#2f8f83', '#e0a43a', '#8e6cc4', '#e8e1d2', '#4f7cac', '#d97a9a', '#6f9e4f', '#b9794f', '#3d4b6b']
LEAF = ['#2e5d34', '#3f7a3a', '#5b8f3a', '#2c4f3f', '#7a9a3a', '#c45a8a', '#d9822b', '#9c4fb0']
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
        self.solids, self.roads, self.gardens, self.circuits, self.tracks = [], [], [], [], []
        self.houses = []

    # -- physical shapes ------------------------------------------------------------------
    def box(self, ident, x, y, a, b, height, *, role='house', base=None, **extra):
        low, high = self.s.ground(x, y, a, b)
        bottom, top = (low - .6, high + height) if base is None else (base - .15, base + height)
        o = dict(id=ident, kind='box', center=[r2(x), r2(y), r2((bottom + top) / 2)], half=[r2(a), r2(b), r2((top - bottom) / 2)],
                 color=extra.pop('color', '#5a6470'), role=role, landable=True, **extra)
        self.solids.append(o)
        self.s.mark(x - a - 1, x + a + 1, y - b - 1, y + b + 1)
        return o

    def cylinder(self, ident, x, y, r, height, *, role, landable, base=None, **extra):
        low, high = self.s.ground(x, y, r, r)
        bottom, top = (low - .6, high + height) if base is None else (base - .15, base + height)
        o = dict(id=ident, kind='cylinder', center=[r2(x), r2(y), r2((bottom + top) / 2)], half=[r2(r), r2(r), r2((top - bottom) / 2)],
                 color=extra.pop('color', '#5a6470'), role=role, landable=landable, **extra)
        self.solids.append(o)
        self.s.mark(x - r - 1, x + r + 1, y - r - 1, y + r + 1)
        return o

    def tree(self, ident, x, y):
        if not self.s.is_free(x - 3, x + 3, y - 3, y + 3):
            return None
        h = float(self.rng.uniform(7, 13))
        r = float(self.rng.uniform(1.4, 2.3))
        leaf = LEAF[int(self.rng.integers(0, 5))] if self.rng.random() < .85 else LEAF[int(self.rng.integers(5, len(LEAF)))]
        return self.cylinder(ident, x, y, r, h, role='broadleaf', landable=False, color=leaf, crown_radius_m=r2(r * 2.1))

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

    def garden(self, kind, x0, y0, x1, y1, tone=0):
        self.gardens.append([kind, r2(x0), r2(y0), r2(x1), r2(y1), int(tone)])

    # -- lot types --------------------------------------------------------------------------
    def homes(self, name, ax, ay, along_x, flavour):
        S, m = TILE, 6.
        c = (ax + S / 2, ay + S / 2)
        lane_w = 7.
        # Keep the longest clear stretch of the lane so it never overlaps street paint or a building.
        run, best = [], []
        for k in range(int(S // 4) + 1):
            u = k * 4.
            x, y = (ax + u, c[1]) if along_x else (c[0], ay + u)
            if self.s.is_free(x - 4.5, x + 4.5, y - 4.5, y + 4.5):
                run.append(u)
                best = max(best, run, key=len)
            else:
                run = []
        if len(best) < 10:
            return self.park(name, ax, ay)
        u0, u1 = best[0], best[-1]
        if along_x:
            lane = [[ax + u0, c[1]], [ax + u1, c[1]]]
        else:
            lane = [[c[0], ay + u0], [c[0], ay + u1]]
        self.roads.append(dict(name=name + ' lane', kind='lane', width_m=lane_w, points=lane, edge_color='#c9a26b'))
        self.s.mark(min(lane[0][0], lane[1][0]) - 4, max(lane[0][0], lane[1][0]) + 4, min(lane[0][1], lane[1][1]) - 4, max(lane[0][1], lane[1][1]) + 4)
        k = 0
        for side in (-1, 1):
            setback = lane_w / 2 + float(self.rng.uniform(4, 7))
            depth = float(self.rng.uniform(8.5, 11))
            cursor = m
            while cursor < S - m - 8:
                odd = self.rng.random() < (.55 if flavour == 'odd' else .22)
                if not odd:
                    run = float(min(self.rng.uniform(26, 46), S - m - cursor))
                    if run < 14:
                        break
                    units = max(2, int(run // float(self.rng.uniform(5.5, 8))))
                    u0, u1 = cursor, cursor + run
                    along = (u0 + u1) / 2
                    off = side * (setback + depth / 2)
                    x, y = (ax + along, c[1] + off) if along_x else (c[0] + off, ay + along)
                    a, b = (run / 2, depth / 2) if along_x else (depth / 2, run / 2)
                    if self.s.is_free(x - a, x + a, y - b, y + b):
                        h = float(self.rng.uniform(6.5, 10.5))
                        o = self.box(f'nb-{name}-{k}', x, y, a, b, h, style='terrace', units=units,
                                     palette=int(self.rng.integers(0, 1 << 20)), front=[0, -side] if along_x else [-side, 0])
                        self.houses.append(o)
                        bx0, bx1 = (x - a, x + a) if along_x else (x + side * b, x + side * (b + 14))
                        by0, by1 = (y + side * b, y + side * (b + 14)) if along_x else (y - b, y + b)
                        self.garden('lawn', min(bx0, bx1), min(by0, by1), max(bx0, bx1), max(by0, by1), self.rng.integers(0, 4))
                        for t in range(int(run // 18)):
                            tu = u0 + 8 + t * 18
                            back = side * (setback + depth + 8)
                            tx, ty = (ax + tu, c[1] + back) if along_x else (c[0] + back, ay + tu)
                            self.tree(f'nbt-{name}-{k}-{t}', tx, ty)
                        k += 1
                    cursor = u1 + float(self.rng.uniform(5, 10))
                else:
                    cursor = self.odd_house(f'{name}-{k}', ax, ay, c, along_x, side, setback, cursor) + float(self.rng.uniform(4, 8))
                    k += 1
        # street trees along the lane
        for t in range(3):
            u = 18 + t * 38
            for side in (-1, 1):
                off = side * (lane_w / 2 + 2.2)
                tx, ty = (ax + u, c[1] + off) if along_x else (c[0] + off, ay + u)
                self.tree(f'nbs-{name}-{t}-{side}', tx, ty)

    def odd_house(self, name, ax, ay, c, along_x, side, setback, cursor):
        roll = self.rng.random()
        size = float(self.rng.uniform(8, 11))
        along = cursor + size / 2 + 1
        off = side * (setback + size / 2)
        x, y = (ax + along, c[1] + off) if along_x else (c[0] + off, ay + along)
        if not self.s.is_free(x - size / 2 - 1, x + size / 2 + 1, y - size / 2 - 1, y + size / 2 + 1):
            return cursor + size
        pal = int(self.rng.integers(0, 1 << 20))
        front = [0, -side] if along_x else [-side, 0]
        if roll < .30:      # round house
            r = size / 2
            self.cylinder(f'nb-{name}', x, y, r, float(self.rng.uniform(6, 9)), role='house', landable=True, style='silo', palette=pal, front=front)
        elif roll < .55:    # narrow tower house, some with a roof pad
            a = float(self.rng.uniform(3.2, 4.2))
            o = self.box(f'nb-{name}', x, y, a, a, float(self.rng.uniform(14, 24)), style='tower', palette=pal, front=front)
            self.houses.append(o)
        else:               # stacked cubes: a lower block with a shifted, cantilevered upper block
            a = size / 2
            low = self.box(f'nb-{name}', x, y, a, a, float(self.rng.uniform(3.8, 4.6)), style='cube', palette=pal, front=front)
            shift = float(self.rng.uniform(1.2, 2.6)) * (1 if self.rng.random() < .5 else -1)
            ux, uy = (x + shift, y) if along_x else (x, y + shift)
            top = low['center'][2] + low['half'][2]
            self.box(f'nb-{name}-up', ux, uy, a * .82, a * .82, float(self.rng.uniform(3.4, 4.2)), base=top + .15,
                     style='cube-upper', palette=pal ^ 0x5a5a5, front=front, support='stacked', parent=low['id'])
            self.s.mark(ux - a, ux + a, uy - a, uy + a)
        self.garden('bed', x - size / 2 - 3, y - size / 2 - 3, x + size / 2 + 3, y + size / 2 + 3, self.rng.integers(0, 6))
        return cursor + size + 2

    def park(self, name, ax, ay):
        S = TILE
        self.garden('lawn', ax + 4, ay + 4, ax + S - 4, ay + S - 4, self.rng.integers(0, 4))
        cx, cy = ax + S / 2, ay + S / 2
        self.garden('path', cx - 2, ay + 4, cx + 2, ay + S - 4)
        self.garden('path', ax + 4, cy - 2, ax + S - 4, cy + 2)
        self.garden('pond' if self.rng.random() < .4 else 'plaza', cx - 12, cy - 9, cx + 12, cy + 9)
        for q in range(4):
            qx, qy = (ax + 8 if q % 2 == 0 else cx + 6), (ay + 8 if q < 2 else cy + 6)
            self.garden('bed', qx, qy, qx + 14, qy + 8, self.rng.integers(0, 6))
        for t in range(int(self.rng.integers(9, 14))):
            tx, ty = ax + float(self.rng.uniform(10, S - 10)), ay + float(self.rng.uniform(10, S - 10))
            if abs(tx - cx) < 16 and abs(ty - cy) < 13:
                continue
            self.tree(f'nbt-{name}-{t}', tx, ty)

    def allotment(self, name, ax, ay, along_x):
        S = TILE
        for i in range(9):
            if along_x:
                self.garden('crops', ax + 8, ay + 8 + i * 10.6, ax + S - 8, ay + 14 + i * 10.6, i % 5)
            else:
                self.garden('crops', ax + 8 + i * 10.6, ay + 8, ax + 14 + i * 10.6, ay + S - 8, i % 5)
        for t in range(3):
            self.tree(f'nbt-{name}-{t}', ax + 6 + t * 50, ay + 4)

    def open_ground(self, name, ax, ay, along_x):
        """Ground-only lots: pitches, wildflower meadows, car parks and allotments. No solids."""
        S = TILE
        kind = int(self.rng.integers(0, 4))
        if kind == 0:       # sports pitch with a running track around it
            self.garden('path', ax + 6, ay + 6, ax + S - 6, ay + S - 6)
            self.garden('lawn', ax + 12, ay + 14, ax + S - 12, ay + S - 14, 3)
            self.garden('pitch', ax + 18, ay + 22, ax + S - 18, ay + S - 22, 0)
        elif kind == 1:     # wildflower meadow with mown paths
            self.garden('bed', ax + 6, ay + 6, ax + S - 6, ay + S - 6, int(self.rng.integers(0, 6)))
            self.garden('path', ax + S / 2 - 1.5, ay + 6, ax + S / 2 + 1.5, ay + S - 6)
        elif kind == 2:     # car park with painted bays
            self.garden('plaza', ax + 8, ay + 8, ax + S - 8, ay + S - 8)
            for i in range(5):
                self.garden('bays', ax + 12, ay + 14 + i * 15, ax + S - 12, ay + 22 + i * 15, 0)
        else:
            for i in range(8):
                if along_x:
                    self.garden('crops', ax + 8, ay + 8 + i * 10, ax + S - 8, ay + 14 + i * 10, i % 5)
                else:
                    self.garden('crops', ax + 8 + i * 10, ay + 8, ax + 14 + i * 10, ay + S - 8, i % 5)

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
        for t in range(4):
            self.tree(f'nbt-{name}-{t}', ax + 4 + t * 34, ay + 6)

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
            i, j, ax, ay = tiles[idx]
            if self.s.free_fraction(ax, ax + TILE, ay, ay + TILE) < .75:
                continue
            if len(self.solids) > GEOM_BUDGET:
                self.open_ground(f'ward-lot-{i:02d}-{j:02d}', ax, ay, (i + j) % 2 == 0)
                self.s.mark(ax + 4, ax + TILE - 4, ay + 4, ay + TILE - 4)
                continue
            cluster = (i // 3) * 7919 + (j // 3) * 104729
            flavour = ['terraces', 'odd', 'gardens', 'terraces', 'odd'][cluster % 5]
            along_x = (cluster // 5) % 2 == 0
            roll = self.rng.random()
            name = f'ward-lot-{i:02d}-{j:02d}'
            if roll < .07 and n_tracks < 14 and self.s.free_fraction(ax, ax + TILE, ay, ay + TILE) > .985:
                self.track(f'Ward Loop {n_tracks + 1}', ax, ay, n_tracks)
                n_tracks += 1
            elif flavour == 'gardens' and roll < .55 or roll > .88:
                self.park(name, ax, ay)
            elif roll > .80:
                self.allotment(name, ax, ay, along_x)
            else:
                self.homes(name, ax, ay, along_x, flavour)
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
    shells = getattr(world, '_shells', None)
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
    for s in builder.solids:
        if s['kind'] == 'mesh':
            s['planes'] = [[float(v) for v in p] for p in s['planes']]
    design = dict(version='33', solids=builder.solids, roads=builder.roads, circuits=builder.circuits,
                  neighbourhoods=dict(gardens=builder.gardens, tracks=builder.tracks, pads=pads, bounds=[X0, X1, Y0, Y1],
                                      pad_classes=[dict(size=c, radius_m=r, colour=col, demands=u) for c, r, col, u in PAD_CLASSES]),
                  missions=plan)
    raw = json.dumps(design, separators=(',', ':'), allow_nan=False).encode()
    args.out.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    kinds = {}
    for s in builder.solids:
        kinds[s.get('style') or s['role']] = kinds.get(s.get('style') or s['role'], 0) + 1
    print(json.dumps(dict(usable_tiles=usable, solids=len(builder.solids), kinds=kinds, lanes=sum(r['kind'] == 'lane' for r in builder.roads),
                          tracks=len(builder.tracks), gardens=len(builder.gardens), pads={c: sum(p['size'] == c for p in pads) for c, *_ in PAD_CLASSES},
                          missions=[m['name'] for m in plan], bytes=args.out.stat().st_size)))


if __name__ == '__main__':
    main()
