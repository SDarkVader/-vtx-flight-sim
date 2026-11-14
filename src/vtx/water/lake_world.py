"""Ricochet Lake: shared 2,000 m x 1,200 m physical freshwater testbed world.

Single source of truth for bathymetry, terrain elevation, shorelines,
harbour/marina structures, launch/recovery ramps, mooring buoys, and marked
test zones across MuJoCo rigid collision, shallow-water solver, hydrodynamics,
and Three.js rendering.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from vtx.mission_selection import MapPoint, SurfaceDecision
from vtx.water.datum import VERTICAL_DATUM, WATER_PHYSICS_REVISION


def _smoothstep(edge0: float, edge1: float, x: np.ndarray | float) -> np.ndarray | float:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _segment_distance(
    px: np.ndarray | float,
    py: np.ndarray | float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> np.ndarray | float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    t = np.clip((wx * vx + wy * vy) / max(denom, 1e-9), 0.0, 1.0)
    dx = px - (ax + t * vx)
    dy = py - (ay + t * vy)
    return np.hypot(dx, dy)


class RicochetLakeWorld:
    """2,000 m x 1,200 m freshwater lake test environment (MLD SI datum)."""

    id = 'ricochet-lake-testbed'
    version = '1'
    environment_key = 'ricochet_lake'
    label = 'Ricochet Lake'
    display_name = 'Ricochet Lake Testbed'
    half_x = 1000.0
    half_y = 600.0
    half = 1000.0
    nx = 401
    ny = 241
    dx = 5.0
    dy = 5.0
    default_departure = [0.0, 0.0]
    default_destination = [300.0, 0.0]
    water_level = 0.0
    water_physics_revision = WATER_PHYSICS_REVISION
    bathymetry_verified = True

    def __init__(self, seed: int = 41031):
        self.seed = int(seed)
        self.xs = np.linspace(-self.half_x, self.half_x, self.nx, dtype=np.float64)
        self.ys = np.linspace(-self.half_y, self.half_y, self.ny, dtype=np.float64)
        self.heights = self._build_bathymetry()
        self.z_min = float(np.min(self.heights))
        self.z_max = float(np.max(self.heights))
        self.obstacles: list[dict[str, Any]] = []
        self.structures = self._build_structures()
        self.buoys = self._build_buoys()
        self.zones = self._build_zones()
        self.ramps = self._build_ramps()
        self.spawn_points = self._build_spawn_points()

    def _build_bathymetry(self) -> np.ndarray:
        xg, yg = np.meshgrid(self.xs, self.ys)  # shape (ny, nx): row=Y, col=X

        # 1. Surrounding watershed rim rising gently inland up to +14 m
        # Normalized elliptical distance from lake core centered near (+40, +10)
        rx = (xg - 40.0) / 880.0
        ry = (yg - 10.0) / 510.0
        # Super-elliptical bowl so east/west open runs stay broad
        r_bowl = np.power(np.abs(rx) ** 3.2 + np.abs(ry) ** 3.2, 1.0 / 3.2)

        # Base depth: -13.0 m deep central basin tapering smoothly across shoreline
        basin_factor = 1.0 - _smoothstep(0.42, 0.94, r_bowl)
        shore_rise = _smoothstep(0.86, 1.24, r_bowl) * 14.0
        z = -13.0 * basin_factor + shore_rise

        # 2. Variable shoreline gradients & subtle deterministic natural bed relief
        rng = np.random.default_rng(self.seed)
        p1, p2, p3 = rng.uniform(0.0, 2.0 * math.pi, size=3)
        undulation = (
            0.35 * np.sin(0.011 * xg + 0.007 * yg + p1)
            + 0.22 * np.cos(0.019 * xg - 0.014 * yg + p2)
            + 0.14 * np.sin(0.031 * xg + 0.029 * yg + p3)
        )
        # Attenuate natural relief where engineered basins/ramps are placed
        z = z + undulation * (1.0 - 0.5 * _smoothstep(0.9, 1.15, r_bowl))

        # 3. Steep rocky bluff along North-East shore (y > +340, x > +150)
        ne_mask = _smoothstep(180.0, 320.0, xg) * _smoothstep(300.0, 440.0, yg)
        z = z + ne_mask * 5.5

        # 4. Gentle 1:28 dissipative beach for wave run-up/retreat along South-East
        beach_x = _smoothstep(60.0, 140.0, xg) * (1.0 - _smoothstep(520.0, 620.0, xg))
        beach_y = _smoothstep(-520.0, -450.0, yg) * (1.0 - _smoothstep(-280.0, -220.0, yg))
        beach_mask = beach_x * beach_y
        # Target uniform slope from -4.2 m at y=-280 up to +2.8 m at y=-476 (~1:28)
        beach_target = np.clip(-4.2 + (-280.0 - yg) / 28.0, -5.0, 3.2)
        z = z * (1.0 - beach_mask) + beach_target * beach_mask

        # 5. Graded North-West shallow-water test shelf (-0.6 m to -3.2 m)
        shelf_x = _smoothstep(-540.0, -470.0, xg) * (1.0 - _smoothstep(-220.0, -150.0, xg))
        shelf_y = _smoothstep(130.0, 190.0, yg) * (1.0 - _smoothstep(340.0, 400.0, yg))
        shelf_mask = shelf_x * shelf_y
        shelf_target = -0.65 - 2.4 * _smoothstep(360.0, 150.0, yg)
        z = z * (1.0 - shelf_mask) + shelf_target * shelf_mask

        # 6. Sheltered Harbour & Marina Basin (West side: x in [-855, -535], y in [-350, -85])
        harbour_x = _smoothstep(-875.0, -830.0, xg) * (1.0 - _smoothstep(-545.0, -505.0, xg))
        harbour_y = _smoothstep(-370.0, -330.0, yg) * (1.0 - _smoothstep(-95.0, -55.0, yg))
        harbour_mask = harbour_x * harbour_y
        z = z * (1.0 - harbour_mask) + (-4.2) * harbour_mask

        # Entrance fairway channel connecting marina (-535..-400, y in [-145, -75]) to open basin
        chan_x = _smoothstep(-565.0, -520.0, xg) * (1.0 - _smoothstep(-410.0, -350.0, xg))
        chan_y = np.exp(-0.5 * ((yg + 110.0) / 38.0) ** 2)
        chan_mask = chan_x * chan_y
        z = np.minimum(z, -4.5 * chan_mask + z * (1.0 - chan_mask))

        # 7. Rock/armored breakwater jetty sheltering marina from east lake waves
        # Crest height +2.3 m from (-510, -370) to (-505, -155), leaving entrance at y > -155
        d_bw = _segment_distance(xg, yg, -510.0, -370.0, -505.0, -155.0)
        bw_profile = 1.0 - _smoothstep(7.5, 22.0, d_bw)
        z = np.maximum(z, -4.2 + bw_profile * 6.5)

        # 8. Service Quay apron along West edge of marina (x <= -835, y in [-335, -140])
        quay_x = _smoothstep(-930.0, -895.0, xg) * (1.0 - _smoothstep(-842.0, -828.0, xg))
        quay_y = _smoothstep(-355.0, -330.0, yg) * (1.0 - _smoothstep(-155.0, -135.0, yg))
        quay_mask = quay_x * quay_y
        z = z * (1.0 - quay_mask) + 1.55 * quay_mask

        # 9. Primary Launch & Recovery Slipway Ramp (y=-110, x in [-890, -755], 1:12 slope)
        ramp1_y = 1.0 - _smoothstep(10.0, 18.0, np.abs(yg + 110.0))
        ramp1_x = _smoothstep(-905.0, -885.0, xg) * (1.0 - _smoothstep(-760.0, -735.0, xg))
        ramp1_mask = ramp1_x * ramp1_y
        # Waterline z=0 at x=-818 m, dry apron +3.0 m at x=-870 m, submerged toe -3.5 m at x=-765 m
        ramp1_z = np.clip((-818.0 - xg) / 14.0, -3.6, 3.2)
        z = z * (1.0 - ramp1_mask) + ramp1_z * ramp1_mask

        # 10. Secondary Recovery Slipway (South Marina: y=-350, x in [-855, -745])
        ramp2_y = 1.0 - _smoothstep(8.0, 15.0, np.abs(yg + 350.0))
        ramp2_x = _smoothstep(-875.0, -855.0, xg) * (1.0 - _smoothstep(-750.0, -730.0, xg))
        ramp2_mask = ramp2_x * ramp2_y
        ramp2_z = np.clip((-795.0 - xg) / 12.0, -3.4, 2.8)
        z = z * (1.0 - ramp2_mask) + ramp2_z * ramp2_mask

        # 11. Carve clean open-water acceleration lane (-350..+650, y in [-55,+55]) >= 10 m deep
        acc_x = _smoothstep(-380.0, -330.0, xg) * (1.0 - _smoothstep(630.0, 680.0, xg))
        acc_y = 1.0 - _smoothstep(45.0, 75.0, np.abs(yg))
        acc_mask = acc_x * acc_y
        z = np.minimum(z, -10.5 * acc_mask + z * (1.0 - acc_mask))

        return z.astype(np.float64)

    def terrain_z(self, x: float, y: float) -> float:
        """Exact MuJoCo-hfield-consistent piecewise-triangular terrain elevation at (x, y)."""
        fx = float(np.clip((x + self.half_x) / self.dx, 0.0, self.nx - 1.000001))
        fy = float(np.clip((y + self.half_y) / self.dy, 0.0, self.ny - 1.000001))
        ix = min(int(math.floor(fx)), self.nx - 2)
        iy = min(int(math.floor(fy)), self.ny - 2)
        tx = fx - ix
        ty = fy - iy
        z00 = float(self.heights[iy, ix])
        z10 = float(self.heights[iy, ix + 1])
        z01 = float(self.heights[iy + 1, ix])
        z11 = float(self.heights[iy + 1, ix + 1])
        # Matches MuJoCo / TestWorld triangle split diagonal
        if tx + ty <= 1.0:
            return z00 + tx * (z10 - z00) + ty * (z01 - z00)
        return z11 + (1.0 - tx) * (z01 - z11) + (1.0 - ty) * (z10 - z11)

    def terrain_z_array(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Vectorized piecewise-triangular terrain elevation matching terrain_z()."""
        fx = np.clip((x + self.half_x) / self.dx, 0.0, self.nx - 1.000001)
        fy = np.clip((y + self.half_y) / self.dy, 0.0, self.ny - 1.000001)
        ix = np.minimum(np.floor(fx).astype(np.intp), self.nx - 2)
        iy = np.minimum(np.floor(fy).astype(np.intp), self.ny - 2)
        tx = fx - ix
        ty = fy - iy
        z00 = self.heights[iy, ix]
        z10 = self.heights[iy, ix + 1]
        z01 = self.heights[iy + 1, ix]
        z11 = self.heights[iy + 1, ix + 1]
        lower = (tx + ty) <= 1.0
        val_lower = z00 + tx * (z10 - z00) + ty * (z01 - z00)
        val_upper = z11 + (1.0 - tx) * (z01 - z11) + (1.0 - ty) * (z10 - z11)
        return np.where(lower, val_lower, val_upper)

    def terrain_normal(self, x: float, y: float) -> np.ndarray:
        eps = 0.5
        dzdx = (self.terrain_z(x + eps, y) - self.terrain_z(x - eps, y)) / (2.0 * eps)
        dzdy = (self.terrain_z(x, y + eps) - self.terrain_z(x, y - eps)) / (2.0 * eps)
        n = np.array([-dzdx, -dzdy, 1.0], dtype=np.float64)
        return n / float(np.linalg.norm(n))

    def surface_z(self, x: float, y: float, water_level: float | None = None) -> float:
        wl = self.water_level if water_level is None else float(water_level)
        return max(self.terrain_z(x, y), wl)

    def water_depth(self, x: float, y: float, water_level: float | None = None) -> float:
        wl = self.water_level if water_level is None else float(water_level)
        return max(0.0, wl - self.terrain_z(x, y))

    def validate(self, point: MapPoint, purpose: str) -> SurfaceDecision:
        x, y = float(point.x_m), float(point.y_m)
        z = self.terrain_z(x, y)
        if abs(x) > self.half_x - 30.0 or abs(y) > self.half_y - 30.0:
            return SurfaceDecision(False, 'Point is outside Ricochet Lake boundary margin.', z)
        if purpose in ('spawn', 'water_test', 'marina'):
            if z > self.water_level - 0.45:
                return SurfaceDecision(False, 'Insufficient water depth for vessel flotation.', z)
            return SurfaceDecision(True, 'Navigable water surface inside Ricochet Lake.', z)
        if purpose in ('ramp', 'recovery'):
            return SurfaceDecision(True, 'Valid shoreline / slipway approach point.', z)
        if z > self.water_level + 0.05:
            return SurfaceDecision(True, 'Dry shoreline surface.', z)
        return SurfaceDecision(True, 'Valid water point inside Ricochet Lake.', z)

    def _build_structures(self) -> list[dict[str, Any]]:
        """Physical collidable and renderable marina, quay, pier, and breakwater structures."""
        return [
            {
                'id': 'service_quay_wall',
                'kind': 'quay',
                'label': 'Service Quay & crane apron',
                'center': [-845.0, -242.5, 0.25],
                'half_extents': [18.0, 95.0, 1.30],  # top at z=+1.55 m
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#646e78',
            },
            {
                'id': 'finger_pier_1',
                'kind': 'pier',
                'label': 'Docking Berth 1 / South Finger Pier',
                'center': [-802.0, -295.0, 0.70],
                'half_extents': [25.0, 1.8, 0.45],  # top at z=+1.15 m
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#8c6b48',
            },
            {
                'id': 'finger_pier_2',
                'kind': 'pier',
                'label': 'Docking Berth 2 / Center Finger Pier',
                'center': [-802.0, -245.0, 0.70],
                'half_extents': [25.0, 1.8, 0.45],
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#8c6b48',
            },
            {
                'id': 'finger_pier_3',
                'kind': 'pier',
                'label': 'Docking Berth 3 / North Finger Pier',
                'center': [-802.0, -195.0, 0.70],
                'half_extents': [25.0, 1.8, 0.45],
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#8c6b48',
            },
            {
                'id': 'harbour_headwalk',
                'kind': 'pier',
                'label': 'Marina Headwalk Pontoon',
                'center': [-824.0, -245.0, 0.70],
                'half_extents': [3.0, 62.0, 0.45],
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#785a3a',
            },
            {
                'id': 'breakwater_crest',
                'kind': 'breakwater',
                'label': 'East Marina Breakwater',
                'center': [-507.5, -262.5, 1.10],
                'half_extents': [8.0, 106.0, 1.25],  # top at +2.35 m
                'yaw_deg': -1.3,
                'collidable': True,
                'color': '#555b62',
            },
            {
                'id': 'breakwater_light_tower',
                'kind': 'beacon',
                'label': 'Breakwater Entrance Beacon',
                'center': [-505.0, -158.0, 3.6],
                'half_extents': [1.2, 1.2, 1.4],
                'yaw_deg': 0.0,
                'collidable': True,
                'color': '#d9534f',
            },
        ]

    def _build_buoys(self) -> list[dict[str, Any]]:
        """Physical mooring buoys & channel markers with bed anchor depths."""
        specs = [
            ('mooring_alpha', 'Mooring Buoy A (Harbour)', -645.0, -215.0, 0.85, '#f59e0b', 'mooring'),
            ('mooring_bravo', 'Mooring Buoy B (Harbour)', -645.0, -275.0, 0.85, '#f59e0b', 'mooring'),
            ('channel_port', 'Channel Marker Port', -450.0, -72.0, 0.75, '#ef4444', 'channel'),
            ('channel_stbd', 'Channel Marker Stbd', -450.0, -148.0, 0.75, '#10b981', 'channel'),
            ('lane_start_n', 'Accel Lane Start N', -340.0, 52.0, 0.70, '#38bdf8', 'lane'),
            ('lane_start_s', 'Accel Lane Start S', -340.0, -52.0, 0.70, '#38bdf8', 'lane'),
            ('lane_end_n', 'Accel Lane End N', 620.0, 52.0, 0.70, '#38bdf8', 'lane'),
            ('lane_end_s', 'Accel Lane End S', 620.0, -52.0, 0.70, '#38bdf8', 'lane'),
            ('turning_center', 'Turning Basin Pivot Buoy', 480.0, 180.0, 0.90, '#eab308', 'turning'),
            ('shallow_zone_marker', 'Shallow Shelf Marker', -340.0, 235.0, 0.75, '#f97316', 'shallow'),
        ]
        out = []
        for bid, label, bx, by, radius, color, kind in specs:
            out.append({
                'id': bid,
                'label': label,
                'x': float(bx),
                'y': float(by),
                'z_bed': self.terrain_z(bx, by),
                'radius_m': float(radius),
                'height_m': 1.4,
                'kind': kind,
                'color': color,
                'collidable': True,
            })
        return out

    def _build_ramps(self) -> list[dict[str, Any]]:
        return [
            {
                'id': 'primary_slipway',
                'label': 'North Marina Launch & Recovery Ramp (1:14)',
                'x_dry': -870.0,
                'x_waterline': -818.0,
                'x_toe': -765.0,
                'y_center': -110.0,
                'width_m': 20.0,
                'slope_ratio': 1.0 / 14.0,
            },
            {
                'id': 'south_slipway',
                'label': 'South Harbour Recovery Ramp (1:12)',
                'x_dry': -840.0,
                'x_waterline': -795.0,
                'x_toe': -755.0,
                'y_center': -350.0,
                'width_m': 16.0,
                'slope_ratio': 1.0 / 12.0,
            },
        ]

    def _build_zones(self) -> list[dict[str, Any]]:
        return [
            {
                'id': 'deep_basin',
                'name': 'Deep Central Basin',
                'kind': 'ellipse',
                'cx': 60.0,
                'cy': 0.0,
                'rx': 380.0,
                'ry': 210.0,
                'color': '#0ea5e9',
                'nominal_depth_m': 13.0,
            },
            {
                'id': 'acceleration_lane',
                'name': 'Open-Water Acceleration Lane (960 m)',
                'kind': 'rect',
                'x_min': -340.0,
                'x_max': 620.0,
                'y_min': -45.0,
                'y_max': 45.0,
                'color': '#22c55e',
                'nominal_depth_m': 11.5,
            },
            {
                'id': 'turning_basin',
                'name': 'Open-Water Turning Circle (R=170 m)',
                'kind': 'circle',
                'cx': 480.0,
                'cy': 180.0,
                'r': 170.0,
                'color': '#eab308',
                'nominal_depth_m': 11.0,
            },
            {
                'id': 'shallow_shelf',
                'name': 'Graded Shallow-Water Shelf (-0.6 to -3.1 m)',
                'kind': 'rect',
                'x_min': -490.0,
                'x_max': -200.0,
                'y_min': 160.0,
                'y_max': 360.0,
                'color': '#f97316',
                'nominal_depth_m': 1.8,
            },
            {
                'id': 'runup_beach',
                'name': 'Wave Run-up & Wet/Dry Shoreline (1:28)',
                'kind': 'rect',
                'x_min': 120.0,
                'x_max': 540.0,
                'y_min': -490.0,
                'y_max': -280.0,
                'color': '#ec4899',
                'nominal_depth_m': 2.0,
            },
            {
                'id': 'sheltered_marina',
                'name': 'Sheltered Marina & Breakwater Basin',
                'kind': 'rect',
                'x_min': -835.0,
                'x_max': -520.0,
                'y_min': -345.0,
                'y_max': -95.0,
                'color': '#38bdf8',
                'nominal_depth_m': 4.2,
            },
        ]

    def _build_spawn_points(self) -> dict[str, dict[str, float]]:
        return {
            'open_water': {'x': 0.0, 'y': 0.0, 'z_offset': 0.05, 'yaw_deg': 0.0},
            'accel_start': {'x': -320.0, 'y': 0.0, 'z_offset': 0.05, 'yaw_deg': 0.0},
            'turning_entry': {'x': 310.0, 'y': 180.0, 'z_offset': 0.05, 'yaw_deg': 0.0},
            'shallow_shelf': {'x': -340.0, 'y': 260.0, 'z_offset': 0.05, 'yaw_deg': 0.0},
            'marina_berth_2': {'x': -772.0, 'y': -220.0, 'z_offset': 0.05, 'yaw_deg': 0.0},
            'ramp_approach': {'x': -780.0, 'y': -110.0, 'z_offset': 0.05, 'yaw_deg': 180.0},
        }

    def public(self) -> dict[str, Any]:
        h_list = np.round(self.heights, 3).tolist()
        return {
            'id': self.id,
            'version': self.version,
            'environment': self.environment_key,
            'label': self.label,
            'display_name': self.display_name,
            'seed': self.seed,
            'half': self.half,
            'half_m': self.half,
            'half_x': self.half_x,
            'half_y': self.half_y,
            'n': self.nx,
            'nx': self.nx,
            'ny': self.ny,
            'dx': self.dx,
            'dy': self.dy,
            'z_min': self.z_min,
            'z_max': self.z_max,
            'default_departure': list(self.default_departure),
            'default_destination': list(self.default_destination),
            'water_level': self.water_level,
            'water_physics_revision': self.water_physics_revision,
            'bathymetry_verified': self.bathymetry_verified,
            'vertical_datum': VERTICAL_DATUM,
            'heights': h_list,
            'heights_m': h_list,
            'obstacles': self.obstacles,
            'structures': self.structures,
            'buoys': self.buoys,
            'ramps': self.ramps,
            'zones': self.zones,
            'spawn_points': self.spawn_points,
            'scale_m': 100,
        }
