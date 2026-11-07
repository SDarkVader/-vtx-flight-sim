"""R6 instrument-based hold derived from the recorded 3 November A-B test.

This is a flight-test controller, not a general model of all R6 variants. It
holds the observed position, clearance and heading without changing the active
objective. The caller owns its lifecycle and must report unavailable inputs.
"""
from __future__ import annotations

import math


def _clamp(value, low, high):
    return max(low, min(high, value))


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Nonfinite R6 instrument value')
    return value


def _vector(obs, key, count):
    value = obs[key]
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError('Invalid R6 instrument: ' + key)
    return [_number(x) for x in value]


class R6HoldController:
    """Hold the current aircraft state using the recovered R6 control gains."""

    def __init__(self, observation):
        cfg = observation.get('configuration', {})
        if (cfg.get('airframe_variant') != 'r6' or cfg.get('reference_rpm') != 1200
                or cfg.get('engine_power_limit_kw') != 300):
            raise ValueError('R6 hold is supported for the recorded 1200 rpm / 300 kW configuration')
        if 'IMPACT' in observation.get('warning_lamps', []) or 'FUEL_EXHAUSTED' in observation.get('warning_lamps', []):
            raise ValueError('R6 hold unavailable with impact or exhausted fuel')
        clearance = observation.get('radar_clearance_m')
        if clearance is None:
            raise ValueError('R6 hold requires a clearance reading')
        if any(x > .001 for x in _vector(observation, 'gear_compression_m', 6)):
            raise ValueError('R6 hold requires an airborne aircraft; ground controls remain held')
        if sum(_vector(observation, 'rotor_rpm', 4)) / 4 < 1100:
            raise ValueError('R6 hold requires the rotor shaft to be running near its reference speed')
        self.position = _vector(observation, 'gnss_xy_m', 2)
        self.clearance = _number(clearance)
        self.heading = _vector(observation, 'attitude_xyz_deg', 3)[2]
        self.last_time = _number(observation['t_s'])
        self.int_roll = self.int_pitch = self.int_z = 0.0

    def snapshot(self):
        return {key: getattr(self, key) for key in
                ('position','clearance','heading','last_time','int_roll','int_pitch','int_z')}

    @classmethod
    def restore(cls, state):
        controller = cls.__new__(cls)
        controller.position = _vector(state, 'position', 2)
        for key in ('clearance','heading','last_time','int_roll','int_pitch','int_z'):
            setattr(controller, key, _number(state[key]))
        return controller

    def decide(self, obs):
        if 'IMPACT' in obs.get('warning_lamps', []) or 'FUEL_EXHAUSTED' in obs.get('warning_lamps', []):
            raise ValueError('R6 hold stopped: impact or exhausted fuel')
        pos = _vector(obs, 'gnss_xy_m', 2)
        vel = _vector(obs, 'gnss_velocity_mps', 3)
        attitude = _vector(obs, 'attitude_xyz_deg', 3)
        rates = _vector(obs, 'gyro_world_deg_s', 3)
        t = _number(obs['t_s'])
        clearance = _number(obs['radar_clearance_m'])
        dt = _clamp(t-self.last_time, 0.0, .1)
        self.last_time = t
        roll, pitch, yaw = attitude
        angle = math.radians(yaw)
        c, s = math.cos(angle), math.sin(angle)
        dx, dy = pos[0]-self.position[0], pos[1]-self.position[1]
        bx, by = c*dx+s*dy, -s*dx+c*dy
        vx, vy = c*vel[0]+s*vel[1], -s*vel[0]+c*vel[1]
        wx, wy = c*rates[0]+s*rates[1], -s*rates[0]+c*rates[1]
        self.int_roll = _clamp(self.int_roll+roll*dt, -1.8, 1.8)
        self.int_pitch = _clamp(self.int_pitch+pitch*dt, -1.8, 1.8)
        self.int_z = _clamp(self.int_z+(self.clearance-clearance)*dt, -1.2, 1.2)
        pitch_des = _clamp(-.32*bx-.45*vx, -2.5, 2.5)
        roll_des = _clamp(.32*by+.45*vy, -2.5, 2.5)
        mean = _clamp(16.98+1.15*(self.clearance-clearance)-1.65*vel[2]+.35*self.int_z, 14.5, 18.65)
        ur = _clamp(-.62*(roll-roll_des)-.32*wx-.24*self.int_roll, -3.5, 3.5)
        up = _clamp(-.62*(pitch-pitch_des)-.32*wy-.24*self.int_pitch, -3.5, 3.5)
        yaw_error = (yaw-self.heading+180) % 360-180
        uy = _clamp(-.85*yaw_error-.55*rates[2], -4, 4)
        return dict(engine=1.0, collective_deg=[mean-up,mean+.70+ur,mean+up,mean-.70-ur],
                    tilt_deg=[[-uy,0],[0,-uy],[uy,0],[0,uy]],
                    cabin_deg=[0,0,0], cabin_level=True,
                    reason='R6 fallback: hold current position, clearance and heading')
