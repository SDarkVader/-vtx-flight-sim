"""Pass 3 Precision CAD/GLB Generator for VTX Ricochet RC-01 Concept A.

Generates a manifold-watertight, hydrostatically calibrated, multi-material,
crisp-livery glTF Binary (public/assets/ricochet-concept-a.glb):
- Deep-V / semi-elliptical Pass 3 hull scaled so LC-03 (900 kg) sits at
  target T = 0.560 m draft (not floating high at 0.31 m) and LC-04 (1050 kg)
  sits around 0.615 m, with V_watertight > 3.5 m^3 (> 1.8 m^3 spec)
- Sponsons mounted at (-0.34, +/-3.80, 0.48) with bottom keel at z_body = 0.36 m,
  putting both side stabilisers cleanly ~0.20 m underwater at calm 0.56 m waterline
- Streamlined aerodynamic ogive nose tip + continuous C2 compound-curved
  3.30 m teardrop polycarbonate canopy (zero flat vertical brick walls)
- Zero-pinch tail pylon-to-duct junction (horizontal cross-arm terminates cleanly
  inside shroud barrel wall |y| <= 0.285 m, clear of Ø0.90 m airflow throat)
- 4-vane nacelle motor stators + clean 9-blade twisted NACA airfoil rotor
- Crisp painted VTX Gold (#f4b41a) trim bands & flush inlaid 'VTX' bow emblem
  with split vertices at every color seam & hard crease (zero vertex-color smear)
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from typing import Any

import numpy as np

from vtx.ricochet.spec_math import (
    RC01_DESIGN_MASS_KG,
    RC01_MAX_STUDY_MASS_KG,
    canopy_and_craft_cd0,
    evaluate_mesh_curve_stability,
)
from vtx.water.datum import RHO_FRESHWATER_15C
from vtx.water.hydrodynamics import _clip_submerged_triangles, _submerged_volume_and_centroid

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONCEPT_A_OUT = _REPO_ROOT / 'public' / 'assets' / 'ricochet-concept-a.glb'

# Linear RGBA colors for glTF COLOR_0 & materials
COL_CARBON = (0.045, 0.052, 0.068, 1.0)      # Deep satin carbon charcoal (#1c2028 sRGB)
COL_CARBON_DARK = (0.025, 0.028, 0.036, 1.0) # Dark matte cockpit tub / trim (#13151a sRGB)
COL_GOLD = (0.910, 0.460, 0.012, 1.0)        # Crisp VTX Racing Gold (#f4b41a sRGB in linear)
COL_TITANIUM = (0.360, 0.400, 0.455, 1.0)    # Brushed Grade-5 Ti-6Al-4V (#a1aab5 sRGB)
COL_ROTOR = (0.145, 0.165, 0.200, 1.0)       # Anodized forged fan blades
COL_GLASS = (0.140, 0.300, 0.420, 0.38)      # Smoke-blue tinted Lexan MR10
COL_SEAT = (0.055, 0.062, 0.075, 1.0)        # Alcantara cockpit seat
COL_AVIONICS = (0.050, 0.720, 0.880, 1.0)    # Dual MFD cyan-blue glow

SPONSON_MOUNT_CONCEPT_A_VTX = (-0.34, 3.80, 0.48)
FAN_CENTER_PORT_VTX = (-2.05, 0.78, 1.56)

def _unit_vec(v: tuple[float, float, float] | np.ndarray) -> tuple[float, float, float]:
    arr = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(arr))
    u = arr / max(1e-12, n)
    return (float(u[0]), float(u[1]), float(u[2]))

# Exact 3D hinge pivots (VTX frame) and unit hinge axes for articulated Concept A control surfaces.
# Wing geometry over |y| in [0.52, 4.64]: t=(y-0.52)/4.12, chord=2.02*(1-0.45*t), x_le=1.15-1.07*t, z=0.875+0.255*t
# At 73% chord hinge line from |y|=2.10 to |y|=4.24:
_AIL_P0 = np.array([1.15 - 1.07 * ((2.10 - 0.52) / 4.12) - 0.73 * 2.02 * (1.0 - 0.45 * ((2.10 - 0.52) / 4.12)), 2.10, 0.875 + 0.255 * ((2.10 - 0.52) / 4.12)])
_AIL_P1 = np.array([1.15 - 1.07 * ((4.24 - 0.52) / 4.12) - 0.73 * 2.02 * (1.0 - 0.45 * ((4.24 - 0.52) / 4.12)), 4.24, 0.875 + 0.255 * ((4.24 - 0.52) / 4.12)])
_AIL_MID_P = 0.5 * (_AIL_P0 + _AIL_P1)
AILERON_HINGE_PORT_VTX = (float(_AIL_MID_P[0]), float(_AIL_MID_P[1]), float(_AIL_MID_P[2]))
AILERON_HINGE_STBD_VTX = (float(_AIL_MID_P[0]), float(-_AIL_MID_P[1]), float(_AIL_MID_P[2]))
# Both axes point generally +Y (port-ward) so +q rotates trailing edge UP (+Z) and -q rotates TE DOWN (-Z).
AILERON_AXIS_PORT = _unit_vec(_AIL_P1 - _AIL_P0)
AILERON_AXIS_STBD = _unit_vec(np.array([-(_AIL_P1[0] - _AIL_P0[0]), +(_AIL_P1[1] - _AIL_P0[1]), -(_AIL_P1[2] - _AIL_P0[2])]))

ELEVATOR_HINGE_VTX = (-3.14, 0.0, 2.302)
ELEVATOR_AXIS = (0.0, 1.0, 0.0)  # +q moves TE up (-M_y = nose up pitch)

_RUD_P0 = np.array([-2.12, 0.0, 0.96])
_RUD_P1 = np.array([-3.06, 0.0, 2.20])
_RUD_MID = 0.5 * (_RUD_P0 + _RUD_P1)
RUDDER_HINGE_VTX = (float(_RUD_MID[0]), 0.0, float(_RUD_MID[2]))
# Point axis downward along hinge post (-s) so +q swings TE toward +Y (port) -> +M_z (left yaw).
RUDDER_AXIS = _unit_vec(_RUD_P0 - _RUD_P1)

REVERSE_BUCKET_HINGE_PORT_VTX = (-2.33, 0.78, 1.56)
REVERSE_BUCKET_HINGE_STBD_VTX = (-2.33, -0.78, 1.56)
REVERSE_BUCKET_AXIS = (0.0, -1.0, 0.0)  # +q in [0, 85 deg] swings stowed upper deflector bucket DOWN across jet exit


# ---------------------------------------------------------------------------
# Low-level Watertight Manifold & Sharp-Seam Visual Builders
# ---------------------------------------------------------------------------
def _vtx_to_gltf(verts: np.ndarray) -> np.ndarray:
    """Convert VTX (+X fwd, +Y port, +Z up) -> glTF (+X fwd, +Y up, -Z port)."""
    v = np.asarray(verts, dtype=np.float32)
    return np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1)


def _check_watertight(verts: np.ndarray, faces: np.ndarray, label: str) -> float:
    """Verify exact closed oriented 2-manifoldness after welding vertices at 1e-5."""
    _, inv = np.unique(np.round(verts, 5), axis=0, return_inverse=True)
    wf = inv[faces]
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    if np.any(areas < 1e-10):
        raise ValueError(f'{label}: has {(areas < 1e-10).sum()} degenerate triangles')
    edges = np.vstack([wf[:, [0, 1]], wf[:, [1, 2]], wf[:, [2, 0]]])
    directed = {(int(a), int(b)) for a, b in edges}
    if len(directed) != edges.shape[0]:
        raise ValueError(f'{label}: NOT oriented 2-manifold (duplicate directed edges={edges.shape[0] - len(directed)})')
    unmatched = sum(1 for a, b in directed if (b, a) not in directed)
    if unmatched != 0:
        raise ValueError(f'{label}: NOT watertight manifold (unmatched directed edges={unmatched})')
    vol = float(np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0)
    if vol < 0:
        raise ValueError(f'{label}: negative signed volume ({vol:.5f}), inverted winding')
    return vol


def _split_sharp_and_color_seams(
    verts: np.ndarray,
    faces: np.ndarray,
    face_colors: np.ndarray,
    face_mats: np.ndarray,
    uvs: np.ndarray | None = None,
    crease_deg: float = 34.0,
) -> list[dict[str, Any]]:
    """Convert welded manifold mesh into crisp multi-primitive visual buffers with ZERO paint bleed or edge blur.

    Returns a list of glTF primitive dicts partitioned by material index.
    All vertices within each face cluster have consistent smooth normals within `crease_deg`
    and identical material/color group — guaranteeing razor-sharp paint borders & chine creases
    while the welded coordinates remain 100% geometrically identical for MuJoCo pinning.
    """
    cos_thresh = math.cos(math.radians(crease_deg))
    n_faces = faces.shape[0]
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    fnorm = np.cross(v1 - v0, v2 - v0)
    flens = np.linalg.norm(fnorm, axis=1, keepdims=True)
    fnorm = fnorm / np.maximum(flens, 1e-12)

    # Weld topology to find adjacent face neighbors per original position
    _, inv = np.unique(np.round(verts, 5), axis=0, return_inverse=True)
    wfaces = inv[faces]
    vert_to_faces: dict[int, list[int]] = {}
    for fi in range(n_faces):
        for k in range(3):
            vert_to_faces.setdefault(int(wfaces[fi, k]), []).append(fi)

    # Build unshared face-corners grouped by material, merging ONLY smooth same-color same-mat neighbors
    prims_out: list[dict[str, Any]] = []
    unique_mats = sorted(set(int(m) for m in face_mats))

    for mat_id in unique_mats:
        out_pos = []
        out_norm = []
        out_col = []
        out_uv = []
        out_idx = []
        cache: dict[tuple[int, int, tuple[float, float, float], tuple[int, int, int]], int] = {}

        face_indices = np.where(face_mats == mat_id)[0]
        for fi in face_indices:
            n_f = fnorm[fi]
            c_f = face_colors[fi]
            c_key = (int(round(c_f[0] * 1000)), int(round(c_f[1] * 1000)), int(round(c_f[2] * 1000)))
            tri_idx = []
            for corner in range(3):
                vi_orig = int(faces[fi, corner])
                wi = int(wfaces[fi, corner])
                # Average normals of neighbor faces that share same welded vertex, same mat & color, and angle <= crease_deg
                acc_n = np.zeros(3, dtype=np.float64)
                for nfi in vert_to_faces[wi]:
                    if int(face_mats[nfi]) != mat_id:
                        continue
                    c_n = face_colors[nfi]
                    if np.max(np.abs(c_n[:3] - c_f[:3])) > 0.04:
                        continue
                    if float(np.dot(fnorm[nfi], n_f)) >= cos_thresh:
                        acc_n += fnorm[nfi]
                n_len = float(np.linalg.norm(acc_n))
                smooth_n = acc_n / n_len if n_len > 1e-10 else n_f
                # Quantize normal key slightly so truly smooth surfaces share vertices cleanly!
                n_key = (int(round(smooth_n[0] * 250)), int(round(smooth_n[1] * 250)), int(round(smooth_n[2] * 250)))
                uv_val = uvs[vi_orig] if uvs is not None else np.array([0.0, 0.0], dtype=np.float32)
                uv_key = (int(round(float(uv_val[0]) * 500)), int(round(float(uv_val[1]) * 500)))
                key = (wi, mat_id, c_key, n_key, uv_key)
                if key not in cache:
                    cache[key] = len(out_pos)
                    out_pos.append(verts[vi_orig])
                    out_norm.append(smooth_n)
                    out_col.append(c_f)
                    out_uv.append(uv_val)
                tri_idx.append(cache[key])
            out_idx.append(tri_idx)

        prims_out.append({
            'material': mat_id,
            'pos': np.asarray(out_pos, dtype=np.float32),
            'norm': np.asarray(out_norm, dtype=np.float32),
            'col': np.asarray(out_col, dtype=np.float32),
            'uv': np.asarray(out_uv, dtype=np.float32),
            'idx': np.asarray(out_idx, dtype=np.uint32).reshape(-1),
        })
    return prims_out


def _loft_closed_rings(rings: list[np.ndarray], close_ends: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Loft a sequence of closed rings (each shape (M, 3)) with consistent outward CC-winding and end caps."""
    n_rings = len(rings)
    m = rings[0].shape[0]
    verts = np.vstack(rings).astype(np.float64)
    faces = []
    for i in range(n_rings - 1):
        b0 = i * m
        b1 = (i + 1) * m
        for j in range(m):
            jn = (j + 1) % m
            faces.append([b0 + j, b1 + j, b1 + jn])
            faces.append([b0 + j, b1 + jn, b0 + jn])
    if close_ends:
        c0 = np.mean(rings[0], axis=0)
        c1 = np.mean(rings[-1], axis=0)
        i_c0 = verts.shape[0]
        i_c1 = i_c0 + 1
        verts = np.vstack([verts, c0[None, :], c1[None, :]])
        b_last = (n_rings - 1) * m
        for j in range(m):
            jn = (j + 1) % m
            faces.append([i_c0, j, jn])
            faces.append([i_c1, b_last + jn, b_last + j])
    faces_arr = np.asarray(faces, dtype=np.int32)
    # Orient outward if signed volume is negative
    v0, v1, v2 = verts[faces_arr[:, 0]], verts[faces_arr[:, 1]], verts[faces_arr[:, 2]]
    vol = float(np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0)
    if vol < 0:
        faces_arr = faces_arr[:, [0, 2, 1]]
    return verts, faces_arr


def _merge_disjoint_parts(parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Concatenate multiple watertight sub-parts (verts, faces, face_colors, face_mats) into one node."""
    vs, fs, fcs, fms = [], [], [], []
    off = 0
    for v, f, fc, fm in parts:
        vs.append(v)
        fs.append(f + off)
        fcs.append(fc)
        fms.append(fm)
        off += v.shape[0]
    return np.vstack(vs), np.vstack(fs), np.vstack(fcs), np.concatenate(fms)


def _naca_4digit(x_frac: np.ndarray, thickness: float = 0.14, camber: float = 0.02, p_cam: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    """Return upper & lower Z/chord offsets for NACA 4-digit airfoil over x_frac in [0, 1]."""
    xc = np.clip(x_frac, 0.0, 1.0)
    yt = 5.0 * thickness * (
        0.2969 * np.sqrt(xc)
        - 0.1260 * xc
        - 0.3516 * (xc ** 2)
        + 0.2843 * (xc ** 3)
        - 0.1036 * (xc ** 4) # sharp/closed trailing edge!
    )
    yc = np.zeros_like(xc)
    dyc = np.zeros_like(xc)
    if abs(camber) > 1e-6:
        m1 = xc < p_cam
        m2 = ~m1
        yc[m1] = (camber / (p_cam ** 2)) * (2.0 * p_cam * xc[m1] - xc[m1] ** 2)
        dyc[m1] = (2.0 * camber / (p_cam ** 2)) * (p_cam - xc[m1])
        yc[m2] = (camber / ((1.0 - p_cam) ** 2)) * ((1.0 - 2.0 * p_cam) + 2.0 * p_cam * xc[m2] - xc[m2] ** 2)
        dyc[m2] = (2.0 * camber / ((1.0 - p_cam) ** 2)) * (p_cam - xc[m2])
    theta = np.arctan(dyc)
    zu = yc + yt * np.cos(theta)
    zl = yc - yt * np.cos(theta)
    return zu, zl


def _add_box_part(cx: float, cy: float, cz: float, hx: float, hy: float, hz: float, color: tuple, mat_id: int, rot_y: float = 0.0, rot_z: float = 0.0):
    """Create a closed watertight oriented box mesh."""
    pts = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy,  hz], [hx, -hy,  hz], [hx, hy,  hz], [-hx, hy,  hz],
    ], dtype=np.float64)
    if abs(rot_y) > 1e-9:
        c, s = math.cos(rot_y), math.sin(rot_y)
        ry = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        pts = pts @ ry.T
    if abs(rot_z) > 1e-9:
        c, s = math.cos(rot_z), math.sin(rot_z)
        rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        pts = pts @ rz.T
    pts += np.array([cx, cy, cz])
    faces = np.array([
        [0, 3, 2], [0, 2, 1],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5],
        [3, 0, 4], [3, 4, 7],
    ], dtype=np.int32)
    fc = np.tile(np.array(color, dtype=np.float32), (len(faces), 1))
    fm = np.full(len(faces), mat_id, dtype=np.int32)
    return pts, faces, fc, fm


# ---------------------------------------------------------------------------
# Parametric Hull + Sponson + Canopy + Wing + Pylon + Duct Builders
# ---------------------------------------------------------------------------
def _canopy_spine_and_sill(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return smooth C2 canopy sill width w(x), sill z_sill(x), and crown height z_crown(x) over x in [-0.25, 2.85]."""
    x_aft, x_fwd = -0.25, 2.85
    u = np.clip((x_fwd - x) / (x_fwd - x_aft), 0.0, 1.0)  # u=0 at sleek nose toe (+2.85), u=1 at rear spine (-0.25)
    # Teardrop planform half-width: sleek pointed front entry, max shoulder width 0.45 m around u=0.52, tapers smoothly aft
    w_sill = 0.45 * (np.sin(math.pi * (u ** 0.82)) ** 0.78) * (1.0 - 0.16 * u)
    w_sill = np.maximum(w_sill, 0.030)
    # High watertight cockpit coaming sill z(x): +0.32m dry freeboard above calm 0.56m WL -> turtledeck (+1.095m @ -0.25)
    z_sill = 0.885 + 0.210 * (u ** 1.12) - 0.025 * np.sin(math.pi * u)
    # Teardrop bubble dome spine height: sleek ~22-deg rake at nose -> ~1.61m crown peak -> smooth aft spine merge
    bump = np.sin(math.pi * (u ** 0.72)) ** 1.08
    z_crown = z_sill + 0.015 + 0.655 * bump
    return w_sill, z_sill, z_crown


def build_pass3_hull_and_cabin(underwater_fullness: float = 0.74) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build streamlined Pass 3 deep-V waterproof hull + dry cockpit well + aerodynamic nose + crisp VTX livery.

    Coordinates are in VTX frame (+X fwd, +Y port, +Z up).
    Hull spans x in [-1.75, +3.35] (nose tip @ +3.35; tail extends to -3.45 -> 6.80 m total length).
    At z_WL = 0.56 m, `underwater_fullness` tunes the deep-V deadrise concavity so:
    - T_design (900 kg) == 0.560 m, LCB_x aligned near CG_x (+0.48..0.52 m)
    - Hull-alone GM_T ~ 0.36-0.52 m (matching RC-01 sheet 0.35-0.55 m) + strong longitudinal GM_L
    - High watertight foredeck, raised gunwales & dry cockpit floor (>= 0.745 m > T_max 0.62 m) prevent swamping.
    """
    n_x = 76
    xs = np.linspace(-1.75, 3.35, n_x)
    m_half = 20
    m = 2 * m_half

    def _hull_beam_top(x_val: float) -> float:
        if x_val >= 2.75:
            xn = max(0.0, min(1.0, (3.35 - x_val) / 0.60))
            return 0.60 * (xn ** 0.58) + 0.015 * (1.0 - xn)
        if x_val <= -1.20:
            xt = max(0.0, min(1.0, (x_val + 1.75) / 0.55))
            return 0.34 + 0.28 * (xt ** 0.75)
        s_m = max(0.0, min(1.0, (x_val + 1.20) / 3.95))
        bt = 0.62 + 0.18 * math.sin(math.pi * (s_m ** 0.88))
        if x_val > 2.25:
            blend = (x_val - 2.25) / 0.50
            bt *= (1.0 - blend * 0.22)
        return bt

    rings = []
    for i, x in enumerate(xs):
        beam_top = _hull_beam_top(float(x))

        # 2) Keel elevation z_k(x): forward-balanced flat keel [-0.15..+2.10] aligning LCB_x close to CG_x ~ +0.50 m
        if x < -0.15:
            xa = (-0.15 - x) / 1.60
            z_k = 0.045 + 0.365 * (xa ** 1.10)
        elif x <= 2.10:
            z_k = 0.000
        else:
            xf = (x - 2.10) / (3.35 - 2.10)
            z_k = 0.575 * (xf ** 1.75)

        # 3) Chine transition & upper deck profile (waterline chine for GM_T 0.38-0.48 m + high watertight freeboard & bow flare)
        z_chine = max(z_k + 0.035, 0.582 + 0.048 * max(0.0, (x - 1.45) / 1.90))
        if x > 2.75:
            xn = max(0.0, min(1.0, (3.35 - x) / 0.60))
            z_chine = 0.630 + 0.018 * (xn ** 0.7)

        if x >= 2.85:
            xn = max(0.0, min(1.0, (3.35 - x) / 0.50))
            z_deck_top = 0.690 + 0.195 * (xn ** 0.72)
        elif x <= -0.25:
            xa = (-0.25 - x) / 1.50
            z_deck_top = 1.095 - 0.140 * (xa ** 0.90)
        else:
            w_c, z_sill, _ = _canopy_spine_and_sill(np.array([x]))
            z_deck_top = float(z_sill[0])

        pts_port = np.zeros((m_half + 1, 3), dtype=np.float64)
        # Waterline chine half-beam ~0.68m midship -> wide waterplane I_T (GM_hull in 0.36-0.52 m)
        w_chine = beam_top * (0.86 if x < 2.55 else 0.91)

        # j=0..6: concave-to-convex deep-V bilge tuned by `underwater_fullness`
        p_shape = 1.85 - 1.05 * underwater_fullness
        for j in range(0, 7):
            s = j / 6.0
            py = s ** max(0.45, p_shape)
            pts_port[j] = [x, w_chine * py, z_k + (z_chine - z_k) * s]

        # j=7: flared chine spray rail stepping cleanly out to full 0.80 m half-beam above waterline!
        pts_port[7] = [x, beam_top * 0.96, z_chine + 0.042]
        z_sh = max(z_chine + 0.10, z_deck_top - 0.055) if (-0.25 <= x <= 2.85) else max(z_chine + 0.08, z_deck_top - 0.085)
        pts_port[8]  = [x, beam_top * 1.00, z_chine + (z_sh - z_chine) * 0.28]
        pts_port[9]  = [x, beam_top * 0.99, z_chine + (z_sh - z_chine) * 0.48]
        pts_port[10] = [x, beam_top * 0.94, z_chine + (z_sh - z_chine) * 0.80]

        if -0.25 < x < 2.85:
            # Sealed coaming & dry watertight cockpit sole (>= 0.745 m, well clear of 0.56 m WL & waves)
            w_c_arr, z_s_arr, _ = _canopy_spine_and_sill(np.array([x]))
            wc = min(float(w_c_arr[0]), beam_top * 0.84)
            zs = float(z_s_arr[0])
            pts_port[11] = [x, wc + 0.058, zs + 0.012]   # outer waterproof coaming flange
            pts_port[12] = [x, wc + 0.018, zs + 0.010]   # gold canopy sill frame rim
            pts_port[13] = [x, wc - 0.005, zs - 0.002]   # elastomeric canopy seal groove
            z_floor_fwd = 0.745 + 0.135 * (max(0.0, (x - 1.65) / 1.20) ** 1.05)
            z_floor = min(max(z_k + 0.34, z_floor_fwd), zs - 0.035)
            wc_in = max(0.02, wc - 0.055)
            pts_port[14] = [x, wc - 0.025, max(z_floor + 0.02, zs - 0.050)]
            pts_port[15] = [x, wc_in * 0.95, zs * 0.52 + z_floor * 0.48]
            pts_port[16] = [x, wc_in * 0.86, z_floor + 0.045]
            pts_port[17] = [x, wc_in * 0.65, z_floor + 0.010]
            pts_port[18] = [x, wc_in * 0.40, z_floor]
            pts_port[19] = [x, wc_in * 0.18, z_floor]
            pts_port[20] = [x, 0.0,          z_floor]
        else:
            # Smooth closed upper foredeck / ogive nose cone / aft turtledeck crown
            w_sh = beam_top * 0.72
            pts_port[11] = [x, w_sh,        z_sh + 0.02]
            pts_port[12] = [x, w_sh * 0.84, z_sh + (z_deck_top - z_sh) * 0.35]
            pts_port[13] = [x, w_sh * 0.68, z_sh + (z_deck_top - z_sh) * 0.60]
            pts_port[14] = [x, w_sh * 0.52, z_sh + (z_deck_top - z_sh) * 0.78]
            pts_port[15] = [x, w_sh * 0.38, z_sh + (z_deck_top - z_sh) * 0.88]
            pts_port[16] = [x, w_sh * 0.26, z_sh + (z_deck_top - z_sh) * 0.94]
            pts_port[17] = [x, w_sh * 0.16, z_sh + (z_deck_top - z_sh) * 0.975]
            pts_port[18] = [x, w_sh * 0.08, z_sh + (z_deck_top - z_sh) * 0.992]
            pts_port[19] = [x, w_sh * 0.03, z_deck_top - 0.002]
            pts_port[20] = [x, 0.0,         z_deck_top]

        # Build full closed ring (k=0 keel -> 1..19 port -> 20 top centerline -> 21..39 stbd mirrored)
        ring = np.zeros((m, 3), dtype=np.float64)
        ring[0:21] = pts_port
        for k in range(1, 20):
            p_mirror = pts_port[20 - k].copy()
            p_mirror[1] = -p_mirror[1]
            ring[20 + k] = p_mirror
        rings.append(ring)

    verts, faces = _loft_closed_rings(rings, close_ends=True)

    # Assign crisp face colors & PBR materials by exact strip & zone!
    # Mat IDs: 0=carbon_satin, 1=vtx_gold_paint, 5=cockpit_detail
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)

    n_quad_faces = (n_x - 1) * m * 2
    for fi in range(n_quad_faces):
        strip_idx = fi // (m * 2)
        k_seg = (fi % (m * 2)) // 2  # perimeter quad index 0..39
        x_mid = 0.5 * (xs[strip_idx] + xs[strip_idx + 1])

        # 1) Crisp VTX Gold Chine Cheek Racing Stripe (j=8->9 on port: k_seg==8; stbd: k_seg==31)
        if k_seg in (8, 31) and (-1.62 <= x_mid <= 3.15):
            fc[fi] = COL_GOLD
            fm[fi] = 1
        # 2) Crisp VTX Gold Cockpit Sill Frame Ribbon (j=12->13 on port: k_seg==12; stbd: k_seg==27)
        elif (-0.28 <= x_mid <= 2.86) and (k_seg in (12, 27)):
            fc[fi] = COL_GOLD
            fm[fi] = 1
        # 3) Cockpit Interior Tub Dark Matte Finish (j=14..25 inside cockpit [-0.25..2.85])
        elif (-0.25 < x_mid < 2.85) and (14 <= k_seg <= 25):
            fc[fi] = COL_CARBON_DARK
            fm[fi] = 5

    parts = [(verts, faces, fc, fm)]

    def add_vtx_emblem(side: float) -> None:
        # Three crisp inlaid 3D strokes forming 'V', 'T', 'X' reading left-to-right on BOTH sides:
        # Port (+Y): +X is viewer-left, -X is viewer-right. Stbd (-Y): -X is viewer-left, +X is viewer-right!
        if side >= 0.0:
            letters = [
                ((2.46, 0.905), (2.39, 0.805), 0.015),  # V left leg
                ((2.32, 0.905), (2.39, 0.805), 0.015),  # V right leg
                ((2.25, 0.905), (2.11, 0.905), 0.014),  # T top
                ((2.18, 0.905), (2.18, 0.805), 0.015),  # T stem
                ((2.04, 0.905), (1.90, 0.805), 0.014),  # X diag 1
                ((1.90, 0.905), (2.04, 0.805), 0.014),  # X diag 2
            ]
        else:
            letters = [
                ((1.90, 0.905), (1.97, 0.805), 0.015),  # V left leg (-X viewer-left)
                ((2.04, 0.905), (1.97, 0.805), 0.015),  # V right leg
                ((2.11, 0.905), (2.25, 0.905), 0.014),  # T top
                ((2.18, 0.905), (2.18, 0.805), 0.015),  # T stem
                ((2.32, 0.905), (2.46, 0.805), 0.014),  # X diag 1
                ((2.46, 0.905), (2.32, 0.805), 0.014),  # X diag 2
            ]
        for (x0, z0), (x1, z1), w in letters:
            xm, zm = 0.5 * (x0 + x1), 0.5 * (z0 + z1)
            bt = _hull_beam_top(xm)
            ym = side * (bt * 0.965)
            dx, dz = x1 - x0, z1 - z0
            seg_len = math.hypot(dx, dz)
            ang_y = -math.atan2(dz, dx)
            b_v, b_f, b_fc, b_fm = _add_box_part(
                xm, ym, zm, seg_len * 0.52, 0.004, w * 0.5, COL_GOLD, 1, rot_y=ang_y
            )
            parts.append((b_v, b_f, b_fc, b_fm))

    add_vtx_emblem(+1.0)
    add_vtx_emblem(-1.0)
    return _merge_disjoint_parts(parts)


def build_pass3_canopy_glass() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build C2 continuous aerodynamic teardrop polycarbonate canopy with tapered aerodynamic forward tip.

    Zero flat vertical end walls! Lower rim seats flush along the hull cockpit sill curve.
    """
    n_x = 56
    t_lin = np.linspace(0.0, 1.0, n_x)
    xs = -0.25 + (2.85 - (-0.25)) * (0.5 * (1.0 - np.cos(math.pi * t_lin)))

    w_arr, z_sill_arr, z_crown_arr = _canopy_spine_and_sill(xs)
    n_arc = 22  # points from port outer sill -> crown -> stbd outer sill -> stbd inner -> inner crown -> port inner sill!
    m = 2 * n_arc  # closed wall loop at every station!
    thickness = 0.0055

    rings = []
    for i in range(n_x):
        x = float(xs[i])
        wc = float(w_arr[i])
        zs = float(z_sill_arr[i])
        zc = float(z_crown_arr[i])
        h = max(0.015, zc - zs)

        # Outer arch points theta in [0, pi] (port y=+wc -> top y=0 -> stbd y=-wc)
        th_out = np.linspace(0.0, math.pi, n_arc)
        # Smooth superellipse arch p=2.2 (streamlined rounded shoulder, continuous tangent at nose/spine)
        y_out = wc * np.cos(th_out)
        z_out = zs + h * (np.sin(th_out) ** 0.88)

        # Inner arch inset smoothly by wall thickness
        th_in = np.linspace(math.pi, 0.0, n_arc)
        wc_in = max(0.005, wc - thickness)
        h_in = max(0.008, h - thickness)
        y_in = wc_in * np.cos(th_in)
        z_in = zs + h_in * (np.sin(th_in) ** 0.88)

        ring = np.vstack([
            np.column_stack([np.full(n_arc, x), y_out, z_out]),
            np.column_stack([np.full(n_arc, x), y_in, z_in]),
        ])
        rings.append(ring)

    verts, faces = _loft_closed_rings(rings, close_ends=True)
    fc = np.tile(np.array(COL_GLASS, dtype=np.float32), (faces.shape[0], 1))
    fm = np.full(faces.shape[0], 3, dtype=np.int32)
    return verts, faces, fc, fm


def build_pass3_cockpit_and_avionics() -> tuple[
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
]:
    """Build clean sculpted pilot bucket seat, glare-shield pod, stick & dual backlit MFD displays."""
    interior_parts = [
        # Seat pan + reclined backrest (cleanly above 0.745 m dry cockpit floor & below 1.61 m canopy)
        _add_box_part(1.16, 0.0, 0.790, 0.24, 0.22, 0.040, COL_SEAT, 5),
        _add_box_part(0.91, 0.0, 1.030, 0.05, 0.21, 0.24, COL_SEAT, 5, rot_y=-0.32),
        # Headrest + VTX Gold harness shoulder trim straps
        _add_box_part(0.80, 0.0, 1.280, 0.05, 0.12, 0.08, COL_CARBON_DARK, 5, rot_y=-0.20),
        _add_box_part(0.95, +0.10, 1.070, 0.055, 0.026, 0.16, COL_GOLD, 1, rot_y=-0.32),
        _add_box_part(0.95, -0.10, 1.070, 0.055, 0.026, 0.16, COL_GOLD, 1, rot_y=-0.32),
        # Center flight stick & pedestal
        _add_box_part(1.42, 0.0, 0.840, 0.025, 0.025, 0.12, COL_CARBON_DARK, 5, rot_y=0.14),
        _add_box_part(1.44, 0.0, 0.970, 0.032, 0.022, 0.040, COL_GOLD, 1),
        # Glare-shield instrument console binnacle (under sloped curved windshield)
        _add_box_part(1.88, 0.0, 1.035, 0.14, 0.28, 0.092, COL_CARBON_DARK, 5, rot_y=0.30),
    ]
    avionics_parts = [
        # Left & right crisp illuminated MFD glass panels angled cleanly toward pilot
        _add_box_part(1.755, +0.135, 1.045, 0.008, 0.105, 0.070, COL_AVIONICS, 6, rot_y=0.30),
        _add_box_part(1.755, -0.135, 1.045, 0.008, 0.105, 0.070, COL_AVIONICS, 6, rot_y=0.30),
    ]
    return _merge_disjoint_parts(interior_parts), _merge_disjoint_parts(avionics_parts)


def build_pass3_sponson(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build chined outboard stabiliser float centered locally around mount (-0.34, +-3.80, 0.48).

    Local z in [-0.12, +0.15] -> world z_keel = 0.48 - 0.12 = 0.36 m -> 0.20 m submerged at calm 0.56 m waterline!
    """
    n_x = 32
    xs = np.linspace(-0.88, 0.78, n_x)
    m = 20
    rings = []
    for x in xs:
        u = max(0.0, min(1.0, (x + 0.88) / 1.66))  # 0 stern, 1 bow
        # Sharp tapered bow, wide planing hull mid-body
        half_w = 0.215 * (max(0.0, math.sin(math.pi * (u ** 0.70))) ** 0.55)
        if u < 0.08:
            half_w = max(half_w, 0.12 * (0.3 + 0.7 * (u / 0.08)))
        half_w = max(half_w, 0.022)
        z_bot = -0.120 + (0.075 * ((max(0.0, (x - 0.30) / 0.48)) ** 1.6))
        z_chine = z_bot + 0.115
        z_top = 0.148 - 0.035 * ((max(0.0, (x - 0.30) / 0.48)) ** 1.4)

        pts = np.zeros((m, 3), dtype=np.float64)
        # 0: keel bottom
        pts[0] = [x, 0.0, z_bot]
        # 1..4: deadrise V-planing bottom -> port chine
        for j in range(1, 5):
            s = j / 4.0
            pts[j] = [x, half_w * s, z_bot + (z_chine - z_bot) * (s ** 1.25)]
        # 5..6: crisp vertical gold chine band!
        pts[5] = [x, half_w * 1.02, z_chine + 0.032]
        pts[6] = [x, half_w * 0.98, z_chine + 0.056]
        # 7..9: curved deck crown -> top center (10)
        for j in range(7, 11):
            s = (j - 6) / 4.0
            pts[j] = [x, half_w * 0.98 * math.cos(0.5 * math.pi * s), (z_chine + 0.056) + (z_top - (z_chine + 0.056)) * math.sin(0.5 * math.pi * s)]
        pts[10] = [x, 0.0, z_top]
        # Mirror to starboard (11..19)
        for k in range(1, 10):
            pm = pts[10 - k].copy()
            pm[1] = -pm[1]
            pts[10 + k] = pm
        rings.append(pts)

    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_x - 1) * m * 2
    for fi in range(n_quad_faces):
        k_seg = (fi % (m * 2)) // 2
        if k_seg in (5, 14):  # crisp port/stbd upper chine VTX gold trim band!
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def build_pass3_wing(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build port (side=+1) or stbd (side=-1) cambered NACA 2414 wing with clean trailing cove for articulated aileron."""
    ys = np.array([0.52, 0.90, 1.28, 1.66, 2.02, 2.08, 2.38, 2.74, 3.12, 3.50, 3.88, 4.24, 4.30, 4.48, 4.64], dtype=np.float64)
    n_y = len(ys)
    n_af = 28  # points around airfoil (14 upper TE->LE, 14 lower LE->TE)
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))  # 0 (LE) -> 1 (TE)

    rings = []
    for y_abs in ys:
        t = (y_abs - 0.52) / (4.64 - 0.52)
        chord = 2.02 * (1.0 - 0.45 * t)
        x_le = 1.15 - 1.07 * t
        z_root = 0.875 + 0.255 * t  # ~3.5 deg dihedral cleanly meeting hull shoulder & winglet!
        y = side * y_abs
        cut = 0.715 if (2.08 <= y_abs <= 4.24) else 1.0
        xc_eff = xc_half * cut
        zu, zl = _naca_4digit(xc_eff, thickness=0.145, camber=0.022)

        pts = []
        # Walk clockwise around airfoil in XZ plane: upper from TE->LE, lower from LE->TE (no duplicate TE vertices!)
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dz_te = 0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_root + zu[j] * chord + dz_te])
        pts.append([x_le, y, z_root])  # LE tip (j=0)
        for j in range(1, n_c):
            dz_te = -0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_root + zl[j] * chord + dz_te])
        rings.append(np.asarray(pts, dtype=np.float64))

    m = rings[0].shape[0]
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_y - 1) * m * 2
    le_idx = len(xc_half) - 1
    for fi in range(n_quad_faces):
        strip_idx = fi // (m * 2)
        k_seg = (fi % (m * 2)) // 2
        y_abs = 0.5 * (ys[strip_idx] + ys[strip_idx + 1])
        # Crisp VTX Gold racing leading-edge strip along inboard half (y < 2.2 m)
        if y_abs < 2.15 and abs(k_seg - le_idx) <= 2:
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def build_pass3_aileron(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build articulated NACA 2414 trailing aileron flap in local coordinates relative to its swept 3D hinge pivot."""
    ys = np.linspace(2.11, 4.21, 14)
    n_y = len(ys)
    n_af = 20
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))
    hinge_origin = np.array(AILERON_HINGE_PORT_VTX if side >= 0 else AILERON_HINGE_STBD_VTX, dtype=np.float64)

    rings = []
    for y_abs in ys:
        t = (y_abs - 0.52) / (4.64 - 0.52)
        chord = 2.02 * (1.0 - 0.45 * t)
        x_le = 1.15 - 1.07 * t
        z_root = 0.875 + 0.255 * t
        y = side * y_abs
        xc_eff = 0.742 + 0.258 * xc_half
        zu, zl = _naca_4digit(xc_eff, thickness=0.145, camber=0.022)
        z_mid_nose = 0.5 * (float(zu[0]) + float(zl[0])) * chord
        pts = []
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dz_te = 0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_root + zu[j] * chord + dz_te] - hinge_origin)
        pts.append([x_le - 0.734 * chord, y, z_root + z_mid_nose] - hinge_origin)
        for j in range(1, n_c):
            dz_te = -0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_root + zl[j] * chord + dz_te] - hinge_origin)
        rings.append(np.asarray(pts, dtype=np.float64))

    m = rings[0].shape[0]
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_y - 1) * m * 2
    for fi in range(n_quad_faces):
        k_seg = (fi % (m * 2)) // 2
        if k_seg <= 2 or k_seg >= m - 4:  # crisp VTX gold trailing edge trim stripe!
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def build_pass3_winglet(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build swept upturned winglet extending cleanly to y = +-4.80 m (9.60 m total wingspan!)."""
    n_s = 16
    n_af = 20
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))
    zu, zl = _naca_4digit(xc_half, thickness=0.11, camber=0.01)

    rings = []
    for s in np.linspace(0.0, 1.0, n_s):
        # Smooth upward sweep from wingtip (y=+-4.62, z=1.125) to tip (y=+-4.80, z=1.66)
        y = side * (4.62 + 0.18 * (s ** 0.85))
        z = 1.120 + 0.540 * s
        chord = 1.10 * (1.0 - 0.55 * s)
        x_le = 0.08 - 0.58 * s
        pts = []
        # Airfoil lies primarily in XY plane oriented vertically along Z!
        # Thickness points inward/outward along Y, chord along X
        dy_scale = 0.90
        for j in range(len(xc_half) - 1, 0, -1):
            pts.append([x_le - xc_half[j] * chord, y - side * zu[j] * chord * dy_scale, z])
        pts.append([x_le, y, z])
        for j in range(1, len(xc_half) - 1):
            pts.append([x_le - xc_half[j] * chord, y - side * zl[j] * chord * dy_scale, z])
        pts.append([x_le - chord, y - side * 0.002, z])
        pts.append([x_le - chord, y + side * 0.002, z])
        rings.append(np.asarray(pts, dtype=np.float64))

    m = rings[0].shape[0]
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_s - 1) * m * 2
    le_idx = len(xc_half) - 1
    for fi in range(n_quad_faces):
        strip_idx = fi // (m * 2)
        k_seg = (fi % (m * 2)) // 2
        if abs(k_seg - le_idx) <= 2 or strip_idx >= n_s - 3:
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def _streamline_strut(p0: np.ndarray, p1: np.ndarray, chord: float, thick: float, color: tuple, mat_id: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Loft a clean streamlined NACA-0024 strut tube directly between 3D anchors p0 and p1."""
    axis = p1 - p0
    L = float(np.linalg.norm(axis))
    t_hat = axis / max(1e-9, L)
    fwd = np.array([1.0, 0.0, 0.0])
    # Orthogonalize chord direction perpendicular to strut axis
    ch_dir = fwd - np.dot(fwd, t_hat) * t_hat
    if np.linalg.norm(ch_dir) < 1e-3:
        ch_dir = np.array([0.0, 1.0, 0.0])
    ch_dir /= np.linalg.norm(ch_dir)
    n_dir = np.cross(t_hat, ch_dir)
    n_dir /= np.linalg.norm(n_dir)

    m = 16
    ths = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False)
    # Closed streamlined oval-foil profile
    xc = 0.5 * np.cos(ths)
    zc = 0.5 * thick * np.sin(ths) * (1.0 - 0.35 * xc)
    xc *= chord

    rings = []
    for s in np.linspace(0.0, 1.0, 8):
        c = p0 + s * axis
        ring = c[None, :] + xc[:, None] * ch_dir[None, :] + zc[:, None] * n_dir[None, :]
        rings.append(ring)
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    fc = np.tile(np.array(color, dtype=np.float32), (faces.shape[0], 1))
    fm = np.full(faces.shape[0], mat_id, dtype=np.int32)
    return verts, faces, fc, fm


def build_pass3_strut(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build twin Ti-6Al-4V airfoil struts + collar lugs cleanly linking wing spar to sponson deck."""
    y_w = side * 3.16
    y_sp = side * SPONSON_MOUNT_CONCEPT_A_VTX[1]
    z_sp_top = SPONSON_MOUNT_CONCEPT_A_VTX[2] + 0.125  # solid socket into sponson deck (0.605m)
    parts = [
        # Forward primary strut (wing front spar @ x=+0.22, z=1.02 -> sponson fwd deck @ x=-0.10, z=0.605)
        _streamline_strut(np.array([0.22, y_w, 1.01]), np.array([-0.10, y_sp, z_sp_top]), 0.11, 0.36, COL_TITANIUM, 2),
        # Aft primary strut (wing rear spar @ x=-0.52, z=1.01 -> sponson aft deck @ x=-0.58, z=0.605)
        _streamline_strut(np.array([-0.52, y_w, 1.01]), np.array([-0.58, y_sp, z_sp_top]), 0.095, 0.36, COL_TITANIUM, 2),
        # Diagonal lateral X-brace
        _streamline_strut(np.array([0.16, y_w, 1.00]), np.array([-0.54, y_sp, z_sp_top + 0.02]), 0.06, 0.42, COL_TITANIUM, 2),
        # Wing & sponson machined gold anodized collar mounts
        _add_box_part(-0.15, y_w, 1.01, 0.42, 0.055, 0.028, COL_GOLD, 1),
        _add_box_part(-0.34, y_sp, z_sp_top + 0.015, 0.34, 0.055, 0.025, COL_GOLD, 1),
    ]
    return _merge_disjoint_parts(parts)


def build_pass3_tail_pylon_t_tail() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build swept T-tail vertical fin, horizontal tailplane, and zero-pinch nacelle cross-arm.

    Trailing coves on vertical fin and H-tail accommodate articulated rudder and elevator bodies.
    Horizontal duct support arm spans ONLY y in [-0.288, +0.288] (zero airflow pinch).
    """
    parts = []
    # 1. Swept vertical tail pylon fin (x_te goes to -3.45 -> overall length = 6.80 m!)
    zs_fin = np.array([0.78, 0.90, 0.96, 1.15, 1.35, 1.56, 1.78, 1.98, 2.19, 2.24, 2.31], dtype=np.float64)
    n_z = len(zs_fin)
    n_af = 20
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))
    rings_fin = []
    for z in zs_fin:
        s = (z - 0.78) / (2.31 - 0.78)
        x_le = -0.92 - 1.56 * s
        chord = 1.18 * (1.0 - 0.25 * s)
        # Straight hinge post line from (-2.12, z=0.96) to (-3.06, z=2.20): leave 1.5 cm cove ahead
        cut = min(0.95, max(0.60, ((x_le - (-2.105 - 0.758 * max(0.0, z - 0.96))) / chord))) if (0.96 <= z <= 2.20) else 1.0
        xc_eff = xc_half * cut
        zu, zl = _naca_4digit(xc_eff, thickness=0.125, camber=0.0)
        pts = []
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dy_te = 0.003 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, +zu[j] * chord + dy_te, z])
        pts.append([x_le, 0.0, z])
        for j in range(1, n_c):
            dy_te = -0.003 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, +zl[j] * chord + dy_te, z])
        rings_fin.append(np.asarray(pts, dtype=np.float64))
    vf, ff = _loft_closed_rings(rings_fin, close_ends=True)
    m_fin = rings_fin[0].shape[0]
    fc_f = np.tile(np.array(COL_CARBON, dtype=np.float32), (ff.shape[0], 1))
    fm_f = np.zeros(ff.shape[0], dtype=np.int32)
    le_idx = len(xc_half) - 1
    for fi in range((n_z - 1) * m_fin * 2):
        k_seg = (fi % (m_fin * 2)) // 2
        if abs(k_seg - le_idx) <= 1:  # crisp VTX Gold leading-edge accent stripe on pylon!
            fc_f[fi] = COL_GOLD
            fm_f[fi] = 1
    parts.append((vf, ff, fc_f, fm_f))

    # 2. Horizontal T-Tailplane (y in [-1.45, +1.45], z=2.305 -> cove aft of x=-3.125 for straight Y-hinge elevator)
    ys = np.array([-1.45, -1.36, -1.28, -1.24, -0.95, -0.60, -0.25, 0.0, 0.25, 0.60, 0.95, 1.24, 1.28, 1.36, 1.45], dtype=np.float64)
    n_y = len(ys)
    rings_ht = []
    for y in ys:
        ayt = abs(y) / 1.45
        chord = 0.88 * (1.0 - 0.28 * ayt)
        x_le = -2.56 - 0.14 * ayt
        z_mid = 2.302 - 0.004 * ayt
        cut = min(0.95, max(0.55, (x_le - (-3.122)) / chord)) if abs(y) <= 1.245 else 1.0
        xc_eff = xc_half * cut
        zu_h, zl_h = _naca_4digit(xc_eff, thickness=0.11, camber=-0.01)
        pts = []
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dz_te = 0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_mid + zu_h[j] * chord + dz_te])
        pts.append([x_le, y, z_mid])
        for j in range(1, n_c):
            dz_te = -0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_mid + zl_h[j] * chord + dz_te])
        rings_ht.append(np.asarray(pts, dtype=np.float64))
    vh, fh = _loft_closed_rings(rings_ht, close_ends=True)
    m_ht = rings_ht[0].shape[0]
    fc_h = np.tile(np.array(COL_CARBON, dtype=np.float32), (fh.shape[0], 1))
    fm_h = np.zeros(fh.shape[0], dtype=np.int32)
    for fi in range((n_y - 1) * m_ht * 2):
        strip_idx = fi // (m_ht * 2)
        if strip_idx <= 1 or strip_idx >= n_y - 3:  # crisp gold tip borders on H-tail!
            fc_h[fi] = COL_GOLD
            fm_h[fi] = 1
    parts.append((vh, fh, fc_h, fm_h))

    # 3. Horizontal Duct Nacelle Support Beam: STRICTLY spans y in [-0.288, +0.288]!
    ys_arm = np.linspace(-0.288, 0.288, 12)
    zu_a, zl_a = _naca_4digit(xc_half, thickness=0.22, camber=0.0)
    rings_arm = []
    for y in ys_arm:
        flare = 1.0 + 0.18 * math.exp(-((abs(y)) / 0.06) ** 2) + 0.14 * math.exp(-((0.288 - abs(y)) / 0.05) ** 2)
        chord = 0.34 * flare
        x_le = -1.87 + 0.02 * (flare - 1.0)
        z_arm = 1.56
        pts = []
        for j in range(len(xc_half) - 1, 0, -1):
            pts.append([x_le - xc_half[j] * chord, y, z_arm + zu_a[j] * chord])
        pts.append([x_le, y, z_arm])
        for j in range(1, len(xc_half) - 1):
            pts.append([x_le - xc_half[j] * chord, y, z_arm + zl_a[j] * chord])
        pts.append([x_le - chord, y, z_arm + 0.002])
        pts.append([x_le - chord, y, z_arm - 0.002])
        rings_arm.append(np.asarray(pts, dtype=np.float64))
    va, fa = _loft_closed_rings(rings_arm, close_ends=True)
    fc_a = np.tile(np.array(COL_CARBON, dtype=np.float32), (fa.shape[0], 1))
    fm_a = np.zeros(fa.shape[0], dtype=np.int32)
    parts.append((va, fa, fc_a, fm_a))

    return _merge_disjoint_parts(parts)


def build_pass3_elevator() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build articulated T-tail elevator in local coordinates around ELEVATOR_HINGE_VTX."""
    ys = np.linspace(-1.22, 1.22, 16)
    n_y = len(ys)
    n_af = 20
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))
    hinge_origin = np.array(ELEVATOR_HINGE_VTX, dtype=np.float64)

    rings = []
    for y in ys:
        ayt = abs(y) / 1.45
        chord = 0.88 * (1.0 - 0.28 * ayt)
        x_le = -2.56 - 0.14 * ayt
        z_mid = 2.302 - 0.004 * ayt
        f_start = min(0.84, max(0.58, (x_le - (-3.146)) / chord))
        xc_eff = f_start + (1.0 - f_start) * xc_half
        zu_h, zl_h = _naca_4digit(xc_eff, thickness=0.11, camber=-0.01)
        z_nose = 0.5 * (float(zu_h[0]) + float(zl_h[0])) * chord
        pts = []
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dz_te = 0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_mid + zu_h[j] * chord + dz_te] - hinge_origin)
        pts.append([-3.136, y, z_mid + z_nose] - hinge_origin)
        for j in range(1, n_c):
            dz_te = -0.002 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, y, z_mid + zl_h[j] * chord + dz_te] - hinge_origin)
        rings.append(np.asarray(pts, dtype=np.float64))

    m = rings[0].shape[0]
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_y - 1) * m * 2
    for fi in range(n_quad_faces):
        k_seg = (fi % (m * 2)) // 2
        if k_seg <= 2 or k_seg >= m - 4:
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def build_pass3_rudder(rudder_cove_clear: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build articulated swept vertical-fin rudder in local coordinates around RUDDER_HINGE_VTX.

    When ``rudder_cove_clear=True`` (opt-in for updated RC-01 revisions/profiles), lifts the
    lower-station leading-edge clamp from 0.84 -> 0.95 so the rudder clears the vertical fin's
    trailing cove across the full span and full +/-30 deg travel with zero vertex interference.
    Default ``False`` preserves byte-identical legacy Concept A geometry.
    """
    zs = np.linspace(0.98, 2.17, 12)
    n_z = len(zs)
    n_af = 20
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_half = 0.5 * (1.0 - np.cos(ang))
    hinge_origin = np.array(RUDDER_HINGE_VTX, dtype=np.float64)

    rings = []
    f_cap = 0.95 if rudder_cove_clear else 0.84
    nose_lead = 0.002 if rudder_cove_clear else 0.008
    for z in zs:
        s = (z - 0.78) / (2.31 - 0.78)
        x_le = -0.92 - 1.56 * s
        chord = 1.18 * (1.0 - 0.25 * s)
        x_hinge_z = -2.12 - 0.758 * (z - 0.96)
        f_start = min(f_cap, max(0.58, (x_le - (x_hinge_z - 0.005)) / chord))
        xc_eff = f_start + (1.0 - f_start) * xc_half
        zu, zl = _naca_4digit(xc_eff, thickness=0.125, camber=0.0)
        pts = []
        n_c = len(xc_eff)
        for j in range(n_c - 1, 0, -1):
            dy_te = 0.003 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, +zu[j] * chord + dy_te, z] - hinge_origin)
        pts.append([x_hinge_z + nose_lead, 0.0, z] - hinge_origin)
        for j in range(1, n_c):
            dy_te = -0.003 if j == n_c - 1 else 0.0
            pts.append([x_le - xc_eff[j] * chord, +zl[j] * chord + dy_te, z] - hinge_origin)
        rings.append(np.asarray(pts, dtype=np.float64))

    m = rings[0].shape[0]
    verts, faces = _loft_closed_rings(rings, close_ends=True)
    n_f = faces.shape[0]
    fc = np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (n_f, 1))
    fm = np.zeros(n_f, dtype=np.int32)
    n_quad_faces = (n_z - 1) * m * 2
    for fi in range(n_quad_faces):
        k_seg = (fi % (m * 2)) // 2
        if k_seg <= 2 or k_seg >= m - 4:
            fc[fi] = COL_GOLD
            fm[fi] = 1
    return verts, faces, fc, fm


def build_pass3_reverse_bucket(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build articulated Ti-6Al-4V clamshell thrust-reverser bucket around duct exit hinge pivot."""
    # Local space around REVERSE_BUCKET_HINGE_PORT/STBD_VTX (-2.33, +-0.78, 1.56).
    # At q=0 (stowed), upper shell arch hovers cleanly above duct shroud collar (r=0.495..0.525, x=[-0.28..+0.02]).
    # Side pivot arms drop down smoothly at y_local = +-0.495 to pivot lugs (0, +-0.495, 0).
    n_arc = 18
    r_in, r_out = 0.495, 0.528
    thetas = np.linspace(math.radians(24.0), math.radians(156.0), n_arc)
    x_st = [-0.28, -0.02]
    rings = []
    for xl in x_st:
        outer = [[xl, r_out * math.cos(th), r_out * math.sin(th)] for th in thetas]
        inner = [[xl, r_in * math.cos(th), r_in * math.sin(th)] for th in reversed(thetas)]
        rings.append(np.asarray(outer + inner, dtype=np.float64))
    vc, fc_idx = _loft_closed_rings(rings, close_ends=True)
    fc_c = np.tile(np.array(COL_TITANIUM, dtype=np.float32), (fc_idx.shape[0], 1))
    fm_c = np.full(fc_idx.shape[0], 2, dtype=np.int32)
    # Paint aft deflector lip with crisp VTX gold band
    for fi in range(fc_idx.shape[0]):
        if np.mean(vc[fc_idx[fi], 0]) < -0.20:
            fc_c[fi] = COL_GOLD
            fm_c[fi] = 1
    parts = [(vc, fc_idx, fc_c, fm_c)]
    for y_arm_sign in (-1.0, +1.0):
        # Diagonal hinge arm connecting lug (0, y*0.505, 0) cleanly into bucket edge (-0.15, y*0.46, 0.21)
        p_lug = np.array([0.0, y_arm_sign * 0.508, 0.0])
        p_edge = np.array([-0.14, y_arm_sign * 0.468, 0.21])
        parts.append(_streamline_strut(p_lug, p_edge, 0.065, 0.028, COL_CARBON_DARK, 0))
    return _merge_disjoint_parts(parts)


def build_pass3_duct(side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build Ø0.90 m inner-throat ducted fan shroud + motor nacelle hub + 4 aerodynamic stator vanes."""
    cx = FAN_CENTER_PORT_VTX[0]
    cy = side * FAN_CENTER_PORT_VTX[1]
    cz = FAN_CENTER_PORT_VTX[2]

    # 1. Closed torus-profile annular duct barrel (NACA-like ring airfoil: inner min radius = 0.450 m exact -> Ø0.90 m!)
    n_theta = 64  # smooth circular ring!
    n_prof = 22   # ring cross-section loop points
    ths_p = np.linspace(0.0, 2.0 * math.pi, n_prof, endpoint=False)
    # Profile parameterized around shroud cross-section (x local in [-0.30, +0.28], r in [0.450, 0.522]):
    # front intake lip curved bellmouth at +0.28, sharp boat-tail exit at -0.30!
    u_loop = 0.5 * (1.0 + np.cos(ths_p))  # 1 at leading edge (+0.28), 0 at trailing nozzle (-0.30)
    x_prof = -0.30 + 0.58 * u_loop
    # Shroud wall thickness: bellmouth nose bulbous at LE, tapering smoothly to exit nozzle
    thick = 0.068 * (0.35 + 0.65 * np.sin(0.5 * math.pi * (u_loop ** 0.55)))
    # Top (outside) vs bottom (inner throat) determined by sin(ths_p) >= 0:
    is_outer = np.sin(ths_p) >= 0.0
    r_inner_base = 0.450 + 0.022 * (u_loop ** 3.0)  # flared bellmouth intake expanding subtly from 0.450 throat to 0.472 inlet!
    r_prof = np.where(is_outer, r_inner_base + thick * np.abs(np.sin(ths_p)) ** 0.72, r_inner_base)

    # Revolve profile around X axis centered at (cx, cy, cz)
    phis = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    verts_sh = []
    for phi in phis:
        cphi, sphi = math.cos(phi), math.sin(phi)
        for k in range(n_prof):
            verts_sh.append([cx + x_prof[k], cy + r_prof[k] * cphi, cz + r_prof[k] * sphi])
    verts_sh = np.asarray(verts_sh, dtype=np.float64)
    faces_sh = []
    for i in range(n_theta):
        inext = (i + 1) % n_theta
        for k in range(n_prof):
            kn = (k + 1) % n_prof
            a = i * n_prof + k
            b = inext * n_prof + k
            c = inext * n_prof + kn
            d = i * n_prof + kn
            faces_sh.append([a, b, c])
            faces_sh.append([a, c, d])
    faces_sh = np.asarray(faces_sh, dtype=np.int32)
    v0, v1, v2 = verts_sh[faces_sh[:, 0]], verts_sh[faces_sh[:, 1]], verts_sh[faces_sh[:, 2]]
    if float(np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0) < 0:
        faces_sh = faces_sh[:, [0, 2, 1]]

    fc_sh = np.tile(np.array(COL_CARBON, dtype=np.float32), (faces_sh.shape[0], 1))
    fm_sh = np.zeros(faces_sh.shape[0], dtype=np.int32)
    # Crisp painted VTX Gold intake bezel rim ONLY on front lip points (x_prof >= cx_lip -> k near 0 / n_prof-1)!
    for fi in range(faces_sh.shape[0]):
        k_pt = faces_sh[fi, 0] % n_prof
        if x_prof[k_pt] >= 0.215:
            fc_sh[fi] = COL_GOLD
            fm_sh[fi] = 1

    parts = [(verts_sh, faces_sh, fc_sh, fm_sh)]

    # 2. Central motor nacelle pod behind rotor (x_local in [-0.26, +0.02], r=0.112 -> 0.04m tailcone!)
    xs_pod = np.linspace(-0.28, 0.02, 10)
    rings_pod = []
    ths_pod = np.linspace(0.0, 2.0 * math.pi, 20, endpoint=False)
    for xl in xs_pod:
        s = (xl + 0.28) / 0.30
        r_p = 0.022 + 0.090 * (math.sin(0.5 * math.pi * s) ** 0.55)
        ring = np.column_stack([
            np.full(20, cx + xl),
            cy + r_p * np.cos(ths_pod),
            cz + r_p * np.sin(ths_pod),
        ])
        rings_pod.append(ring)
    vp, fp = _loft_closed_rings(rings_pod, close_ends=True)
    parts.append((vp, fp, np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (fp.shape[0], 1)), np.zeros(fp.shape[0], dtype=np.int32)))

    # 3. Four structural stator vanes anchoring central motor pod cleanly to duct inner wall (zero floating pod!)
    for ang_deg in (45.0, 135.0, 225.0, 315.0):
        ar = math.radians(ang_deg)
        p_in = np.array([cx - 0.13, cy + 0.095 * math.cos(ar), cz + 0.095 * math.sin(ar)])
        p_out = np.array([cx - 0.14, cy + 0.462 * math.cos(ar), cz + 0.462 * math.sin(ar)])
        parts.append(_streamline_strut(p_in, p_out, 0.085, 0.24, COL_TITANIUM, 2))

    return _merge_disjoint_parts(parts)


def build_pass3_fan_rotor_and_spinner() -> tuple[
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
]:
    """Build 9-blade twisted NACA airfoil rotor (local node space around (0,0,0)) + parabolic gold/carbon spinner."""
    parts_r = []
    # Central machined rotor hub barrel (x in [-0.04, +0.03], r=0.112)
    ths = np.linspace(0.0, 2.0 * math.pi, 24, endpoint=False)
    rings_hub = []
    for xl, rh in [(-0.045, 0.112), (0.030, 0.112)]:
        rings_hub.append(np.column_stack([np.full(24, xl), rh * np.cos(ths), rh * np.sin(ths)]))
    vh, fh = _loft_closed_rings(rings_hub, close_ends=True)
    parts_r.append((vh, fh, np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (fh.shape[0], 1)), np.zeros(fh.shape[0], dtype=np.int32)))

    # 9 clean twisted NACA-4412 fan blades spanning r=0.105 -> 0.439 m (1.1 cm clear of r=0.450 throat!)
    n_r = 8
    n_af = 16
    ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
    xc_h = 0.5 * (1.0 - np.cos(ang))
    zu_b, zl_b = _naca_4digit(xc_h, thickness=0.11, camber=0.03)
    r_vals = np.linspace(0.104, 0.439, n_r)

    for b_idx in range(9):
        az = 2.0 * math.pi * b_idx / 9.0
        ca, sa = math.cos(az), math.sin(az)
        e_rad = np.array([0.0, ca, sa])
        e_tan = np.array([0.0, -sa, ca])
        e_fwd = np.array([1.0, 0.0, 0.0])

        rings_b = []
        for s_idx, rv in enumerate(r_vals):
            sf = s_idx / (n_r - 1)
            chord = 0.095 + 0.025 * math.sin(math.pi * sf) - 0.040 * (sf ** 2.2)
            pitch = math.radians(48.0 - 24.0 * sf)
            cp, sp = math.cos(pitch), math.sin(pitch)
            dir_ch = cp * e_tan + sp * e_fwd
            dir_th = -sp * e_tan + cp * e_fwd
            c_center = rv * e_rad + (-0.005) * e_fwd
            pts = []
            for j in range(len(xc_h) - 1, 0, -1):
                x0 = (0.4 - xc_h[j]) * chord
                pts.append(c_center + x0 * dir_ch + (zu_b[j] * chord) * dir_th)
            pts.append(c_center + (0.4 * chord) * dir_ch)
            for j in range(1, len(xc_h) - 1):
                x0 = (0.4 - xc_h[j]) * chord
                pts.append(c_center + x0 * dir_ch + (zl_b[j] * chord) * dir_th)
            pts.append(c_center + (-0.6 * chord) * dir_ch + 0.001 * dir_th)
            pts.append(c_center + (-0.6 * chord) * dir_ch - 0.001 * dir_th)
            rings_b.append(np.asarray(pts, dtype=np.float64))
        vb, fb = _loft_closed_rings(rings_b, close_ends=True)
        parts_r.append((vb, fb, np.tile(np.array(COL_ROTOR, dtype=np.float32), (fb.shape[0], 1)), np.full(fb.shape[0], 4, dtype=np.int32)))

    rotor_merged = _merge_disjoint_parts(parts_r)

    # Sleek Parabolic Nose Spinner (x_local in [0.025, 0.195], r=0.112 -> 0.006, crisp VTX Gold nose tip!)
    xs_sp = np.linspace(0.025, 0.195, 14)
    rings_sp = []
    ths_sp = np.linspace(0.0, 2.0 * math.pi, 28, endpoint=False)
    for xl in xs_sp:
        s = (xl - 0.025) / 0.170
        r_s = max(0.006, 0.112 * math.sqrt(max(0.0, 1.0 - (s ** 1.25))))
        rings_sp.append(np.column_stack([np.full(28, xl), r_s * np.cos(ths_sp), r_s * np.sin(ths_sp)]))
    vs, fs = _loft_closed_rings(rings_sp, close_ends=True)
    fc_s = np.tile(np.array(COL_GOLD, dtype=np.float32), (fs.shape[0], 1))
    fm_s = np.full(fs.shape[0], 1, dtype=np.int32)
    # Dark carbon base collar on back 2 rings for crisp two-tone spinner contrast
    for fi in range(2 * 28 * 2):
        fc_s[fi] = COL_CARBON_DARK
        fm_s[fi] = 0
    return rotor_merged, (vs, fs, fc_s, fm_s)


# ---------------------------------------------------------------------------
# GLB Serializer (glTF 2.0 Binary with Multi-Material PBR + Normals + Colors)
# ---------------------------------------------------------------------------
def _export_concept_a_glb(nodes_data: list[dict[str, Any]], out_path: Path) -> None:
    """Serialize all 19 nodes into standard glTF 2.0 GLB with explicit PBR materials & crisp visuals."""
    materials = [
        {'name': 'carbon_satin', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.18, 'roughnessFactor': 0.42}},
        {'name': 'vtx_gold_paint', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.65, 'roughnessFactor': 0.20}},
        {'name': 'titanium_strut', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.85, 'roughnessFactor': 0.25}},
        {'name': 'canopy_glass', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.08, 'roughnessFactor': 0.06}, 'alphaMode': 'BLEND', 'doubleSided': True},
        {'name': 'fan_rotor', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.55, 'roughnessFactor': 0.30}},
        {'name': 'cockpit_detail', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.08, 'roughnessFactor': 0.72}},
        {'name': 'avionics_glow', 'pbrMetallicRoughness': {'baseColorFactor': [1.0, 1.0, 1.0, 1.0], 'metallicFactor': 0.05, 'roughnessFactor': 0.20}, 'emissiveFactor': [0.06, 0.75, 0.92]},
    ]

    bin_chunks = bytearray()
    buffer_views = []
    accessors = []

    def add_buf(arr: np.ndarray, target: int, acc_type: str, comp_type: int, min_max: bool = False) -> int:
        raw = arr.tobytes()
        pad = (-len(bin_chunks)) % 4
        if pad:
            bin_chunks.extend(b'\x00' * pad)
        off = len(bin_chunks)
        bin_chunks.extend(raw)
        bv_idx = len(buffer_views)
        buffer_views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(raw), 'target': target})
        acc = {'bufferView': bv_idx, 'componentType': comp_type, 'count': int(arr.shape[0]), 'type': acc_type}
        if min_max:
            acc['min'] = np.min(arr, axis=0).astype(float).tolist()
            acc['max'] = np.max(arr, axis=0).astype(float).tolist()
        acc_idx = len(accessors)
        accessors.append(acc)
        return acc_idx

    gltf_meshes = []
    gltf_nodes = []
    scene_nodes = []

    for nd in nodes_data:
        prims_gltf = []
        for p in nd['prims']:
            pos_gltf = _vtx_to_gltf(p['pos'])
            norm_gltf = _vtx_to_gltf(p['norm'])
            # Re-normalize just in case
            nl = np.linalg.norm(norm_gltf, axis=1, keepdims=True)
            norm_gltf = (norm_gltf / np.maximum(nl, 1e-12)).astype(np.float32)

            acc_pos = add_buf(pos_gltf.astype(np.float32), 34962, 'VEC3', 5126, min_max=True)
            acc_norm = add_buf(norm_gltf.astype(np.float32), 34962, 'VEC3', 5126)
            acc_col = add_buf(p['col'].astype(np.float32), 34962, 'VEC4', 5126)
            acc_uv = add_buf(p['uv'].astype(np.float32), 34962, 'VEC2', 5126)
            acc_idx = add_buf(p['idx'].astype(np.uint32), 34963, 'SCALAR', 5125)
            prims_gltf.append({
                'attributes': {
                    'POSITION': acc_pos,
                    'NORMAL': acc_norm,
                    'COLOR_0': acc_col,
                    'TEXCOORD_0': acc_uv,
                },
                'indices': acc_idx,
                'material': int(p['material']),
            })

        m_idx = len(gltf_meshes)
        gltf_meshes.append({'name': nd['name'] + '_Mesh', 'primitives': prims_gltf})
        tx, ty, tz = nd['offset_vtx']
        # VTX (+X, +Y, +Z) -> glTF (+X, +Z, -Y)
        node_obj: dict[str, Any] = {
            'name': nd['name'],
            'mesh': m_idx,
            'translation': [float(tx), float(tz), float(-ty)],
        }
        n_idx = len(gltf_nodes)
        gltf_nodes.append(node_obj)
        scene_nodes.append(n_idx)

    gltf = {
        'asset': {'version': '2.0', 'generator': 'VTX Ricochet RC-01 Pass 3 Spec Builder'},
        'scene': 0,
        'scenes': [{'nodes': scene_nodes}],
        'nodes': gltf_nodes,
        'meshes': gltf_meshes,
        'materials': materials,
        'bufferViews': buffer_views,
        'accessors': accessors,
        'buffers': [{'byteLength': len(bin_chunks)}],
    }
    json_bytes = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    j_pad = (-len(json_bytes)) % 4
    if j_pad:
        json_bytes += b' ' * j_pad
    b_pad = (-len(bin_chunks)) % 4
    if b_pad:
        bin_chunks.extend(b'\x00' * b_pad)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_chunks)
    header = struct.pack('<III', 0x46546C67, 2, total_len)
    c0 = struct.pack('<II', len(json_bytes), 0x4E4F534A) + json_bytes
    c1 = struct.pack('<II', len(bin_chunks), 0x004E4942) + bytes(bin_chunks)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(header + c0 + c1)


# ---------------------------------------------------------------------------
# Hydrostatic Target Solver + Complete Build Pipeline
# ---------------------------------------------------------------------------
def build_concept_a_glb(out_path: Path = DEFAULT_CONCEPT_A_OUT, target_draft_m: float = 0.560) -> dict[str, Any]:
    """Build calibrated Pass 3 Concept A GLB, solving hull bilge fullness so T_design == 0.560 m @ 900 kg."""
    sp_port_v, sp_port_f, sp_port_fc, sp_port_fm = build_pass3_sponson(+1)
    sp_stbd_v, sp_stbd_f, sp_stbd_fc, sp_stbd_fm = build_pass3_sponson(-1)

    # Newton/bisection calibration on underwater_fullness parameter for exact target draft = 0.560 m @ 900 kg
    lo_u, hi_u = -0.60, 1.35
    best_u = 0.50
    for _ in range(14):
        mid_u = 0.5 * (lo_u + hi_u)
        hv, hf, _, _ = build_pass3_hull_and_cabin(underwater_fullness=mid_u)
        stab = evaluate_mesh_curve_stability(
            hv, hf, sp_port_v, sp_port_f,
            sponson_mount_z_m=SPONSON_MOUNT_CONCEPT_A_VTX[2],
            sponson_mount_y_m=SPONSON_MOUNT_CONCEPT_A_VTX[1],
            mass_kg=RC01_DESIGN_MASS_KG,
        )
        # Higher fullness -> shallower draft; lower fullness -> deeper draft
        if stab['draft_m'] > target_draft_m:
            lo_u = mid_u
        else:
            hi_u = mid_u
        best_u = mid_u

    hull_v, hull_f, hull_fc, hull_fm = build_pass3_hull_and_cabin(underwater_fullness=best_u)
    hull_vol = _check_watertight(hull_v, hull_f, 'Ricochet_ConceptA_Hull_Cabin')
    sp_vol = _check_watertight(sp_port_v, sp_port_f, 'Ricochet_Sponson_Port')
    _check_watertight(sp_stbd_v, sp_stbd_f, 'Ricochet_Sponson_Stbd')

    stab_900 = evaluate_mesh_curve_stability(
        hull_v, hull_f, sp_port_v, sp_port_f,
        sponson_mount_z_m=SPONSON_MOUNT_CONCEPT_A_VTX[2],
        sponson_mount_y_m=SPONSON_MOUNT_CONCEPT_A_VTX[1],
        mass_kg=RC01_DESIGN_MASS_KG,
    )
    stab_1050 = evaluate_mesh_curve_stability(
        hull_v, hull_f, sp_port_v, sp_port_f,
        sponson_mount_z_m=SPONSON_MOUNT_CONCEPT_A_VTX[2],
        sponson_mount_y_m=SPONSON_MOUNT_CONCEPT_A_VTX[1],
        mass_kg=RC01_MAX_STUDY_MASS_KG,
    )

    wing_p = build_pass3_wing(+1)
    wing_s = build_pass3_wing(-1)
    ail_p = build_pass3_aileron(+1)
    ail_s = build_pass3_aileron(-1)
    wlet_p = build_pass3_winglet(+1)
    wlet_s = build_pass3_winglet(-1)
    strut_p = build_pass3_strut(+1)
    strut_s = build_pass3_strut(-1)
    tail = build_pass3_tail_pylon_t_tail()
    elev = build_pass3_elevator()
    rud = build_pass3_rudder()
    duct_p = build_pass3_duct(+1)
    duct_s = build_pass3_duct(-1)
    rev_p = build_pass3_reverse_bucket(+1)
    rev_s = build_pass3_reverse_bucket(-1)
    rotor_p, spinner_p = build_pass3_fan_rotor_and_spinner()
    rotor_s, spinner_s = build_pass3_fan_rotor_and_spinner()
    canopy = build_pass3_canopy_glass()
    interior, avionics = build_pass3_cockpit_and_avionics()

    raw_nodes = [
        ('Ricochet_ConceptA_Hull_Cabin', (0.0, 0.0, 0.0), (hull_v, hull_f, hull_fc, hull_fm)),
        ('Ricochet_Sponson_Port', SPONSON_MOUNT_CONCEPT_A_VTX, (sp_port_v, sp_port_f, sp_port_fc, sp_port_fm)),
        ('Ricochet_Sponson_Stbd', (SPONSON_MOUNT_CONCEPT_A_VTX[0], -SPONSON_MOUNT_CONCEPT_A_VTX[1], SPONSON_MOUNT_CONCEPT_A_VTX[2]), (sp_stbd_v, sp_stbd_f, sp_stbd_fc, sp_stbd_fm)),
        ('Ricochet_Wing_Port', (0.0, 0.0, 0.0), wing_p),
        ('Ricochet_Wing_Stbd', (0.0, 0.0, 0.0), wing_s),
        ('Ricochet_Aileron_Port', AILERON_HINGE_PORT_VTX, ail_p),
        ('Ricochet_Aileron_Stbd', AILERON_HINGE_STBD_VTX, ail_s),
        ('Ricochet_Winglet_Port', (0.0, 0.0, 0.0), wlet_p),
        ('Ricochet_Winglet_Stbd', (0.0, 0.0, 0.0), wlet_s),
        ('Ricochet_Strut_Port', (0.0, 0.0, 0.0), strut_p),
        ('Ricochet_Strut_Stbd', (0.0, 0.0, 0.0), strut_s),
        ('Ricochet_Tail_Pylon_T_Tail', (0.0, 0.0, 0.0), tail),
        ('Ricochet_Elevator', ELEVATOR_HINGE_VTX, elev),
        ('Ricochet_Rudder', RUDDER_HINGE_VTX, rud),
        ('Ricochet_Duct_Port', (0.0, 0.0, 0.0), duct_p),
        ('Ricochet_Duct_Stbd', (0.0, 0.0, 0.0), duct_s),
        ('Ricochet_Reverse_Bucket_Port', REVERSE_BUCKET_HINGE_PORT_VTX, rev_p),
        ('Ricochet_Reverse_Bucket_Stbd', REVERSE_BUCKET_HINGE_STBD_VTX, rev_s),
        ('Ricochet_Fan_Rotor_Port', FAN_CENTER_PORT_VTX, rotor_p),
        ('Ricochet_Fan_Rotor_Stbd', (FAN_CENTER_PORT_VTX[0], -FAN_CENTER_PORT_VTX[1], FAN_CENTER_PORT_VTX[2]), rotor_s),
        ('Ricochet_Fan_Spinner_Port', FAN_CENTER_PORT_VTX, spinner_p),
        ('Ricochet_Fan_Spinner_Stbd', (FAN_CENTER_PORT_VTX[0], -FAN_CENTER_PORT_VTX[1], FAN_CENTER_PORT_VTX[2]), spinner_s),
        ('Ricochet_Canopy_Glass', (0.0, 0.0, 0.0), canopy),
        ('Ricochet_Cockpit_Interior', (0.0, 0.0, 0.0), interior),
        ('Ricochet_Avionics_Display', (0.0, 0.0, 0.0), avionics),
    ]

    nodes_serialized = []
    for name, off, (v, f, fc, fm) in raw_nodes:
        _check_watertight(v, f, name)
        prims = _split_sharp_and_color_seams(v, f, fc, fm, crease_deg=34.0)
        nodes_serialized.append({'name': name, 'offset_vtx': off, 'prims': prims})

    _export_concept_a_glb(nodes_serialized, out_path)
    return {
        'glb_path': str(out_path),
        'node_count': len(nodes_serialized),
        'underwater_fullness': float(best_u),
        'hull_enclosed_volume_m3': float(hull_vol),
        'sponson_volume_each_m3': float(sp_vol),
        'hydro_900kg': stab_900,
        'hydro_1050kg': stab_1050,
        'aero_drag_estimate': canopy_and_craft_cd0(windshield_rake_deg=24.0, canopy_fineness_ratio=4.0),
    }


def build_profile_ski_mesh(ski_spec: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build watertight carbon-satin ski blade (planing or cambered hydrofoil) + yoke + optional fin.

    Geometry is in the ski body frame: origin (0, 0, 0) at incidence hinge pivot, +X forward, +Y port, +Z up.
    """
    L = float(ski_spec['length_m'])
    b = float(ski_spec['beam_m'])
    t_pl = float(ski_spec['thickness_m'])
    a = float(ski_spec['hinge_from_trailing_edge_m'])
    zb = float(ski_spec['bottom_below_pivot_m'])
    hydro_mode = str(ski_spec.get('hydro_mode', 'planing'))
    x_te = -a
    x_le = L - a
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []

    if hydro_mode == 'hydrofoil_ski':
        b_f = float(ski_spec.get('foil_span_m', b))
        c_f = float(ski_spec.get('foil_chord_m', L))
        tc = float(ski_spec.get('foil_tc', 0.11))
        camber = max(0.0, min(0.06, -float(ski_spec.get('foil_alpha0_deg', -3.5)) / 100.0))
        ys = np.linspace(-0.5 * b_f, 0.5 * b_f, 18)
        n_af = 22
        ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
        xc_half = 0.5 * (1.0 - np.cos(ang))
        zu, zl = _naca_4digit(xc_half, thickness=tc, camber=camber)
        z_center = -zb + 0.5 * max(t_pl, tc * c_f)
        rings = []
        for y in ys:
            eta = abs(y) / max(0.5 * b_f, 1e-6)
            taper = 1.0 - 0.25 * (max(0.0, (eta - 0.72) / 0.28) ** 1.6)
            c_loc = c_f * taper
            x_le_loc = x_le - 0.25 * (c_f - c_loc)
            pts = []
            n_c = len(xc_half)
            for j in range(n_c - 1, 0, -1):
                dz_te = 0.0015 if j == n_c - 1 else 0.0
                pts.append([x_le_loc - xc_half[j] * c_loc, y, z_center + zu[j] * c_loc + dz_te])
            pts.append([x_le_loc, y, z_center])
            for j in range(1, n_c):
                dz_te = -0.0015 if j == n_c - 1 else 0.0
                pts.append([x_le_loc - xc_half[j] * c_loc, y, z_center + zl[j] * c_loc + dz_te])
            rings.append(np.asarray(pts, dtype=np.float64))
        v_bl, f_bl = _loft_closed_rings(rings, close_ends=True)
        m_r = rings[0].shape[0]
        fc_bl = np.tile(np.array(COL_CARBON, dtype=np.float32), (f_bl.shape[0], 1))
        fm_bl = np.zeros(f_bl.shape[0], dtype=np.int32)
        le_idx = len(xc_half) - 1
        for fi in range((len(ys) - 1) * m_r * 2):
            k_seg = (fi % (m_r * 2)) // 2
            if abs(k_seg - le_idx) <= 1:
                fc_bl[fi] = COL_GOLD
                fm_bl[fi] = 1
        parts.append((v_bl, f_bl, fc_bl, fm_bl))
        z_top_blade = z_center + 0.5 * tc * c_f
    else:
        # Planing hydro-ski with crisp flat/shallow-V bottom, gold side rails, and upturned bow tip
        deadrise = math.radians(max(0.0, float(ski_spec.get('deadrise_deg', 0.0))))
        xs = np.linspace(x_te, x_le, 18)
        rings = []
        for x in xs:
            u = (x - x_te) / max(L, 1e-6)  # 0 TE -> 1 LE
            bow_t = max(0.0, (u - 0.82) / 0.18)
            hw = 0.5 * b * (1.0 - 0.72 * (bow_t ** 1.7))
            hw = max(hw, 0.025)
            z_rise = 0.055 * (bow_t ** 2.0)
            z_keel = -zb + z_rise
            z_chine = z_keel + hw * math.tan(deadrise)
            t_loc = t_pl * (1.0 - 0.35 * bow_t)
            z_deck_edge = z_chine + 0.65 * t_loc
            z_deck_crown = z_chine + t_loc
            pts = np.array([
                [x, 0.0, z_keel],
                [x, 0.5 * hw, 0.5 * (z_keel + z_chine)],
                [x, hw, z_chine],
                [x, hw, z_deck_edge],
                [x, 0.65 * hw, z_deck_crown],
                [x, 0.0, z_deck_crown + 0.008],
                [x, -0.65 * hw, z_deck_crown],
                [x, -hw, z_deck_edge],
                [x, -hw, z_chine],
                [x, -0.5 * hw, 0.5 * (z_keel + z_chine)],
            ], dtype=np.float64)
            rings.append(pts)
        v_bl, f_bl = _loft_closed_rings(rings, close_ends=True)
        m_r = rings[0].shape[0]
        fc_bl = np.tile(np.array(COL_CARBON, dtype=np.float32), (f_bl.shape[0], 1))
        fm_bl = np.zeros(f_bl.shape[0], dtype=np.int32)
        for fi in range((len(xs) - 1) * m_r * 2):
            k_seg = (fi % (m_r * 2)) // 2
            if k_seg in (2, 7):  # VTX gold outer rail stripes
                fc_bl[fi] = COL_GOLD
                fm_bl[fi] = 1
        parts.append((v_bl, f_bl, fc_bl, fm_bl))
        z_top_blade = -zb + t_pl

    # Machined Ti-6Al-4V incidence hinge yoke collar connecting blade spine to pivot (0, 0, 0)
    yoke_h = max(0.025, 0.5 * abs(z_top_blade))
    yoke_cz = 0.5 * z_top_blade
    parts.append(_add_box_part(0.0, 0.0, yoke_cz, min(0.11, 0.25 * L), min(0.055, 0.16 * b), yoke_h + 0.012, COL_TITANIUM, 2))
    parts.append(_add_box_part(0.0, 0.0, 0.0, 0.045, min(0.075, 0.20 * b), 0.028, COL_GOLD, 1))

    # Optional streamlined NACA 0012 tracking fin beneath the ski
    fin = ski_spec.get('fin')
    if fin:
        fx = float(fin['x_from_pivot_m'])
        f_span = float(fin['span_m'])
        f_chord = float(fin['chord_m'])
        n_af = 16
        ang = np.linspace(0.0, math.pi, n_af // 2 + 1)
        xc_half = 0.5 * (1.0 - np.cos(ang))
        zu_f, zl_f = _naca_4digit(xc_half, thickness=0.12, camber=0.0)
        zs_f = np.linspace(-zb + 0.005, -zb - f_span, 8)
        rings_f = []
        for idx_z, z in enumerate(zs_f):
            s = idx_z / max(len(zs_f) - 1, 1)
            c_loc = f_chord * (1.0 - 0.22 * s)
            x_le_f = fx + 0.5 * f_chord - 0.15 * f_chord * s
            pts = []
            n_c = len(xc_half)
            for j in range(n_c - 1, 0, -1):
                dy = 0.0015 if j == n_c - 1 else 0.0
                pts.append([x_le_f - xc_half[j] * c_loc, +zu_f[j] * c_loc + dy, z])
            pts.append([x_le_f, 0.0, z])
            for j in range(1, n_c):
                dy = -0.0015 if j == n_c - 1 else 0.0
                pts.append([x_le_f - xc_half[j] * c_loc, +zl_f[j] * c_loc + dy, z])
            rings_f.append(np.asarray(pts, dtype=np.float64))
        vf, ff = _loft_closed_rings(rings_f, close_ends=True)
        fc_f = np.tile(np.array(COL_CARBON_DARK, dtype=np.float32), (ff.shape[0], 1))
        fm_f = np.zeros(ff.shape[0], dtype=np.int32)
        m_rf = rings_f[0].shape[0]
        for fi in range((len(zs_f) - 1) * m_rf * 2):
            strip = fi // (m_rf * 2)
            if strip >= len(zs_f) - 2:
                fc_f[fi] = COL_GOLD
                fm_f[fi] = 1
        parts.append((vf, ff, fc_f, fm_f))

    return _merge_disjoint_parts(parts)


def build_profile_ski_strut_mesh(
    pivot_local: tuple[float, float, float] | list[float],
    anchor_local: tuple[float, float, float] | list[float],
    *,
    chord_m: float = 0.18,
    thickness_m: float = 0.036,
    aft_brace_anchor: tuple[float, float, float] | list[float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build streamlined Ti-6Al-4V ski strut (+ optional diagonal brace) in parent body local frame."""
    p0 = np.asarray(anchor_local, dtype=np.float64)
    p1 = np.asarray(pivot_local, dtype=np.float64)
    if float(np.linalg.norm(p1 - p0)) < 0.03:
        p0 = p1 + np.array([0.0, 0.0, 0.08], dtype=np.float64)
    parts = [
        _streamline_strut(p0, p1, chord_m, thickness_m, COL_TITANIUM, 2),
        _add_box_part(float(p0[0]), float(p0[1]), float(p0[2]), 0.55 * chord_m, max(0.035, 0.9 * thickness_m), 0.022, COL_GOLD, 1),
    ]
    if aft_brace_anchor is not None:
        pb = np.asarray(aft_brace_anchor, dtype=np.float64)
        if float(np.linalg.norm(p1 - pb)) > 0.12:
            parts.append(_streamline_strut(pb, p1 + np.array([0.0, 0.0, 0.03]), 0.65 * chord_m, 0.72 * thickness_m, COL_TITANIUM, 2))
            parts.append(_add_box_part(float(pb[0]), float(pb[1]), float(pb[2]), 0.40 * chord_m, max(0.03, 0.75 * thickness_m), 0.02, COL_GOLD, 1))
    return _merge_disjoint_parts(parts)


def _part_tuple_to_watertight_mesh(
    name: str,
    part: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    source_id: str = 'procedural_profile',
):
    """Wrap (verts, faces, face_colors, face_mats) into a WatertightMesh with sharp visual buffers."""
    from vtx.water.hydrodynamics import WatertightMesh

    v, f, fc, fm = part
    _check_watertight(v, f, name)
    wmesh = WatertightMesh(name=name, vertices=v, faces=f, source_id=source_id)
    prims = _split_sharp_and_color_seams(v, f, fc, fm, crease_deg=34.0)
    vis_v, vis_n, vis_c, vis_f = [], [], [], []
    v_off = 0
    for pr in prims:
        pv = np.asarray(pr['pos'], dtype=np.float64)
        pn = np.asarray(pr['norm'], dtype=np.float32)
        pc = np.asarray(pr['col'], dtype=np.float32)[:, :3]
        pi = np.asarray(pr['idx'], dtype=np.int32).reshape(-1, 3) + v_off
        vis_v.append(pv)
        vis_n.append(pn)
        vis_c.append(pc)
        vis_f.append(pi)
        v_off += pv.shape[0]
    wmesh._visual_vertices = np.concatenate(vis_v, axis=0)  # type: ignore[attr-defined]
    wmesh._visual_normals = np.concatenate(vis_n, axis=0)  # type: ignore[attr-defined]
    wmesh._visual_colors_rgb = np.concatenate(vis_c, axis=0)  # type: ignore[attr-defined]
    wmesh._visual_faces = np.concatenate(vis_f, axis=0)  # type: ignore[attr-defined]
    return wmesh


if __name__ == '__main__':
    report = build_concept_a_glb()
    print(json.dumps(report, indent=2))
