"""Polygon-scoped shared water for the Airport harbour; no flight imports."""

from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import threading
import types
import numpy as np

from .water.shallow_water import HybridWaterField
from .water.datum import WaterEnvironmentConfig


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
                        half_extents=[float(np.linalg.norm(delta)) / 2, access["width"] / 2, 0.6],
                        yaw_deg=-np.degrees(np.arctan2(delta[1], delta[0])),
                        collidable=True,
                    )
                )
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
            json.dumps(meta, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
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
        x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        shape = x.shape
        origin = self.harbour["origin"]
        points = np.column_stack((x.ravel() - origin[0], origin[1] - y.ravel()))
        layout = self.harbour["layout"]
        wet = contains(points, layout["outer"])
        for island in layout["islands"]:
            ring = np.asarray(island["ring"])
            lo = ring.min(axis=0)
            hi = ring.max(axis=0)
            ids = np.flatnonzero(wet & np.all(points >= lo, axis=1) & np.all(points <= hi, axis=1))
            if len(ids):
                wet[ids] &= ~contains(points[ids], ring)
        return wet.reshape(shape)

    def terrain_z_array(self, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        u = np.clip((x + self.half) / (2 * self.half) * (self.n - 1), 0, self.n - 1.000001)
        v = np.clip((y + self.half) / (2 * self.half) * (self.n - 1), 0, self.n - 1.000001)
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
        super().__init__(world, config, swe_nx=world.n, swe_ny=world.n)
        xx, yy = np.meshgrid(self.shallow.xs, self.shallow.ys)
        self.grid_mask = world.mask(xx, yy)
        self.shallow.bed[~self.grid_mask] = float(config.water_level_m) + 20.0
        self.shallow._harbour_mask = self.grid_mask
        self.shallow.sample = types.MethodType(self._sample, self.shallow)
        self.reset(water_level_m=config.water_level_m)

    @staticmethod
    def _sample(s, x, y, eta_only=False):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        shape = x.shape
        fx = np.clip((x.ravel() + s.half_x) / s.dx, 0, s.nx - 1.000001)
        fy = np.clip((y.ravel() + s.half_y) / s.dy, 0, s.ny - 1.000001)
        ix = fx.astype(int)
        iy = fy.astype(int)
        tx = fx - ix
        ty = fy - iy
        ids = iy * s.nx + ix
        ids = np.stack((ids, ids + 1, ids + s.nx, ids + s.nx + 1), axis=1)
        weights = (
            np.stack(((1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty), axis=1)
            * s._harbour_mask.ravel()[ids]
        )
        weights /= np.maximum(weights.sum(axis=1)[:, None], 1e-12)
        interp = lambda a: np.sum(a.ravel()[ids] * weights, axis=1).reshape(shape)
        h = interp(s.h)
        eta = interp(s.bed + s.h)
        if eta_only:
            return eta, h, np.empty(0), np.empty(0)
        return (
            eta,
            h,
            np.where(h > s.h_vel_damp, interp(s.hu) / np.maximum(h, s.h_vel_damp), 0),
            np.where(h > s.h_vel_damp, interp(s.hv) / np.maximum(h, s.h_vel_damp), 0),
        )

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
            super().step(dt)
            self._enforce()

    def apply_for(self, vessel_id, **kwargs):
        with self._guard:
            super().apply_vessel_disturbance(**kwargs)
            self.wakes[vessel_id] = deepcopy(self._vessel_wake)
            self._vessel_wake = self._default_wake_state()
            self._enforce()

    def get_wake_state(self):
        return dict(vessels=deepcopy(self.wakes))

    def evaluate(self, x, y, z=None, t=None, *, eta_only=False):
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
                else -base.normal[..., :2] / np.maximum(base.normal[..., 2, None], 1e-12)
            )
            if self.config.wake_enabled:
                for wake in self.wakes.values():
                    if not wake.get("active"):
                        continue
                    self._vessel_wake = wake
                    sample = super().evaluate(x, y, z=z, t=t, eta_only=eta_only)
                    eta += sample.eta - base.eta
                    if not eta_only:
                        velocity += sample.velocity - base.velocity
                        acceleration += sample.acceleration - base.acceleration
                        pressure += sample.dynamic_pressure - base.dynamic_pressure
                        slope += -sample.normal[..., :2] / np.maximum(
                            sample.normal[..., 2, None], 1e-12
                        ) + base.normal[..., :2] / np.maximum(base.normal[..., 2, None], 1e-12)
            self._vessel_wake = self._default_wake_state()
            wet = self.world.mask(x, y)
            bed = self.world.terrain_z_array(x, y)
            eta = np.where(wet, np.maximum(eta, bed), bed)
            depth = np.where(wet, np.maximum(eta - bed, 0), 0)
            changes = dict(
                eta=eta, depth=depth, wet_fraction=np.where(wet, np.clip(depth / 0.04, 0, 1), 0)
            )
            if not eta_only:
                normal = np.concatenate((-slope, np.ones(slope.shape[:-1] + (1,))), axis=-1)
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
                schema="airport-harbour-water-v1",
                world_sha256=self.world.fingerprint,
                native=super().checkpoint_state(),
                wakes=deepcopy(self.wakes),
            )

    def restore_state(self, state):
        # Called only on a fresh unpublished fleet, never on an active instance.
        if (
            state.get("schema") != "airport-harbour-water-v1"
            or state.get("world_sha256") != self.world.fingerprint
        ):
            raise ValueError("Harbour water environment differs from saved state")
        json.dumps(state, allow_nan=False)
        native = state.get("native")
        wakes = state.get("wakes")
        if not isinstance(native, dict) or not isinstance(wakes, dict) or len(wakes) > 4:
            raise ValueError("Invalid harbour water checkpoint")
        for key in ("sim_time_s", "_swe_accum_s", "swe_step_interval_s"):
            value = native.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not np.isfinite(value)
                or value < 0
            ):
                raise ValueError("Invalid water clock " + key)
        if (
            native["swe_step_interval_s"] < 0.0025
            or native["_swe_accum_s"] >= native["swe_step_interval_s"] + 1e-9
        ):
            raise ValueError("Invalid water integration phase")
        shallow = native.get("shallow")
        if not isinstance(shallow, dict) or shallow.get("config") != native.get("config"):
            raise ValueError("Inconsistent shallow-water configuration")
        for key in ("t", "water_level_m", "initial_volume_m3", "_expected_volume_m3", "manning_n"):
            value = shallow.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not np.isfinite(value)
            ):
                raise ValueError("Invalid shallow-water scalar " + key)
        for key in ("h", "hu", "hv"):
            array = np.asarray(shallow.get(key), dtype=float)
            if array.shape != self.grid_mask.shape or not np.isfinite(array).all():
                raise ValueError("Invalid water array " + key)
            if np.any(array[~self.grid_mask] != 0) or (key == "h" and np.any(array < 0)):
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
