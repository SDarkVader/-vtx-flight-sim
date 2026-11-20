"""Crest Gardens and district-specific weather on a separate Vaderland revision."""
import json

import numpy as np

from .cathedral_grand_loop import CathedralGrandLoop
from .vaderland import PACK


class CrestGardensDistrict(CathedralGrandLoop):
    id = environment_key = 'vaderland-31'
    version = '31'
    label = 'Vaderland \u00b7 Meridian Crest Gardens'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with (PACK / 'crest-gardens-31.json').open(encoding='utf-8') as file:
            garden = json.load(file)
        shapes = garden.pop('solids')
        self.obstacles.extend(shapes)
        self._shells.extend((shape, np.asarray(shape['planes'])) for shape in shapes)
        self.vaderland['crest_gardens'] = garden
        self.vaderland['places'].append({'name': 'Crest Gardens', 'point': garden['center']})
