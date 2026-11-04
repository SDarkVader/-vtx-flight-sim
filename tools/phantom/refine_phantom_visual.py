"""VTX Phantom visual refinement pass (render only; never touches physics, mass ledger or CAD).

Reads a Phantom GLB exported by export_phantom_glb.py (or the animated cassette GLB) and writes a
"-visual" sibling with:

  1. Smooth body shell: crease-aware Phong tessellation of the exterior shell meshes. Every original
     CAD vertex keeps its exact position (dimensions and clearances are unchanged at the vertices);
     only the new in-between vertices are lifted onto a smooth surface built from the vertex normals,
     so faceted panels read as continuous curved, airflow-shaped surfaces. Only strong feature lines
     (dihedral > CREASE_DEG) stay sharp.
  2. Finishes: clearcoat gunmetal paint, glowing gold-amber light lines, smoked glass, brushed Ti.
  3. Exposed wing bay: the opaque deck over the A10 wing cassette and the sleeve's top plate become
     smoked inspection glazing, with a visual-only rib frame and amber LED rails, so the stowed wings,
     ball screws, slide motors, lock pins and rails are visible from above.

Node names, node order, glTF extras (phantom_joint, axis_parent, q_rest ...) and animations are
preserved, so phantom-look.js and the cassette animations keep working. Every added node carries
extras visual_only=true, mass_kg=0.

  python tools/phantom/refine_phantom_visual.py public/assets/phantom-a10.glb public/assets/phantom-a10-visual.glb
  python tools/phantom/refine_phantom_visual.py assets/derived/phantom-a10-cassette.glb assets/derived/phantom-a10-cassette-visual.glb
"""
from __future__ import annotations
import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from pygltflib import GLTF2, Accessor, BufferView, Buffer, Mesh, Primitive, Attributes, Node, Material, PbrMetallicRoughness

CREASE_DEG = 58.0      # dihedral above which an edge stays sharp (higher = smoother body)
ALPHA = 0.78           # Phong tessellation shape factor (0 = flat, 1 = full)
MAX_LIFT = 0.035       # m, safety cap on how far a new vertex may leave the flat facet
BAY = dict(x=(-1.50, -0.60), y=1.26, z_min=1.035)   # A10 cassette footprint (sleeve x -1.49..-0.62)
WINDOW = dict(xc=-1.055, yc=0.0, hx=0.29, hy=0.56, r=0.11, seg=6)   # compact inspection window over both screws

DT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

# ---------------------------------------------------------------------------------- glTF plumbing


class Glb:
    def __init__(self, path):
        self.g = GLTF2().load(path)
        self.blob = self.g.binary_blob()
        self.data = [self._read(i) for i in range(len(self.g.accessors))]
        self.image_bytes = {}
        # live exports are Z-up with an 'airframe' root; Blender's default glTF export (cassette) is Y-up
        self.yup = not any((n.extras or {}).get('physical_body') == 'airframe' for n in self.g.nodes)
        for k, im in enumerate(self.g.images or []):
            if im.bufferView is not None:
                bv = self.g.bufferViews[im.bufferView]
                self.image_bytes[k] = self.blob[(bv.byteOffset or 0):(bv.byteOffset or 0) + bv.byteLength]

    def _read(self, i):
        a = self.g.accessors[i]
        bv = self.g.bufferViews[a.bufferView]
        n = NC[a.type]
        dt = np.dtype(DT[a.componentType])
        off = (bv.byteOffset or 0) + (a.byteOffset or 0)
        stride = bv.byteStride or dt.itemsize * n
        if stride == dt.itemsize * n:
            arr = np.frombuffer(self.blob, dtype=dt, count=a.count * n, offset=off).copy()
        else:
            raw = np.frombuffer(self.blob, dtype=np.uint8, count=stride * (a.count - 1) + dt.itemsize * n, offset=off)
            arr = np.stack([np.frombuffer(raw[k * stride:k * stride + dt.itemsize * n].tobytes(), dt) for k in range(a.count)]).ravel()
        return arr.reshape(-1, n) if n > 1 else arr

    def add(self, arr, kind):
        """kind: 'pos' | 'vec3' | 'vec2' | 'idx'"""
        arr = np.ascontiguousarray(arr)
        if kind == 'idx':
            arr = arr.astype(np.uint32).ravel()
            acc = Accessor(componentType=5125, count=len(arr), type='SCALAR')
        else:
            arr = arr.astype(np.float32)
            acc = Accessor(componentType=5126, count=len(arr), type='VEC3' if arr.shape[1] == 3 else 'VEC2')
            if kind == 'pos':
                acc.min = arr.min(0).tolist(); acc.max = arr.max(0).tolist()
        self.g.accessors.append(acc)
        self.data.append(arr)
        return len(self.g.accessors) - 1

    def save(self, path):
        """Re-pack every accessor into a fresh compact buffer (drops orphaned data)."""
        used = set()
        for m in self.g.meshes:
            for p in m.primitives:
                used.update(v for v in p.attributes.__dict__.values() if isinstance(v, int))
                if p.indices is not None:
                    used.add(p.indices)
        for an in self.g.animations or []:
            for s in an.samplers:
                used.update([s.input, s.output])
        for sk in self.g.skins or []:
            if sk.inverseBindMatrices is not None:
                used.add(sk.inverseBindMatrices)
        remap, accs, views, chunks, off = {}, [], [], [], 0
        idx_accs = {p.indices for m in self.g.meshes for p in m.primitives if p.indices is not None}
        for i, a in enumerate(self.g.accessors):
            if i not in used:
                continue
            b = np.ascontiguousarray(self.data[i]).tobytes()
            pad = (-off) % 4
            chunks.append(b'\0' * pad); off += pad
            views.append(BufferView(buffer=0, byteOffset=off, byteLength=len(b),
                                    target=34963 if i in idx_accs else (34962 if a.type != 'SCALAR' or i in idx_accs else None)))
            chunks.append(b); off += len(b)
            a.bufferView = len(views) - 1; a.byteOffset = 0
            remap[i] = len(accs); accs.append(a)
        # animation inputs/outputs are not vertex attributes
        for k, b in sorted(self.image_bytes.items()):
            pad = (-off) % 4
            chunks.append(b'\0' * pad); off += pad
            views.append(BufferView(buffer=0, byteOffset=off, byteLength=len(b)))
            chunks.append(b); off += len(b)
            self.g.images[k].bufferView = len(views) - 1
        anim = {remap[x] for an in (self.g.animations or []) for s in an.samplers for x in (s.input, s.output)}
        for k in anim:
            views[accs[k].bufferView].target = None
        for m in self.g.meshes:
            for p in m.primitives:
                for k, v in p.attributes.__dict__.items():
                    if isinstance(v, int):
                        setattr(p.attributes, k, remap[v])
                if p.indices is not None:
                    p.indices = remap[p.indices]
        for an in self.g.animations or []:
            for s in an.samplers:
                s.input, s.output = remap[s.input], remap[s.output]
        for sk in self.g.skins or []:
            if sk.inverseBindMatrices is not None:
                sk.inverseBindMatrices = remap[sk.inverseBindMatrices]
        self.g.accessors, self.g.bufferViews = accs, views
        self.g.buffers = [Buffer(byteLength=off)]
        self.g.set_binary_blob(b''.join(chunks))
        self.g.save_binary(path)


def tris_of(glb, p):
    P = glb.data[p.attributes.POSITION].astype(np.float64)
    N = glb.data[p.attributes.NORMAL].astype(np.float64) if p.attributes.NORMAL is not None else None
    I = glb.data[p.indices].astype(np.int64).reshape(-1, 3) if p.indices is not None else np.arange(len(P)).reshape(-1, 3)
    return P, N, I

# ------------------------------------------------------------------------ smooth shell tessellation


def phong_tessellate(P, I, n_sub, crease_deg=CREASE_DEG, alpha=ALPHA):
    """Weld, find smoothing groups, Phong-tessellate. Returns positions, normals, indices."""
    key = np.round(P / 1e-5).astype(np.int64)
    _, weld, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    V = P[weld]
    F = inv[I]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    e1, e2 = V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]
    fn = np.cross(e1, e2)
    area2 = np.linalg.norm(fn, axis=1)
    F, fn, area2 = F[area2 > 1e-12], fn[area2 > 1e-12], area2[area2 > 1e-12]
    fn /= area2[:, None]
    nf = len(F)
    # corner angles (angle-weighted normals)
    ang = np.zeros((nf, 3))
    for k in range(3):
        a = V[F[:, (k + 1) % 3]] - V[F[:, k]]
        b = V[F[:, (k + 2) % 3]] - V[F[:, k]]
        ang[:, k] = np.arccos(np.clip((a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-15), -1, 1))
    # edge -> faces
    edges = {}
    for f in range(nf):
        for k in range(3):
            a, b = F[f, k], F[f, (k + 1) % 3]
            edges.setdefault((min(a, b), max(a, b)), []).append(f)
    cos_c = np.cos(np.radians(crease_deg))
    smooth_adj = {}
    for e, fs in edges.items():
        if len(fs) == 2 and np.dot(fn[fs[0]], fn[fs[1]]) > cos_c:
            smooth_adj.setdefault((e[0], fs[0]), []).append(fs[1])
            smooth_adj.setdefault((e[0], fs[1]), []).append(fs[0])
            smooth_adj.setdefault((e[1], fs[0]), []).append(fs[1])
            smooth_adj.setdefault((e[1], fs[1]), []).append(fs[0])
    # corner normals: flood the fan of faces around vertex connected through smooth edges
    CN = np.zeros((nf, 3, 3))
    done = {}
    for f in range(nf):
        for k in range(3):
            v = F[f, k]
            if (v, f) in done:
                CN[f, k] = done[(v, f)]
                continue
            group, stack = {f}, [f]
            while stack:
                g = stack.pop()
                for h in smooth_adj.get((v, g), []):
                    if h not in group:
                        group.add(h); stack.append(h)
            s = np.zeros(3)
            for g in group:
                kk = int(np.where(F[g] == v)[0][0])
                s += fn[g] * ang[g, kk]
            s /= np.linalg.norm(s) + 1e-15
            for g in group:
                done[(v, g)] = s
            CN[f, k] = s
    # an edge is Phong-curved only if both faces agree on both end normals; otherwise straight
    straight = np.ones((nf, 3), bool)   # straight[f, k]: edge opposite corner k
    for e, fs in edges.items():
        if len(fs) != 2:
            continue
        f0, f1 = fs
        ok = True
        for v in e:
            k0 = int(np.where(F[f0] == v)[0][0]); k1 = int(np.where(F[f1] == v)[0][0])
            if np.dot(CN[f0, k0], CN[f1, k1]) < 0.9999:
                ok = False
        if ok:
            for f in fs:
                ks = [int(np.where(F[f] == v)[0][0]) for v in e]
                straight[f, 3 - sum(ks)] = False
    # barycentric lattice
    bary = [(i, j, n_sub - i - j) for i in range(n_sub + 1) for j in range(n_sub + 1 - i)]
    lid = {b: t for t, b in enumerate(bary)}
    tri_local = []
    for i in range(n_sub):
        for j in range(n_sub - i):
            tri_local.append((lid[(i, j, n_sub - i - j)], lid[(i + 1, j, n_sub - i - j - 1)], lid[(i, j + 1, n_sub - i - j - 1)]))
            if i + j < n_sub - 1:
                tri_local.append((lid[(i + 1, j, n_sub - i - j - 1)], lid[(i + 1, j + 1, n_sub - i - j - 2)], lid[(i, j + 1, n_sub - i - j - 1)]))
    B = np.array(bary, float) / n_sub            # (m,3) weights for corners 0,1,2
    T = np.array(tri_local)
    out_p, out_n, out_i, base = [], [], [], 0
    for f in range(nf):
        C = V[F[f]]; N = CN[f]
        lin = B @ C
        proj = np.zeros_like(lin)
        for k in range(3):
            d = ((lin - C[k]) * N[k]).sum(1, keepdims=True)
            proj += B[:, k:k + 1] * (lin - d * N[k])
        disp = alpha * (proj - lin)
        fac = np.ones(len(B))
        for k in range(3):
            if straight[f, k]:
                fac *= np.clip(B[:, k] * 2.5, 0, 1)   # fade to straight along that edge
        disp *= fac[:, None]
        L = np.linalg.norm(disp, axis=1, keepdims=True)
        disp *= np.minimum(1, MAX_LIFT / (L + 1e-12))
        pts = lin + disp
        nrm = B @ N
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-15
        # keep winding consistent with the source face
        out_p.append(pts); out_n.append(nrm); out_i.append(T + base); base += len(B)
    Pn, Nn, In = np.concatenate(out_p), np.concatenate(out_n), np.concatenate(out_i)
    # weld identical (position, normal) pairs to keep the vertex count down
    k2 = np.concatenate([np.round(Pn / 1e-6), np.round(Nn / 1e-4)], 1).astype(np.int64)
    _, first, inv2 = np.unique(k2, axis=0, return_index=True, return_inverse=True)
    return Pn[first], Nn[first], inv2.ravel()[In]


def blister(P, I, W, crown=0.045):
    """lift the glazing into a slick crowned blister: zero at its rim, `crown` m at the centre (in world z)."""
    Pw = P @ W[:3, :3].T + W[:3, 3]
    lo, hi = Pw[:, :2].min(0), Pw[:, :2].max(0)
    t = (Pw[:, :2] - lo) / (hi - lo)
    b = np.sin(np.pi * np.clip(t[:, 0], 0, 1)) ** 0.7 * np.sin(np.pi * np.clip(t[:, 1], 0, 1)) ** 0.45
    Pw[:, 2] += crown * b + 0.003
    Wi = np.linalg.inv(W)
    Pl = Pw @ Wi[:3, :3].T + Wi[:3, 3]
    fn = np.cross(Pl[I[:, 1]] - Pl[I[:, 0]], Pl[I[:, 2]] - Pl[I[:, 0]])
    N = np.zeros_like(Pl)
    for k in range(3):
        np.add.at(N, I[:, k], fn)
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-15
    return Pl, N


def window_polygon():
    w = WINDOW
    pts = []
    for cx, cy, a0 in ((w['hx'] - w['r'], w['hy'] - w['r'], 0), (-(w['hx'] - w['r']), w['hy'] - w['r'], 90),
                       (-(w['hx'] - w['r']), -(w['hy'] - w['r']), 180), (w['hx'] - w['r'], -(w['hy'] - w['r']), 270)):
        for k in range(w['seg'] + 1):
            a = np.radians(a0 + 90 * k / w['seg'])
            pts.append((w['xc'] + cx + w['r'] * np.cos(a), w['yc'] + cy + w['r'] * np.sin(a)))
    return np.array(pts)          # counter-clockwise, convex


def _clip(poly, n, d, keep_inside):
    """Sutherland-Hodgman against half-plane n.xy <= d (inside) on 3D points."""
    out = []
    f = lambda q: (np.dot(n, q[:2]) - d) * (1 if keep_inside else -1)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa, fb = f(a), f(b)
        if fa <= 0:
            out.append(a)
        if (fa < 0 < fb) or (fb < 0 < fa):
            out.append(a + (b - a) * (fa / (fa - fb)))
    return out


def cut_window(P, I, W):
    """Split deck faces of the hull by the convex window polygon (world xy). Returns (P', I_outside, I_inside_up).
    Up-facing inside pieces become glazing; down-facing inside pieces (the bay lid) are dropped."""
    poly = window_polygon()
    edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    planes = []
    for a, b in edges:
        t = b - a; n = np.array([t[1], -t[0]]); n /= np.linalg.norm(n)   # outward for CCW
        planes.append((n, np.dot(n, a)))
    Pw = P @ W[:3, :3].T + W[:3, 3]
    lo, hi = poly.min(0), poly.max(0)
    newP = [Pw]; base = len(Pw); out_I, in_I = [], []
    fn = np.cross(Pw[I[:, 1]] - Pw[I[:, 0]], Pw[I[:, 2]] - Pw[I[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-15
    touched = 0

    def emit(poly3, dst):
        nonlocal base
        if len(poly3) < 3:
            return
        Q = np.array(poly3); newP.append(Q)
        for k in range(1, len(Q) - 1):
            dst.append([base, base + k, base + k + 1])
        base += len(Q)
    for f, tri in enumerate(I):
        T = Pw[tri]
        deck = abs(fn[f, 2]) > 0.5 and T[:, 2].mean() > BAY['z_min']
        if not deck or T[:, 0].max() < lo[0] or T[:, 0].min() > hi[0] or T[:, 1].max() < lo[1] or T[:, 1].min() > hi[1]:
            out_I.append(tri); continue
        touched += 1
        rest = [T[0], T[1], T[2]]
        for n, d in planes:
            emit(_clip(rest, n, d, keep_inside=False), out_I)      # piece outside this edge
            rest = _clip(rest, n, d, keep_inside=True)
            if len(rest) < 3:
                break
        if len(rest) >= 3 and fn[f, 2] > 0:
            emit(rest, in_I)
    if not touched:
        return P, I, None
    Pw = np.concatenate(newP)
    Wi = np.linalg.inv(W)
    P2 = Pw @ Wi[:3, :3].T + Wi[:3, 3]
    # keep source winding: fan triangulation preserves polygon order, which follows the source triangle
    return P2, np.array(out_I, np.int64), np.array(in_I, np.int64).reshape(-1, 3)


def smooth_normals_only(P, I, crease_deg=CREASE_DEG):
    Pn, Nn, In = phong_tessellate(P, I, 1, crease_deg, 0.0)
    return Pn, Nn, In

# ----------------------------------------------------------------------------------- materials


def ext_mat(name, base, metal, rough, emissive=None, strength=None, clearcoat=None, alpha=None):
    m = Material(name=name, pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=list(base) + [alpha if alpha is not None else 1.0],
                                                                       metallicFactor=metal, roughnessFactor=rough))
    m.doubleSided = True
    m.extensions = {}
    if emissive is not None:
        m.emissiveFactor = list(emissive)
        if strength:
            m.extensions['KHR_materials_emissive_strength'] = {'emissiveStrength': strength}
    if clearcoat is not None:
        m.extensions['KHR_materials_clearcoat'] = {'clearcoatFactor': clearcoat[0], 'clearcoatRoughnessFactor': clearcoat[1]}
    if alpha is not None:
        m.alphaMode = 'BLEND'
    return m


AMBER = (1.0, 0.52, 0.03)
FINISH = {   # existing material name prefix -> new finish (style kept: dark gunmetal + amber)
    'A6 VTX Phantom satin gunmetal armour': dict(base=(0.045, 0.050, 0.060), metal=0.72, rough=0.26, clearcoat=(1.0, 0.04)),
    'A6 sharp graphite armour facet': dict(base=(0.070, 0.078, 0.092), metal=0.65, rough=0.28, clearcoat=(1.0, 0.05)),
    'A6 dark carbon structural CFRP': dict(base=(0.022, 0.025, 0.032), metal=0.35, rough=0.30, clearcoat=(1.0, 0.03)),
    'A6 dark wheel face and thrust cover': dict(base=(0.03, 0.034, 0.04), metal=0.8, rough=0.22, clearcoat=(0.8, 0.05)),
    'A6 recessed air-channel charcoal': dict(base=(0.012, 0.014, 0.018), metal=0.3, rough=0.45),
    'A6 amber accent light': dict(base=AMBER, metal=0.0, rough=0.3, emissive=AMBER, strength=2.2),
    'Vaders amber luminescent edge': dict(base=AMBER, metal=0.0, rough=0.3, emissive=AMBER, strength=2.0),
    'A6 sharp black polygon windscreen': dict(base=(0.015, 0.025, 0.04), metal=0.1, rough=0.03, clearcoat=(1.0, 0.0), alpha=0.62),
    'Ti6Al4V local pivot metal': dict(base=(0.56, 0.58, 0.62), metal=0.92, rough=0.24),
    'A9 PH13-8Mo pin steel': dict(base=(0.80, 0.80, 0.82), metal=1.0, rough=0.16),
    'A9 electromechanical actuator housing': dict(base=(0.20, 0.22, 0.26), metal=0.75, rough=0.3, clearcoat=(0.6, 0.1)),
    'A9 CFRP structural laminate (IM7/8552 class)': dict(base=(0.05, 0.055, 0.065), metal=0.3, rough=0.32, clearcoat=(0.8, 0.06)),
    'Road/VTOL wheel tyre dark elastomer': dict(base=(0.018, 0.02, 0.022), metal=0.0, rough=0.82),
    'Directional nozzle ceramic heat shield': dict(base=(0.04, 0.10, 0.20), metal=0.3, rough=0.45, emissive=(0.15, 0.40, 1.0), strength=0.8),
    'A7 restraint belt webbing amber': dict(base=(0.9, 0.5, 0.06), metal=0.0, rough=0.6),
}
GLASS_BAY = ('VTX visual · smoked inspection glazing', dict(base=(0.05, 0.075, 0.10), metal=0.0, rough=0.02, clearcoat=(1.0, 0.0), alpha=0.12))
RIB = ('VTX visual · machined Ti inspection rib', dict(base=(0.30, 0.32, 0.36), metal=0.95, rough=0.22, clearcoat=(0.6, 0.05)))
THRUST = ('VTX visual · ring thruster face', dict(base=(0.025, 0.03, 0.04), metal=0.85, rough=0.22, clearcoat=(0.8, 0.05)))
HUB = ('VTX visual · ring thruster core glow', dict(base=(0.05, 0.006, 0.003), metal=0.0, rough=0.3, emissive=(1.0, 0.12, 0.03), strength=0.9))
ALLOY = ('VTX visual · polished forged alloy', dict(base=(0.78, 0.80, 0.83), metal=1.0, rough=0.16, clearcoat=(0.6, 0.03)))
# VTX monogram alloy spokes in the unit wheel disc (u right, v up): T crossbar, V arms, centre stem, X diagonals
_c45 = 0.97 * math.sqrt(0.5)
VTX_SPOKES = [((-0.80, 0.60), (0.80, 0.60)),                         # T crossbar
              ((0.0, 0.60), (0.0, -0.97)),                           # T stem
              ((-0.80, 0.60), (0.0, -0.97)), ((0.80, 0.60), (0.0, -0.97)),   # V
              ((-_c45, -_c45), (_c45, _c45)), ((-_c45, _c45), (_c45, -_c45))]   # X
LED = ('VTX visual · amber bay LED rail', dict(base=AMBER, metal=0.0, rough=0.3, emissive=AMBER, strength=2.6))


def apply_finishes(glb):
    for m in glb.g.materials:
        spec = FINISH.get(m.name)
        if not spec:
            continue
        new = ext_mat(m.name, **spec)
        m.pbrMetallicRoughness = new.pbrMetallicRoughness
        m.extensions = new.extensions
        m.emissiveFactor = new.emissiveFactor if spec.get('emissive') else m.emissiveFactor
        if spec.get('alpha') is not None:
            m.alphaMode = 'BLEND'


def add_material(glb, name, spec):
    glb.g.materials.append(ext_mat(name, **spec))
    return len(glb.g.materials) - 1

# ---------------------------------------------------------------------------- shell selection


SHELL_MATS = {'A6 VTX Phantom satin gunmetal armour', 'A6 sharp graphite armour facet', 'A6 dark carbon structural CFRP',
              'A6 sharp black polygon windscreen', 'A6 dark wheel face and thrust cover'}
SKIP_NODE = ('AMBER', 'HIGHLIGHT', 'GASKET', 'MARKER', 'PROBE', 'SPLITTER')


def node_world(glb):
    """world matrices of nodes (column-major glTF -> numpy 4x4)."""
    g = glb.g
    parent = {c: i for i, n in enumerate(g.nodes) for c in (n.children or [])}
    cache = {}

    def local(n):
        if n.matrix:
            return np.array(n.matrix, float).reshape(4, 4).T
        t = np.array(n.translation or [0, 0, 0], float)
        x, y, z, w = n.rotation or [0, 0, 0, 1]
        s = np.array(n.scale or [1, 1, 1], float)
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t
        return M

    C = np.eye(4)
    if glb.yup:   # express everything in the Z-up engineering frame: z_up = y_gltf, y_up = -z_gltf
        C[:3, :3] = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]

    def world(i):
        if i not in cache:
            cache[i] = (world(parent[i]) if i in parent else C) @ local(g.nodes[i])
        return cache[i]
    return world, parent


def visual_root(glb):
    """'airframe' root for live exports; for Y-up files a new scene root rotating Z-up content into Y-up."""
    g = glb.g
    for i, n in enumerate(g.nodes):
        if (n.extras or {}).get('physical_body') == 'airframe' or n.name == 'VTX_VISUAL_ZUP_ROOT':
            return i
    h = math.sqrt(0.5)
    g.nodes.append(Node(name='VTX_VISUAL_ZUP_ROOT', rotation=[-h, 0, 0, h], children=[],
                        extras=dict(visual_only=True, note='Z-up frame for the visual-only additions')))
    g.scenes[g.scene or 0].nodes.append(len(g.nodes) - 1)
    return len(g.nodes) - 1

# ----------------------------------------------------------------------------------- the pass


def refine(src, dst):
    glb = Glb(src)
    g = glb.g
    world, parent = node_world(glb)
    mat_name = lambda p: g.materials[p.material].name if p.material is not None else ''
    glass_bay = add_material(glb, *GLASS_BAY)
    rib_mat = add_material(glb, *RIB)
    led_mat = add_material(glb, *LED)
    shell_meshes = {}
    for i, n in enumerate(g.nodes):
        if n.mesh is None or any(s in (n.name or '').upper() for s in SKIP_NODE):
            continue
        shell_meshes.setdefault(n.mesh, i)
    stats = dict(shell_prims=0, v_before=0, v_after=0, bay_faces=0)
    airframe_idx = visual_root(glb)
    for mi, ni in shell_meshes.items():
        node = g.nodes[ni]
        W = world(ni)
        new_prims = []
        for p in g.meshes[mi].primitives:
            mn = mat_name(p)
            if mn not in SHELL_MATS:
                new_prims.append(p); continue
            P, N, I = tris_of(glb, p)
            stats['v_before'] += len(P)
            ext = np.ptp(P, axis=0).max()
            n_sub = 4 if ext > 1.5 else 3 if ext > 0.5 else 2
            is_hull = 'HULL' in (node.name or '').upper()
            # cut a compact rounded window into the hull deck over the cassette -> inspection glazing
            win = None
            if is_hull:
                P, I, win = cut_window(P, I, W)
                if win is not None:
                    stats['bay_faces'] += len(win)
            Pn, Nn, In = phong_tessellate(P, I, n_sub)
            stats['v_after'] += len(Pn); stats['shell_prims'] += 1
            new_prims.append(Primitive(attributes=Attributes(POSITION=glb.add(Pn, 'pos'), NORMAL=glb.add(Nn, 'vec3')),
                                       indices=glb.add(In, 'idx'), material=p.material, mode=4))
            if win is not None and len(win):
                Pg, Ng, Ig = phong_tessellate(P, win, 6, crease_deg=89.0, alpha=0.0)
                Pg, Ng = blister(Pg, Ig, W, crown=0.014)
                new_prims.append(Primitive(attributes=Attributes(POSITION=glb.add(Pg, 'pos'), NORMAL=glb.add(Ng, 'vec3')),
                                           indices=glb.add(Ig, 'idx'), material=glass_bay, mode=4))
        g.meshes[mi].primitives = new_prims
    # sleeve top plate (panel-level ceiling of the carry-through box) -> glazing as a visual cutaway
    for n in g.nodes:
        if n.mesh is not None and (n.name or '').startswith('A10_SLEEVE_CARRY_THROUGH_BOX'):
            for p in g.meshes[n.mesh].primitives:
                P = glb.data[p.attributes.POSITION]
                if len(P) <= 24 and np.ptp(P[:, 2]) < 0.03 and P[:, 2].min() > 1.0:
                    p.material = glass_bay
    thrust_mat = add_material(glb, *THRUST)
    hub_mat = add_material(glb, *HUB)
    from phantom_livery import add_texture, ember_gradient
    from pygltflib import TextureInfo
    tex = add_texture(glb, ember_gradient())
    g.materials[hub_mat].emissiveTexture = TextureInfo(index=tex)
    g.materials[hub_mat].emissiveFactor = [1.0, 1.0, 1.0]
    alloy_mat = add_material(glb, *ALLOY)
    world, _ = node_world(glb)
    for ni, n in enumerate(list(g.nodes)):
        if n.mesh is None or 'THRUST_INLET_OUTLET' not in (n.name or ''):
            continue
        for p in g.meshes[n.mesh].primitives:
            p.material = thrust_mat
        p0 = g.meshes[n.mesh].primitives[0]
        P, N, I = tris_of(glb, p0)
        c = P.mean(0); U, S_, Vt = np.linalg.svd(P - c, full_matrices=False)
        ax = Vt[2]                                        # disc normal (thinnest direction), node-local
        d = P - c; along = (d @ ax)[:, None] * ax
        R_disc = np.linalg.norm(d - along, axis=1).max()
        # outward = away from the wheel body (structural disk centre)
        Wn = world(ni)
        wheel = n.name.split('_THRUST')[0]
        body = next((j for j, m in enumerate(g.nodes) if m.name == wheel + '_STRUCTURAL_DISK'), None)
        out = ax
        if body is not None:
            cb = glb.data[g.meshes[g.nodes[body].mesh].primitives[0].attributes.POSITION].mean(0)
            cb_l = np.linalg.inv(Wn) @ (world(body) @ np.r_[cb, 1.0])
            if np.dot(c - cb_l[:3], ax) < 0:
                out = -ax
        up = np.linalg.inv(Wn[:3, :3]) @ np.array([0, 0, 1.0]); up -= np.dot(up, ax) * ax
        up = up / np.linalg.norm(up) if np.linalg.norm(up) > 1e-6 else Vt[0]
        right = np.cross(up, out)
        # blue thrust glow across the face, seen between the spokes
        Pc = c + (d - along) * 0.92 + along * 1.1
        kids = []
        uv = np.stack([(Pc - c) @ right, (Pc - c) @ up], 1) / (2 * R_disc * 0.92) + 0.5
        g.meshes.append(Mesh(name=n.name + '_CORE_GLOW', primitives=[Primitive(
            attributes=Attributes(POSITION=glb.add(Pc, 'pos'), NORMAL=glb.add(N, 'vec3'), TEXCOORD_0=glb.add(uv, 'vec2')),
            indices=glb.add(I, 'idx'), material=hub_mat, mode=4)]))
        g.nodes.append(Node(name='VTX_VISUAL_' + n.name + '_CORE_GLOW', mesh=len(g.meshes) - 1, extras=dict(visual_only=True, mass_kg=0.0)))
        kids.append(len(g.nodes) - 1)
        # VTX monogram alloy spokes reaching the rim lip, plus a centre cap
        Rs = 0.232 if R_disc < 0.22 else R_disc
        o = c + out * 0.010
        parts = []
        for (u0, v0), (u1, v1) in VTX_SPOKES:
            a = o + Rs * (u0 * right + v0 * up); b = o + Rs * (u1 * right + v1 * up)
            parts.append(rail_n(a, b, 0.024, 0.020, out))
        cap = Pc - c; cap_al = (cap @ ax)[:, None] * ax
        parts.append((c + out * 0.012 + (cap - cap_al) * (0.055 / R_disc / 0.92) + cap_al * 2.2, N, I))
        Ps, Ns, Is, base = [], [], [], 0
        for Pp, Np, Ip in parts:
            Ps.append(Pp); Ns.append(Np); Is.append(Ip + base); base += len(Pp)
        g.meshes.append(Mesh(name=n.name + '_VTX_ALLOY_SPOKES', primitives=[Primitive(
            attributes=Attributes(POSITION=glb.add(np.concatenate(Ps), 'pos'), NORMAL=glb.add(np.concatenate(Ns), 'vec3')),
            indices=glb.add(np.concatenate(Is), 'idx'), material=alloy_mat, mode=4)]))
        g.nodes.append(Node(name='VTX_VISUAL_' + wheel + '_VTX_ALLOY_SPOKES', mesh=len(g.meshes) - 1,
                            extras=dict(visual_only=True, mass_kg=0.0, note='VTX monogram alloy spoke face (render-only)')))
        kids.append(len(g.nodes) - 1)
        n.children = list(n.children or []) + kids
    # the wheel lip ring goes from amber to polished alloy
    for n in g.nodes:
        if n.mesh is not None and n.name.startswith('WHEEL_') and n.name.endswith('_AMBER_RING'):
            for p in g.meshes[n.mesh].primitives:
                p.material = alloy_mat
    paint = next(i for i, m in enumerate(g.materials) if m.name == 'A6 VTX Phantom satin gunmetal armour')
    add_wing_cowls(glb, airframe_idx, world, paint, led_mat)
    from phantom_livery import carbon_twill
    carbon = add_material(glb, 'VTX visual · 2x2 twill carbon fibre', dict(base=(1.0, 1.0, 1.0), metal=0.10, rough=0.42, clearcoat=(1.0, 0.04)))
    g.materials[carbon].pbrMetallicRoughness.baseColorTexture = TextureInfo(index=add_texture(glb, carbon_twill()))
    ti = add_material(glb, 'VTX visual · machined Ti-6Al-4V', dict(base=(0.60, 0.62, 0.66), metal=0.95, rough=0.22, clearcoat=(0.3, 0.1)))
    red = add_material(glb, 'VTX visual · red LED brake strip', dict(base=(1.0, 0.05, 0.03), metal=0.0, rough=0.2, emissive=(1.0, 0.02, 0.01), strength=1.1))
    add_drs(glb, airframe_idx, world, dict(carbon=carbon, ti=ti, red=red, amber=led_mat))
    ceramic = add_material(glb, 'VTX visual · ceramic matrix nozzle face', dict(base=(0.09, 0.09, 0.10), metal=0.0, rough=0.62))
    add_booster_cowls(glb, airframe_idx, world, dict(ti=ti, ceramic=ceramic))
    if airframe_idx is not None:
        add_bay_frame(glb, airframe_idx, rib_mat, led_mat, world)
    apply_finishes(glb)
    used = set(g.extensionsUsed or [])
    used.update(['KHR_materials_emissive_strength', 'KHR_materials_clearcoat'] + (['KHR_lights_punctual'] if 'KHR_lights_punctual' in (g.extensions or {}) else []))
    g.extensionsUsed = sorted(used)
    g.asset.extras = dict(g.asset.extras or {}, vtx_visual_pass=dict(
        tool='tools/phantom/refine_phantom_visual.py', source=src, crease_deg=CREASE_DEG, phong_alpha=ALPHA,
        note='render-only refinement; original CAD vertices unchanged; physics/mass ledger untouched'))
    glb.save(dst)
    return stats


def box(c, size):
    """axis-aligned box: 24 verts (flat normals) + indices."""
    c = np.asarray(c, float); h = np.asarray(size, float) / 2
    P, N, I = [], [], []
    for ax in range(3):
        for s in (-1, 1):
            u, v = [(ax + 1) % 3, (ax + 2) % 3]
            q = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.zeros(3); p[ax] = s * h[ax]; p[u] = a * h[u]; p[v] = b * h[v]; q.append(c + p)
            nn = np.zeros(3); nn[ax] = s
            k = len(P)
            P += q; N += [nn] * 4
            I += [[k, k + 1, k + 2], [k, k + 2, k + 3]] if s > 0 else [[k, k + 2, k + 1], [k, k + 3, k + 2]]
    return np.array(P), np.array(N), np.array(I)


def rail(a, b, w, h):
    """bar from a to b (any direction) with square-ish section w x h, built as a transformed box."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d); x = d / L
    z = np.array([0, 0, 1.0]); y = np.cross(z, x); y /= np.linalg.norm(y); z = np.cross(x, y)
    P, N, I = box([0, 0, 0], [L, w, h])
    R = np.stack([x, y, z], 1)
    return P @ R.T + (a + b) / 2, N @ R.T, I


def rail_n(a, b, w, h, up):
    """bar from a to b, width w across, depth h along `up` (centred on the a-b line)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d); x = d / L
    z = np.asarray(up, float) - np.dot(up, x) * x; z /= np.linalg.norm(z); y = np.cross(z, x)
    P, N, I = box([0, 0, 0], [L + w, w, h])
    R = np.stack([x, y, z], 1)
    return P @ R.T + (a + b) / 2, N @ R.T, I


# Wing-cassette shoulder: one continuous body-side profile (y, z) from the roof, over a shoulder roll, down the
# reveal panel that carries the wing slot, and tucked under into the fender. Not a pod: it starts tangent to the roof.
COWL_PROFILE = [(0.74, 1.074), (0.86, 1.104), (1.00, 1.128), (1.12, 1.132), (1.215, 1.120), (1.268, 1.098),
                (1.292, 1.068), (1.300, 1.030), (1.303, 0.990), (1.300, 0.945), (1.290, 0.905), (1.262, 0.862),
                (1.205, 0.826), (1.130, 0.808)]
COWL = dict(slot=dict(x=(-1.515, -0.595), z=(0.932, 1.072)), y_mouth=1.244,
            front=dict(end=(-0.18, -0.52), ramp=0.25), rear=dict(end=(-2.05, -1.90), ramp=0.38), tip=(1.02, (1.035, 0.90)),
            channel=dict(z=(0.935, 1.070), depth=0.009))


def _catmull(pts, per=10):
    P = np.array(pts, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1:i + 3]
        for t in np.linspace(0, 1, per, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


_PROF = None


def _profile():
    global _PROF
    if _PROF is None:
        pr = _catmull(COWL_PROFILE, 6)
        c = COWL['channel']; zc = 0.5 * (c['z'][0] + c['z'][1]); hz = 0.5 * (c['z'][1] - c['z'][0])
        outboard = pr[:, 0] > 1.27
        band = np.clip(1 - ((pr[:, 1] - zc) / hz) ** 4, 0, 1) * outboard     # flat-bottomed air channel at slot height
        pr[:, 0] -= c['depth'] * band
        _PROF = pr
    return _PROF


def _smoother(t):
    t = np.clip(t, 0, 1)
    return t * t * t * (t * (6 * t - 15) + 10)


def _cowl_point_u(x, k):
    """profile point k at station x, melted back into the body over raked fore/aft ramps."""
    pr = _profile(); u = k / (len(pr) - 1)
    y, z = pr[k]
    F, R = COWL['front'], COWL['rear']
    xe_f = F['end'][0] + (F['end'][1] - F['end'][0]) * float(_smoother((u - 0.45) / 0.55))   # swept leading edge: lower panel ends earlier
    xe_r = R['end'][0] + (R['end'][1] - R['end'][0]) * u
    t = max(_smoother((x - (xe_f - F['ramp'])) / F['ramp']), _smoother(((xe_r + R['ramp']) - x) / R['ramp']))
    ty, (tz0, tz1) = COWL['tip']
    tz = tz0 + (tz1 - tz0) * u            # melt onto a short vertical edge inside the haunch, not a point (no beak)
    w = float(min(1.0, max(0.0, 1 - t)))
    # shrink toward an inboard tip inside the haunch, keeping the shoulder fuller than the lower panel (sculpted, not conical)
    y2 = ty + (y - ty) * w ** (0.8 + 0.6 * u)
    z2 = tz + (z - tz) * w ** (0.6 + 0.3 * (1 - u))
    return y2, z2


def _cowl_y_at(z):
    """outer surface y of the full section at height z (reveal panel)."""
    pr = _profile()
    rev = pr[(pr[:, 0] > 1.2)]
    order = np.argsort(rev[:, 1])
    return float(np.interp(z, rev[order, 1], rev[order, 0]))


def add_wing_cowls(glb, root_idx, world, paint_mat, led_mat):
    """Smooth aerodynamic cowls over the blocky wing-cassette ends that stand proud of the body.
    The wing slot stays open (with a short tunnel back to the real mouth flange) so the wing still deploys through it."""
    g = glb.g
    C = COWL
    xs = np.concatenate([np.linspace(-2.00, -1.50, 22, endpoint=False), np.linspace(-1.50, -0.60, 40, endpoint=False), np.linspace(-0.60, -0.20, 20)])
    nprof = len(_profile())
    G = np.array([[[x, *_cowl_point_u(x, k)] for k in range(nprof)] for x in xs])     # (nx, nu, 3), +y side
    sx0, sx1 = C['slot']['x']; sz0, sz1 = C['slot']['z']
    parts_paint, parts_led = [], []
    for side in (1, -1):
        P = G.copy(); P[..., 1] *= side
        nx, nt = P.shape[:2]
        idx = np.arange(nx * nt).reshape(nx, nt)
        I = []
        for i in range(nx - 1):
            for j in range(nt - 1):
                q = P[i:i + 2, j:j + 2].reshape(-1, 3)
                cx, cz = q[:, 0].mean(), q[:, 2].mean()
                if sx0 < cx < sx1 and sz0 < cz < sz1 and abs(q[:, 1]).mean() > 1.2:
                    continue                                   # wing slot opening
                a, b, c, d = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
                I += [[a, b, c], [a, c, d]] if side > 0 else [[a, c, b], [a, d, c]]
        I = np.array(I)
        V = P.reshape(-1, 3)
        fn = np.cross(V[I[:, 1]] - V[I[:, 0]], V[I[:, 2]] - V[I[:, 0]])
        N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, I[:, k], fn)
        N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-15
        # outward check: at theta=0 the normal must point to +side*y
        mid = idx[nx // 2, nt // 2]
        if N[mid, 1] * side < 0:
            I = I[:, [0, 2, 1]]; N = -N
        parts_paint.append((V, N, I))
        # tunnel from the slot opening back to the mouth flange
        ym = C['y_mouth']
        for z in (sz0, sz1):
            yo = _cowl_y_at(z)
            Q = np.array([[sx0, ym, z], [sx1, ym, z], [sx1, yo, z], [sx0, yo, z]]); Q[:, 1] *= side
            nrm = np.array([0, 0, 1.0 if z == sz0 else -1.0])
            parts_paint.append((Q, np.repeat(nrm[None], 4, 0), np.array([[0, 1, 2], [0, 2, 3], [0, 2, 1], [0, 3, 2]])))
        for x in (sx0, sx1):
            zz = np.linspace(sz0, sz1, 8)
            Q = [[x, ym * side, z] for z in zz] + [[x, _cowl_y_at(z) * side, z] for z in zz]
            Q = np.array(Q); T = []
            for k in range(7):
                T += [[k, k + 1, 8 + k + 1], [k, 8 + k + 1, 8 + k], [k, 8 + k + 1, k + 1], [k, 8 + k, 8 + k + 1]]
            nrm = np.array([1.0 if x == sx0 else -1.0, 0, 0])
            parts_paint.append((Q, np.repeat(nrm[None], len(Q), 0), np.array(T)))
        # amber LED lip along the slot's upper and lower edges + a shoulder line replacing the covered haunch crease
        for z in (sz0 - 0.006, sz1 + 0.006):
            yo = _cowl_y_at(z) + 0.002
            parts_led.append(rail_n([sx0 - 0.01, yo * side, z], [sx1 + 0.01, yo * side, z], 0.006, 0.005, [0, side, 0]))
        # amber character line on the shoulder roll (profile point between crown and reveal), following the melt-in
        ks = int(np.argmin(np.abs(_profile()[:, 0] - 1.24)))
        pts = [np.array([x, _cowl_point_u(x, ks)[0] * side, _cowl_point_u(x, ks)[1]]) for x in np.linspace(-1.80, -0.36, 30)]
        for p0, p1 in zip(pts[:-1], pts[1:]):
            pa, pb = _profile()[ks - 1], _profile()[ks + 1]
            tn = np.array([0, (pb[0] - pa[0]) * side, pb[1] - pa[1]]); nrm = np.array([0, tn[2] * side, -tn[1] * side]) if False else np.array([0, -(pb[1] - pa[1]) * side, (pb[0] - pa[0])])
            nrm /= np.linalg.norm(nrm)
            if nrm[2] < 0:
                nrm = -nrm
            parts_led.append(rail_n(p0 + nrm * 0.003, p1 + nrm * 0.003, 0.006, 0.004, nrm))
    Wi = np.linalg.inv(world(root_idx))
    for name, parts, mat in (('VTX_VISUAL_WING_CASSETTE_COWLS', parts_paint, paint_mat), ('VTX_VISUAL_WING_COWL_AMBER_LINES', parts_led, led_mat)):
        Ps, Ns, Is, base = [], [], [], 0
        for Pp, Np, Ip in parts:
            Ps.append(Pp); Ns.append(Np); Is.append(Ip + base); base += len(Pp)
        Pw, Nw = np.concatenate(Ps), np.concatenate(Ns)
        Pl = Pw @ Wi[:3, :3].T + Wi[:3, 3]; Nl = Nw @ np.linalg.inv(Wi[:3, :3]); Nl /= np.linalg.norm(Nl, axis=1, keepdims=True) + 1e-15
        g.meshes.append(Mesh(name=name, primitives=[Primitive(attributes=Attributes(POSITION=glb.add(Pl, 'pos'), NORMAL=glb.add(Nl, 'vec3')),
                                                              indices=glb.add(np.concatenate(Is), 'idx'), material=mat, mode=4)]))
        g.nodes.append(Node(name=name, mesh=len(g.meshes) - 1, extras=dict(
            visual_only=True, mass_kg=0.0, note='aerodynamic fairing over the wing-cassette ends (render-only; slot kept open)')))
        g.nodes[root_idx].children = list(g.nodes[root_idx].children or []) + [len(g.nodes) - 1]


def cyl(a, b, r, seg=20, caps=True):
    """closed cylinder from a to b (smooth sides, flat caps)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ax = b - a; L = np.linalg.norm(ax); ax /= L
    u = np.cross(ax, [0, 0, 1.0] if abs(ax[2]) < 0.9 else [1.0, 0, 0]); u /= np.linalg.norm(u); v = np.cross(ax, u)
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    P = np.concatenate([a + r * ring, b + r * ring]); N = np.concatenate([ring, ring]); I = []
    for k in range(seg):
        k2 = (k + 1) % seg
        I += [[k, k2, seg + k2], [k, seg + k2, seg + k]]
    I = np.array(I)
    if caps:
        Pc = np.concatenate([a + r * ring, b + r * ring, [a, b]]); base = len(P)
        P = np.concatenate([P, Pc]); N = np.concatenate([N, np.repeat(-ax[None], seg, 0), np.repeat(ax[None], seg, 0), [-ax, ax]])
        ca, cb = base + 2 * seg, base + 2 * seg + 1
        I = np.concatenate([I, [[ca, base + (k + 1) % seg, base + k] for k in range(seg)], [[cb, base + seg + k, base + seg + (k + 1) % seg] for k in range(seg)]])
    return P, N, I


def _orient(P, N, I):
    """make winding agree with the supplied normals."""
    fn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    flip = (fn * N[I[:, 0]]).sum(1) < 0
    I = I.copy(); I[flip] = I[flip][:, [0, 2, 1]]
    return I


def loft_section(sec_xz, y0, y1, uv_scale=0.12):
    """extrude a closed x-z section along y with end caps; returns P, N, UV, I (normals outward)."""
    n = len(sec_xz)
    ctr = sec_xz.mean(0)
    P, N, UV, I = [], [], [], []
    # perimeter arc length for UVs
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(sec_xz, axis=0), axis=1))])
    for y in (y0, y1):
        for k in range(n):
            P.append([sec_xz[k, 0], y, sec_xz[k, 1]]); UV.append([y / uv_scale, arc[k] / uv_scale])
    # side normals from the section outline
    for y in (y0, y1):
        for k in range(n):
            a, b = sec_xz[max(k - 1, 0)], sec_xz[min(k + 1, n - 1)]
            t = b - a; nn = np.array([t[1], 0.0, -t[0]]); nn /= np.linalg.norm(nn) + 1e-12
            if np.dot(nn[[0, 2]], sec_xz[k] - ctr) < 0:
                nn = -nn
            N.append(nn)
    for k in range(n - 1):
        I += [[k, k + 1, n + k + 1], [k, n + k + 1, n + k]]
    base = len(P)
    for y, sgn in ((y0, -1.0), (y1, 1.0)):
        b0 = len(P)
        for k in range(n):
            P.append([sec_xz[k, 0], y, sec_xz[k, 1]]); N.append([0, sgn, 0]); UV.append([sec_xz[k, 0] / uv_scale, sec_xz[k, 1] / uv_scale])
        P.append([ctr[0], y, ctr[1]]); N.append([0, sgn, 0]); UV.append([ctr[0] / uv_scale, ctr[1] / uv_scale])
        c = len(P) - 1
        for k in range(n - 1):
            I.append([c, b0 + k, b0 + k + 1])
    P, N, UV, I = np.array(P, float), np.array(N, float), np.array(UV, float), np.array(I)
    return P, N, UV, _orient(P, N, I)


def add_drs(glb, root_idx, world, mats):
    """Split carbon DRS/airbrake flap between the fins on one hinge axis, joined and driven by a central
    titanium rotary EMA on a carbon pylon. Geometry and aero from engineering/phantom/drs_flap.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('drs_flap', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'engineering', 'phantom', 'drs_flap.py'))
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
    g = glb.g
    px, pz = D.PIVOT
    pivot = np.array([px, 0.0, pz])
    sec = D.section_world(D.REST_DEG, 40) - np.array([px, pz])          # hinge-local x-z
    moving = dict(carbon=[], ti=[], red=[])
    fixed = dict(carbon=[], ti=[], amber=[])
    for s_ in (1, -1):
        y0, y1 = sorted((s_ * D.Y_ROOT, s_ * D.Y_TIP))
        moving['carbon'].append(loft_section(sec, y0, y1))
        # titanium root and tip ribs (section outline grown 3 mm)
        ctr = sec.mean(0); grown = ctr + (sec - ctr) * 1.0 + (sec - ctr) / (np.linalg.norm(sec - ctr, axis=1, keepdims=True) + 1e-9) * 0.003
        for yr, th in ((s_ * D.Y_ROOT, 0.004), (s_ * (D.Y_TIP - 0.002), 0.003)):
            a, b = sorted((yr - th / 2, yr + th / 2))
            P, N, UV, I = loft_section(grown, a, b)
            moving['ti'].append((P, N, None, I))
        # splined output hub and tip shaft on the hinge axis
        P, N, I = cyl([0, s_ * 0.036, 0], [0, s_ * (D.Y_ROOT + 0.012), 0], 0.016)
        moving['ti'].append((P, N, None, I))
        P, N, I = cyl([0, s_ * (D.Y_TIP - 0.012), 0], [0, s_ * 0.560, 0], 0.010)
        moving['ti'].append((P, N, None, I))
    # Gurney lip and red LED brake strip along the trailing edge (TE = aft-most point of the section)
    te = sec[np.argmin(sec[:, 0])]
    a = np.radians(D.REST_DEG)
    up = np.array([np.sin(a), 0, np.cos(a)])            # section normal, pressure (upper) side of the inverted blade
    aft = np.array([-np.cos(a), 0, np.sin(a)])
    for s_ in (1, -1):
        y0, y1 = sorted((s_ * D.Y_ROOT, s_ * (D.Y_TIP - 0.004)))
        tep = np.array([te[0], 0, te[1]])
        gur = rail_n(tep + up * D.GURNEY_H / 2 + [0, y0, 0], tep + up * D.GURNEY_H / 2 + [0, y1, 0], 0.0025, D.GURNEY_H, aft)
        moving['carbon'].append((gur[0], gur[1], None, gur[2]))
        led = rail_n(tep + aft * 0.0015 + up * 0.002 + [0, y0 + s_ * 0.004 if s_ > 0 else y0, 0], tep + aft * 0.0015 + up * 0.002 + [0, y1, 0], 0.0035, 0.004, aft)
        moving['red'].append((led[0], led[1], None, led[2]))
    # ---- fixed titanium mechanism (world positions)
    fx = lambda v: (np.asarray(v, float))
    # central coaxial rotary EMA drum with flanges and cooling rings
    P, N, I = cyl(pivot + [0, -0.034, 0], pivot + [0, 0.034, 0], 0.033, 28); fixed['ti'].append((P, N, None, I))
    for yy in (-0.030, -0.012, 0.012, 0.030):
        P, N, I = cyl(pivot + [0, yy - 0.0015, 0], pivot + [0, yy + 0.0015, 0], 0.037, 28); fixed['ti'].append((P, N, None, I))
    P, N, I = cyl(pivot + [0, -0.0035, 0], pivot + [0, 0.0035, 0], 0.0345, 28); fixed['amber'].append((P, N, None, I))   # status ring
    # BLDC motor can + gear cover below/forward of the drum
    mpos = pivot + [0.030, 0, -0.058]
    P, N, I = cyl(mpos + [0, -0.032, 0], mpos + [0, 0.032, 0], 0.021, 24); fixed['ti'].append((P, N, None, I))
    gc = rail_n(pivot + [0.016, -0.026, -0.030], pivot + [0.016, 0.026, -0.030], 0.040, 0.050, [1.0, 0, 0])
    fixed['ti'].append((gc[0], gc[1], None, gc[2]))
    # carbon aerofoil pylon from the deck to the actuator, Ti foot plate and top clevis
    deck_z = 0.900
    pyl = []
    from math import pi
    ss = 0.5 * (1 - np.cos(np.linspace(0, pi, 18)))
    yt = 5 * 0.14 * (0.2969 * np.sqrt(ss) - 0.1260 * ss - 0.3516 * ss ** 2 + 0.2843 * ss ** 3 - 0.1036 * ss ** 4)
    cpy = 0.095
    sec_xy = np.concatenate([np.stack([px + 0.035 - ss * cpy, yt * cpy], 1), np.stack([px + 0.035 - ss[::-1][1:] * cpy, -yt[::-1][1:] * cpy], 1)])
    z0, z1 = deck_z - 0.02, pz - 0.050
    nn = len(sec_xy); Pp, Np_, Ip = [], [], []
    for zz in (z0, z1):
        for k in range(nn):
            Pp.append([sec_xy[k, 0], sec_xy[k, 1], zz])
    ctr2 = sec_xy.mean(0)
    for zz in (z0, z1):
        for k in range(nn):
            a2, b2 = sec_xy[max(k - 1, 0)], sec_xy[min(k + 1, nn - 1)]; t2 = b2 - a2
            nv = np.array([t2[1], -t2[0], 0.0]); nv /= np.linalg.norm(nv) + 1e-12
            if np.dot(nv[:2], sec_xy[k] - ctr2) < 0:
                nv = -nv
            Np_.append(nv)
    for k in range(nn - 1):
        Ip += [[k, k + 1, nn + k + 1], [k, nn + k + 1, nn + k]]
    Pp, Np_ = np.array(Pp), np.array(Np_); Ip = _orient(Pp, Np_, np.array(Ip))
    UVp = np.stack([Pp[:, 0] / 0.08, Pp[:, 2] / 0.08], 1)
    fixed['carbon'].append((Pp, Np_, UVp, Ip))
    foot = rail_n([px + 0.05, 0, deck_z - 0.012], [px - 0.075, 0, deck_z - 0.012], 0.050, 0.012, [0, 0, 1.0]); fixed['ti'].append((foot[0], foot[1], None, foot[2]))
    for yy in (-0.018, 0.018):
        cl = rail_n([px + 0.02, yy, pz - 0.056], [px + 0.02, yy, pz - 0.030], 0.020, 0.006, [0, 1.0, 0]); fixed['ti'].append((cl[0], cl[1], None, cl[2]))
    # flanged titanium bearing housings on each fin's inner face, with four bolt heads
    for s_ in (1, -1):
        y_in = 0.487 + (pz - 1.05) * 0.373
        P, N, I = cyl(pivot + [0, s_ * (y_in - 0.020), 0], pivot + [0, s_ * (y_in + 0.004), 0], 0.019, 24); fixed['ti'].append((P, N, None, I))
        P, N, I = cyl(pivot + [0, s_ * (y_in - 0.004), 0], pivot + [0, s_ * (y_in + 0.002), 0], 0.031, 28); fixed['ti'].append((P, N, None, I))
        for k in range(4):
            an = np.pi / 4 + k * np.pi / 2
            c = pivot + [0.024 * np.cos(an), s_ * (y_in - 0.006), 0.024 * np.sin(an)]
            P, N, I = cyl(c + [0, s_ * 0.003, 0], c - [0, s_ * 0.002, 0], 0.0042, 10); fixed['ti'].append((P, N, None, I))

    def emit(name, parts, mat, parent, offset, extras):
        Ps, Ns, UVs, Is, base, has_uv = [], [], [], [], 0, any(p[2] is not None for p in parts)
        for P, N, UV, I in parts:
            Ps.append(P - offset); Ns.append(N); Is.append(I + base); base += len(P)
            if has_uv:
                UVs.append(UV if UV is not None else np.zeros((len(P), 2)))
        att = Attributes(POSITION=glb.add(np.concatenate(Ps), 'pos'), NORMAL=glb.add(np.concatenate(Ns), 'vec3'))
        if has_uv:
            att.TEXCOORD_0 = glb.add(np.concatenate(UVs), 'vec2')
        g.meshes.append(Mesh(name=name, primitives=[Primitive(attributes=att, indices=glb.add(np.concatenate(Is), 'idx'), material=mat, mode=4)]))
        g.nodes.append(Node(name=name, mesh=len(g.meshes) - 1, extras=extras))
        g.nodes[parent].children = list(g.nodes[parent].children or []) + [len(g.nodes) - 1]
    Wi = np.linalg.inv(world(root_idx))
    to_root = lambda parts: [((P @ Wi[:3, :3].T + Wi[:3, 3]), N @ np.linalg.inv(Wi[:3, :3]), UV, I) for P, N, UV, I in parts]
    pivot_root = pivot @ Wi[:3, :3].T + Wi[:3, 3]
    axis_root = (Wi[:3, :3] @ np.array([0, 1.0, 0])); axis_root /= np.linalg.norm(axis_root)
    g.nodes.append(Node(name='VTX_VISUAL_DRS_HINGE', translation=pivot_root.tolist(), children=[], extras=dict(
        visual_only=True, mass_kg=0.0, joint_type='hinge', axis_parent=axis_root.tolist(), q_rest=0.0, range_deg=[0.0, D.AIRBRAKE_DEG],
        positive='trailing edge up (airbrake)', rest_te_up_deg=D.REST_DEG,
        note='split carbon DRS/airbrake flap; both halves on one axis, driven by the central Ti rotary EMA. Not in the MuJoCo plant; '
             'aero screening in engineering/phantom/drs_flap.py -> evidence/phantom/drs_balance.json')))
    hinge = len(g.nodes) - 1
    g.nodes[root_idx].children = list(g.nodes[root_idx].children or []) + [hinge]
    ex = dict(visual_only=True, mass_kg=0.0)
    # moving parts are authored hinge-local (rotation in root frame is identity for the Z-up live file; for Y-up
    # files the root itself carries the frame rotation, so hinge-local = root-local minus the pivot)
    rot_parts = lambda parts: [((np.asarray(P) + pivot) @ Wi[:3, :3].T + Wi[:3, 3] - pivot_root, N @ np.linalg.inv(Wi[:3, :3]), UV, I) for P, N, UV, I in parts]
    emit('VTX_VISUAL_DRS_CARBON_BLADES', rot_parts(moving['carbon']), mats['carbon'], hinge, 0, ex)
    emit('VTX_VISUAL_DRS_TI_RIBS_AND_SHAFTS', rot_parts(moving['ti']), mats['ti'], hinge, 0, ex)
    emit('VTX_VISUAL_DRS_RED_LED_BRAKE_STRIP', rot_parts(moving['red']), mats['red'], hinge, 0, ex)
    emit('VTX_VISUAL_DRS_CARBON_PYLON', to_root(fixed['carbon']), mats['carbon'], root_idx, 0, ex)
    emit('VTX_VISUAL_DRS_TI_ACTUATOR_AND_BEARINGS', to_root(fixed['ti']), mats['ti'], root_idx, 0, ex)
    emit('VTX_VISUAL_DRS_ACTUATOR_STATUS_RING', to_root(fixed['amber']), mats['amber'], root_idx, 0, ex)


BOOSTER = dict(y=0.40, z=0.51, x_hinge=-2.405, r_hinge=0.183, length=0.200, converge=0.032, theta_half_deg=74.0,
               cheek_aft_frac=0.62, thick=0.006, range_deg=(-15.0, 20.0))


def _shell_patch(axis_pt, th0, th1, x0, L, r_of_s, thick, nu=26, ns=14):
    """thick curved shell over angle th0..th1 (from +z toward +y) and length L aft of x0; returns outer, inner, P, N, I."""
    yb, zb = axis_pt
    th = np.radians(np.linspace(th0, th1, nu)); ss = np.linspace(0, 1, ns)
    def surf(dr):
        return np.array([[[x0 - L * s_, yb + (r_of_s(s_) + dr) * np.sin(t), zb + (r_of_s(s_) + dr) * np.cos(t)] for t in th] for s_ in ss])
    O, In = surf(0.0), surf(-thick)
    Ps, Ns, Is = [], [], []
    def grid(G, flip):
        n0, n1 = G.shape[:2]; V = G.reshape(-1, 3); I = []
        for i in range(n0 - 1):
            for j in range(n1 - 1):
                a, b, c, d = i * n1 + j, (i + 1) * n1 + j, (i + 1) * n1 + j + 1, i * n1 + j + 1
                I += [[a, b, c], [a, c, d]]
        I = np.array(I)
        if flip:
            I = I[:, [0, 2, 1]]
        fn = np.cross(V[I[:, 1]] - V[I[:, 0]], V[I[:, 2]] - V[I[:, 0]]); N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, I[:, k], fn)
        N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
        return V, N, I
    def strip(A, B):               # cap between two matching edge polylines
        V = np.concatenate([A, B]); n = len(A); I = []
        for k in range(n - 1):
            I += [[k, k + 1, n + k + 1], [k, n + k + 1, n + k]]
        I = np.array(I); fn = np.cross(V[I[:, 1]] - V[I[:, 0]], V[I[:, 2]] - V[I[:, 0]]); N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, I[:, k], fn)
        N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
        return V, N, I
    outer = grid(O, False); inner = grid(In, True)
    caps = [strip(O[-1], In[-1]), strip(In[0], O[0]), strip(O[:, 0], In[:, 0]), strip(In[:, -1], O[:, -1])]
    return outer, inner, caps


def add_booster_cowls(glb, root_idx, world, mats):
    """Conical split cowling on each rear booster (axisymmetric vectoring nozzle): 12 overlapping Ti petals with ceramic
    inner faces, each hinged at its root on a tangential axis, a Ti sync ring and four actuators. All petals rotating
    inward = partial closing (exit-area modulation); deflection varying as cos(theta - theta_v) tilts the cone =
    directional (vectoring). phantom-look.js drives the petals from the plant's booster state. Not a force model."""
    B = BOOSTER; g = glb.g
    Wi = np.linalg.inv(world(root_idx)); R = Wi[:3, :3]; t = Wi[:3, 3]
    NPET, L = 12, 0.215
    rS = lambda s_: B['r_hinge'] - 0.040 * s_ ** 1.15           # convergent cone, 0.183 -> 0.143 m
    def node(name, parts, mat, parent, origin_w, extras):
        Ps, Ns, Is, base = [], [], [], 0
        o_root = R @ origin_w + t if origin_w is not None else np.zeros(3)
        for P, N, I in parts:
            Ps.append(P @ R.T + t - o_root); Ns.append(N @ R.T); Is.append(I + base); base += len(P)
        g.meshes.append(Mesh(name=name, primitives=[Primitive(attributes=Attributes(POSITION=glb.add(np.concatenate(Ps), 'pos'), NORMAL=glb.add(np.concatenate(Ns), 'vec3')),
                                                              indices=glb.add(np.concatenate(Is), 'idx'), material=mat, mode=4)]))
        g.nodes.append(Node(name=name, mesh=len(g.meshes) - 1, extras=extras))
        g.nodes[parent].children = list(g.nodes[parent].children or []) + [len(g.nodes) - 1]
    ex = dict(visual_only=True, mass_kg=0.0)
    for side, tag in ((-1, 'L'), (1, 'R')):
        yb, zb = side * B['y'], B['z']
        fixed = []
        # Ti sync ring and four actuators (body on the nozzle, rod to the ring)
        xr = B['x_hinge'] + 0.030
        for k in range(36):
            a0, a1 = np.radians(k * 10), np.radians((k + 1) * 10)
            p0 = np.array([xr, yb + 0.197 * np.sin(a0), zb + 0.197 * np.cos(a0)]); p1 = np.array([xr, yb + 0.197 * np.sin(a1), zb + 0.197 * np.cos(a1)])
            fixed.append(cyl(p0, p1, 0.009, 10, caps=False))
        for k in range(4):
            th = np.radians(45 + 90 * k)
            rad = np.array([0, np.sin(th), np.cos(th)])
            c0 = np.array([B['x_hinge'] + 0.200, yb, zb]) + rad * 0.192
            c1 = np.array([B['x_hinge'] + 0.075, yb, zb]) + rad * 0.197
            fixed.append(cyl(c0, c1, 0.013, 14))                             # actuator body
            fixed.append(cyl(c1, np.array([xr + 0.008, yb, zb]) + rad * 0.197, 0.006, 10))   # rod to the sync ring
            fixed.append(cyl(c0 + [0.010, 0, 0], c0 - [0.008, 0, 0], 0.017, 12))           # trunnion
        node(f'VTX_VISUAL_BOOSTER_{tag}_SYNC_RING_AND_ACTUATORS', fixed, mats['ti'], root_idx, None, ex)
        for k in range(NPET):
            thc = 360.0 * k / NPET
            half = 360.0 / NPET / 2 + (2.2 if k % 2 else 0.0)                  # seals (odd) overlap the primary petals
            dr = 0.0025 if k % 2 else 0.0
            outer, inner, caps = _shell_patch((yb, zb), thc - half, thc + half, B['x_hinge'], L, lambda s_: rS(s_) + dr, 0.005, nu=8, ns=12)
            th = np.radians(thc)
            root = np.array([B['x_hinge'], yb + (B['r_hinge'] + dr) * np.sin(th), zb + (B['r_hinge'] + dr) * np.cos(th)])
            axis_w = np.array([0.0, -np.cos(th), np.sin(th)])                   # +rotation = tip toward the jet axis (closing)
            axis_r = R @ axis_w; axis_r /= np.linalg.norm(axis_r)
            g.nodes.append(Node(name=f'VTX_VISUAL_BOOSTER_{tag}_PETAL_{k:02d}_HINGE', translation=(R @ root + t).tolist(), children=[], extras=dict(
                visual_only=True, mass_kg=0.0, joint_type='hinge', axis_parent=axis_r.tolist(), q_rest=0.0, range_deg=[-12.0, 18.0],
                positive='closing (tip toward the jet axis)', theta_deg=thc, booster=('right' if side < 0 else 'left'),   # plant: physical left = +Y
                note='conical vectoring cowl petal: closing = all petals +; vectoring adds delta*cos(theta - theta_v). Not in the MuJoCo plant.')))
            h = len(g.nodes) - 1
            g.nodes[root_idx].children = list(g.nodes[root_idx].children or []) + [h]
            node(f'VTX_VISUAL_BOOSTER_{tag}_PETAL_{k:02d}_TI', [outer] + caps, mats['ti'], h, root, ex)
            node(f'VTX_VISUAL_BOOSTER_{tag}_PETAL_{k:02d}_CERAMIC', [inner], mats['ceramic'], h, root, ex)


def add_bay_frame(glb, airframe_idx, rib_mat, led_mat, world):
    """Visual-only frame over the exposed bay: ribs that follow the deck height + amber LED rails."""
    g = glb.g
    # sample deck height from the glazing we just made (hull primitives with glass material)
    pts = []
    for i, n in enumerate(g.nodes):
        if n.mesh is None:
            continue
        W = world(i)
        for p in g.meshes[n.mesh].primitives:
            if g.materials[p.material].name.startswith('VTX visual · smoked'):
                P = glb.data[p.attributes.POSITION].astype(float)
                pts.append(P @ W[:3, :3].T + W[:3, 3])
    if not pts:
        return
    pts = np.concatenate(pts)
    x0, x1 = pts[:, 0].min(), pts[:, 0].max()

    # one continuous slim frame + amber LED edge around the glazing footprint (no cross ribs: open look)
    from scipy.spatial import ConvexHull
    gl = []
    for i, n in enumerate(g.nodes):
        if n.mesh is None:
            continue
        W = world(i)
        for p in g.meshes[n.mesh].primitives:
            if g.materials[p.material].name.startswith('VTX visual · smoked') and len(glb.data[p.attributes.POSITION]) > 24:
                gl.append(glb.data[p.attributes.POSITION].astype(float) @ W[:3, :3].T + W[:3, 3])
    if not gl:
        return
    gl = np.concatenate(gl)
    hull = gl[ConvexHull(gl[:, :2]).vertices]
    ring = []
    for a0, a1 in zip(hull, np.roll(hull, -1, 0)):
        L = np.linalg.norm(a1[:2] - a0[:2])
        for t in np.linspace(0, 1, max(2, int(L / 0.03)), endpoint=False):
            ring.append(a0 + t * (a1 - a0))
    ring = np.array(ring)
    for r in ring:   # rim height = glazing height at that point
        d = np.linalg.norm(gl[:, :2] - r[:2], axis=1); r[2] = gl[np.argmin(d), 2]
    ctr = gl.mean(0)
    parts = []
    for r0, r1 in zip(ring, np.roll(ring, -1, 0)):
        mid = 0.5 * (r0 + r1); inward = ctr - mid; inward[2] = 0; inward /= np.linalg.norm(inward) + 1e-12
        lift = np.array([0, 0, 0.005])
        parts.append(('rib', rail(r0 + lift, r1 + lift, 0.022, 0.010)))
        parts.append(('led', rail(r0 + inward * 0.017 + lift, r1 + inward * 0.017 + lift, 0.005, 0.007)))
    for kind in ('rib', 'led'):
        Ps, Ns, Is, base = [], [], [], 0
        for k, (P, N, I) in parts:
            if k != kind:
                continue
            Ps.append(P); Ns.append(N); Is.append(I + base); base += len(P)
        Pw, Nw, Iw = np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Is)
        Wi = np.linalg.inv(world(airframe_idx))
        Pl = Pw @ Wi[:3, :3].T + Wi[:3, 3]
        Nl = Nw @ np.linalg.inv(Wi[:3, :3])
        Nl /= np.linalg.norm(Nl, axis=1, keepdims=True)
        prim = Primitive(attributes=Attributes(POSITION=glb.add(Pl, 'pos'), NORMAL=glb.add(Nl, 'vec3')),
                         indices=glb.add(Iw, 'idx'), material=rib_mat if kind == 'rib' else led_mat, mode=4)
        g.meshes.append(Mesh(name=f'VTX_VISUAL_WING_BAY_{kind.upper()}', primitives=[prim]))
        g.nodes.append(Node(name=f'VTX_VISUAL_WING_BAY_{"INSPECTION_FRAME" if kind == "rib" else "AMBER_LED_RAILS"}',
                            mesh=len(g.meshes) - 1,
                            extras=dict(visual_only=True, mass_kg=0.0, note='render-only; not in the mass ledger or collision model')))
        g.nodes[airframe_idx].children = list(g.nodes[airframe_idx].children or []) + [len(g.nodes) - 1]
    # two warm service lights inside the bay so the mechanism reads through the glazing
    ext = g.extensions.setdefault('KHR_lights_punctual', {'lights': []})
    ext['lights'].append({'name': 'VTX_VISUAL_WING_BAY_LIGHT', 'type': 'point', 'color': [1.0, 0.82, 0.6], 'intensity': 3.0, 'range': 1.5})
    li = len(ext['lights']) - 1
    Wi = np.linalg.inv(world(airframe_idx))
    for y in (-0.66, 0.66):
        pw = np.array([0.5 * (x0 + x1), y, 1.072, 1.0])
        g.nodes.append(Node(name=f'VTX_VISUAL_WING_BAY_LIGHT_{"R" if y < 0 else "L"}', translation=(Wi @ pw)[:3].tolist(),
                            extensions={'KHR_lights_punctual': {'light': li}}, extras=dict(visual_only=True, mass_kg=0.0)))
        g.nodes[airframe_idx].children.append(len(g.nodes) - 1)


def build(src, dst, livery=True):
    stats = refine(src, dst)
    if livery:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from phantom_livery import apply_livery
        glb = Glb(dst)
        world, _ = node_world(glb)
        af = visual_root(glb)
        apply_livery(glb, dst, af, world, stats, yup=glb.yup)
        glb.save(dst)
    return stats


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    print(build(src, dst, livery='--no-livery' not in sys.argv))
