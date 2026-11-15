"""Recovered 3 November R6 valley, not the later extended sandbox.

This is a separately identified world definition for a historical experiment.
It reproduces the recorded terrain and obstacles but does not select an aircraft
or itself remove the later boundary floor.
"""
import math
import numpy as np
from .world import TestWorld

R6_HISTORICAL_VARIANT = 'r6-argon-20261103'
R6_HISTORICAL_ENVIRONMENT = 'r6-valley-20261103'


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
        xs = np.linspace(-self.half, self.half, self.n)
        x, y = np.meshgrid(xs, xs)
        edge = np.clip((np.maximum(abs(x), abs(y)) - 220) / 240, 0, 1)
        edge = edge * edge * (3 - 2 * edge)
        self.heights = edge * (22 + 14 * np.sin(x / 81) ** 2 + 21 * np.cos(y / 107) ** 2)
        self.obstacles = [
            dict(id='hangar',kind='box',center=[85.,45.,9.],half=[23.,17.,9.],color='#606f7a',landable=True),
            dict(id='workshop',kind='box',center=[150.,-95.,5.],half=[23.,21.,5.],color='#627970',landable=True),
            dict(id='tower',kind='box',center=[115.,115.,29.],half=[9.,9.,29.],color='#71838a',landable=False),
            dict(id='freight',kind='box',center=[-100.,105.,4.],half=[18.,11.,4.],color='#ae735c',landable=True),
            dict(id='ridge-block',kind='box',center=[-175.,-110.,12.],half=[14.,30.,12.],color='#747b76',landable=False),
            dict(id='dispatch',kind='box',center=[45.,110.,12.],half=[14.,12.,12.],color='#355453',landable=True),
            dict(id='arcade',kind='box',center=[185.,45.,6.],half=[15.,11.,6.],color='#634e56',landable=True),
            dict(id='operations',kind='box',center=[50.,-145.,8.],half=[15.,12.,8.],color='#496c70',landable=True),
            dict(id='terminal',kind='box',center=[-145.,100.,7.],half=[15.,12.,7.],color='#725d50',landable=True),
        ]
        rng = np.random.default_rng(seed)
        for i in range(36):
            angle = rng.uniform(0, 2 * math.pi); radius = rng.uniform(125, 210)
            cx, cy = radius * np.cos(angle), radius * np.sin(angle)
            if any(abs(cx-o['center'][0]) < o['half'][0]+12 and abs(cy-o['center'][1]) < o['half'][1]+12 for o in self.obstacles):
                continue
            height = float(rng.uniform(5, 13)); tree_radius = float(rng.uniform(.7, 1.6))
            self.obstacles.append(dict(id=f'tree-{i}',kind='cylinder',center=[float(cx),float(cy),height/2],
                half=[tree_radius,tree_radius,height/2],color='#536a55',landable=False))
        self.water = dict(x=-265.,y=30.,half_x=28.,half_y=80.)
