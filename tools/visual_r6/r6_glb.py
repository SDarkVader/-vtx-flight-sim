"""Shared GLB reading and exact mesh-contact kernels for the R6 visual tools (no rendering).

load(path) -> GLBModel with .G (glTF JSON), .BIN, .parts (one per mesh node, with its body container) and .roots.
"""
from __future__ import annotations

import json
import struct

import numpy as np

NEAR = 0.010  # gap window used when measuring contact (m)
CT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def quat_mat(q):  # x, y, z, w
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def local(n):
    if 'matrix' in n:
        return np.array(n['matrix'], dtype=float).reshape(4, 4).T
    M = np.eye(4)
    M[:3, :3] = quat_mat(n.get('rotation', [0, 0, 0, 1])) * np.array(n.get('scale', [1, 1, 1]))
    M[:3, 3] = n.get('translation', [0, 0, 0])
    return M


def sim(p):
    w, x, y, z = p['quat_wxyz']
    M = np.eye(4)
    M[:3, :3] = quat_mat([x, y, z, w])
    M[:3, 3] = p['pos']
    return M


class GLBModel:
    def __init__(self, G, BIN):
        self.G, self.BIN = G, BIN
        self.parts, self.roots = [], {}
        for r in G['scenes'][G.get('scene', 0)]['nodes']:
            self._walk(r, np.eye(4), None)

    def accessor(self, i):
        G, BIN = self.G, self.BIN
        a = G['accessors'][i]
        bv = G['bufferViews'][a['bufferView']]
        dt = np.dtype(CT[a['componentType']])
        n, c = a['count'], NC[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 0) or dt.itemsize * c
        raw = np.frombuffer(BIN, dtype=np.uint8, count=stride * (n - 1) + dt.itemsize * c, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(n, dt.itemsize * c), strides=(stride, 1))
        out = np.ascontiguousarray(rows).view(dt)
        return out.reshape(n, c) if c > 1 else out.reshape(n)

    def _walk(self, i, parent_M, body):
        n = self.G['nodes'][i]
        M = parent_M @ local(n)
        if body is None:
            body = n.get('name', f'node{i}')
            self.roots[body] = M
        if 'mesh' in n:
            V, F = [], []
            for prim in self.G['meshes'][n['mesh']]['primitives']:
                if prim.get('mode', 4) != 4:
                    continue
                p = self.accessor(prim['attributes']['POSITION']).astype(float)
                idx = self.accessor(prim['indices']).astype(np.int64) if 'indices' in prim else np.arange(len(p))
                F.append(idx.reshape(-1, 3) + sum(len(v) for v in V))
                V.append(p)
            if V:
                self.parts.append(dict(name=n.get('name', f'node{i}'), node=i, body=body,
                                       extras_body=n.get('extras', {}).get('physical_body'),
                                       local=(np.linalg.inv(self.roots[body]) @ M), V=np.vstack(V), F=np.vstack(F)))
        for c in n.get('children', []):
            self._walk(c, M, body)

    def container_pose(self, body, pose=None):
        """World matrix the cockpit gives a body container. A container with extras.vtx_spin_centre (shafts) is
        spun about that visual centreline instead of the physics pivot, exactly as public/app.js does."""
        if not (pose and body in pose):
            return self.roots[body]
        M = sim(pose[body])
        node = next(n for n in self.G['nodes'] if n.get('name') == body)
        c = node.get('extras', {}).get('vtx_spin_centre')
        if c is not None and 'airframe' in pose:
            c = np.asarray(c, float)
            A = sim(pose['airframe'])
            rest_rel = np.linalg.inv(self.roots['airframe'])[:3, :3] @ self.roots[body][:3, :3]
            centre = M[:3, 3] + A[:3, :3] @ rest_rel @ c
            M = M.copy()
            M[:3, 3] = centre - M[:3, :3] @ c
        return M

    def world(self, part, pose=None):
        """Part vertices in simulator coordinates; pose = {body: {pos, quat_wxyz}} or None for the GLB rest."""
        M = self.container_pose(part['body'], pose)
        T = M @ part['local']
        return part['V'] @ T[:3, :3].T + T[:3, 3]


def load(path):
    blob = open(path, 'rb').read()
    jlen = struct.unpack_from('<I', blob, 12)[0]
    G = json.loads(blob[20:20 + jlen])
    off = 20 + jlen + 8
    return GLBModel(G, blob[off:off + struct.unpack_from('<I', blob, 20 + jlen)[0]])


def pt_tri_d2(Pt, A, B, C):
    """Squared distance from points (k,3) to triangles (t,3 each) -> (k,t). Ericson closest point."""
    p = Pt[:, None, :]
    a, b, c = A[None], B[None], C[None]
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    denom = va + vb + vc
    with np.errstate(divide='ignore', invalid='ignore'):
        v_ = np.where(np.abs(denom) > 1e-30, vb / denom, 0.0)
        w_ = np.where(np.abs(denom) > 1e-30, vc / denom, 0.0)
        q = a + ab * v_[..., None] + ac * w_[..., None]
        t_ab = np.clip(np.where(d1 - d3 != 0, d1 / (d1 - d3), 0), 0, 1)
        t_ac = np.clip(np.where(d2 - d6 != 0, d2 / (d2 - d6), 0), 0, 1)
        t_bc = np.clip(np.where((d4 - d3) + (d5 - d6) != 0, (d4 - d3) / ((d4 - d3) + (d5 - d6)), 0), 0, 1)
    cands = [q,
             a + ab * t_ab[..., None], a + ac * t_ac[..., None], b + (c - b) * t_bc[..., None],
             np.broadcast_to(a, q.shape), np.broadcast_to(b, q.shape), np.broadcast_to(c, q.shape)]
    inside = (va >= 0) & (vb >= 0) & (vc >= 0)
    d2s = np.stack([((p - x) ** 2).sum(-1) for x in cands])
    best_edge = d2s[1:].min(0)
    return np.where(inside, d2s[0], best_edge)


def seg_tri_hit(S0, S1, A, B, C):
    """Any segment (e,3) crossing any triangle (t,3) -> bool."""
    d = (S1 - S0)[:, None, :]
    e1, e2 = (B - A)[None], (C - A)[None]
    h = np.cross(d, e2)
    a = (e1 * h).sum(-1)
    ok = np.abs(a) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    s = S0[:, None, :] - A[None]
    u = f * (s * h).sum(-1)
    q = np.cross(s, e1)
    v = f * (d * q).sum(-1)
    t = f * (e2 * q).sum(-1)
    return bool(np.any(ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)))


def chunked_min_d2(Pt, A, B, C, budget=1_500_000):
    if len(Pt) == 0 or len(A) == 0:
        return np.inf
    step = max(1, budget // max(1, len(Pt)))
    best = np.full(len(Pt), np.inf)
    for i in range(0, len(A), step):
        best = np.minimum(best, pt_tri_d2(Pt, A[i:i + step], B[i:i + step], C[i:i + step]).min(1))
    return best


def edges(F):
    e = np.sort(np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    return np.unique(e, axis=0)


class Geo:
    def __init__(self, part, W):
        self.part, self.W = part, W
        self.tri = W[part['F']]
        self.E = edges(part['F'])
        self.lo, self.hi = W.min(0), W.max(0)


RAY_DIRS = np.array([[0.2113, 0.5774, 0.7887], [-0.6337, 0.3124, -0.7077]])


def inside(pts, h):
    """Points lying inside part h's surface (ray parity in two directions, both odd)."""
    if len(pts) == 0:
        return np.zeros(0, bool)
    A, B, C = h.tri[:, 0], h.tri[:, 1], h.tri[:, 2]
    e1, e2 = B - A, C - A
    res = np.ones(len(pts), bool)
    for dvec in RAY_DIRS:
        hvec = np.cross(dvec, e2)
        a = (e1 * hvec).sum(-1)
        ok = np.abs(a) > 1e-14
        f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
        s = pts[:, None, :] - A[None]
        u = f * (s * hvec).sum(-1)
        q = np.cross(s, e1[None])
        v = f * (q @ dvec)
        t = f * (e2[None] * q).sum(-1)
        hits = (ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum(1)
        res &= hits % 2 == 1
    return res


def embedded(g, h, lo, hi):
    """Any vertex of g (inside the overlap box) enclosed by h, or vice versa."""
    for a, b in ((g, h), (h, g)):
        vin = np.nonzero(np.all((a.W >= lo) & (a.W <= hi), 1))[0]
        if len(vin) and len(b.tri) * min(len(vin), 64) < 4_000_000:
            if inside(a.W[vin[np.linspace(0, len(vin) - 1, min(len(vin), 64)).astype(int)]], b).any():
                return True
    return False


def pair_distance(g, h, pad=NEAR):
    """Minimum gap between two parts (0 if they interpenetrate or one is embedded in the other)."""
    lo, hi = np.maximum(g.lo, h.lo) - pad, np.minimum(g.hi, h.hi) + pad
    if np.any(lo > hi):
        return np.inf
    if embedded(g, h, lo, hi):
        return 0.0
    best = np.inf
    for a, b in ((g, h), (h, g)):
        vin = np.all((a.W >= lo) & (a.W <= hi), 1)
        tl, th = b.tri.min(1), b.tri.max(1)
        tin = np.all((th >= lo) & (tl <= hi), 1)
        if vin.any() and tin.any():
            T = b.tri[tin]
            best = min(best, float(np.sqrt(chunked_min_d2(a.W[vin], T[:, 0], T[:, 1], T[:, 2]).min())))
        # edges whose span overlaps the window (a long edge can cross b with both ends far outside)
        p0, p1 = a.W[a.E[:, 0]], a.W[a.E[:, 1]]
        E = a.E[np.all((np.maximum(p0, p1) >= lo) & (np.minimum(p0, p1) <= hi), 1)]
        if len(E) and tin.any():
            T = b.tri[tin]
            for i in range(0, len(E), 2000):
                if seg_tri_hit(a.W[E[i:i + 2000, 0]], a.W[E[i:i + 2000, 1]], T[:, 0], T[:, 1], T[:, 2]):
                    return 0.0
    return best


def end_contact(g, ends, others, inward=None):
    """For each end of an elongated part, the smallest gap from its end region to any other part.
    The end region is the end vertices swept `inward` (vector per end) along the rod axis."""
    res = []
    for k, idx in enumerate(ends):
        pts = g.W[idx]
        swept = np.vstack([pts, pts + inward[k]]) if inward is not None else pts
        best = np.inf
        for h in others:
            if np.all((h.hi >= pts.min(0)) & (h.lo <= pts.max(0))) and inside(pts, h).any():
                best = 0.0
                break
            lo, hi = swept.min(0) - NEAR, swept.max(0) + NEAR
            tl, th = h.tri.min(1), h.tri.max(1)
            tin = np.all((th >= lo) & (tl <= hi), 1)
            if not tin.any():
                continue
            T = h.tri[tin]
            best = min(best, float(np.sqrt(chunked_min_d2(pts, T[:, 0], T[:, 1], T[:, 2]).min())))
            sel = np.isin(g.E, idx).any(1)
            E = g.E[sel]
            if len(E) and seg_tri_hit(g.W[E[:, 0]], g.W[E[:, 1]], T[:, 0], T[:, 1], T[:, 2]):
                best = 0.0
            if best == 0.0:
                break
        res.append(best)
    return res
