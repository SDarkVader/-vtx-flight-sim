"""Meridian ward tracks, rooftop landing zones and missions, and the Lantern Race in the Needle narrows."""
import gzip
import json

import numpy as np

from .lantern_marina import LanternMarinaDistrict
from .mission_timing import MissionTiming
from .vaderland import PACK


def blend_meridian_road_transition(world):
    """Ease the surveyed grade break at Terrace 1 and Airfield North Access."""
    axis = np.linspace(-world.half, world.half, world.n)
    columns = np.flatnonzero(abs(axis) < 80.0)
    rows = np.flatnonzero(abs(axis - 640.0) < 125.0)
    # Two five-sample longitudinal passes need four extra rows at each end.
    start, stop = rows[0] - 4, rows[-1] + 5
    if start < 0 or stop > world.n:
        raise ValueError("Meridian road transition is outside the terrain grid")
    original = world.heights[start:stop, columns]
    curve = original
    for _ in range(2):
        curve = (curve[:-4] + 4 * curve[1:-3] + 6 * curve[2:-2] + 4 * curve[3:-1] + curve[4:]) / 16

    def taper(distance, inner, outer):
        fraction = np.clip((distance - inner) / (outer - inner), 0.0, 1.0)
        return 1 - (3 - 2 * fraction) * fraction**2

    weights = taper(abs(axis[rows] - 640.0), 65.0, 125.0)[:, None] * taper(abs(axis[columns]), 20.0, 80.0)
    world.heights[np.ix_(rows, columns)] += (curve - original[4:-4]) * weights


class RooftopQuarter(LanternMarinaDistrict):
    id = environment_key = 'vaderland-33'
    version = '33.1'
    label = 'Vaderland · Lantern Race and Meridian Rooftop Quarter'

    def __init__(self, seed=41031):
        super().__init__(seed)
        blend_meridian_road_transition(self)
        with gzip.open(PACK / 'rooftop-quarter-33.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        solids = design['solids']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids if o['kind'] == 'mesh')
        self.vaderland['routes'].extend(design['roads'])
        self.vaderland['neighbourhoods'] = design['neighbourhoods']
        self.vaderland['missions'] = design['missions']
        self.vaderland['brake_line'] = design['brake_line']
        self.timing = MissionTiming(self.timing.courses + design['circuits'], self.timing.air, design['missions'])
        self.vaderland['time_trials'].extend(
            dict(course=c['name'], zone='Meridian Wards', spawn=t['spawn'], length_m=c['length_m'])
            for c, t in zip(design['circuits'], design['neighbourhoods']['tracks']))
        self.vaderland['time_trials'].extend(
            dict(course=m['name'], zone=m['zone'], spawn=m['spawn'], length_m=m['length_m'], format='mission',
                 gates=len(m['steps']), tier=m['tier'], size=m['size'], brief=m['brief'])
            for m in design['missions'])
        self.vaderland['places'].append({'name': 'Meridian Rooftop Quarter', 'point': [-2100., 3900.]})
        race = design['lantern_race']
        # The harbour water and fleet read the rapid and the race lines from the harbour chart.
        self.harbour['rapids'] = [race['rapid']]
        self.harbour['races'] = race['races']
        self.vaderland['lantern_race'] = {k: v for k, v in race.items() if k not in ('rapid', 'races')}
        self.vaderland['places'].append({'name': 'Lantern Race', 'point': race['centre']})
