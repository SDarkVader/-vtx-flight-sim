"""Rooftop missions on the native simulation clock.

A mission is an ordered list of steps:

- ``hoop``: a directional circular gate, crossed in the direction of ``normal`` within ``radius_m``;
- ``land``: a touchdown zone (``circle`` with ``radius_m`` or ``box`` with ``half``). The vehicle must be
  in contact inside the zone, within 6 m of its surface height, slower than ``max_speed_m_s`` for
  ``hold_s`` of simulated time;
- ``hover``: a station-keeping volume (a vertical cylinder of ``radius_m`` and ``half_height_m`` about
  ``center``). The vehicle must stay inside it, out of contact, slower than ``max_speed_m_s`` for
  ``hold_s``.

The clock starts at the first hoop. Contact anywhere other than the current or the previous touchdown
zone ends the attempt, so a mission is flown, not driven. Results use the same run record as the
trackside and air courses (start, next, splits, last, best, laps) plus the position error of each
touchdown or hover.
"""
import math

from .air_trial_timing import AirTrialTiming, _dot


def _inside(step, xyz):
    cx, cy, cz = step['center']
    if step['type'] == 'hover':
        return abs(xyz[2] - cz) <= step['half_height_m'] and math.hypot(xyz[0] - cx, xyz[1] - cy) <= step['radius_m']
    if abs(xyz[2] - cz) > 6.:
        return False
    if step['shape'] == 'circle':
        return math.hypot(xyz[0] - cx, xyz[1] - cy) <= step['radius_m']
    hx, hy = step['half']
    return abs(xyz[0] - cx) <= hx and abs(xyz[1] - cy) <= hy


class MissionTiming(AirTrialTiming):
    def __init__(self, ground, air, missions):
        super().__init__(ground, air)
        self.missions = missions
        for m in missions:
            self.runs[m['name']] = self._fresh(dict(last=None, best=None, laps=0))

    @staticmethod
    def _fresh(record):
        return dict(start=None, next=0, splits=[], last=record['last'], best=record['best'], laps=record['laps'],
                    hold=0., landing_error_m=[])

    @staticmethod
    def _advance(state, steps, idx, stamp):
        """Complete step ``idx`` at ``stamp``: start the clock, record a split, or finish the mission."""
        if idx == 0:
            state.update(start=stamp, next=1, splits=[], hold=0., landing_error_m=[])
        elif idx == len(steps) - 1:
            result = round(stamp - state['start'], 3)
            state.update(start=None, next=0, last=result, laps=state['laps'] + 1, hold=0.)
            state['best'] = min(result, state['best']) if state['best'] is not None else result
        else:
            state['splits'].append(round(stamp - state['start'], 3))
            state.update(next=idx + 1, hold=0.)

    def sample(self, t, position, *, air_allowed=True, contact=False):
        prev = self.previous
        super().sample(t, position, air_allowed=air_allowed, contact=contact)
        if not prev or self.previous is prev or not 0 < self.previous[0] - prev[0] < 2:
            return
        now, xyz = self.previous
        dt = now - prev[0]
        speed = math.dist(xyz, prev[1]) / dt
        for m in self.missions:
            state = self.runs[m['name']]
            idx = state['next']
            if state['start'] is None and idx == 0 and not air_allowed:
                continue
            steps = m['steps']
            step = steps[idx]
            previous_zone = next((s for s in reversed(steps[:idx]) if s['type'] == 'land'), None)
            on_previous = previous_zone is not None and _inside(previous_zone, xyz)
            if step['type'] in ('land', 'hover'):
                inside = _inside(step, xyz)
                held = inside and speed <= step['max_speed_m_s'] and (contact if step['type'] == 'land' else not contact)
                if held:
                    state['hold'] += dt
                    if state['hold'] >= step['hold_s']:
                        c = step['center']
                        state['landing_error_m'].append(round(math.hypot(xyz[0] - c[0], xyz[1] - c[1]), 3))
                        self._advance(state, steps, idx, now)
                elif contact and not (step['type'] == 'land' and inside) and not on_previous and state['start'] is not None:
                    self.runs[m['name']] = self._fresh(state)
                else:
                    state['hold'] = 0.
                continue
            # hoop
            if contact and state['start'] is not None and not on_previous:
                self.runs[m['name']] = self._fresh(state)
                continue
            centre = step['center']
            before = [q - r for q, r in zip(prev[1], centre)]
            after = [q - r for q, r in zip(xyz, centre)]
            a, b = _dot(step['normal'], before), _dot(step['normal'], after)
            if not a < 0 <= b:
                continue
            f = -a / (b - a)
            local = [u + f * (v - u) for u, v in zip(before, after)]
            if math.hypot(_dot(local, step['right']), _dot(local, step['up'])) > step['radius_m']:
                continue
            self._advance(state, steps, idx, prev[0] + f * dt)
