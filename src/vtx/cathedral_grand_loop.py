"""A separately versioned Cathedral Grand Loop on the existing Meridian world."""
import gzip
import json

import numpy as np

from .meridian_air_trials import MeridianAirTrials
from .vaderland import PACK


class CathedralGrandLoop(MeridianAirTrials):
    id = environment_key = 'vaderland-30'
    version = '30'
    label = 'Vaderland \u00b7 Cathedral Grand Loop'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'grand-loop-30.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        # Only replace the large loop's baked solids. Leave the compact loop,
        # road joins and all other districts in their previous order.
        retired = {o['id'] for o in self.obstacles if o['id'].startswith('vertical-loop-full-')}
        self.obstacles[:] = [o for o in self.obstacles if o['id'] not in retired]
        self.obstacles.extend(design['solids'])
        self._shells[:] = [(o, planes) for o, planes in self._shells if o['id'] not in retired]
        self._shells.extend((o, np.asarray(o['planes'])) for o in design['solids'])
        grand = design['track']
        self.vaderland['vertical_loops'] = [
            grand if t['id'] == grand['id'] else t for t in self.vaderland['vertical_loops']
        ]
        route = design['route']
        self.vaderland['routes'] = [
            route if r['name'] == route['name'] else r for r in self.vaderland['routes']
        ]
        self.vaderland['departure_presets'] = [
            {'name': 'Meridian \u00b7 Crest forecourt', 'point': [-218., 2268.]},
        ]
