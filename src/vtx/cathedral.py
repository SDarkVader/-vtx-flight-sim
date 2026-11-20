"""Cathedral of Velocity. Tested course geometry is independent of the vehicle."""
import gzip
import json

import numpy as np

from .course_timing import CourseTiming
from .meridian_parallax import ParallaxInstrumentRoom
from .vaderland import PACK


class CathedralOfVelocity(ParallaxInstrumentRoom):
    id = environment_key = 'vaderland-22'
    version = '22'
    label = 'Vaderland \u00b7 Cathedral of Velocity'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'cathedral-22.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        course = design['course']
        solids = design['solids']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids)
        self.vaderland['routes'].extend(course['links'])
        self.vaderland['cathedral'] = {**design['visual'], **course}
        self.timing = CourseTiming([*self.timing.courses, course['timing']])
        self.vaderland['places'].extend([
            {'name': 'Cathedral west portal', 'point': design['visual']['portal_origin'][:2]},
            {'name': 'Cathedral of Velocity start', 'point': course['timing']['gates'][0]['center'][:2]},
        ])


class CathedralRaceApproach(CathedralOfVelocity):
    id = environment_key = 'vaderland-24'
    version = '24'
    label = 'Vaderland \u00b7 Cathedral West Approach'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'cathedral-approach-24.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        solids = design['solids']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids)
        approach = design['approach']
        self.vaderland['cathedral']['west_approach'] = approach
        self.vaderland['places'].append({'name':'Cathedral west gantry','point':approach['sign'][:2]})
