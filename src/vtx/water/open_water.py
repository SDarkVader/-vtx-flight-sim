"""Deterministic directional open-water wave field (still, regular, JONSWAP irregular).

Computes analytical surface elevation eta(x, y, t), unit surface normal,
water-particle orbital velocity & acceleration, and linear unsteady dynamic
pressure at arbitrary 3D coordinates (x, y, z), supporting vectorized NumPy
arrays for triangle-mesh panel integration as well as scalar queries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from vtx.water.datum import G_SI, RHO_FRESHWATER_15C, WaterEnvironmentConfig


def solve_dispersion_wavenumber(omega: float, depth: float, g: float = G_SI) -> float:
    """Solve linear finite-depth dispersion relation omega^2 = g * k * tanh(k * h)."""
    if omega <= 0.0:
        return 0.0
    h = max(float(depth), 0.15)
    k = (omega * omega) / g
    # Initial shallow/intermediate guess (Eckart approximation)
    alpha = (omega * omega * h) / g
    k = (alpha + alpha * alpha * 0.666667 / (1.0 + 0.666667 * alpha)) / h
    k = max(k, omega / math.sqrt(g * h))
    for _ in range(10):
        kh = min(k * h, 40.0)
        th = math.tanh(kh)
        sech2 = 1.0 - th * th
        f = g * k * th - omega * omega
        df = g * (th + kh * sech2)
        if abs(df) < 1e-12:
            break
        dk = f / df
        k = max(1e-6, k - dk)
        if abs(dk) < 1e-10 * max(1.0, k):
            break
    return float(k)


def _jonswap_spectrum(omega: np.ndarray, hs: float, tp: float, gamma: float = 3.3) -> np.ndarray:
    """One-sided JONSWAP wave energy density S(omega) in m^2 / (rad/s)."""
    if hs <= 0.0 or tp <= 0.0:
        return np.zeros_like(omega)
    wp = 2.0 * math.pi / tp
    sigma = np.where(omega <= wp, 0.07, 0.09)
    r = np.exp(-0.5 * ((omega - wp) / (sigma * wp)) ** 2)
    alpha_pm = (5.0 / 16.0) * (hs ** 2) * (wp ** 4)
    # JONSWAP normalization factor (approx 1 - 0.287*ln(gamma))
    c_norm = 1.0 - 0.287 * math.log(max(gamma, 1.0))
    pm = alpha_pm / np.maximum(omega, 1e-6) ** 5 * np.exp(-1.25 * (wp / np.maximum(omega, 1e-6)) ** 4)
    return c_norm * pm * (gamma ** r)


@dataclass
class WaveSample:
    """Evaluated open-water wave kinematics at query coordinates."""

    eta: np.ndarray
    normal: np.ndarray  # shape (..., 3)
    velocity: np.ndarray  # shape (..., 3) includes ambient current
    acceleration: np.ndarray  # shape (..., 3)
    dynamic_pressure: np.ndarray  # Pa, unsteady dynamic pressure (-rho * dPhi/dt)


class OpenWaterWaveField:
    """Deterministic multi-mode directional linear wave kinematics engine."""

    def __init__(self, config: WaterEnvironmentConfig | None = None, reference_depth_m: float = 11.0):
        self.config = config or WaterEnvironmentConfig()
        self.reference_depth_m = max(float(reference_depth_m), 0.5)
        self._build_components()

    def reconfigure(self, config: WaterEnvironmentConfig, reference_depth_m: float | None = None) -> None:
        self.config = config
        if reference_depth_m is not None:
            self.reference_depth_m = max(float(reference_depth_m), 0.5)
        self._build_components()

    def _build_components(self) -> None:
        cfg = self.config
        g = float(cfg.g_m_s2)
        theta_mean = math.radians(float(cfg.wave_direction_deg))

        curr_ang = math.radians(float(cfg.current_direction_deg))
        self.current_xy = np.array(
            [
                float(cfg.current_speed_mps) * math.cos(curr_ang),
                float(cfg.current_speed_mps) * math.sin(curr_ang),
            ],
            dtype=np.float64,
        )

        mode = str(cfg.wave_mode).lower()
        hs = max(0.0, float(cfg.wave_height_m))
        tp = max(0.5, float(cfg.wave_period_s))

        if mode == 'still' or hs <= 1e-6:
            self.amp = np.zeros(0, dtype=np.float64)
            self.omega = np.zeros(0, dtype=np.float64)
            self.k = np.zeros(0, dtype=np.float64)
            self.kx = np.zeros(0, dtype=np.float64)
            self.ky = np.zeros(0, dtype=np.float64)
            self.dir_x = np.zeros(0, dtype=np.float64)
            self.dir_y = np.zeros(0, dtype=np.float64)
            self.phase = np.zeros(0, dtype=np.float64)
            self._cache_spectral_products()
            return

        if mode == 'regular':
            omega = 2.0 * math.pi / tp
            k = solve_dispersion_wavenumber(omega, self.reference_depth_m, g)
            self.amp = np.array([0.5 * hs], dtype=np.float64)
            self.omega = np.array([omega], dtype=np.float64)
            self.k = np.array([k], dtype=np.float64)
            self.dir_x = np.array([math.cos(theta_mean)], dtype=np.float64)
            self.dir_y = np.array([math.sin(theta_mean)], dtype=np.float64)
            self.kx = self.k * self.dir_x
            self.ky = self.k * self.dir_y
            self.phase = np.array([float(cfg.wave_phase_rad)], dtype=np.float64)
            self._cache_spectral_products()
            return

        # Seeded directional JONSWAP spectrum with cosine-squared spreading
        n_comp = max(6, int(cfg.wave_components))
        rng = np.random.default_rng(int(cfg.wave_seed))
        wp = 2.0 * math.pi / tp
        w_min = 0.52 * wp
        w_max = 2.65 * wp
        edges = np.linspace(w_min, w_max, n_comp + 1, dtype=np.float64)
        # Non-uniform jittered center inside each bin to avoid exact beat repetition
        dw = np.diff(edges)
        omega = edges[:-1] + dw * rng.uniform(0.2, 0.8, size=n_comp)
        s_w = _jonswap_spectrum(omega, hs, tp, gamma=3.3)
        raw_amp = np.sqrt(2.0 * np.maximum(s_w, 0.0) * dw)
        # Rescale discrete realization energy to match target Hs = 4 * sqrt(m0) cleanly
        m0 = 0.5 * float(np.sum(raw_amp * raw_amp))
        if m0 > 1e-12:
            target_m0 = (hs / 4.0) ** 2
            raw_amp = raw_amp * math.sqrt(target_m0 / m0)

        # Deterministic directional spreading around theta_mean (+/- 35 deg typical fetch)
        dtheta = rng.normal(0.0, math.radians(18.0), size=n_comp)
        dtheta = np.clip(dtheta, -math.radians(55.0), math.radians(55.0))
        theta = theta_mean + dtheta

        self.amp = raw_amp
        self.omega = omega
        self.k = np.array(
            [solve_dispersion_wavenumber(float(w), self.reference_depth_m, g) for w in omega],
            dtype=np.float64,
        )
        self.dir_x = np.cos(theta)
        self.dir_y = np.sin(theta)
        self.kx = self.k * self.dir_x
        self.ky = self.k * self.dir_y
        self.phase = rng.uniform(0.0, 2.0 * math.pi, size=n_comp) + float(cfg.wave_phase_rad)
        self._cache_spectral_products()

    def _cache_spectral_products(self) -> None:
        self._amp_kx = self.amp * self.kx
        self._amp_ky = self.amp * self.ky
        self._amp_omega = self.amp * self.omega
        self._amp_omega_dx = self._amp_omega * self.dir_x
        self._amp_omega_dy = self._amp_omega * self.dir_y
        self._amp_omega2 = self.amp * (self.omega * self.omega)
        self._amp_omega2_dx = self._amp_omega2 * self.dir_x
        self._amp_omega2_dy = self._amp_omega2 * self.dir_y
        if self.amp.size > 0:
            self._k_xy_t = np.ascontiguousarray(np.vstack([self.kx, self.ky]))
            self._neg_amp_kxy = np.ascontiguousarray(np.column_stack([-self._amp_kx, -self._amp_ky]))
        else:
            self._k_xy_t = np.zeros((2, 0), dtype=np.float64)
            self._neg_amp_kxy = np.zeros((0, 2), dtype=np.float64)

    def shelter_factor(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | float:
        """Wave sheltering inside Ricochet Lake marina harbour west of breakwater."""
        if (
            x.size == 0
            or float(np.min(x)) >= -500.0
            or float(np.max(x)) <= -890.0
            or float(np.min(y)) >= -120.0
            or float(np.max(y)) <= -370.0
        ):
            return 1.0
        # Harbour sits roughly in x in [-870, -508], y in [-365, -135]
        in_x = 1.0 - np.clip((x - (-535.0)) / 35.0, 0.0, 1.0)
        in_x = in_x * np.clip((x - (-890.0)) / 30.0, 0.0, 1.0)
        in_y = np.clip((y - (-370.0)) / 25.0, 0.0, 1.0) * (1.0 - np.clip((y - (-155.0)) / 35.0, 0.0, 1.0))
        # Breakwater transmits ~15% diffracted residual swell inside sheltered berths
        return 1.0 - 0.85 * (in_x * in_y)

    def evaluate(
        self,
        x: np.ndarray | float,
        y: np.ndarray | float,
        z: np.ndarray | float | None = None,
        t: float = 0.0,
        local_depth: np.ndarray | float | None = None,
        water_level_offset: float | None = None,
        eta_only: bool = False,
    ) -> WaveSample:
        """Evaluate surface elevation, normal, orbital kinematics, and dynamic pressure.

        Works on arbitrary array shapes `(...)` or scalars. When `eta_only=True`, only
        free-surface elevation `eta` is populated to avoid vertex orbital tensor overhead.
        """
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        xa, ya = np.broadcast_arrays(xa, ya)
        shape = xa.shape

        wl = float(self.config.water_level_m if water_level_offset is None else water_level_offset)
        if self.amp.size == 0:
            eta = np.full(shape, wl, dtype=np.float64)
            if eta_only:
                empty = np.empty(0, dtype=np.float64)
                return WaveSample(eta=eta, normal=empty, velocity=empty, acceleration=empty, dynamic_pressure=empty)
            vel = np.zeros(shape + (3,), dtype=np.float64)
            vel[..., 0] = self.current_xy[0]
            vel[..., 1] = self.current_xy[1]
            acc = np.zeros(shape + (3,), dtype=np.float64)
            norm = np.zeros(shape + (3,), dtype=np.float64)
            norm[..., 2] = 1.0
            p_dyn = np.zeros(shape, dtype=np.float64)
            return WaveSample(eta=eta, normal=norm, velocity=vel, acceleration=acc, dynamic_pressure=p_dyn)

        if local_depth is None:
            depth = np.full(shape, self.reference_depth_m, dtype=np.float64)
        else:
            depth = np.broadcast_to(np.asarray(local_depth, dtype=np.float64), shape)

        # Smooth depth-limited wave breaking / attenuation factor (Miche-style cap eta_rms <= 0.4 * depth)
        shelter = self.shelter_factor(xa, ya)
        flat_x = xa.ravel()
        flat_y = ya.ravel()
        flat_depth = np.maximum(depth.ravel(), 0.2)
        uniform_atten = isinstance(shelter, float) and shelter == 1.0 and float(np.min(flat_depth)) >= 1.2
        if not uniform_atten:
            flat_atten = np.asarray(shelter, dtype=np.float64).ravel() * np.clip(flat_depth / 1.2, 0.0, 1.0)

        # Theta_c,i = kx*x + ky*y - omega*t + phase
        t_phase = self.phase - float(t) * self.omega
        if self.amp.size == 1:
            a0 = float(self.amp[0])
            kx0 = float(self.kx[0])
            ky0 = float(self.ky[0])
            k0 = float(self.k[0])
            om0 = float(self.omega[0])
            dx0 = float(self.dir_x[0])
            dy0 = float(self.dir_y[0])
            theta = flat_x * kx0 + flat_y * ky0 + float(t_phase[0])
            cos_th = np.cos(theta)
            d_eta = (a0 * cos_th) if uniform_atten else (a0 * flat_atten * cos_th)
            eta_flat = wl + d_eta
            if eta_only:
                empty = np.empty(0, dtype=np.float64)
                return WaveSample(
                    eta=eta_flat.reshape(shape),
                    normal=empty,
                    velocity=empty,
                    acceleration=empty,
                    dynamic_pressure=empty,
                )
            flat_z = np.full(flat_x.shape, wl, dtype=np.float64) if z is None else np.broadcast_to(np.asarray(z, dtype=np.float64), shape).ravel()
            sin_th = np.sin(theta)
            a_eff = a0 if uniform_atten else a0 * flat_atten
            d_eta_dx = -(a_eff * kx0) * sin_th
            d_eta_dy = -(a_eff * ky0) * sin_th
            z_rel = flat_z - wl
            z_stretched = np.where(
                d_eta > -flat_depth + 0.05,
                (z_rel - d_eta) * flat_depth / np.maximum(flat_depth + d_eta, 0.15),
                z_rel,
            )
            z_col = np.clip(z_stretched, -flat_depth, 0.0)
            k_zh = np.clip((z_col + flat_depth) * k0, 0.0, 35.0)
            exp_kzh = np.exp(k_zh)
            inv_exp_kzh = 1.0 / exp_kzh
            cosh_kzh = 0.5 * (exp_kzh + inv_exp_kzh)
            sinh_kzh = 0.5 * (exp_kzh - inv_exp_kzh)
            kh = np.minimum(flat_depth * k0, 35.0)
            exp_kh = np.exp(kh)
            inv_exp_kh = 1.0 / exp_kh
            sinh_kh = np.maximum(0.5 * (exp_kh - inv_exp_kh), 1e-6)
            cosh_kh = np.maximum(0.5 * (exp_kh + inv_exp_kh), 1.0)
            rho_g = float(self.config.rho_water_kg_m3) * float(self.config.g_m_s2)
            inv_sinh_kh = 1.0 / sinh_kh
            c_over_s = cosh_kzh * inv_sinh_kh
            s_over_s = sinh_kzh * inv_sinh_kh
            vh = a_eff * om0 * c_over_s * cos_th
            vz_flat = a_eff * om0 * s_over_s * sin_th
            ah = a_eff * (om0 * om0) * c_over_s * sin_th
            az_flat = -a_eff * (om0 * om0) * s_over_s * cos_th
            p_dyn_flat = rho_g * a_eff * (cosh_kzh / cosh_kh) * cos_th
            vx_flat = self.current_xy[0] + vh * dx0
            vy_flat = self.current_xy[1] + vh * dy0
            ax_flat = ah * dx0
            ay_flat = ah * dy0
            sub_fade = np.clip((eta_flat - flat_z + 0.04) / 0.08, 0.0, 1.0)
            p_dyn_flat *= sub_fade
            eta = eta_flat.reshape(shape)
            vel = np.empty(shape + (3,), dtype=np.float64)
            vel[..., 0] = vx_flat.reshape(shape)
            vel[..., 1] = vy_flat.reshape(shape)
            vel[..., 2] = vz_flat.reshape(shape)
            acc = np.empty(shape + (3,), dtype=np.float64)
            acc[..., 0] = ax_flat.reshape(shape)
            acc[..., 1] = ay_flat.reshape(shape)
            acc[..., 2] = az_flat.reshape(shape)
            inv_n = 1.0 / np.sqrt(d_eta_dx * d_eta_dx + d_eta_dy * d_eta_dy + 1.0)
            norm = np.column_stack([-d_eta_dx * inv_n, -d_eta_dy * inv_n, inv_n]).reshape(shape + (3,))
            return WaveSample(eta=eta, normal=norm, velocity=vel, acceleration=acc, dynamic_pressure=p_dyn_flat.reshape(shape))

        xy = np.column_stack([flat_x, flat_y])
        theta = xy @ self._k_xy_t + t_phase[None, :]
        cos_th = np.cos(theta)
        d_eta = (cos_th @ self.amp) if uniform_atten else flat_atten * (cos_th @ self.amp)
        eta_flat = wl + d_eta
        if eta_only:
            empty = np.empty(0, dtype=np.float64)
            return WaveSample(
                eta=eta_flat.reshape(shape),
                normal=empty,
                velocity=empty,
                acceleration=empty,
                dynamic_pressure=empty,
            )

        if z is None:
            flat_z = np.full(flat_x.shape, wl, dtype=np.float64)
        else:
            flat_z = np.broadcast_to(np.asarray(z, dtype=np.float64), shape).ravel()

        sin_th = np.sin(theta)
        grad = sin_th @ self._neg_amp_kxy
        d_eta_dx = grad[:, 0] if uniform_atten else flat_atten * grad[:, 0]
        d_eta_dy = grad[:, 1] if uniform_atten else flat_atten * grad[:, 1]

        # Wheeler stretching: map z relative to instantaneous free surface [wl - h, eta_flat] -> [wl - h, wl]
        # keeping cosh/sinh bounded and continuous across zero/crest
        z_rel = flat_z - wl
        z_stretched = np.where(
            d_eta > -flat_depth + 0.05,
            (z_rel - d_eta) * flat_depth / np.maximum(flat_depth + d_eta, 0.15),
            z_rel,
        )
        # Clamp within water column [ -flat_depth, 0 ] for linear Airy orbital profiles
        z_col = np.clip(z_stretched, -flat_depth, 0.0)
        k_zh = np.clip(np.outer(z_col + flat_depth, self.k), 0.0, 35.0)
        exp_kzh = np.exp(k_zh)
        inv_exp_kzh = 1.0 / exp_kzh
        cosh_kzh = 0.5 * (exp_kzh + inv_exp_kzh)
        sinh_kzh = 0.5 * (exp_kzh - inv_exp_kzh)

        rho_g = float(self.config.rho_water_kg_m3) * float(self.config.g_m_s2)
        if flat_depth.size > 0 and float(np.max(flat_depth) - np.min(flat_depth)) <= 1e-7:
            kh_1d = np.minimum(self.k * float(flat_depth[0]), 35.0)
            inv_sinh = 1.0 / np.maximum(np.sinh(kh_1d), 1e-6)
            inv_cosh = 1.0 / np.maximum(np.cosh(kh_1d), 1.0)
            w_cc = np.column_stack([
                self._amp_omega_dx * inv_sinh,
                self._amp_omega_dy * inv_sinh,
                self.amp * (rho_g * inv_cosh),
            ])
            w_cs = np.column_stack([
                self._amp_omega2_dx * inv_sinh,
                self._amp_omega2_dy * inv_sinh,
            ])
            vxy_p = (cosh_kzh * cos_th) @ w_cc
            axy = (cosh_kzh * sin_th) @ w_cs
            vz_flat = (sinh_kzh * sin_th) @ (self._amp_omega * inv_sinh)
            az_flat = (sinh_kzh * cos_th) @ (-self._amp_omega2 * inv_sinh)
            if not uniform_atten:
                vxy_p *= flat_atten[:, None]
                axy *= flat_atten[:, None]
                vz_flat *= flat_atten
                az_flat *= flat_atten
            vx_flat = self.current_xy[0] + vxy_p[:, 0]
            vy_flat = self.current_xy[1] + vxy_p[:, 1]
            p_dyn_flat = vxy_p[:, 2]
            ax_flat = axy[:, 0]
            ay_flat = axy[:, 1]
        else:
            kh = np.minimum(self.k[None, :] * flat_depth[:, None], 35.0)
            exp_kh = np.exp(kh)
            inv_exp_kh = 1.0 / exp_kh
            sinh_kh = np.maximum(0.5 * (exp_kh - inv_exp_kh), 1e-6)
            cosh_kh = np.maximum(0.5 * (exp_kh + inv_exp_kh), 1.0)
            inv_sinh_kh = 1.0 / sinh_kh
            c_over_s = cosh_kzh * inv_sinh_kh
            s_over_s = sinh_kzh * inv_sinh_kh
            c_cos = c_over_s * cos_th
            s_sin = s_over_s * sin_th
            c_sin = c_over_s * sin_th
            s_cos = s_over_s * cos_th
            atten_col = 1.0 if uniform_atten else flat_atten
            p_dyn_flat = rho_g * atten_col * (((cosh_kzh / cosh_kh) * cos_th) @ self.amp)
            vx_flat = self.current_xy[0] + atten_col * (c_cos @ self._amp_omega_dx)
            vy_flat = self.current_xy[1] + atten_col * (c_cos @ self._amp_omega_dy)
            vz_flat = atten_col * (s_sin @ self._amp_omega)
            ax_flat = atten_col * (c_sin @ self._amp_omega2_dx)
            ay_flat = atten_col * (c_sin @ self._amp_omega2_dy)
            az_flat = -atten_col * (s_cos @ self._amp_omega2)

        # Above water surface zero out wave dynamic pressure & exponentially decay air orbital blend smoothly
        sub_fade = np.clip((eta_flat - flat_z + 0.04) / 0.08, 0.0, 1.0)
        p_dyn_flat *= sub_fade

        eta = eta_flat.reshape(shape)
        vel = np.empty(shape + (3,), dtype=np.float64)
        vel[..., 0] = vx_flat.reshape(shape)
        vel[..., 1] = vy_flat.reshape(shape)
        vel[..., 2] = vz_flat.reshape(shape)
        acc = np.empty(shape + (3,), dtype=np.float64)
        acc[..., 0] = ax_flat.reshape(shape)
        acc[..., 1] = ay_flat.reshape(shape)
        acc[..., 2] = az_flat.reshape(shape)

        inv_n = 1.0 / np.sqrt(d_eta_dx * d_eta_dx + d_eta_dy * d_eta_dy + 1.0)
        norm = np.column_stack([-d_eta_dx * inv_n, -d_eta_dy * inv_n, inv_n]).reshape(shape + (3,))
        p_dyn = p_dyn_flat.reshape(shape)

        return WaveSample(eta=eta, normal=norm, velocity=vel, acceleration=acc, dynamic_pressure=p_dyn)
