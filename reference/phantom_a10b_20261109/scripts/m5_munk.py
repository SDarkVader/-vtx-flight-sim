"""Munk step 5: hull Munk moment for the A10 body envelope (free air, no ground effect).
Sections treated as ellipses (w x h): vertical added mass per unit length = rho*pi*(w/2)^2 (exact for an ellipse, independent of h).
(A) closed-body slender-body/Munk:  M = q sin(2a) (Vaz - k1 Vol),  Vaz = int pi/4 w^2 dx
(B) Multhopp-style split: forebody (nose -> wing root LE) factor 1 (no upwash credit, so a lower bound for that part);
    wing-covered body omitted (carried by the plant's wing S_ref, which spans the body); aft body factor (x/l_h)(1 - de/da)."""
import json, math, numpy as np, sys
D = json.load(open(sys.argv[1] + '/m4_cad.json')); x = np.array(D['x']); w = np.array(D['w']); h = np.array(D['h'])
rho = 1.225; S_ref, c_ref = 3.934, 0.872                # plant wing reference (A10 handover)
x_le, c_w = -0.806 + 0.25 * 0.872, 0.872; x_te = x_le - c_w; x_tail = -2.055      # wing MAC LE/TE, stabilator hinge
Sa = math.pi / 4 * w ** 2; Vaz = np.trapezoid(Sa, x); Vol = np.trapezoid(math.pi / 4 * w * h, x)
L = x.max() - x.min(); Amax = (math.pi / 4 * w * h).max(); De = math.sqrt(4 * Amax / math.pi); ld = L / De
e = math.sqrt(1 - (1 / ld) ** 2); a0 = 2 * (1 - e * e) / e ** 3 * (0.5 * math.log((1 + e) / (1 - e)) - e); k1 = a0 / (2 - a0)
fore = x >= x_le; aft = x <= x_te; l_h = x_te - x_tail
Vf = np.trapezoid(Sa[fore], x[fore])
dede = 0.45
fa = np.clip((x_te - x[aft]) / l_h, 0, 1) * (1 - dede); Va_aft = np.trapezoid(Sa[aft] * fa, x[aft])
out = dict(length_m=L, Vaz_m3=Vaz, volume_ellipse_sections_m3=Vol, L_over_Deq=ld, k1_prolate=k1, Vax_m3=k1 * Vol,
           forebody_Va_m3=Vf, aft_Va_m3_with_downwash=Va_aft, wing_LE_x=x_le, wing_TE_x=x_te)
cases = {'A closed-body potential (upper bound)': Vaz - k1 * Vol, 'B Multhopp split, forebody factor 1 + aft': Vf + Va_aft, 'B forebody only': Vf}
CMA = {'70089cca (P6 on)': -2.674, 'b835295b (P6 off)': -2.232}
print(json.dumps({k: round(v, 3) for k, v in out.items()}))
for name, Va in cases.items():
    dM = 2 * Va                               # dM/dalpha per rad, per unit dynamic pressure (small alpha)
    dCm = dM / (S_ref * c_ref)
    print(f'\n{name}: Va = {Va:.2f} m3 -> dM/da = {dM:.2f} q N m/rad -> dCm_a = +{dCm:.2f}/rad (S_ref {S_ref}, c {c_ref})')
    for k, cm in CMA.items(): print(f'    {k}: plant Cm_a {cm:+.2f} -> with Munk {cm + dCm:+.2f}/rad', '(UNSTABLE)' if cm + dCm > 0 else '')
    for V in (70, 94, 120):
        q = 0.5 * rho * V * V
        print('    V %3d m/s  q %5.0f Pa: M_munk at a=5 deg %6.0f, 10 deg %6.0f, 15 deg %6.0f N m (nose-up)' % (V, q, *(q * math.sin(2 * math.radians(a)) * Va for a in (5, 10, 15))))
json.dump(dict(out, cases=cases), open(sys.argv[1] + '/m5_munk.json', 'w'))
