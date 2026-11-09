"""Munk cross-check: vortex-lattice (horseshoe) model of the hull planform w(x) as a flat lifting surface (free air).
Gives body-alone lift slope and centre of pressure -> pitching moment about the CG, independent of slender-body theory."""
import json, math, sys, numpy as np
D = json.load(open(sys.argv[1] + '/m4_cad.json')); X = np.array(D['x']); Wd = np.array(D['w'])
def vlm(xmin, xmax, dx=0.05, dy=0.0625):
    xs = np.arange(xmax, xmin, -dx); ys = np.arange(-1.25 + dy / 2, 1.25, dy); P = []
    for x in xs:
        half = np.interp(x - dx / 2, X, Wd) / 2
        for y in ys:
            if abs(y) <= half: P.append((x, y))
    P = np.array(P); n = len(P)
    # panel: LE at x, TE at x-dx (flow toward -x). bound vortex at x - dx/4, control point at x - 3dx/4
    xb = P[:, 0] - dx / 4; xc = P[:, 0] - 3 * dx / 4; ya = P[:, 1] - dy / 2; yb = P[:, 1] + dy / 2
    def seg(px, py, x1, y1, x2, y2):          # z-velocity at (px,py,0) from a vortex segment in the plane, unit strength (Biot-Savart)
        r1x, r1y = px - x1, py - y1; r2x, r2y = px - x2, py - y2; r0x, r0y = x2 - x1, y2 - y1
        cz = r1x * r2y - r1y * r2x; r1 = np.hypot(r1x, r1y); r2 = np.hypot(r2x, r2y)
        with np.errstate(divide='ignore', invalid='ignore'):
            k = (r0x * (r1x / r1 - r2x / r2) + r0y * (r1y / r1 - r2y / r2)) / (4 * math.pi * cz)
        return np.where(np.abs(cz) < 1e-10, 0.0, k)
    BIG = 1e3
    px = xc[:, None]; py = P[:, 1][:, None]
    A = (seg(px, py, xb[None] - BIG, ya[None], xb[None], ya[None]) + seg(px, py, xb[None], ya[None], xb[None], yb[None]) + seg(px, py, xb[None], yb[None], xb[None] - BIG, yb[None]))
    G = np.linalg.solve(A, -np.ones(n))      # unit freestream normal velocity (alpha = 1 rad, V = 1)
    # Kutta-Joukowski: lift per panel = rho V Gamma dy (sign: G negative for upward lift with this convention)
    l = -G * dy; CLa = 2 * l.sum() / (P[:, 0].size and (dx * dy * n)); xcp = (l * xb).sum() / l.sum()
    return CLa, xcp, dx * dy * n
x_cg = -0.152; S_ref, c_ref = 3.934, 0.872; x_le = -0.806 + 0.218
for name, (a, b) in {'whole hull planform': (X.min(), X.max()), 'forebody (nose -> wing LE)': (x_le, X.max())}.items():
    CLa, xcp, Sp = vlm(a, b)
    dM = CLa * Sp * (xcp - x_cg)                       # per rad per unit q, nose-up if CP ahead of CG
    print(f'{name}: area {Sp:.2f} m2, CL_a {CLa:.3f}/rad (on own area), lift slope {CLa*Sp:.2f} q N/rad, CP x {xcp:+.3f} m -> dM/da about CG {dM:+.2f} q N m/rad -> dCm_a {dM/(S_ref*c_ref):+.2f}/rad')
