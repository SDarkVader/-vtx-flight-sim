"""Parasite-drag component build-up of the RC-01 airframe computed from its own meshes.

Method (Raymer, Aircraft Design, ch. 12 component build-up; Hoerner, Fluid-Dynamic Drag, for the canopy):
    CdA_parasite = sum_c Cf_c * FF_c * Q_c * S_wet,c  +  canopy protuberance  (subsonic, M ~ 0.1)
  * Cf: fully turbulent flat plate 0.455 / (log10 Re)^2.58 (conservative: no laminar run credited),
    Re limited by the surface-roughness cut-off Re_cut = 38.21 (l / k)^1.053, so the skin material and
    finish enter through k.
  * FF: streamlined bodies 1 + 60/f^3 + f/400 (f = l / d_eq); aerofoil surfaces 1 + 2 t/c + 60 (t/c)^4;
  * Q: interference factors for pods, struts, ducts and tail junctions.
  * Canopy: protuberance on the hull, Hoerner-type frontal-area coefficient from its fineness and
    windscreen rake (spec_math.canopy_and_craft_cd0), on the frontal area it adds above the hull.
Every geometric input (wetted area, length, frontal area, fineness, rake, chord) is measured on the
mesh, so changing the canopy or body shape changes the drag through the geometry only.
"""
from __future__ import annotations

import math
import pathlib
from typing import Any

import numpy as np

from vtx.ricochet.hull_geometry import load_glb_watertight_mesh
from vtx.ricochet.spec_math import canopy_and_craft_cd0

NU_AIR = 1.46e-5  # m^2/s, ISA sea level
S_REF_M2 = 15.5
LEAKAGE_PROTUBERANCE_FRACTION = 0.05

# Equivalent sand-grain roughness k [m] (Raymer table 12.5 order of magnitude; finish, not just material)
SURFACE_FINISH_K_M = {
    'camouflage_paint': 1.015e-5,
    'smooth_paint': 0.634e-5,
    'production_sheet_metal': 0.405e-5,
    'polished_sheet_metal': 0.152e-5,
    'smooth_molded_composite': 0.052e-5,
    'polished_transparency': 0.052e-5,  # thermoformed acrylic / polycarbonate, hard-coated: optically smooth
}

# node -> (kind, interference Q, t/c for aerofoil kinds, finish)
COMPONENTS: dict[str, tuple[str, float, float, str]] = {
    'Ricochet_ConceptA_Hull_Cabin': ('hull', 1.0, 0.0, 'smooth_molded_composite'),
    'Ricochet_Canopy_Glass': ('canopy', 1.0, 0.0, 'polished_transparency'),
    'Ricochet_Sponson_Port': ('pod', 1.25, 0.0, 'smooth_molded_composite'),
    'Ricochet_Sponson_Stbd': ('pod', 1.25, 0.0, 'smooth_molded_composite'),
    'Ricochet_Wing_Port': ('aerofoil', 1.0, 0.145, 'smooth_molded_composite'),
    'Ricochet_Wing_Stbd': ('aerofoil', 1.0, 0.145, 'smooth_molded_composite'),
    'Ricochet_Aileron_Port': ('aerofoil', 1.0, 0.145, 'smooth_molded_composite'),
    'Ricochet_Aileron_Stbd': ('aerofoil', 1.0, 0.145, 'smooth_molded_composite'),
    'Ricochet_Winglet_Port': ('aerofoil', 1.05, 0.11, 'smooth_molded_composite'),
    'Ricochet_Winglet_Stbd': ('aerofoil', 1.05, 0.11, 'smooth_molded_composite'),
    'Ricochet_Strut_Port': ('aerofoil', 1.2, 0.24, 'smooth_molded_composite'),
    'Ricochet_Strut_Stbd': ('aerofoil', 1.2, 0.24, 'smooth_molded_composite'),
    'Ricochet_Tail_Pylon_T_Tail': ('aerofoil', 1.05, 0.13, 'smooth_molded_composite'),
    'Ricochet_Elevator': ('aerofoil', 1.05, 0.11, 'smooth_molded_composite'),
    'Ricochet_Rudder': ('aerofoil', 1.05, 0.125, 'smooth_molded_composite'),
    'Ricochet_Duct_Port': ('duct', 1.3, 0.11, 'smooth_molded_composite'),
    'Ricochet_Duct_Stbd': ('duct', 1.3, 0.11, 'smooth_molded_composite'),
    'Ricochet_Reverse_Bucket_Port': ('aerofoil', 1.3, 0.10, 'smooth_molded_composite'),
    'Ricochet_Reverse_Bucket_Stbd': ('aerofoil', 1.3, 0.10, 'smooth_molded_composite'),
    # Internal / enclosed: fan rotor and spinner are in the duct flow (fan losses), cockpit items are under the canopy
}
FAN_CENTRES_VTX = {'Ricochet_Duct_Port': (-2.05, 0.78, 1.56), 'Ricochet_Duct_Stbd': (-2.05, -0.78, 1.56)}


def _tri_areas_normals(v: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    cr = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cr, axis=1)
    n = cr / np.maximum(2.0 * area[:, None], 1e-15)
    return area, n, (a + b + c) / 3.0


def projected_mask(v: np.ndarray, f: np.ndarray, cell: float, origin: tuple[float, float], shape: tuple[int, int]) -> np.ndarray:
    """Rasterise the (y, z) projection of a triangle mesh onto a grid (cell centres inside any triangle)."""
    mask = np.zeros(shape, dtype=bool)
    y0, z0 = origin
    P = v[:, 1:3]
    for tri in f:
        p = P[tri]
        lo = np.floor((p.min(axis=0) - (y0, z0)) / cell).astype(int)
        hi = np.ceil((p.max(axis=0) - (y0, z0)) / cell).astype(int)
        lo = np.maximum(lo, 0)
        hi = np.minimum(hi, np.array(shape) - 1)
        if np.any(hi < lo):
            continue
        ys = y0 + (np.arange(lo[0], hi[0] + 1) + 0.5) * cell
        zs = z0 + (np.arange(lo[1], hi[1] + 1) + 0.5) * cell
        Y, Z = np.meshgrid(ys, zs, indexing='ij')
        (ya, za), (yb, zb), (yc, zc) = p
        d = (zb - zc) * (ya - yc) + (yc - yb) * (za - zc)
        if abs(d) < 1e-14:
            continue
        l1 = ((zb - zc) * (Y - yc) + (yc - yb) * (Z - zc)) / d
        l2 = ((zc - za) * (Y - yc) + (ya - yc) * (Z - zc)) / d
        inside = (l1 >= 0) & (l2 >= 0) & (1.0 - l1 - l2 >= 0)
        mask[lo[0]:hi[0] + 1, lo[1]:hi[1] + 1] |= inside
    return mask


def cf_turbulent(re: float) -> float:
    return 0.455 / (math.log10(max(re, 1e4)) ** 2.58)


def _cf(speed: float, length: float, finish: str) -> tuple[float, float, float]:
    k = SURFACE_FINISH_K_M[finish]
    re = speed * length / NU_AIR
    re_cut = 38.21 * (length / k) ** 1.053
    return cf_turbulent(min(re, re_cut)), re, re_cut


def _canopy_rake_deg(v: np.ndarray) -> float:
    """Windscreen rake from horizontal: slope of the canopy crown line ahead of its peak (10-80 % of height).

    The crown line is the highest vertex at each station, so the result does not depend on which off-centre
    vertices fall near the centreline at the narrow ends."""
    xr = np.round(v[:, 0], 4)
    ux, inv = np.unique(xr, return_inverse=True)
    zmax = np.full(len(ux), -np.inf)
    np.maximum.at(zmax, inv, v[:, 2])
    x, z = ux, zmax
    i_pk = int(np.argmax(z))
    xf, zf = x[i_pk:], z[i_pk:]
    z_lo, z_hi = float(zf.min()), float(zf.max())
    sel = (zf >= z_lo + 0.1 * (z_hi - z_lo)) & (zf <= z_lo + 0.8 * (z_hi - z_lo))
    if sel.sum() < 2:
        return 30.0
    p = np.polyfit(xf[sel], zf[sel], 1)
    return float(math.degrees(math.atan(abs(p[0]))))


def build_up(glb_path: str | pathlib.Path, speed_mps: float = 30.0, finishes: dict[str, str] | None = None,
             canopy_sill: Any = None) -> dict[str, Any]:
    """Return per-component and total parasite CdA [m^2] at ``speed_mps`` for the airframe in ``glb_path``.

    ``canopy_sill(x) -> (half_width, z_sill)`` describes the cockpit opening, so the hull tub faces under the
    canopy are excluded from the hull's exposed wetted area.
    """
    finishes = finishes or {}
    meshes = {n: load_glb_watertight_mesh(glb_path, node_name=n) for n in COMPONENTS}
    out: dict[str, Any] = {'speed_mps': speed_mps, 'components': {}}
    cell = 0.005
    hull = meshes['Ricochet_ConceptA_Hull_Cabin']
    can = meshes['Ricochet_Canopy_Glass']
    vy = np.concatenate([hull.vertices[:, 1], can.vertices[:, 1]])
    vz = np.concatenate([hull.vertices[:, 2], can.vertices[:, 2]])
    origin = (float(vy.min()) - 0.02, float(vz.min()) - 0.02)
    shape = (int((vy.max() - vy.min() + 0.04) / cell) + 1, int((vz.max() - vz.min() + 0.04) / cell) + 1)
    m_h = projected_mask(hull.vertices, hull.faces, cell, origin, shape)
    m_c = projected_mask(can.vertices, can.faces, cell, origin, shape)
    a_hull = float(m_h.sum()) * cell * cell
    a_canopy_excess = float((m_c & ~m_h).sum()) * cell * cell
    total = 0.0
    for name, (kind, q_int, tc, finish) in COMPONENTS.items():
        mesh = meshes[name]
        v, f = mesh.vertices, mesh.faces
        area, nrm, cen = _tri_areas_normals(v, f)
        ext = v.max(axis=0) - v.min(axis=0)
        fin = finishes.get(name, finish)
        rec: dict[str, Any] = {'kind': kind, 'Q': q_int, 'finish': fin}
        if kind == 'canopy':
            s_out = float(area.sum()) * 0.5  # double-walled shell: outer skin only
            length = float(ext[0])
            d_eq = math.sqrt(4.0 * max(a_canopy_excess, 1e-6) / math.pi)
            f_r = length / d_eq
            rake = _canopy_rake_deg(v)
            cdc = canopy_and_craft_cd0(windshield_rake_deg=rake, canopy_fineness_ratio=f_r,
                                       frontal_canopy_area_m2=a_canopy_excess)
            cda = cdc['cd_canopy_local'] * a_canopy_excess
            rec.update(wetted_m2=round(s_out, 3), length_m=round(length, 3), frontal_excess_m2=round(a_canopy_excess, 4),
                       fineness=round(f_r, 2), rake_deg=round(rake, 1), cd_frontal=round(cdc['cd_canopy_local'], 4),
                       height_m=round(float(v[:, 2].max()), 3), max_width_m=round(float(ext[1]), 3))
        else:
            s_wet = float(area.sum())
            if kind == 'hull' and canopy_sill is not None:
                # exclude cockpit tub / coaming faces enclosed by the canopy
                hw, zs = canopy_sill(cen[:, 0])
                inside = (cen[:, 0] > -0.25) & (cen[:, 0] < 2.85) & (np.abs(cen[:, 1]) < hw + 0.06) & (cen[:, 2] > zs - 0.06) \
                    | ((cen[:, 0] > -0.25) & (cen[:, 0] < 2.85) & (np.abs(cen[:, 1]) < hw) & (nrm[:, 2] > 0.5) & (cen[:, 2] > 0.5))
                s_wet = float(area[~inside].sum())
                rec['tub_excluded_m2'] = round(float(area[inside].sum()), 3)
            if kind == 'hull':
                # Flat aft-facing faces (transom / blunt base) carry base drag, not skin friction (Raymer 12.5.6)
                base = (nrm[:, 0] < -0.95) & ~inside if canopy_sill is not None else (nrm[:, 0] < -0.95)
                a_base = float((area[base] * -nrm[base, 0]).sum())
                s_wet -= float(area[base].sum())
                mach = speed_mps / 340.3
                cda_base = (0.139 + 0.419 * (mach - 0.161) ** 2) * a_base
                # Aft-body upsweep (Raymer eq. 12.36): centreline slope aft of the maximum section
                xs = np.linspace(float(v[:, 0].min()) + 0.05, float(v[:, 0].max()) - 0.05, 40)
                zc, ar = [], []
                for xi in xs:
                    sl = v[np.abs(v[:, 0] - xi) < 0.04]
                    zc.append(0.5 * (sl[:, 2].min() + sl[:, 2].max()) if len(sl) else np.nan)
                    ar.append((sl[:, 2].max() - sl[:, 2].min()) * 2 * np.abs(sl[:, 1]).max() if len(sl) else 0.0)
                zc, ar = np.asarray(zc), np.asarray(ar)
                i_max = int(np.nanargmax(ar))
                aft = slice(0, i_max + 1)
                ok = np.isfinite(zc[aft])
                slope = float(np.polyfit(xs[aft][ok], zc[aft][ok], 1)[0]) if ok.sum() > 2 else 0.0
                upsweep = max(0.0, -slope)  # centreline rising toward the tail (x decreasing)
                u = math.atan(upsweep)
                cda_upsweep = 3.83 * u ** 2.5 * a_hull
                rec.update(base_area_m2=round(a_base, 4), CdA_base_m2=round(cda_base, 5),
                           upsweep_deg=round(math.degrees(u), 2), CdA_upsweep_m2=round(cda_upsweep, 5))
            if kind == 'duct':
                c0 = np.asarray(FAN_CENTRES_VTX[name])
                radial = cen[:, 1:3] - c0[1:3]
                outer = np.einsum('ij,ij->i', nrm[:, 1:3], radial) > 0.0
                s_wet = float(area[outer].sum())
            if kind in ('hull', 'pod', 'duct'):
                length = float(ext[0])
                if kind == 'hull':
                    a_max = a_hull
                elif kind == 'pod':
                    m_p = projected_mask(v, f, cell, (float(v[:, 1].min()) - 0.02, float(v[:, 2].min()) - 0.02),
                                         (int(ext[1] / cell) + 10, int(ext[2] / cell) + 10))
                    a_max = float(m_p.sum()) * cell * cell
                else:
                    a_max = math.pi * 0.25 * (ext[1] ** 2)
                d_eq = math.sqrt(4.0 * a_max / math.pi)
                f_r = length / max(d_eq, 1e-6)
                ff = 1.0 + 60.0 / f_r ** 3 + f_r / 400.0 if kind != 'duct' else 1.0 + 2.0 * tc + 60.0 * tc ** 4
                lref = length
                rec.update(frontal_m2=round(a_max, 4), fineness=round(f_r, 2))
            else:
                span_axis = 1 if ext[1] >= ext[2] else 2
                span = float(ext[span_axis])
                planform = s_wet / 2.04
                lref = planform / max(span, 1e-3)
                ff = 1.0 + 2.0 * tc + 60.0 * tc ** 4
                rec.update(span_m=round(span, 3), mean_chord_m=round(lref, 3), t_c=tc)
            cf, re, re_cut = _cf(speed_mps, lref, fin)
            cda = cf * ff * q_int * s_wet
            if kind == 'hull':
                rec['CdA_friction_form_m2'] = round(cda, 5)
                cda += rec['CdA_base_m2'] + rec['CdA_upsweep_m2']
            rec.update(wetted_m2=round(s_wet, 3), ref_length_m=round(lref, 3), Re=float(f'{re:.3g}'),
                       roughness_limited=bool(re_cut < re), Cf=round(cf, 5), FF=round(ff, 3))
        rec['CdA_m2'] = round(cda, 5)
        out['components'][name] = rec
        total += cda
    # Leakage and protuberances (hinge gaps, fasteners, antennae, vents): Raymer 2-5 % for propeller aircraft;
    # the upper bound is taken because the craft also carries hatch seals and water-drain fittings.
    out['leakage_protuberance_fraction'] = LEAKAGE_PROTUBERANCE_FRACTION
    out['CdA_components_m2'] = round(total, 4)
    total *= 1.0 + LEAKAGE_PROTUBERANCE_FRACTION
    out['hull_frontal_m2'] = round(a_hull, 4)
    out['canopy_frontal_excess_m2'] = round(a_canopy_excess, 4)
    out['CdA_parasite_m2'] = round(total, 4)
    out['Cd0_on_S_ref'] = round(total / S_REF_M2, 5)
    out['drag_n_at_speed'] = round(0.5 * 1.225 * speed_mps ** 2 * total, 1)
    return out
