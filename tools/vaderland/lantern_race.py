"""Vaderland 33: the Lantern Race, a tidal race through the Needle narrows of Lantern Sound.

The narrows between Heron Island (west) and Needle Island (east) is about 96 m wide at its
throat. This module designs everything that uses it:

- the rapid: a downstream current (about 4 m/s in the throat), counter-current eddies along both
  banks, a standing-wave train and the flow around rocks, consumed by the harbour water physics;
- rocks: the Lantern Rock splitter with its beacon, a throat guard, a rock garden and bank
  boulders, all collision hulls seated on the bed;
- three boat lines sharing a start and a finish (Main Chute, Rock Garden, Eddy Line), marked with
  lantern piles and timed point to point;
- anchored floating ramps for planing hulls: a chute kicker, a small-craft hop and one
  deep-water outlier;
- Needle Island: a trail loop with a tabletop for wheeled vehicles, a slipway for amphibious
  ones, and an overlook deck that is also the Low Line air mission's landing zone;
- scenery: conifer stands on both islands and render-only lanterns along the banks and trail.

The terrain is not changed. Every new solid is a rock, a ramp, a mark pile, a tree, a pole or the
overlook deck.
"""
import math

import numpy as np
from scipy.spatial import ConvexHull

RACE_CENTRE, RACE_AXIS_DEG = (-428., -1972.), 75.
# Surface current along the reach (station s in metres downstream of the centre, speed m/s).
RACE_SPEED = [(-170, .7), (-140, 1.3), (-80, 2.2), (-20, 3.2), (30, 4.1), (90, 3.8), (150, 2.6), (185, 1.6), (205, .9)]
LINE_COLOURS = {'Main Chute': '#ffb05f', 'Rock Garden': '#c792ff', 'Eddy Line': '#68e3ee'}
START_COLOUR = '#f4e6c4'
TRAIL_INSET_M = 13.
TRAIL_WIDTH_M = 7.
FIR_COLOURS = ['#354b42', '#3c5240', '#445a46', '#2f4436', '#4a5a43']


def r2(v):
    return round(float(v), 3)


def convex_solid(ident, points, **extra):
    """A convex mesh obstacle (vertices relative to centre, outward faces, planes) from world points."""
    pts = np.unique(np.round(np.asarray(points, float), 4), axis=0)
    lo, hi = pts.min(0), pts.max(0)
    centre = np.round((lo + hi) / 2, 3)
    local = np.unique(np.round(pts - centre, 3), axis=0)       # planes are computed from the stored vertices
    hull = ConvexHull(local)
    local = local[hull.vertices]
    hull = ConvexHull(local)
    faces = []
    for simplex, eq in zip(hull.simplices, hull.equations):
        a, b, c = local[simplex]
        if np.dot(np.cross(b - a, c - a), eq[:3]) < 0:
            simplex = simplex[[0, 2, 1]]
        faces.append([int(i) for i in simplex])
    planes = np.unique(np.round(hull.equations, 9), axis=0)
    return dict(id=ident, kind='mesh', center=[r2(v) for v in centre], half=[r2(v) for v in np.abs(local).max(0)],
                vertices=[[r2(v) for v in p] for p in local], faces=faces,
                planes=[[float(v) for v in p] for p in planes], **extra)


def terrain(world, x, y):
    """Vectorised copy of the world's triangle interpolation of the height grid."""
    x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
    u = np.clip((x + world.half) / (2 * world.half) * (world.n - 1), 0, world.n - 1.000001)
    v = np.clip((y + world.half) / (2 * world.half) * (world.n - 1), 0, world.n - 1.000001)
    i, j = u.astype(int), v.astype(int)
    a, b = u - i, v - j
    h = np.asarray(world.heights)
    return np.where(a > b, (1 - a) * h[j, i] + (a - b) * h[j, i + 1] + b * h[j + 1, i + 1],
                    (1 - b) * h[j, i] + (b - a) * h[j + 1, i] + a * h[j + 1, i + 1])


class Frame:
    """Race coordinates: s downstream along the narrows axis, n positive to the left of the flow (Heron Island)."""

    def __init__(self, world):
        self.world = world
        self.level = float(world.harbour['waterLevelM'])
        a = math.radians(RACE_AXIS_DEG)
        self.A = np.array([math.cos(a), math.sin(a)])
        self.N = np.array([-self.A[1], self.A[0]])
        self.C = np.array(RACE_CENTRE)

    def xy(self, s, n):
        s, n = np.broadcast_arrays(np.asarray(s, float), np.asarray(n, float))
        return self.C + self.A * s[..., None] + self.N * n[..., None]

    def sn(self, x, y):
        d = np.stack([np.asarray(x, float), np.asarray(y, float)], -1) - self.C
        return d @ self.A, d @ self.N

    def wet(self, s, n):
        p = self.xy(s, n)
        return self.world.harbour_water_mask(p[..., 0], p[..., 1])

    def z(self, s, n):
        p = self.xy(s, n)
        return terrain(self.world, p[..., 0], p[..., 1])

    def clear_land(self, s, n, radius):
        """Dry at the point and at eight points around it."""
        ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        ss = np.asarray(s, float)[..., None] + radius * np.cos(ang)
        nn = np.asarray(n, float)[..., None] + radius * np.sin(ang)
        return ~self.wet(s, n) & ~self.wet(ss, nn).any(-1)


def survey_channel(f):
    """Channel centre offset and half width at every 10 m station where both banks are near."""
    n = np.arange(0., 400., 1.)
    rows = []
    for st in range(-180, 250, 10):
        if not f.wet(st, 0.):
            continue
        west, east = f.wet(st, n), f.wet(st, -n)
        if west.all() or east.all():
            continue
        right, left = n[np.argmax(~west)], n[np.argmax(~east)]
        rows.append((st, (right - left) / 2, (right + left) / 2))
    S, OFF, HW = (np.array(v) for v in zip(*rows))
    return S, OFF, HW


def needle_shores(f):
    """Needle Island's west and east shore (n) at 4 m stations: the first dry run east of the channel."""
    n = -np.arange(20., 340., 1.)
    rows = []
    for st in np.arange(-240., 262., 4.):
        dry = ~f.wet(st, n)
        idx = np.flatnonzero(dry)
        if idx.size == 0:
            continue
        i0 = i1 = idx[0]
        while i1 + 1 < dry.size and dry[i1 + 1]:
            i1 += 1
        if i1 - i0 >= 12:
            rows.append((st, n[i0], n[i1]))
    return np.array(rows)


def chaikin(points, rounds=3):
    p = np.asarray(points, float)
    for _ in range(rounds):
        q, r = p, np.roll(p, -1, axis=0)
        p = np.empty((2 * len(q), 2))
        p[0::2], p[1::2] = .75 * q + .25 * r, .25 * q + .75 * r
    return p


def resample_loop(points, step):
    p = np.vstack([points, points[:1]])
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0.], np.cumsum(seg)])
    t = np.arange(0., cum[-1], cum[-1] / max(8, round(cum[-1] / step)))
    return np.column_stack([np.interp(t, cum, p[:, 0]), np.interp(t, cum, p[:, 1])])


def needle_trail(f, shores):
    """A loop around Needle Island, TRAIL_INSET_M inside its shores, smoothed and kept on dry land."""
    s, nw, ne = shores.T
    kernel = np.ones(5) / 5
    nw = np.convolve(np.pad(nw, 2, mode='edge'), kernel, 'valid')
    ne = np.convolve(np.pad(ne, 2, mode='edge'), kernel, 'valid')
    ok = (nw - ne) >= 2 * TRAIL_INSET_M + 18
    blocks = np.split(np.arange(len(s)), np.flatnonzero(np.diff(ok.astype(int))) + 1)
    block = max((b for b in blocks if ok[b[0]]), key=len)
    s, nw, ne = s[block], nw[block], ne[block]
    west = np.column_stack([s, nw - TRAIL_INSET_M])
    east = np.column_stack([s, ne + TRAIL_INSET_M])[::-1]
    caps = [[s[-1] + 9, (nw[-1] + ne[-1]) / 2], [s[0] - 9, (nw[0] + ne[0]) / 2]]
    loop = np.vstack([west, [caps[0]], east, [caps[1]]])
    loop = resample_loop(chaikin(loop, 3), 6.)
    mid = lambda st: (np.interp(st, s, nw) + np.interp(st, s, ne)) / 2
    for _ in range(12):                                    # nudge any point near water towards the island's spine
        bad = ~f.clear_land(loop[:, 0], loop[:, 1], TRAIL_WIDTH_M / 2 + 4)
        if not bad.any():
            break
        loop[bad, 1] += np.sign(mid(loop[bad, 0]) - loop[bad, 1]) * 1.5
    return loop


def race_lantern_rocks(f, S, OFF, HW, rng):
    centre = lambda st: f.xy(st, np.interp(st, S, OFF))
    at = lambda st, n: f.xy(st, np.interp(st, S, OFF) + n)
    solids, flow_rocks = [], []

    def boulder(ident, st, n, r, top, flat=1.):
        x, y = at(st, n)
        bed = float(terrain(f.world, x, y)) - .4
        ztop = f.level + top
        pts = []
        for _ in range(18):
            u, v = rng.uniform(0, 2 * math.pi), rng.uniform(-.9, .9)
            rad = r * rng.uniform(.82, 1.08)
            pts.append([x + rad * math.cos(u) * math.sqrt(1 - v * v), y + rad * .86 * math.sin(u) * math.sqrt(1 - v * v),
                        bed + (ztop - bed) * (.5 + .5 * v * flat)])
        for k in range(8):                                 # a footing ring seats the rock on the bed
            u = 2 * math.pi * k / 8 + rng.uniform(-.2, .2)
            pts.append([x + .92 * r * math.cos(u), y + .8 * r * math.sin(u), bed - .6])
        pts += [[x, y, ztop], [x + .3 * r, y - .2 * r, ztop - .25 * r]]
        o = convex_solid(ident, pts, role='rock', color='#2a2b30', finish='shell', skin='raceRock', landable=True,
                         rock=dict(radius_m=r2(r), top_m=r2(top)))
        solids.append(o)
        if top > -.6 and f.wet(*f.sn(x, y)):
            flow_rocks.append(dict(x=r2(x), y=r2(y), r_m=r2(r)))
        return o

    big = boulder('lr-rock-lantern', 122, 15, 8., 4.2, flat=.8)
    boulder('lr-rock-throat', 18, -27, 4.5, 1.5)
    # Rocks flank the slalom: each sits outside a turn of the Rock Garden line, 3-6 m off the direct path,
    # and the two just awash (tops at -0.1 m and -0.15 m) show only as boils on the surface.
    garden = [(58, -22, 1.6, .6), (66, -36, 2.4, 1.2), (82, -21, 1.4, -.1), (86, -42, 2.2, .9), (96, -30, 1.8, .4),
              (104, -18, 1.3, -.2), (116, -38, 2.6, 1.4), (126, -26, 1.5, .2), (138, -44, 2.0, .8), (148, -36, 1.7, -.15),
              (158, -20, 1.4, .5), (164, -40, 2.2, 1.0)]
    for k, (st, n, r, top) in enumerate(garden):
        boulder(f'lr-rock-garden-{k}', st, n, r, top)
    for k, st in enumerate(range(-130, 200, 26)):          # bank boulders catch eddies and frame the race
        for side in (1, -1):
            if rng.random() < .7:
                hw = np.interp(st, S, HW)
                boulder(f'lr-rock-bank-{k}-{"w" if side > 0 else "e"}', st, side * (hw - rng.uniform(1., 5.)),
                        rng.uniform(2., 4.2), rng.uniform(.2, 2.4))
    return solids, flow_rocks, big, centre, at


def lantern_race(world):
    f = Frame(world)
    level = f.level
    rng = np.random.default_rng(7707)
    S, OFF, HW = survey_channel(f)
    rocks, flow_rocks, big, centre, at = race_lantern_rocks(f, S, OFF, HW, rng)
    solids = list(rocks)
    speed = lambda st: float(np.interp(st, [q[0] for q in RACE_SPEED], [q[1] for q in RACE_SPEED]))
    stations = [[*map(r2, centre(st)), r2(np.interp(st, S, HW) - 4.), r2(speed(st))]
                for st in range(int(S[1]), int(S[-2]) + 1, 10)]
    s0 = int(S[1])

    def tangent(st):
        t = f.A + f.N * (np.interp(st + 5, S, OFF) - np.interp(st - 5, S, OFF)) / 10.
        return t / np.linalg.norm(t)

    # The beacon mast on the Lantern Rock.
    bx, by = big['center'][:2]
    rock_top = level + 4.2
    solids.append(dict(id='lr-beacon-mast', kind='cylinder', center=[bx, by, r2(rock_top + 4.4)], half=[.35, .35, 4.6],
                       color='#1c1d22', role='architecture', landable=False))

    # Anchored floating ramps, wet and slick (friction 0.22), for planing hulls.
    def water_ramp(ident, st, n, turn, length, lip, width, purpose):
        x, y = at(st, n)
        t = tangent(st)
        heading = math.atan2(t[1], t[0]) + turn
        ca, sa = math.cos(heading), math.sin(heading)
        entry = level - .55
        pts = []
        for u, z in ((-length / 2, entry), (length / 2, level + lip), (length / 2, entry - .4), (-length / 2, entry - .4)):
            for v in (-width / 2, width / 2):
                pts.append([x + u * ca - v * sa, y + u * sa + v * ca, z])
        o = convex_solid(ident, pts, role='ramp', color='#1d1e22', finish='shell', skin='waterRamp', landable=True,
                         friction=.22, ramp=dict(kind=purpose, heading=r2(heading), length_m=length, height_m=lip,
                                                 width_m=width, top_m=0., floating=True))
        solids.append(o)

    water_ramp('lr-ramp-chute-kicker', 184, 3, 0., 14., 1.35, 7., 'planing-hull kicker')
    water_ramp('lr-ramp-garden-hop', 170, -30, .12, 8., .8, 4.5, 'small-craft hop')
    water_ramp('lr-ramp-deep-outlier', 204, 34, -.30, 20., 3.0, 7., 'deep-water outlier')

    # Lantern piles and three lines through the race, sharing a start and a finish.
    marks = {}

    def gate(key, st, n, width, colour):
        x, y = at(st, n)
        t = tangent(st)
        right = np.array([-t[1], t[0]])
        ids = []
        for side in (-1, 1):
            mx, my = np.array([x, y]) + right * side * (width / 2 + .8)
            ident = f'lr-mark-{key}-{"a" if side < 0 else "b"}'
            bed = min(float(terrain(world, mx, my)) - .5, level - 1.)
            top = level + 3.4
            marks[ident] = dict(id=ident, kind='cylinder', center=[r2(mx), r2(my), r2((bed + top) / 2)],
                                half=[.55, .55, r2((top - bed) / 2)], color=colour, role='race-mark', landable=False)
            ids.append(ident)
        return dict(center=[r2(x), r2(y), level], normal=[r2(t[0]), r2(t[1])], width_m=width, marks=ids, station_m=float(st))

    start = gate('start', -140, 0, 70., START_COLOUR)
    finish = gate('finish', 250, 0, 76., START_COLOUR)
    plan = {
        'Main Chute': [(-40, 2, 26.), (32, 4, 22.), (96, -1, 22.), (164, 3, 18.)],
        'Rock Garden': [(44, -24, 14.), (72, -31, 12.), (100, -24, 12.), (132, -35, 12.), (160, -27, 14.)],
        'Eddy Line': [(-60, 34, 16.), (18, 26, 14.), (76, 12, 14.), (124, 33, 12.), (192, 30, 16.)],
    }
    races = []
    flow = math.atan2(f.A[1], f.A[0])
    sx, sy = at(-185, 0)
    for name, line in plan.items():
        key = name.lower().replace(' ', '-')
        gates = [start] + [gate(f'{key}-{k + 1}', st, n, w, LINE_COLOURS[name]) for k, (st, n, w) in enumerate(line)] + [finish]
        pts = [[r2(sx), r2(sy)]] + [g['center'][:2] for g in gates]
        length = sum(math.dist(a['center'][:2], b['center'][:2]) for a, b in zip(gates, gates[1:]))
        races.append(dict(id='lantern-race-' + key, name='Lantern Race · ' + name, colour=LINE_COLOURS[name],
                          gates=gates, points=pts, length_m=r2(length), position=[r2(sx), r2(sy)],
                          heading_rad=r2(flow), sprint=True))
    solids.extend(marks.values())

    # Needle Island: trail loop, tabletop, slipway and overlook deck.
    shores = needle_shores(f)
    trail_sn = needle_trail(f, shores)
    trail_xy = f.xy(trail_sn[:, 0], trail_sn[:, 1])
    trail = [[r2(x), r2(y)] for x, y in trail_xy] + [[r2(trail_xy[0, 0]), r2(trail_xy[0, 1])]]
    roads = [dict(name='Needle Island trail', kind='track', width_m=TRAIL_WIDTH_M, points=trail, edge_color='#8f6f37',
                  surface_color='#4a4136', mitre=True)]

    # Slipway: from the trail's northern apex straight down into the exit pool.
    apex = int(np.argmax(trail_sn[:, 0]))
    a_s, a_n = trail_sn[apex]
    land = np.array([a_s + TRAIL_WIDTH_M / 2 + .6, a_n])
    run = 6.
    while run < 60 and not (f.wet(land[0] + run, land[1]) and float(f.z(land[0] + run, land[1])) < level - 1.4):
        run += 1.
    run += 4.
    p0, p1 = f.xy(*land), f.xy(land[0] + run, land[1])
    z0 = float(f.z(*land)) + .15
    z1 = level - 1.3
    along = np.linspace(0, 1, 12)
    under = float(terrain(world, p0[0] + (p1[0] - p0[0]) * along, p0[1] + (p1[1] - p0[1]) * along).min())
    pts = []
    for p, z in ((p0, z0), (p1, z1)):
        for v in (-4., 4.):
            q = p + f.N * v
            pts += [[q[0], q[1], z], [q[0], q[1], min(under, z) - 1.]]
    solids.append(convex_solid('lr-slipway', pts, role='ramp', color='#4a4740', finish='shell', skin='slipway', landable=True,
                               ramp=dict(kind='amphibious slipway', heading=r2(flow), length_m=r2(run), height_m=r2(z0 - z1),
                                         width_m=8., top_m=0.)))

    # Tabletop on the flattest stretch of the trail (up 9 m, top 6 m, down 9 m, 1.2 m high).
    d = np.diff(np.vstack([trail_sn, trail_sn[:1]]), axis=0)
    heading_sn = np.arctan2(d[:, 1], d[:, 0])
    turn = np.abs(np.angle(np.exp(1j * (np.roll(heading_sn, -3) - np.roll(heading_sn, 3)))))
    zt = f.z(trail_sn[:, 0], trail_sn[:, 1])
    grade = np.abs(np.roll(zt, -2) - np.roll(zt, 2)) / 24.
    side = np.abs(f.z(trail_sn[:, 0] + 3 * np.sin(heading_sn), trail_sn[:, 1] - 3 * np.cos(heading_sn))
                  - f.z(trail_sn[:, 0] - 3 * np.sin(heading_sn), trail_sn[:, 1] + 3 * np.cos(heading_sn))) / 6.
    far = np.hypot(trail_sn[:, 0] - a_s, trail_sn[:, 1] - a_n) > 60
    k = int(np.argmin(np.where(far, turn + 2 * grade + 3 * side, 9.)))
    tx, ty = trail_xy[k]
    tdir = trail_xy[(k + 1) % len(trail_xy)] - trail_xy[(k - 1) % len(trail_xy)]
    tdir = tdir / np.linalg.norm(tdir)
    tnorm = np.array([-tdir[1], tdir[0]])

    def trail_block(ident, u0, u1, h0, h1, purpose):
        pts = []
        base = []
        for u, h in ((u0, h0), (u1, h1)):
            c = np.array([tx, ty]) + tdir * u
            for v in (-3.4, 3.4):
                q = c + tnorm * v
                g = float(terrain(world, *q))
                base.append(g)
                pts.append([q[0], q[1], g + h])
        low = min(base) - .6
        pts += [[p[0], p[1], low] for p in pts]
        solids.append(convex_solid(ident, pts, role='ramp', color='#24252a', finish='shell', skin='trailRamp', landable=True,
                                   ramp=dict(kind=purpose, heading=r2(math.atan2(tdir[1], tdir[0])), length_m=abs(u1 - u0),
                                             height_m=max(h0, h1), width_m=6.8, top_m=0.)))

    trail_block('lr-trail-table-up', -12., -3., 0., 1.2, 'tabletop up-ramp')
    trail_block('lr-trail-table-top', -3., 3., 1.2, 1.2, 'tabletop deck')
    trail_block('lr-trail-table-down', 3., 12., 1.2, 0., 'tabletop down-ramp')

    # Overlook deck: the flattest 28 x 20 m footprint uphill of the trail's west leg, facing the race.
    best = None
    sh_s, sh_w = shores[:, 0], shores[:, 1]
    for st in np.arange(10., 125., 5.):
        nw = float(np.interp(st, sh_s, sh_w))
        for off in np.arange(32., 56., 2.):
            n0 = nw - off
            ss, nn = np.meshgrid(st + np.linspace(-14, 14, 8), n0 + np.linspace(-10, 10, 6))
            if f.wet(ss, nn).any():
                continue
            gap = np.min(np.maximum(np.abs(trail_sn[:, 0] - st) - 14, np.abs(trail_sn[:, 1] - n0) - 10))
            if gap < TRAIL_WIDTH_M / 2 + 9:
                continue
            z = f.z(ss, nn)
            score = (z.max() - z.min()) - .12 * z.mean() + .02 * off
            if best is None or score < best[0]:
                best = (score, st, n0, float(z.min()), float(z.max()))
    _, os_, on_, zlo, zhi = best
    deck = zhi + .4
    spread = min(3., .25 * (deck - zlo + .8))             # basalt shelf: the cliff faces lean out towards the foot
    corners = [f.xy(os_ + u, on_ + v) for u in (-14., 14.) for v in (-10., 10.)]
    feet = [f.xy(os_ + u * (1 + spread / 14), on_ + v * (1 + spread / 10)) for u in (-14., 14.) for v in (-10., 10.)]
    pts = [[c[0], c[1], deck] for c in corners] + [[c[0], c[1], zlo - .8] for c in feet]
    overlook = convex_solid('lr-overlook', pts, role='architecture', color='#2c2c30', finish='shell', skin='basaltShelf',
                            landable=True)
    solids.append(overlook)
    ox, oy = f.xy(os_, on_)
    for k, (u, v) in enumerate(((-13.4, -9.4), (13.4, -9.4), (-13.4, 9.4), (13.4, 9.4))):
        px, py = f.xy(os_ + u, on_ + v)
        solids.append(dict(id=f'lr-banner-pole-{k}', kind='cylinder', center=[r2(px), r2(py), r2(deck + 3.)], half=[.12, .12, 3.],
                           color='#16171b', role='architecture', landable=False))

    # Render-only lanterns: along both banks of the race and around the trail.
    lanterns = []
    bank_stations = [(st, sgn) for sgn in (1, -1) for st in np.cumsum(np.r_[-150 + 9 * (sgn < 0), rng.uniform(13, 23, 30)])
                     if st < 236]
    for st, sgn in bank_stations:
        hw, off = np.interp(st, S, HW), np.interp(st, S, OFF)
        for _ in (0,):
            for extra in np.arange(2., 14., 1.):
                n = off + sgn * (hw + extra)
                if f.clear_land(st, n, 1.5) and level + .6 < float(f.z(st, n)) < level + 9:
                    x, y = f.xy(st, n)
                    lanterns.append([r2(x), r2(y), r2(terrain(world, x, y))])
                    break
    for k in range(0, len(trail_sn), 5):
        s_, n_ = trail_sn[k]
        h = heading_sn[k]
        out = (s_ + 5.2 * math.sin(h), n_ - 5.2 * math.cos(h))
        if f.clear_land(*out, 1.):
            x, y = f.xy(*out)
            lanterns.append([r2(x), r2(y), r2(terrain(world, x, y))])

    # Conifer stands on both islands, clear of the water, trail, deck, slipway and lanterns.
    keep = [(np.array([ox, oy]), 24.), (np.array(f.xy(*land)), 12.), (np.array(f.xy(land[0] + run, land[1])), 12.)]
    keep += [(np.array([tx, ty]), 16.)]
    stands = [(rng.uniform(-200, 250), rng.uniform(-260, 300), rng.uniform(28, 60)) for _ in range(20)]
    trees = []
    for gs in np.arange(-230., 262., 10.):
        for gn in np.arange(-300., 320., 10.):
            s_, n_ = gs + rng.uniform(-3.5, 3.5), gn + rng.uniform(-3.5, 3.5)
            dens = sum(math.exp(-((s_ - a) ** 2 + (n_ - b) ** 2) / (2 * r * r)) for a, b, r in stands)
            if rng.random() > min(.7, .02 + .75 * dens):
                continue
            if not f.clear_land(s_, n_, 9.):
                continue
            g = float(f.z(s_, n_))
            if g < level + 1.8 or g - float(f.z(s_ + 4, n_)) > 2.6 or g - float(f.z(s_, n_ + 4)) > 2.6:
                continue
            x, y = f.xy(s_, n_)
            if np.min(np.hypot(trail_xy[:, 0] - x, trail_xy[:, 1] - y)) < TRAIL_WIDTH_M / 2 + 4:
                continue
            if any(np.hypot(*(np.array([x, y]) - c)) < r for c, r in keep):
                continue
            if lanterns and min(math.hypot(x - q[0], y - q[1]) for q in lanterns) < 4:
                continue
            if trees and min(math.hypot(x - q[0], y - q[1]) for q, _ in trees[-60:]) < 5:
                continue
            inland = min(1., max(0., (g - level) / 18.))
            height = (9. + 8. * inland) * rng.uniform(.8, 1.15)
            trees.append(((x, y), (g, height)))
    for k, ((x, y), (g, height)) in enumerate(trees):
        bottom = g - .4
        solids.append(dict(id=f'lr-fir-{k}', kind='cylinder', center=[r2(x), r2(y), r2(bottom + height / 2)],
                           half=[r2(.019 * height), r2(.019 * height), r2(height / 2)], role='conifer', landable=False,
                           color=FIR_COLOURS[k % len(FIR_COLOURS)], crown_radius_m=r2(.19 * height)))

    # The Low Line: low hoops down the race, a held touchdown on the overlook, out over the island.
    def low_hoop(st, n, height, radius):
        x, y = at(st, n)
        t = tangent(st)
        return dict(type='hoop', center=[r2(x), r2(y), r2(level + height)], normal=[r2(t[0]), r2(t[1]), 0.],
                    right=[r2(-t[1]), r2(t[0]), 0.], up=[0., 0., 1.], radius_m=radius)

    hoops = [low_hoop(-150, 0, 18, 12.), low_hoop(-40, 2, 14, 10.), low_hoop(36, 4, 12, 9.), low_hoop(122, -12, 12, 8.),
             low_hoop(198, 2, 16, 10.)]
    land_step = dict(type='land', shape='circle', center=[r2(ox), r2(oy), r2(deck)], radius_m=9., hold_s=3.,
                     max_speed_m_s=.8, pad='lr-overlook')
    es = os_ + 40.
    en = float(np.interp(es, sh_s, shores[:, 2])) - 40.
    ex, ey = f.xy(es, en)
    exit_hoop = dict(type='hoop', center=[r2(ex), r2(ey), r2(float(terrain(world, ex, ey)) + 34.)],
                     normal=[r2(-f.N[0]), r2(-f.N[1]), 0.], right=[r2(f.N[1]), r2(-f.N[0]), 0.], up=[0., 0., 1.], radius_m=14.)
    low_line = dict(name='Lantern Race · Low Line', zone='Lantern Sound', spawn=[r2(ox), r2(oy)], length_m=900.,
                    pad='lr-overlook', size='M', tier='silver', steps=hoops + [land_step, exit_hoop],
                    brief='Lift off the basalt shelf on Needle Island, fly five low hoops down the race past the Lantern Rock '
                          'beacon, settle back on the shelf for three seconds and leave east through the hoop over the island.')
    rapid = dict(id='lantern-race', name='Lantern Race', stations=stations, margin_m=12., reach_margin_m=40., eddy_fraction=.28,
                 boil_amplitude_m=.06, waves=dict(from_m=float(30 - s0), to_m=float(160 - s0), amplitude_m=.5), rocks=flow_rocks)
    info = dict(centre=list(RACE_CENTRE), axis_deg=RACE_AXIS_DEG, water_level_m=level, rapid=rapid, races=races,
                overlook=dict(id='lr-overlook', center=[r2(ox), r2(oy), r2(deck)], half=[14., 10.],
                              heading=r2(flow)),
                beacon=[r2(bx), r2(by), r2(rock_top + 9.1)], lanterns=lanterns,
                trail=dict(points=trail, width_m=TRAIL_WIDTH_M), trees=len(trees))
    return solids, roads, rapid, races, low_line, info
