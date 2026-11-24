"""Offline, deterministic A-to-B sortie for the R6 physics plant. No server, no cockpit, no files written
except the JSON named on the command line.

The pilot is the controller that flew run 20261103T125202-92636c (argon_flight_test.py gains and trims),
running in-process at 50 Hz with a 20 ms transport delay and noiseless instruments, so two checkouts
given the same aircraft must produce the same trajectory bit for bit.

usage: python r6_physics_replay.py <checkout_root> <variant> <world: historical|sandbox> <out.json> [seconds]
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time

root, variant, world_kind, out_path = sys.argv[1:5]
limit_s = float(sys.argv[5]) if len(sys.argv) > 5 else 150.0
sys.path.insert(0, root + '/src')

import mujoco as mj  # noqa: E402
import numpy as np  # noqa: E402
from vtx._rotation import Rotation  # noqa: E402
from vtx.aircraft import Aircraft, DT  # noqa: E402

if world_kind == 'historical':
    from vtx.r6_historical_valley import R6HistoricalValley as World
else:
    from vtx.world import TestWorld as World

REQUEST = dict(gear_variant='critical-damping-proposal', rpm=1200.0, fuel_kg=10.0, engine_power_limit_kw=300.0,
               atmosphere_model='constant', wind_world_mps=(0.0, 0.0, 0.0))
A, B = (0.0, 0.0), (-50.0, 20.0)
CONTROL_STEPS = 8          # 50 Hz pilot at 400 Hz physics
DELAY_STEPS = 8            # 20 ms simulated transport, as recorded

world = World()
p = Aircraft(world, airframe_variant=variant, **REQUEST)
p.spawn(A[0], A[1], world.surface_z(*A))
m, d = p.model, p.data
bid = p.bids['airframe']


def observe():
    q = d.xquat[bid]
    euler = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_euler('xyz', degrees=True)
    v = np.zeros(6)
    mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_BODY, bid, v, 0)
    return dict(t=float(d.time), pos=d.xpos[bid].copy(), clear=p.ground_clearance(), att=euler,
                rate=np.degrees(v[:3]), vel=v[3:].copy(),
                rpm=[abs(p.joint(f'rotor{i}_spin')[1]) * 60 / (2 * math.pi) for i in range(1, 5)],
                tilt=[math.hypot(math.degrees(p.joint(f'nacelle{i}_x')[0]), math.degrees(p.joint(f'nacelle{i}_y')[0]))
                      for i in range(1, 5)])


# Pilot state (gains and trims as flown)
kp_att, kd_rate, ki_att, kp_vel, kd_vel = 0.62, 0.32, 0.24, 0.32, 0.45
trim_r2_r4, trim_r3_r1 = 0.70, 0.00
I = dict(roll=0.0, pitch=0.0, z=0.0)
S = dict(spool_t=None, phase='spool', phase_t=0.0, last_t=0.0, target=list(A))
CRUISE_CLEAR, HOVER_S = 9.74, 8.0


def pilot(o):
    dt = max(0.0, min(0.1, o['t'] - S['last_t']))
    S['last_t'] = o['t']
    if S['spool_t'] is None:
        if sum(o['rpm']) / 4 >= 1180.0 and max(o['tilt']) <= 1.2:
            S['spool_t'] = S['phase_t'] = o['t']
            S['phase'] = 'climb'
        return dict(engine=1.0, collective_deg=[0.0] * 4, tilt_deg=[[0.0, 0.0]] * 4, cabin_deg=[0.0, 0.0, 0.0], cabin_level=True)
    tp = o['t'] - S['phase_t']
    clear = o['clear'] if o['clear'] is not None else 0.0
    dx, dy = o['pos'][0] - S['target'][0], o['pos'][1] - S['target'][1]
    if S['phase'] == 'climb':
        target_clear, vz_ff = min(CRUISE_CLEAR, 1.15 * tp), (1.15 if 1.15 * tp < CRUISE_CLEAR else 0.0)
        if clear >= 9.0 and tp > CRUISE_CLEAR / 1.15 + HOVER_S:
            S['phase'], S['phase_t'], S['target'] = 'transit', o['t'], list(B)
    elif S['phase'] == 'transit':
        target_clear, vz_ff = CRUISE_CLEAR, 0.0
        if math.hypot(dx, dy) < 1.5 and math.hypot(*o['vel'][:2]) < 0.4:
            S['phase'], S['phase_t'] = 'descend', o['t']
    elif S['phase'] == 'descend':
        target_clear, vz_ff = max(-0.3, CRUISE_CLEAR - 0.8 * tp), -0.8
        if clear < 0.05 and abs(o['vel'][2]) < 0.2:
            S['phase'], S['phase_t'] = 'landed', o['t']
    else:
        return dict(engine=1.0, collective_deg=[0.0] * 4, tilt_deg=[[0.0, 0.0]] * 4, cabin_deg=[0.0, 0.0, 0.0], cabin_level=True)
    roll, pitch, yaw = o['att']
    wx, wy, wz = o['rate']
    vx, vy, vz = o['vel']
    if clear > 0.14:
        I['roll'] = max(-1.8, min(1.8, I['roll'] + roll * dt))
        I['pitch'] = max(-1.8, min(1.8, I['pitch'] + pitch * dt))
        I['z'] = max(-1.2, min(1.2, I['z'] + (target_clear - clear) * dt))
    pitch_des = max(-2.5, min(2.5, -kp_vel * dx - kd_vel * vx)) if clear > 0.34 else 0.0
    roll_des = max(-2.5, min(2.5, kp_vel * dy + kd_vel * vy)) if clear > 0.34 else 0.0
    c_mean = max(14.5, min(18.65, 16.98 + 1.15 * (target_clear - clear) + 1.65 * (vz_ff - vz) + 0.35 * I['z']))
    u_roll = max(-3.5, min(3.5, -kp_att * (roll - roll_des) - kd_rate * wx - ki_att * I['roll']))
    u_pitch = max(-3.5, min(3.5, -kp_att * (pitch - pitch_des) - kd_rate * wy - ki_att * I['pitch']))
    c = [c_mean - trim_r3_r1 - u_pitch, c_mean + trim_r2_r4 + u_roll, c_mean + trim_r3_r1 + u_pitch, c_mean - trim_r2_r4 - u_roll]
    u_yaw = max(-4.0, min(4.0, -0.85 * yaw - 0.55 * wz))
    return dict(engine=1.0, collective_deg=[max(0.0, min(30.0, x)) for x in c],
                tilt_deg=[[-u_yaw, 0.0], [0.0, -u_yaw], [u_yaw, 0.0], [0.0, u_yaw]],
                cabin_deg=[0.0, 0.0, 0.0], cabin_level=True)


trace, digest, pending, wall0 = [], hashlib.sha256(), [], time.perf_counter()
p.set_command(pilot(observe()))
max_tilt_deg, step = 0.0, 0
while d.time < limit_s and S['phase'] != 'landed' and not p.crashed:
    if step % CONTROL_STEPS == 0:
        o = observe()
        pending.append((step + DELAY_STEPS, pilot(o)))
        if step % 40 == 0:
            trace.append(dict(t=round(o['t'], 4), phase=S['phase'], pos=[round(float(x), 5) for x in o['pos']],
                              att=[round(float(x), 4) for x in o['att']], vel=[round(float(x), 4) for x in o['vel']],
                              clear=None if o['clear'] is None else round(o['clear'], 4),
                              rpm=round(sum(o['rpm']) / 4, 2), shaft_kw=round(p.power['engine_w'] / 1000, 2)))
    while pending and pending[0][0] <= step:
        p.set_command(pending.pop(0)[1])
    p.step()
    digest.update(d.qpos.tobytes())
    digest.update(d.qvel.tobytes())
    max_tilt_deg = max(max_tilt_deg, max(observe()['tilt']) if step % 40 == 0 else 0.0)
    step += 1

final = observe()
result = dict(checkout=root, variant=variant, world=world_kind, model_xml_sha256=hashlib.sha256(p.xml.encode()).hexdigest(),
              steps=step, simulated_s=round(float(d.time), 4), wall_s=round(time.perf_counter() - wall0, 1),
              outcome='landed' if S['phase'] == 'landed' else ('crashed' if p.crashed else f'stopped in {S["phase"]}'),
              final_pos=[round(float(x), 4) for x in final['pos']],
              distance_to_B_m=round(math.hypot(final['pos'][0] - B[0], final['pos'][1] - B[1]), 3),
              max_clearance_m=max((r['clear'] or 0) for r in trace), max_attitude_deg=max(max(abs(r['att'][0]), abs(r['att'][1])) for r in trace),
              fuel_used_kg=round(10.0 - float(p.fuel.sum()), 4), max_gear_load_n=round(p.max_gear_load_n, 1),
              max_nongear_impact_n=round(p.max_nongear_impact_n, 1), flags=sorted(p.flags),
              state_trajectory_sha256=digest.hexdigest(), trace=trace)
json.dump(result, open(out_path, 'w'), indent=1)
print(json.dumps({k: v for k, v in result.items() if k != 'trace'}, indent=1))
