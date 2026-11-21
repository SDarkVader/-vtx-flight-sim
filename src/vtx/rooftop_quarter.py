"""Meridian ward tracks, rooftop landing zones and missions, and the Lantern Race in the Needle narrows."""
import gzip
import json

import numpy as np

from .lantern_marina import LanternMarinaDistrict
from .mission_timing import MissionTiming
from .vaderland import PACK


class RooftopQuarter(LanternMarinaDistrict):
    id = environment_key = 'vaderland-33'
    version = '33'
    label = 'Vaderland · Meridian Rooftop Quarter'

    def __init__(self, seed=41031):
        super().__init__(seed)
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
