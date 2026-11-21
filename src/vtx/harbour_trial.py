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
        # Optional point-to-point race lines sharing a start and finish (Vaderland 33 Lantern Race).
        self.races = self.world.harbour.get('races') or []
        if self.races:
            self.race_lines = {boat:CourseTiming(self.races) for boat in self.crafts}
            self.race_line_fouls = {boat:None for boat in self.crafts}
            self._mark_geoms |= {
                self.model.geom('airport_'+key).id
                for race in self.races for gate in race['gates'] for key in gate['marks']
            }

    def reset_trial(self, boat_id, reason=None):
        clock = self.race_clocks[boat_id]
        clock.previous = None
        clock.runs[self.trial['name']].update(start=None, next=0, splits=[])
        self.race_fouls[boat_id] = reason
        if self.races:
            lines = self.race_lines[boat_id]
            lines.previous = None
            for run in lines.runs.values():
                run.update(start=None, next=0, splits=[])
            self.race_line_fouls[boat_id] = reason

    def _commit_line(self, boat_id):
        """Passing one line's first gate commits the boat to that line; the other lines stop."""
        runs = self.race_lines[boat_id].runs
        if any(run['start'] is not None and run['next'] >= 2 for run in runs.values()):
            for run in runs.values():
                if run['start'] is not None and run['next'] == 1:
                    run.update(start=None, next=0, splits=[])

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
                    if self.races:
                        self.race_lines[boat_id].sample(t, xyz)
                        self._commit_line(boat_id)
                        if any(run['start'] is not None for run in self.race_lines[boat_id].runs.values()):
                            self.race_line_fouls[boat_id] = None

    def public(self):
        with self._lock:
            status = super().public()
            state = {}
            for key, clock in self.race_clocks.items():
                race = clock.runs[self.trial['name']]
                state[key] = {**deepcopy(race), 'foul':self.race_fouls[key],
                              'elapsed_s':None if race['start'] is None else status['t_s']-race['start']}
            status['lantern_trial'] = {'name':self.trial['name'], 'runs':state}
            if self.races:
                status['lantern_races'] = {
                    'lines':[race['name'] for race in self.races],
                    'runs':{key:{line:{**deepcopy(run), 'elapsed_s':None if run['start'] is None else status['t_s']-run['start']}
                                 for line, run in lines.runs.items()} for key, lines in self.race_lines.items()},
                    'fouls':dict(self.race_line_fouls),
                }
            return status

    def serialize(self):
        with self._lock:
            state = super().serialize()
            state['lantern_trial'] = {
                'course':self.trial['id'], 'runs':{key:clock.save() for key,clock in self.race_clocks.items()},
                'fouls':dict(self.race_fouls),
            }
            if self.races:
                state['lantern_races'] = {
                    'courses':[race['id'] for race in self.races],
                    'runs':{key:lines.save() for key, lines in self.race_lines.items()},
                    'fouls':dict(self.race_line_fouls),
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
        if result.races:
            lines = state.get('lantern_races')
            if (lines is None or lines['courses'] != [race['id'] for race in result.races]
                    or set(lines['runs']) != set(result.crafts) or set(lines['fouls']) != set(result.crafts)):
                raise ValueError('Lantern Race checkpoint belongs to a different course or fleet')
            for key, timing in result.race_lines.items():
                item = lines['runs'][key]
                previous = item['previous']
                for race in result.races:
                    raw = item['runs'][race['name']]
                    if (type(raw['next']) is not int or not 0 <= raw['next'] < len(race['gates'])
                            or type(raw['laps']) is not int or raw['laps'] < 0
                            or (raw['start'] is not None and not 0 <= raw['start'] <= t)):
                        raise ValueError('Invalid Lantern Race gate or clock')
                if previous is not None and (len(previous) != 2 or len(previous[1]) != 3 or not 0 <= previous[0] <= t):
                    raise ValueError('Invalid Lantern Race clock')
                if lines['fouls'][key] not in (None, 'Course marker contact', 'Impact'):
                    raise ValueError('Invalid Lantern Race contact state')
                timing.restore(deepcopy(item))
                result.race_line_fouls[key] = lines['fouls'][key]
        return result