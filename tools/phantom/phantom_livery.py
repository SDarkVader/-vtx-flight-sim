"""VTX Phantom livery + fastener pass (render only). Called by refine_phantom_visual.py after the shell pass.

Adds, as visual-only nodes under the 'airframe' root (extras visual_only=True, mass_kg=0):
  * Vader's Taxis artwork: angular gold V emblem + stacked VADER'S TAXIS wordmark on both doors, V emblem on
    both raked fins and on the bonnet. Each decal is a grid ray-projected onto the actual (refined) surface,
    lifted 2 mm along the hit normal, so it wraps the curvature instead of floating as a flat card.
  * Red LED tail chevrons projected onto the tail, white LED headlight blades on the front face.
  * Rivet rows: low dome fasteners every RIVET_PITCH along the shell's feature creases, set RIVET_INSET
    inside the panel, snapped to the surface.
Artwork is drawn procedurally here (PIL) and embedded as PNG textures; no external images.
"""
from __future__ import annotations
import io
import math
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pygltflib import Mesh, Primitive, Attributes, Node, Material, PbrMetallicRoughness, Image as GImage, Texture, Sampler, TextureInfo

FONT = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
FONT_FALLBACK = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
GOLD = (255, 176, 28)
SILVER = (214, 220, 228)
RIVET_PITCH = 0.055
RIVET_INSET = 0.016
RIVET_R = 0.0042
CREASE_MIN_DEG = 24.0
RIVET_MATS = ('A6 VTX Phantom satin gunmetal armour', 'A6 sharp graphite armour facet')


def _font(px):
    try:
        return ImageFont.truetype(FONT, px)
    except OSError:
        return ImageFont.truetype(FONT_FALLBACK, px)

# ------------------------------------------------------------------------------------- artwork


def v_emblem(size=512):
    """Original solid faceted V badge: light-gold left arm, deeper-gold right arm, fine dark centre seam."""
    S = size * 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = S / 100.0
    P = lambda pts: [(x * s, y * s) for x, y in pts]
    left = [(6, 12), (34, 12), (50, 60), (50, 92), (44, 92)]
    right = [(94, 12), (66, 12), (50, 60), (50, 92), (56, 92)]
    d.polygon(P(left), fill=(255, 202, 74, 255))
    d.polygon(P(right), fill=(214, 140, 14, 255))
    d.line(P([(50, 60), (50, 92)]), fill=(70, 40, 4, 255), width=max(2, int(0.8 * s)))
    d.line(P([(6, 12), (34, 12)]), fill=(255, 232, 170, 255), width=max(2, int(1.0 * s)))      # top bevel highlight
    d.line(P([(66, 12), (94, 12)]), fill=(255, 214, 120, 255), width=max(2, int(1.0 * s)))
    im = im.resize((size, size), Image.LANCZOS)
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(size / 70))
    base = Image.new('RGBA', im.size, (0, 0, 0, 0))
    base.putalpha(glow.point(lambda a: a * 0.30))
    return Image.alpha_composite(base, im)


def wordmark(w=1536, h=200):
    """Slanted VADER'S TAXIS (text only; the amber lines are separate curved ribbons that follow the door)."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = _font(int(h * 0.70))
    d.text((int(w * 0.10), int(h * 0.08)), "VADER'S TAXIS", font=f, fill=SILVER + (255,))
    im = im.transform(im.size, Image.AFFINE, (1, 0.22, -h * 0.20, 0, 1, 0), resample=Image.BICUBIC)  # italic shear
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(4))
    base = Image.new('RGBA', im.size, GOLD + (0,)); base.putalpha(glow.point(lambda a: a * 0.18))
    return Image.alpha_composite(base, im)


# Amber door swoops in the side view (x forward, z up), kept low under the door's Z-shaped highlight trough
# (trough ~ (-0.42, 0.544) -> (0.10, 0.49) -> (0.59, 0.70)) so they never cross a body line.
DOOR_SWOOPS = [((-0.50, 0.506), (-0.18, 0.462), (0.12, 0.452), (0.44, 0.528), 0.011),
               ((-0.36, 0.472), (-0.08, 0.437), (0.14, 0.432), (0.33, 0.476), 0.008)]


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n)[:, None]
    P = [np.array(p) for p in (p0, p1, p2, p3)]
    return (1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3]


def ribbon(surface, xz, side, width, lift=0.0025, max_jump=0.03):
    """amber ribbon following a side-view curve, ray-projected point by point onto the body."""
    org = np.stack([xz[:, 0], np.full(len(xz), side * 2.5), xz[:, 1]], 1)
    hit, nrm = surface.cast(org, np.repeat(np.array([[0, -side, 0.0]]), len(org), 0))
    Ps, Ns, Is, base = [], [], [], 0
    run = []

    def flush():
        nonlocal base
        if len(run) < 2:
            return
        R = np.array([h for h, _ in run]); Nn = np.array([n for _, n in run])
        T = np.gradient(R, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
        B = np.cross(Nn, T); B /= np.linalg.norm(B, axis=1, keepdims=True) + 1e-12
        # taper the ends to points, like a swept pin-stripe
        k = len(R); taper = np.minimum(1, np.minimum(np.arange(k), np.arange(k)[::-1]) / 6.0)[:, None]
        L = R + Nn * lift + B * width * 0.5 * taper; Rr = R + Nn * lift - B * width * 0.5 * taper
        V = np.concatenate([L, Rr]); N2 = np.concatenate([Nn, Nn])
        I = []
        for i in range(k - 1):
            a, b, c, d = i, i + 1, k + i + 1, k + i
            I += [[a, b, c], [a, c, d]]
        I = np.array(I)
        fn = np.cross(V[I[:, 1]] - V[I[:, 0]], V[I[:, 2]] - V[I[:, 0]])
        flip = (fn * N2[I[:, 0]]).sum(1) < 0
        I[flip] = I[flip][:, [0, 2, 1]]
        Ps.append(V); Ns.append(N2); Is.append(I + base); base += len(V)
    prev = None
    for h, n in zip(hit, nrm):
        if np.isnan(h).any() or (prev is not None and abs(h[1] - prev[1]) > max_jump):
            flush(); run = []
        if not np.isnan(h).any():
            run.append((h, n)); prev = h
    flush()
    if not Ps:
        return np.zeros((0, 3)), np.zeros((0, 3)), None, np.zeros((0, 3), np.int64)
    return np.concatenate(Ps), np.concatenate(Ns), None, np.concatenate(Is)


def tail_chevron(w=1024, h=256):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for side in (-1, 1):
        cx = w / 2 + side * w * 0.04
        pts = [(cx, h * 0.62), (cx + side * w * 0.40, h * 0.22), (cx + side * w * 0.46, h * 0.22),
               (cx + side * w * 0.43, h * 0.34), (cx + side * w * 0.03, h * 0.78)]
        d.polygon(pts, fill=(255, 8, 4, 255))
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(6))
    base = Image.new('RGBA', im.size, (255, 20, 10, 0)); base.putalpha(glow.point(lambda a: a * 0.6))
    return Image.alpha_composite(base, im)


def led_lens(w=1024, h=128):
    """tail-lamp lens: fine LED segments behind a light-guide outline, deep red between them."""
    im = Image.new('RGB', (w, h), (46, 2, 2))
    d = ImageDraw.Draw(im)
    seg, gap = 18, 7
    for x in range(10, w - 10, seg + gap):
        d.rectangle([x, int(h * 0.30), x + seg, int(h * 0.70)], fill=(255, 24, 12))
        d.rectangle([x + 3, int(h * 0.38), x + seg - 3, int(h * 0.62)], fill=(255, 120, 90))
    d.rectangle([4, 4, w - 5, h - 5], outline=(255, 40, 20), width=5)          # light-guide outline
    return im.filter(ImageFilter.GaussianBlur(1.2))


def head_blade(w=512, h=128):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(w * 0.02, h * 0.70), (w * 0.88, h * 0.18), (w * 0.98, h * 0.18), (w * 0.14, h * 0.82)], fill=(235, 245, 255, 255))
    for k in range(4):
        x = w * (0.30 + 0.14 * k)
        d.line([(x, h * 0.55 - k * h * 0.08), (x + w * 0.06, h * 0.52 - k * h * 0.08)], fill=(20, 24, 30, 255), width=3)
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(4))
    base = Image.new('RGBA', im.size, (200, 225, 255, 0)); base.putalpha(glow.point(lambda a: a * 0.5))
    return Image.alpha_composite(base, im)


def carbon_twill(size=512, tows=12):
    """2x2 twill carbon weave: alternating tow blocks with fibre sheen, tileable."""
    t = size // tows
    y, x = np.mgrid[0:size, 0:size]
    i, j = x // t, y // t
    warp = ((i + j) // 2) % 2 == 0                    # 2x2 twill diagonal
    u, v = (x % t) / t, (y % t) / t
    fib = np.where(warp, np.sin(v * np.pi), np.sin(u * np.pi))          # tow crown
    streak = np.where(warp, np.sin(x * 2.1) * 0.5 + 0.5, np.sin(y * 2.1) * 0.5 + 0.5)
    lum = 10 + 78 * fib ** 1.3 + 22 * streak * fib
    col = np.stack([lum * 0.92, lum * 0.96, lum * 1.05], -1)
    return Image.fromarray(col.clip(0, 255).astype(np.uint8), 'RGB')


def ember_gradient(size=256):
    """mild radial ember glow for the thruster hubs: warm orange core -> deep red rim."""
    y, x = np.mgrid[0:size, 0:size] / (size - 1) * 2 - 1
    r = np.clip(np.hypot(x, y), 0, 1)
    core, rim = np.array([255, 62, 18.0]), np.array([120, 6, 2.0])
    t = r[..., None] ** 1.4
    col = core * (1 - t) + rim * t
    col *= (1 - 0.55 * r ** 3)[..., None]
    return Image.fromarray(col.clip(0, 255).astype(np.uint8), 'RGB')


def emissive_of(im, keep):
    """emissive map: only the pixels whose colour matches `keep` (callable on rgb)."""
    a = np.asarray(im).astype(np.float32)
    m = np.array([[keep(*px[:3]) for px in row] for row in a[::1]], np.float32) if False else keep(a[..., 0], a[..., 1], a[..., 2])
    out = np.zeros_like(a)
    out[..., :3] = a[..., :3] * (m * a[..., 3:4].squeeze(-1) / 255.0)[..., None]
    out[..., 3] = 255
    return Image.fromarray(out.astype(np.uint8)).convert('RGB')

# ----------------------------------------------------------------------------------- projection


class Surface:
    def __init__(self, glb_path, exclude=('VTX_VISUAL', 'probe', 'PROBE'), yup=False):
        sc = load_zup(glb_path, yup)
        parts = []
        for name in sc.graph.nodes_geometry:
            if any(e in name for e in exclude):
                continue
            T, gn = sc.graph[name]
            m = sc.geometry[gn]
            mat = getattr(getattr(m, 'visual', None), 'material', None)
            if mat is not None and 'glazing' in (mat.name or ''):
                continue
            mm = m.copy(); mm.apply_transform(T); parts.append(mm)
        self.mesh = trimesh.util.concatenate(parts)
        self.tri = self.mesh.triangles
        self.fn = self.mesh.face_normals

    def cast(self, origins, dirs):
        """nearest hit per ray (Moller-Trumbore, numpy); rays of one call share a direction."""
        d = dirs[0] / np.linalg.norm(dirs[0])
        # cull triangles outside the ray bundle's footprint (plane normal to d)
        a = np.cross(d, [0, 0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0, 0]); a /= np.linalg.norm(a); b = np.cross(d, a)
        po = np.stack([origins @ a, origins @ b], 1)
        tp = np.stack([self.tri @ a, self.tri @ b], 2)          # (T,3,2)
        lo, hi = po.min(0) - 1e-3, po.max(0) + 1e-3
        keep = (tp[..., 0].max(1) >= lo[0]) & (tp[..., 0].min(1) <= hi[0]) & (tp[..., 1].max(1) >= lo[1]) & (tp[..., 1].min(1) <= hi[1])
        T = self.tri[keep]; FN = self.fn[keep]
        hit = np.full((len(origins), 3), np.nan); nrm = np.full((len(origins), 3), np.nan)
        if not len(T):
            return hit, nrm
        v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        pv = np.cross(d, e2); det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        for s0 in range(0, len(origins), 64):
            O = origins[s0:s0 + 64]
            tv = O[:, None, :] - v0[None]
            u = (tv * pv[None]).sum(2) * inv[None]
            qv = np.cross(tv, e1[None])
            v = (qv @ d) * inv[None]
            t = (qv * e2[None]).sum(2) * inv[None]
            m = ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
            t = np.where(m, t, np.inf)
            k = t.argmin(1); tb = t[np.arange(len(O)), k]
            good = np.isfinite(tb)
            hit[s0:s0 + 64][good] = O[good] + d * tb[good, None]
            nrm[s0:s0 + 64][good] = FN[k[good]]
        flip = (nrm @ d) > 0
        nrm[flip] *= -1
        return hit, nrm


def load_zup(path, yup):
    sc = trimesh.load(path, force='scene')
    if yup:
        C = np.eye(4); C[:3, :3] = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
        sc.apply_transform(C)
    return sc


def fin_emblem(m, size=0.16, lift=0.0025):
    """flat emblem quad fitted to the fin's outboard face plane (a thin canted plate: a ray grid tears there)."""
    side = 1.0 if m.vertices[:, 1].mean() > 0 else -1.0
    fn, ar, ctr = m.face_normals, m.area_faces, m.triangles_center
    sel = fn[:, 1] * side > 0.35
    n = (fn[sel] * ar[sel, None]).sum(0); n /= np.linalg.norm(n)
    # the face cluster aligned with the dominant outboard plane
    sel &= (fn @ n) > 0.97
    c = (ctr[sel] * ar[sel, None]).sum(0) / ar[sel].sum()
    up = np.array([0, 0, 1.0]) - n[2] * n; up /= np.linalg.norm(up)
    right = np.cross(up, n)
    # centre on the point of the outboard face farthest from its outline (largest inscribed circle), so it can't clip
    from scipy.spatial import ConvexHull
    pts = m.vertices[np.unique(m.faces[sel])] - c
    q = np.stack([pts @ right, pts @ up], 1)
    hull = q[ConvexHull(q).vertices]
    lo, hi = q.min(0), q.max(0)
    gx, gy = np.meshgrid(np.linspace(lo[0], hi[0], 80), np.linspace(lo[1], hi[1], 80))
    G = np.stack([gx.ravel(), gy.ravel()], 1)
    d = np.full(len(G), np.inf); inside = np.ones(len(G), bool)
    for a, b in zip(hull, np.roll(hull, -1, 0)):
        t = b - a; nrm = np.array([t[1], -t[0]]) / np.linalg.norm(t)
        sd = (G - a) @ nrm                       # CCW hull: outward normal -> inside is sd < 0
        inside &= sd < 0
        d = np.minimum(d, -sd)
    d[~inside] = -1
    k = int(np.argmax(d)); r_in = d[k]
    sz = min(size, 1.30 * r_in)
    c = c + right * G[k, 0] + up * G[k, 1] + n * lift
    P = np.array([c - right * sz / 2 - up * sz / 2, c + right * sz / 2 - up * sz / 2, c + right * sz / 2 + up * sz / 2, c - right * sz / 2 + up * sz / 2])
    UV = np.array([[0, 1], [1, 1], [1, 0], [0, 0.0]])
    if side < 0:            # read the same way from both sides
        UV[:, 0] = 1 - UV[:, 0]
    I = np.array([[0, 1, 2], [0, 2, 3]])
    fnq = np.cross(P[1] - P[0], P[2] - P[0])
    if np.dot(fnq, n) < 0:
        I = I[:, [0, 2, 1]]
    return P, np.repeat(n[None], 4, 0), UV, I


def decal(surface, center, u, v, w, h, direction, nu=40, nv=14, lift=0.002, max_jump=0.06):
    """grid in the (u, v) plane at `center`, cast along `direction`; returns P, N, UV, I (drops missed quads)."""
    center, u, v, direction = (np.asarray(x, float) for x in (center, u, v, direction))
    direction /= np.linalg.norm(direction)
    su, sv = np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1)
    U, V = np.meshgrid(su, sv, indexing='ij')
    pts = center + (U[..., None] - 0.5) * w * u + (V[..., None] - 0.5) * h * v
    org = pts.reshape(-1, 3) - direction * 1.5
    dirs = np.repeat(direction[None], len(org), 0)
    hit, nrm = surface.cast(org, dirs)
    P = hit + nrm * lift
    uv = np.stack([U.ravel(), 1 - V.ravel()], 1)
    idx = np.arange(len(org)).reshape(nu + 1, nv + 1)
    I = []
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
            q = P[[a, b, c, d]]
            if np.isnan(q).any():
                continue
            # skip quads that straddle two different surfaces (depth jump)
            if np.ptp((q * direction).sum(1)) > max_jump:
                continue
            I += [[a, b, c], [a, c, d]]
    I = np.array(I, np.int64)
    used = np.unique(I)
    remap = -np.ones(len(P), np.int64); remap[used] = np.arange(len(used))
    P, N, uv = P[used], nrm[used], uv[used]
    # orient faces to the outward normal
    I = remap[I]
    fn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    flip = (fn * N[I[:, 0]]).sum(1) < 0
    I[flip] = I[flip][:, [0, 2, 1]]
    return P, N, uv, I

# -------------------------------------------------------------------------------------- rivets


def dome(r=RIVET_R, h=0.0016, seg=8):
    P = [[0, 0, h]]; N = [[0, 0, 1]]
    for ring, (rr, zz) in enumerate(((r * 0.6, h * 0.8), (r, 0.0))):
        for k in range(seg):
            a = 2 * math.pi * k / seg
            P.append([rr * math.cos(a), rr * math.sin(a), zz])
            nz = 0.75 if ring == 0 else 0.3
            n = np.array([math.cos(a) * (1 - nz), math.sin(a) * (1 - nz), nz]); N.append(n / np.linalg.norm(n))
    I = []
    for k in range(seg):
        I.append([0, 1 + k, 1 + (k + 1) % seg])
        a, b, c, d = 1 + k, 1 + seg + k, 1 + seg + (k + 1) % seg, 1 + (k + 1) % seg
        I += [[a, b, c], [a, c, d]]
    return np.array(P, float), np.array(N, float), np.array(I)


def rivet_sites(shell_meshes):
    """(point, normal) pairs along feature creases of the given world-space trimesh panels."""
    pts, nrms = [], []
    for m in shell_meshes:
        m = m.copy(); m.merge_vertices(merge_tex=True, merge_norm=True)
        if len(m.faces) < 4:
            continue
        adj = m.face_adjacency; ang = m.face_adjacency_angles; edges = m.face_adjacency_edges
        sel = ang > math.radians(CREASE_MIN_DEG)
        fn = m.face_normals; area = m.area_faces
        for (f0, f1), e in zip(adj[sel], edges[sel]):
            f = f0 if area[f0] >= area[f1] else f1
            a, b = m.vertices[e[0]], m.vertices[e[1]]
            L = np.linalg.norm(b - a)
            if L < 1e-4:
                continue
            t = (b - a) / L
            inward = np.cross(fn[f], t)
            if np.dot(inward, m.triangles_center[f] - a) < 0:
                inward = -inward
            # deterministic sampling on a global arc-length lattice so neighbouring segments line up
            s0 = (np.dot(a, [0.6, 0.3, 0.1]) % RIVET_PITCH)
            for s in np.arange(RIVET_PITCH - s0, L, RIVET_PITCH):
                pts.append(a + t * s + inward * RIVET_INSET); nrms.append(fn[f])
    if not pts:
        return np.zeros((0, 3)), np.zeros((0, 3))
    P, N = np.array(pts), np.array(nrms)
    ok = np.isfinite(P).all(1) & np.isfinite(N).all(1) & (np.linalg.norm(N, axis=1) > 0.5)
    P, N = P[ok], N[ok]
    # thin out duplicates (two creases meeting at a corner)
    keep = np.ones(len(P), bool)
    key = np.round(P / (RIVET_PITCH * 0.5)).astype(np.int64)
    _, first = np.unique(key, axis=0, return_index=True)
    keep[:] = False; keep[first] = True
    return P[keep], N[keep]


def rivet_mesh(P, N):
    dP, dN, dI = dome()
    out_p, out_n, out_i = [], [], []
    for k, (p, n) in enumerate(zip(P, N)):
        z = n / np.linalg.norm(n)
        x = np.cross(z, [0, 0, 1.0] if abs(z[2]) < 0.9 else [1.0, 0, 0]); x /= np.linalg.norm(x)
        y = np.cross(z, x)
        R = np.stack([x, y, z], 1)
        out_p.append(dP @ R.T + p - z * 0.0004); out_n.append(dN @ R.T); out_i.append(dI + k * len(dP))
    return np.concatenate(out_p), np.concatenate(out_n), np.concatenate(out_i)

# ---------------------------------------------------------------------------------- glTF glue


def _png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


def add_texture(glb, im):
    g = glb.g
    g.images = g.images or []; g.textures = g.textures or []; g.samplers = g.samplers or []
    if not g.samplers:
        g.samplers.append(Sampler(magFilter=9729, minFilter=9987, wrapS=33071, wrapT=33071))
    g.images.append(GImage(mimeType='image/png'))
    glb.image_bytes[len(g.images) - 1] = _png(im)
    g.textures.append(Texture(sampler=0, source=len(g.images) - 1))
    return len(g.textures) - 1


def decal_material(glb, name, art, emissive=None, strength=1.0, metal=0.2, rough=0.35, clearcoat=True):
    tb = add_texture(glb, art)
    m = Material(name=name, alphaMode='BLEND', doubleSided=False,
                 pbrMetallicRoughness=PbrMetallicRoughness(baseColorTexture=TextureInfo(index=tb), metallicFactor=metal, roughnessFactor=rough))
    m.extensions = {}
    if emissive is not None:
        m.emissiveTexture = TextureInfo(index=add_texture(glb, emissive))
        m.emissiveFactor = [1.0, 1.0, 1.0]
        m.extensions['KHR_materials_emissive_strength'] = {'emissiveStrength': strength}
    if clearcoat:
        m.extensions['KHR_materials_clearcoat'] = {'clearcoatFactor': 1.0, 'clearcoatRoughnessFactor': 0.04}
    glb.g.materials.append(m)
    return len(glb.g.materials) - 1


def add_node(glb, airframe_idx, world, name, parts, material, note):
    """parts: list of (P, N, UV|None, I) in world space -> one mesh node under the airframe root."""
    g = glb.g
    Wi = np.linalg.inv(world(airframe_idx))
    Ps, Ns, UVs, Is, base = [], [], [], [], 0
    for P, N, UV, I in parts:
        if len(I) == 0:
            continue
        Ps.append(P @ Wi[:3, :3].T + Wi[:3, 3]); Ns.append(N @ np.linalg.inv(Wi[:3, :3])); Is.append(I + base)
        if UV is not None:
            UVs.append(UV)
        base += len(P)
    if not Ps:
        return
    P, N, I = np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Is)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    att = Attributes(POSITION=glb.add(P, 'pos'), NORMAL=glb.add(N, 'vec3'))
    if UVs:
        att.TEXCOORD_0 = glb.add(np.concatenate(UVs), 'vec2')
    g.meshes.append(Mesh(name=name, primitives=[Primitive(attributes=att, indices=glb.add(I, 'idx'), material=material, mode=4)]))
    g.nodes.append(Node(name=name, mesh=len(g.meshes) - 1, extras=dict(visual_only=True, mass_kg=0.0, note=note)))
    g.nodes[airframe_idx].children = list(g.nodes[airframe_idx].children or []) + [len(g.nodes) - 1]


def closest_on_triangles(Pts, T):
    """closest point on a triangle soup for each point (Ericson, Real-Time Collision Detection 5.1.5), vectorised.
    Returns (points, face index)."""
    out = np.zeros_like(Pts); idx = np.zeros(len(Pts), int)
    A, B, C = T[:, 0], T[:, 1], T[:, 2]
    AB, AC = B - A, C - A
    for i, p in enumerate(Pts):
        AP = p - A
        d1, d2 = (AB * AP).sum(1), (AC * AP).sum(1)
        BP = p - B; d3, d4 = (AB * BP).sum(1), (AC * BP).sum(1)
        CP = p - C; d5, d6 = (AB * CP).sum(1), (AC * CP).sum(1)
        va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
        res = np.zeros_like(A); done = np.zeros(len(A), bool)
        m = (d1 <= 0) & (d2 <= 0); res[m] = A[m]; done |= m
        m = ~done & (d3 >= 0) & (d4 <= d3); res[m] = B[m]; done |= m
        m = ~done & (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        v = d1 / np.where(d1 - d3 == 0, 1, d1 - d3); res[m] = A[m] + v[m, None] * AB[m]; done |= m
        m = ~done & (d6 >= 0) & (d5 <= d6); res[m] = C[m]; done |= m
        m = ~done & (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        w = d2 / np.where(d2 - d6 == 0, 1, d2 - d6); res[m] = A[m] + w[m, None] * AC[m]; done |= m
        m = ~done & (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
        den = (d4 - d3) + (d5 - d6); w = (d4 - d3) / np.where(den == 0, 1, den); res[m] = B[m] + w[m, None] * (C[m] - B[m]); done |= m
        den = va + vb + vc; den = np.where(den == 0, 1, den); v = vb / den; w = vc / den
        m = ~done; res[m] = A[m] + v[m, None] * AB[m] + w[m, None] * AC[m]
        k = int(np.argmin(((res - p) ** 2).sum(1))); out[i] = res[k]; idx[i] = k
    return out, idx


SNAP_STRIPS = ('SIDEBLADE_AMBER', 'NARROW_AMBER_BROW', 'FRONT_FENDER_AMBER_SLIT', 'FIN_AMBER_RAKE', 'AMBER_CHEVRON_LAMP')
HIDE_STRIPS = ('HAUNCH_L_AMBER_CREASE', 'HAUNCH_R_AMBER_CREASE')     # replaced by the cowl shoulder line


def snap_strips(glb, surface_path, world, yup, stats):
    """lay the original CAD amber strips flush on the (smoothed) body: each vertex is ray-snapped along the strip's
    own normal (its thinnest axis) to the nearest body surface and lifted 2.5 mm. Planform is kept."""
    from refine_phantom_visual import tris_of
    body = Surface(surface_path, exclude=('VTX_VISUAL', 'PROBE', 'AMBER', 'CHEVRON_LAMP', 'LIVERY', 'RIVET'), yup=yup)
    g = glb.g; moved = []
    for ni, n in enumerate(g.nodes):
        if n.mesh is None:
            continue
        if any(h in n.name for h in HIDE_STRIPS):
            n.extras = dict(n.extras or {}, visual_hidden='replaced by the wing-cassette cowl shoulder line'); n.mesh = None; continue
        if not any(k in n.name for k in SNAP_STRIPS):
            continue
        W = world(ni); Wi = np.linalg.inv(W)
        for p in g.meshes[n.mesh].primitives:
            P, N, I = tris_of(glb, p)
            Pw = P @ W[:3, :3].T + W[:3, 3]
            c = Pw.mean(0); _, _, Vt = np.linalg.svd(Pw - c, full_matrices=False); a = Vt[2]
            best = np.full(len(Pw), np.inf); hit = Pw.copy(); nh = np.zeros_like(Pw)
            for sgn in (1, -1):
                h, nn = body.cast(Pw + sgn * a * 0.12, np.repeat((-sgn * a)[None], len(Pw), 0))
                dist = np.linalg.norm(h - Pw, axis=1)
                ok = np.isfinite(dist) & (dist < best) & (dist < 0.11)
                best[ok] = dist[ok]; hit[ok] = h[ok]; nh[ok] = nn[ok]
            # fallback for strips standing edge-on to the body: true closest point on nearby body triangles
            lo, hi = Pw.min(0) - 0.15, Pw.max(0) + 0.15
            tri = body.tri; near = ((tri.max(1) >= lo) & (tri.min(1) <= hi)).all(1)
            if near.any():
                cp, fi = closest_on_triangles(Pw, tri[near])
                dcp = np.linalg.norm(cp - Pw, axis=1)
                use = ~np.isfinite(best) | (dcp < best - 1e-4)
                fnn = body.fn[near][fi]
                # orient the normal toward where the strip was (outside)
                flip = ((Pw - cp) * fnn).sum(1) < 0
                fnn[flip] *= -1
                best[use] = dcp[use]; hit[use] = cp[use]; nh[use] = fnn[use]
            ok = np.isfinite(best) & (best < 0.12)
            new = Pw.copy(); new[ok] = hit[ok] + nh[ok] * 0.0025
            Nw = np.where(ok[:, None], nh, (N @ W[:3, :3].T))
            Pl = new @ Wi[:3, :3].T + Wi[:3, 3]; Nl = Nw @ W[:3, :3]; Nl /= np.linalg.norm(Nl, axis=1, keepdims=True) + 1e-12
            p.attributes.POSITION = glb.add(Pl, 'pos'); p.attributes.NORMAL = glb.add(Nl, 'vec3')
            moved.append((n.name, float(np.median(best[ok])) if ok.any() else None, int(ok.sum()), len(Pw)))
    stats['amber_strips_snapped'] = len(moved)
    return moved


TAIL_LAMP = dict(inner=(0.075, 0.734), outer=(0.375, 0.812), t_in=0.030, t_out=0.016)


def _offset_poly(P2, d):
    """miter offset of a convex CCW polygon (outward for d > 0)."""
    n = len(P2); out = []
    for i in range(n):
        a, b, c = P2[i - 1], P2[i], P2[(i + 1) % n]
        e1 = (b - a) / np.linalg.norm(b - a); e2 = (c - b) / np.linalg.norm(c - b)
        n1 = np.array([e1[1], -e1[0]]); n2 = np.array([e2[1], -e2[0]])
        m = n1 + n2; m /= np.linalg.norm(m)
        out.append(b + m * d / max(0.3, np.dot(m, n1)))
    return np.array(out)


def tail_lamps(S):
    """two swept LED tail lamps on the flat rear panel: bevelled dark bezel (outline) + recessed textured lens."""
    T = TAIL_LAMP
    (y0, z0), (y1, z1), t0, t1 = T['inner'], T['outer'], T['t_in'], T['t_out']
    dirv = np.array([y1 - y0, z1 - z0]); L = np.linalg.norm(dirv); dirv /= L; nrm = np.array([-dirv[1], dirv[0]])
    # blade outline (y, z): angled inboard cut, tapered, pointed outboard tip; CCW seen from behind
    base = np.array([y0, z0])
    poly = np.array([base - nrm * t0 / 2 + dirv * 0.012, base + dirv * (L - 0.010) - nrm * t1 / 2, base + dirv * L + nrm * t1 * 0.1,
                     base + dirv * (L - 0.016) + nrm * t1 / 2, base + nrm * t0 / 2 - dirv * 0.004])
    if np.cross(np.append(poly[1] - poly[0], 0), np.append(poly[2] - poly[1], 0))[2] < 0:
        poly = poly[::-1]
    C0, C1, C2 = poly, _offset_poly(poly, 0.004), _offset_poly(poly, 0.007)
    bez, lens = [], []
    for side in (-1, 1):
        def lift(C, h):
            Y = C[:, 0] * side; Z = C[:, 1]
            org = np.stack([np.full(len(C), -4.0), Y, Z], 1)
            hit, nn = S.cast(org, np.repeat(np.array([[1.0, 0, 0]]), len(C), 0))
            return hit + nn * h, nn
        rings = [lift(C2, 0.0005), lift(C2, 0.003), lift(C1, 0.009), lift(C0, 0.009), lift(C0, 0.004)]
        Ps, Ns, Is = [], [], []
        for (A, _), (B, _) in zip(rings[:-1], rings[1:]):
            n = len(A)
            for k in range(n):
                q = np.array([A[k], A[(k + 1) % n], B[(k + 1) % n], B[k]])
                fn = np.cross(q[1] - q[0], q[3] - q[0]); fn /= np.linalg.norm(fn) + 1e-12
                b0 = sum(len(p) for p in Ps)
                Ps.append(q); Ns.append(np.repeat(fn[None], 4, 0)); Is.append(np.array([[b0, b0 + 1, b0 + 2], [b0, b0 + 2, b0 + 3]]))
        P = np.concatenate(Ps); N = np.concatenate(Ns); I = np.concatenate(Is)
        outward = rings[0][1].mean(0)
        # all bezel faces should face away from the panel (or sideways); flip any facing into it
        fl = (N @ outward) < -0.2
        N[fl] *= -1
        I = np.concatenate([_tri_fix(P, N, I)])
        bez.append((P, N, None, I))
        # lens: fan over the recessed inner contour, UV along the blade
        LP, LN = rings[-1]
        ctr = LP.mean(0); P2 = np.vstack([LP, ctr]); N2 = np.vstack([LN, LN.mean(0)])
        n = len(LP); I2 = np.array([[n, k, (k + 1) % n] for k in range(n)])
        I2 = _tri_fix(P2, N2, I2)
        rel = np.vstack([C0, C0.mean(0)]) - base
        UV = np.stack([(rel @ dirv) / L, 0.5 + (rel @ nrm) / (t0 * 1.15)], 1)
        lens.append((P2, N2, UV, I2))
    return bez, lens


def _tri_fix(P, N, I):
    fn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    flip = (fn * N[I[:, 0]]).sum(1) < 0
    I = I.copy(); I[flip] = I[flip][:, [0, 2, 1]]
    return I


def apply_livery(glb, surface_path, airframe_idx, world, stats, yup=False):
    snap_strips(glb, surface_path, world, yup, stats)
    S = Surface(surface_path, yup=yup)
    ex, ey, ez = np.eye(3)
    # ---- flank wordmark on both doors (reads front-to-back on each side)
    art = wordmark()
    gold_only = lambda r, gch, b: ((r > 180) & (gch > 100) & (b < 120)).astype(np.float32)
    mat_word = decal_material(glb, 'VTX visual · Vaders Taxis flank livery', art, emissive_of(art, gold_only), strength=1.4)
    parts = []
    for side in (-1, 1):          # side = sign of y
        u = ex if side < 0 else -ex   # text left->right as seen from that side
        parts.append(decal(S, [-0.06, side * 0.95, 0.664], u, ez, 0.84, 0.110, [0, -side, 0], nu=52, nv=8, max_jump=0.12))
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LIVERY_FLANK_WORDMARK', parts, mat_word, 'Vaders Taxis flank wordmark (render-only artwork)')
    amber = Material(name='VTX visual · amber door swoop', doubleSided=False, emissiveFactor=[1.0, 0.52, 0.03],
                     pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=[1.0, 0.55, 0.05, 1], metallicFactor=0.0, roughnessFactor=0.3))
    amber.extensions = {'KHR_materials_emissive_strength': {'emissiveStrength': 2.0}}
    glb.g.materials.append(amber)
    parts = []
    for side in (-1, 1):
        for p0, p1, p2, p3, wdt in DOOR_SWOOPS:
            parts.append(ribbon(S, _bezier(p0, p1, p2, p3, 70), side, wdt))
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LIVERY_DOOR_SWOOPS', parts, len(glb.g.materials) - 1, 'curved amber door swoops (render-only artwork)')
    # ---- V emblem: fins (outer faces) + bonnet
    em = v_emblem()
    mat_em = decal_material(glb, 'VTX visual · V emblem', em, emissive_of(em, gold_only), strength=1.6, metal=0.6, rough=0.25)
    parts = []
    sc_f = load_zup(surface_path, yup)
    for name in sc_f.graph.nodes_geometry:
        if 'ANGULAR_RAKED_V_TAIL' not in name:
            continue
        T, gn = sc_f.graph[name]
        m = sc_f.geometry[gn].copy(); m.apply_transform(T)
        parts.append(fin_emblem(m))
    parts.append(decal(S, [1.86, 0.0, 1.2], -ey, ex, 0.20, 0.20, [0, 0, -1], nu=16, nv=16, max_jump=0.08))
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LIVERY_V_EMBLEMS', parts, mat_em, 'V emblem on fins and bonnet (render-only artwork)')
    # ---- red LED tail lamps: bevelled bezel + recessed textured lens, on the flat rear panel only
    bez, lens = tail_lamps(S)
    glb.g.materials.append(Material(name='VTX visual · gloss black tail-lamp bezel', doubleSided=False,
                                    pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=[0.035, 0.035, 0.04, 1], metallicFactor=1.0, roughnessFactor=0.14)))
    glb.g.materials[-1].extensions = {'KHR_materials_clearcoat': {'clearcoatFactor': 1.0, 'clearcoatRoughnessFactor': 0.02}}
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LED_TAIL_LAMP_BEZELS', bez, len(glb.g.materials) - 1, 'tail-lamp bezels (render-only)')
    lt = led_lens()
    mat_lens = decal_material(glb, 'VTX visual · red LED tail-lamp lens', lt.convert('RGBA'), lt, strength=1.2, metal=0.0, rough=0.08)
    glb.g.materials[mat_lens].alphaMode = 'OPAQUE'
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LED_TAIL_LAMP_LENSES', lens, mat_lens, 'LED tail-lamp lenses (render-only)')
    # ---- white LED headlight blades
    hb = head_blade()
    mat_head = decal_material(glb, 'VTX visual · white LED headlight blade', hb, hb.convert('RGB'), strength=3.0, metal=0.0, rough=0.15, clearcoat=False)
    parts = []
    for side in (-1, 1):
        u = (ey * side)
        parts.append(decal(S, [2.2, side * 0.70, 0.58], u, ez, 0.42, 0.11, [-1, 0, 0], nu=24, nv=6, max_jump=0.10))
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LED_HEADLIGHTS', parts, mat_head, 'LED headlight graphic (render-only)')
    # ---- rivets along the feature creases of the painted shell
    sc = load_zup(surface_path, yup)
    panels = []
    for name in sc.graph.nodes_geometry:
        if not name.startswith(('PHANTOM_', 'A10_CANARD')) or 'VTX_VISUAL' in name:
            continue
        T, gn = sc.graph[name]
        m = sc.geometry[gn]
        mat = getattr(getattr(m, 'visual', None), 'material', None)
        if mat is None or not (mat.name or '').startswith(RIVET_MATS):
            continue
        mm = m.copy(); mm.apply_transform(T); panels.append(mm)
    P, N = rivet_sites(panels)
    stats['rivets'] = int(len(P))
    glb.g.materials.append(Material(name='VTX visual · dark Ti dome rivet', doubleSided=False,
                                    pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=[0.16, 0.17, 0.19, 1], metallicFactor=0.9, roughnessFactor=0.32)))
    rivet_mat = len(glb.g.materials) - 1
    if len(P):
        RP, RN, RI = rivet_mesh(P, N)
        add_node(glb, airframe_idx, world, 'VTX_VISUAL_PANEL_RIVETS', [(RP, RN, None, RI)], rivet_mat, f'{len(P)} dome rivets along panel creases (render-only)')
