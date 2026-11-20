"""Race scoring for a versioned harbour, sampled on the unchanged fleet clock."""
from copy import deepcopy
from .course_timing import CourseTiming
from .harbour_fleet import DT, HarbourFleet


def fleet_type(world):
    if world.harbour.get('timeTrial'):
        return LanternTrialFleet
    return HarbourFleet


class LanternTrialFleet(HarbourFleet):
    def __init__(self, world, **kwargs):
        super().__init__(world, **kwargs)
        self.trial = self.world.harbour['timeTrial']
        self.race_clocks = {boat:CourseTiming([self.trial]) for boat in self.crafts}
        self.race_fouls = {boat:None for boat in self.crafts}
        self._mark_geoms = {
            self.model.geom('airport_'+key).id
            for gate in self.trial['gates'] for key in gate['marks']
        }
        self._boat_geom_ids = {
            geom:boat for boat, model in self.mappings.items() for geom in model['gids']
        }

    def reset_trial(self, boat_id, reason=None):
        clock = self.race_clocks[boat_id]
        clock.previous = None
        clock.runs[self.trial['name']].update(start=None, next=0, splits=[])
        self.race_fouls[boat_id] = reason

    def step(self, dt=DT):
        with self._lock:
            super().step(dt)
            struck = set()
            for contact in self.data.contact:
                if contact.dist > 0:
                    continue
                for fixed, moving in ((contact.geom1,contact.geom2),(contact.geom2,contact.geom1)):
                    if fixed in self._mark_geoms and moving in self._boat_geom_ids:
                        struck.add(self._boat_geom_ids[moving])
            t = float(self.data.time)
            name = self.trial['name']
            for boat_id, clock in self.race_clocks.items():
                active = clock.runs[name]['start'] is not None
                if boat_id in struck:
                    self.reset_trial(boat_id,'Course marker contact')
                elif self.crafts[boat_id].crashed or boat_id in self.moorings:
                    self.reset_trial(boat_id,'Impact' if active else self.race_fouls[boat_id])
                else:
                    xyz = self.data.xpos[self.mappings[boat_id]['bid']]
                    clock.sample(t, xyz)
                    if clock.runs[name]['start'] is not None:
                        self.race_fouls[boat_id] = None

    def public(self):
        with self._lock:
            status = super().public()
            state = {}
            for key, clock in self.race_clocks.items():
                race = clock.runs[self.trial['name']]
                state[key] = {**deepcopy(race), 'foul':self.race_fouls[key],
                              'elapsed_s':None if race['start'] is None else status['t_s']-race['start']}
            status['lantern_trial'] = {'name':self.trial['name'], 'runs':state}
            return status

    def serialize(self):
        with self._lock:
            state = super().serialize()
            state['lantern_trial'] = {
                'course':self.trial['id'], 'runs':{key:clock.save() for key,clock in self.race_clocks.items()},
                'fouls':dict(self.race_fouls),
            }
            return state

    @classmethod
    def restore(cls, world, state):
        result = super().restore(world, state)
        saved = state.get('lantern_trial')
        if saved is None:
            raise ValueError('Lantern trial state is missing from this checkpoint')
        if (saved['course'] != result.trial['id']
                or set(saved['runs']) != set(result.crafts)
                or set(saved['fouls']) != set(result.crafts)):
            raise ValueError('Lantern trial checkpoint belongs to a different course or fleet')
        t = float(result.data.time)
        for key, clock in result.race_clocks.items():
            item = saved['runs'][key]
            raw = item['runs'][result.trial['name']]
            previous = item['previous']
            if (not 0 <= raw['next'] < len(result.trial['gates']) or
                    type(raw['next']) is not int or type(raw['laps']) is not int or raw['laps'] < 0
                    or (raw['start'] is not None and not 0 <= raw['start'] <= t)
                    or (previous is not None and (len(previous) != 2 or len(previous[1]) != 3
                                                  or not 0 <= previous[0] <= t))):
                raise ValueError('Invalid Lantern trial gate or clock')
            if saved['fouls'][key] not in (None,'Course marker contact','Impact'):
                raise ValueError('Invalid Lantern trial contact state')
            clock.restore(deepcopy(item))
            result.race_fouls[key] = saved['fouls'][key]
        return result