"""Polygon-scoped shared water for the Airport harbour; no flight imports."""

from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import threading
import types
import numpy as np

from .water.shallow_water import HybridWaterField
from .water.datum import WaterEnvironmentConfig

SWE_INTERVAL_S = 0.1
DRY_HALO_CELLS = 3


def contains(points, ring):
    points = np.atleast_2d(points)
    ring = np.asarray(ring, dtype=float)
    inside = np.zeros(len(points), dtype=bool)
    if not len(points):
        return inside
    end = np.roll(ring, -1, axis=0)
    relevant = (np.maximum(ring[:, 1], end[:, 1]) > points[:, 1].min()) & (
        np.minimum(ring[:, 1], end[:, 1]) <= points[:, 1].max()
    )
    a = ring[relevant]
    b = end[relevant]
    for start in range(0, len(points), 512):
        p = points[start : start + 512]
        crosses = (a[None, :, 1] > p[:, None, 1]) != (b[None, :, 1] > p[:, None, 1])
        x = a[None, :, 0] + (b - a)[None, :, 0] * (p[:, None, 1] - a[None, :, 1]) / (
            (b - a)[None, :, 1] + 1e-100
        )
        inside[start : start + len(p)] = (
            np.count_nonzero(crosses & (p[:, None, 0] < x), axis=1) % 2 == 1
        )
    return inside


class HarbourWorld:
    """Read-only view of the same Airport heightfield, basin and structures."""

    def __init__(self, world):
        if not getattr(world, "harbour", None):
            raise ValueError("This environment has no declared harbour")
        self.source = world
        self.harbour = deepcopy(world.harbour)
        self.half = self.half_x = self.half_y = float(world.half)
        self.n = self.nx = self.ny = int(world.n)
        self.heights = np.asarray(world.heights, dtype=float).copy()
        self.z_min = float(self.heights.min())
        self.z_max = float(self.heights.max())
        self.id = str(world.id)
        self.environment_key = str(world.environment_key)
        self.obstacles = deepcopy(world.obstacles)
        self.buoys = []
        self.whirlpools = []
        self.rapids = deepcopy(self.harbour.get("rapids", []))
        self.structures = []
        docks = self.harbour["docks"]
        level = float(self.harbour["waterLevelM"])
        for pier in docks["piers"]:
            self.structures.append(
                dict(
                    id=pier["id"],
                    center=[*self.to_world(pier["center"]), level + 0.6],
                    half_extents=[pier["length"] / 2, pier["width"] / 2, 0.6],
                    yaw_deg=-np.degrees(pier["heading"]),
                    collidable=True,
                )
            )
        for access in docks.get("access", []):
            for i, (a, b) in enumerate(zip(access["points"], access["points"][1:])):
                a = np.asarray(a)
                b = np.asarray(b)
                delta = b - a
                self.structures.append(
                    dict(
                        id=f"{access['id']}-{i}",
                        center=[*self.to_world((a + b) / 2), level + 0.6],
                        half_extents=[
                            float(np.linalg.norm(delta)) / 2,
                            access["width"] / 2,
                            0.6,
                        ],
                        yaw_deg=-np.degrees(np.arctan2(delta[1], delta[0])),
                        collidable=True,
                    )
                )
        # Some land worlds provide a contact mesh for the existing dock chart.
        # Keep the chart's collider as the fleet's sole copy of that structure.
        dock_ids = {structure["id"] for structure in self.structures}
        self.obstacles = [obstacle for obstacle in self.obstacles if obstacle.get("harbour_structure") not in dock_ids]
        meta = dict(
            id=world.id,
            version=world.version,
            environment=world.environment_key,
            seed=world.seed,
            half=world.half,
            n=world.n,
            harbour=self.harbour,
            obstacles=self.obstacles,
        )
        digest = hashlib.sha256(
            json.dumps(
                meta, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        )
        digest.update(np.ascontiguousarray(self.heights, dtype="<f8").tobytes())
        self.fingerprint = digest.hexdigest()

    def to_world(self, point):
        origin = self.harbour["origin"]
        return [float(origin[0] + point[0]), float(origin[1] - point[1])]

    def mask(self, x, y):
        source_mask = getattr(self.source, "harbour_water_mask", None)
        if callable(source_mask):
            return np.asarray(source_mask(x, y), dtype=bool)
        x, y = np.broadcast_arrays(
            np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        )
        shape = x.shape
        origin = self.harbour["origin"]
        points = np.column_stack((x.ravel() - origin[0], origin[1] - y.ravel()))
        layout = self.harbour["layout"]
        wet = contains(points, layout["outer"])
        for island in layout["islands"]:
            ring = np.asarray(island["ring"])
            lo = ring.min(axis=0)
            hi = ring.max(axis=0)
            ids = np.flatnonzero(
                wet & np.all(points >= lo, axis=1) & np.all(points <= hi, axis=1)
            )
            if len(ids):
                wet[ids] &= ~contains(points[ids], ring)
        return wet.reshape(shape)

    def terrain_z_array(self, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        u = np.clip(
            (x + self.half) / (2 * self.half) * (self.n - 1), 0, self.n - 1.000001
        )
        v = np.clip(
            (y + self.half) / (2 * self.half) * (self.n - 1), 0, self.n - 1.000001
        )
        i = u.astype(int)
        j = v.astype(int)
        a = u - i
        b = v - j
        h = self.heights
        return np.where(
            a > b,
            (1 - a) * h[j, i] + (a - b) * h[j, i + 1] + b * h[j + 1, i + 1],
            (1 - b) * h[j, i] + (b - a) * h[j + 1, i] + a * h[j + 1, i + 1],
        )

    def terrain_z(self, x, y):
        return float(self.terrain_z_array(x, y))


class HarbourWater(HybridWaterField):
    """One SWE clock/domain, with an independent analytical wake per vessel."""

    def __init__(self, world, config):
        self._guard = threading.RLock()
        self.wakes = {}
        super().__init__(
            world,
            config,
            swe_nx=world.n,
            swe_ny=world.n,
            swe_step_interval_s=SWE_INTERVAL_S,
        )
        xx, yy = np.meshgrid(self.shallow.xs, self.shallow.ys)
        self.grid_mask = world.mask(xx, yy)
        self.shallow.bed[~self.grid_mask] = float(config.water_level_m) + 20.0
        self._crop_to_basin()
        self._repeated_basin = getattr(getattr(world, 'source', None), 'reuse_water_neighbourhoods', False)
        if self._repeated_basin:
            from .water.repeated_faces import RepeatedFaces
            self.shallow._advance_substep=RepeatedFaces(self.shallow)
        self.shallow._harbour_mask = self.grid_mask
        self.shallow.sample = types.MethodType(self._sample, self.shallow)
        self.shallow.apply_momentum_impulse = types.MethodType(
            self._impulse, self.shallow
        )
        self.reset(water_level_m=config.water_level_m)

    def _crop_to_basin(self):
        """Keep the original cell spacing/lattice and an inactive shore halo.

        The full Airport collision heightfield is unchanged. Only work on dry
        water cells far beyond the basin is removed from the marine solver.
        """
        s = self.shallow
        rows, columns = np.where(self.grid_mask)
        if not len(rows):
            raise ValueError("Harbour has no wet water-solver cells")
        global_nx, global_ny = s.nx, s.ny
        j0 = max(0, int(rows.min()) - DRY_HALO_CELLS)
        j1 = min(s.ny, int(rows.max()) + DRY_HALO_CELLS + 1)
        i0 = max(0, int(columns.min()) - DRY_HALO_CELLS)
        i1 = min(s.nx, int(columns.max()) + DRY_HALO_CELLS + 1)
        s._global_nx, s._global_ny = global_nx, global_ny
        s._global_half_x, s._global_half_y = s.half_x, s.half_y
        s._crop_i0, s._crop_j0 = i0, j0
        for key in ("h", "hu", "hv", "bed"):
            setattr(s, key, getattr(s, key)[j0:j1, i0:i1].copy())
        s.xs = s.xs[i0:i1].copy()
        s.ys = s.ys[j0:j1].copy()
        s.nx = i1 - i0
        s.ny = j1 - j0
        s.half_x = float((s.xs[-1] - s.xs[0]) / 2)
        s.half_y = float((s.ys[-1] - s.ys[0]) / 2)
        s.origin_x = float((s.xs[0] + s.xs[-1]) / 2)
        s.origin_y = float((s.ys[0] + s.ys[-1]) / 2)
        self.grid_mask = self.grid_mask[j0:j1, i0:i1].copy()
        self.grid_identity = dict(
            scheme="airport-global-lattice-crop-v1",
            global_shape=[global_ny, global_nx],
            global_half_m=[s._global_half_x, s._global_half_y],
            slice_start=[j0, i0],
            shape=[s.ny, s.nx],
            cell_spacing_m=[s.dx, s.dy],
            origin_xy_m=[s.origin_x, s.origin_y],
            bounds_m=[float(s.xs[0]), float(s.xs[-1]), float(s.ys[0]), float(s.ys[-1])],
            dry_halo_cells=DRY_HALO_CELLS,
        )

    @staticmethod
    def _sample(s, x, y, eta_only=False):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        shape = x.shape
        fx = np.clip((x.ravel() + s._global_half_x) / s.dx, 0, s._global_nx - 1.000001)
        fy = np.clip((y.ravel() + s._global_half_y) / s.dy, 0, s._global_ny - 1.000001)
        gx = fx.astype(int)
        gy = fy.astype(int)
        tx = fx - gx
        ty = fy - gy
        ix = gx - s._crop_i0
        iy = gy - s._crop_j0
        valid = (ix >= 0) & (ix < s.nx - 1) & (iy >= 0) & (iy < s.ny - 1)
        ix = np.clip(ix, 0, s.nx - 2)
        iy = np.clip(iy, 0, s.ny - 2)
        ids = iy * s.nx + ix
        ids = np.stack((ids, ids + 1, ids + s.nx, ids + s.nx + 1), axis=1)
        weights = (
            np.stack(
                ((1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty), axis=1
            )
            * s._harbour_mask.ravel()[ids]
            * valid[:, None]
        )
        weights /= np.maximum(weights.sum(axis=1)[:, None], 1e-12)
        interp = lambda a: np.sum(a.ravel()[ids] * weights, axis=1).reshape(shape)
        h = interp(s.h)
        # Gather first: exact same per-cell addition/reduction, without making
        # a whole-grid temporary for each small hull sample.
        eta = np.sum((s.bed.ravel()[ids] + s.h.ravel()[ids]) * weights, axis=1).reshape(
            shape
        )
        if eta_only:
            return eta, h, np.empty(0), np.empty(0)
        return (
            eta,
            h,
            np.where(h > s.h_vel_damp, interp(s.hu) / np.maximum(h, s.h_vel_damp), 0),
            np.where(h > s.h_vel_damp, interp(s.hv) / np.maximum(h, s.h_vel_damp), 0),
        )

    @staticmethod
    def _impulse(s, cx, cy, fx_n, fy_n, dt, radius_m=5.0):
        """Original PR momentum equation on the unchanged global cell lattice."""
        if (
            dt <= 0
            or not s.config.shallow_water_enabled
            or abs(fx_n) + abs(fy_n) < 1e-3
        ):
            return
        sigma = max(float(radius_m), 0.75 * max(s.dx, s.dy))
        span = 3 * sigma
        ix0 = max(
            0, int(math.floor((cx - span + s._global_half_x) / s.dx)) - s._crop_i0
        )
        ix1 = min(
            s.nx, int(math.ceil((cx + span + s._global_half_x) / s.dx)) + 1 - s._crop_i0
        )
        iy0 = max(
            0, int(math.floor((cy - span + s._global_half_y) / s.dy)) - s._crop_j0
        )
        iy1 = min(
            s.ny, int(math.ceil((cy + span + s._global_half_y) / s.dy)) + 1 - s._crop_j0
        )
        if ix1 <= ix0 or iy1 <= iy0:
            return
        h = s.h[iy0:iy1, ix0:ix1]
        wet = h > s.h_vel_damp
        if not np.any(wet):
            return
        xg, yg = np.meshgrid(s.xs[ix0:ix1], s.ys[iy0:iy1])
        r2 = ((xg - cx) ** 2 + (yg - cy) ** 2) / (sigma * sigma)
        weights = np.where(wet, np.exp(-0.5 * r2), 0.0)
        total = float(np.sum(weights))
        if total <= 1e-12:
            return
        rho = max(float(s.config.rho_water_kg_m3), 100.0)
        g = float(s.config.g_m_s2)
        scale = float(dt) / (rho * total * s.cell_area)
        hu = s.hu[iy0:iy1, ix0:ix1] + float(fx_n) * scale * weights
        hv = s.hv[iy0:iy1, ix0:ix1] + float(fy_n) * scale * weights
        max_q = np.where(
            wet, h * np.minimum(5.5, 0.55 * np.sqrt(g * np.maximum(h, 0.0))), 0.0
        )
        magnitude = np.hypot(hu, hv)
        cap = np.where(magnitude > max_q, max_q / np.maximum(magnitude, 1e-12), 1.0)
        s.hu[iy0:iy1, ix0:ix1] = np.where(wet, hu * cap, 0.0)
        s.hv[iy0:iy1, ix0:ix1] = np.where(wet, hv * cap, 0.0)
        s._state_version += 1

    def _enforce(self):
        if hasattr(self, "grid_mask"):
            for key in ("h", "hu", "hv"):
                getattr(self.shallow, key)[~self.grid_mask] = 0.0

    def reset(self, water_level_m=None):
        with self._guard:
            super().reset(water_level_m)
            self.wakes = {}
            self._enforce()

    def step(self, dt):
        with self._guard:
            previous=self.shallow.substep_count
            super().step(dt)
            # The original SWE intentionally skips advancement when disabled.
            # Retain a consistent scheduled clock without evolving its arrays.
            if not self.config.shallow_water_enabled:
                self.shallow.t = self.sim_time_s - self._swe_accum_s
            if not self._repeated_basin or self.shallow.substep_count!=previous:
                self._enforce()

    def apply_for(self, vessel_id, **kwargs):
        with self._guard:
            super().apply_vessel_disturbance(**kwargs)
            self.wakes[vessel_id] = deepcopy(self._vessel_wake)
            self._vessel_wake = self._default_wake_state()
            # The charted impulse writes only its local patch and explicitly zeros dry cells.
            if not self._repeated_basin:
                self._enforce()

    def get_wake_state(self):
        return dict(vessels=deepcopy(self.wakes))

    @staticmethod
    def _query_key(value):
        if value is None:
            return None
        array = np.asarray(value)
        return array.shape, array.dtype.str, array.tobytes()

    def _base_components(self, x, y, z, t, eta_only):
        cache = getattr(self, "_query_base_cache", None)
        if cache is None:
            return super()._base_components(x, y, z, t, eta_only)
        key = tuple(self._query_key(v) for v in (x, y, z, t)) + (eta_only,)
        if key not in cache:
            cache[key] = super()._base_components(x, y, z, t, eta_only)
        return cache[key]

    @staticmethod
    def _zero_wake_contribution(wake, x, y):
        # Exact upstream amplitude and strict support-box gates. The near-wake
        # equations and every individual shore clamp stay in the parent field.
        speed = float(wake["speed_mps"])
        draft = max(float(wake["draft_m"]), 0.15)
        amp_k = min(0.36, 0.032 * draft * speed * min(speed / 2.0, 1.0))
        amp_h = min(0.16, 0.055 * abs(float(wake["heave_rate_mps"]))) * min(
            draft / 0.25, 1.0
        )
        if not (amp_k > 1e-4 or amp_h > 1e-4):
            return True
        xa, ya = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        if not xa.size or not ya.size:
            return True
        wx, wy = float(wake["x"]), float(wake["y"])
        return bool(
            float(np.max(xa)) < wx - 115.0
            or float(np.min(xa)) > wx + 115.0
            or float(np.max(ya)) < wy - 115.0
            or float(np.min(ya)) > wy + 115.0
        )

    def evaluate(self, x, y, z=None, t=None, *, eta_only=False):
        # One frozen query only: configuration, water clock and arrays cannot
        # change under this guard. No cache survives a return or interruption.
        with self._guard:
            previous = getattr(self, "_query_base_cache", None)
            self._query_base_cache = {}
            try:
                return self._evaluate_scoped(x, y, z=z, t=t, eta_only=eta_only)
            finally:
                self._query_base_cache = previous

    def _evaluate_scoped(self, x, y, z=None, t=None, *, eta_only=False):
        with self._guard:
            self._vessel_wake = self._default_wake_state()
            base = super().evaluate(x, y, z=z, t=t, eta_only=eta_only)
            eta = base.eta.copy()
            velocity = base.velocity.copy()
            acceleration = base.acceleration.copy()
            pressure = base.dynamic_pressure.copy()
            slope = (
                None
                if eta_only
                else -base.normal[..., :2]
                / np.maximum(base.normal[..., 2, None], 1e-12)
            )
            if self.config.wake_enabled:
                for wake in self.wakes.values():
                    if not wake.get("active"):
                        continue
                    self._vessel_wake = wake
                    sample = (
                        base
                        if self._zero_wake_contribution(wake, x, y)
                        else super().evaluate(x, y, z=z, t=t, eta_only=eta_only)
                    )
                    eta += sample.eta - base.eta
                    if not eta_only:
                        velocity += sample.velocity - base.velocity
                        acceleration += sample.acceleration - base.acceleration
                        pressure += sample.dynamic_pressure - base.dynamic_pressure
                        slope += -sample.normal[..., :2] / np.maximum(
                            sample.normal[..., 2, None], 1e-12
                        ) + base.normal[..., :2] / np.maximum(
                            base.normal[..., 2, None], 1e-12
                        )
            self._vessel_wake = self._default_wake_state()
            wet = self.world.mask(x, y)
            bed = self._base_components(x, y, z, t, eta_only)[3]
            eta = np.where(wet, np.maximum(eta, bed), bed)
            depth = np.where(wet, np.maximum(eta - bed, 0), 0)
            changes = dict(
                eta=eta,
                depth=depth,
                wet_fraction=np.where(wet, np.clip(depth / 0.04, 0, 1), 0),
            )
            if not eta_only:
                normal = np.concatenate(
                    (-slope, np.ones(slope.shape[:-1] + (1,))), axis=-1
                )
                normal /= np.linalg.norm(normal, axis=-1)[..., None]
                changes.update(
                    normal=normal,
                    velocity=np.where(wet[..., None], velocity, 0),
                    acceleration=np.where(wet[..., None], acceleration, 0),
                    dynamic_pressure=np.where(wet, pressure, 0),
                )
            return replace(base, **changes)

    def checkpoint_state(self):
        with self._guard:
            return dict(
                schema="airport-harbour-water-v2",
                world_sha256=self.world.fingerprint,
                grid=deepcopy(self.grid_identity),
                native=super().checkpoint_state(),
                wakes=deepcopy(self.wakes),
            )

    def elevation_grid(self, nx=81, ny=49, t=None):
        """Publish actual world bounds for the offset water-solver domain."""
        if (
            type(nx) is not int
            or type(ny) is not int
            or not 2 <= nx <= 401
            or not 2 <= ny <= 401
        ):
            raise ValueError(
                "Harbour elevation grid dimensions must be integers from 2 to 401"
            )
        with self._guard:
            s = self.shallow
            xx, yy = np.meshgrid(
                np.linspace(s.xs[0], s.xs[-1], nx), np.linspace(s.ys[0], s.ys[-1], ny)
            )
            sample = self.evaluate(xx, yy, t=t, eta_only=True)
            return dict(
                t=self.sim_time_s if t is None else float(t),
                nx=nx,
                ny=ny,
                half_x=s.half_x,
                half_y=s.half_y,
                origin_xy_m=[s.origin_x, s.origin_y],
                bounds_m=deepcopy(self.grid_identity["bounds_m"]),
                water_level_m=float(self.config.water_level_m),
                eta=np.round(sample.eta, 3).tolist(),
                depth=np.round(sample.depth, 3).tolist(),
            )

    def restore_state(self, state):
        # Called only on a fresh unpublished fleet, never on an active instance.
        if (
            not isinstance(state, dict)
            or state.get("schema") != "airport-harbour-water-v2"
            or state.get("world_sha256") != self.world.fingerprint
        ):
            raise ValueError("Harbour water environment differs from saved state")
        if state.get("grid") != self.grid_identity:
            raise ValueError("Harbour water grid/dynamics differ from saved state")
        json.dumps(state, allow_nan=False)
        native = state.get("native")
        wakes = state.get("wakes")
        if (
            not isinstance(native, dict)
            or not isinstance(wakes, dict)
            or len(wakes) > 4
        ):
            raise ValueError("Invalid harbour water checkpoint")
        for key in ("sim_time_s", "_swe_accum_s", "swe_step_interval_s"):
            value = native.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not np.isfinite(value)
                or value < -1e-10
            ):
                raise ValueError("Invalid water clock " + key)
        if (
            abs(native["swe_step_interval_s"] - SWE_INTERVAL_S) > 1e-15
            or native["_swe_accum_s"] >= native["swe_step_interval_s"] + 1e-9
        ):
            raise ValueError("Invalid water integration phase")
        shallow = native.get("shallow")
        if not isinstance(shallow, dict) or shallow.get("config") != native.get(
            "config"
        ):
            raise ValueError("Inconsistent shallow-water configuration")
        for key in (
            "t",
            "water_level_m",
            "initial_volume_m3",
            "_expected_volume_m3",
            "manning_n",
        ):
            value = shallow.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not np.isfinite(value)
            ):
                raise ValueError("Invalid shallow-water scalar " + key)
        if abs(
            shallow["t"] + native["_swe_accum_s"] - native["sim_time_s"]
        ) > 1e-8 + 2e-9 * abs(native["sim_time_s"]):
            raise ValueError("Water checkpoint clock/phase mismatch")
        if (
            type(shallow.get("substep_count")) is not int
            or shallow["substep_count"] < 0
        ):
            raise ValueError("Invalid shallow-water integration counter")
        for key in ("h", "hu", "hv"):
            array = np.asarray(shallow.get(key), dtype=float)
            if array.shape != self.grid_mask.shape or not np.isfinite(array).all():
                raise ValueError("Invalid water array " + key)
            if np.any(array[~self.grid_mask] != 0) or (
                key == "h" and np.any(array < 0)
            ):
                raise ValueError("Checkpoint contains water outside its basin")
        default = self._default_wake_state()
        if native.get("_vessel_wake") != default:
            raise ValueError("Unexpected unowned analytical wake")
        for vessel_id, wake in wakes.items():
            if (
                not isinstance(vessel_id, str)
                or not isinstance(wake, dict)
                or set(wake) != set(default)
            ):
                raise ValueError("Invalid vessel wake identity or shape")
            if not isinstance(wake["active"], bool):
                raise ValueError("Invalid wake active flag")
            for key, value in wake.items():
                if key != "active" and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not np.isfinite(value)
                ):
                    raise ValueError("Invalid vessel wake " + key)
            if (
                wake["t_s"] > native["sim_time_s"] + 1e-9
                or wake["speed_mps"] < 0
                or wake["beam_m"] <= 0
                or wake["length_m"] <= 0
            ):
                raise ValueError("Invalid vessel wake values")
        with self._guard:
            super().restore_state(state["native"])
            self.wakes = deepcopy(state["wakes"])
            self._enforce()

    def reconfigure(self, payload):
        with self._guard:
            result = super().reconfigure(payload)
            self.shallow.bed[~self.grid_mask] = float(result.water_level_m) + 20.0
            self._enforce()
            return result
