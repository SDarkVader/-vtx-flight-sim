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
    """Original angular V: faceted gold chevron with a dark inner cut and a bevel highlight."""
    S = size * 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = S / 100.0
    outer = [(4, 14), (36, 14), (50, 58), (64, 14), (96, 14), (58, 90), (42, 90)]
    inner = [(20, 22), (32, 22), (50, 72), (68, 22), (80, 22), (55, 82), (45, 82)]
    wing_l = [(4, 14), (14, 6), (40, 6), (36, 14)]
    wing_r = [(96, 14), (86, 6), (60, 6), (64, 14)]
    P = lambda pts: [(x * s, y * s) for x, y in pts]
    d.polygon(P(outer), fill=GOLD + (255,))
    d.polygon(P(wing_l), fill=(255, 205, 90, 255))
    d.polygon(P(wing_r), fill=(255, 205, 90, 255))
    d.polygon(P(inner), fill=(18, 18, 22, 255))
    d.polygon(P([(45, 82), (55, 82), (50, 72)]), fill=GOLD + (255,))
    d.line(P([(4, 14), (42, 90)]), fill=(255, 226, 150, 255), width=int(1.2 * s))
    im = im.resize((size, size), Image.LANCZOS)
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(size / 60))
    base = Image.new('RGBA', im.size, (0, 0, 0, 0))
    base.putalpha(glow.point(lambda a: a * 0.35))
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
        d.polygon(pts, fill=(255, 30, 20, 255))
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(6))
    base = Image.new('RGBA', im.size, (255, 20, 10, 0)); base.putalpha(glow.point(lambda a: a * 0.6))
    return Image.alpha_composite(base, im)


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
    # keep the emblem inside the face: shrink toward the face's centroid, then sit it a little low on the fin
    pts = m.vertices[np.unique(m.faces[sel])] - c
    span_u, span_v = np.ptp(pts @ right), np.ptp(pts @ up)
    sz = min(size, 0.42 * span_u, 0.42 * span_v)
    c = c - up * 0.10 * span_v + n * lift
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


def apply_livery(glb, surface_path, airframe_idx, world, stats, yup=False):
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
    # ---- red LED tail chevrons
    tl = tail_chevron()
    mat_tail = decal_material(glb, 'VTX visual · red LED tail chevron', tl, tl.convert('RGB'), strength=3.0, metal=0.0, rough=0.2, clearcoat=False)
    add_node(glb, airframe_idx, world, 'VTX_VISUAL_LED_TAIL_CHEVRON',
             [decal(S, [-2.3, 0.0, 0.80], -ey, ez, 1.5, 0.30, [1, 0, 0], nu=60, nv=12, max_jump=0.12)], mat_tail, 'LED tail lamp graphic (render-only)')
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
