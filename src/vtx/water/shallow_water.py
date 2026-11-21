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
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    bed: np.ndarray,
    eta: np.ndarray,
    g: float,
    h_dry: float,
    *,
    axis: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Well-balanced Audusse hydrostatic reconstruction + Rusanov flux on 1D faces.

    Returns (flux_h, flux_hu, flux_hv, bed_src_left, bed_src_right) where
    bed_src_* = 0.5 * g * (h_rec^2 - h^2) directly ensures C-property (lake at rest).
    """
    if axis == 1:
        left, right = np.s_[:, :-1], np.s_[:, 1:]
    else:
        left, right = np.s_[:-1, :], np.s_[1:, :]
    h_l, h_r = h[left], h[right]
    z_l, z_r = bed[left], bed[right]
    eta_l, eta_r = eta[left], eta[right]
    z_iface = np.maximum(z_l, z_r)

    h_star_l = np.maximum(0.0, eta_l - z_iface)
    h_star_r = np.maximum(0.0, eta_r - z_iface)

    # Zero velocity if reconstructed face depth is dry
    wet_l = h_star_l > h_dry
    wet_r = h_star_r > h_dry
    u_l = np.where(wet_l, u[left], 0.0)
    v_l = np.where(wet_l, v[left], 0.0)
    u_r = np.where(wet_r, u[right], 0.0)
    v_r = np.where(wet_r, v[right], 0.0)

    hu_star_l = h_star_l * u_l
    hv_star_l = h_star_l * v_l
    hu_star_r = h_star_r * u_r
    hv_star_r = h_star_r * v_r
    h_star_l_sq = h_star_l * h_star_l
    h_star_r_sq = h_star_r * h_star_r

    # Physical fluxes
    f0_l = hu_star_l
    f1_l = hu_star_l * u_l + 0.5 * g * h_star_l_sq
    f2_l = hu_star_l * v_l

    f0_r = hu_star_r
    f1_r = hu_star_r * u_r + 0.5 * g * h_star_r_sq
    f2_r = hu_star_r * v_r

    c_l = np.sqrt(g * h_star_l)
    c_r = np.sqrt(g * h_star_r)
    s_max = np.maximum(np.abs(u_l) + c_l, np.abs(u_r) + c_r)
    # Zero numerical diffusion across completely dry interface
    both_dry = (h_star_l <= h_dry) & (h_star_r <= h_dry)
    diffusion = 0.5 * np.where(both_dry, 0.0, s_max)

    flux_h = 0.5 * (f0_l + f0_r) - diffusion * (h_star_r - h_star_l)
    flux_hu = 0.5 * (f1_l + f1_r) - diffusion * (hu_star_r - hu_star_l)
    flux_hv = 0.5 * (f2_l + f2_r) - diffusion * (hv_star_r - hv_star_l)

    # Topographic pressure correction: preserves eta = const -> exact zero tendency
    # Also prevents false dry-cliff pull on empty cell
    p_l = 0.5 * g * (h_star_l_sq - h_l * h_l)
    p_r = 0.5 * g * (h_star_r_sq - h_r * h_r)
    # Zero momentum source if cell is dry and wet neighbor is below cell bed
    p_l = np.where((h_l <= h_dry) & (eta_r <= z_l), 0.0, p_l)
    p_r = np.where((h_r <= h_dry) & (eta_l <= z_r), 0.0, p_r)

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

        self._state_version = 0
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
        self._state_version = getattr(self, '_state_version', 0) + 1

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
        self._state_version += 1

    def inject_solitary_pulse(self, cx: float, cy: float, amp_m: float, sigma_m: float) -> None:
        """Add a conservative zero-net-check or deterministic free-surface pulse (tests/waves)."""
        xg, yg = np.meshgrid(self.xs, self.ys)
        r2 = ((xg - cx) ** 2 + (yg - cy) ** 2) / max(sigma_m ** 2, 1.0)
        dh = amp_m * np.exp(-0.5 * r2) * (self.h > 0.2)
        self.h = np.maximum(0.0, self.h + dh)
        self._expected_volume_m3 += float(np.sum(dh) * self.cell_area)
        self._state_version += 1

    def apply_momentum_impulse(
        self,
        cx: float,
        cy: float,
        fx_n: float,
        fy_n: float,
        dt: float,
        radius_m: float = 5.0,
    ) -> None:
        """Couple craft hydrodynamic reaction & fan slipstream into wet SWE momentum (zero mass change)."""
        if dt <= 0.0 or not self.config.shallow_water_enabled:
            return
        if abs(fx_n) + abs(fy_n) < 1e-3:
            return
        sigma = max(float(radius_m), 0.75 * max(self.dx, self.dy))
        span_x = 3.0 * sigma
        span_y = 3.0 * sigma
        ix0 = max(0, int(math.floor((cx - span_x + self.half_x) / self.dx)))
        ix1 = min(self.nx, int(math.ceil((cx + span_x + self.half_x) / self.dx)) + 1)
        iy0 = max(0, int(math.floor((cy - span_y + self.half_y) / self.dy)))
        iy1 = min(self.ny, int(math.ceil((cy + span_y + self.half_y) / self.dy)) + 1)
        if ix1 <= ix0 or iy1 <= iy0:
            return

        h_sub = self.h[iy0:iy1, ix0:ix1]
        wet = h_sub > self.h_vel_damp
        if not np.any(wet):
            return

        xg, yg = np.meshgrid(self.xs[ix0:ix1], self.ys[iy0:iy1])
        r2 = ((xg - cx) ** 2 + (yg - cy) ** 2) / (sigma * sigma)
        weights = np.where(wet, np.exp(-0.5 * r2), 0.0)
        w_sum = float(np.sum(weights))
        if w_sum <= 1e-12:
            return
        # Convert Newtons integrated over cell_area to m^2/s^2 momentum source
        rho_w = max(float(self.config.rho_water_kg_m3), 100.0)
        g = float(self.config.g_m_s2)
        scale = float(dt) / (rho_w * w_sum * self.cell_area)
        hu_next = self.hu[iy0:iy1, ix0:ix1] + float(fx_n) * scale * weights
        hv_next = self.hv[iy0:iy1, ix0:ix1] + float(fy_n) * scale * weights

        # Preserve sub-critical Froude CFL stability on localized impulse cells
        max_q = np.where(wet, h_sub * np.minimum(5.5, 0.55 * np.sqrt(g * np.maximum(h_sub, 0.0))), 0.0)
        q_mag = np.hypot(hu_next, hv_next)
        cap = np.where(q_mag > max_q, max_q / np.maximum(q_mag, 1e-12), 1.0)
        self.hu[iy0:iy1, ix0:ix1] = np.where(wet, hu_next * cap, 0.0)
        self.hv[iy0:iy1, ix0:ix1] = np.where(wet, hv_next * cap, 0.0)
        self._state_version += 1

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
        self._state_version += 1

    def _advance_substep(self, dt: float) -> None:
        g = float(self.config.g_m_s2)
        rho_w = float(self.config.rho_water_kg_m3)
        h_dry = self.h_dry

        # A cell supplies four faces. Share its depth, elevation and velocities
        # while retaining each face's own reconstruction and flux arithmetic.
        wet_cells = self.h > h_dry
        depth = np.maximum(self.h, h_dry)
        u = np.where(wet_cells, self.hu / depth, 0.0)
        v = np.where(wet_cells, self.hv / depth, 0.0)
        eta = self.h + self.bed

        # --- X-direction interior faces: (ny, nx-1) ---
        fx_h, fx_hu, fx_hv, p_xl, p_xr = _audusse_rusanov_flux_1d(
            self.h, u, v, self.bed, eta, g, h_dry, axis=1
        )

        # --- Y-direction interior faces: (ny-1, nx) ---
        # Notice swap of (hu, hv) -> (hv, hu) along Y normal
        fy_h, fy_hv, fy_hu, p_yl, p_yr = _audusse_rusanov_flux_1d(
            self.h, v, u, self.bed, eta, g, h_dry, axis=0
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
        friction_depth = np.maximum(h_new, self.h_vel_damp)
        u_tmp = np.where(wet, hu_new / friction_depth, 0.0)
        v_tmp = np.where(wet, hv_new / friction_depth, 0.0)
        speed = np.hypot(u_tmp, v_tmp)
        cf = (g * (self.manning_n ** 2)) / np.power(friction_depth, 4.0 / 3.0)
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

    def sample(
        self,
        x: np.ndarray | float,
        y: np.ndarray | float,
        *,
        eta_only: bool = False,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
        omx = 1.0 - tx
        omy = 1.0 - ty
        w00 = omy * omx
        w10 = omy * tx
        w01 = ty * omx
        w11 = ty * tx
        nx = self.nx
        idx = iy * nx + ix

        def bilerp(field: np.ndarray) -> np.ndarray:
            f = field.ravel()
            return (w00 * f[idx] + w10 * f[idx + 1] + w01 * f[idx + nx] + w11 * f[idx + nx + 1]).reshape(shape)

        h = bilerp(self.h)
        bed = bilerp(self.bed)
        eta = bed + h
        if eta_only:
            empty = np.empty(0, dtype=np.float64)
            return eta, h, empty, empty
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

    def checkpoint_state(self, *, copy_arrays=False) -> dict[str, Any]:
        """Capture complete float64 state, optionally retaining detached NumPy arrays."""
        return {
            'nx': int(self.nx),
            'ny': int(self.ny),
            'half_x': float(self.half_x),
            'half_y': float(self.half_y),
            'manning_n': float(self.manning_n),
            'water_level_m': float(self.water_level_m),
            'initial_volume_m3': float(self.initial_volume_m3),
            **{key: (array.copy() if copy_arrays else array.tolist())
               for key, array in (('h', self.h), ('hu', self.hu), ('hv', self.hv))},
            't': float(self.t),
            'substep_count': int(self.substep_count),
            '_expected_volume_m3': float(self._expected_volume_m3),
            'config': self.config.to_dict(),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore complete float64 shallow-water solver state from a checkpoint."""
        if int(state['nx']) != self.nx or int(state['ny']) != self.ny:
            raise ValueError(
                f"ShallowWaterSolver grid mismatch: expected ({self.nx}, {self.ny}), "
                f"got ({state['nx']}, {state['ny']})"
            )
        if abs(float(state['half_x']) - self.half_x) > 1e-6 or abs(float(state['half_y']) - self.half_y) > 1e-6:
            raise ValueError(
                f"ShallowWaterSolver domain mismatch: expected ({self.half_x}, {self.half_y}), "
                f"got ({state['half_x']}, {state['half_y']})"
            )

        expected_shape = (self.ny, self.nx)
        restored_arrays: dict[str, np.ndarray] = {}
        for key in ('h', 'hu', 'hv'):
            arr = np.asarray(state[key], dtype=np.float64)
            if arr.shape != expected_shape or not np.all(np.isfinite(arr)):
                raise ValueError(f'Invalid shallow-water checkpoint array {key!r}: shape={arr.shape}')
            restored_arrays[key] = arr.copy()

        if 'config' in state and state['config'] is not None:
            cfg = state['config']
            self.config = cfg if isinstance(cfg, WaterEnvironmentConfig) else WaterEnvironmentConfig.from_dict(cfg)
        if 'manning_n' in state:
            self.manning_n = float(state['manning_n'])
        self.water_level_m = float(state.get('water_level_m', self.config.water_level_m))
        self.h = restored_arrays['h']
        self.hu = restored_arrays['hu']
        self.hv = restored_arrays['hv']
        self.t = float(state['t'])
        self.substep_count = int(state['substep_count'])
        self._expected_volume_m3 = float(state['_expected_volume_m3'])
        self.initial_volume_m3 = float(state.get('initial_volume_m3', self._expected_volume_m3))
        self._state_version += 1


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
        self._vessel_wake: dict[str, Any] = self._default_wake_state()
        self._state_version = 0

    @staticmethod
    def _default_wake_state() -> dict[str, Any]:
        return {
            'active': False,
            'x': 40.0,
            'y': 0.0,
            'heading_rad': 0.0,
            'speed_mps': 0.0,
            'vx_mps': 0.0,
            'vy_mps': 0.0,
            'heave_rate_mps': 0.0,
            'draft_m': 0.0,
            'submerged_vol_m3': 0.0,
            'thrust_n': 0.0,
            'beam_m': 1.6,
            'length_m': 6.8,
            't_s': 0.0,
        }

    def reset(self, water_level_m: float | None = None) -> None:
        """Reset water clock, SWE accumulator, wake overlay, and shallow-water fields."""
        if water_level_m is not None:
            wl = float(water_level_m)
            if abs(wl - float(self.config.water_level_m)) > 1e-12:
                merged = self.config.to_dict()
                merged['water_level_m'] = wl
                self.config = WaterEnvironmentConfig.from_dict(merged)
                self.open_water.reconfigure(self.config)
                self.shallow.config = self.config
        self.shallow.reset(water_level_m=water_level_m)
        self.sim_time_s = 0.0
        self._swe_accum_s = 0.0
        self._vessel_wake = self._default_wake_state()
        self._state_version += 1

    def checkpoint_state(self, *, copy_arrays=False) -> dict[str, Any]:
        """Serialize complete float64 hybrid water field and SWE solver state."""
        wake_copy = {
            k: (
                bool(v)
                if isinstance(v, (bool, np.bool_))
                else (float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v)
            )
            for k, v in self._vessel_wake.items()
        }
        return {
            'sim_time_s': float(self.sim_time_s),
            '_swe_accum_s': float(self._swe_accum_s),
            'swe_step_interval_s': float(self.swe_step_interval_s),
            '_vessel_wake': wake_copy,
            'config': self.config.to_dict(),
            'shallow': self.shallow.checkpoint_state(copy_arrays=copy_arrays),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore complete hybrid water field and SWE solver state from a checkpoint."""
        cfg_data = state.get('config')
        if cfg_data is not None:
            cfg = cfg_data if isinstance(cfg_data, WaterEnvironmentConfig) else WaterEnvironmentConfig.from_dict(cfg_data)
            self.config = cfg
            self.open_water.reconfigure(cfg)
            self.shallow.config = cfg

        self.sim_time_s = float(state['sim_time_s'])
        self._swe_accum_s = float(state['_swe_accum_s'])
        if 'swe_step_interval_s' in state:
            self.swe_step_interval_s = max(float(state['swe_step_interval_s']), 0.0025)

        wake_raw = state.get('_vessel_wake')
        wake_restored = self._default_wake_state()
        if isinstance(wake_raw, dict):
            for k, v in wake_raw.items():
                if k == 'active':
                    wake_restored[k] = bool(v)
                elif isinstance(v, (int, float, np.integer, np.floating)):
                    wake_restored[k] = float(v)
                else:
                    wake_restored[k] = v
        self._vessel_wake = wake_restored

        if 'shallow' in state and state['shallow'] is not None:
            self.shallow.restore_state(state['shallow'])
        self._state_version += 1

    def apply_vessel_disturbance(
        self,
        x: float,
        y: float,
        heading_rad: float,
        vx_world: float,
        vy_world: float,
        heave_rate_mps: float,
        draft_m: float,
        submerged_vol_m3: float,
        hydro_reaction_xy: tuple[float, float] | np.ndarray,
        fan_thrust_n: float,
        dt: float,
        beam_m: float = 1.6,
        length_m: float = 6.8,
        t_s: float | None = None,
    ) -> None:
        """Update vessel wake state and inject opposing hull+propwash momentum into SWE."""
        speed = math.hypot(float(vx_world), float(vy_world))
        thr = float(fan_thrust_n)
        heave = float(heave_rate_mps)
        active = bool(speed >= 0.08 or abs(heave) >= 0.04 or abs(thr) >= 40.0)
        self._vessel_wake = {
            'active': active,
            'x': float(x),
            'y': float(y),
            'heading_rad': float(heading_rad),
            'speed_mps': speed,
            'vx_mps': float(vx_world),
            'vy_mps': float(vy_world),
            'heave_rate_mps': heave,
            'draft_m': max(0.0, float(draft_m)),
            'submerged_vol_m3': max(0.0, float(submerged_vol_m3)),
            'thrust_n': thr,
            'beam_m': float(beam_m),
            'length_m': float(length_m),
            't_s': self.sim_time_s if t_s is None else float(t_s),
        }
        self._state_version += 1
        if not active or not getattr(self.config, 'wake_enabled', True):
            return
        # Opposing hull hydrodynamic drag/lift + aft ducted-fan slipstream wash (-cos(psi), -sin(psi))
        fx_water = -float(hydro_reaction_xy[0]) - 0.25 * thr * math.cos(float(heading_rad))
        fy_water = -float(hydro_reaction_xy[1]) - 0.25 * thr * math.sin(float(heading_rad))
        self.shallow.apply_momentum_impulse(
            cx=float(x),
            cy=float(y),
            fx_n=fx_water,
            fy_n=fy_water,
            dt=float(dt),
            radius_m=max(4.5, 0.75 * float(length_m)),
        )

    def get_wake_state(self) -> dict[str, Any]:
        return dict(self._vessel_wake)

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
        self._state_version += 1
        return cfg

    def step(self, dt: float) -> None:
        dt_f = float(dt)
        self.sim_time_s += dt_f
        self._swe_accum_s += dt_f
        if self._swe_accum_s >= self.swe_step_interval_s - 1e-9:
            self.shallow.step(self._swe_accum_s)
            self._swe_accum_s = 0.0
        self._state_version += 1

    def _base_components(self, x, y, z, t, eta_only):
        """Immutable query primitives shared by the wave/wake overlays.

        Default standalone evaluation computes these in the original order.
        The harbour subclass can reuse them within one locked query only.
        """
        t_eval = self.sim_time_s if t is None else float(t)
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        xa, ya = np.broadcast_arrays(xa, ya)

        if hasattr(self.world, 'terrain_z_array'):
            bed = self.world.terrain_z_array(xa, ya)
        else:
            bed = np.vectorize(self.world.terrain_z)(xa, ya)

        eta_swe, h_swe, u_swe, v_swe = self.shallow.sample(xa, ya, eta_only=eta_only)
        # Depth relative to local shallow water surface
        local_depth = np.maximum(0.0, eta_swe - bed)
        wave = self.open_water.evaluate(
            xa,
            ya,
            z=z,
            t=t_eval,
            local_depth=np.maximum(local_depth, 0.25),
            water_level_offset=0.0,
            eta_only=eta_only,
        )
        return t_eval, xa, ya, bed, eta_swe, h_swe, u_swe, v_swe, wave

    def evaluate(
        self,
        x: np.ndarray | float,
        y: np.ndarray | float,
        z: np.ndarray | float | None = None,
        t: float | None = None,
        *,
        eta_only: bool = False,
    ) -> HybridWaterSample:
        return self._evaluate_components(
            self._base_components(x, y, z, t, eta_only), self._vessel_wake, eta_only
        )

    def _evaluate_components(self, components, wake, eta_only):
        t_eval, xa, ya, bed, eta_swe, h_swe, u_swe, v_swe, wave = components

        # Blend open-water orbital wave disturbance (zero-mean eta_wave = wave.eta)
        # atop SWE bathymetry-aware free surface (eta_swe).
        # Near dry shoreline (h_swe < 0.25 m), attenuate wave perturbation smoothly to 0
        # so dry banks remain dry unless SWE run-up wets them.
        wave_blend = np.clip((h_swe - 0.08) / 0.35, 0.0, 1.0)
        eta_delta = wave.eta * wave_blend

        if not eta_only:
            vel = wave.velocity.copy()
            vel[..., 0] = (vel[..., 0] - self.open_water.current_xy[0]) * wave_blend + u_swe
            vel[..., 1] = (vel[..., 1] - self.open_water.current_xy[1]) * wave_blend + v_swe
            vel[..., 2] = vel[..., 2] * wave_blend

            acc = wave.acceleration * wave_blend[..., None]
            p_dyn = wave.dynamic_pressure * wave_blend

            # Recover total free-surface slope gradients (d_eta / dx, d_eta / dy)
            nz_safe = np.maximum(wave.normal[..., 2], 1e-6)
            dhdx_tot = -(wave.normal[..., 0] / nz_safe) * wave_blend
            dhdy_tot = -(wave.normal[..., 1] / nz_safe) * wave_blend
            has_slope = self.open_water.amp.size > 0

        # Overlay analytical Kelvin V-wake & heave rings strictly aft/outside hull center when underway
        if wake is not None and getattr(self.config, 'wake_enabled', True) and wake.get('active') and xa.size > 0:
            spd = float(wake['speed_mps'])
            draft_eff = max(float(wake['draft_m']), 0.15)
            amp_k = min(0.36, 0.032 * draft_eff * spd * min(spd / 2.0, 1.0))
            h_rate = float(wake['heave_rate_mps'])
            amp_h = min(0.16, 0.055 * abs(h_rate)) * min(draft_eff / 0.25, 1.0)
            if amp_k > 1e-4 or amp_h > 1e-4:
                wx, wy = float(wake['x']), float(wake['y'])
                if not (
                    float(np.max(xa)) < wx - 115.0
                    or float(np.min(xa)) > wx + 115.0
                    or float(np.max(ya)) < wy - 115.0
                    or float(np.min(ya)) > wy + 115.0
                ):
                    dx_w = xa - wx
                    dy_w = ya - wy
                    r_w_sq = dx_w * dx_w + dy_w * dy_w
                    if np.any(r_w_sq < 13225.0):
                        r_w = np.sqrt(r_w_sq)
                        if amp_k > 1e-4:
                            psi = float(wake['heading_rad'])
                            c_p, s_p = math.cos(psi), math.sin(psi)
                            # Track direction follows velocity vector when moving fast, else craft heading
                            if spd >= 0.4:
                                u_dir = float(wake['vx_mps']) / spd
                                v_dir = float(wake['vy_mps']) / spd
                            else:
                                u_dir, v_dir = c_p, s_p
                            # s_aft > 0 behind stern; y_lat signed offset port/starboard from wake axis
                            s_aft = -(dx_w * u_dir + dy_w * v_dir)
                            y_lat = -dx_w * v_dir + dy_w * u_dir
                            s_abs = np.maximum(s_aft, 0.0)

                            # Smooth Kelvin 19.47 deg half-wedge window beginning behind midship (s_aft >= 0)
                            aft_gate = np.clip((s_aft - 0.8) / 2.2, 0.0, 1.0) * (1.0 - np.clip((s_aft - 80.0) / 30.0, 0.0, 1.0))
                            wedge_half = np.maximum(1.2, 0.36 * s_abs + 1.6)
                            in_wedge = np.exp(-0.5 * np.maximum(0.0, np.abs(y_lat) - 0.72 * wedge_half) ** 2 / np.maximum(0.18 * wedge_half, 1.2) ** 2)
                            g_val = float(self.config.g_m_s2)
                            lam_k = max(4.5, min(28.0, 2.0 * math.pi * max(spd, 2.5) ** 2 / g_val))
                            k_k = 2.0 * math.pi / lam_k
                            phase_div = k_k * (s_abs - 2.35 * np.abs(y_lat)) - 0.65 * spd * t_eval
                            phase_tr = k_k * s_abs - 0.55 * spd * t_eval
                            env = aft_gate * in_wedge / np.sqrt(1.0 + 0.055 * s_abs) * wave_blend
                            eta_wake = amp_k * env * (0.72 * np.cos(phase_div) + 0.28 * np.cos(phase_tr))
                            eta_delta = eta_delta + eta_wake
                            if not eta_only:
                                # Approximate slope gradient for tilted Kelvin facets
                                d_phase_s = k_k * amp_k * env * (-0.72 * np.sin(phase_div) - 0.28 * np.sin(phase_tr))
                                dhdx_tot = dhdx_tot + (-u_dir) * d_phase_s
                                dhdy_tot = dhdy_tot + (-v_dir) * d_phase_s
                                has_slope = True
                                # Orbital velocity under Kelvin surface wave
                                vel[..., 0] = vel[..., 0] + eta_wake * 0.65 * u_dir
                                vel[..., 1] = vel[..., 1] + eta_wake * 0.65 * v_dir

                        # Circular heave radiation ring outside r > 1.8 m (eliminates self-excitation loop)
                        if amp_h > 1e-4:
                            outer = np.clip((r_w - 1.8) / 1.8, 0.0, 1.0) * (1.0 - np.clip((r_w - 35.0) / 15.0, 0.0, 1.0))
                            eta_h = amp_h * outer * np.cos(0.95 * r_w - 3.6 * t_eval) / np.sqrt(1.0 + 0.12 * r_w) * wave_blend
                            eta_delta = eta_delta + eta_h

        # Overlay Burgers-Rott whirlpools (compact support strictly zero outside r_influence_m)
        wp_enabled = getattr(self.config, 'whirlpools_enabled', True)
        wp_intensity = max(0.0, float(getattr(self.config, 'whirlpool_intensity', 1.0)))
        whirlpools = getattr(self.world, 'whirlpools', ()) if (wp_enabled and wp_intensity > 1e-4 and xa.size > 0) else ()
        rho_w = float(self.config.rho_water_kg_m3)
        for wp in whirlpools:
            cx, cy = float(wp['x']), float(wp['y'])
            r_core = max(float(wp['r_core_m']), 1.0)
            r_infl = max(float(wp['r_influence_m']), r_core + 5.0)
            if (
                float(np.max(xa)) < cx - r_infl
                or float(np.min(xa)) > cx + r_infl
                or float(np.max(ya)) < cy - r_infl
                or float(np.min(ya)) > cy + r_infl
            ):
                continue
            dx_v = xa - cx
            dy_v = ya - cy
            r_v_sq = dx_v * dx_v + dy_v * dy_v
            if not np.any(r_v_sq < r_infl * r_infl):
                continue
            r_v = np.sqrt(r_v_sq)
            r_safe = np.maximum(r_v, 1e-3)
            xi = r_v / r_core
            # Smooth C^2 compact window: 1 in core, 0 for r >= r_infl
            tw = np.clip((r_v - 0.62 * r_infl) / (0.38 * r_infl), 0.0, 1.0)
            taper = (1.0 - tw * tw * (3.0 - 2.0 * tw)) * np.clip((h_swe - 0.15) / 0.5, 0.0, 1.0)

            r_f = 1.45 * r_core
            eta_wp = wp_intensity * float(wp['core_drop_m']) * np.exp(-0.5 * (r_v / r_f) ** 2) * taper
            eta_delta = eta_delta + eta_wp
            if eta_only:
                continue

            spin = float(wp.get('spin', 1))
            v_theta = spin * wp_intensity * float(wp['max_swirl_mps']) * ((1.0 - np.exp(-(xi * xi))) / np.maximum(xi * 0.6382, 1e-3)) * taper
            v_rad = -wp_intensity * float(wp['max_suction_mps']) * (2.0 * xi / (1.0 + xi * xi)) * taper
            w_down = -wp_intensity * (0.45 * float(wp['max_suction_mps'])) * np.exp(-(xi * xi)) * taper

            er_x = dx_v / r_safe
            er_y = dy_v / r_safe
            et_x = -er_y
            et_y = er_x
            v_theta = np.where(r_v > 0.05, v_theta, 0.0)
            v_rad = np.where(r_v > 0.05, v_rad, 0.0)
            ux_v = v_theta * et_x + v_rad * er_x
            uy_v = v_theta * et_y + v_rad * er_y
            vel[..., 0] = vel[..., 0] + ux_v
            vel[..., 1] = vel[..., 1] + uy_v
            vel[..., 2] = vel[..., 2] + w_down

            # Analytical spatial slope for funnel depression
            d_eta_dr = eta_wp * (-r_v / (r_f * r_f))
            dhdx_tot = dhdx_tot + np.where(r_v > 0.05, d_eta_dr * er_x, 0.0)
            dhdy_tot = dhdy_tot + np.where(r_v > 0.05, d_eta_dr * er_y, 0.0)
            has_slope = True

            # Centripetal fluid acceleration a_c = -v_theta^2 / r * e_r
            ac_mag = np.where(r_v > 0.2, -(v_theta * v_theta) / r_safe, 0.0)
            acc[..., 0] = acc[..., 0] + ac_mag * er_x
            acc[..., 1] = acc[..., 1] + ac_mag * er_y

            # Bernoulli dynamic pressure drop in high-swirl core
            p_dyn = p_dyn - 0.5 * rho_w * (v_theta * v_theta + v_rad * v_rad)

        # Rapids declared by the world (tidal races, river reaches): compactly supported current
        # jets, standing waves, eddy lines and rock wakes. Absent rapids leave this a no-op.
        rapids = getattr(self.world, 'rapids', ()) if getattr(self.config, 'rapids_enabled', True) else ()
        if rapids and xa.size > 0:
            from .rapids import rapids_overlay
            r_int = max(0.0, float(getattr(self.config, 'rapids_intensity', 1.0)))
            wet_w = np.clip((h_swe - 0.15) / 0.5, 0.0, 1.0)
            for rapid in rapids:
                r_eta, r_vel, r_acc, r_sx, r_sy = rapids_overlay(rapid, xa, ya, t_eval, eta_only=eta_only, intensity=r_int)
                eta_delta = eta_delta + r_eta * wet_w
                if eta_only:
                    continue
                vel = vel + r_vel * wet_w[..., None]
                acc = acc + r_acc * wet_w[..., None]
                dhdx_tot = dhdx_tot + r_sx * wet_w
                dhdy_tot = dhdy_tot + r_sy * wet_w
                has_slope = True

        eta_hybrid = np.where(
            h_swe > 1e-4,
            np.maximum(bed, eta_swe + eta_delta),
            bed,
        )
        depth_hybrid = np.maximum(0.0, eta_hybrid - bed)
        wet_frac = np.clip(depth_hybrid / 0.04, 0.0, 1.0)

        if eta_only:
            empty = np.empty(0, dtype=np.float64)
            return HybridWaterSample(
                eta=eta_hybrid,
                depth=depth_hybrid,
                normal=empty,
                velocity=empty,
                acceleration=empty,
                dynamic_pressure=empty,
                wet_fraction=wet_frac,
            )

        # Effective surface normal blends total free-surface slope in wet regions toward vertical when dry
        if not has_slope:
            norm = np.zeros(xa.shape + (3,), dtype=np.float64)
            norm[..., 2] = 1.0
        else:
            inv_n = 1.0 / np.sqrt(dhdx_tot * dhdx_tot + dhdy_tot * dhdy_tot + 1.0)
            norm = np.stack([-dhdx_tot * inv_n, -dhdy_tot * inv_n, inv_n], axis=-1)

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
        samp = self.evaluate(xg, yg, t=t, eta_only=True)
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
