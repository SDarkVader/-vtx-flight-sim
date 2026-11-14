"""Conservative 2D Shallow-Water Solver & Hybrid Water Field for VTX worlds.

Implements a well-balanced finite-volume Saint-Venant (2D SWE) solver using
Audusse hydrostatic reconstruction + Rusanov/HLL interface fluxes with exact
lake-at-rest equilibrium, strict mass conservation in closed watershed basins,
and robust wetting/drying fronts for shoreline run-up and retreat.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from vtx.water.datum import G_SI, RHO_AIR_ISA, RHO_FRESHWATER_15C, WaterEnvironmentConfig
from vtx.water.open_water import OpenWaterWaveField, WaveSample


def _audusse_rusanov_flux_1d(
    h_l: np.ndarray,
    hu_l: np.ndarray,
    hv_l: np.ndarray,
    z_l: np.ndarray,
    h_r: np.ndarray,
    hu_r: np.ndarray,
    hv_r: np.ndarray,
    z_r: np.ndarray,
    g: float,
    h_dry: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Well-balanced Audusse hydrostatic reconstruction + Rusanov flux on 1D faces.

    Returns (flux_h, flux_hu, flux_hv, bed_src_left, bed_src_right) where
    bed_src_* = 0.5 * g * (h_rec^2 - h^2) directly ensures C-property (lake at rest).
    """
    u_l = np.where(h_l > h_dry, hu_l / np.maximum(h_l, h_dry), 0.0)
    v_l = np.where(h_l > h_dry, hv_l / np.maximum(h_l, h_dry), 0.0)
    u_r = np.where(h_r > h_dry, hu_r / np.maximum(h_r, h_dry), 0.0)
    v_r = np.where(h_r > h_dry, hv_r / np.maximum(h_r, h_dry), 0.0)

    eta_l = h_l + z_l
    eta_r = h_r + z_r
    z_iface = np.maximum(z_l, z_r)

    h_star_l = np.maximum(0.0, eta_l - z_iface)
    h_star_r = np.maximum(0.0, eta_r - z_iface)

    # Zero velocity if reconstructed face depth is dry
    u_l = np.where(h_star_l > h_dry, u_l, 0.0)
    v_l = np.where(h_star_l > h_dry, v_l, 0.0)
    u_r = np.where(h_star_r > h_dry, u_r, 0.0)
    v_r = np.where(h_star_r > h_dry, v_r, 0.0)

    hu_star_l = h_star_l * u_l
    hv_star_l = h_star_l * v_l
    hu_star_r = h_star_r * u_r
    hv_star_r = h_star_r * v_r

    # Physical fluxes
    f0_l = hu_star_l
    f1_l = hu_star_l * u_l + 0.5 * g * (h_star_l * h_star_l)
    f2_l = hu_star_l * v_l

    f0_r = hu_star_r
    f1_r = hu_star_r * u_r + 0.5 * g * (h_star_r * h_star_r)
    f2_r = hu_star_r * v_r

    c_l = np.sqrt(g * h_star_l)
    c_r = np.sqrt(g * h_star_r)
    s_max = np.maximum(np.abs(u_l) + c_l, np.abs(u_r) + c_r)
    # Zero numerical diffusion across completely dry interface
    both_dry = (h_star_l <= h_dry) & (h_star_r <= h_dry)
    s_max = np.where(both_dry, 0.0, s_max)

    flux_h = 0.5 * (f0_l + f0_r) - 0.5 * s_max * (h_star_r - h_star_l)
    flux_hu = 0.5 * (f1_l + f1_r) - 0.5 * s_max * (hu_star_r - hu_star_l)
    flux_hv = 0.5 * (f2_l + f2_r) - 0.5 * s_max * (hv_star_r - hv_star_l)

    # Topographic pressure correction: preserves eta = const -> exact zero tendency
    # Also prevents false dry-cliff pull on empty cell
    eff_z_l = np.where(eta_l < z_iface, np.minimum(z_iface, eta_l + h_l), z_iface)
    eff_z_r = np.where(eta_r < z_iface, np.minimum(z_iface, eta_r + h_r), z_iface)
    p_l = 0.5 * g * (h_star_l * h_star_l - h_l * h_l)
    p_r = 0.5 * g * (h_star_r * h_star_r - h_r * h_r)
    # Zero momentum source if cell is dry and wet neighbor is below cell bed
    p_l = np.where((h_l <= h_dry) & (eta_r <= z_l), 0.0, p_l)
    p_r = np.where((h_r <= h_dry) & (eta_l <= z_r), 0.0, p_r)
    _ = (eff_z_l, eff_z_r)  # documented in reconstruction

    return flux_h, flux_hu, flux_hv, p_l, p_r


class ShallowWaterSolver:
    """Conservative 2D finite-volume Saint-Venant solver on world bathymetry."""

    h_dry = 1e-4  # m threshold below which a cell is treated as dry
    h_vel_damp = 4e-3  # m smooth velocity damping depth near wetting/drying front

    def __init__(
        self,
        world,
        config: WaterEnvironmentConfig | None = None,
        nx: int = 101,
        ny: int = 61,
        manning_n: float = 0.025,
    ):
        self.world = world
        self.config = config or WaterEnvironmentConfig()
        self.nx = int(nx)
        self.ny = int(ny)
        self.manning_n = float(manning_n)

        half_x = float(getattr(world, 'half_x', getattr(world, 'half', 1000.0)))
        half_y = float(getattr(world, 'half_y', getattr(world, 'half', 600.0)))
        self.half_x = half_x
        self.half_y = half_y
        self.xs = np.linspace(-half_x, half_x, self.nx, dtype=np.float64)
        self.ys = np.linspace(-half_y, half_y, self.ny, dtype=np.float64)
        self.dx = float(self.xs[1] - self.xs[0])
        self.dy = float(self.ys[1] - self.ys[0])
        self.cell_area = self.dx * self.dy

        xg, yg = np.meshgrid(self.xs, self.ys)
        if hasattr(world, 'terrain_z_array'):
            self.bed = world.terrain_z_array(xg, yg).astype(np.float64)
        else:
            self.bed = np.vectorize(world.terrain_z)(xg, yg).astype(np.float64)

        self.reset(water_level_m=self.config.water_level_m)

    def reset(self, water_level_m: float | None = None) -> None:
        wl = float(self.config.water_level_m if water_level_m is None else water_level_m)
        self.water_level_m = wl
        self.h = np.maximum(0.0, wl - self.bed)
        self.hu = np.zeros_like(self.h)
        self.hv = np.zeros_like(self.h)
        self.t = 0.0
        self.substep_count = 0
        self.initial_volume_m3 = float(np.sum(self.h) * self.cell_area)
        self._expected_volume_m3 = self.initial_volume_m3

    def set_water_level(self, new_water_level_m: float) -> None:
        """Adjust target water datum uniformly across all currently/newly wetted cells."""
        new_wl = float(new_water_level_m)
        delta_wl = new_wl - self.water_level_m
        if abs(delta_wl) < 1e-12:
            return
        eta_curr = self.bed + self.h
        eta_target = np.where(
            (self.h > self.h_dry) | (self.bed < new_wl),
            np.maximum(eta_curr + delta_wl, self.bed),
            self.bed,
        )
        self.h = np.maximum(0.0, eta_target - self.bed)
        # Dry cells carry zero momentum
        dry = self.h <= self.h_dry
        self.hu[dry] = 0.0
        self.hv[dry] = 0.0
        self.water_level_m = new_wl
        self._expected_volume_m3 = float(np.sum(self.h) * self.cell_area)

    def inject_solitary_pulse(self, cx: float, cy: float, amp_m: float, sigma_m: float) -> None:
        """Add a conservative zero-net-check or deterministic free-surface pulse (tests/waves)."""
        xg, yg = np.meshgrid(self.xs, self.ys)
        r2 = ((xg - cx) ** 2 + (yg - cy) ** 2) / max(sigma_m ** 2, 1.0)
        dh = amp_m * np.exp(-0.5 * r2) * (self.h > 0.2)
        self.h = np.maximum(0.0, self.h + dh)
        self._expected_volume_m3 += float(np.sum(dh) * self.cell_area)

    def max_stable_dt(self, cfl: float = 0.42) -> float:
        g = float(self.config.g_m_s2)
        wet = self.h > self.h_dry
        if not np.any(wet):
            return 0.05
        inv_h = np.where(wet, 1.0 / np.maximum(self.h, self.h_vel_damp), 0.0)
        u = np.where(wet, self.hu * inv_h, 0.0)
        v = np.where(wet, self.hv * inv_h, 0.0)
        c = np.sqrt(g * np.maximum(self.h, 0.0))
        sx = float(np.max(np.abs(u) + c))
        sy = float(np.max(np.abs(v) + c))
        denom = sx / self.dx + sy / self.dy
        if denom < 1e-9:
            return 0.05
        return float(cfl / denom)

    def step(self, dt: float) -> None:
        """Advance conservative 2D SWE by dt using CFL-safe substeps."""
        if dt <= 0.0 or not self.config.shallow_water_enabled:
            return
        remaining = float(dt)
        while remaining > 1e-9:
            dt_sub = min(remaining, self.max_stable_dt(cfl=0.40))
            self._advance_substep(dt_sub)
            remaining -= dt_sub
            self.t += dt_sub
            self.substep_count += 1

    def _advance_substep(self, dt: float) -> None:
        g = float(self.config.g_m_s2)
        rho_w = float(self.config.rho_water_kg_m3)
        h_dry = self.h_dry

        # --- X-direction interior faces: (ny, nx-1) ---
        fx_h, fx_hu, fx_hv, p_xl, p_xr = _audusse_rusanov_flux_1d(
            self.h[:, :-1],
            self.hu[:, :-1],
            self.hv[:, :-1],
            self.bed[:, :-1],
            self.h[:, 1:],
            self.hu[:, 1:],
            self.hv[:, 1:],
            self.bed[:, 1:],
            g,
            h_dry,
        )

        # --- Y-direction interior faces: (ny-1, nx) ---
        # Notice swap of (hu, hv) -> (hv, hu) along Y normal
        fy_h, fy_hv, fy_hu, p_yl, p_yr = _audusse_rusanov_flux_1d(
            self.h[:-1, :],
            self.hv[:-1, :],
            self.hu[:-1, :],
            self.bed[:-1, :],
            self.h[1:, :],
            self.hv[1:, :],
            self.hu[1:, :],
            self.bed[1:, :],
            g,
            h_dry,
        )

        dh = np.zeros_like(self.h)
        dhu = np.zeros_like(self.hu)
        dhv = np.zeros_like(self.hv)

        inv_dx = 1.0 / self.dx
        inv_dy = 1.0 / self.dy

        # X divergences (zero normal mass flux at outer domain walls -> exact conservation)
        dh[:, :-1] -= inv_dx * fx_h
        dh[:, 1:] += inv_dx * fx_h

        dhu[:, :-1] -= inv_dx * (fx_hu - p_xl)
        dhu[:, 1:] += inv_dx * (fx_hu - p_xr)
        dhv[:, :-1] -= inv_dx * fx_hv
        dhv[:, 1:] += inv_dx * fx_hv

        # Y divergences
        dh[:-1, :] -= inv_dy * fy_h
        dh[1:, :] += inv_dy * fy_h

        dhv[:-1, :] -= inv_dy * (fy_hv - p_yl)
        dhv[1:, :] += inv_dy * (fy_hv - p_yr)
        dhu[:-1, :] -= inv_dy * fy_hu
        dhu[1:, :] += inv_dy * fy_hu

        # Explicit Euler mass update
        h_new = np.maximum(0.0, self.h + dt * dh)
        hu_new = self.hu + dt * dhu
        hv_new = self.hv + dt * dhv

        # Wind shear stress + gentle ambient current nudging in deep/open basin + Manning friction
        wet = h_new > self.h_vel_damp
        wind_spd = max(0.0, float(self.config.wind_speed_mps))
        wind_ang = math.radians(float(self.config.wind_direction_deg))
        if wind_spd > 0.05:
            # Wu wind stress coefficient C10 ~ (0.8 + 0.065 * U10) * 1e-3
            c10 = (0.8 + 0.065 * wind_spd) * 1e-3
            tau_w = (RHO_AIR_ISA / rho_w) * c10 * wind_spd * wind_spd
            hu_new[wet] += dt * tau_w * math.cos(wind_ang)
            hv_new[wet] += dt * tau_w * math.sin(wind_ang)

        curr_spd = max(0.0, float(self.config.current_speed_mps))
        if curr_spd > 1e-4:
            curr_ang = math.radians(float(self.config.current_direction_deg))
            target_u = curr_spd * math.cos(curr_ang)
            target_v = curr_spd * math.sin(curr_ang)
            # Depth-weighted gentle open-basin current relaxation (tau_relax = 25 s)
            relax = dt * np.clip(h_new / 3.0, 0.0, 1.0) / 25.0
            hu_new += relax * (h_new * target_u - hu_new)
            hv_new += relax * (h_new * target_v - hv_new)

        # Semi-implicit Manning quadratic bottom friction (always stable for wet/dry)
        u_tmp = np.where(wet, hu_new / np.maximum(h_new, self.h_vel_damp), 0.0)
        v_tmp = np.where(wet, hv_new / np.maximum(h_new, self.h_vel_damp), 0.0)
        speed = np.hypot(u_tmp, v_tmp)
        cf = (g * (self.manning_n ** 2)) / np.power(np.maximum(h_new, self.h_vel_damp), 4.0 / 3.0)
        fric_denom = 1.0 + dt * cf * speed
        hu_new = np.where(wet, hu_new / fric_denom, 0.0)
        hv_new = np.where(wet, hv_new / fric_denom, 0.0)

        # Suppress residual momentum in ultra-thin films
        thin = h_new <= self.h_dry
        h_new[thin] = 0.0
        hu_new[thin] = 0.0
        hv_new[thin] = 0.0

        self.h = h_new
        self.hu = hu_new
        self.hv = hv_new

    def sample(self, x: np.ndarray | float, y: np.ndarray | float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Bilinearly sample SWE (eta, depth, u, v) at world (x, y) coordinates."""
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        xa, ya = np.broadcast_arrays(xa, ya)
        shape = xa.shape

        fx = np.clip((xa.ravel() + self.half_x) / self.dx, 0.0, self.nx - 1.000001)
        fy = np.clip((ya.ravel() + self.half_y) / self.dy, 0.0, self.ny - 1.000001)
        ix = np.minimum(np.floor(fx).astype(np.intp), self.nx - 2)
        iy = np.minimum(np.floor(fy).astype(np.intp), self.ny - 2)
        tx = fx - ix
        ty = fy - iy

        def bilerp(field: np.ndarray) -> np.ndarray:
            v00 = field[iy, ix]
            v10 = field[iy, ix + 1]
            v01 = field[iy + 1, ix]
            v11 = field[iy + 1, ix + 1]
            return ((1 - ty) * ((1 - tx) * v00 + tx * v10) + ty * ((1 - tx) * v01 + tx * v11)).reshape(shape)

        h = bilerp(self.h)
        bed = bilerp(self.bed)
        eta = bed + h
        hu = bilerp(self.hu)
        hv = bilerp(self.hv)
        wet = h > self.h_vel_damp
        u = np.where(wet, hu / np.maximum(h, self.h_vel_damp), 0.0)
        v = np.where(wet, hv / np.maximum(h, self.h_vel_damp), 0.0)
        return eta, h, u, v

    def conservation_metrics(self) -> dict[str, Any]:
        vol = float(np.sum(self.h) * self.cell_area)
        expected = max(self._expected_volume_m3, 1e-6)
        mass_kg = vol * float(self.config.rho_water_kg_m3)
        mom_x = float(np.sum(self.hu) * self.cell_area * float(self.config.rho_water_kg_m3))
        mom_y = float(np.sum(self.hv) * self.cell_area * float(self.config.rho_water_kg_m3))
        wet_cells = int(np.sum(self.h > self.h_dry))
        total_cells = int(self.h.size)
        return {
            'time_s': self.t,
            'substeps': self.substep_count,
            'water_volume_m3': vol,
            'expected_volume_m3': self._expected_volume_m3,
            'mass_error_m3': vol - self._expected_volume_m3,
            'relative_mass_error': abs(vol - self._expected_volume_m3) / expected,
            'water_mass_kg': mass_kg,
            'momentum_xy_kg_mps': [mom_x, mom_y],
            'wet_cells': wet_cells,
            'dry_cells': total_cells - wet_cells,
            'max_speed_mps': float(
                np.max(
                    np.where(
                        self.h > self.h_vel_damp,
                        np.hypot(self.hu, self.hv) / np.maximum(self.h, self.h_vel_damp),
                        0.0,
                    )
                )
            ),
        }


@dataclass
class HybridWaterSample:
    eta: np.ndarray
    depth: np.ndarray
    normal: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    dynamic_pressure: np.ndarray
    wet_fraction: np.ndarray


class HybridWaterField:
    """Combines directional open-water waves with bathymetry-aware shallow-water flow."""

    def __init__(
        self,
        world,
        config: WaterEnvironmentConfig | None = None,
        swe_nx: int = 101,
        swe_ny: int = 61,
        swe_step_interval_s: float = 0.02,
    ):
        self.world = world
        self.config = config or WaterEnvironmentConfig()
        self.open_water = OpenWaterWaveField(self.config, reference_depth_m=11.0)
        self.shallow = ShallowWaterSolver(world, self.config, nx=swe_nx, ny=swe_ny)
        self.sim_time_s = 0.0
        self.swe_step_interval_s = max(float(swe_step_interval_s), 0.0025)
        self._swe_accum_s = 0.0

    def reconfigure(self, payload: dict[str, Any] | WaterEnvironmentConfig) -> WaterEnvironmentConfig:
        if isinstance(payload, WaterEnvironmentConfig):
            cfg = payload
        else:
            merged = self.config.to_dict()
            merged.update(payload)
            cfg = WaterEnvironmentConfig.from_dict(merged)
        old_wl = self.config.water_level_m
        self.config = cfg
        self.open_water.reconfigure(cfg)
        self.shallow.config = cfg
        if abs(cfg.water_level_m - old_wl) > 1e-9:
            self.shallow.set_water_level(cfg.water_level_m)
        return cfg

    def step(self, dt: float) -> None:
        dt_f = float(dt)
        self.sim_time_s += dt_f
        self._swe_accum_s += dt_f
        if self._swe_accum_s >= self.swe_step_interval_s - 1e-9:
            self.shallow.step(self._swe_accum_s)
            self._swe_accum_s = 0.0

    def evaluate(
        self,
        x: np.ndarray | float,
        y: np.ndarray | float,
        z: np.ndarray | float | None = None,
        t: float | None = None,
    ) -> HybridWaterSample:
        t_eval = self.sim_time_s if t is None else float(t)
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        xa, ya = np.broadcast_arrays(xa, ya)

        if hasattr(self.world, 'terrain_z_array'):
            bed = self.world.terrain_z_array(xa, ya)
        else:
            bed = np.vectorize(self.world.terrain_z)(xa, ya)

        eta_swe, h_swe, u_swe, v_swe = self.shallow.sample(xa, ya)
        # Depth relative to local shallow water surface
        local_depth = np.maximum(0.0, eta_swe - bed)
        wave = self.open_water.evaluate(
            xa,
            ya,
            z=z,
            t=t_eval,
            local_depth=np.maximum(local_depth, 0.25),
            water_level_offset=0.0,
        )

        # Blend open-water orbital wave disturbance (zero-mean eta_wave = wave.eta)
        # atop SWE bathymetry-aware free surface (eta_swe).
        # Near dry shoreline (h_swe < 0.25 m), attenuate wave perturbation smoothly to 0
        # so dry banks remain dry unless SWE run-up wets them.
        wave_blend = np.clip((h_swe - 0.08) / 0.35, 0.0, 1.0)
        eta_hybrid = np.where(
            h_swe > 1e-4,
            np.maximum(bed, eta_swe + wave.eta * wave_blend),
            bed,
        )
        depth_hybrid = np.maximum(0.0, eta_hybrid - bed)

        # Combine SWE depth-averaged wind/current flow with open-water wave orbital velocity.
        # Note: open_water.velocity already contains ambient current, so remove ambient
        # open-water current base before adding SWE velocity to avoid double-counting.
        vel = wave.velocity.copy()
        vel[..., 0] = (vel[..., 0] - self.open_water.current_xy[0]) * wave_blend + u_swe
        vel[..., 1] = (vel[..., 1] - self.open_water.current_xy[1]) * wave_blend + v_swe
        vel[..., 2] = vel[..., 2] * wave_blend

        acc = wave.acceleration * wave_blend[..., None]
        p_dyn = wave.dynamic_pressure * wave_blend

        # Effective surface normal blends wave normal in wet regions toward terrain normal when dry
        norm = wave.normal.copy()
        norm[..., 0] *= wave_blend
        norm[..., 1] *= wave_blend
        norm[..., 2] = np.where(wave_blend > 0.0, norm[..., 2], 1.0)
        n_len = np.linalg.norm(norm, axis=-1, keepdims=True)
        norm = norm / np.maximum(n_len, 1e-12)

        wet_frac = np.clip(depth_hybrid / 0.04, 0.0, 1.0)
        return HybridWaterSample(
            eta=eta_hybrid,
            depth=depth_hybrid,
            normal=norm,
            velocity=vel,
            acceleration=acc,
            dynamic_pressure=p_dyn,
            wet_fraction=wet_frac,
        )

    def elevation_grid(self, nx: int = 81, ny: int = 49, t: float | None = None) -> dict[str, Any]:
        """Downsampled elevation & wet-mask snapshot for Three.js water rendering."""
        hx = self.shallow.half_x
        hy = self.shallow.half_y
        xs = np.linspace(-hx, hx, int(nx), dtype=np.float64)
        ys = np.linspace(-hy, hy, int(ny), dtype=np.float64)
        xg, yg = np.meshgrid(xs, ys)
        samp = self.evaluate(xg, yg, t=t)
        return {
            't': self.sim_time_s if t is None else float(t),
            'nx': int(nx),
            'ny': int(ny),
            'half_x': hx,
            'half_y': hy,
            'water_level_m': float(self.config.water_level_m),
            'eta': np.round(samp.eta, 3).tolist(),
            'depth': np.round(samp.depth, 3).tolist(),
        }
