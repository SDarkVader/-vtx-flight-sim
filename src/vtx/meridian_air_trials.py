"""Meridian air courses and surveyed surface treatments."""
import json

from .air_trial_timing import AirTrialTiming
from .lantern_islet import LanternIsletDistrict
from .vaderland import PACK


class MeridianAirTrials(LanternIsletDistrict):
    id = environment_key = 'vaderland-29'
    version = '29'
    label = 'Vaderland \u00b7 Meridian Air Trials'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with (PACK/'meridian-air-29.json').open(encoding='utf-8') as stream:
            routes=json.load(stream)
        self.timing=AirTrialTiming(self.timing.courses,routes)
        self.vaderland['air_trials']=routes
        self.vaderland['time_trials'].extend(dict(course=r['name'],zone=r['zone'],
            spawn=r['spawn'],length_m=r['length_m'],format='air',gates=len(r['gates']))
            for r in routes)
        self.vaderland['surface_detail']=dict(quarry_mud=True,water_displacement=True)