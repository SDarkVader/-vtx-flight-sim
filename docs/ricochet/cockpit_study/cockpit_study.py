"""RC-01 cockpit enclosure study (concept stage: nothing here is adopted into the craft).

For each enclosure variant x pilot posture it writes an isolated study GLB = the unchanged Concept A airframe
+ that enclosure + a seat/console placed for that posture + a pilot manikin node, and measures:
  * pilot fit: each variant fixes only its silhouette and section SHAPE; its size is the smallest that clears
    the pilot's helmet, shoulders, torso and legs by CLEAR_M (checked in 3-D, signed, after building);
  * drag: mesh component build-up (vtx.ricochet.aero_buildup) of the whole airframe with this enclosure;
  * glazing / opaque-fairing area and mass for candidate glazing materials;
  * view over the nose from the pilot's eye and the angle at which the forward sightline meets the glazing;
  * pilot CG and the craft CG shift relative to the load-case pilot item (85 kg at (1.30, 0, 0.80)).
Human representation: one average adult pilot, 50th-percentile male body dimensions, 85 kg (the existing load-case
pilot mass). Body dimensions are PROVISIONAL (ANSUR-order values recalled, not yet checked against the ANSUR II
report NATICK/TR-15/007); helmet allowance and clearance are stated study assumptions.
Pilot seat placement is posture-driven, not chosen: the seat stays at the current back line (x = 1.03) unless the
pilot's shoulders/head would sit where the existing cockpit opening is too narrow, in which case it moves forward
the minimum needed. The hull, opening (sill) and everything outside the enclosure are unchanged.
Usage: python cockpit_study.py <worktree> <out_dir>
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

WT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WT / 'scratch' / 'cockpit_study'
sys.path.insert(0, str(WT / 'src'))
from vtx.ricochet import aero_buildup as ab  # noqa: E402
from vtx.ricochet import concept_a_builder as cab  # noqa: E402

PILOT = dict(sitting_height=0.915, eye_height_sitting=0.795, acromial_height_sitting=0.600, buttock_knee=0.616,
             knee_height_sitting=0.559, bideltoid=0.505, head_length=0.197, head_breadth=0.155, mass_kg=85.0,
             status='provisional 50th-percentile adult male (ANSUR-order, unverified)')
HELMET_M = 0.030
CLEAR_M = 0.050
SEAT_TOP_Z = 0.830          # existing seat pan top (0.790 + 0.040)
X_BACK_REF = 1.03           # existing seat-back line at the seat surface
ETA_MAX_FIT = 0.85          # pilot points above the sill must sit inside 85 % of the opening half-width
# back recline from vertical, thigh elevation: only the back recline varies, so the postures differ in one thing
POSTURES = {'upright_18': (18.0, 10.0), 'semi_35': (35.0, 10.0), 'reclined_50': (50.0, 10.0)}
NECK_FLEX_MAX_DEG = 25.0
GLAZING_T_M = 0.0055
GLAZING_DENSITY = {'stretched_acrylic': 1190.0, 'polycarbonate': 1200.0}
FAIRING_KG_M2 = 2.5         # opaque carbon/foam sandwich skin, provisional
LC_PILOT_REF = (1.30, 0.80)
CRAFT_MASS_KG = 958.29      # rc01-real-components-v1 profile total
X_AFT, X_FWD = -0.25, 2.85
COL_PILOT = (0.62, 0.36, 0.20, 1.0)
COL_HELMET = (0.80, 0.80, 0.78, 1.0)


def sill(x):
    w, zs, zc = cab._canopy_spine_and_sill(np.atleast_1d(np.asarray(x, dtype=float)))
    return w, zs, zc


def floor_z(x):
    x = np.atleast_1d(np.asarray(x, dtype=float))
    zk = np.where(x < -0.15, 0.045 + 0.365 * np.clip((-0.15 - x) / 1.60, 0, None) ** 1.10,
                  np.where(x <= 2.10, 0.0, 0.575 * np.clip((x - 2.10) / 1.25, 0, None) ** 1.75))
    zf = 0.745 + 0.135 * np.clip((x - 1.65) / 1.20, 0, None) ** 1.05
    _, zs, _ = sill(x)
    return np.minimum(np.maximum(zk + 0.34, zf), zs - 0.035)


# ----------------------------------------------------------------------------------------------- pilot
def pose(recline_deg: float, thigh_deg: float, x_back: float) -> dict:
    P = PILOT
    th = math.radians(recline_deg)
    d_t = np.array([-math.sin(th), math.cos(th)])
    f_t = np.array([math.cos(th), math.sin(th)])
    thh = math.radians(max(0.0, recline_deg - NECK_FLEX_MAX_DEG))
    d_h = np.array([-math.sin(thh), math.cos(thh)])
    f_h = np.array([math.cos(thh), math.sin(thh)])
    B = np.array([x_back, SEAT_TOP_Z])
    Bax = B + 0.10 * f_t                               # body axis ~0.10 forward of the seat-back line
    S = Bax + P['acromial_height_sitting'] * d_t
    V = S + (P['sitting_height'] - P['acromial_height_sitting']) * d_h
    C_head = V - 0.115 * d_h
    E = S + (P['eye_height_sitting'] - P['acromial_height_sitting']) * d_h + 0.08 * f_h
    H = Bax + 0.09 * d_t
    phi = math.radians(thigh_deg)
    L_t = P['buttock_knee'] - 0.15
    K = H + L_t * np.array([math.cos(phi), math.sin(phi)])
    L_s = P['knee_height_sitting'] - 0.13
    A = None
    ax = K[0] + 0.2
    for _ in range(40):  # heel on the cockpit floor (floor rises toward the bow)
        dz = K[1] - (float(floor_z(ax)[0]) + 0.08)
        if dz >= L_s:     # knee too high for the heel to reach the floor: feet on raised pedals
            A = K + L_s * np.array([math.sin(math.radians(15.0)), -math.cos(math.radians(15.0))])
            break
        ax_new = K[0] + math.sqrt(L_s * L_s - dz * dz)
        if abs(ax_new - ax) < 1e-7:
            break
        ax = ax_new
    if A is None:
        A = np.array([ax, float(floor_z(ax)[0]) + 0.08])
    T = A + 0.19 * np.array([math.cos(math.radians(35.0)), math.sin(math.radians(35.0))])
    G = H + np.array([0.40, 0.14])                     # stick grip
    return dict(recline_deg=recline_deg, thigh_deg=thigh_deg, x_back=x_back, B=B, S=S, V=V, C_head=C_head, E=E,
                H=H, K=K, A=A, T=T, G=G, d_t=d_t, f_t=f_t, d_h=d_h, f_h=f_h, theta_head=math.degrees(thh))


def _x3(p2, y=0.0):
    return np.array([p2[0], y, p2[1]])


def _ellipsoid(c, e1, e2, radii, color, mat, nu=18, nv=11):
    e1 = e1 / np.linalg.norm(e1)
    e2 = e2 - e1 * float(e2 @ e1)
    e2 = e2 / np.linalg.norm(e2)
    e3 = np.cross(e1, e2)
    a, b, cc = radii
    rings = []
    for t in np.linspace(-0.97, 0.97, nv):
        r = math.sqrt(1.0 - t * t)
        ph = np.linspace(0.0, 2 * math.pi, nu, endpoint=False)
        pts = c[None, :] + a * t * e1[None, :] + (b * r * np.cos(ph))[:, None] * e2[None, :] + (cc * r * np.sin(ph))[:, None] * e3[None, :]
        rings.append(pts)
    v, f = cab._loft_closed_rings(rings, close_ends=True)
    return v, f, np.tile(np.array(color, np.float32), (len(f), 1)), np.full(len(f), mat, np.int32)


def _segment(p0, p1, r_lat, r_dep, color, mat, side=np.array([0.0, 1.0, 0.0])):
    L = float(np.linalg.norm(p1 - p0))
    e1 = (p1 - p0) / L
    return _ellipsoid(0.5 * (p0 + p1), e1, side, (0.5 * L + 0.6 * min(r_lat, r_dep), r_lat, r_dep), color, mat)


def manikin(ps: dict) -> tuple[dict, dict]:
    """Return (display parts, envelope parts) as {name: (v, f, fc, fm)}; envelope excludes the arms/hands."""
    yl = PILOT['bideltoid'] / 2.0 - 0.065
    up = np.array([0.0, 1.0, 0.0])
    env, disp = {}, {}
    d_h3, f_h3 = _x3(ps['d_h']), _x3(ps['f_h'])
    env['head'] = _ellipsoid(_x3(ps['C_head']), d_h3, up, (0.115 + HELMET_M, PILOT['head_breadth'] / 2 + HELMET_M,
                                                            PILOT['head_length'] / 2 + HELMET_M), COL_HELMET, 5)
    env['torso'] = _segment(_x3(ps['H']), _x3(ps['S']) - 0.03 * _x3(ps['d_t']), 0.17, 0.11, COL_PILOT, 5)
    for sgn, nm in ((1, 'p'), (-1, 's')):
        env['shoulder_' + nm] = _ellipsoid(_x3(ps['S'], sgn * yl), np.array([1.0, 0, 0]), up, (0.065, 0.065, 0.065), COL_PILOT, 5)
        env['thigh_' + nm] = _segment(_x3(ps['H'], sgn * 0.09), _x3(ps['K'], sgn * 0.11), 0.075, 0.075, COL_PILOT, 5)
        env['shin_' + nm] = _segment(_x3(ps['K'], sgn * 0.11), _x3(ps['A'], sgn * 0.12), 0.055, 0.055, COL_PILOT, 5)
        env['foot_' + nm] = _segment(_x3(ps['A'], sgn * 0.12), _x3(ps['T'], sgn * 0.12), 0.045, 0.045, COL_PILOT, 5)
        hand = _x3(ps['G'], -0.03) if sgn < 0 else _x3(ps['H'] + np.array([0.30, 0.12]), 0.22)
        sh = _x3(ps['S'], sgn * yl)
        elbow = 0.5 * (sh + hand) + np.array([0.0, sgn * 0.05, -0.12])
        disp['uarm_' + nm] = _segment(sh, elbow, 0.045, 0.045, COL_PILOT, 5)
        disp['farm_' + nm] = _segment(elbow, hand, 0.04, 0.04, COL_PILOT, 5)
    disp.update(env)
    return disp, env


def pilot_cg(ps: dict) -> np.ndarray:
    yl = PILOT['bideltoid'] / 2.0 - 0.065
    S = ps['S']
    hand_r = ps['G']
    hand_l = ps['H'] + np.array([0.30, 0.12])
    el_r = 0.5 * (S + hand_r) + np.array([0.0, -0.12])
    el_l = 0.5 * (S + hand_l) + np.array([0.0, -0.12])
    segs = [(0.081, ps['C_head']), (0.497, 0.5 * (ps['H'] + S)),
            (0.028, 0.5 * (S + el_r)), (0.028, 0.5 * (S + el_l)), (0.022, 0.5 * (el_r + hand_r)), (0.022, 0.5 * (el_l + hand_l)),
            (0.100, ps['H'] + 0.433 * (ps['K'] - ps['H'])), (0.100, ps['H'] + 0.433 * (ps['K'] - ps['H'])),
            (0.061, 0.5 * (ps['K'] + ps['A'])), (0.061, 0.5 * (ps['K'] + ps['A']))]
    m = sum(s[0] for s in segs)
    _ = yl
    return sum(s[0] * s[1] for s in segs) / m


def place_pilot(recline_deg: float, thigh_deg: float) -> dict:
    for xb in np.arange(X_BACK_REF, 1.90, 0.01):
        ps = pose(recline_deg, thigh_deg, float(xb))
        _, env = manikin(ps)
        pts = np.vstack([p[0] for p in env.values()])
        w, zs, _ = sill(pts[:, 0])
        above = pts[:, 2] > zs - 0.02
        inside_x = (pts[:, 0] > X_AFT + 0.05) & (pts[:, 0] < X_FWD - 0.05)
        if np.any(above & ~inside_x):
            continue
        eta = (np.abs(pts[:, 1]) + CLEAR_M) / w
        if np.all(eta[above] <= ETA_MAX_FIT) and ps['T'][0] <= X_FWD - 0.10:
            ps['envelope_pts'] = pts
            return ps
    raise RuntimeError(f'no seat position fits the opening for recline {recline_deg}')


# ----------------------------------------------------------------------------------------------- variants
def g_super(n):
    return lambda eta: np.clip(1.0 - np.abs(eta) ** n, 0.0, 1.0) ** (1.0 / n)


def g_faceted(eta):
    e = np.abs(eta)
    return np.interp(e, [0.0, 0.42, 0.78, 1.0], [1.0, 1.0, 0.70, 0.0])


def g_bubble(eta):
    return np.clip(1.0 - np.asarray(eta) ** 2, 0.0, 1.0) ** 0.44


ETA_SMOOTH = np.cos(np.linspace(0.0, math.pi, 31))
ETA_FACET = np.array([1.0, 0.93, 0.86, 0.78, 0.72, 0.66, 0.60, 0.54, 0.48, 0.42, 0.28, 0.14, 0.0])
ETA_FACET = np.concatenate([ETA_FACET, -ETA_FACET[-2::-1]])


SIZING_GRID = {  # free position parameters searched (offsets from the pilot's head centre x) for the lowest clearing height
    'A_continuous': dict(x_pk=np.arange(-0.20, 0.95, 0.05)),
    'B_faceted': dict(rf=np.arange(0.30, 0.85, 0.05), ra=np.arange(0.20, 0.45, 0.05)),
    'C_hardtop': dict(rf=np.arange(0.30, 0.85, 0.05), ra=np.arange(0.20, 0.45, 0.05)),
}


def size_variant(key: str, ps: dict) -> tuple[dict, float, dict]:
    xv = float(ps['C_head'][0])
    best = None
    if key == 'A_continuous':
        cands = [dict(x_pk=xv + o) for o in SIZING_GRID[key]['x_pk']]
    else:
        cands = [dict(rf=a, ra=b) for a in SIZING_GRID[key]['rf'] for b in SIZING_GRID[key]['ra']]
    for c in cands:
        var = make_variant(key, xv, **c)
        amp = required_amplitude(var, ps['envelope_pts'])
        if best is None or amp < best[1] - 1e-9:
            best = (var, amp, c)
    var, amp, c = best
    env = manikin(ps)[1]
    for _ in range(30):
        cl = clearance(var, h_fn_for(var, amp), env)
        if min(cl.values()) >= CLEAR_M - 0.004:
            break
        amp *= 1.03
    return var, amp, {k: round(float(v), 3) for k, v in c.items()}


def make_variant(key: str, xv: float, x_pk: float | None = None, rf: float = 0.40, ra: float = 0.30) -> dict:
    L = X_FWD - X_AFT
    if key == 'A_continuous':
        p_pk = ((x_pk if x_pk is not None else xv) - X_AFT) / L
        al, be = 1.25, 1.25 * (1 - p_pk) / p_pk
        if be < 1.25:
            be, al = 1.25, 1.25 * p_pk / (1 - p_pk)

        def s(x):
            p = np.clip((np.asarray(x) - X_AFT) / L, 0.0, 1.0)
            return (p / p_pk) ** al * ((1 - p) / (1 - p_pk)) ** be

        def zone(x, eta):
            return np.where(x > xv - 0.22, 'glass', 'opaque')
        return dict(key=key, s=s, g=g_super(2.5), eta=ETA_SMOOTH, zone=zone, crease=34.0,
                    label='Continuous: one smooth line from the nose deck over the pilot into the aft deck; rounded section; '
                          'glazed forward, opaque aft fairing')
    if key == 'B_faceted':
        x_rf, x_ra = xv + rf, max(xv - ra, X_AFT + 0.15)

        def s(x):
            x = np.asarray(x, dtype=float)
            return np.where(x >= x_rf, (X_FWD - x) / (X_FWD - x_rf), np.where(x >= x_ra, 1.0, (x - X_AFT) / (x_ra - X_AFT)))

        def zone(x, eta):
            return np.where(x > x_ra + 0.02, 'glass', 'opaque')
        return dict(key=key, s=s, g=g_faceted, eta=ETA_FACET, zone=zone, crease=12.0, x_rf=x_rf, x_ra=x_ra,
                    label='Faceted: straight raked windscreen, flat roof, straight aft slope; chamfered polygon section '
                          'with crisp creases; glazed forward of the roof end, opaque aft')
    if key == 'C_hardtop':
        x_rf, x_ra = xv + rf, max(xv - ra, X_AFT + 0.15)

        def s(x):
            x = np.asarray(x, dtype=float)
            q = np.clip((X_FWD - x) / (X_FWD - x_rf), 0, 1)
            q2 = np.clip((x_ra - x) / (x_ra - X_AFT), 0, 1)
            roof = 1.0 - 0.04 * ((x_rf - x) / (x_rf - x_ra)) ** 2
            return np.where(x >= x_rf, 1.0 - (1.0 - q) ** 1.8, np.where(x >= x_ra, roof, 0.96 * (1.0 - q2) ** 1.4))

        def zone(x, eta):
            return np.where(x > x_rf, 'glass', np.where((x > x_ra) & (np.abs(eta) > 0.5), 'glass', 'opaque'))
        return dict(key=key, s=s, g=g_super(4.0), eta=ETA_SMOOTH, zone=zone, crease=34.0, x_rf=x_rf, x_ra=x_ra,
                    label='Hardtop: curved wrap windscreen, opaque roof panel with side glazing, fastback to the aft deck; '
                          'squarer rounded section')
    raise KeyError(key)


def reference_bubble() -> dict:
    def h_of_x(x):
        _, zs, zc = sill(x)
        return zc - zs
    return dict(key='REF_current_bubble', h_fn=h_of_x, g=g_bubble, eta=ETA_SMOOTH,
                zone=lambda x, eta: np.full(np.shape(x), 'glass'), crease=34.0, label='Current bubble canopy (reference)')


def h_fn_for(var: dict, amp: float):
    if 'h_fn' in var:
        return var['h_fn']
    return lambda x: np.maximum(0.012, amp * var['s'](x))


def required_amplitude(var: dict, pts: np.ndarray) -> float:
    w, zs, _ = sill(pts[:, 0])
    above = pts[:, 2] + CLEAR_M > zs
    eta = np.clip((np.abs(pts[:, 1]) + CLEAR_M) / w, 0.0, 0.999)
    g = var['g'](eta)
    h_need = (pts[:, 2] + CLEAR_M - zs) / np.maximum(g, 1e-3)
    s = var['s'](pts[:, 0])
    ok = above & (s > 1e-3)
    return float(np.max(h_need[ok] / s[ok])) if np.any(ok) else 0.0


def inner_surface(var: dict, h_fn, nx=420, ne=181):
    xs = X_AFT + (X_FWD - X_AFT) * (0.5 * (1 - np.cos(np.linspace(0, math.pi, nx))))
    eta = np.cos(np.linspace(0, math.pi, ne))
    w, zs, _ = sill(xs)
    h = h_fn(xs)
    X = np.repeat(xs, ne)
    E = np.tile(eta, nx)
    Y = E * np.repeat(w - GLAZING_T_M, ne)
    Z = np.repeat(zs, ne) + np.repeat(np.maximum(h - GLAZING_T_M, 0.006), ne) * var['g'](E)
    return np.column_stack([X, Y, Z])


def clearance(var: dict, h_fn, env: dict) -> dict:
    surf = inner_surface(var, h_fn)
    tree = cKDTree(surf)
    out = {}
    for name, (v, *_r) in env.items():
        w, zs, _ = sill(v[:, 0])
        above = v[:, 2] > zs
        if not np.any(above):
            continue
        p = v[above]
        w, zs = w[above], zs[above]
        eta = np.abs(p[:, 1]) / np.maximum(w - GLAZING_T_M, 1e-3)
        h = h_fn(p[:, 0])
        z_top = zs + np.maximum(h - GLAZING_T_M, 0.006) * var['g'](np.clip(eta, 0, 1))
        inside = (eta < 1.0) & (p[:, 2] < z_top) & (p[:, 0] > X_AFT) & (p[:, 0] < X_FWD)
        d, _i = tree.query(p)
        sd = np.where(inside, d, -d)
        part = name.split('_')[0]
        out[part] = round(min(out.get(part, 9.0), float(sd.min())), 4)
    return out


def enclosure_mesh(var: dict, h_fn, n_x=80):
    t = np.linspace(0, 1, n_x)
    xs = X_AFT + (X_FWD - X_AFT) * (0.5 * (1 - np.cos(math.pi * t)))
    w_all, zs_all, _ = sill(xs)
    h_all = h_fn(xs)
    eo = var['eta']
    rings = []
    for x, w, zs, h in zip(xs, w_all, zs_all, h_all):
        h = max(float(h), 0.012)
        zo = zs + h * var['g'](eo)
        ei = eo[::-1]
        zi = zs + max(h - GLAZING_T_M, 0.006) * var['g'](ei)
        rings.append(np.vstack([np.column_stack([np.full(len(eo), x), eo * w, zo]),
                                np.column_stack([np.full(len(ei), x), ei * max(w - GLAZING_T_M, 0.005), zi])]))
    v, f = cab._loft_closed_rings(rings, close_ends=True)
    # Zone per lofted quad (both triangles share it) so glass / fairing boundaries follow stations, not a zigzag
    n_e = len(eo)
    m = 2 * n_e
    eta_ring = np.concatenate([eo, eo[::-1]])
    k = np.arange(len(f))
    n_side = (n_x - 1) * m * 2
    strip = np.minimum(k // (2 * m), n_x - 2)
    jj = (k % (2 * m)) // 2
    qx = np.where(k < n_side, 0.5 * (xs[strip] + xs[strip + 1]), np.where((k - n_side) % 2 == 0, xs[0], xs[-1]))
    jc = np.where(k < n_side, jj, ((k - n_side) // 2) % m)
    qeta = 0.5 * (eta_ring[jc] + eta_ring[(jc + 1) % m])
    zone = var['zone'](qx, qeta)
    glass = zone == 'glass'
    fc = np.where(glass[:, None], np.array(cab.COL_GLASS, np.float32), np.array(cab.COL_CARBON, np.float32)).astype(np.float32)
    fm = np.where(glass, 3, 0).astype(np.int32)
    a = 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    areas = dict(glass_m2=round(float(a[glass].sum()) / 2.0, 3), opaque_m2=round(float(a[~glass].sum()) / 2.0, 3))
    return (v, f, fc, fm), areas


def interior(ps: dict):
    C = cab.COL_SEAT
    th = math.radians(ps['recline_deg'])
    phi_s = math.radians(ps['thigh_deg']) * 0.6
    B, Hh, K = ps['B'], ps['H'], ps['K']
    pan_c = B + 0.25 * np.array([math.cos(phi_s), math.sin(phi_s)]) - np.array([0.0, 0.04])
    back_c = B + 0.32 * ps['d_t'] - 0.05 * ps['f_t']
    head_c = ps['C_head'] - (PILOT['head_length'] / 2 + HELMET_M + 0.045) * ps['f_h']
    k_top = K[1] + 0.06
    con_x = K[0] + 0.06 + 0.14
    con_z = k_top + 0.10
    parts = [
        cab._add_box_part(pan_c[0], 0.0, pan_c[1], 0.25, 0.22, 0.04, C, 5, rot_y=-phi_s),
        cab._add_box_part(back_c[0], 0.0, back_c[1], 0.05, 0.21, 0.32, C, 5, rot_y=-th),
        cab._add_box_part(head_c[0], 0.0, head_c[1], 0.04, 0.12, 0.09, cab.COL_CARBON_DARK, 5, rot_y=-math.radians(ps['theta_head'])),
        cab._add_box_part(ps['G'][0] - 0.01, 0.0, 0.5 * (ps['G'][1] + float(floor_z(ps['G'][0])[0])), 0.02, 0.02,
                          0.5 * (ps['G'][1] - float(floor_z(ps['G'][0])[0])), cab.COL_CARBON_DARK, 5),
        cab._add_box_part(con_x, 0.0, con_z, 0.14, 0.26, 0.08, cab.COL_CARBON_DARK, 5, rot_y=0.25),
    ]
    avi = [cab._add_box_part(con_x - 0.13, sgn * 0.125, con_z + 0.005, 0.008, 0.10, 0.065, cab.COL_AVIONICS, 6, rot_y=0.25)
           for sgn in (1, -1)]
    c, s = math.cos(0.25), math.sin(0.25)   # _add_box_part rot_y: x' = c x + s z, z' = -s x + c z
    console_top = [(con_x + c * lx + s * 0.08, con_z - s * lx + c * 0.08) for lx in (-0.14, 0.14)]
    return cab._merge_disjoint_parts(parts), cab._merge_disjoint_parts(avi), console_top


def vision(ps: dict, var: dict, h_fn, console_top) -> dict:
    ex, ez = ps['E']
    obst = list(console_top)
    for x in np.linspace(2.85, 3.35, 26):
        xn = max(0.0, min(1.0, (3.35 - x) / 0.50))
        obst.append((x, 0.690 + 0.195 * xn ** 0.72))
    xs = np.linspace(ex + 0.05, X_FWD, 200)
    z_top = sill(xs)[1] + h_fn(xs)
    zone = var['zone'](xs, np.zeros_like(xs))
    for x, z, zn in zip(xs, z_top, zone):
        if zn != 'glass':
            obst.append((x, z))
    # only obstructions below the eye line limit the view down over the nose
    ang = max(math.degrees(math.atan2(z - ez, x - ex)) for x, z in obst if x > ex + 0.05 and z < ez)
    cross = np.where(z_top < ez)[0]
    eye_outside = float(sill(ex)[1][0] + h_fn(np.array([ex]))[0]) < ez
    if eye_outside:
        return dict(eye_xz=[round(ex, 3), round(ez, 3)], over_nose_down_view_deg=round(-ang, 1),
                    sightline_meets_glass_at_x=None, sightline_to_glass_angle_deg=None, eye_above_enclosure=True)
    if len(cross):
        i = int(cross[0])
        sl = (z_top[i] - z_top[max(i - 1, 0)]) / max(xs[i] - xs[max(i - 1, 0)], 1e-6)
        x_cross, glass_ang = float(xs[i]), math.degrees(math.atan(abs(sl)))
    else:
        x_cross, glass_ang = None, None
    return dict(eye_xz=[round(ex, 3), round(ez, 3)], over_nose_down_view_deg=round(-ang, 1),
                sightline_meets_glass_at_x=None if x_cross is None else round(x_cross, 2),
                sightline_to_glass_angle_deg=None if glass_ang is None else round(glass_ang, 1))


# ----------------------------------------------------------------------------------------------- assembly
def base_parts():
    ref_glb = OUT / '_reference_rebuild.glb'
    info = cab.build_concept_a_glb(ref_glb)
    same = ref_glb.read_bytes() == (WT / 'public' / 'assets' / 'ricochet-concept-a.glb').read_bytes()
    u = info['underwater_fullness']
    hull = cab.build_pass3_hull_and_cabin(underwater_fullness=u)
    spp, sps = cab.build_pass3_sponson(+1), cab.build_pass3_sponson(-1)
    rotor_p, spinner_p = cab.build_pass3_fan_rotor_and_spinner()
    rotor_s, spinner_s = cab.build_pass3_fan_rotor_and_spinner()
    S = cab.SPONSON_MOUNT_CONCEPT_A_VTX
    F = cab.FAN_CENTER_PORT_VTX
    nodes = [
        ('Ricochet_ConceptA_Hull_Cabin', (0.0, 0.0, 0.0), hull),
        ('Ricochet_Sponson_Port', S, spp),
        ('Ricochet_Sponson_Stbd', (S[0], -S[1], S[2]), sps),
        ('Ricochet_Wing_Port', (0.0, 0.0, 0.0), cab.build_pass3_wing(+1)),
        ('Ricochet_Wing_Stbd', (0.0, 0.0, 0.0), cab.build_pass3_wing(-1)),
        ('Ricochet_Aileron_Port', cab.AILERON_HINGE_PORT_VTX, cab.build_pass3_aileron(+1)),
        ('Ricochet_Aileron_Stbd', cab.AILERON_HINGE_STBD_VTX, cab.build_pass3_aileron(-1)),
        ('Ricochet_Winglet_Port', (0.0, 0.0, 0.0), cab.build_pass3_winglet(+1)),
        ('Ricochet_Winglet_Stbd', (0.0, 0.0, 0.0), cab.build_pass3_winglet(-1)),
        ('Ricochet_Strut_Port', (0.0, 0.0, 0.0), cab.build_pass3_strut(+1)),
        ('Ricochet_Strut_Stbd', (0.0, 0.0, 0.0), cab.build_pass3_strut(-1)),
        ('Ricochet_Tail_Pylon_T_Tail', (0.0, 0.0, 0.0), cab.build_pass3_tail_pylon_t_tail()),
        ('Ricochet_Elevator', cab.ELEVATOR_HINGE_VTX, cab.build_pass3_elevator()),
        ('Ricochet_Rudder', cab.RUDDER_HINGE_VTX, cab.build_pass3_rudder()),
        ('Ricochet_Duct_Port', (0.0, 0.0, 0.0), cab.build_pass3_duct(+1)),
        ('Ricochet_Duct_Stbd', (0.0, 0.0, 0.0), cab.build_pass3_duct(-1)),
        ('Ricochet_Reverse_Bucket_Port', cab.REVERSE_BUCKET_HINGE_PORT_VTX, cab.build_pass3_reverse_bucket(+1)),
        ('Ricochet_Reverse_Bucket_Stbd', cab.REVERSE_BUCKET_HINGE_STBD_VTX, cab.build_pass3_reverse_bucket(-1)),
        ('Ricochet_Fan_Rotor_Port', F, rotor_p),
        ('Ricochet_Fan_Rotor_Stbd', (F[0], -F[1], F[2]), rotor_s),
        ('Ricochet_Fan_Spinner_Port', F, spinner_p),
        ('Ricochet_Fan_Spinner_Stbd', (F[0], -F[1], F[2]), spinner_s),
    ]
    ser = [{'name': n, 'offset_vtx': o, 'prims': cab._split_sharp_and_color_seams(*m, crease_deg=34.0)} for n, o, m in nodes]
    return ser, dict(underwater_fullness=u, rebuild_identical_to_public_glb=same)


def write_glb(path, base_ser, canopy, crease, inter, avi, pilot_parts):
    cab._check_watertight(canopy[0], canopy[1], 'study enclosure')
    nodes = list(base_ser)
    nodes.append({'name': 'Ricochet_Canopy_Glass', 'offset_vtx': (0.0, 0.0, 0.0),
                  'prims': cab._split_sharp_and_color_seams(*canopy, crease_deg=crease)})
    nodes.append({'name': 'Ricochet_Cockpit_Interior', 'offset_vtx': (0.0, 0.0, 0.0), 'prims': cab._split_sharp_and_color_seams(*inter)})
    nodes.append({'name': 'Ricochet_Avionics_Display', 'offset_vtx': (0.0, 0.0, 0.0), 'prims': cab._split_sharp_and_color_seams(*avi)})
    nodes.append({'name': 'Study_Pilot_Manikin', 'offset_vtx': (0.0, 0.0, 0.0),
                  'prims': cab._split_sharp_and_color_seams(*cab._merge_disjoint_parts(list(pilot_parts.values())))})
    cab._export_concept_a_glb(nodes, path)


def sill_wz(x):
    w, zs, _ = sill(x)
    return w, zs


def evaluate(case_id, var, ps, amp, base_ser, posture_key):
    h_fn = h_fn_for(var, amp)
    disp, env = manikin(ps)
    canopy, areas = enclosure_mesh(var, h_fn)
    inter, avi, console_top = interior(ps)
    glb = OUT / f'{case_id}.glb'
    write_glb(glb, base_ser, canopy, var['crease'], inter, avi, disp)
    xs = np.linspace(X_AFT, X_FWD, 400)
    h = h_fn(xs)
    zs = sill(xs)[1]
    i_pk = int(np.argmax(zs + h))
    bu = ab.build_up(glb, 30.0, canopy_sill=sill_wz)
    can = bu['components']['Ricochet_Canopy_Glass']
    cg = pilot_cg(ps)
    rec = dict(
        case=case_id, variant=var['key'], label=var['label'], posture=posture_key,
        seat_back_x=round(ps['x_back'], 3), seat_moved_fwd_m=round(ps['x_back'] - X_BACK_REF, 3),
        head_top_z=round(float(ps['V'][1]), 3), head_x=round(float(ps['C_head'][0]), 3),
        enclosure_peak_z=round(float(zs[i_pk] + h[i_pk]), 3), enclosure_peak_x=round(float(xs[i_pk]), 3),
        height_above_sill_at_peak=round(float(h[i_pk]), 3), max_height_above_sill=round(float(h.max()), 3),
        clearance_m=clearance(var, h_fn, env),
        glazing_m2=areas['glass_m2'], opaque_fairing_m2=areas['opaque_m2'],
        glazing_mass_kg={k: round(areas['glass_m2'] * GLAZING_T_M * rho, 1) for k, rho in GLAZING_DENSITY.items()},
        fairing_mass_kg=round(areas['opaque_m2'] * FAIRING_KG_M2, 1),
        canopy_frontal_excess_m2=can['frontal_excess_m2'], canopy_fineness=can['fineness'], canopy_rake_deg=can['rake_deg'],
        canopy_cd_frontal=can['cd_frontal'], canopy_CdA_m2=can['CdA_m2'], craft_CdA_parasite_m2=bu['CdA_parasite_m2'],
        craft_Cd0=bu['Cd0_on_S_ref'], drag_30mps_n=bu['drag_n_at_speed'],
        vision=vision(ps, var, h_fn, console_top),
        pilot_cg_xz=[round(float(cg[0]), 3), round(float(cg[1]), 3)],
        craft_cg_shift_vs_load_case_m=[round(PILOT['mass_kg'] * (float(cg[0]) - LC_PILOT_REF[0]) / CRAFT_MASS_KG, 4),
                                       round(PILOT['mass_kg'] * (float(cg[1]) - LC_PILOT_REF[1]) / CRAFT_MASS_KG, 4)],
        glb=str(glb.relative_to(WT)).replace('\\', '/'),
    )
    rec['enclosure_mass_kg_acrylic'] = round(rec['glazing_mass_kg']['stretched_acrylic'] + rec['fairing_mass_kg'], 1)
    return rec


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    base_ser, base_info = base_parts()
    results = []
    # Reference: current bubble with the average pilot in the current seat (upright 18 deg, back line 1.03)
    ps_ref = pose(18.0, 10.0, X_BACK_REF)
    ref = reference_bubble()
    results.append(evaluate('REF_current_bubble__upright_18', ref, ps_ref, 0.0, base_ser, 'upright_18'))
    print(json.dumps({k: results[-1][k] for k in ('case', 'clearance_m', 'canopy_CdA_m2', 'craft_CdA_parasite_m2')}), flush=True)
    for pk, (rec_deg, th_deg) in POSTURES.items():
        ps = place_pilot(rec_deg, th_deg)
        for vk in ('A_continuous', 'B_faceted', 'C_hardtop'):
            var, amp, sizing = size_variant(vk, ps)
            rec = evaluate(f'{vk}__{pk}', var, ps, amp, base_ser, pk)
            rec['amplitude_m'] = round(amp, 4)
            rec['sizing_params'] = sizing
            results.append(rec)
            print(json.dumps({k: rec[k] for k in ('case', 'seat_back_x', 'max_height_above_sill', 'enclosure_peak_z', 'clearance_m',
                                                  'canopy_CdA_m2', 'craft_CdA_parasite_m2', 'glazing_m2', 'opaque_fairing_m2')}), flush=True)
    meta = dict(method=__doc__, pilot=PILOT, helmet_allowance_m=HELMET_M, clearance_m=CLEAR_M, eta_max_fit=ETA_MAX_FIT,
                glazing_thickness_m=GLAZING_T_M, glazing_density=GLAZING_DENSITY, fairing_kg_m2=FAIRING_KG_M2,
                load_case_pilot_ref_xz=LC_PILOT_REF, craft_mass_kg=CRAFT_MASS_KG, base=base_info,
                wall_s=round(time.time() - t0, 1))
    (OUT / 'cockpit_study.json').write_text(json.dumps(dict(meta=meta, results=results), indent=1, default=str), encoding='utf-8')
    print('done', meta['base'], meta['wall_s'])


if __name__ == '__main__':
    main()
