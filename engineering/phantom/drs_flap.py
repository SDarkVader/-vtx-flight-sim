"""VTX Phantom rear DRS / airbrake flap: geometry (single source of truth) and road-mode pitch balance.

The flap is a split, inverted cambered blade spanning between the two raked fins (which act as its
end plates). Both halves share one hinge axis and are joined by a central coaxial rotary EMA, so they move
together:
  * road / cruise: rest incidence REST_DEG (trailing edge up) -> rear downforce;
  * braking: trailing edge rises a further AIRBRAKE_DEG -> stalled plate, drag plus downforce.

The flap is NOT in the MuJoCo plant yet. This module evaluates it with the plant's own aerodynamic model
(vtx.phantom.surface_aero: SurfaceAero for canards, fins and body drag; coefficients() for the flap). It
adds the two terms the plant does not model:
  * the hull Munk moment, 2 q V_munk alpha, with the same definition and V_munk = 4.35 m^3 x 0.85
    (SYNTHETIC) as engineering/phantom/wing_loads.py;
  * the tractive force at the tyre contact that balances drag at constant speed.
It then solves the front/rear axle load changes. "Nose rise" here means front-axle unloading with speed.

Run:  PYTHONPATH=src python engineering/phantom/drs_flap.py      (writes evidence/phantom/drs_balance.json)
Screening analysis only: no CFD, no ground-effect or body-wake model beyond the ETA_Q factor below.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- geometry (Z-up body frame, metres)
SECTION = dict(name='NACA 4412, inverted', m=0.04, p=0.4, t=0.12)
CHORD = 0.240
PIVOT = (-2.055, 1.130)            # hinge axis (x, z), at 25 % chord = section aerodynamic centre
LE_X = PIVOT[0] + 0.25 * CHORD     # -1.995: inside the fin chord at this height (fin x -2.285 .. -1.963)
REST_DEG = 6.0                     # trailing edge up (downforce incidence)
AIRBRAKE_DEG = 55.0                # extra trailing-edge-up travel for braking
Y_TIP = 0.497                      # 9 mm clear of the fin inner face at the flap's lowest point
Y_ROOT = 0.040                     # split: the central actuator sits in |y| < 0.036
FIN_ABOVE = 0.33                   # fin height above the flap (end-plate height for the AR correction)
ETA_Q = 0.85                       # SYNTHETIC: dynamic-pressure ratio at the flap (cabin/deck wake)
GURNEY_H = 0.010                   # 10 mm Gurney lip on the trailing edge (visual; its delta-CL is folded into ALPHA0)

SPAN_GEOM = 2 * Y_TIP                       # tip to tip; the central 80 mm gap is closed by the actuator drum
AREA = 2 * (Y_TIP - Y_ROOT) * CHORD         # 0.219 m^2 of blade
AR = SPAN_GEOM ** 2 / (SPAN_GEOM * CHORD)
AR_EFF = AR * (1 + 1.9 * FIN_ABOVE / SPAN_GEOM)          # Hoerner end-plate correction
CLA = 2 * math.pi * AR_EFF / (2 + math.sqrt(AR_EFF ** 2 + 4))   # Helmbold low-AR lift slope, per rad
ALPHA0_DEG = 4.0 + 1.5             # inverted 4412 zero-lift angle (+4.0 deg) + Gurney (~ +1.5 deg)
ALPHA_STALL_DEG = 12.0
CD0 = 0.012
K_IND = 1 / (math.pi * AR_EFF * 0.9)
CM_AC = 0.09                       # inverted 4412 (sign: trailing edge up about the hinge)


def naca4(n=48, m=SECTION['m'], p=SECTION['p'], t=SECTION['t'], inverted=True):
    """closed section, chord 1, LE at s=0, ordered upper TE -> LE -> lower TE; returns (s, z)."""
    beta = np.linspace(0, math.pi, n)
    s = 0.5 * (1 - np.cos(beta))
    yt = 5 * t * (0.2969 * np.sqrt(s) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1036 * s ** 4)
    yc = np.where(s < p, m / p ** 2 * (2 * p * s - s ** 2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * s - s ** 2))
    dyc = np.where(s < p, 2 * m / p ** 2 * (p - s), 2 * m / (1 - p) ** 2 * (p - s))
    th = np.arctan(dyc)
    xu, zu = s - yt * np.sin(th), yc + yt * np.cos(th)
    xl, zl = s + yt * np.sin(th), yc - yt * np.cos(th)
    if inverted:
        zu, zl = -zu, -zl
    xs = np.concatenate([xu[::-1], xl[1:]]); zs = np.concatenate([zu[::-1], zl[1:]])
    return xs, zs


def section_world(deg_te_up, n=48):
    """section points in the body x-z plane for a trailing-edge-up deflection (rest + travel)."""
    s, z = naca4(n)
    x_loc = -(s - 0.25) * CHORD          # chord runs aft (-x) from the LE; origin at the hinge (25 % c)
    z_loc = z * CHORD
    a = math.radians(deg_te_up)          # TE up: rotate +a about +y (x -> -z) puts the aft TE higher
    xr = x_loc * math.cos(a) + z_loc * math.sin(a)
    zr = -x_loc * math.sin(a) + z_loc * math.cos(a)
    return np.stack([PIVOT[0] + xr, PIVOT[1] + zr], 1)

# ------------------------------------------------------------------------------------- analysis


def _plant():
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from vtx.phantom.params import Params
    from vtx.phantom.ledger import PhantomLedger
    from vtx.phantom.surface_aero import SurfaceAero, Surface, coefficients
    P = Params('phantom')
    L = PhantomLedger(P)
    mp = L.mass_properties()
    return P, SurfaceAero(P), Surface, coefficients, mp


def evaluate(V, theta_deg, canard_deg, flap_te_up_deg, munk_factor, with_flap=True):
    """steady straight driving at V (m/s), body pitch theta (nose up +). Returns forces and axle load changes."""
    P, SA, Surface, coefficients, mp = _plant()
    th = math.radians(theta_deg)
    v_body = np.array([V * math.cos(th), 0.0, -V * math.sin(th)])
    zero = np.zeros(3)
    st = dict(wing_frac=dict(left=0.0, right=0.0), wing_locked=dict(left=False, right=False),
              flap=dict(left=0.0, right=0.0), aileron=dict(left=0.0, right=0.0),
              canard_pitch=dict(left=math.radians(canard_deg), right=math.radians(canard_deg)),
              canard_deployed=dict(left=True, right=True))
    r = SA.compute(v_body, zero, zero, st)
    F, Mo = r['force_body'].copy(), r['moment_body'].copy()
    parts = {s['name']: s['force_n'] for s in r['surfaces'] if 'force_n' in s}
    q = 0.5 * SA.rho * V * V
    if with_flap:
        a = math.radians(flap_te_up_deg)
        drs = Surface('drs', [PIVOT[0], 0.0, PIVOT[1]], [math.cos(a), 0, -math.sin(a)], [math.sin(a), 0, math.cos(a)], AREA, CLA,
                      math.radians(ALPHA0_DEG), math.radians(ALPHA_STALL_DEG), CD0, K_IND, 'drs')
        vp = v_body.copy()
        alpha = math.atan2(-(vp @ drs.n), vp @ drs.c)
        cl, cd, stall = coefficients(alpha, drs.cla, drs.alpha0, drs.alpha_stall, drs.cd0, drs.k_ind, SA.cn_fp, SA.M)
        Vn = np.linalg.norm(vp); ddir = -vp / Vn; span = np.cross(drs.c, drs.n); ldir = np.cross(ddir, span); ldir /= np.linalg.norm(ldir)
        qf = ETA_Q * q
        f = qf * AREA * (cl * ldir + cd * ddir)
        F += f; Mo += np.cross(drs.ac, f)
        # Attached: force at the AC (= hinge) plus the section couple. Inverted 4412 Cm_ac = +0.09 turns the LE up and the
        # TE down, i.e. a -y moment in this frame (+y turns +x toward -z). Stalled: force at the flat-plate centre of
        # pressure ~0.40 c, 0.15 c aft of the hinge. Hinge moment > 0 means it tries to close the flap (TE down).
        couple = -qf * AREA * CHORD * CM_AC
        r_cp = -0.15 * CHORD * drs.c
        m_cp = np.cross(r_cp, f)[1]
        Mo += np.array([0.0, (1 - stall) * couple + stall * m_cp, 0.0])
        hinge = -((1 - stall) * couple + stall * m_cp)
        parts['drs'] = f.tolist()
    else:
        alpha = cl = cd = stall = hinge = 0.0
    # hull Munk moment (nose up for nose-up attitude): body +y moment is nose-DOWN in this frame
    M_munk = 2 * q * 4.35 * munk_factor * th
    Mo += np.array([0.0, -M_munk, 0.0])
    # steady speed: tyres supply traction = -Fx at the ground (z = 0)
    T = np.array([-F[0], 0.0, 0.0])
    Mo += np.cross(np.array([mp['cg_m'][0], 0.0, 0.0]), T)
    # axle loads (vertical reactions at the pod hinge stations) balancing Fz and My about the origin
    xf, xr = P['pods.hinge_x_front_m'], P['pods.hinge_x_rear_m']
    # Nf + Nr = -Fz ; moment of reactions: My_react = -(xf Nf + xr Nr) * (-1) ... solve with cross products:
    # r x (0,0,N) has y = -x N ; equilibrium: Mo_y + (-xf Nf - xr Nr) = 0 ; Fz + Nf + Nr = 0
    A = np.array([[1.0, 1.0], [-xf, -xr]])
    b = np.array([-F[2], -Mo[1]])
    Nf, Nr = np.linalg.solve(A, b)
    m = mp['mass_kg']; g = 9.80665
    Wf = m * g * (mp['cg_m'][0] - xr) / (xf - xr)
    return dict(V=V, q_pa=q, theta_deg=theta_deg, canard_deg=canard_deg, flap_te_up_deg=flap_te_up_deg if with_flap else None,
                munk_factor=munk_factor, downforce_n=-F[2], drag_n=-F[0], dN_front_n=Nf, dN_rear_n=Nr,
                front_share_aero=Nf / (Nf + Nr) if abs(Nf + Nr) > 1e-9 else None, static_front_share=Wf / (m * g),
                munk_nose_up_nm=M_munk, drs=dict(alpha_deg=math.degrees(alpha), cl=cl, cd=cd, stall_blend=stall, hinge_moment_nm=hinge),
                parts=parts)


def solve_canard(V, theta_deg, munk_factor, target='static_share', with_flap=True, flap_deg=REST_DEG):
    """canard incidence that makes the aero load split equal the static split (no attitude change), or dN_front = 0."""
    def g(d):
        r = evaluate(V, theta_deg, d, flap_deg, munk_factor, with_flap)
        if target == 'zero_front_unload':
            return r['dN_front_n']
        return r['dN_front_n'] - r['static_front_share'] * (r['dN_front_n'] + r['dN_rear_n'])
    lo, hi = -20.0, 25.0
    glo, ghi = g(lo), g(hi)
    if glo * ghi > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi); gm = g(mid)
        if glo * gm <= 0:
            hi, ghi = mid, gm
        else:
            lo, glo = mid, gm
    return 0.5 * (lo + hi)


def main():
    P, SA, *_ , mp = _plant()
    V200 = 200 * 0.44704
    out = dict(geometry=dict(section=SECTION['name'], chord_m=CHORD, area_m2=AREA, span_m=SPAN_GEOM, AR=AR, AR_eff=AR_EFF,
                             cla_per_rad=CLA, alpha0_deg=ALPHA0_DEG, rest_te_up_deg=REST_DEG, airbrake_travel_deg=AIRBRAKE_DEG,
                             pivot_xz_m=PIVOT, eta_q=ETA_Q),
               vehicle=dict(mass_kg=mp['mass_kg'], cg_m=list(mp['cg_m']), pod_x_front=P['pods.hinge_x_front_m'], pod_x_rear=P['pods.hinge_x_rear_m']),
               cases=[])
    for theta in (2.9, 0.0):                  # as-drawn stance (flight test D-4) and level
        for mf in (0.60, 0.85, 1.10):         # Munk factor band around the SYNTHETIC 0.85
            row = dict(theta_deg=theta, munk_factor=mf)
            row['no_aero_devices'] = evaluate(V200, theta, 0.0, REST_DEG, mf, with_flap=False) | dict(note='canards deployed at 0 deg, no flap')
            row['flap_only'] = evaluate(V200, theta, 0.0, REST_DEG, mf)
            for tgt in ('zero_front_unload', 'static_share'):
                d = solve_canard(V200, theta, mf, tgt)
                row[f'canard_for_{tgt}_deg'] = d
                if d is not None:
                    row[f'with_canard_{tgt}'] = evaluate(V200, theta, d, REST_DEG, mf)
            out['cases'].append(row)
    # braking: airbrake at 200 mph and 100 km/h, canards at the static-share trim
    d = solve_canard(V200, 2.9, 0.85, 'static_share')
    if d is None:
        d = solve_canard(V200, 2.9, 0.85, 'zero_front_unload')
    out['braking_canard_deg'] = d
    out['braking'] = []
    for V in (V200, 100 / 3.6):
        rest = evaluate(V, 2.9, d, REST_DEG, 0.85)
        brk = evaluate(V, 2.9, d, REST_DEG + AIRBRAKE_DEG, 0.85)
        h_cg = mp['cg_m'][2]
        out['braking'].append(dict(V=V, rest=rest, airbrake=brk,
                                   extra_drag_n=brk['drag_n'] - rest['drag_n'], extra_downforce_n=brk['downforce_n'] - rest['downforce_n'],
                                   decel_g_from_airbrake=(brk['drag_n'] - rest['drag_n']) / (mp['mass_kg'] * 9.80665),
                                   brake_dive_moment_at_1g_nm=mp['mass_kg'] * 9.80665 * h_cg,
                                   hinge_moment_nm=brk['drs']['hinge_moment_nm']))
    path = ROOT / 'evidence/phantom/drs_balance.json'
    path.write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == '__main__':
    o = main()
    g = o['geometry']
    print(f"flap: {g['section']}, c={g['chord_m']} m, S={g['area_m2']:.3f} m2, AR={g['AR']:.2f} -> AR_eff={g['AR_eff']:.2f}, CLa={g['cla_per_rad']:.2f}/rad")
    print(f"vehicle: m={o['vehicle']['mass_kg']:.0f} kg, cg x={o['vehicle']['cg_m'][0]:.3f} z={o['vehicle']['cg_m'][2]:.3f}")
    for c in o['cases']:
        a, b = c['no_aero_devices'], c['flap_only']
        print(f"\ntheta {c['theta_deg']} deg, Munk x{c['munk_factor']}: (at 200 mph)")
        print(f"  no flap, canards 0:   dN_front {a['dN_front_n']:+7.0f} N  dN_rear {a['dN_rear_n']:+7.0f} N  Munk {a['munk_nose_up_nm']:6.0f} N m")
        print(f"  flap at rest:         dN_front {b['dN_front_n']:+7.0f} N  dN_rear {b['dN_rear_n']:+7.0f} N  flap CL {b['drs']['cl']:+.2f}")
        for t in ('zero_front_unload', 'static_share'):
            d = c[f'canard_for_{t}_deg']
            if d is None:
                print(f"  canard for {t}: not reachable in -20..+25 deg"); continue
            r = c[f'with_canard_{t}']
            print(f"  canard {d:+6.2f} deg ({t}): dN_front {r['dN_front_n']:+7.0f}  dN_rear {r['dN_rear_n']:+7.0f}  downforce {r['downforce_n']:6.0f} N  drag {r['drag_n']:6.0f} N")
    for bk in o['braking']:
        print(f"\nairbrake at {bk['V']:.1f} m/s: +drag {bk['extra_drag_n']:.0f} N ({bk['decel_g_from_airbrake']:.3f} g), +downforce {bk['extra_downforce_n']:.0f} N, "
              f"dN_front {bk['airbrake']['dN_front_n'] - bk['rest']['dN_front_n']:+.0f} N, hinge {bk['hinge_moment_nm']:.0f} N m; "
              f"1 g brake-dive moment {bk['brake_dive_moment_at_1g_nm']:.0f} N m")
