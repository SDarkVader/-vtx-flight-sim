"""VTX Phantom — preliminary wing, root-joint, control-surface and aeroelastic screening.

Run:  python engineering/phantom/wing_loads.py
Writes: evidence/phantom/wing_loads_results.json

Every numeric input carries a basis label:
  MEASURED              read from the pinned A8 source (evidence/phantom/a8_inventory.json)
  MANUFACTURER          published catalogue value (source cited in SOURCE_REGISTER / report)
  REGULATORY_REFERENCE  number taken from a certification-code pattern (CS-23 style), used as a
                        design-practice reference only, not a compliance claim
  DERIVED               computed here from labelled inputs
  SYNTHETIC_UNVALIDATED declared modelling hypothesis with stated bounds

This is closed-form screening (strip theory, Schrenk, thin-walled box, typical-section Theodorsen
flutter). It is NOT finite-element analysis, CFD, or a coupled aeroelastic model.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
from scipy.special import hankel2

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "phantom" / "wing_loads_results.json"
INVENTORY = ROOT / "evidence" / "phantom" / "a8_inventory.json"

G = 9.80665
RHO0 = 1.225
A_SL = 340.29


def lab(value, basis, note=""):
    d = {"value": value, "basis": basis}
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- inputs

MASS = {
    "mtow_kg": lab(1300.0, "SYNTHETIC_UNVALIDATED", "project notional mass (SYSTEMS_CONTRACT); bounds 1100-1500"),
    "min_flying_kg": lab(1050.0, "SYNTHETIC_UNVALIDATED", "one occupant, low fuel/energy; used for gust case"),
    "Ixx_body_kg_m2": lab(600.0, "SYNTHETIC_UNVALIDATED", "box estimate m(w^2+h^2)/12 with w=2.0, h=1.0 m, +/-30%"),
    "Iyy_kg_m2": lab(2300.0, "SYNTHETIC_UNVALIDATED", "box estimate m(L^2+h^2)/12, L=4.85 m, +/-30%"),
}
SPEEDS = {
    "VC_mps": lab(178.8, "DERIVED", "400 mph flight maximum target taken as design cruise/VMO"),
    "VD_over_VC": lab(1.25, "REGULATORY_REFERENCE", "CS-23.335(b) minimum VD/VC pattern"),
    "q_deploy_max_Pa": lab(600.0, "SYNTHETIC_UNVALIDATED", "wing transit allowed only at q<=600 Pa (~31 m/s EAS); to be validated"),
}
ENVELOPE = {
    # Candidate structural envelope (justified in the report); prior +8/+12 kept as sensitivity.
    "n_pos_limit": lab(6.0, "REGULATORY_REFERENCE", "CS-23 aerobatic-category positive limit"),
    "n_neg_limit": lab(-3.0, "REGULATORY_REFERENCE", "CS-23 aerobatic negative limit (0.5 x positive)"),
    "ultimate_factor": lab(1.5, "REGULATORY_REFERENCE", "CS-23.303"),
    "fitting_factor": lab(1.15, "REGULATORY_REFERENCE", "CS-23.625 fitting factor on joints"),
    "gust_Ude_VC_mps": lab(15.24, "REGULATORY_REFERENCE", "CS-23.341, 50 ft/s EAS at VC"),
    "gust_Ude_VD_mps": lab(7.62, "REGULATORY_REFERENCE", "CS-23.341, 25 ft/s EAS at VD"),
    "rolling_asym_factor": lab(0.60, "REGULATORY_REFERENCE", "CS-23.349 aerobatic: 100% one side, 60% other, at 2/3 n_limit"),
    "flutter_margin_on_VD": lab(1.20, "REGULATORY_REFERENCE", "CS-23.629: free from flutter/divergence/reversal to 1.2 VD"),
    "prior_estimate": lab({"n_limit": 8.0, "n_ultimate": 12.0}, "SYNTHETIC_UNVALIDATED", "earlier project screen; kept for comparison"),
}
MATERIAL = {
    # IM7/8552-class carbon/epoxy laminate values at design (strain-limited) allowables.
    "cfrp_density": lab(1580.0, "MANUFACTURER", "Hexcel 8552/IM7 cured laminate density ~1.57-1.59 g/cc"),
    "E_cap_Pa": lab(105e9, "DERIVED", "60/30/10 (0/+-45/90) laminate, classical lamination estimate from IM7/8552 ply data"),
    "strain_allow_ult": lab(0.0035, "SYNTHETIC_UNVALIDATED", "damage-tolerant (BVID, hot/wet) ultimate design strain; bounds 0.0030-0.0045"),
    "G_web_Pa": lab(30e9, "DERIVED", "+-45-dominated web laminate"),
    "G_skin_Pa": lab(20e9, "DERIVED", "cap-dominated skin laminate"),
    "tau_allow_ult_Pa": lab(150e6, "SYNTHETIC_UNVALIDATED", "web/skin ultimate shear allowable incl. stability by sandwich/stiffening"),
    "t_min_m": lab(1.0e-3, "SYNTHETIC_UNVALIDATED", "minimum handling/impact gauge"),
    "secondary_areal_kg_m2": lab(9.0, "SYNTHETIC_UNVALIDATED",
                                 "ribs, sandwich cores, LE, TE, control surfaces, hinges, sealing, LPS per m^2 planform; "
                                 "set so panel mass agrees with Raymer GA statistical wing weight (see raymer_check)"),
    "ti64_Ftu_Pa": lab(896e6, "MANUFACTURER", "Ti-6Al-4V annealed, MMPDS-typical Ftu 130 ksi"),
    "ti64_Fsu_Pa": lab(552e6, "MANUFACTURER", "Ti-6Al-4V annealed, MMPDS-typical Fsu 80 ksi"),
    "ti64_density": lab(4430.0, "MANUFACTURER", "Ti-6Al-4V"),
    "pin_steel_Fsu_Pa": lab(910e6, "SYNTHETIC_UNVALIDATED", "PH13-8Mo H1000 class, ~0.6 x Ftu 1517 MPa"),
    "pin_steel_Ftu_Pa": lab(1517e6, "MANUFACTURER", "PH13-8Mo H1000 typical Ftu 220 ksi"),
    "ti_lug_notched_endurance_Pa": lab(200e6, "SYNTHETIC_UNVALIDATED", "Kt~3, R=0.1, 1e7 cycles max stress; replace with MMPDS S-N for chosen form"),
    "pin_stiffness_N_per_m": lab(3.0e8, "SYNTHETIC_UNVALIDATED", "pin + bushing + local lug radial stiffness per pin"),
}
BEARINGS = [  # MANUFACTURER, SKF catalogue figures (confirmed against distributor listings 2026-11-02)
    {"part": "SKF GEH 50 TXE-2LS", "bore_mm": 50, "C_kN": 695, "C0_kN": 1160},
    {"part": "SKF GE 80 TXE-2LS", "bore_mm": 80, "C_kN": 1140, "C0_kN": 1900},
]
AERO = {
    "cl_alpha_2d_factor": lab(0.90, "SYNTHETIC_UNVALIDATED", "section lift slope = 0.9 * 2*pi / beta"),
    "cm0_section": lab(-0.04, "SYNTHETIC_UNVALIDATED", "NACA 64A2xx-class cambered section; CFD/polar to replace"),
    "CLmax_clean": lab(1.20, "SYNTHETIC_UNVALIDATED", "3D clean, low sweep, t/c 0.10-0.12"),
    "CLmax_flap": lab(1.60, "SYNTHETIC_UNVALIDATED", "plain/simple-slotted inboard flaps 30 deg"),
    "x_ac_frac": lab(0.25, "DERIVED", "subsonic section aerodynamic centre"),
    "x_ea_frac": lab(0.40, "SYNTHETIC_UNVALIDATED", "elastic axis of a 15-60% box"),
    "x_cg_frac": lab(0.43, "SYNTHETIC_UNVALIDATED", "section CG with mass-balanced control surfaces"),
    "Ch_delta_per_rad": lab(-0.70, "SYNTHETIC_UNVALIDATED", "sealed plain flap cf/c~0.28, no aero balance; bounds x0.7..x1.3"),
    "Ch_alpha_per_rad": lab(-0.35, "SYNTHETIC_UNVALIDATED", "as above"),
    "hinge_bound_factor": lab(1.30, "SYNTHETIC_UNVALIDATED", "upper-bound multiplier used for actuator sizing"),
    "control_viscous_factor": lab(0.80, "SYNTHETIC_UNVALIDATED", "thin-airfoil flap effectiveness correction"),
}


@dataclass
class Wing:
    name: str
    y_root: float          # body-side station where the exposed panel starts (m from centreline)
    span_exp: float        # exposed semi-span (m, along y)
    c_root: float          # chord at y_root (m)
    c_tip: float
    x_le_root: float       # LE x at y_root (model X forward)
    x_le_tip: float
    tc_root: float
    tc_tip: float
    z: float               # mean wing plane height (m)
    box_fs: float = 0.15
    box_rs: float = 0.60
    aileron_eta: tuple = (0.55, 0.95)   # fractions of exposed span
    flap_eta: tuple = (0.05, 0.50)
    cf_c: float = 0.28
    joint: dict = field(default_factory=dict)
    source: str = ""

    # ---------------------------------------------------------------- planform
    def chord(self, y):
        t = (y - self.y_root) / self.span_exp
        return self.c_root + (self.c_tip - self.c_root) * t

    def x_le(self, y):
        t = (y - self.y_root) / self.span_exp
        return self.x_le_root + (self.x_le_tip - self.x_le_root) * t

    def tc(self, y):
        t = (y - self.y_root) / self.span_exp
        return self.tc_root + (self.tc_tip - self.tc_root) * t

    @property
    def semispan(self):
        return self.y_root + self.span_exp

    @property
    def c0(self):  # chord extrapolated to the centreline
        return self.chord(0.0)

    @property
    def S_ref(self):
        return (self.c0 + self.c_tip) * self.semispan

    @property
    def S_exp(self):
        return (self.c_root + self.c_tip) * self.span_exp

    @property
    def b(self):
        return 2 * self.semispan

    @property
    def AR(self):
        return self.b ** 2 / self.S_ref

    def sweep(self, frac):
        dx = (self.x_le_tip + frac * self.c_tip) - (self.x_le_root + frac * self.c_root)
        return math.atan2(-dx, self.span_exp)  # positive = swept back

    @property
    def mac(self):
        lam = self.c_tip / self.c0
        return 2 / 3 * self.c0 * (1 + lam + lam ** 2) / (1 + lam)

    @property
    def y_mac(self):
        lam = self.c_tip / self.c0
        return self.semispan / 3 * (1 + 2 * lam) / (1 + lam)

    @property
    def x_ac_mac(self):
        return self.x_le(self.y_mac) - 0.25 * self.chord(self.y_mac)


def cl_alpha_wing(w: Wing, mach):
    beta = math.sqrt(max(1e-6, 1 - mach ** 2))
    kappa = AERO["cl_alpha_2d_factor"]["value"]
    tan_c2 = math.tan(w.sweep(0.5))
    A = w.AR
    return 2 * math.pi * A / (2 + math.sqrt(A ** 2 * beta ** 2 / kappa ** 2 * (1 + tan_c2 ** 2 / beta ** 2) + 4))


# --------------------------------------------------------------------------- V-n

def vn_envelope(w: Wing, mass, n_pos, n_neg):
    W = mass * G
    S = w.S_ref
    VC = SPEEDS["VC_mps"]["value"]
    VD = VC * SPEEDS["VD_over_VC"]["value"]
    clmax = AERO["CLmax_clean"]["value"]
    VS1 = math.sqrt(2 * W / (RHO0 * S * clmax))
    VA = VS1 * math.sqrt(n_pos)
    VS_neg = math.sqrt(2 * W / (RHO0 * S * 0.8 * clmax))
    VG = VS_neg * math.sqrt(-n_neg)
    cbar = S / w.b
    res = dict(W_N=W, S_ref=S, wing_loading_Pa=W / S, VS1=VS1, VA=VA, VG_neg=VG, VC=VC, VD=VD,
               VA_exceeds_VC=VA > VC)
    for tag, V, Ude in (("VC", VC, ENVELOPE["gust_Ude_VC_mps"]["value"]), ("VD", VD, ENVELOPE["gust_Ude_VD_mps"]["value"])):
        a = cl_alpha_wing(w, V / A_SL)
        mu = 2 * (W / S) / (RHO0 * cbar * a * G)
        Kg = 0.88 * mu / (5.3 + mu)
        dn = Kg * RHO0 * Ude * V * a / (2 * W / S)
        res[f"gust_{tag}"] = dict(V=V, mach=V / A_SL, CLalpha=a, mu_g=mu, Kg=Kg, dn=dn, n_pos=1 + dn, n_neg=1 - dn)
    return res


# --------------------------------------------------------------------------- spanwise loads

def strips(w: Wing, n=60):
    ys = np.linspace(w.y_root, w.semispan, n + 1)
    yc = 0.5 * (ys[1:] + ys[:-1])
    return yc, np.diff(ys)


def schrenk_fraction(w: Wing):
    """Fraction of the total wing-body lift (both sides) carried by ONE exposed panel, and its spanwise share."""
    b, S = w.b, w.S_ref
    ys = np.linspace(0, w.semispan, 2001)
    c = w.c0 + (w.c_tip - w.c0) * ys / w.semispan
    ce = 4 * S / (math.pi * b) * np.sqrt(np.clip(1 - (2 * ys / b) ** 2, 0, None))
    cs = 0.5 * (c + ce)
    half = np.trapezoid(cs, ys)
    return cs, ys, half


def wing_mass_distribution(w: Wing, m_panel):
    yc, dy = strips(w)
    c = w.chord(yc)
    return m_panel * c * dy / np.sum(c * dy)


def panel_loads(w: Wing, L_total, n_inertia, q, m_panel, delta_ail=0.0, delta_flap=0.0, side_factor=1.0):
    """Root loads of one exposed panel at the body-side station.

    L_total     total wing-body lift both sides (N) for the condition
    n_inertia   load factor for inertia relief
    q           dynamic pressure (Pa) for section pitching moments
    delta_ail   aileron deflection on this side (rad, +TE down)
    side_factor fraction of symmetric airload on this side (rolling cases)
    Returns shear, bending (perpendicular to EA), torsion about EA (nose-down +) at root.
    """
    cs_all, ys_all, half = schrenk_fraction(w)
    yc, dy = strips(w)
    cs = np.interp(yc, ys_all, cs_all)
    l = side_factor * 0.5 * L_total * cs / half          # N/m
    c = w.chord(yc)
    x_ac = w.x_le(yc) - AERO["x_ac_frac"]["value"] * c
    cm = np.full_like(yc, AERO["cm0_section"]["value"])
    # control-surface increments (thin airfoil, viscous factor)
    th = math.acos(2 * w.cf_c - 1)
    tau = 1 - (th - math.sin(th)) / math.pi
    cmd = -0.5 * math.sin(th) * (1 - math.cos(th))
    kv = AERO["control_viscous_factor"]["value"]
    eta = (yc - w.y_root) / w.span_exp
    for (e0, e1), d in ((w.aileron_eta, delta_ail), (w.flap_eta, delta_flap)):
        on = (eta >= e0) & (eta <= e1)
        cla = 2 * math.pi * AERO["cl_alpha_2d_factor"]["value"]
        l = l + on * q * c * cla * tau * kv * d
        cm = cm + on * cmd * kv * d
    m_strip = wing_mass_distribution(w, m_panel)
    x_cg = w.x_le(yc) - AERO["x_cg_frac"]["value"] * c
    Fz = l * dy - n_inertia * G * m_strip                   # net upward per strip
    # moment of strip loads about root EA point (vector form, model frame X fwd, Y out, Z up)
    xr = w.x_le_root - AERO["x_ea_frac"]["value"] * w.c_root
    Mx = np.sum((yc - w.y_root) * Fz)
    My = np.sum(-(x_ac - xr) * l * dy + (x_cg - xr) * n_inertia * G * m_strip) + np.sum(-q * c ** 2 * cm * dy)
    x_tip_ea = w.x_le_tip - AERO["x_ea_frac"]["value"] * w.c_tip
    e = np.array([x_tip_ea - xr, w.span_exp, 0.0]); e /= np.linalg.norm(e)
    nvec = np.cross(e, [0, 0, 1.0])
    Mvec = np.array([Mx, My, 0.0])
    # running shear and bending along span for box sizing
    Fz_out = np.cumsum(Fz[::-1])[::-1]
    Mb_run = np.array([np.sum((yc[i:] - yc[i]) * Fz[i:]) for i in range(len(yc))]) / math.cos(w.sweep(AERO["x_ea_frac"]["value"]))
    T_run = np.array([np.sum(-(x_ac[i:] - (w.x_le(yc[i]) - AERO["x_ea_frac"]["value"] * c[i])) * l[i:] * dy[i:]) -
                      np.sum(q * c[i:] ** 2 * cm[i:] * dy[i:]) for i in range(len(yc))])
    return dict(V=float(np.sum(Fz)), Mx_streamwise=float(Mx), My_streamwise=float(My),
                M_bend=float(Mvec @ nvec), T_ea=float(Mvec @ e), lift_panel=float(np.sum(l * dy)),
                run=dict(y=yc.tolist(), V=Fz_out.tolist(), M=Mb_run.tolist(), T=T_run.tolist()))


# --------------------------------------------------------------------------- box sizing

def size_box(w: Wing, run_ult, m_tongue_factor=1.3):
    """Strain-limited CFRP torsion box at each strip from ULTIMATE running loads."""
    E, eps = MATERIAL["E_cap_Pa"]["value"], MATERIAL["strain_allow_ult"]["value"]
    sig = E * eps
    tau = MATERIAL["tau_allow_ult_Pa"]["value"]
    tmin = MATERIAL["t_min_m"]["value"]
    rho = MATERIAL["cfrp_density"]["value"]
    Gw, Gs = MATERIAL["G_web_Pa"]["value"], MATERIAL["G_skin_Pa"]["value"]
    cosL = math.cos(w.sweep(AERO["x_ea_frac"]["value"]))
    rows = []
    yc, dy = strips(w)
    for i, y in enumerate(yc):
        c = w.chord(y) * cosL
        h = 0.90 * w.tc(y) * w.chord(y)
        wb = (w.box_rs - w.box_fs) * c
        M, V, T = abs(run_ult["M"][i]), abs(run_ult["V"][i]), abs(run_ult["T"][i])
        hc = h
        for _ in range(5):
            Acap = M / (hc * sig)
            tcap = max(tmin, Acap / wb)
            hc = h - tcap
        qT = T / (2 * wb * h)
        tweb = max(tmin, V / (2 * h * tau) + qT / tau)
        tskin = max(tcap, qT / tau)
        GJ = 4 * (wb * h) ** 2 / (2 * wb / (Gs * tskin) + 2 * h / (Gw * tweb))
        EI = 2 * E * tcap * wb * (hc / 2) ** 2
        mpl = rho * (2 * wb * tskin + 2 * h * tweb) * 1.15
        rows.append(dict(y=y, chord=w.chord(y), h=h, box_w=wb, t_cap=tcap, t_web=tweb, t_skin=tskin,
                         EI=EI, GJ=GJ, box_mass_per_m=mpl, dy=dy[i]))
    box_mass = sum(r["box_mass_per_m"] * r["dy"] / cosL for r in rows)
    sec = MATERIAL["secondary_areal_kg_m2"]["value"] * w.S_exp / 2
    tongue_len = w.joint.get("tongue_length_m", 0.0)
    tongue_mass = rows[0]["box_mass_per_m"] * tongue_len * m_tongue_factor
    return rows, dict(box_kg=box_mass, secondary_kg=sec, tongue_kg=tongue_mass, panel_kg=box_mass + sec,
                      total_kg=box_mass + sec + tongue_mass)


# --------------------------------------------------------------------------- root joints

def pin_diameter(F, Fsu, planes=2):
    return math.sqrt(4 * F / (planes * math.pi * Fsu))


def lug_thickness(F, D, Ftu):
    W = 2.5 * D
    t_net = F / (0.9 * (W - D) * Ftu)
    t_brg = F / (D * 1.5 * Ftu)
    return max(t_net, t_brg)


def raymer_wing_mass(w: Wing, mass, n_ult):
    """Raymer (Aircraft Design: A Conceptual Approach) general-aviation wing weight, whole wing incl.
    carry-through, imperial units; scaled to the exposed panels by area. Statistical cross-check only."""
    S_ft2 = w.S_ref * 10.7639
    lam = math.cos(w.sweep(0.25))
    q_psf = 0.5 * RHO0 * SPEEDS["VC_mps"]["value"] ** 2 * 0.0208854
    W_lb = mass * 2.20462
    taper = w.c_tip / w.c0
    Wlb = (0.036 * S_ft2 ** 0.758 * (w.AR / lam ** 2) ** 0.6 * q_psf ** 0.006 * taper ** 0.04
           * (100 * w.tc_root / lam) ** -0.3 * (n_ult * W_lb) ** 0.49)
    whole = Wlb / 2.20462
    return dict(whole_wing_kg=whole, exposed_panel_kg_each=whole * (w.S_exp / w.S_ref) / 2,
                basis="DERIVED statistical (metal GA database); composite typically 10-25% lighter")


def joint_options(w: Wing, root_ult):
    ff = ENVELOPE["fitting_factor"]["value"]
    Mx, V, My = abs(root_ult["Mx_streamwise"]) * ff, abs(root_ult["V"]) * ff, abs(root_ult["My_streamwise"]) * ff
    Fsu, Ftu = MATERIAL["pin_steel_Fsu_Pa"]["value"], MATERIAL["ti64_Ftu_Pa"]["value"]
    root_depth = 0.9 * w.tc_root * w.c_root
    box_w = (w.box_rs - w.box_fs) * w.c_root
    opts = {}

    def entry(name, F_pin, n_pins, sep, kind, note):
        d = pin_diameter(F_pin, Fsu)
        t = lug_thickness(F_pin, d, Ftu)
        brg = [dict(part=b["part"], C0_kN=b["C0_kN"], margin_C0=b["C0_kN"] * 1e3 / F_pin - 1) for b in BEARINGS]
        opts[name] = dict(kind=kind, couple_separation_m=sep, max_pin_force_N=F_pin, pins=n_pins,
                          pin_diameter_m=d, ti_lug_thickness_m=t, bearings=brg, note=note)

    # A: as-drawn A8 vertical-pin hinge, moment reacted across wing/fairing depth
    for tag, h in (("A8_plate_46mm", 0.046), ("A8_fairing_160mm", 0.160), ("root_box_depth", root_depth)):
        F = Mx / h + V / 2
        entry(f"A_vertical_couple_{tag}", F, 2, h, "depth-limited lug/bearing couple", "moment reacted by upper/lower lugs separated by available depth")
    # C: spanwise tongue couple in carry-through sleeve (two stations, two pins each: front & rear spar)
    D = w.joint.get("lock_spacing_m")
    if D:
        F_in = Mx / D
        F_out = Mx / D + V
        Ft = My / (2 * w.joint.get("pin_pair_separation_m", box_w))  # torsion shared by two stations (pin pair x-separation; default box width)
        F_pin = max(F_out / 2 + Ft / 2, F_in / 2 + Ft / 2)
        entry("C_spanwise_tongue_couple", F_pin, 4, D, "tongue in carry-through sleeve, 2 stations x 2 pins",
              "moment reacted by vertical forces at outboard (sleeve mouth) and inboard (tongue end) stations")
    return dict(applied_ultimate_with_fitting_factor=dict(Mx=Mx, V=V, My=My, fitting_factor=ff), options=opts)


# --------------------------------------------------------------------------- control surfaces & roll

def flap_theory(cf_c):
    th = math.acos(2 * cf_c - 1)
    tau = 1 - (th - math.sin(th)) / math.pi
    cmd = -0.5 * math.sin(th) * (1 - math.cos(th))
    return tau, cmd


def surface_geometry(w: Wing, eta):
    y0 = w.y_root + eta[0] * w.span_exp
    y1 = w.y_root + eta[1] * w.span_exp
    c0, c1 = w.chord(y0), w.chord(y1)
    span = y1 - y0
    S = w.cf_c * (c0 + c1) / 2 * span
    cf_mean = w.cf_c * (c0 + c1) / 2
    t_hinge = w.tc((y0 + y1) / 2) * w.chord((y0 + y1) / 2) * 0.55  # local depth at ~72% chord
    return dict(y0=y0, y1=y1, span=span, area=S, cf_mean=cf_mean, depth_at_hinge=t_hinge)


def hinge_moment(q, area, cf, alpha, delta, bound=1.0):
    Cha, Chd = AERO["Ch_alpha_per_rad"]["value"], AERO["Ch_delta_per_rad"]["value"]
    return q * area * cf * (Cha * alpha + Chd * delta) * bound


def roll_performance(w: Wing, V, delta, Ixx, q_rev=None):
    beta = math.sqrt(max(1e-6, 1 - (V / A_SL) ** 2))
    cla = 2 * math.pi * AERO["cl_alpha_2d_factor"]["value"] / beta
    tau, _ = flap_theory(w.cf_c)
    tau *= AERO["control_viscous_factor"]["value"]
    S, b = w.S_ref, w.b
    ys = np.linspace(w.y_root, w.semispan, 400)
    c = w.chord(ys)
    ga = surface_geometry(w, w.aileron_eta)
    on = (ys >= ga["y0"]) & (ys <= ga["y1"])
    Clda = 2 * cla * tau / (S * b) * np.trapezoid(np.where(on, c * ys, 0), ys)
    Clp = -4 * cla / (S * b ** 2) * np.trapezoid(c * ys ** 2, ys)
    q = 0.5 * RHO0 * V ** 2
    eff = 1.0 if not q_rev else max(0.0, 1 - q / q_rev)
    p_hat = -Clda * delta * eff / Clp
    p = p_hat * 2 * V / b
    Lp = Clp * q * S * b ** 2 / (2 * V)
    tau_r = Ixx / -Lp
    p_dot0 = Clda * delta * eff * q * S * b / Ixx
    t90 = None
    if p > 0:
        ts = np.linspace(0, 10, 10001)
        phi = p * (ts - tau_r * (1 - np.exp(-ts / tau_r)))
        k = np.argmax(phi >= math.pi / 2)
        t90 = float(ts[k]) if phi[-1] >= math.pi / 2 else None
    return dict(V=V, delta_deg=math.degrees(delta), Cl_delta_a=Clda, Cl_p=Clp, effectiveness=eff,
                pb_2V=p_hat, p_deg_s=math.degrees(p), roll_time_constant_s=tau_r,
                initial_roll_accel_deg_s2=math.degrees(p_dot0), time_to_90deg_bank_s=t90)


# --------------------------------------------------------------------------- aeroelastic

def theodorsen_C(k):
    H1, H0 = hankel2(1, k), hankel2(0, k)
    return H1 / (H1 + 1j * H0)


def flutter_k_method(mu, a, x_a, r2, sigma, ks=None):
    """Typical-section flutter, k-method (V-g). Returns flutter V/(b*omega_alpha) and k.

    mu = m/(pi rho b^2), a = EA position aft of mid-chord in semichords, x_a = CG aft of EA
    in semichords, r2 = r_alpha^2, sigma = omega_h/omega_alpha.
    """
    if ks is None:
        ks = np.geomspace(2.0, 0.02, 1200)
    Ms = np.array([[1.0, x_a], [x_a, r2]])
    K = np.array([[sigma ** 2, 0.0], [0.0, r2]])
    branches = []
    for k in ks:
        C = theodorsen_C(k)
        Lh = -1 + 2j * C / k
        La = 1j / k + a + 2 * C / k ** 2 + 2j * C * (0.5 - a) / k
        Mh = -a + 2j * C * (a + 0.5) / k
        Ma = -1j * (0.5 - a) / k + (1 / 8 + a ** 2) + 2 * C * (a + 0.5) / k * (1 / k + 1j * (0.5 - a))
        A = Ms + (1 / mu) * np.array([[-Lh, -La], [Mh, Ma]])
        lam = np.linalg.eigvals(np.linalg.solve(K, A))  # lam = (1+ig)/omega^2 (omega in units of omega_alpha)
        row = []
        for l in lam:
            if l.real <= 0:
                row.append((np.nan, np.nan))
                continue
            om = 1 / math.sqrt(l.real)
            g = l.imag / l.real
            row.append((om / k, g))
        branches.append(sorted(row, key=lambda t: (np.nan_to_num(t[0], nan=1e9))))
    br = np.array(branches)  # [k, mode, (V, g)]
    best = None
    for m in range(br.shape[1]):
        V, g = br[:, m, 0], br[:, m, 1]
        for i in range(1, len(ks)):
            if np.isfinite(g[i - 1]) and np.isfinite(g[i]) and g[i - 1] < 0 <= g[i]:
                f = -g[i - 1] / (g[i] - g[i - 1])
                Vf = V[i - 1] + f * (V[i] - V[i - 1])
                kf = ks[i - 1] + f * (ks[i] - ks[i - 1])
                if best is None or Vf < best[0]:
                    best = (Vf, kf, m)
    return dict(V_over_b_omega_alpha=None if best is None else float(best[0]),
                k_flutter=None if best is None else float(best[1]))


def aeroelastic_screen(w: Wing, rows, m_panel, Kb_root, Kt_root, VD):
    ea = AERO["x_ea_frac"]["value"]
    cosL = math.cos(w.sweep(ea))
    L = w.span_exp / cosL
    i35 = int(0.35 * len(rows))
    EI, GJ = rows[i35]["EI"], rows[i35]["GJ"]
    st = 0.70
    y = w.y_root + st * w.span_exp
    c = w.chord(y)
    bsc = c / 2
    m_line = m_panel / L                                      # kg/m (uniform equivalent)
    a = 2 * ea - 1
    x_a = 2 * (AERO["x_cg_frac"]["value"] - ea)
    r_cg = 0.25 * c                                           # radius of gyration about section CG, SYNTHETIC
    Ia = m_line * (r_cg ** 2 + (x_a * bsc) ** 2)
    r2 = Ia / (m_line * bsc ** 2)
    wh_beam = 1.875 ** 2 * math.sqrt(EI / (m_line * L ** 4))
    wh_root = math.sqrt(Kb_root / (m_line * L ** 3 / 3))
    wh = 1 / math.sqrt(1 / wh_beam ** 2 + 1 / wh_root ** 2)
    wa_beam = math.pi / (2 * L) * math.sqrt(GJ / Ia)
    wa_root = math.sqrt(Kt_root / (Ia * L))
    wa = 1 / math.sqrt(1 / wa_beam ** 2 + 1 / wa_root ** 2)
    out = dict(station_eta=st, semichord_m=bsc, mass_per_m=m_line, I_alpha=Ia, a=a, x_alpha=x_a, r_alpha2=r2,
               f_bending_Hz=wh / (2 * math.pi), f_torsion_Hz=wa / (2 * math.pi),
               f_bending_beam_only_Hz=wh_beam / (2 * math.pi), f_torsion_beam_only_Hz=wa_beam / (2 * math.pi))
    for tag, rho in (("SL", RHO0), ("3000m", 0.9093)):
        mu = m_line / (math.pi * rho * bsc ** 2)
        fl = flutter_k_method(mu, a, x_a, r2, wh / wa)
        VF = None if fl["V_over_b_omega_alpha"] is None else fl["V_over_b_omega_alpha"] * bsc * wa
        VF_eas = None if VF is None else VF * math.sqrt(rho / RHO0)
        out[f"flutter_{tag}"] = dict(mu=mu, **fl, VF_TAS=VF, VF_EAS=VF_eas,
                                     margin_vs_1p2VD=None if VF_eas is None else VF_eas / (1.2 * VD) - 1)
    # divergence and aileron reversal, typical section at the aileron centroid
    ga = surface_geometry(w, w.aileron_eta)
    ya = 0.5 * (ga["y0"] + ga["y1"])
    yc = np.array([r["y"] for r in rows])
    GJs = np.array([r["GJ"] for r in rows])
    sel = yc <= ya
    comp = np.trapezoid(1 / GJs[sel], yc[sel] / cosL) + 1 / Kt_root
    Kth = 1 / comp
    ca = w.chord(ya)
    Sa = ca * ga["span"]
    cla = 2 * math.pi * AERO["cl_alpha_2d_factor"]["value"]
    tau, cmd = flap_theory(w.cf_c)
    kv = AERO["control_viscous_factor"]["value"]
    cld, cmd = cla * tau * kv, cmd * kv
    q_rev = -Kth * cld / (Sa * ca * cla * cmd)
    e = ea - AERO["x_ac_frac"]["value"]
    q_div = Kth / (Sa * ca * e * cla)
    out.update(K_theta_at_aileron=Kth, q_reversal=q_rev, V_reversal_EAS=math.sqrt(2 * q_rev / RHO0),
               q_divergence_unswept=q_div, V_divergence_EAS_unswept=math.sqrt(2 * q_div / RHO0),
               note="typical-section screens; sweep-back bending/torsion coupling raises divergence and lowers reversal speed; not a coupled model")
    return out


# --------------------------------------------------------------------------- canard & transition

def canard_trim(w: Wing, canard, x_cg, body_munk_m3, mass, flap_deg=30.0):
    """Canard lift share and CL to trim at 1 g, wing + canard + body Munk moment, no thrust moment."""
    W = mass * G
    th = math.acos(2 * w.cf_c - 1)
    tau, cmd = flap_theory(w.cf_c)
    kv = AERO["control_viscous_factor"]["value"]
    fl = surface_geometry(w, w.flap_eta)
    d = math.radians(flap_deg)
    a_w = cl_alpha_wing(w, 0.15)
    dCL_flap = 2 * math.pi * 0.9 * tau * kv * d * (fl["area"] / w.cf_c) / w.S_ref
    dCm_flap = cmd * kv * d * (fl["area"] / w.cf_c) / w.S_ref
    x_w = w.x_ac_mac
    rows = []
    for V in (30, 40, 50, 60, 70, 80, 90, 110, 140, 178.8):
        q = 0.5 * RHO0 * V ** 2
        # solve: L_w + L_c = W ; L_c (x_c - x_cg) + L_w (x_w - x_cg) + q S c (Cm0 + dCm_flap) + Munk = 0
        Cm0 = AERO["cm0_section"]["value"] + (dCm_flap if V < 90 else 0)
        M0 = q * w.S_ref * w.mac * Cm0
        # Munk moment needs alpha: iterate
        alpha = 0.05
        for _ in range(30):
            M_body = q * body_munk_m3 * alpha * 2  # nose-up, 2 q Vol (k2-k1) alpha with (k2-k1)~1 folded into body_munk_m3
            Lc = (-(W) * (x_w - x_cg) - M0 - M_body) / ((canard["x_ac"] - x_cg) - (x_w - x_cg))
            Lw = W - Lc
            CLw = Lw / (q * w.S_ref)
            alpha = max(-0.2, min(0.4, (CLw - (dCL_flap if V < 90 else 0)) / a_w))
        CLc = Lc / (q * canard["S"])
        rows.append(dict(V=V, CL_wing=CLw, CL_canard=CLc, canard_lift_share=Lc / W, alpha_deg=math.degrees(alpha),
                         wing_feasible=CLw <= 0.85 * (AERO["CLmax_flap"]["value"] if V < 90 else AERO["CLmax_clean"]["value"]),
                         canard_feasible=abs(CLc) <= 0.9))
    Vmin = next((r["V"] for r in rows if r["wing_feasible"] and r["canard_feasible"]), None)
    return dict(x_cg=x_cg, x_wing_ac=x_w, x_canard_ac=canard["x_ac"], canard_S=canard["S"],
                min_speed_full_wingborne_trim=Vmin, rows=rows)


def neutral_point(w: Wing, canard, body_munk_m3, mach=0.15):
    a_w = cl_alpha_wing(w, mach)
    a_c = canard["CLalpha"]
    dM = a_w * w.S_ref * w.x_ac_mac + a_c * canard["S"] * canard["x_ac"] + 2 * body_munk_m3
    dL = a_w * w.S_ref + a_c * canard["S"]
    return dict(x_np=dM / dL, x_np_without_body=(dM - 2 * body_munk_m3) / dL)


# --------------------------------------------------------------------------- cassette mechanism

def cassette_mechanism(w: Wing, m_wing):
    qd = SPEEDS["q_deploy_max_Pa"]["value"]
    S_half = w.S_exp / 2
    CN = 1.2  # SYNTHETIC worst normal-force coefficient during transit (crosswind/downwash)
    Fn = qd * S_half * CN
    arm = w.span_exp * 0.45
    tongue = w.joint.get("tongue_length_m", 0.5)
    roller_sep = tongue * 0.9
    N_roll = (Fn + 2.0 * m_wing * G) * arm / roller_sep + (Fn + 2.0 * m_wing * G)
    mu_roll, mu_pad = 0.01, 0.08
    a = 0.5
    F_axial = mu_pad * N_roll + m_wing * a + m_wing * G * math.sin(math.radians(10)) + 0.05 * Fn
    stroke = w.span_exp + 0.03
    t_deploy = 6.0
    v = stroke / (t_deploy - 1.0)
    P_mech = F_axial * v
    # stowed retention (emergency-landing inertia pattern, CS-23.561) for wing + tongue
    stow = {k: m_wing * G * g for k, g in (("fwd_9g", 9.0), ("down_6g", 6.0), ("up_3g", 3.0), ("side_1p5g", 1.5))}
    # hatch doors at VD, closed: suction Cp -1.5 on each door
    VD = SPEEDS["VC_mps"]["value"] * SPEEDS["VD_over_VC"]["value"]
    door_area = w.c_root * 1.05 * (0.9 * w.tc_root * w.c_root + 0.03) / 2
    door_load = 0.5 * RHO0 * VD ** 2 * 1.5 * door_area
    return dict(q_deploy_Pa=qd, normal_force_transit_N=Fn, roller_reaction_max_N=N_roll,
                slide_actuator_force_N=F_axial, slide_stroke_m=stroke, deploy_time_s=t_deploy,
                slide_speed_mps=v, slide_mech_power_W=P_mech,
                slide_energy_J=F_axial * stroke, stowed_retention_N=stow,
                hatch_door_area_m2=door_area, hatch_door_load_at_VD_N=door_load,
                basis="DERIVED from SYNTHETIC_UNVALIDATED transit q, CN=1.2, mu_pad=0.08, a=0.5 m/s^2, 10 deg slope")


# --------------------------------------------------------------------------- run

def analyse(w: Wing, canard, body_munk_m3, x_cg_list, n_pos, n_neg, label):
    res = dict(label=label, geometry={k: v for k, v in asdict(w).items()},
               planform=dict(S_ref=w.S_ref, S_exposed_both=w.S_exp, span=w.b, AR=w.AR, mac=w.mac, y_mac=w.y_mac,
                             x_ac_mac=w.x_ac_mac, sweep_le_deg=math.degrees(w.sweep(0.0)),
                             sweep_c4_deg=math.degrees(w.sweep(0.25)), taper=w.c_tip / w.c0,
                             root_box_depth_m=0.9 * w.tc_root * w.c_root))
    mass = MASS["mtow_kg"]["value"]
    W = mass * G
    uf = ENVELOPE["ultimate_factor"]["value"]
    vn = vn_envelope(w, mass, n_pos, n_neg)
    vn_light = vn_envelope(w, MASS["min_flying_kg"]["value"], n_pos, n_neg)
    res["vn"] = dict(mtow=vn, min_flying=vn_light)
    VA, VC, VD = min(vn["VA"], vn["VC"]), vn["VC"], vn["VD"]
    n_g_pos = max(vn["gust_VC"]["n_pos"], vn_light["gust_VC"]["n_pos"], vn["gust_VD"]["n_pos"])
    n_g_neg = min(vn["gust_VC"]["n_neg"], vn_light["gust_VC"]["n_neg"], vn["gust_VD"]["n_neg"])
    ail_max, ail_VD = math.radians(20), math.radians(20 / 3)
    # Lift share of one exposed panel under Schrenk (body-portion treated as wing). The body's real
    # lift is unknown without CFD, so a conservative bound puts all wing-body lift on the panels.
    share = panel_loads(w, W, 0.0, 0.0, 1.0)["lift_panel"] / W
    nb = 0.5 / share
    res["panel_lift_share_schrenk"] = share
    conds = [
        ("PHAA_VA_noBodyLift", n_pos, VA, 0, 0, nb),
        ("ROLL_PULLUP_VA_noBodyLift", 2 / 3 * n_pos, VA, ail_max, 0, nb),
        ("NEG_VD_noBodyLift", n_neg, VD, 0, 0, nb),
        ("PHAA_VA", n_pos, VA, 0, 0, 1.0),
        ("PLAA_VD", n_pos, VD, 0, 0, 1.0),
        ("NEG_VD", n_neg, VD, 0, 0, 1.0),
        ("GUST_POS", n_g_pos, VC, 0, 0, 1.0),
        ("GUST_NEG", n_g_neg, VC, 0, 0, 1.0),
        ("ROLL_PULLUP_VA_100pct", 2 / 3 * n_pos, VA, ail_max, 0, 1.0),
        ("ROLL_PULLUP_VD_100pct", 2 / 3 * n_pos, VD, ail_VD, 0, 1.0),
        ("FLAPS_30deg_n2", 2.0, 75.0, 0, math.radians(30), 1.0),
        ("PRIOR_8g_at_VA", 8.0, min(vn["VS1"] * math.sqrt(8), VC), 0, 0, 1.0),
    ]
    m_panel = 30.0
    for it in range(4):
        loads = {}
        for name, n, V, da, df, sf in conds:
            q = 0.5 * RHO0 * V ** 2
            loads[name] = panel_loads(w, n * W, n, q, m_panel, da, df, sf)
        crit = {k: max(loads.values(), key=lambda L: abs(L[k]))[k] for k in ("V", "M_bend", "T_ea", "Mx_streamwise", "My_streamwise")}
        design = [k for k in loads if not k.startswith("PRIOR")]
        n_strip = len(loads[design[0]]["run"]["y"])
        run_ult = dict(M=[uf * max(abs(loads[k]["run"]["M"][i]) for k in design) for i in range(n_strip)],
                       V=[uf * max(abs(loads[k]["run"]["V"][i]) for k in design) for i in range(n_strip)],
                       T=[uf * max(abs(loads[k]["run"]["T"][i]) for k in design) for i in range(n_strip)])
        rows, masses = size_box(w, run_ult)
        m_panel = masses["panel_kg"]
    res["conditions_limit"] = {k: {kk: vv for kk, vv in L.items() if kk != "run"} for k, L in loads.items()}
    env_root = {k: max((loads[c] for c in design), key=lambda L: abs(L[k]))[k] for k in ("V", "M_bend", "T_ea", "Mx_streamwise", "My_streamwise")}
    res["root_envelope_limit"] = env_root
    res["root_envelope_ultimate"] = {k: v * uf for k, v in env_root.items()}
    res["box_sizing"] = dict(rows=[{k: r[k] for k in ("y", "chord", "h", "box_w", "t_cap", "t_web", "t_skin", "EI", "GJ")} for r in rows[::6]],
                             masses=masses, material_basis="strain-limited IM7/8552-class, see MATERIAL",
                             raymer_check=raymer_wing_mass(w, mass, n_pos * uf))
    root_ult = {k: v * uf for k, v in env_root.items()}
    res["root_joint"] = joint_options(w, root_ult)
    # root joint stiffness for aeroelastic
    kp = MATERIAL["pin_stiffness_N_per_m"]["value"]
    D = w.joint.get("lock_spacing_m") or 0.9 * w.tc_root * w.c_root
    bw = (w.box_rs - w.box_fs) * w.c_root
    Kb, Kt = kp * D ** 2, kp * bw ** 2
    res["root_joint"]["rotational_stiffness"] = dict(bending_Nm_per_rad=Kb, torsion_Nm_per_rad=Kt, basis="DERIVED from SYNTHETIC pin stiffness")
    ae = aeroelastic_screen(w, rows, m_panel, Kb, Kt, VD)
    res["aeroelastic"] = ae
    # control surfaces
    cs = {}
    alpha_VA = n_pos * W / (0.5 * RHO0 * VA ** 2 * w.S_ref) / cl_alpha_wing(w, VA / A_SL)
    for sname, eta, dmax, rate in (("aileron", w.aileron_eta, 20.0, 80.0), ("flap", w.flap_eta, 35.0, 15.0)):
        g = surface_geometry(w, eta)
        bound = AERO["hinge_bound_factor"]["value"]
        if sname == "aileron":
            cases = [("VA_full", VA, alpha_VA, math.radians(dmax)), ("VC_2/3", VC, 0.05, math.radians(dmax * 2 / 3)),
                     ("VD_1/3", VD, 0.03, math.radians(dmax / 3))]
        else:
            VF = 75.0
            cases = [("VF_full", VF, math.radians(8), math.radians(dmax)), ("VF_gust", VF, math.radians(12), math.radians(dmax))]
        Hs = {c: hinge_moment(0.5 * RHO0 * V ** 2, g["area"], g["cf_mean"], al, d) for c, V, al, d in cases}
        Hmax = max(abs(h) for h in Hs.values())
        T_stall = 1.25 * Hmax * bound
        horn = max(0.02, 0.8 * g["depth_at_hinge"])
        w_rad = math.radians(rate)
        cs[sname] = dict(geometry=g, travel_deg=[-dmax if sname == "aileron" else -5, dmax], rate_deg_s=rate,
                         hinge_moments_Nm=Hs, H_max_nominal_Nm=Hmax, actuator_stall_torque_Nm=T_stall,
                         linear_EMA=dict(horn_radius_m=horn, stall_force_N=T_stall / horn / math.cos(math.radians(25)),
                                         stroke_m=2 * horn * math.sin(math.radians(dmax))),
                         mech_power_peak_W=0.5 * T_stall * w_rad, elec_power_peak_W=0.5 * T_stall * w_rad / 0.70,
                         hinge_inertia_kg_m2=(MATERIAL["secondary_areal_kg_m2"]["value"] * 1.2 * g["area"]) * g["cf_mean"] ** 2 / 3,
                         basis="DERIVED; hinge coefficients SYNTHETIC_UNVALIDATED")
        f_req = 1.5 * ae["f_torsion_Hz"]
        cs[sname]["actuator_min_stiffness_Nm_per_rad"] = (2 * math.pi * f_req) ** 2 * cs[sname]["hinge_inertia_kg_m2"]
        cs[sname]["stiffness_rule"] = "surface rotation frequency on actuator >= 1.5 x wing torsion frequency, plus mass balance to hinge line"
    res["control_surfaces"] = cs
    Ixx = MASS["Ixx_body_kg_m2"]["value"] + 2 * m_panel * (w.y_root + 0.45 * w.span_exp) ** 2
    res["roll"] = dict(Ixx_kg_m2=Ixx, cases=[roll_performance(w, V, d, Ixx, ae["q_reversal"]) for V, d in
                                             ((VA, math.radians(20)), (VC, math.radians(13.3)), (VD, math.radians(6.7)), (80.0, math.radians(20)))])
    # canard and longitudinal balance
    res["longitudinal"] = dict(
        neutral_point=neutral_point(w, canard, body_munk_m3),
        trim=[canard_trim(w, canard, x, body_munk_m3, mass) for x in x_cg_list])
    # canard hinge (all-moving, pivot at 22% MAC)
    hc = []
    for V, CL in ((VA, 1.0), (VC, 0.5), (VD, 0.35)):
        q = 0.5 * RHO0 * V ** 2
        for xac in (0.23, 0.30):
            hc.append(dict(V=V, CL=CL, x_ac=xac, H_Nm=q * canard["S"] * canard["c"] * (CL * (xac - 0.22) + -0.02)))
    Lc_ult = max(abs(r["CL"]) * 0.5 * RHO0 * r["V"] ** 2 for r in hc) * canard["S"] * uf
    spindle_M = Lc_ult * canard["span"] * 0.45
    bearing_sep = 0.20
    res["canard"] = dict(input=canard, hinge_cases=hc, H_max_Nm=max(abs(r["H_Nm"]) for r in hc),
                         actuator_stall_torque_Nm=1.25 * AERO["hinge_bound_factor"]["value"] * max(abs(r["H_Nm"]) for r in hc),
                         rate_deg_s=40.0, travel_deg=[-20, 25],
                         ultimate_lift_N=Lc_ult, spindle_root_moment_ult_Nm=spindle_M,
                         spindle_bearing_separation_m=bearing_sep,
                         spindle_bearing_force_ult_N=spindle_M / bearing_sep + Lc_ult,
                         ti_spindle_outer_diameter_m=(32 * spindle_M / (math.pi * MATERIAL["ti64_Ftu_Pa"]["value"] * 0.8 * (1 - 0.6 ** 4))) ** (1 / 3),
                         basis="DERIVED; canard CL limits and pivot location SYNTHETIC_UNVALIDATED")
    res["cassette_mechanism"] = cassette_mechanism(w, masses["total_kg"])
    return res


def carry_through(root_ult_ff, lock_stations=(1.17, 0.24), support_y=0.62, depth=0.251, width=0.857,
                  face_t=0.0015, core_t=0.012):
    """Sleeve (carry-through) box: overhang bending between the outboard lock station and the tub
    support, facesheet stress and simply-supported sandwich-panel buckling (k=4, long plate)."""
    M, V = root_ult_ff["Mx"], root_ult_ff["V"]
    D = lock_stations[0] - lock_stations[1]
    F_out, F_in = M / D + V, M / D
    M_support = F_out * (lock_stations[0] - support_y) - F_in * max(0.0, lock_stations[1] - support_y)
    E_face = 60e9  # quasi-isotropic IM7/8552 facesheet, DERIVED
    A_face = width * face_t
    h = depth - face_t
    sigma = M_support / (h * A_face)
    Dp = E_face * face_t * (core_t + face_t) ** 2 / 2
    sigma_cr = 4 * math.pi ** 2 * Dp / (width ** 2 * face_t)
    mono_t = 0.006
    sigma_mono = M_support / ((depth - mono_t) * width * mono_t)
    sigma_cr_mono = 4 * math.pi ** 2 * E_face * mono_t ** 2 / (12 * (1 - 0.3 ** 2) * width ** 2)
    return dict(station_forces_N=dict(outboard=F_out, inboard=F_in), support_y_m=support_y,
                bending_at_support_Nm=M_support, sandwich=dict(face_mm=face_t * 1e3, core_mm=core_t * 1e3,
                                                               face_stress_Pa=sigma, buckling_stress_Pa=sigma_cr,
                                                               buckling_margin=sigma_cr / sigma - 1),
                monolithic_6mm_check=dict(stress_Pa=sigma_mono, buckling_stress_Pa=sigma_cr_mono,
                                          buckling_margin=sigma_cr_mono / sigma_mono - 1),
                basis="DERIVED closed-form; supports idealised as rigid tub posts at |y|=0.62 m; not FEA")


def tongue_check(root_ult_ff, depth, width, length, lock_spacing=0.94, label=""):
    """Root tongue at the outboard lock station: strain-limited CFRP caps for the full root moment,
    webs for the couple shear (method as size_box). Closed-form screening only."""
    E, eps = MATERIAL["E_cap_Pa"]["value"], MATERIAL["strain_allow_ult"]["value"]
    tau, rho = MATERIAL["tau_allow_ult_Pa"]["value"], MATERIAL["cfrp_density"]["value"]
    M, V = root_ult_ff["Mx"], root_ult_ff["V"]
    h = depth
    t_cap = M / (0.9 * h * E * eps * width)
    shear = M / lock_spacing + V
    t_web = shear / (2 * 0.8 * h * tau)
    mass = rho * (2 * width * t_cap + 2 * h * t_web) * length * 1.6   # +60% lug inserts, ribs, bores (SYNTHETIC)
    return dict(label=label, depth_m=depth, width_m=width, length_m=length, cap_thickness_m=t_cap, web_thickness_m=t_web,
                web_shear_N=shear, mass_estimate_kg=mass, EI_Nm2=2 * E * t_cap * width * (h / 2) ** 2,
                basis="DERIVED closed-form, strain-limited caps; +60% fittings factor SYNTHETIC_UNVALIDATED")


def divider_spar_check(root_ult_ff, lock_stations=(1.17, 0.24), mouth_y=1.235, post_y=0.635, depth=0.114, cap_w=0.03):
    """A10 divider spar: one pin of each station pair. Outboard pin load goes 0.065 m to the Ti mouth-flange
    bulkhead; inboard pin load cantilevers 0.395 m from the divider post."""
    M, V = root_ult_ff["Mx"], root_ult_ff["V"]
    D = lock_stations[0] - lock_stations[1]
    P_out, P_in = (M / D + V) / 2, (M / D) / 2
    M_div = max(P_out * (mouth_y - lock_stations[0]), P_in * (post_y - lock_stations[1]))
    E, eps = MATERIAL["E_cap_Pa"]["value"], MATERIAL["strain_allow_ult"]["value"]
    A_cap = M_div / (0.9 * depth * E * eps)
    t_web = P_out / (0.8 * depth * MATERIAL["tau_allow_ult_Pa"]["value"])
    return dict(pin_load_out_N=P_out, pin_load_in_N=P_in, max_bending_Nm=M_div, cap_area_m2=A_cap,
                cap_thickness_at_width_m=A_cap / cap_w, cap_width_m=cap_w, web_thickness_m=t_web,
                basis="DERIVED closed-form; rigid mouth-flange bulkhead and post idealised; not FEA")


def flutter_validation():
    """Reference typical section (Hodges & Pierce, 'Introduction to Structural Dynamics and
    Aeroelasticity', Ch.5 example): a=-1/5, x_a=0.1, mu=20, r^2=6/25, sigma=0.4.
    Published flutter speed approx U/(b omega_theta) = 2.17 (k-method & p-k)."""
    r = flutter_k_method(20.0, -0.2, 0.1, 6 / 25, 0.4)
    return dict(case="H&P typical section", computed=r["V_over_b_omega_alpha"], k=r["k_flutter"], reference=2.17)


def measured_constraints():
    inv = json.loads(INVENTORY.read_text())
    ob = {o["name"]: o for o in inv["objects"]}
    def bb(n):
        b = ob[n]["bounds"]
        return dict(min=[round(x, 4) for x in b["min"]], max=[round(x, 4) for x in b["max"]])
    keys = ["PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL", "SEAT_DRIVER_CFRP_ENERGY_ABSORBING_BACK",
            "SEAT_DRIVER_INTEGRATED_HEAD_RESTRAINT", "MOUNT_001_WING_CARBON_CARRY_THROUGH_BENDING_BOX",
            "PHANTOM_LEFT_TRIANGULAR_COUPÉ_SIDEGLASS", "PHANTOM_LEFT_BLACK_INVERTED_SPEAR_DOOR",
            "PHANTOM_REAR_LEFT_WIDEBODY_ANGULAR_FENDER", "WHEEL_RL_CLOSED_TYRE", "PHANTOM_LEFT_ANGULAR_RAKED_V_TAIL",
            "PHANTOM_CARBON_CENTRAL_REAR_DORSAL", "TUB_REAR_MOTOR_CFRP_FULL_WIDTH_BULKHEAD",
            "TUB_L_REAR_CONTINUOUS_SHEAR_WALL", "DUCT_ENGINE_MAIN_SHOULDER_INLET_LEFT_SEALING_PERIMETER",
            "PHANTOM_LEFT_WING_AERODYNAMIC_ENVELOPE", "PHANTOM_LEFT_NOSE_CANARD_STOWED_BLADE", "WHEEL_FL_CLOSED_TYRE",
            "LEG_RL_CFRP_GAITOR"]
    out = {}
    for k in keys:
        name = k if k in ob else next((n for n in ob if n.startswith(k[:30])), None)
        if name:
            out[name] = bb(name)
    return out


def main():
    # A8 as drawn (MEASURED planform from deployed frame 85-117 of the pinned source; 46 mm flat plate)
    a8 = Wing(name="A8_as_drawn", y_root=0.91, span_exp=2.17, c_root=1.10, c_tip=0.25,
              x_le_root=-0.45, x_le_tip=-1.55, tc_root=0.046 / 1.10, tc_tip=0.046 / 0.25, z=0.93,
              joint={}, source="MEASURED envelope bounds x -1.69..-0.41, y 0.91..3.08, plate 0.046 m; chords approximate from outline")
    # Option T: telescopic stacked-sleeve cassette (body-change candidate; see report)
    opt_t = Wing(name="T_telescopic_sleeve", y_root=1.12, span_exp=1.35, c_root=0.80, c_tip=0.32,
                 x_le_root=-0.66, x_le_tip=-1.14, tc_root=0.11, tc_tip=0.10, z=0.95,
                 joint=dict(tongue_length_m=0.85, lock_spacing_m=0.76),
                 source="geometry chosen to fit measured bay x -0.63..-1.48, z 0.82..1.06, |y|<=1.12; straight TE at x -1.46")
    # A9 build geometry (approved Option T): shoulder flank moved out to the fender line |y| = 1.245,
    # which lengthens the sleeve to 2.43 m and allows a 1.05 m tongue with 0.94 m lock-station spacing.
    a9 = Wing(name="A9_cassette_build", y_root=1.245, span_exp=1.35, c_root=0.80, c_tip=0.32,
              x_le_root=-0.66, x_le_tip=-1.14, tc_root=0.11, tc_tip=0.10, z=0.95,
              joint=dict(tongue_length_m=1.05, lock_spacing_m=0.94),
              source="A9 revision geometry (tools/phantom/build_a9_cassette.py); bay x -0.62..-1.49, z 0.815..1.066, |y|<=1.245")
    # A10: split-level cassette. Panels share one level (common height); tongues run side by side in fore/aft
    # channels. Stroke 1.205 m keeps each panel on its own side: exposed span 1.184 m (tip |y| 2.429), tip chord
    # 0.32 -> 0.42 m. Tongue 1.05 m, stations 0.94 m apart; pin pair x-separation 0.41 m (channel width).
    a10 = Wing(name="A10_split_level", y_root=1.245, span_exp=1.184, c_root=0.80, c_tip=0.42,
               x_le_root=-0.66, x_le_tip=-1.04, tc_root=0.11, tc_tip=0.10, z=0.987,
               joint=dict(tongue_length_m=1.05, lock_spacing_m=0.94, pin_pair_separation_m=0.41),
               source="A10 revision geometry (tools/phantom/build_a10_cassette.py); both chord planes z 0.987 (MEASURED-K)")
    canard_a8 = dict(name="A8 canard", S=0.32 * 2, c=0.55, span=0.65, x_ac=1.70, CLalpha=3.0,
                     basis="MEASURED planform ~0.32 m^2 per side from pinned source; CLalpha SYNTHETIC")
    canard_a9 = dict(name="A9 telescopic all-moving canard", S=(0.60 + 0.36) / 2 * 0.58 * 2, c=0.49, span=0.58, x_ac=1.71,
                     CLalpha=3.0, basis="A9 build planform (root 0.60, tip 0.36, span 0.58 per side); CLalpha SYNTHETIC")
    body_munk = 4.35 * 0.85  # MEASURED hull volume 4.35 m^3 x (k2-k1)~0.85 SYNTHETIC
    x_cgs = [-0.25, -0.50, -0.75]
    results = dict(
        schema="phantom-wing-loads-0.1",
        disclaimer="Closed-form screening only. Not FEA, CFD or coupled aeroelastic analysis. Kinematic Blender checks are separate.",
        inputs=dict(mass=MASS, speeds=SPEEDS, envelope=ENVELOPE, material=MATERIAL, bearings=BEARINGS, aero=AERO,
                    body_munk_volume_m3=lab(body_munk, "DERIVED", "MEASURED hull volume 4.35 m^3 x SYNTHETIC (k2-k1)=0.85"),
                    x_cg_candidates=lab(x_cgs, "SYNTHETIC_UNVALIDATED", "no mass ledger yet; mid/rear-engine estimate -0.25")),
        measured_constraints=measured_constraints(),
        flutter_method_validation=flutter_validation(),
        cases={},
    )
    n_pos, n_neg = ENVELOPE["n_pos_limit"]["value"], ENVELOPE["n_neg_limit"]["value"]
    for w, cn in ((a8, canard_a8), (opt_t, canard_a8), (a9, canard_a9), (a10, canard_a9)):
        results["cases"][w.name] = analyse(w, cn, body_munk, x_cgs, n_pos, n_neg, w.name)
    a9r = results["cases"][a9.name]
    a9r["carry_through"] = carry_through(a9r["root_joint"]["applied_ultimate_with_fitting_factor"])
    a10r = results["cases"][a10.name]
    ff10 = a10r["root_joint"]["applied_ultimate_with_fitting_factor"]
    a10r["carry_through"] = carry_through(ff10)
    a10r["tongue_check"] = tongue_check(ff10, 0.095, 0.394, 1.05, label="A10 half-chord tongue 0.095 x 0.394 m")
    a10r["tongue_check_A9_reference"] = tongue_check(a9r["root_joint"]["applied_ultimate_with_fitting_factor"], 0.090, 0.822, 1.05,
                                                     label="A9 full-chord tongue 0.090 x 0.822 m (same method, comparison)")
    a10r["divider_spar"] = divider_spar_check(ff10)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=float))
    print(json.dumps(summary(results), indent=1, default=lambda v: round(v, 3) if isinstance(v, float) else v))


def summary(r):
    s = dict(flutter_validation=r["flutter_method_validation"])
    for k, c in r["cases"].items():
        vn = c["vn"]["mtow"]
        s[k] = dict(
            S_ref=c["planform"]["S_ref"], span=c["planform"]["span"], AR=c["planform"]["AR"], x_ac_mac=c["planform"]["x_ac_mac"],
            VS1=vn["VS1"], VA=vn["VA"], VD=vn["VD"], gust_n_VC=vn["gust_VC"]["n_pos"], gust_n_VC_light=c["vn"]["min_flying"]["gust_VC"]["n_pos"],
            root_ult=c["root_envelope_ultimate"], wing_mass=c["box_sizing"]["masses"],
            joints={n: dict(F_kN=o["max_pin_force_N"] / 1e3, d_mm=o["pin_diameter_m"] * 1e3, lug_mm=o["ti_lug_thickness_m"] * 1e3, sep=o["couple_separation_m"])
                    for n, o in c["root_joint"]["options"].items()},
            freq=dict(fb=c["aeroelastic"]["f_bending_Hz"], ft=c["aeroelastic"]["f_torsion_Hz"]),
            flutter_SL_EAS=c["aeroelastic"]["flutter_SL"]["VF_EAS"], V_rev=c["aeroelastic"]["V_reversal_EAS"],
            V_div=c["aeroelastic"]["V_divergence_EAS_unswept"],
            roll=[(round(x["V"]), round(x["p_deg_s"]), x["time_to_90deg_bank_s"]) for x in c["roll"]["cases"]],
            ail=dict(H=c["control_surfaces"]["aileron"]["H_max_nominal_Nm"], T=c["control_surfaces"]["aileron"]["actuator_stall_torque_Nm"],
                     F=c["control_surfaces"]["aileron"]["linear_EMA"]["stall_force_N"]),
            flap=dict(H=c["control_surfaces"]["flap"]["H_max_nominal_Nm"], T=c["control_surfaces"]["flap"]["actuator_stall_torque_Nm"]),
            np=c["longitudinal"]["neutral_point"],
            trim=[(t["x_cg"], t["min_speed_full_wingborne_trim"], round(t["rows"][-1]["canard_lift_share"], 2), round(t["rows"][-1]["CL_canard"], 2)) for t in c["longitudinal"]["trim"]],
            canard=dict(H=c["canard"]["H_max_Nm"], T=c["canard"]["actuator_stall_torque_Nm"], spindle_d=c["canard"]["ti_spindle_outer_diameter_m"]),
            cassette=dict(F=c["cassette_mechanism"]["slide_actuator_force_N"], P=c["cassette_mechanism"]["slide_mech_power_W"]),
        )
    return s


if __name__ == "__main__":
    main()
