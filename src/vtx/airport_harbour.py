"""Main Airport harbour survey. Local chart coordinates are east and south in metres."""

from functools import lru_cache
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


SURVEY = Path(__file__).resolve().parents[2] / "inputs" / "main_airport_harbour.json"
BANK_WIDTH = 100.0


@lru_cache(maxsize=1)
def survey():
    return json.loads(SURVEY.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def shoreline():
    layout = survey()["layout"]
    rings = [layout["outer"], *(island["ring"] for island in layout["islands"])]
    starts = np.concatenate(rings)
    ends = np.concatenate([np.roll(ring, -1, axis=0) for ring in rings])
    low = np.minimum(starts, ends)
    high = np.maximum(starts, ends)
    return starts, ends, low, high


def water_mask(east, north):
    """Even-odd polygon membership, including all island holes."""
    ox, oy = survey()["origin"]
    lx, ly = np.broadcast_arrays(np.asarray(east) - ox, oy - np.asarray(north))
    x, y = lx.ravel(), ly.ravel()
    starts, ends, low, high = shoreline()
    wet = np.zeros(x.size, dtype=bool)
    if x.size:
        relevant = np.flatnonzero(
            (high[:, 1] > y.min())
            & (low[:, 1] <= y.max())
            & (high[:, 0] > x.min())
            & (starts[:, 1] != ends[:, 1])
        )
        for i in relevant:
            ax, ay = starts[i]
            bx, by = ends[i]
            wet ^= ((ay > y) != (by > y)) & (x < ax + (y - ay) * (bx - ax) / (by - ay))
    return wet.reshape(lx.shape)


@lru_cache(maxsize=4)
def _bank_samples(n, half, corridor):
    chart = survey()
    ox, oy = chart["origin"]
    axis = np.linspace(-half, half, n)
    east, north = np.meshgrid(axis, axis)
    within = (
        (east >= ox - BANK_WIDTH)
        & (east <= ox + chart["layout"]["width"] + BANK_WIDTH)
        & (north < -corridor)
        & (north >= oy - chart["layout"]["height"] - BANK_WIDTH)
    )
    x, y = east[within], north[within]
    starts, ends, _, _ = shoreline()
    samples = []
    for a, b in zip(starts, ends):
        count = max(1, int(np.ceil(np.linalg.norm(b - a) / 2)))
        samples.append(np.linspace(a, b, count, endpoint=False))
    distance = cKDTree(np.concatenate(samples)).query(np.column_stack((x - ox, oy - y)))[0]
    apron = np.clip((-y - corridor) / 38.0, 0.0, 1.0)
    return within, water_mask(x, y), distance, apron * apron * (3 - 2 * apron)


def carve_basin(world):
    """Grade only the basin and its 100 m banks on the actual collision grid."""
    within, wet, distance, apron = _bank_samples(
        world.n, world.half, world.approach_corridor["flat_half_width_m"]
    )
    original = world.heights[within]
    level = survey()["waterLevelM"]
    t = np.clip(distance / BANK_WIDTH, 0.0, 1.0)
    blend = t * t * (3.0 - 2.0 * t)
    shore = level + np.minimum(distance * 0.09, 4.0)
    bank = np.where(distance < BANK_WIDTH, shore * (1 - blend) + original * blend, original)
    bed = level - 6.0 * np.tanh(distance / 36.0)
    world.heights[within] = original + (np.where(wet, bed, bank) - original) * apron


def footprint_over_water(world, x, y, radius):
    """Check polygon and aircraft footprint against the surrounding heightfield cells."""
    chart = world.harbour
    ox, oy = chart["origin"]
    p = np.array([x - ox, oy - y])
    if not (
        -radius <= p[0] <= chart["layout"]["width"] + radius
        and -radius <= p[1] <= chart["layout"]["height"] + radius
    ):
        return False
    if not water_mask(x, y):
        starts, ends, low, high = shoreline()
        nearby = np.all((low <= p + radius) & (high >= p - radius), axis=1)
        if not nearby.any():
            return False
        a = starts[nearby]
        ab = ends[nearby] - a
        length2 = np.sum(ab * ab, axis=1)
        t = np.clip(np.sum((p - a) * ab, axis=1) / np.maximum(length2, 1e-16), 0.0, 1.0)
        if np.min(np.linalg.norm(a + t[:, None] * ab - p, axis=1)) > radius:
            return False
    step = 2.0 * world.half / (world.n - 1)
    point = np.array([x, y]) + world.half
    i0, j0 = np.maximum(0, np.floor((point - radius) / step).astype(int))
    i1, j1 = np.minimum(world.n - 1, np.ceil((point + radius) / step).astype(int))
    return float(world.heights[j0 : j1 + 1, i0 : i1 + 1].min()) < chart["waterLevelM"]
