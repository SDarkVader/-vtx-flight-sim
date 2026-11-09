"""Hull lift / Munk moment coefficients for the Phantom A10 body (overlay inputs/phantom_overlays/hull_lift_v1.json).

The plant's wing reference area spans the body (screening basis), so the body region under the wing is already
carried by the wing. What the plant lacks is the forebody: the low-aspect-ratio lifting body ahead of the wing,
which produces the destabilising Munk-type pitching moment (and its yaw counterpart on the side profile).

Method: body-only CAD envelope from public/assets/phantom-a10.glb (exact plane sections, same part exclusions as
the parameter file's projected areas), then a horseshoe vortex lattice of
  * pitch: the forebody plan form (nose -> wing MAC leading edge), span = section width;
  * yaw:   the side profile ahead of the fins (span = section height), no wing on the side.
Free air, flat-plate (thin) lifting surface, no ground effect, no thickness or separation. Cross-checked against
Multhopp's slender-body fuselage moment (reported alongside).

  python tools/phantom/hull_lift_vlm.py            # writes evidence/phantom/hull_lift_vlm.json
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GLB = ROOT / 'public/assets/phantom-a10.glb'
OUT = ROOT / 'evidence/phantom/hull_lift_vlm.json'
EXCLUDE = ('WHEEL_', 'LEG_', 'A10_WING', 'A10_CANARD', 'CFD_', 'A10_HATCH', 'PHANTOM_FL_', 'PHANTOM_FR_', 'PHANTOM_RL_',
           'PHANTOM_RR_', 'JOINT_', 'SEAT_')
X_CG = -0.152                       # phantom-fx ledger CG (body frame)
X_WING_LE = -0.806 + 0.25 * 0.872   # A10 handover: MAC aerodynamic centre + c/4
X_FIN_LE = -1.86                    # fin AC -2.06 m (parameter file) + ~0.2 m
S_REF, C_REF = 3.934, 0.872         # A10 handover wing reference


def sections(n=99):
    import trimesh
    sc = trimesh.load(GLB)
    meshes = []
    for name in sc.graph.nodes_geometry:
        if name.startswith(EXCLUDE):
            continue
        T, g = sc.graph[name]
        m = sc.geometry[g].copy(); m.apply_transform(T); meshes.append(m)
    xs = np.linspace(-2.44, 2.45, n); out = []
    for x in xs:
        ys, zs = [], []
        for m in meshes:
            if m.bounds[0][0] > x or m.bounds[1][0] < x:
                continue
            sec = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
            if sec is None:
                continue
            v = sec.vertices; ys += [v[:, 1].min(), v[:, 1].max()]; zs += [v[:, 2].min(), v[:, 2].max()]
        out.append((float(x), min(ys) if ys else 0.0, max(ys) if ys else 0.0, min(zs) if zs else 0.0, max(zs) if zs else 0.0))
    return np.array(out)


def vlm(x_st, lo, hi, x_min, x_max, dx=0.05, ds=0.0625):
    """Flat lifting surface in the (x, s) plane, span interval [lo(x), hi(x)], flow toward -x.
    Returns lift slope (per rad, in units of dynamic pressure: N/rad per Pa = m^2) and centre of pressure x."""
    s_all = np.arange(min(lo.min(), 0) + ds / 2, max(hi.max(), 0), ds)
    P = []
    for x in np.arange(x_max, x_min, -dx):
        a, b = np.interp(x - dx / 2, x_st, lo), np.interp(x - dx / 2, x_st, hi)
        P += [(x, s) for s in s_all if a <= s <= b]
    P = np.array(P); n = len(P)
    xb = P[:, 0] - dx / 4; xc = P[:, 0] - 3 * dx / 4; sa = P[:, 1] - ds / 2; sb = P[:, 1] + ds / 2

    def seg(px, py, x1, y1, x2, y2):
        r1x, r1y, r2x, r2y = px - x1, py - y1, px - x2, py - y2
        r0x, r0y = x2 - x1, y2 - y1
        cz = r1x * r2y - r1y * r2x; r1 = np.hypot(r1x, r1y); r2 = np.hypot(r2x, r2y)
        with np.errstate(divide='ignore', invalid='ignore'):
            k = (r0x * (r1x / r1 - r2x / r2) + r0y * (r1y / r1 - r2y / r2)) / (4 * math.pi * cz)
        return np.where(np.abs(cz) < 1e-10, 0.0, k)
    far = 1e3; px = xc[:, None]; py = P[:, 1][:, None]
    A = (seg(px, py, xb[None] - far, sa[None], xb[None], sa[None]) + seg(px, py, xb[None], sa[None], xb[None], sb[None])
         + seg(px, py, xb[None], sb[None], xb[None] - far, sb[None]))
    G = np.linalg.solve(A, -np.ones(n))
    lift = -G * ds                                   # Kutta-Joukowski, V = 1, alpha = 1 rad -> per unit rho V^2 ... /q gives 2x
    K = 2 * lift.sum()                               # dL/dalpha / q  [m^2]
    return dict(K_m2=float(K), x_cp_m=float((lift * xb).sum() / lift.sum()), area_m2=float(dx * ds * n), panels=n)


def main():
    S = sections()
    x, ylo, yhi, zlo, zhi = S.T
    w = yhi - ylo; h = zhi - zlo
    plan = float(np.trapezoid(w, x)); side = float(np.trapezoid(h, x))
    pitch = vlm(x, ylo, yhi, X_WING_LE, x.max())
    pitch_whole = vlm(x, ylo, yhi, x.min(), x.max())
    yaw = vlm(x, zlo, zhi, X_FIN_LE, x.max())
    fore = x >= X_WING_LE
    multhopp = float(2 * np.trapezoid(math.pi / 4 * w[fore] ** 2, x[fore]))     # dM/dalpha / q, forebody, factor 1
    res = dict(
        method='horseshoe vortex lattice on the body-only CAD envelope; free air; thin surface; no ground effect',
        glb=str(GLB.relative_to(ROOT)), excluded_parts=list(EXCLUDE),
        envelope=dict(plan_area_m2=plan, side_area_m2=side, parameter_file_plan_m2=10.138, parameter_file_side_m2=3.9576,
                      length_m=float(x.max() - x.min()), max_width_m=float(w.max()), max_height_m=float(h.max())),
        x_cg_m=X_CG, x_wing_le_m=X_WING_LE, x_fin_le_m=X_FIN_LE,
        pitch_forebody=dict(pitch, dM_dalpha_about_cg_m3=pitch['K_m2'] * (pitch['x_cp_m'] - X_CG),
                            dCm_dalpha_per_rad=pitch['K_m2'] * (pitch['x_cp_m'] - X_CG) / (S_REF * C_REF)),
        pitch_whole_body_check=dict(pitch_whole, dCm_dalpha_per_rad=pitch_whole['K_m2'] * (pitch_whole['x_cp_m'] - X_CG) / (S_REF * C_REF)),
        yaw_side_profile_ahead_of_fins=dict(yaw, dN_dbeta_about_cg_m3=yaw['K_m2'] * (yaw['x_cp_m'] - X_CG)),
        multhopp_forebody_check=dict(dM_dalpha_m3=multhopp, dCm_dalpha_per_rad=multhopp / (S_REF * C_REF)),
        sections=[dict(x=round(a, 4), ylo=round(b, 4), yhi=round(c, 4), zlo=round(d, 4), zhi=round(e, 4)) for a, b, c, d, e in S])
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != 'sections'}, indent=1))


if __name__ == '__main__':
    sys.exit(main())
