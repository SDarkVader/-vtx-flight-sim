"""Dry-bank transport connection between Meridian Arrivals and Lantern Marina."""
import gzip
import json

import numpy as np

from .crest_gardens import CrestGardensDistrict
from .vaderland import PACK


class LanternMarinaDistrict(CrestGardensDistrict):
    id = environment_key = 'vaderland-32'
    version = '32'
    label = 'Vaderland \u00b7 Lantern Marina'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'lantern-marina-32.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        for row, col, height in design['terrain']:
            self.heights[row, col] = height
        retired = set(design['removed'])
        self.obstacles = [o for o in self.obstacles if o['id'] not in retired] + design['solids']
        self._shells = [(o, planes) for o, planes in self._shells if o['id'] not in retired]
        self._shells.extend((o, np.asarray(o['planes'])) for o in design['solids'] if o['kind']=='mesh')
        marina = design['marina']
        self.vaderland['lantern_marina'] = marina
        self.vaderland['routes'].extend(design['roads'])
        self.vaderland['places'].append({'name': 'Lantern Marina interchange', 'point': marina['center']})
        self.vaderland['departure_presets'].extend([
            {'name': 'Meridian Arrivals \u00b7 Shore Link', 'point': marina['approach']},
            {'name': 'Lantern Marina \u00b7 turnaround', 'point': marina['spawn']},
        ])
