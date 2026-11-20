"""Lantern Paddock, the quarry course and the timed-event starts across Vaderland."""
import gzip
import json

import numpy as np

from .course_timing import CourseTiming
from .vaderland import PACK
from .vertical_loops import CathedralVerticalLoops


class CathedralEastDistrict(CathedralVerticalLoops):
    id = environment_key = 'vaderland-27'
    version = '27'
    label = 'Vaderland \u00b7 Cathedral East Proving District'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'cathedral-east-27.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        for row, col, height in design['terrain']:
            self.heights[row, col] = height
        self.obstacles.extend(design['solids'])
        self._shells.extend((o, np.asarray(o['planes'])) for o in design['solids'])
        paddock = design['paddock']
        self.vaderland['cathedral_east'] = paddock
        self.vaderland['routes'].extend(design['roads'])
        self.vaderland['places'].extend([
            {'name': paddock['name'], 'point': paddock['point']},
            {'name': 'Lantern Quarry start', 'point': paddock['spawn']},
        ])
        self.timing = CourseTiming([*self.timing.courses, paddock['course']])
        courses = {c['name']: c for c in self.timing.courses}
        self.vaderland['time_trials'] = [
            {'course': name, 'zone': zone, 'spawn': point,
             'length_m': courses[name]['length_m']}
            for name, zone, point in (
                ('Lantern Quarry', 'Cathedral East', paddock['spawn']),
                ('Cathedral of Velocity', 'Lantern Gallery', [3057.45695, -3703.03794]),
                ('Night Velocity', 'Meridian City', [-10.76637, 2223.37585]),
                ('Handling Loop', 'Meridian Handling Yard', [1056., 2564.]),
                ('Precision Loop', 'Meridian Handling Yard', [1068., 2582.5]),
            )
        ]