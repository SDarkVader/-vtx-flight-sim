"""Versioned Lantern Islet race marks and sailing line on the existing Sound."""
import json

from .cathedral_east import CathedralEastDistrict
from .vaderland import PACK


class LanternIsletDistrict(CathedralEastDistrict):
    id = environment_key = 'vaderland-28'
    version = '28'
    label = 'Vaderland \u00b7 Lantern Islet Trial'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with (PACK / 'lantern-islet-28.json').open(encoding='utf-8') as file:
            trial = json.load(file)
        self.obstacles.extend(trial.pop('solids'))
        self.harbour['timeTrial'] = trial
        self.vaderland['places'].append({'name':trial['name'],'point':trial['position']})