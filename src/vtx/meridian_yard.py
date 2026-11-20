"""Connected ground handling area inside the surveyed Meridian road network."""
import gzip
import json

import numpy as np

from .cathedral import CathedralRaceApproach
from .course_timing import CourseTiming
from .vaderland import PACK


class MeridianHandlingYard(CathedralRaceApproach):
    id = environment_key = 'vaderland-25'
    version = '25'
    label = 'Vaderland \u00b7 Meridian Handling Yard'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'meridian-yard-25.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        yard=design['yard']
        self.obstacles.extend(design['solids'])
        self._shells.extend((o,np.asarray(o['planes'])) for o in design['solids'])
        self.vaderland['routes'].extend(design['roads'])
        self.vaderland['meridian_yard']=yard
        self.vaderland['places'].extend([
            {'name':'Meridian Handling Yard','point':yard['point']},
            {'name':'Handling Yard entrance','point':yard['access']},
        ])
        self.timing=CourseTiming([*self.timing.courses,*yard['courses']])
