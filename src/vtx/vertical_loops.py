"""Cathedral proving loops with wheel-bearing geometry, connections and route maps."""
import gzip
import json

import numpy as np

from .meridian_yard import MeridianHandlingYard
from .vaderland import PACK


class CathedralVerticalLoops(MeridianHandlingYard):
    id = environment_key = 'vaderland-26'
    version = '26'
    label = 'Vaderland \u00b7 Cathedral Vertical Loops'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'vertical-loops-26.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        self.obstacles.extend(design['solids'])
        self._shells.extend((o, np.asarray(o['planes'])) for o in design['solids'])
        self.vaderland['routes'].extend(design['roads'])
        self.vaderland['vertical_loops'] = design['tracks']
        self.vaderland['places'].extend(
            {'name': track['name'] + ' entrance', 'point': track['entry']}
            for track in design['tracks']
        )