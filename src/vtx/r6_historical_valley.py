"""Recovered 3 November R6 valley, not the later extended sandbox.

This is a separately identified world definition for a historical experiment.
It reproduces the recorded terrain and obstacles but does not select an aircraft
or itself remove the later boundary floor.
"""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from .world import TestWorld

R6_HISTORICAL_VARIANT = 'r6-argon-20261103'
R6_HISTORICAL_ENVIRONMENT = 'r6-valley-20261103'
_RECORDED_SEED = 41031
_GEOMETRY = Path(__file__).resolve().parents[2] / 'inputs/r6_historical_valley_20261103.npz'


@lru_cache(maxsize=1)
def _recorded_geometry():
    # These are the recovered world's original binary64 values, not a new
    # generation of its sin/cos recipe through the current platform's libm.
    with np.load(_GEOMETRY, allow_pickle=False) as archive:
        heights = archive['heights']
        obstacles = archive['obstacles_json'].tobytes()
    if (heights.shape != (101, 101) or heights.dtype != np.dtype('<f8') or
        hashlib.sha256(heights.tobytes()).hexdigest() != 'de71fbb67da06357b1f92bd2fdc6c78a6c66f22cb06d3553382bd271653bb32e' or
        hashlib.sha256(obstacles).hexdigest() != 'd2403b2dad7eee42c6b9d7a737b755c0d2464ddde2074651b69e8a004f6d9776'):
        raise ValueError('Historical R6 geometry differs from the original recorded world')
    heights.setflags(write=False)
    return heights, obstacles


class R6HistoricalValley(TestWorld):
    __test__ = False
    # Retain the recorded id/version for evidence, while distinguishing this
    # world from the newer sandbox through its unique environment key.
    id = 'stage1-valley'
    version = '2'
    environment_key = R6_HISTORICAL_ENVIRONMENT
    label = 'Historical R6 valley · 3 November 2026'
    half = 500.
    n = 101
    default_departure = [0., 0.]
    default_destination = [-50., 20.]

    def __init__(self, seed=41031):
        self.seed = seed
        heights, obstacles = _recorded_geometry()
        self.heights = heights.copy()
        self.obstacles = json.loads(obstacles)
        self.water = dict(x=-265.,y=30.,half_x=28.,half_y=80.)
        rng = np.random.default_rng(seed)
        if isinstance(seed, (int, np.integer)) and int(seed) == _RECORDED_SEED:
            return
        # Explicit alternate seeds retain their existing obstacle-generation
        # behavior. The terrain itself never depended on the random seed.
        self.obstacles = [o for o in self.obstacles if o['kind'] == 'box']
        for i in range(36):
            angle = rng.uniform(0, 2 * math.pi); radius = rng.uniform(125, 210)
            cx, cy = radius * np.cos(angle), radius * np.sin(angle)
            if any(abs(cx-o['center'][0]) < o['half'][0]+12 and abs(cy-o['center'][1]) < o['half'][1]+12 for o in self.obstacles):
                continue
            height = float(rng.uniform(5, 13)); tree_radius = float(rng.uniform(.7, 1.6))
            self.obstacles.append(dict(id=f'tree-{i}',kind='cylinder',center=[float(cx),float(cy),height/2],
                half=[tree_radius,tree_radius,height/2],color='#536a55',landable=False))
