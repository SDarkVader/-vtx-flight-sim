"""Opt-in real-component profiles for the Ricochet RC-01 plant.

A profile replaces the idealised surface servos with the selected off-the-shelf actuators
(torque and torque-speed limits read from ``docs/ricochet/components/components.json``)
and adds hinged planing or cambered hydrofoil-section skis with fins under the outboard
sponson pods (and optionally a compact aft trim ski/foil under the stern). Nothing here is
used unless a ``RicochetCraft`` is built with ``profile=...``; the legacy plant is unchanged.

Ski hydrodynamics (per ski, every rigid-body step):
  * planing (trailing edge wet, leading edge dry): Savitsky flat/deadrise-plate lift
    C_L0 = tau^1.1 (0.012 lambda^0.5 + 0.0055 lambda^2.5 / Cv^2), wetted length from the
    geometric waterline crossing, centre of pressure
    l_p / (lambda b) = 0.75 - 1 / (5.21 Cv^2 / lambda^2 + 2.39) from the trailing edge;
    the hydrostatic (second) term is faded in with Cv (transom ventilation) and the
    dynamic term uses the flow angle so heave and pitch rates are damped;
  * fully submerged (planing mode): low-aspect-ratio plate
    C_N = (pi AR / 2) sin a + 2 sin a |sin a| with a free-surface (image) factor,
    C^1-blended from planing over half a beam of leading-edge depth, with regularized CP
    (0.50 + 0.20 * u / hypot(u, wn, 0.2)) * len_w so pure heave at rest gives zero pitch moment;
  * fully submerged (hydrofoil_ski mode): 3-D finite-span cambered hydrofoil with Helmbold
    lift slope, Breslin/Wadlin free-surface factor, physical cavitation & shallow ventilation
    caps, ITTC-57 + form-factor profile drag, 3-D induced + image-vortex free-surface wave drag,
    quarter-chord AC + camber pitching moment Cm_ac, C^1-blended into Savitsky planing as the
    leading edge breaches the free surface;
  * surface-piercing strut (optional): ITTC-57 section profile drag + Hoerner spray drag
    (0.24 * t^2) + lateral hydrodynamic damping;
  * fin (optional): Helmbold lift slope, end-plate effect when root is wet, lift capped
    (ventilation cap when surface-piercing);
  * strictly passive centroidal heave drag + 6-strip chordwise rotational pitch-rate damping;
  * smooth 6-strip plate buoyancy (zero grazing step discontinuity);
  * C^1 smooth strip-theory added inertia about the incidence hinge.
Assumptions are named in the profile file and the component register.
"""

from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILE_DIR = REPO_ROOT / 'inputs' / 'ricochet_profiles'
PROFILE_FILES = {
    'rc01-real-components-v1': 'rc01_real_components_v1.json',
    'rc01-planing-3pt-v1': 'rc01_planing_3pt_v1.json',
    'rc01-hydrofoil-ski-v1': 'rc01_hydrofoil_ski_v1.json',
}

PROFILE_REVISIONS = {
    None: 'RC01-CA-0',
    'rc01-real-components-v1': 'RC01-CA-1',
    'rc01-planing-3pt-v1': 'RC01-P1-R1',
    'rc01-hydrofoil-ski-v1': 'RC01-H1-R1',
}

PROFILE_REVISION_ALIASES: dict[str, str | None] = {
    'rc01-ca-0': None,
    'rc01-ca0': None,
    'legacy': None,
    'rc01-ca-1': 'rc01-real-components-v1',
    'rc01-ca1': 'rc01-real-components-v1',
    'rc01-real-components-v1': 'rc01-real-components-v1',
    'rc01-p1-r1': 'rc01-planing-3pt-v1',
    'rc01-p1': 'rc01-planing-3pt-v1',
    'rc01-planing-3pt-v1': 'rc01-planing-3pt-v1',
    'rc01-h1-r1': 'rc01-hydrofoil-ski-v1',
    'rc01-h1': 'rc01-hydrofoil-ski-v1',
    'rc01-hydrofoil-ski-v1': 'rc01-hydrofoil-ski-v1',
}


def resolve_profile_id(profile_or_revision: str | None) -> str | None:
    """Resolve a canonical profile ID or model revision code (e.g. 'RC01-P1-R1', 'RC01-H1-R1', 'RC01-CA-0')."""
    if profile_or_revision is None or profile_or_revision == '':
        return None
    if not isinstance(profile_or_revision, str):
        raise ValueError(f'Unknown Ricochet profile {profile_or_revision!r}; no substitution allowed')
    key = profile_or_revision.strip().lower()
    if key in PROFILE_REVISION_ALIASES:
        return PROFILE_REVISION_ALIASES[key]
    if profile_or_revision in PROFILE_FILES:
        return profile_or_revision
    raise ValueError(f'Unknown Ricochet profile or model revision {profile_or_revision!r}; no substitution allowed')


def _smoothstep(x: float) -> float:
    """C^1 cubic Hermite ramp on [0, 1] with zero derivative at both endpoints."""
    t = min(max(float(x), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


@lru_cache(maxsize=None)
def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_profile(profile_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a named profile (by profile_id or model_revision alias); ``overrides`` is for calibration sweeps only."""
    resolved = resolve_profile_id(profile_id)
    if resolved is None or resolved not in PROFILE_FILES:
        raise ValueError(f'Unknown Ricochet profile {profile_id!r}; no substitution allowed')
    prof = copy.deepcopy(_load_json(str(PROFILE_DIR / PROFILE_FILES[resolved])))
    if prof.get('profile_id') != resolved:
        raise ValueError(f'Profile file does not declare {resolved!r}')
    reg = copy.deepcopy(_load_json(str(REPO_ROOT / prof['components_register'])))
    prof['_components'] = reg['components']
    if overrides:
        _deep_merge(prof, overrides)
        prof['_overrides'] = copy.deepcopy(overrides)
    return prof


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)


def rotary_envelope(component: dict[str, Any], degraded: bool = False) -> dict[str, float]:
    """Torque / speed envelope of a rotary EMA from its register entry."""
    if degraded and 'degraded_one_channel' in component:
        dg = component['degraded_one_channel']
        return {
            'rated_nm': float(dg['rated_torque_nm']),
            'peak_nm': float(dg['peak_torque_nm']),
            'no_load_deg_s': float(dg['no_load_deg_s_max']),
            'rated_deg_s': float(dg['rated_deg_s_max']),
        }
    return {
        'rated_nm': float(component['torque_nm']['rated_at_rated_speed']),
        'peak_nm': float(component['torque_nm']['peak']),
        'no_load_deg_s': float(component['speed_deg_s']['no_load']),
        'rated_deg_s': float(component['speed_deg_s']['at_rated_torque']),
    }


def linear_on_lever_envelope(component: dict[str, Any], lever_m: float, stroke_mm: float | None = None) -> dict[str, float]:
    """Hinge torque / rate / travel of a linear EMA on a lever. No peak published -> continuous is the limit."""
    f_cont = float(component['force_n']['continuous_motor_limited'])
    v_max = float(component['speed_mm_s']['max']) / 1000.0
    torque = f_cont * float(lever_m)
    rate = math.degrees(v_max / float(lever_m))
    stroke = float(stroke_mm if stroke_mm is not None else component['stroke_mm']['selected'])
    s_min, s_max = float(component['stroke_mm']['min']), float(component['stroke_mm']['max'])
    if not s_min <= stroke <= s_max:
        raise ValueError(f'stroke {stroke} mm outside the published {s_min}-{s_max} mm range')
    # Rod moves along the lever tangent at mid-travel: travel = 2 asin(s / 2r)
    travel = math.degrees(2.0 * math.asin(min(1.0, stroke / 1000.0 / (2.0 * float(lever_m)))))
    return {'rated_nm': torque, 'peak_nm': torque, 'no_load_deg_s': rate, 'rated_deg_s': rate,
            'stroke_mm': stroke, 'travel_deg': travel}


def linear_actuator_mass_kg(component: dict[str, Any], stroke_mm: float) -> float:
    """Mass from the published zero-stroke mass plus mass per inch of stroke."""
    m = component['mass_kg']
    return float(m['zero_stroke']) + float(m['per_inch_stroke']) * float(stroke_mm) / 25.4


def max_rate_deg_s(env: dict[str, float], opposing_load_nm: float) -> float:
    """Linear torque-speed line through (0, no-load) and (rated torque, rated speed); stall at peak."""
    load = max(0.0, float(opposing_load_nm))
    if load >= env['peak_nm']:
        return 0.0
    wn, wr, tr = env['no_load_deg_s'], env['rated_deg_s'], max(env['rated_nm'], 1e-6)
    return max(0.0, wn - (wn - wr) * load / tr)


def servo_gains(env: dict[str, float], inertia_kg_m2: float, damping_ratio: float = 1.0) -> tuple[float, float]:
    """kp = rated torque per degree of error (assumed loop stiffness); kv for the given damping ratio."""
    kp = env['rated_nm'] / math.radians(1.0)
    kv = 2.0 * damping_ratio * math.sqrt(kp * max(inertia_kg_m2, 1e-4))
    return kp, kv


def _ittc_cf(speed: float, length: float, nu: float) -> float:
    re = max(abs(speed) * max(length, 1e-3) / max(nu, 1e-9), 2.0e4)
    return 0.075 / (math.log10(re) - 2.0) ** 2 + 0.0004


def ski_hydro(
    ski: dict[str, Any],
    origin_w: np.ndarray,
    rot_w: np.ndarray,
    v_origin_w: np.ndarray,
    omega_w: np.ndarray,
    sample: Callable[[np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]],
    rho: float,
    nu: float,
    g: float,
    fin_steer_rad: float = 0.0,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], dict[str, Any]]:
    """Forces on one ski (world frame) as (application point, force) pairs, plus telemetry.

    Ski body frame: origin at the incidence pivot, +x forward, +y port, +z up (joint at 0).
    ``sample(x, y, z)`` returns (eta[N], water_velocity[N, 3]).
    """
    L = float(ski['length_m'])
    b = float(ski['beam_m'])
    t_pl = float(ski['thickness_m'])
    a = float(ski['hinge_from_trailing_edge_m'])
    zb = float(ski['bottom_below_pivot_m'])
    hydro_mode = str(ski.get('hydro_mode', 'planing'))
    deadrise_deg = max(0.0, float(ski.get('deadrise_deg', 0.0)))
    fin = ski.get('fin')
    strut = ski.get('strut')
    ex, ey, ez = rot_w[:, 0], rot_w[:, 1], rot_w[:, 2]

    def to_w(p_local: tuple[float, float, float]) -> np.ndarray:
        return origin_w + rot_w @ np.asarray(p_local, dtype=np.float64)

    def vel_at(p_w: np.ndarray, w_vel: np.ndarray) -> np.ndarray:
        return v_origin_w + np.cross(omega_w, p_w - origin_w) - w_vel

    te = to_w((-a, 0.0, -zb))
    le = to_w((L - a, 0.0, -zb))
    sample_pts = [te, le]
    fin_idx = -1
    if fin:
        fr = to_w((float(fin['x_from_pivot_m']), 0.0, -zb))
        ft = to_w((float(fin['x_from_pivot_m']), 0.0, -zb - float(fin['span_m'])))
        fin_idx = len(sample_pts)
        sample_pts.append(fr)
    strut_idx = -1
    if strut:
        st_x = float(strut.get('x_from_pivot_m', 0.0))
        st_bot = to_w((st_x, 0.0, -zb + t_pl))
        st_top = to_w((st_x, 0.0, float(strut.get('top_above_pivot_m', 0.45))))
        strut_idx = len(sample_pts)
        sample_pts.append(st_bot)

    pts = np.stack(sample_pts)
    eta, wvel = sample(pts[:, 0], pts[:, 1], pts[:, 2])
    d_te = float(eta[0] - te[2])
    d_le = float(eta[1] - le[2])
    forces: list[tuple[np.ndarray, np.ndarray]] = []
    tel: dict[str, Any] = {'d_te_m': round(d_te, 4), 'd_le_m': round(d_le, 4), 'hydro_mode': hydro_mode}
    tau_g = math.asin(float(np.clip(ex[2], -1.0, 1.0)))  # leading edge up > 0
    tel['trim_geom_deg'] = round(math.degrees(tau_g), 3)

    # ---------------- planing / hydrofoil lifting surface ----------------
    if d_te <= 0.0 and d_le <= 0.0:
        regime = 'dry'
        s0 = s1 = 0.0
    elif d_le <= 0.0:
        regime = 'planing'
        s0, s1 = 0.0, L * d_te / max(d_te - d_le, 1e-9)
    elif d_te <= 0.0:
        regime = 'nose_dug'
        s0, s1 = L * (-d_te) / max(d_le - d_te, 1e-9), L
    else:
        regime = 'submerged'
        s0, s1 = 0.0, L
    lw = max(0.0, s1 - s0)
    tel.update(regime=regime, wetted_length_m=round(lw, 4))
    n_total = 0.0
    if lw > 1e-3:
        s_c = 0.5 * (s0 + s1)
        pc = te + ex * s_c
        wvel_c = wvel[0] if regime != 'nose_dug' else wvel[1]
        v_rel = vel_at(pc, wvel_c)
        u = float(v_rel @ ex)
        wn = float(v_rel @ ez)
        u_pos = max(u, 0.0)
        alpha = math.atan2(-wn, max(u_pos, 0.3))
        cv = u_pos / math.sqrt(g * b)
        cos_t = max(math.cos(tau_g), 0.2)

        def planing(lam_len: float) -> tuple[float, float, float, float]:
            lam = max(lam_len / b, 0.05)
            tf = min(max(math.degrees(alpha), 0.0), 20.0)
            tg = min(max(math.degrees(tau_g), 0.0), 20.0)
            cl0_dyn = (tf ** 1.1) * 0.012 * math.sqrt(lam)
            vent = _smoothstep((cv - 0.5) / 1.0)  # transom clears smoothly from Cv ~0.5 to 1.5
            cl0_hs = vent * (tg ** 1.1) * 0.0055 * (lam ** 2.5) / max(cv * cv, 0.25) if cv > 0.5 else 0.0
            if deadrise_deg > 0.0:
                cl0_tot = cl0_dyn + cl0_hs
                clb_tot = max(0.0, cl0_tot - 0.0065 * deadrise_deg * (cl0_tot ** 0.60))
                scale_beta = clb_tot / max(cl0_tot, 1e-9) if cl0_tot > 1e-9 else 1.0
            else:
                scale_beta = 1.0
            l_dyn = scale_beta * 0.5 * rho * u_pos * u_pos * b * b * cl0_dyn
            l_hs = scale_beta * vent * 0.5 * rho * g * (b ** 3) * (tg ** 1.1) * 0.0055 * (lam ** 2.5)
            n = (l_dyn + l_hs) / cos_t
            cvv = max(cv, 1e-3)
            frac = 0.75 - 1.0 / (5.21 * cvv * cvv / (lam * lam) + 2.39)
            lp = min(max(frac, 0.1), 0.9) * lam_len
            cf = _ittc_cf(u_pos, lam_len, nu)
            df = 0.5 * rho * u_pos * u_pos * cf * b * lam_len / cos_t
            return n, lp, df, 0.0

        def submerged_plate(len_w: float, depth_mid: float) -> tuple[float, float, float, float]:
            ar = b / max(len_w, 1e-3)
            v2 = u_pos * u_pos + wn * wn
            sa = math.sin(alpha)
            cn = 0.5 * math.pi * ar * sa + 2.0 * sa * abs(sa)
            hc = max(depth_mid, 0.0) / max(len_w, 1e-3)
            k_fs = (1.0 + 16.0 * hc * hc) / (2.0 + 16.0 * hc * hc)
            n = 0.5 * rho * v2 * b * len_w * cn * k_fs
            cf = _ittc_cf(u_pos, len_w, nu)
            df = 0.5 * rho * u_pos * u_pos * cf * 2.0 * b * len_w
            # Regularized CP: exact 0.50 at rest (zero heave pitching torque), 0.70 underway forward
            cp_frac = 0.50 + 0.20 * u / math.hypot(u, wn, 0.2)
            return n, cp_frac * len_w, df, 0.0

        def submerged_foil(len_w: float, depth_mid: float) -> tuple[float, float, float, float]:
            """3-D cambered hydrofoil with free-surface image factor, cavitation/ventilation caps & wave drag."""
            c_f = float(ski.get('foil_chord_m', L))
            b_f = float(ski.get('foil_span_m', b))
            ar = b_f / max(c_f, 1e-3)
            hc = max(depth_mid, 0.0) / max(c_f, 1e-3)
            k_fs = (1.0 + 16.0 * hc * hc) / (2.0 + 16.0 * hc * hc)
            a_3d = 2.0 * math.pi * ar / (2.0 + math.sqrt(ar * ar + 4.0))
            u_circ = _smoothstep(u_pos / 0.8)
            alpha_0 = math.radians(float(ski.get('foil_alpha0_deg', -3.5)))
            alpha_eff = alpha - u_circ * alpha_0
            cl_lin = a_3d * k_fs * math.sin(alpha_eff)

            # Physical cavitation + shallow surface ventilation + stall limits
            p_amb_minus_pv = 99000.0 + rho * g * max(depth_mid, 0.0)
            q_u = 0.5 * rho * u_pos * u_pos
            sigma_c = p_amb_minus_pv / max(q_u, 1.0)
            cl_cav = 0.55 * sigma_c + 0.15
            cl_vent = 0.35 + 0.90 * _smoothstep(hc / 0.45)
            cl_stall = float(ski.get('foil_cl_stall', 1.25))
            cl_cap = min(cl_stall, cl_cav, cl_vent)
            cl = float(np.clip(cl_lin, -cl_cap, cl_cap))

            v2 = u_pos * u_pos + wn * wn
            q_flow = 0.5 * rho * v2
            s_foil = b_f * len_w
            l_foil = q_flow * s_foil * cl * u_circ

            tc = float(ski.get('foil_tc', 0.11))
            ff = 1.0 + 2.0 * tc + 60.0 * (tc ** 4)
            cf = _ittc_cf(u_pos, len_w, nu)
            cd0 = 2.0 * cf * ff
            e_osw = float(ski.get('foil_oswald_e', 0.80))
            k_wave_i = 1.0 + 1.0 / (1.0 + 16.0 * hc * hc)
            cd_i = (cl * cl) / (math.pi * e_osw * max(ar, 0.2)) * k_wave_i
            cd_sep = 1.6 * (max(0.0, abs(alpha) - math.radians(14.0)) ** 2)
            d_foil = q_flow * s_foil * (cd0 + cd_i + cd_sep)

            # Strictly passive flow-axis projection + low-speed cross-flow heave drag
            n_xflow = (1.0 - u_circ) * (-0.5 * rho * 1.2 * s_foil * wn * abs(wn))
            ca, sa = math.cos(alpha), math.sin(alpha)
            n = l_foil * ca + d_foil * sa + n_xflow
            df = d_foil * ca - l_foil * sa

            ac_frac = float(ski.get('foil_ac_from_te_frac', 0.75))
            cp_frac = 0.50 + (ac_frac - 0.50) * u_circ
            cm_ac = float(ski.get('foil_cm_ac', -0.075))
            m_ac_le_up = q_flow * s_foil * len_w * cm_ac * u_circ  # < 0 pitches LE down
            tel['foil_cl'] = round(cl, 4)
            tel['foil_cl_cav_cap'] = round(cl_cav, 3)
            tel['foil_sigma_cav'] = round(sigma_c, 3)
            tel['foil_ld'] = round(l_foil / max(d_foil, 1e-3), 2) if d_foil > 1e-2 else 0.0
            return n, cp_frac * len_w, df, m_ac_le_up

        submerged_fn = submerged_foil if hydro_mode == 'hydrofoil_ski' else submerged_plate
        blend_len = float(ski.get('foil_chord_m', b)) if hydro_mode == 'hydrofoil_ski' else b

        m_couple = 0.0
        if regime == 'planing':
            if hydro_mode == 'hydrofoil_ski':
                f_foil_sk = _smoothstep(d_te / max(0.35 * blend_len, 0.02))
                n1, lp1, df1, m1 = planing(lw)
                n2, lp2, df2, m2 = submerged_foil(lw, 0.5 * d_te)
                n = (1.0 - f_foil_sk) * n1 + f_foil_sk * n2
                lp = (1.0 - f_foil_sk) * lp1 + f_foil_sk * lp2
                df = (1.0 - f_foil_sk) * df1 + f_foil_sk * df2
                m_couple = (1.0 - f_foil_sk) * m1 + f_foil_sk * m2
                p_n = te + ex * lp
                f_sub = f_foil_sk
            else:
                n, lp, df, m_couple = planing(lw)
                p_n = te + ex * lp
                f_sub = 0.0
        elif regime == 'nose_dug':
            n, lp, df, m_couple = submerged_fn(lw, 0.5 * d_le)
            if hydro_mode == 'hydrofoil_ski':
                ac_max = float(ski.get('foil_ac_from_te_frac', 0.75)) * L
                p_n = te + ex * min(s0 + lp, ac_max)
            else:
                p_n = te + ex * (s0 + lp)
            f_sub = 1.0
        else:
            f_blend = _smoothstep(d_le / max(0.5 * blend_len, 0.05))
            n1, lp1, df1, m1 = planing(L)
            n2, lp2, df2, m2 = submerged_fn(L, 0.5 * (d_te + d_le))
            n = (1.0 - f_blend) * n1 + f_blend * n2
            lp = (1.0 - f_blend) * lp1 + f_blend * lp2
            df = (1.0 - f_blend) * df1 + f_blend * df2
            m_couple = (1.0 - f_blend) * m1 + f_blend * m2
            p_n = te + ex * lp
            f_sub = f_blend

        forces.append((p_n, ez * n))
        forces.append((pc, -ex * df * (1.0 if u >= 0.0 else -1.0)))
        if abs(m_couple) > 1e-9:
            # Pure couple about -ey (+m_couple pitches LE up, zero net force)
            forces.append((pc + 0.5 * ex, ez * m_couple))
            forces.append((pc - 0.5 * ex, -ez * m_couple))

        # Strictly passive centroidal low-speed heave drag (applied at wetted centroid pc, NOT p_n)
        w_lo = min(1.0, max(0.0, 1.0 - u_pos / 3.0))
        b_eff = float(ski.get('foil_span_m', b)) if hydro_mode == 'hydrofoil_ski' else b
        n_heave = w_lo * (1.0 - f_sub) * (-0.5 * rho * 1.2 * b_eff * lw * wn * abs(wn))
        if abs(n_heave) > 1e-9:
            forces.append((pc, ez * n_heave))

        # 6-strip chordwise rotational pitch-rate damping (strictly dissipative) & smooth plate buoyancy
        n_strips = 6
        ds = lw / n_strips
        omega_pitch = float(omega_w @ (-ey))  # + raises leading edge
        ar_eff = min(b_eff / max(lw, 0.2), 4.0)
        fb_total = 0.0
        fb_moment_s = 0.0
        for k in range(n_strips):
            s_k = s0 + (k + 0.5) * ds
            r_k = s_k - s_c
            if abs(omega_pitch) > 1e-9:
                wn_k = wn + r_k * omega_pitch
                dn_quad = -0.5 * rho * 1.2 * b_eff * ds * (wn_k * abs(wn_k) - wn * abs(wn))
                dn_circ = -0.5 * rho * (0.5 * math.pi * ar_eff) * u_pos * b_eff * ds * (r_k * omega_pitch)
                forces.append((te + ex * s_k, ez * (dn_quad + dn_circ)))
            d_k = d_te + (d_le - d_te) * (s_k / max(L, 1e-6))
            sub_t_k = min(max(d_k, 0.0), t_pl)
            fb_k = rho * g * b_eff * ds * sub_t_k
            fb_total += fb_k
            fb_moment_s += fb_k * s_k
        if fb_total > 1e-9:
            p_fb = te + ex * (fb_moment_s / fb_total)
            forces.append((p_fb, np.array([0.0, 0.0, fb_total])))

        n_total = n + n_heave
        tel.update(u_mps=round(u, 3), alpha_flow_deg=round(math.degrees(alpha), 3), cv=round(cv, 3),
                   lambda_=round(lw / b, 3), normal_n=round(n_total, 1), friction_n=round(df, 1),
                   buoyancy_n=round(fb_total, 1), cp_from_te_m=round(float((p_n - te) @ ex), 4))

    # ---------------- surface-piercing strut (optional) ----------------
    if strut and strut_idx >= 0:
        st_len = max(float(st_top[2] - st_bot[2]), 1e-3)
        h_st = min(max(float(eta[strut_idx] - st_bot[2]), 0.0), st_len)
        if h_st > 0.005:
            p_st = st_bot + (st_top - st_bot) * (0.5 * h_st / st_len)
            v_st = vel_at(p_st, wvel[strut_idx])
            u_st = float(v_st @ ex)
            v_st_lat = float(v_st @ ey)
            c_st = float(strut.get('chord_m', 0.18))
            t_st = float(strut.get('thickness_m', 0.036))
            tc_st = t_st / max(c_st, 1e-3)
            cf_st = _ittc_cf(u_st, c_st, nu)
            cd_st = 2.0 * cf_st * (1.0 + 2.0 * tc_st + 60.0 * (tc_st ** 4))
            q_st = 0.5 * rho * (u_st * u_st + v_st_lat * v_st_lat)
            d_prof = q_st * h_st * c_st * cd_st
            piercing = float(eta[strut_idx]) < float(st_top[2])
            d_spray = 0.5 * rho * u_st * abs(u_st) * 0.24 * (t_st * t_st) if piercing else 0.0
            d_strut = d_prof + abs(d_spray)
            fy_strut = -0.5 * rho * h_st * c_st * 1.1 * v_st_lat * abs(v_st_lat)
            forces.append((p_st, ey * fy_strut - ex * d_strut * (1.0 if u_st >= 0.0 else -1.0)))
            tel.update(strut_immersed_m=round(h_st, 4), strut_drag_n=round(d_strut, 1))
        else:
            tel.update(strut_immersed_m=0.0, strut_drag_n=0.0)

    # ---------------- fin (optional) ----------------
    if fin and fin_idx >= 0:
        span = float(fin['span_m'])
        chord = float(fin['chord_m'])
        h_imm = min(max(float(eta[fin_idx] - ft[2]), 0.0), span)
        fin_y = 0.0
        if h_imm > 0.01:
            root_wet = float(eta[fin_idx]) > float(fr[2])
            ar = (2.0 if root_wet else 1.0) * h_imm / chord
            cla = 2.0 * math.pi * ar / (2.0 + math.sqrt(ar * ar + 4.0))
            p_f = ft + (fr - ft) * (0.5 * h_imm / span)
            v_rel = vel_at(p_f, wvel[fin_idx])
            uf = float(v_rel @ ex)
            vf = float(v_rel @ ey)
            q = 0.5 * rho * (uf * uf + vf * vf)
            beta = math.atan2(vf, max(abs(uf), 0.3))
            cl_max = float(fin['cl_max_submerged'] if root_wet else fin['cl_max_piercing'])
            cl = float(np.clip(cla * (beta + fin_steer_rad), -cl_max, cl_max))
            area = h_imm * chord
            fin_y = -q * area * cl
            cd = 2.0 * _ittc_cf(uf, chord, nu) + cl * cl / (math.pi * 0.8 * max(ar, 0.1))
            fin_d = q * area * cd
            forces.append((p_f, ey * fin_y - ex * fin_d * (1.0 if uf >= 0.0 else -1.0)))
            tel.update(fin_immersed_m=round(h_imm, 4), fin_beta_deg=round(math.degrees(beta), 3),
                       fin_side_n=round(fin_y, 1), fin_drag_n=round(fin_d, 1),
                       fin_root_wet=bool(root_wet), fin_cl=round(cl, 4))
        else:
            tel.update(fin_immersed_m=0.0, fin_side_n=0.0)
    else:
        tel.update(fin_immersed_m=0.0, fin_side_n=0.0)

    # C^1 smooth strip-theory added (entrained-water) inertia about the incidence hinge
    if lw > 1e-3:
        x0, x1 = s0 - a, s1 - a
        b_am = float(ski.get('foil_span_m', b)) if hydro_mode == 'hydrofoil_ski' else b
        depth = max(0.0, 0.5 * (max(d_te, 0.0) + max(d_le, 0.0)))
        wet_ramp = _smoothstep(max(d_te, d_le) / max(t_pl, 0.02))
        k_fs_am = 0.5 + 0.5 * _smoothstep(d_le / max(0.5 * b_am, 0.05)) * _smoothstep(depth / max(b_am, 0.1))
        tel['added_inertia_kg_m2'] = wet_ramp * k_fs_am * rho * math.pi * 0.25 * b_am * b_am * (x1 ** 3 - x0 ** 3) / 3.0
    else:
        tel['added_inertia_kg_m2'] = 0.0

    # hinge moment about the incidence axis (joint axis = -y body): + raises the leading edge
    hm = 0.0
    for p, f in forces:
        hm += float(np.cross(p - origin_w, f) @ (-ey))
    tel['hinge_moment_nm'] = round(hm, 2)
    tel['normal_force_n'] = round(n_total, 1)
    return forces, tel


def classify_rc01_ecu_mode(u_mps: float, pilot_cmd: dict[str, float]) -> str:
    """Classify RC-01 operating regime across the 5 amphibious / WIG control-allocation modes."""
    u = max(0.0, float(u_mps))
    rev = float(pilot_cmd.get('reverse_bucket', 0.0))
    throt = float(pilot_cmd.get('throttle', 0.0))
    if rev > 0.08 or (u > 6.0 and throt < 0.08):
        return 'braking_flare'
    if u < 3.0:
        return 'displacement'
    if u < 11.5:
        return 'hump_transition'
    if u < 23.0:
        return 'on_plane_foil'
    return 'wig_skim'


def rc01_ecu_command(
    ecu_cfg: dict[str, Any],
    *,
    pilot_cmd: dict[str, float],
    u_mps: float,
    roll_deg: float,
    pitch_deg: float,
    roll_rate_deg_s: float,
    pitch_rate_deg_s: float,
    yaw_rate_deg_s: float,
    keel_clear_m: float,
    surface_limits: dict[str, dict[str, Any]],
    telemetry_out: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Telemetry-only on-board 5-mode speed-scheduled trim, coordinated-turn & stabilization ECU.

    Note sign conventions in VTX body frame (+X fwd, +Y port, +Z up):
      * roll_deg > 0 = right-wing down; +aileron_deg = right roll; +ski_differential_deg = port LE up (+right roll)
      * pitch_deg > 0 = nose DOWN (Euler xyz about +Y port!); pitch_nose_up_deg = -pitch_deg
      * +elevator_deg = TE up -> nose-UP pitch
      * +rudder_deg = TE port -> nose-left (+Z) yaw; yaw_rate_deg_s > 0 = nose-left yaw
    """
    out = dict(pilot_cmd)
    u = max(0.0, float(u_mps))
    mode = classify_rc01_ecu_mode(u, pilot_cmd)
    enabled = bool(ecu_cfg and ecu_cfg.get('enabled', False))
    base_target_nose_up = float(ecu_cfg.get('target_nose_up_deg', 3.0)) if ecu_cfg else 0.0
    if not enabled:
        if telemetry_out is not None:
            telemetry_out.update(
                enabled=False,
                assist=0.0,
                mode=mode,
                target_roll_deg=0.0,
                target_nose_up_deg=round(base_target_nose_up, 3),
                effective_command={k: round(float(v), 4) for k, v in out.items()},
            )
        return out
    blend = float(np.clip(pilot_cmd.get('ecu_assist', float(ecu_cfg.get('default_assist', 1.0))), 0.0, 1.0))
    if blend <= 1e-4:
        if telemetry_out is not None:
            telemetry_out.update(
                enabled=True,
                assist=round(blend, 3),
                mode=mode,
                target_roll_deg=0.0,
                target_nose_up_deg=round(base_target_nose_up, 3),
                effective_command={k: round(float(v), 4) for k, v in out.items()},
            )
        return out

    nose_up_deg = -float(pitch_deg)
    nose_up_rate = -float(pitch_rate_deg_s)
    u_gate = _smoothstep((u - 1.5) / 3.0)
    turn_gate = _smoothstep((u - 3.5) / 3.0)

    # Coordinated inward target bank angle (clipped to +/-12 deg) when pilot commands a turn underway (u > 3.5 m/s)
    pilot_rud = float(pilot_cmd.get('rudder_deg', 0.0))
    pilot_ail = float(pilot_cmd.get('aileron_deg', 0.0))
    pilot_diff = float(pilot_cmd.get('differential_thrust', 0.0))
    # Right turn: rudder_deg < 0 or aileron_deg > 0 or differential_thrust > 0 => target_roll_deg > 0 (lean right)
    turn_right_norm = (-pilot_rud / 30.0) + 0.70 * (pilot_ail / 25.0) + 0.50 * pilot_diff
    max_bank_deg = float(ecu_cfg.get('max_turn_bank_deg', 12.0))
    bank_gain_deg = float(ecu_cfg.get('turn_bank_gain_deg', 10.0))
    target_roll_deg = float(np.clip(turn_gate * bank_gain_deg * turn_right_norm, -max_bank_deg, max_bank_deg)) if u > 3.5 else 0.0

    # Bank lift compensation (+deg to ski_incidence_deg and elevator_deg) so nose doesn't drop in banked turns
    cos_phi = max(math.cos(math.radians(float(roll_deg))), 0.85)
    bank_lift_comp_deg = 1.5 * (1.0 / cos_phi - 1.0)

    # Braking / deceleration anti-dive flare guard when reverse_bucket > 0.08 at u > 4 m/s
    rev_cmd = float(pilot_cmd.get('reverse_bucket', 0.0))
    flare_active = (rev_cmd > 0.08 and u > 4.0)
    flare_ski_deg = 2.0 if flare_active else 0.0
    flare_elev_deg = 4.0 if flare_active else 0.0
    flare_aft_deg = -1.0 if flare_active else 0.0

    target_nose_up = base_target_nose_up + (1.0 if flare_active else 0.0)

    # 1. Speed-scheduled ski collective incidence wash-out + target height / pitch-trim feedback
    sched = ecu_cfg.get('ski_schedule_mps_deg')
    if sched and 'ski_incidence_deg' in surface_limits:
        xs = [float(pt[0]) for pt in sched]
        ys = [float(pt[1]) for pt in sched]
        base_inc = float(np.interp(u, xs, ys))
        # Height / ride-clearance feedback keeps hull cleanly clear without porpoising
        h_ref = float(ecu_cfg.get('target_keel_clear_m', 0.18))
        kh = float(ecu_cfg.get('k_height_deg_per_m', 6.0))
        kp_ski = float(ecu_cfg.get('k_ski_pitch_deg_per_deg', 0.35))
        kd_ski = float(ecu_cfg.get('k_ski_pitch_rate_s', 0.12))
        h_err = h_ref - float(keel_clear_m)
        p_err = target_nose_up - nose_up_deg
        inc_cmd = (
            base_inc
            + u_gate * (kh * h_err + kp_ski * p_err - kd_ski * nose_up_rate + bank_lift_comp_deg)
            + flare_ski_deg
        )
        lim = surface_limits['ski_incidence_deg']
        # Additive pilot trim relative to 0 (pilot can override manually at any time)
        out['ski_incidence_deg'] = float(np.clip(
            pilot_cmd.get('ski_incidence_deg', 0.0) + blend * inc_cmd,
            lim['min'], lim['max'],
        ))

    # 2. Aft trim ski pitch stabilizer (if present in profile)
    if 'aft_ski_incidence_deg' in surface_limits:
        aft_sched = ecu_cfg.get('aft_ski_schedule_mps_deg')
        aft_base = float(np.interp(u, [p[0] for p in aft_sched], [p[1] for p in aft_sched])) if aft_sched else 0.0
        # Positive aft ski incidence lifts stern -> pushes nose DOWN (reduces nose_up_deg)
        ka_p = float(ecu_cfg.get('k_aft_pitch_deg_per_deg', 0.6))
        ka_d = float(ecu_cfg.get('k_aft_pitch_rate_s', 0.25))
        aft_cmd = aft_base + u_gate * (ka_p * (nose_up_deg - target_nose_up) + ka_d * nose_up_rate) + flare_aft_deg
        lim = surface_limits['aft_ski_incidence_deg']
        out['aft_ski_incidence_deg'] = float(np.clip(
            pilot_cmd.get('aft_ski_incidence_deg', 0.0) + blend * aft_cmd,
            lim['min'], lim['max'],
        ))

    # 3. Coordinated roll-bank tracking & leveling via differential skis + ailerons
    roll_err = float(roll_deg) - target_roll_deg
    if 'ski_differential_deg' in surface_limits:
        k_phi = float(ecu_cfg.get('k_ski_roll_deg_per_deg', 0.45))
        k_p = float(ecu_cfg.get('k_ski_roll_rate_s', 0.12))
        # roll_err > 0 (banked further right than target) needs -ski_differential_deg (stbd LE up -> roll left)
        diff_cmd = u_gate * (-k_phi * roll_err - k_p * float(roll_rate_deg_s))
        lim = surface_limits['ski_differential_deg']
        out['ski_differential_deg'] = float(np.clip(
            pilot_cmd.get('ski_differential_deg', 0.0) + blend * diff_cmd,
            lim['min'], lim['max'],
        ))

    if 'aileron_deg' in surface_limits:
        ka_phi = float(ecu_cfg.get('k_ail_roll_deg_per_deg', 0.8))
        ka_p = float(ecu_cfg.get('k_ail_roll_rate_s', 0.25))
        ail_cmd = u_gate * (-ka_phi * roll_err - ka_p * float(roll_rate_deg_s))
        lim = surface_limits['aileron_deg']
        out['aileron_deg'] = float(np.clip(
            pilot_cmd.get('aileron_deg', 0.0) + blend * ail_cmd,
            lim['min'], lim['max'],
        ))

    # 4. Pitch attitude & rate damping via T-tail elevator (active across hump + WIG transition + bank/flare compensation)
    if 'elevator_deg' in surface_limits:
        ke_p = float(ecu_cfg.get('k_elev_pitch_deg_per_deg', 1.4))
        ke_d = float(ecu_cfg.get('k_elev_pitch_rate_s', 0.45))
        elev_bias = float(ecu_cfg.get('elev_hump_bias_deg', 0.0)) * _smoothstep((u - 2.0) / 3.0) * (1.0 - _smoothstep((u - 16.0) / 8.0))
        # nose_up_deg < target -> positive elevator_deg (TE up -> nose up)
        elev_cmd = (
            elev_bias
            + u_gate * (ke_p * (target_nose_up - nose_up_deg) - ke_d * nose_up_rate + bank_lift_comp_deg)
            + flare_elev_deg
        )
        lim = surface_limits['elevator_deg']
        out['elevator_deg'] = float(np.clip(
            pilot_cmd.get('elevator_deg', 0.0) + blend * elev_cmd,
            lim['min'], lim['max'],
        ))

    # 5. Yaw-rate damping around pilot's commanded turn rate via rudder (responsive turns without spin-out)
    if 'rudder_deg' in surface_limits:
        kr_r = float(ecu_cfg.get('k_rud_yaw_rate_s', 0.55))
        yaw_rate_gain = float(ecu_cfg.get('k_cmd_yaw_rate_per_rud_deg', 0.45))
        target_yaw_rate_deg_s = (
            turn_gate * (yaw_rate_gain * pilot_rud - 5.0 * pilot_diff)
            if (abs(pilot_rud) > 0.5 or abs(pilot_diff) > 0.05)
            else 0.0
        )
        yaw_rate_err = float(yaw_rate_deg_s) - target_yaw_rate_deg_s
        rud_cmd = u_gate * (-kr_r * yaw_rate_err)
        lim = surface_limits['rudder_deg']
        out['rudder_deg'] = float(np.clip(
            pilot_cmd.get('rudder_deg', 0.0) + blend * rud_cmd,
            lim['min'], lim['max'],
        ))

    if telemetry_out is not None:
        telemetry_out.update(
            enabled=True,
            assist=round(blend, 3),
            mode=mode,
            target_roll_deg=round(target_roll_deg, 3),
            target_nose_up_deg=round(target_nose_up, 3),
            effective_command={k: round(float(v), 4) for k, v in out.items()},
        )
    return out
