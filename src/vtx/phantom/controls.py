"""Phantom fly-by-wire: one action schema for human and AI, allocation, disclosed augmentation, PTI.

Schema "phantom-fbw-1" (POST /api/action). Every optional field defaults to "hold" (the previous
command is kept). Sign conventions (pilot-facing): pitch +1 = nose up, roll +1 = right side down,
yaw +1 = nose right; arrays are in physical order FL, FR, RL, RR / left, right (left = +Y).

Stability modes (disclosed, bounded, logged separately from the pilot):
  off            - stick = normalised differential moment demand
  rate_damping   - off + rate damping on sensed body rates (default)
  attitude       - stick = bank/pitch command, pedal = yaw-rate command; PD attitude loops
  attitude_vs    - attitude + vertical-speed command/hold: the pilot sets climb rate, the FCC
                   moves collective around a mass-based trim estimate within vs_authority,
                   using a LEAKY integrator so the mode can never act as an altitude hold.
No altitude, position or velocity hold exists; no pose is ever written.
PTI (step, doublet, 3211, sweep) is armed by the pilot, executed by the FCC on one axis, added at
the stick, and logged as PTI, not piloting; it auto-stops at the bank/pitch limit lines.
"""
from __future__ import annotations
import math
from typing import Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .geometry import PODS, SIDE, FRONT

PHANTOM_SCHEMA = 'phantom-fbw-1'
MODES = ('off', 'rate_damping', 'attitude', 'attitude_vs')


class PTI(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    command: Literal['arm', 'abort'] = 'arm'
    axis: Literal['roll', 'pitch', 'yaw', 'heave'] = 'pitch'
    type: Literal['step', 'doublet', '3211', 'sweep'] = 'doublet'
    amplitude: float = Field(default=0.1, ge=-0.5, le=0.5)
    pulse_s: float = Field(default=1.0, ge=0.05, le=20)
    f0_hz: float = Field(default=0.1, ge=0.01, le=10)
    f1_hz: float = Field(default=2.0, ge=0.01, le=10)
    duration_s: float = Field(default=20.0, ge=0.1, le=120)


def _fixed(n, lo, hi, name):
    def chk(v):
        if v is None:
            return v
        if len(v) != n or any(not (lo <= x <= hi) for x in v):
            raise ValueError(f'{name}: {n} values each {lo}..{hi}')
        return v
    return chk


class PhantomAction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_: Literal['phantom-fbw-1'] = Field(alias='schema')
    authority: str
    observation_id: int | None = None
    pilot_id: str | None = None
    pilot_epoch: int | None = None
    pilot_run_id: str | None = None
    reason: str = Field(min_length=3, max_length=2000)
    engine: float | None = Field(default=None, ge=0, le=1)
    collective: float | None = Field(default=None, ge=0, le=1)
    vertical_speed_m_s: float | None = Field(default=None, ge=-3, le=3)
    pitch: float | None = Field(default=None, ge=-1, le=1)
    roll: float | None = Field(default=None, ge=-1, le=1)
    yaw: float | None = Field(default=None, ge=-1, le=1)
    stability_mode: Literal['off', 'rate_damping', 'attitude', 'attitude_vs'] | None = None
    pod_tilt_deg: list[float] | None = None
    flap_deg: list[float] | None = None
    aileron_trim_deg: list[float] | None = None
    canard_pitch_deg: list[float] | None = None
    canard_fold: Literal['deployed', 'folded'] | None = None
    booster_throttle: list[float] | None = None
    wheel_drive: list[float] | None = None
    brake: list[float] | None = None
    leg_extension_m: list[float] | None = None
    wing: Literal['hold', 'deploy', 'stow'] | None = None
    pti: PTI | None = None

    _t = field_validator('pod_tilt_deg')(classmethod(lambda c, v: _fixed(4, 0, 90, 'pod_tilt_deg')(v)))
    _f = field_validator('flap_deg')(classmethod(lambda c, v: _fixed(2, -5, 35, 'flap_deg')(v)))
    _a = field_validator('aileron_trim_deg')(classmethod(lambda c, v: _fixed(2, -20, 20, 'aileron_trim_deg')(v)))
    _c = field_validator('canard_pitch_deg')(classmethod(lambda c, v: _fixed(2, -20, 25, 'canard_pitch_deg')(v)))
    _b = field_validator('booster_throttle')(classmethod(lambda c, v: _fixed(2, 0, 1, 'booster_throttle')(v)))
    _w = field_validator('wheel_drive')(classmethod(lambda c, v: _fixed(4, -1, 1, 'wheel_drive')(v)))
    _k = field_validator('brake')(classmethod(lambda c, v: _fixed(4, 0, 1, 'brake')(v)))
    _l = field_validator('leg_extension_m')(classmethod(lambda c, v: _fixed(4, 0, 0.52, 'leg_extension_m')(v)))


COMMAND_FIELDS = ('engine', 'collective', 'vertical_speed_m_s', 'pitch', 'roll', 'yaw', 'stability_mode', 'pod_tilt_deg', 'flap_deg', 'aileron_trim_deg',
                  'canard_pitch_deg', 'canard_fold', 'booster_throttle', 'wheel_drive', 'brake', 'leg_extension_m', 'wing')


def default_command(start='vtol'):
    return dict(engine=1.0, collective=0.0, vertical_speed_m_s=0.0, pitch=0.0, roll=0.0, yaw=0.0, stability_mode='rate_damping',
                pod_tilt_deg=[90.0] * 4 if start == 'vtol' else [0.0] * 4, flap_deg=[0.0, 0.0], aileron_trim_deg=[0.0, 0.0],
                canard_pitch_deg=[0.0, 0.0], canard_fold='folded', booster_throttle=[0.0, 0.0], wheel_drive=[0.0] * 4, brake=[1.0] * 4,
                leg_extension_m=[0.52] * 4 if start == 'vtol' else [0.0] * 4, wing='hold')


class PTIGenerator:
    def __init__(self):
        self.active = None; self.t0 = 0.0; self.log = []

    def arm(self, spec: dict, t):
        self.active = dict(spec); self.t0 = t
        self.log.append(dict(event='pti_start', t_s=t, spec=spec))

    def abort(self, t, why):
        if self.active:
            self.log.append(dict(event='pti_stop', t_s=t, reason=why, spec=self.active))
        self.active = None

    def value(self, t):
        if not self.active:
            return None, 0.0
        s = self.active; tau = t - self.t0; A = s['amplitude']; p = s['pulse_s']
        if s['type'] == 'step':
            seq, total = [1], p
        elif s['type'] == 'doublet':
            seq, total = [1, -1], 2 * p
        elif s['type'] == '3211':
            seq, total = [1] * 3 + [-1] * 2 + [1] + [-1], 7 * p
        else:
            total = s['duration_s']
            if tau > total:
                self.abort(t, 'complete'); return None, 0.0
            k = (s['f1_hz'] - s['f0_hz']) / total
            return s['axis'], A * math.sin(2 * math.pi * (s['f0_hz'] * tau + 0.5 * k * tau * tau))
        if tau > total:
            self.abort(t, 'complete'); return None, 0.0
        return s['axis'], A * seq[min(int(tau / p), len(seq) - 1)]


class FlightControl:
    """FCC: pilot command -> per-effector targets. Uses sensed state and declared mass properties only."""

    def __init__(self, P, fan, n_gen_power_w):
        self.P = P; self.fan = fan
        self.cmd = default_command()
        self.vs_int = 0.0
        self.pti = PTIGenerator()
        self.last = {}
        self.pod_x = {k: (P['pods.hinge_x_front_m'] if FRONT[k] else P['pods.hinge_x_rear_m']) for k in PODS}

    def apply(self, action: dict, t):
        for k in COMMAND_FIELDS:
            if action.get(k) is not None:
                self.cmd[k] = action[k]
        if action.get('pti'):
            p = action['pti']
            if p.get('command') == 'abort':
                self.pti.abort(t, 'pilot abort')
            else:
                self.pti.arm({k: v for k, v in p.items() if k != 'command'}, t)

    def update(self, t, sensed, mass_kg, cg_x, g, fan_enabled, thrust_avail):
        """sensed: roll, pitch_up, yaw (rad); p, q_up, r_left (rad/s body); vz (m/s up). Returns allocation dict."""
        P = self.P; c = self.cmd; mode = c['stability_mode']
        stick = dict(roll=c['roll'], pitch=c['pitch'], yaw=c['yaw'], heave=0.0)
        pti_axis, pti_val = self.pti.value(t)
        lim = P['fbw.pti_attitude_limits_deg']
        if pti_axis and (abs(math.degrees(sensed['roll'])) > lim[0] or abs(math.degrees(sensed['pitch_up'])) > lim[1]):
            self.pti.abort(t, 'limit line reached'); pti_axis, pti_val = None, 0.0
        if pti_axis:
            stick[pti_axis] = stick[pti_axis] + pti_val
        # moment demands (normalised -1..1 of moment authority): x roll-right, y nose-up, z nose-right
        aug = np.zeros(3); pil = np.zeros(3)
        kd = P['fbw.rate_damping_gain_s']; ka = P['fbw.attitude_gain']
        rates = np.array([sensed['p'], sensed['q_up'], -sensed['r_left']])   # roll-right, nose-up, nose-right
        if mode in ('off', 'rate_damping'):
            pil[:] = [stick['roll'], stick['pitch'], stick['yaw']]
            if mode == 'rate_damping':
                aug = -np.array(kd) * rates
        else:
            phi_c = stick['roll'] * math.radians(P['fbw.attitude_bank_max_deg'])
            th_c = stick['pitch'] * math.radians(P['fbw.attitude_pitch_max_deg'])
            r_c = stick['yaw'] * math.radians(P['fbw.yaw_rate_max_deg_s'])
            aug[0] = ka[0] * (phi_c - sensed['roll']) - kd[0] * rates[0]
            aug[1] = ka[1] * (th_c - sensed['pitch_up']) - kd[1] * rates[1]
            aug[2] = kd[2] * 2 * (r_c - rates[2])
        aa = P['fbw.augmentation_authority_fraction'] / P['fbw.moment_authority_fraction']
        aug = np.clip(aug, -aa if mode in ('off', 'rate_damping') else -1, aa if mode in ('off', 'rate_damping') else 1)
        demand = np.clip(pil + aug, -1, 1)
        # collective / vertical speed
        T_rated = 4 * self.fan.thrust_max
        trim = mass_kg * g / max(math.cos(sensed['roll']) * math.cos(sensed['pitch_up']), 0.5) / T_rated
        vs_contrib = 0.0
        if mode == 'attitude_vs':
            dt = 0.01
            err = c['vertical_speed_m_s'] + (stick['heave'] * P['fbw.vs_max_m_s']) - sensed['vz']
            self.vs_int += (err - self.vs_int / P['fbw.vs_leak_tau_s']) * dt
            vs_contrib = float(np.clip(P['fbw.vs_kp_per_m_s'] * err + P['fbw.vs_ki_per_m'] * self.vs_int, -P['fbw.vs_authority'], P['fbw.vs_authority']))
            coll = float(np.clip(trim + vs_contrib, 0, 1)) if c['collective'] > 0.05 else 0.0
        else:
            self.vs_int = 0.0
            coll = float(np.clip(c['collective'] + stick['heave'], 0, 1))
        # allocation: trim shares from declared CG (hover pitch trim from front/rear differential only)
        xf, xr = P['pods.hinge_x_front_m'], P['pods.hinge_x_rear_m']
        f = float(np.clip((cg_x - xr) / (xf - xr), 0.05, 0.95))
        share = {k: (f if FRONT[k] else 1 - f) / 2 for k in PODS}
        total = coll * T_rated
        auth = P['fbw.moment_authority_fraction'] * self.fan.thrust_max
        T = {}
        for k in PODS:
            d = demand[0] * SIDE[k] * 0.5 + demand[1] * (1 if FRONT[k] else -1) * 0.5    # roll right: left pods up
            T[k] = share[k] * total + d * auth * (coll > 0.02)
        # attitude-priority desaturation (disclosed): reduce collective part if a pod exceeds its limit
        sat = False
        over = max(T[k] / max(thrust_avail[k], 1.0) for k in PODS)
        if over > 1:
            sat = True
            diff = {k: T[k] - share[k] * total for k in PODS}
            room = min((thrust_avail[k] - diff[k]) / max(share[k] * total, 1e-6) for k in PODS)
            room = float(np.clip(room, 0, 1))
            T = {k: max(0.0, share[k] * total * room + diff[k]) for k in PODS}
        T = {k: max(0.0, T[k]) if fan_enabled[k] else 0.0 for k in PODS}
        # yaw: reaction-torque differential (spin senses) + diagonal tilt-back
        spin = P['pods.rotor_spin_sense']
        yaw_split = demand[2] * 0.15
        for k in PODS:
            # nose right = negative z moment; rotor reaction on body = -spin sense * Q
            T[k] *= (1 + yaw_split * spin[k]) if T[k] > 0 else 1
        tilt_back = demand[2] * P['fbw.yaw_tilt_authority_deg']
        tilt = list(c['pod_tilt_deg'])
        for i, k in enumerate(PODS):
            # nose right: tilt back FR and RL (their outboard force gives -z moment)
            diag = 1 if k in ('FR', 'RL') else -1
            back = max(0.0, tilt_back * diag)
            tilt[i] = float(np.clip(tilt[i] - back, 0, 90))
        # surfaces: pilot + trim; roll -> ailerons, pitch -> canards (effect physical, nil at zero airspeed)
        ail = [c['aileron_trim_deg'][0] + 20 * demand[0], c['aileron_trim_deg'][1] - 20 * demand[0]]
        can = [c['canard_pitch_deg'][i] + 15 * demand[1] for i in range(2)]
        self.last = dict(mode=mode, pilot_moment=pil.tolist(), augmentation_moment=aug.tolist(), moment_demand=demand.tolist(),
                         collective_cmd=c['collective'], collective_applied=coll, vs_cmd=c['vertical_speed_m_s'], vs_contribution=vs_contrib, vs_integrator=self.vs_int,
                         trim_collective_estimate=trim, trim_front_share=f, pti_axis=pti_axis, pti_value=pti_val, pod_thrust_cmd=[T[k] for k in PODS],
                         saturated=sat, tilt_cmd=tilt, aileron_cmd=ail, canard_cmd=can)
        return dict(thrust=[T[k] for k in PODS], tilt_deg=tilt, aileron_deg=[float(np.clip(a, -20, 20)) for a in ail],
                    canard_deg=[float(np.clip(x, -20, 25)) for x in can])

    def lease_failsafe(self):
        """5 s without a command: cut collective, boosters, wheel drive; brakes on; hold the rest."""
        self.cmd.update(collective=0.0, vertical_speed_m_s=0.0, booster_throttle=[0.0, 0.0], wheel_drive=[0.0] * 4, brake=[1.0] * 4)
        self.pti.abort(0.0, 'lease expired')
