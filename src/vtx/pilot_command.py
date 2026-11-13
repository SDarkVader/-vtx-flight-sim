"""Spoken or typed pilot instruction -> one validated phantom-fbw-1 action -> telemetry confirmation.

The interpreter is deterministic (no language model in the control loop). It only ever produces a patch of
PhantomAction fields; the patch goes through the same Laboratory.accept_action authority, run and schema checks as
every other pilot, and nothing is reported as executed until the plant's own held command shows it.
public/voice-pilot.js carries the same grammar for offline use; this module is the authority when the server is up."""
from __future__ import annotations
import math, re

UNITS = dict(zero=0, oh=0, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12,
             thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17, eighteen=18, nineteen=19)
TENS = dict(twenty=20, thirty=30, forty=40, fifty=50, sixty=60, seventy=70, eighty=80, ninety=90)
FILLER = r"\b(please|can you|could you|would you|will you|let's|lets|i want you to|i need you to|go ahead and|now|just|okay|ok|hey|pilot|colin|for me|a bit|a little)\b"


def normalise(text):
    s = str(text or '').lower().replace('per cent', 'percent').replace('%', ' percent ')
    s = re.sub(r"[,!?;:']", ' ', s); s = re.sub(r'(\d)\.(\d)', r'\1§\2', s).replace('.', ' ').replace('§', '.').replace('-', ' ')
    s = re.sub(FILLER, ' ', s)
    toks, out, i = s.split(), [], 0
    while i < len(toks):
        t = toks[i]
        if t == 'a' and i + 1 < len(toks) and toks[i + 1] == 'hundred':
            out.append('100'); i += 2; continue
        if t in UNITS or t in TENS:
            cur, j = 0, i
            while j < len(toks):
                w = toks[j]
                if w in TENS: cur += TENS[w]
                elif w in UNITS: cur += UNITS[w]
                elif w == 'hundred': cur = (cur or 1) * 100
                elif w == 'and' and j + 1 < len(toks) and (toks[j + 1] in UNITS or toks[j + 1] in TENS): pass
                else: break
                j += 1
            if j + 1 < len(toks) and toks[j] == 'point' and toks[j + 1] in UNITS:
                out.append(str(cur + UNITS[toks[j + 1]] / 10)); i = j + 2; continue
            out.append(str(cur)); i = j; continue
        out.append('50' if t == 'half' else t); i += 1
    return re.sub(r' (minus|negative) (\d+(?:\.\d+)?)', r' -\2', ' ' + ' '.join(out) + ' ')


def _num(s):
    m = re.search(r'(-?\d+(?:\.\d+)?)', s)
    return float(m.group(1)) if m else None


def _clamp(x, lo, hi):
    return min(hi, max(lo, x))


def _g(x):
    return f'{x:g}'


def parse(text, obs=None):
    """Return dict(intent, patch?, say, risky?). 'refused' carries the reason a command was not formed."""
    s = normalise(text); n = _num(s); has = lambda rx: re.search(rx, s) is not None
    obs = obs or {}
    R = lambda intent, say, patch=None, risky=False: dict(intent=intent, say=say, patch=patch, risky=risky)
    if has(r' (confirm|confirmed|affirmative|do it|execute|yes) '): return R('confirm', 'Confirmed.')
    if has(r' (cancel|abort that|belay that|no|never mind) '): return R('cancel', 'Cancelled.')
    if has(r' (status|report|readout|how are we doing|what is our|whats our|where are we) '): return R('status', '')
    if has(r' boost(ers?)? ') or has(r' afterburners? '):
        if has(r' (off|cut|kill|idle|zero) '): return R('boost', 'Boosters off.', dict(booster_throttle=[0.0, 0.0]))
        if has(r' (full|max|maximum) '): return R('boost', 'Boosters full thrust.', dict(booster_throttle=[1.0, 1.0]))
        if n is not None:
            f = _clamp(n, 0, 100) / 100; thr = math.sqrt(f)   # spoken value is a thrust fraction; throttle commands rotor speed
            return R('boost', f'Boosters {round(f * 100)} percent thrust.', dict(booster_throttle=[thr, thr]))
    if has(r' (take ?off|takeoff) (config|configuration|setup) '):
        return R('takeoff_config', 'Take-off configuration: wings deploying, flaps thirty, canards deployed, attitude hold.',
                 dict(wing='deploy', flap_deg=[30.0, 30.0], canard_fold='deployed', canard_pitch_deg=[0.0, 0.0], stability_mode='attitude', pitch=0.0, roll=0.0))
    if has(r' (take ?off|takeoff|lift ?off|take us up|get us (up|airborne|in the air)|go up) ') and n is None:
        tilt = obs.get('pod_tilt_deg') or []
        if not tilt or min(tilt) < 80:
            return R('refused', 'I cannot lift off vertically: the pods are not vertical. Say VTOL mode first.')
        return R('vtol_takeoff', 'Lifting off, climbing 1.5 metres per second.',
                 dict(stability_mode='attitude_vs', collective=1.0, vertical_speed_m_s=1.5, brake=[0.0] * 4, wheel_drive=[0.0] * 4, pitch=0.0, roll=0.0))
    if has(r' (land|set (us|it) down|touch down|put (us|it) down) '):
        return R('land', 'Descending 1 metre per second to land.', dict(stability_mode='attitude_vs', vertical_speed_m_s=-1.0, pitch=0.0, roll=0.0))
    if has(r' (stop|halt|brakes? on|set (the )?brakes?|full brakes?|hit the brakes?) '):
        return R('brake', 'Brakes on, drive zero.', dict(brake=[1.0] * 4, wheel_drive=[0.0] * 4))
    if has(r' (release (the )?brakes?|brakes? off) '): return R('brake', 'Brakes released.', dict(brake=[0.0] * 4))
    if has(r' (slow down|ease off|slower) '): return R('drive', 'Drive zero, half brakes.', dict(wheel_drive=[0.0] * 4, brake=[0.5] * 4))
    if has(r' (coast|neutral) '): return R('drive', 'Drive zero, coasting.', dict(wheel_drive=[0.0] * 4))
    if has(r' reverse '):
        v = _clamp(n if n is not None else 20, 0, 100) / 100
        return R('drive', f'Reverse drive {round(v * 100)} percent.', dict(wheel_drive=[-v] * 4, brake=[0.0] * 4))
    if has(r' (floor it|full (speed|power|drive)|go faster|speed up|punch it) '):
        return R('drive', 'Wheel drive 100 percent, brakes released.', dict(wheel_drive=[1.0] * 4, brake=[0.0] * 4))
    if has(r' (drive|accelerate|wheels?|forward|ahead) ') and n is not None:
        v = _clamp(n, 0, 100) / 100
        return R('drive', f'Wheel drive {round(v * 100)} percent.', dict(wheel_drive=[v] * 4, brake=[0.0] * 4))
    if has(r' (drive|go) (forward|ahead) ') or has(r' (move|roll) forward '):
        return R('drive', 'Wheel drive 50 percent, brakes released.', dict(wheel_drive=[0.5] * 4, brake=[0.0] * 4))
    if has(r' (turn|steer|yaw|go) (hard )?(left|right) ') or has(r' (left|right) (turn|rudder) ') or has(r' hard (left|right) '):
        d = _clamp(n if n is not None else (100 if has(r' hard ') else 50), 0, 100) / 100
        sign = 1.0 if has(r' right ') else -1.0   # yaw +1 = nose right
        return R('steer', f'Steering {"right" if sign > 0 else "left"} {round(d * 100)} percent.', dict(yaw=sign * d))
    if has(r' (straight|centre|center|straighten) '): return R('steer', 'Steering centred.', dict(yaw=0.0))
    if has(r' wings? (out|deploy|extend) ') or has(r' (deploy|extend|open) (the )?wings? '): return R('wing', 'Wings deploying.', dict(wing='deploy'))
    if has(r' wings? (in|stow|retract) ') or has(r' (stow|retract|close) (the )?wings? '): return R('wing', 'Stow the wings?', dict(wing='stow'), True)
    if has(r' flaps? '):
        d = 0.0 if has(r' (up|retract|clean) ') else 30.0 if has(r' (down|full) ') and n is None else n
        if d is None: return R('unknown', 'Flaps to what angle?')
        d = _clamp(d, -5, 35); return R('flap', f'Flaps {_g(d)} degrees.', dict(flap_deg=[d, d]))
    if has(r' (max|maximum) downforce '): return R('downforce', 'Maximum road downforce: canards minus ten.', dict(canard_fold='deployed', canard_pitch_deg=[-10.0, -10.0]))
    if has(r' (downforce|road trim|road aero) '): return R('downforce', 'Road downforce: canards minus six.', dict(canard_fold='deployed', canard_pitch_deg=[-6.0, -6.0]))
    if has(r' canards? '):
        if has(r' (fold|stow|in) '): return R('canard', 'Fold the canards?', dict(canard_fold='folded'), True)
        if has(r' (deploy|out) ') and n is None: return R('canard', 'Canards deploying.', dict(canard_fold='deployed'))
        if n is not None: d = _clamp(n, -20, 25); return R('canard', f'Canards {_g(d)} degrees.', dict(canard_pitch_deg=[d, d]))
    if has(r' (nose|pitch) ') and has(r' (up|down) '):
        d = _clamp(n if n is not None else 5, 0, 10) * (-1 if has(r' down ') else 1)
        return R('pitch', f'Attitude hold, pitch {_g(d)} degrees.', dict(stability_mode='attitude', pitch=d / 10))
    if has(r' (level|wings level|hold attitude) '): return R('level', 'Levelling, attitude hold.', dict(stability_mode='attitude', pitch=0.0, roll=0.0))
    if has(r' (vtol|hover) mode ') or has(r' (pods?|wheels?) (up|vertical) '):
        return R('mode', 'VTOL mode: pods vertical, legs extended.', dict(pod_tilt_deg=[90.0] * 4, leg_extension_m=[0.52] * 4))
    if has(r' (road|drive|driving|car) mode '): return R('mode', 'Road mode: pods down and legs up?', dict(pod_tilt_deg=[0.0] * 4, leg_extension_m=[0.0] * 4), True)
    if has(r' (hover|hold altitude|hold height|hold here|stay here) '): return R('vs', 'Holding altitude.', dict(stability_mode='attitude_vs', vertical_speed_m_s=0.0))
    if has(r' (climb|ascend|up|higher) '):
        v = _clamp(n if n is not None else 1.0, 0, 3); return R('vs', f'Climbing {_g(v)} metres per second.', dict(stability_mode='attitude_vs', vertical_speed_m_s=v))
    if has(r' (descend|down|lower) '):
        v = _clamp(abs(n) if n is not None else 1.0, 0, 3); return R('vs', f'Descending {_g(v)} metres per second.', dict(stability_mode='attitude_vs', vertical_speed_m_s=-v))
    if has(r' collective ') and n is not None: c = _clamp(n, 0, 100) / 100; return R('collective', f'Collective {round(c * 100)} percent.', dict(collective=c))
    if has(r' (legs? (down|extend)|extend (the )?legs?) '): return R('legs', 'Legs extending.', dict(leg_extension_m=[0.52] * 4))
    if has(r' (legs? (up|retract)|retract (the )?legs?) '): return R('legs', 'Retract the legs?', dict(leg_extension_m=[0.0] * 4), True)
    if has(r' engines? '):
        if has(r' (off|stop|shut ?down|kill) '): return R('engine', 'Shut the engine down?', dict(engine=0.0), True)
        if has(r' idle '): return R('engine', 'Engine idle.', dict(engine=0.15))
        if has(r' (on|start|run|full) '): return R('engine', 'Engine running.', dict(engine=1.0))
    if has(r' (stability|augmentation) off '): return R('stability', 'Turn stability augmentation off?', dict(stability_mode='off'), True)
    if has(r' rate damping '): return R('stability', 'Rate damping.', dict(stability_mode='rate_damping'))
    if has(r' (auto|automatic) (mode|modes|law) '): return R('stability', 'Automatic law selection by flight phase.', dict(stability_mode='auto'))
    if has(r' attitude (mode|hold) '): return R('stability', 'Attitude hold.', dict(stability_mode='attitude'))
    return R('unknown', f'Not understood: {str(text or "").strip()}')


def status_readback(o):
    parts = []
    a, h = o.get('airspeed_m_s'), o.get('radar_altimeter_m'); vz = (o.get('velocity_world_m_s') or [None] * 3)[2]
    if a is not None: parts.append(f'airspeed {round(a)} metres per second')
    if h is not None: parts.append(f'radar altitude {h:.1f} metres')
    if vz is not None: parts.append(f'vertical speed {vz:.1f}')
    if o.get('weight_on_wheels') is not None: parts.append('weight on wheels' if o['weight_on_wheels'] else 'airborne')
    if o.get('wing_state'): parts.append('wings ' + ' and '.join(str(v) for v in o['wing_state'].values()))
    if o.get('buffer_soc') is not None: parts.append(f"battery {round(o['buffer_soc'] * 100)} percent")
    lamps = o.get('warning_lamps') or []
    parts.append('warnings: ' + ', '.join(lamps).lower().replace('_', ' ') if lamps else 'no warnings')
    return '. '.join(parts) + '.'


TELEMETRY_KEYS = ('t_s', 'airspeed_m_s', 'radar_altimeter_m', 'velocity_world_m_s', 'attitude_deg', 'pod_tilt_deg', 'leg_extension_m',
                  'wing_state', 'flap_deg', 'canard_pitch_deg', 'fan_rpm', 'weight_on_wheels', 'generator_kw', 'stability_mode', 'warning_lamps')


def telemetry_excerpt(o):
    return {k: o.get(k) for k in TELEMETRY_KEYS if k in o}


def held(cmd, patch):
    """True when every commanded field is now the plant's held command (the action was applied by the physics loop)."""
    def same(a, b):
        if isinstance(b, (list, tuple)):
            return isinstance(a, (list, tuple)) and len(a) == len(b) and all(abs(float(x) - float(y)) < 1e-6 for x, y in zip(a, b))
        if isinstance(b, (int, float)) and not isinstance(b, bool):
            return a is not None and abs(float(a) - float(b)) < 1e-6
        return a == b
    return all(same(cmd.get(k), v) for k, v in patch.items())
