"""Meridian Avenue's Parallax Exchange scenery revision."""
import gzip
import json

import numpy as np

from .vaderland import MeridianCityLights, PACK


class MeridianParallax(MeridianCityLights):
    id = environment_key = 'vaderland-19'
    version = '19'
    label = 'Vaderland \u00b7 Meridian Parallax'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'parallax-19.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        solids = design['solids']
        landmark = design['landmark']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids)
        self.vaderland['parallax'] = landmark
        self.vaderland['places'].append({'name': landmark['name'], 'point': landmark['point'][:2]})


class ParallaxCourt(MeridianParallax):
    id = environment_key = 'vaderland-20'
    version = '20'
    label = 'Vaderland \u00b7 Parallax Court'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'parallax-court-20.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        solids = design['solids']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids)
        self.vaderland['parallax_court'] = design['court']
        self.vaderland['places'].append({'name': 'Parallax Court', 'point': design['court']['door']})



class ParallaxInstrumentRoom(ParallaxCourt):
    id = environment_key = 'vaderland-21'
    version = '21'
    label = 'Vaderland \u00b7 Parallax Instrument Room'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with gzip.open(PACK / 'instrument-room-21.json.gz', 'rt', encoding='utf-8') as package:
            design = json.load(package)
        replaced = design['replace']
        overrides = design['support_remap']
        self.obstacles = [({**o, 'parent': overrides[o['id']]} if o['id'] in overrides else o)
                          for o in self.obstacles if o['id'] != replaced]
        self._shells = [(o, p) for o, p in self._shells if o['id'] != replaced]
        solids = design['solids']
        self.obstacles.extend(solids)
        self._shells.extend((o, np.asarray(o['planes'])) for o in solids if 'motion' not in o)
        self.vaderland['instrument_room'] = design['room']
        self.vaderland['places'].append(
            {'name': 'Parallax Instrument Room', 'point': design['room']['origin'][:2]})
