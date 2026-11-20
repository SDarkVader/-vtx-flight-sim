"""Opt-in real-component profiles for the Ricochet RC-01 plant.

A profile replaces the idealised surface servos with the selected off-the-shelf actuators
(torque and torque-speed limits read from ``docs/ricochet/components/components.json``)
and adds hinged planing skis with fins under the outboard sponson pods. Nothing here is
used unless a ``RicochetCraft`` is built with ``profile=...``; the legacy plant is unchanged.

Ski hydrodynamics (per ski, every 400 Hz step):
  * planing (trailing edge wet, leading edge dry): Savitsky flat-plate lift
    C_L0 = tau^1.1 (0.012 lambda^0.5 + 0.0055 lambda^2.5 / Cv^2), wetted length from the
    geometric waterline crossing, centre of pressure
    l_p / (lambda b) = 0.75 - 1 / (5.21 Cv^2 / lambda^2 + 2.39) from the trailing edge;
    the hydrostatic (second) term is faded in with Cv (transom ventilation) and the
    dynamic term uses the flow angle so heave and pitch rates are damped;
  * fully submerged: low-aspect-ratio plate C_N = (pi AR / 2) sin a + 2 sin a |sin a|
    with a free-surface (image) factor, blended from planing over half a beam of
    leading-edge depth; a dug-in nose produces a diving force on the wetted fore part;
  * fin: Helmbold lift slope, end-plate effect when the root is wet, lift capped
    (ventilation cap when surface-piercing);
  * ITTC-57 friction; plate buoyancy; low-speed normal (heave) drag.
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
}


@lru_cache(maxsize=None)
def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_profile(profile_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a named profile; ``overrides`` (deep-merged) is for calibration sweeps only."""
    if profile_id not in PROFILE_FILES:
        raise ValueError(f'Unknown Ricochet profile {profile_id!r}; no substitution allowed')
    prof = copy.deepcopy(_load_json(str(PROFILE_DIR / PROFILE_FILES[profile_id])))
    if prof.get('profile_id') != profile_id:
        raise ValueError(f'Profile file does not declare {profile_id!r}')
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
    fin = ski['fin']
    ex, ey, ez = rot_w[:, 0], rot_w[:, 1], rot_w[:, 2]

    def to_w(p_local: tuple[float, float, float]) -> np.ndarray:
        return origin_w + rot_w @ np.asarray(p_local, dtype=np.float64)

    def vel_at(p_w: np.ndarray, w_vel: np.ndarray) -> np.ndarray:
        return v_origin_w + np.cross(omega_w, p_w - origin_w) - w_vel

    te = to_w((-a, 0.0, -zb))
    le = to_w((L - a, 0.0, -zb))
    fr = to_w((float(fin['x_from_pivot_m']), 0.0, -zb))
    ft = to_w((float(fin['x_from_pivot_m']), 0.0, -zb - float(fin['span_m'])))
    pts = np.stack([te, le, fr])
    eta, wvel = sample(pts[:, 0], pts[:, 1], pts[:, 2])
    d_te = float(eta[0] - te[2])
    d_le = float(eta[1] - le[2])
    forces: list[tuple[np.ndarray, np.ndarray]] = []
    tel: dict[str, Any] = {'d_te_m': round(d_te, 4), 'd_le_m': round(d_le, 4)}
    tau_g = math.asin(float(np.clip(ex[2], -1.0, 1.0)))  # leading edge up > 0
    tel['trim_geom_deg'] = round(math.degrees(tau_g), 3)

    # ---------------- planing surface ----------------
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
        pc = te + ex * (0.5 * (s0 + s1))
        v_rel = vel_at(pc, wvel[0] if regime != 'nose_dug' else wvel[1])
        u = float(v_rel @ ex)
        wn = float(v_rel @ ez)
        u_pos = max(u, 0.0)
        alpha = math.atan2(-wn, max(u_pos, 0.3))
        cv = u_pos / math.sqrt(g * b)
        cos_t = max(math.cos(tau_g), 0.2)

        def planing(lam_len: float) -> tuple[float, float, float]:
            lam = max(lam_len / b, 0.05)
            tf = min(max(math.degrees(alpha), 0.0), 20.0)
            tg = min(max(math.degrees(tau_g), 0.0), 20.0)
            l_dyn = 0.5 * rho * u_pos * u_pos * b * b * (tf ** 1.1) * 0.012 * math.sqrt(lam)
            vent = min(1.0, max(0.0, (cv - 0.5) / 1.0))  # transom clears from Cv ~0.5 to 1.5
            l_hs = vent * 0.5 * rho * g * b ** 3 * (tg ** 1.1) * 0.0055 * lam ** 2.5
            n = (l_dyn + l_hs) / cos_t
            cvv = max(cv, 1e-3)
            frac = 0.75 - 1.0 / (5.21 * cvv * cvv / (lam * lam) + 2.39)
            lp = min(max(frac, 0.1), 0.9) * lam_len
            cf = _ittc_cf(u_pos, lam_len, nu)
            df = 0.5 * rho * u_pos * u_pos * cf * b * lam_len / cos_t
            return n, lp, df

        def submerged(len_w: float, depth_mid: float) -> tuple[float, float, float]:
            ar = b / max(len_w, 1e-3)
            v2 = u_pos * u_pos + wn * wn
            sa = math.sin(alpha)
            cn = 0.5 * math.pi * ar * sa + 2.0 * sa * abs(sa)
            hc = max(depth_mid, 0.0) / max(len_w, 1e-3)
            k_fs = (1.0 + 16.0 * hc * hc) / (2.0 + 16.0 * hc * hc)
            n = 0.5 * rho * v2 * b * len_w * cn * k_fs
            cf = _ittc_cf(u_pos, len_w, nu)
            df = 0.5 * rho * u_pos * u_pos * cf * 2.0 * b * len_w
            return n, 0.70 * len_w, df  # CP 0.30 of wetted length aft of its leading edge

        if regime == 'planing':
            n, lp, df = planing(lw)
            p_n = te + ex * lp
        elif regime == 'nose_dug':
            n, lp, df = submerged(lw, 0.5 * d_le)
            p_n = te + ex * (s0 + lp)
        else:
            f_blend = min(1.0, max(0.0, d_le / (0.5 * b)))
            n1, lp1, df1 = planing(L)
            n2, lp2, df2 = submerged(L, 0.5 * (d_te + d_le))
            n = (1.0 - f_blend) * n1 + f_blend * n2
            lp = (1.0 - f_blend) * lp1 + f_blend * lp2
            df = (1.0 - f_blend) * df1 + f_blend * df2
            p_n = te + ex * lp
        # low-speed normal (heave) drag, faded out as forward flow takes over; the submerged plate's
        # cross-flow term already carries it, so only the surface-running share gets this term
        w_lo = min(1.0, max(0.0, 1.0 - u_pos / 3.0))
        f_sub = 1.0 if regime == 'nose_dug' else (min(1.0, max(0.0, d_le / (0.5 * b))) if regime == 'submerged' else 0.0)
        n += w_lo * (1.0 - f_sub) * (-0.5 * rho * 1.2 * b * lw * wn * abs(wn))
        forces.append((p_n, ez * n))
        forces.append((pc, -ex * df * (1.0 if u >= 0.0 else -1.0)))
        # plate buoyancy (submerged part of the plate's own volume)
        fb = rho * g * b * t_pl * lw
        forces.append((pc, np.array([0.0, 0.0, fb])))
        n_total = n
        tel.update(u_mps=round(u, 3), alpha_flow_deg=round(math.degrees(alpha), 3), cv=round(cv, 3),
                   lambda_=round(lw / b, 3), normal_n=round(n, 1), friction_n=round(df, 1), buoyancy_n=round(fb, 1),
                   cp_from_te_m=round(float((p_n - te) @ ex), 4))

    # ---------------- fin ----------------
    span = float(fin['span_m'])
    chord = float(fin['chord_m'])
    h_imm = min(max(float(eta[2] - ft[2]), 0.0), span)
    fin_y = 0.0
    if h_imm > 0.01:
        root_wet = float(eta[2]) > float(fr[2])
        ar = (2.0 if root_wet else 1.0) * h_imm / chord
        cla = 2.0 * math.pi * ar / (2.0 + math.sqrt(ar * ar + 4.0))
        p_f = ft + (fr - ft) * (0.5 * h_imm / span)
        v_rel = vel_at(p_f, wvel[2])
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
        tel.update(fin_immersed_m=round(h_imm, 4), fin_beta_deg=round(math.degrees(beta), 3), fin_side_n=round(fin_y, 1),
                   fin_drag_n=round(fin_d, 1), fin_root_wet=bool(root_wet), fin_cl=round(cl, 4))
    else:
        tel.update(fin_immersed_m=0.0, fin_side_n=0.0)

    # Added (entrained-water) inertia about the hinge for rotation of the plate: strip theory with the 2-D
    # flat-plate added mass rho*pi*(b/2)^2 per metre, halved at the free surface, full once a beam deep.
    if lw > 1e-3:
        x0, x1 = s0 - a, s1 - a
        depth = max(0.0, 0.5 * (max(d_te, 0.0) + max(d_le, 0.0)))
        k_fs_am = 0.5 + 0.5 * min(1.0, depth / b) if regime == 'submerged' else 0.5
        tel['added_inertia_kg_m2'] = k_fs_am * rho * math.pi * 0.25 * b * b * (x1 ** 3 - x0 ** 3) / 3.0
    else:
        tel['added_inertia_kg_m2'] = 0.0

    # hinge moment about the incidence axis (joint axis = -y body): + raises the leading edge
    hm = 0.0
    for p, f in forces:
        hm += float(np.cross(p - origin_w, f) @ (-ey))
    tel['hinge_moment_nm'] = round(hm, 2)
    tel['normal_force_n'] = round(n_total, 1)
    return forces, tel
