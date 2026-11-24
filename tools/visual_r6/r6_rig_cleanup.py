"""Build a cleaned R6 rig from the connected rig: every floating part and free rod end is joined to its mount.

usage: python r6_rig_cleanup.py <in.glb> <out.glb> <log.json> [<audit.json of the input>]

What it may change (owner-approved cleanup, 24 Nov 2026):
  * a part node's translation / rotation / scale (move it onto its mount, or lengthen a rod to reach its mount);
  * the parent of one part (IMU/flight ECU moves from airframe to cabin, keeping its world position);
  * the index lists of the two CFRP cabin shells (zero-area triangles removed, nothing visible changes);
  * extras on the four shaft containers (vtx_spin_centre: the visual shaft centreline, for the cockpit).
What it never changes: the 20 body containers (simulator pivots), vertex positions, materials, names.
Every edit is logged with the part, the operation and the distance moved.
"""
from __future__ import annotations

import json
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import r6_glb as K  # noqa: E402

src, dst, log_path = sys.argv[1:4]
audit = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else None
OVERLAP = 0.0005   # final penetration so contact is unambiguous (m)
TOUCH = 0.0003     # contact reached during a search (m)

blob = open(src, 'rb').read()
jlen = struct.unpack_from('<I', blob, 12)[0]
G = json.loads(blob[20:20 + jlen])
off = 20 + jlen + 8
BIN = bytearray(blob[off:off + struct.unpack_from('<I', blob, 20 + jlen)[0]])
M = K.GLBModel(G, bytes(BIN))
PARTS = {p['name']: p for p in M.parts}
NODE = {n.get('name'): i for i, n in enumerate(G['nodes'])}
PARENT = {c: i for i, n in enumerate(G['nodes']) for c in n.get('children', [])}
BODY_OF = {p['name']: p['body'] for p in M.parts}
LOG = []
_geo = {}


# ---------------------------------------------------------------- transforms
def node_world(i):
    m = K.local(G['nodes'][i])
    while i in PARENT:
        i = PARENT[i]
        m = K.local(G['nodes'][i]) @ m
    return m


def subtree(i):
    out = [i]
    for c in G['nodes'][i].get('children', []):
        out += subtree(c)
    return out


def mat_quat(R):
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q)


def set_world(i, W):
    """Give node i the world matrix W (rotation*scale + translation), stored as TRS in its parent frame."""
    L = np.linalg.inv(node_world(PARENT[i])) @ W
    S = np.linalg.norm(L[:3, :3], axis=0)
    R = L[:3, :3] / S
    n = G['nodes'][i]
    n.pop('matrix', None)
    n['translation'] = [float(v) for v in L[:3, 3]]
    n['rotation'] = [float(v) for v in mat_quat(R)]
    if np.allclose(S, 1, atol=1e-9):
        n.pop('scale', None)
    else:
        n['scale'] = [float(v) for v in S]
    for k in subtree(i):
        for name, p in PARTS.items():
            if p['node'] == k:
                _geo.pop(name, None)


def verts(name):
    p = PARTS[name]
    W = node_world(p['node'])
    return p['V'] @ W[:3, :3].T + W[:3, 3]


def geo(name):
    if name not in _geo:
        _geo[name] = K.Geo(PARTS[name], verts(name))
    return _geo[name]


# ---------------------------------------------------------------- distances
def true_distance(g, h):
    if np.all((g.lo <= h.hi + K.NEAR) & (g.hi >= h.lo - K.NEAR)):
        return K.pair_distance(g, h)
    d1 = K.chunked_min_d2(g.W, h.tri[:, 0], h.tri[:, 1], h.tri[:, 2])
    d2 = K.chunked_min_d2(h.W, g.tri[:, 0], g.tri[:, 1], g.tri[:, 2])
    return float(np.sqrt(min(np.min(d1), np.min(d2))))


def closest_on_tri(p, a, b, c):
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0:
        return a
    bp = p - b
    d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return a + ab * (d1 / (d1 - d3))
    cp = p - c
    d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return a + ac * (d2 / (d2 - d6))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)))
    den = 1 / (va + vb + vc)
    return a + ab * (vb * den) + ac * (vc * den)


def closest_pair(group, anchors):
    """(distance, point on group, point on anchor) over all group/anchor parts."""
    best = (np.inf, None, None)
    for gn in group:
        g = geo(gn)
        for an in anchors:
            h = geo(an)
            for a, b, flip in ((g, h, False), (h, g, True)):
                d = K.pt_tri_d2(a.W, b.tri[:, 0], b.tri[:, 1], b.tri[:, 2]) if len(a.W) * len(b.tri) < 6e6 else None
                if d is None:
                    dv = K.chunked_min_d2(a.W, b.tri[:, 0], b.tri[:, 1], b.tri[:, 2])
                    vi = int(np.argmin(dv))
                    dt = K.pt_tri_d2(a.W[vi:vi + 1], b.tri[:, 0], b.tri[:, 1], b.tri[:, 2])[0]
                    ti = int(np.argmin(dt))
                    dist = math.sqrt(dt[ti])
                else:
                    vi, ti = np.unravel_index(int(np.argmin(d)), d.shape)
                    dist = math.sqrt(d[vi, ti])
                if dist < best[0]:
                    p = a.W[vi]
                    q = closest_on_tri(p, *b.tri[ti])
                    best = (dist, q, p) if flip else (dist, p, q)
    return best


def group_gap(group, anchors):
    return min(true_distance(geo(g), geo(a)) for g in group for a in anchors)


# ---------------------------------------------------------------- operations
def translate(group, delta):
    for name in group:
        i = PARTS[name]['node']
        W = node_world(i)
        W[:3, 3] += delta
        set_world(i, W)


def touch(group, anchors, direction=None, why=''):
    """Move a rigid group until it just touches the anchors (straight at them, or along `direction`)."""
    if len(anchors) > 20:  # keep only anchors near the group
        lo = np.min([geo(g).lo for g in group], 0) - 0.4
        hi = np.max([geo(g).hi for g in group], 0) + 0.4
        anchors = [a for a in anchors if np.all((geo(a).lo <= hi) & (geo(a).hi >= lo))]
    d0 = group_gap(group, anchors)
    if d0 <= 0.001:
        LOG.append(dict(op='touch', parts=group, anchors=anchors[:3], moved_mm=0.0, why=why, note='already touching'))
        return
    if direction is None:
        dist, p, q = closest_pair(group, anchors)
        v = q - p
        u = v / np.linalg.norm(v)
        move = u * (dist + OVERLAP)
        translate(group, move)
    else:
        u = np.asarray(direction, float) / np.linalg.norm(direction)
        lo, hi = 0.0, None
        t = d0
        while hi is None:
            translate(group, u * (t - lo))
            if group_gap(group, anchors) <= TOUCH:
                hi = t
            else:
                lo, t = t, t + max(0.002, d0 * 0.25)
                if t > 1.0:
                    raise SystemExit(f'touch: {group} never reaches {anchors[:3]} along {direction}')
        cur = hi
        for _ in range(25):
            mid = (lo + hi) / 2
            translate(group, u * (mid - cur))
            cur = mid
            if group_gap(group, anchors) <= TOUCH:
                hi = mid
            else:
                lo = mid
        translate(group, u * (hi + OVERLAP - cur))
        move = u * (hi + OVERLAP)
    LOG.append(dict(op='touch', parts=group, anchors=anchors[:3], moved_mm=round(float(np.linalg.norm(move)) * 1000, 2),
                    direction=[round(float(x), 4) for x in move / np.linalg.norm(move)], why=why))


def long_axis(name):
    V = PARTS[name]['V']
    ext = V.max(0) - V.min(0)
    return int(np.argmax(ext))


def end_caps(name, k):
    V = PARTS[name]['V']
    lo, hi = V[:, k].min(), V[:, k].max()
    band = 0.02 * (hi - lo)
    return {'min': np.nonzero(V[:, k] <= lo + band)[0], 'max': np.nonzero(V[:, k] >= hi - band)[0]}


def cap_gap(name, idx, anchors):
    pts = geo(name).W[idx]
    best = np.inf
    for a in anchors:
        h = geo(a)
        if np.all((h.hi >= pts.min(0) - 0.3) & (h.lo <= pts.max(0) + 0.3)):
            if K.inside(pts, h).any():
                return 0.0
            best = min(best, float(np.sqrt(np.min(K.chunked_min_d2(pts, h.tri[:, 0], h.tri[:, 1], h.tri[:, 2])))))
    return best


def stretch(name, end, anchors, max_ext=0.15, why=''):
    """Lengthen a rod along its own long axis at one end (the other end stays put) until that end meets an anchor."""
    i = PARTS[name]['node']
    n = G['nodes'][i]
    k = long_axis(name)
    V = PARTS[name]['V']
    lo, hi = V[:, k].min(), V[:, k].max()
    L = hi - lo
    caps = end_caps(name, k)
    if end == 'low' or end == 'high' or end == 'inner':
        W = verts(name)
        zc = {e: W[caps[e]].mean(0) for e in caps}
        if end == 'inner':
            end = min(caps, key=lambda e: np.linalg.norm(zc[e][:2]))
        else:
            end = min(caps, key=lambda e: zc[e][2]) if end == 'low' else max(caps, key=lambda e: zc[e][2])
    if cap_gap(name, caps[end], anchors) <= 0.001:
        LOG.append(dict(op='stretch', part=name, end=end, extended_mm=0.0, why=why, note='already touching'))
        return
    T0 = np.array(n.get('translation', [0, 0, 0]), float)
    R0 = K.quat_mat(n.get('rotation', [0, 0, 0, 1]))
    S0 = np.array(n.get('scale', [1, 1, 1]), float)
    fixed = lo if end == 'max' else hi
    world_per_local = float(np.linalg.norm(node_world(i)[:3, k]))

    def apply(delta_world):
        f = (L + delta_world / world_per_local) / L
        S = S0.copy()
        S[k] *= f
        e = np.zeros(3)
        e[k] = fixed * (1 - f)
        n['translation'] = [float(v) for v in T0 + R0 @ (S0 * e)]
        n['scale'] = [float(v) for v in S]
        _geo.pop(name, None)

    lo_d, hi_d, t = 0.0, None, 0.001
    while hi_d is None:
        apply(t)
        if cap_gap(name, caps[end], anchors) <= TOUCH:
            hi_d = t
        else:
            lo_d, t = t, t + 0.002
            if t > max_ext:
                apply(0.0)
                LOG.append(dict(op='stretch', part=name, end=end, extended_mm=None, why=why, note=f'no anchor within {max_ext} m; left unchanged'))
                return
    for _ in range(25):
        mid = (lo_d + hi_d) / 2
        apply(mid)
        if cap_gap(name, caps[end], anchors) <= TOUCH:
            hi_d = mid
        else:
            lo_d = mid
    apply(hi_d + OVERLAP)
    LOG.append(dict(op='stretch', part=name, end=end, axis=int(k), extended_mm=round((hi_d + OVERLAP) * 1000, 2),
                    length_m=round(L * world_per_local, 4), why=why))


def place(name, centre_world, axis_world, length_world=None, why=''):
    """Put a rod-like part with its long axis along axis_world, centred at centre_world (optionally a new length)."""
    i = PARTS[name]['node']
    k = long_axis(name)
    V = PARTS[name]['V']
    c_local = (V.max(0) + V.min(0)) / 2
    W0 = node_world(i)
    S0 = np.linalg.norm(W0[:3, :3], axis=0)
    a = np.asarray(axis_world, float) / np.linalg.norm(axis_world)
    src_axis = np.eye(3)[k]
    v = np.cross(src_axis, a)
    s, c = np.linalg.norm(v), src_axis @ a
    if s < 1e-12:
        R = np.eye(3) if c > 0 else -np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)
    S = S0.copy()
    if length_world:
        S[k] = length_world / (V[:, k].max() - V[:, k].min())
    W = np.eye(4)
    W[:3, :3] = R * S
    W[:3, 3] = np.asarray(centre_world) - (R * S) @ c_local
    before = verts(name).mean(0)
    set_world(i, W)
    LOG.append(dict(op='place', part=name, moved_mm=round(float(np.linalg.norm(verts(name).mean(0) - before)) * 1000, 1),
                    centre=[round(float(x), 4) for x in centre_world], axis=[round(float(x), 4) for x in a],
                    length_m=length_world, why=why))


def reparent(name, container, why=''):
    i = PARTS[name]['node']
    W = node_world(i)
    old = PARENT[i]
    G['nodes'][old]['children'].remove(i)
    if not G['nodes'][old]['children']:
        G['nodes'][old].pop('children')
    new = NODE[container]
    G['nodes'][new].setdefault('children', []).append(i)
    PARENT[i] = new
    set_world(i, W)
    ex = G['nodes'][i].get('extras')
    if ex and 'physical_body' in ex:
        ex['physical_body'] = container
    PARTS[name]['body'] = container
    LOG.append(dict(op='reparent', part=name, old=G['nodes'][old].get('name'), new=container, why=why))


def drop_degenerate(name):
    removed = 0
    for prim in G['meshes'][G['nodes'][PARTS[name]['node']]['mesh']]['primitives']:
        a = G['accessors'][prim['indices']]
        idx = M.accessor(prim['indices']).astype(np.int64).reshape(-1, 3)
        P = M.accessor(prim['attributes']['POSITION']).astype(float)
        t = P[idx]
        area = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) / 2
        keep = idx[area >= 1e-12]
        if len(keep) == len(idx):
            continue
        # The index list may be shared with another mesh, so this primitive gets its own new index accessor
        # (appended to the binary buffer); the original list is left as it is for any other user.
        dt = np.dtype(K.CT[a['componentType']])
        BIN.extend(b'\0' * (-len(BIN) % 4))
        start = len(BIN)
        data = keep.astype(dt).tobytes()
        BIN.extend(data)
        G['bufferViews'].append(dict(buffer=0, byteOffset=start, byteLength=len(data), target=34963))
        G['accessors'].append(dict(bufferView=len(G['bufferViews']) - 1, componentType=a['componentType'],
                                   count=int(keep.size), type='SCALAR'))
        prim['indices'] = len(G['accessors']) - 1
        G['buffers'][0]['byteLength'] = len(BIN)
        removed += len(idx) - len(keep)
    LOG.append(dict(op='drop_zero_area_triangles', part=name, removed=removed))


def body_parts(body, prefix=None, exclude=()):
    return [n for n, p in PARTS.items() if p['body'] == body and (prefix is None or n.startswith(prefix)) and n not in exclude]


FLOATING = {n for f in (audit or {}).get('floating_groups', []) for n in f['parts']}

# ================================================================ the cleanup
for shell in ('P04 | CFRP lower spherical sandwich', 'P04 | CFRP upper spherical sandwich'):
    drop_degenerate(shell)

# Landing gear: the foot goes back onto the physics contact box (gear-local origin, same 0.35 x 0.35 x 0.075 m size);
# the piston is lengthened down to it. Fixes feet drawn 250 mm above the physics contact and the 34 mm gap.
for i in range(1, 7):
    foot = f'V4 P10 | LANDING leg{i} replaceable contact foot'
    n = G['nodes'][PARTS[foot]['node']]
    before = verts(foot).mean(0)
    n['translation'] = [0.0, 0.0, 0.0]
    _geo.pop(foot, None)
    LOG.append(dict(op='place', part=foot, moved_mm=round(float(np.linalg.norm(verts(foot).mean(0) - before)) * 1000, 1),
                    why='onto the physics gear contact box (gear-local origin)'))
    stretch(f'V4 P10 | LANDING leg{i} sliding piston and hardstop', 'low', [foot], max_ext=0.40,
            why='piston reaches the foot')

for j in range(1, 5):
    nac = f'nacelle{j}'
    vanes = [n for n in PARTS if n.startswith(f'P02 | F{j} fixed stator vane ')]
    duct_side = body_parts(nac, exclude=vanes)
    for v in vanes:
        for e in ('min', 'max'):
            stretch(v, e, duct_side, max_ext=0.02, why='stator vane reaches duct wall / stator boss')
    touch([f'Phase2_Duct_Lip_Glow_F{j}'], [f'P02 | F{j} nacelle inlet lip'], why='glow ring sits on the inlet lip')
    rotor = f'rotor{j}'
    for b in range(1, 5):
        link = f'V2 P02 | F{j} blade{b} pitch link'
        if link in PARTS:
            for e in ('min', 'max'):
                stretch(link, e, body_parts(rotor, exclude=[link]), max_ext=0.02, why='pitch link reaches the hub')
    stretch(f'P03 | F{j} radial drive shaft', 'inner', ['P03 | Four way reduction gearbox'], max_ext=0.25,
            why='radial drive shaft reaches the central four-way gearbox')

# Cabin: floor onto the shell, seats onto the floor, IMU into the cabin and onto the floor, panel spans wall to wall.
shell_parts = body_parts('cabin', prefix='P04 |')
touch(['V3 P04 | Lightweight nonstructural cabin footwell floor'], ['P04 | CFRP lower spherical sandwich'], direction=[0, 0, -1],
      why='floor rests on the lower shell')
floor = ['V3 P04 | Lightweight nonstructural cabin footwell floor']
for s in (1, 2):
    touch([f'P09 | Seat {s} headrest'], [f'P09 | Seat {s} backrest'], direction=[0, 0, -1], why='headrest on its backrest')
    for h in (f'P09 | Seat {s} harness', f'P09 | Seat {s} harness.001'):
        for e in ('min', 'max'):
            stretch(h, e, [f'P09 | Seat {s} cushion', f'P09 | Seat {s} backrest'], max_ext=0.02, why='harness strap anchored on the seat')
    seat = [f'P09 | Seat {s} cushion', f'P09 | Seat {s} backrest', f'P09 | Seat {s} headrest',
            f'P09 | Seat {s} harness', f'P09 | Seat {s} harness.001']
    touch(seat, floor, direction=[0, 0, -1], why='seat stands on the footwell floor')
reparent('P08 | Independent IMU/flight ECU', 'cabin', why='it sits inside the gimballed cabin, behind the seats')
touch(['P08 | Independent IMU/flight ECU'], floor, direction=[0, 0, -1], why='IMU/ECU stands on the cabin floor')
for e in ('min', 'max'):
    stretch('P08 | Cockpit panel', e, shell_parts, max_ext=0.25, why='cockpit panel spans to the cabin shell')
touch(['P08 | Instrument screen'], ['P08 | Cockpit panel'], direction=[0, 1, 0], why='screen mounted on the panel face')
touch(['P08 | Instrument screen.001', 'V3 P08 | Physical guarded descent/land switch', 'V3 P08 | Physical hover-hold switch'],
      ['P08 | Cockpit panel'], direction=[0, 1, 0], why='screen and switches mounted on the panel face')

# Yoke: the stem and lateral grip bar were left at the aircraft origin. The bar runs between the two cushioned grips
# (x -0.38 / -0.10, y -0.73, z 1.245) through the yaw dial; the stem runs forward from the yoke base to the bar.
base = geo('V3 P08 | Compact flight yoke base')
gl, gr = geo('V3 P08 | Yoke cushioned grip'), geo('V3 P08 | Yoke cushioned grip.001')
bar_c = ((gl.lo + gl.hi) / 2 + (gr.lo + gr.hi) / 2) / 2
place('V3 P08 | Yoke lateral grips', bar_c, [1, 0, 0], why='grip bar between the two cushioned grips')
bar = geo('V3 P08 | Yoke lateral grips')
x_mid, z_mid = (base.lo[0] + base.hi[0]) / 2, min(base.hi[2] - 0.016, bar_c[2])
y0, y1 = base.lo[1] + 0.003, bar.hi[1] - 0.003           # 3 mm into the base and into the bar
place('V3 P08 | Short-stroke fly-by-wire yoke stem', [x_mid, (y0 + y1) / 2, z_mid], [0, -1, 0], length_world=abs(y1 - y0),
      why='stem from the yoke base forward to the grip bar')

# Airframe avionics and fuel-bay clamps: each moved straight onto the nearest structure it should bolt to.
airframe_fixed = [n for n in body_parts('airframe') if n not in FLOATING]
for g in (['P11 | Power distribution module', 'V3 P08 | FCC redundant controller bay 2'],
          ['V3 P08 | Independent AHRS inertial sensor 3']):
    touch(g, airframe_fixed, why='avionics bolted to the nearest airframe structure')
for b in range(1, 5):
    for c in (1, 2):
        touch([f'V4 P07 | BAY{b} clamp attach {c}'], [f'P07 | F{b} protected fuel cell'], why='clamp attach on its fuel cell')

# Free rod ends on the airframe.
for part in ('P01 | Mount A', 'P01 | Mount B', 'V2 P06 | Turbine/gearbox lower cradle side 1', 'V2 P06 | Turbine/gearbox lower cradle side -1'):
    for e in ('min', 'max'):
        stretch(part, e, [n for n in airframe_fixed if n != part], max_ext=0.10, why='strut end reaches its mount')

# Shaft containers: record the visual centreline so the cockpit spins each shaft in place (physics unchanged).
for j in range(1, 5):
    shaft = f'P03 | F{j} radial drive shaft'
    ci = NODE[f'shaft{j}']
    Wc = node_world(ci)
    c_local = np.linalg.inv(Wc) @ np.append((geo(shaft).lo + geo(shaft).hi) / 2, 1.0)
    G['nodes'][ci].setdefault('extras', {})['vtx_spin_centre'] = [round(float(v), 6) for v in c_local[:3]]
    LOG.append(dict(op='spin_centre', container=f'shaft{j}', vtx_spin_centre=G['nodes'][ci]['extras']['vtx_spin_centre']))

G.setdefault('asset', {}).setdefault('extras', {})['vtx_cleanup'] = 'r6_rig_cleanup.py 2026-11-24: connectivity cleanup of airframe-r6-blendstra-rig.glb'
js = json.dumps(G, separators=(',', ':')).encode()
js += b' ' * (-len(js) % 4)
binb = bytes(BIN) + b'\0' * (-len(BIN) % 4)
out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binb)) + struct.pack('<II', len(js), 0x4E4F534A) + js \
    + struct.pack('<II', len(binb), 0x004E4942) + binb
open(dst, 'wb').write(out)
json.dump(LOG, open(log_path, 'w'), indent=1)
print('edits', len(LOG), 'unchanged:', [e['part'] for e in LOG if e.get('extended_mm') is None and e['op'] == 'stretch'])
