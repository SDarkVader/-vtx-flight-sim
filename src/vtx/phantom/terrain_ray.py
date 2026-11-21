"""Ray queries for the large, unrotated Vaderland heightfield."""

import numpy as np
import mujoco as mj
from scipy.spatial import cKDTree


GROUND_GROUP = np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8)
_GEOM = mj.mjtGeom


def _dot(x, y, z, v):
    return x * v[0] + y * v[1] + z * v[2]


class TerrainRay:
    """Use a bounded heightfield search when it can prove an interior first hit."""

    @classmethod
    def build(cls, model, data, terrain):
        heightfield = model.geom_dataid[terrain]
        half_x, half_y, height, _ = model.hfield_size[heightfield]
        rows, cols = model.hfield_nrow[heightfield], model.hfield_ncol[heightfield]
        dx = 2 * half_x / (cols - 1)
        dy = 2 * half_y / (rows - 1)
        geoms = np.flatnonzero(model.geom_group <= 0)
        types = model.geom_type[geoms]
        allowed = [_GEOM.mjGEOM_HFIELD, _GEOM.mjGEOM_PLANE, _GEOM.mjGEOM_SPHERE,
                   _GEOM.mjGEOM_CAPSULE, _GEOM.mjGEOM_ELLIPSOID, _GEOM.mjGEOM_CYLINDER,
                   _GEOM.mjGEOM_BOX, _GEOM.mjGEOM_MESH]
        if (half_x != half_y or rows != cols or dx != dy or dx < 1
                or dx != int(dx) or half_x != int(half_x)
                or terrain not in geoms or model.geom_bodyid[terrain] != 0
                or model.geom_matid[terrain] != -1 or model.geom_rgba[terrain, 3] == 0
                or not np.array_equal(data.geom_xpos[terrain], [0, 0, 0])
                or not np.array_equal(data.geom_xmat[terrain], np.eye(3).ravel())
                or np.count_nonzero(types == _GEOM.mjGEOM_HFIELD) != 1
                or not np.isin(types, allowed).all()):
            return None
        start = model.hfield_adr[heightfield]
        surface = model.hfield_data[start:start + rows * cols].astype(np.float64).reshape(rows, cols) * height
        return cls(model, data, terrain, geoms, types, surface, half_x, height, dx)

    def __init__(self, model, data, terrain, geoms, types, surface, half, height, spacing):
        self.model = model
        self.data = data
        self.terrain = terrain
        self.surface = surface
        self.half = half
        self.height = height
        self.spacing = spacing
        self.cells = surface.shape[0] - 1
        self.columns = np.arange(97)
        self.adjacent = np.array([-1, 0, 1])
        self.planes = geoms[types == _GEOM.mjGEOM_PLANE]
        solids = geoms[(types != _GEOM.mjGEOM_PLANE) & (geoms != terrain)]
        self.static = solids[model.geom_bodyid[solids] == 0]
        self.moving = solids[model.geom_bodyid[solids] != 0]
        self.centers = data.geom_xpos[self.static].copy()
        self.tree = cKDTree(self.centers)
        self.max_radius = model.geom_rbound[self.static].max(initial=0)

    @staticmethod
    def suitable(point, direction):
        dx, dy, dz = direction
        wide = max(abs(dx), abs(dy))
        return (0 < point[2] and abs(dz) <= .16 * wide
                and min(abs(dx), abs(dy)) > .07 * wide)

    def _interior_hit(self, p, v):
        size = self.spacing
        half = self.half
        # Keep edge and base intersections in the native routine.
        margin = 1e-6 * size
        if max(abs(p[0]), abs(p[1])) >= half - margin or not margin < p[2] < self.height - margin:
            return None
        axis = int(abs(v[1]) > abs(v[0]))
        across = 1 - axis
        direction = 1 if v[axis] > 0 else -1
        start = int((p[axis] + half) / size)
        major = start + self.columns * direction
        center_t = ((major + .5) * size - half - p[axis]) / v[axis]
        minor = np.floor((p[across] + center_t * v[across] + half) / size).astype(int)
        minor = (minor[:, None] + self.adjacent).ravel()
        major = np.repeat(major, len(self.adjacent))
        col, row = (minor, major) if axis else (major, minor)
        inside = (col >= 0) & (col < self.cells) & (row >= 0) & (row < self.cells)
        col, row = col[inside], row[inside]
        x, y = col * size - half, row * size - half

        # MuJoCo splits each cell from lower left to upper right. The two
        # triangle planes use the same vertex order and float64 arithmetic.
        h = self.surface
        low = h[row, col]
        right = h[row, col + 1]
        high = h[row + 1, col + 1]
        left = h[row + 1, col]
        nx = np.stack(((-size) * (right - high) - (low - high) * (-size),
                       (-size) * (high - left)))
        ny = np.stack((size * (right - high), size * (low - left)))
        nz = size * size
        denom = _dot(nx, ny, nz, v)
        x2 = np.stack((x + size, x))
        z2 = np.stack((high, left))
        numerator = (p[0] - x2) * nx + (p[1] - (y + size)) * ny + (p[2] - z2) * nz
        with np.errstate(divide='ignore', invalid='ignore'):
            t = -numerator / denom
            u = (p[0] - x) + t * v[0]
            w = (p[1] - y) + t * v[1]
            diagonal = np.stack((u[0] - w[0], w[1] - u[1]))
        hits = ((t >= 0) & (u >= -margin) & (u <= size + margin)
                & (w >= -margin) & (w <= size + margin) & (diagonal >= -margin))
        distances = np.where(hits, t, np.inf)
        nearest = np.unravel_index(np.argmin(distances), distances.shape)
        distance = distances[nearest]
        if not np.isfinite(distance):
            return None
        # Use the native test at cell seams, shallow contacts and past the
        # scanned columns, where the local search cannot certify the result.
        last_edge = (major[-1] + (direction > 0)) * size - half
        limit = (last_edge - p[axis]) / v[axis]
        endpoint = p + distance * v
        if (distance >= limit - margin or max(abs(endpoint[0]), abs(endpoint[1])) >= half - margin
                or not margin < endpoint[2] < self.height - margin
                or min(u[nearest], size-u[nearest], w[nearest], size-w[nearest], diagonal[nearest]) <= margin
                or abs(denom[nearest]) <= 1e-6 * (abs(nx[nearest]) + abs(ny[nearest]) + nz)):
            return None
        return float(distance)

    def hit(self, point, direction):
        distance = self._interior_hit(point, direction)
        if distance is None:
            return None
        # Broad-phase bounds only. The nearest eligible scenery surface
        # still comes from the original MuJoCo intersection functions.
        model, data = self.model, self.data
        end = point + direction * distance
        center = (point + end) * .5
        radius = .5 * np.linalg.norm(end - point) + self.max_radius + 1e-6
        nearby = self.static[self.tree.query_ball_point(center, radius)]
        finite = np.concatenate((nearby, self.moving))
        offset = data.geom_xpos[finite] - point
        along = np.clip((offset @ direction) / (direction @ direction), 0, distance)
        residual = offset - along[:, None] * direction
        within = np.einsum('ij,ij->i', residual, residual) <= (model.geom_rbound[finite] + 1e-6) ** 2
        found = self.terrain
        for gid in np.sort(np.concatenate((self.planes, finite[within]))):
            material = model.geom_matid[gid]
            opacity = model.geom_rgba[gid, 3] if material < 0 else model.mat_rgba[material, 3]
            if opacity == 0:
                continue
            kind = model.geom_type[gid]
            if kind == _GEOM.mjGEOM_MESH:
                hit = mj.mj_rayMesh(model, data, gid, point, direction)
            else:
                hit = mj.mju_rayGeom(data.geom_xpos[gid], data.geom_xmat[gid],
                                    model.geom_size[gid], point, direction, kind)
            if hit >= 0 and (hit < distance or (hit == distance and gid < found)):
                distance, found = hit, int(gid)
        return distance, found
