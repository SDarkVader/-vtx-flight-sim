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

    def shelter_factor(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Wave sheltering inside Ricochet Lake marina harbour west of breakwater."""
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
    ) -> WaveSample:
        """Evaluate surface elevation, normal, orbital kinematics, and dynamic pressure.

        Works on arbitrary array shapes `(...)` or scalars.
        """
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        xa, ya = np.broadcast_arrays(xa, ya)
        shape = xa.shape

        wl = float(self.config.water_level_m if water_level_offset is None else water_level_offset)
        if z is None:
            za = np.full(shape, wl, dtype=np.float64)
        else:
            za = np.broadcast_to(np.asarray(z, dtype=np.float64), shape)

        if local_depth is None:
            depth = np.full(shape, self.reference_depth_m, dtype=np.float64)
        else:
            depth = np.broadcast_to(np.asarray(local_depth, dtype=np.float64), shape)

        eta = np.full(shape, wl, dtype=np.float64)
        vel = np.zeros(shape + (3,), dtype=np.float64)
        vel[..., 0] = self.current_xy[0]
        vel[..., 1] = self.current_xy[1]
        acc = np.zeros(shape + (3,), dtype=np.float64)
        norm = np.zeros(shape + (3,), dtype=np.float64)
        norm[..., 2] = 1.0
        p_dyn = np.zeros(shape, dtype=np.float64)

        if self.amp.size == 0:
            return WaveSample(eta=eta, normal=norm, velocity=vel, acceleration=acc, dynamic_pressure=p_dyn)

        # Smooth depth-limited wave breaking / attenuation factor (Miche-style cap eta_rms <= 0.4 * depth)
        shelter = self.shelter_factor(xa, ya)
        depth_atten = np.clip(depth / 1.2, 0.0, 1.0)
        atten = shelter * depth_atten

        flat_x = xa.ravel()
        flat_y = ya.ravel()
        flat_z = za.ravel()
        flat_depth = np.maximum(depth.ravel(), 0.2)
        flat_atten = atten.ravel()

        # Theta_c,i = kx*x + ky*y - omega*t + phase
        theta = (
            flat_x[:, None] * self.kx[None, :]
            + flat_y[:, None] * self.ky[None, :]
            - float(t) * self.omega[None, :]
            + self.phase[None, :]
        )
        cos_th = np.cos(theta)
        sin_th = np.sin(theta)

        a_eff = flat_atten[:, None] * self.amp[None, :]
        d_eta = np.sum(a_eff * cos_th, axis=1)
        d_eta_dx = np.sum(-a_eff * self.kx[None, :] * sin_th, axis=1)
        d_eta_dy = np.sum(-a_eff * self.ky[None, :] * sin_th, axis=1)

        eta_flat = wl + d_eta
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
        kh = np.minimum(self.k[None, :] * flat_depth[:, None], 35.0)
        k_zh = np.clip(self.k[None, :] * (z_col[:, None] + flat_depth[:, None]), 0.0, 35.0)

        sinh_kh = np.maximum(np.sinh(kh), 1e-6)
        cosh_kzh = np.cosh(k_zh)
        sinh_kzh = np.sinh(k_zh)

        # Airy kinematics:
        #   u_h = (a * omega * cosh(k(z+h))/sinh(kh)) * cos(theta)
        #   w   = (a * omega * sinh(k(z+h))/sinh(kh)) * sin(theta)
        #   p_dyn = rho * g * a * (cosh(k(z+h))/cosh(kh)) * cos(theta)
        v_h_mag = a_eff * self.omega[None, :] * (cosh_kzh / sinh_kh) * cos_th
        v_z_comp = a_eff * self.omega[None, :] * (sinh_kzh / sinh_kh) * sin_th

        a_h_mag = a_eff * (self.omega[None, :] ** 2) * (cosh_kzh / sinh_kh) * sin_th
        a_z_comp = -a_eff * (self.omega[None, :] ** 2) * (sinh_kzh / sinh_kh) * cos_th

        cosh_kh = np.maximum(np.cosh(kh), 1.0)
        p_dyn_flat = (
            float(self.config.rho_water_kg_m3)
            * float(self.config.g_m_s2)
            * np.sum(a_eff * (cosh_kzh / cosh_kh) * cos_th, axis=1)
        )

        vx_flat = self.current_xy[0] + np.sum(v_h_mag * self.dir_x[None, :], axis=1)
        vy_flat = self.current_xy[1] + np.sum(v_h_mag * self.dir_y[None, :], axis=1)
        vz_flat = np.sum(v_z_comp, axis=1)

        ax_flat = np.sum(a_h_mag * self.dir_x[None, :], axis=1)
        ay_flat = np.sum(a_h_mag * self.dir_y[None, :], axis=1)
        az_flat = np.sum(a_z_comp, axis=1)

        # Above water surface zero out wave dynamic pressure & exponentially decay air orbital blend smoothly
        sub_fade = np.clip((eta_flat - flat_z + 0.04) / 0.08, 0.0, 1.0)
        p_dyn_flat *= sub_fade

        eta = eta_flat.reshape(shape)
        vel[..., 0] = vx_flat.reshape(shape)
        vel[..., 1] = vy_flat.reshape(shape)
        vel[..., 2] = vz_flat.reshape(shape)
        acc[..., 0] = ax_flat.reshape(shape)
        acc[..., 1] = ay_flat.reshape(shape)
        acc[..., 2] = az_flat.reshape(shape)

        n_raw = np.stack([-d_eta_dx, -d_eta_dy, np.ones_like(d_eta_dx)], axis=-1)
        n_mag = np.linalg.norm(n_raw, axis=-1, keepdims=True)
        norm = (n_raw / np.maximum(n_mag, 1e-12)).reshape(shape + (3,))
        p_dyn = p_dyn_flat.reshape(shape)

        return WaveSample(eta=eta, normal=norm, velocity=vel, acceleration=acc, dynamic_pressure=p_dyn)
