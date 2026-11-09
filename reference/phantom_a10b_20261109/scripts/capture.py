"""Capture physical snapshots of phantom-a10b at points of interest for rendering (with telemetry for the data panel)."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom.geometry import PODS, SIDE
sc = sys.argv[2]; OUT = sys.argv[1] + f'/shots/{sc}.json'
a = C.plant('phantom-a10b', None, start_configuration='vtol' if sc == 'vtol' else 'road'); m, d = a.model, a.data; P = a.P
W = a.mass_properties()['mass_kg'] * 9.80665; frames = []
def tele(a, label, note=''):
    att = a.attitude(); vb = a.vel_body(); b = a.bus.last or {}; snap = a.physical_snapshot(); ph = snap['phantom']
    u = float(vb[0]); V = float(np.linalg.norm(d.qvel[:3]))
    return dict(label=label, note=note, t=round(float(d.time), 2), snap=dict(body_poses=snap['body_poses'], phantom=ph, boosters=snap['boosters'],
                command=a.fcc.cmd, t_s=snap['t_s']),
                data=dict(speed_m_s=round(V, 1), speed_kmh=round(V * 3.6), altitude_m=round(float(d.qpos[2]) - z0, 1), pitch_deg=round(math.degrees(att['pitch_up']), 1),
                          bank_deg=round(math.degrees(att['roll']), 1), heading_deg=round(math.degrees(att['yaw_left']), 1),
                          aoa_deg=round(math.degrees(math.atan2(-vb[2], max(abs(vb[0]), 1e-3))), 1) if V > 5 else None,
                          sideslip_deg=round(math.degrees(math.atan2(vb[1], max(abs(vb[0]), 1e-3))), 1) if V > 5 else None,
                          dynamic_pressure_pa=round(0.5 * 1.225 * V * V), wing_state=a.wing_state['left'],
                          fan_thrust_n=[round(s.get('thrust_n', 0)) for s in a.fan_state], pod_tilt_deg=[round(math.degrees(abs(a.joint(f'pod_{k}')[0]))) for k in PODS],
                          booster_thrust_n=[round(s.get('thrust_n', 0)) for s in a.booster_state], tvc_deg=[round(math.degrees(x), 1) for x in a.tvc],
                          rudder_deg=round(math.degrees(a.rudder), 1), steer_deg=round(math.degrees(a.joint('pod_FL_steer')[0]), 1),
                          suspension_m=[round(a.joint(f'pod_{k}_susp')[0], 3) for k in PODS], pitch_demand=round((a.fcc.last or {}).get('moment_demand', [0, 0, 0])[1], 2),
                          bus_kw=round(b.get('delivered_w', 0) / 1e3), buffer_soc=round(a.bus.soc, 3), tyres_on_ground=a.support_count(),
                          mass_kg=round(a.mass_properties()['mass_kg'], 1)))
z0 = float(d.qpos[2])
def run_until(cond, tmax, every=0.05):
    n = int(tmax / every)
    for _ in range(n):
        C.run(a, every)
        if cond(): return True
    return False
if sc == 'deploy':
    a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], wing='deploy', canard_fold='deployed'))
    run_until(lambda: a.wing_state['left'] == 'hatch_opening' and a.joint('hatch_left')[0] < 2.0, 3); frames.append(tele(a, 'Wing deployment 1/3: hatches opening', 'standing start, no brakes, full drive + boosters'))
    run_until(lambda: a.wing_state['left'] == 'sliding_out' and (a.joint('wing_left')[0] + P.wing_stroke_m) / P.wing_stroke_m > 0.5, 6); frames.append(tele(a, 'Wing deployment 2/3: wings sliding out', 'transit limit 600 Pa (31.3 m/s); guard predicts lock speed'))
    run_until(lambda: a.wing_state['left'] == 'locked', 6); frames.append(tele(a, 'Wing deployment 3/3: wings locked', 'locked at ~25 m/s, inside the 600 Pa transit limit'))
elif sc == 'steer':
    a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4))
    run_until(lambda: float(a.vel_body()[0]) > 10.0, 10)
    a.set_command(dict(wheel_drive=[0.25]*4, yaw=1.0)); C.run(a, 1.5); frames.append(tele(a, 'Road turning: steer-by-wire, full right lock', 'front wheels steered, speed-scheduled to 0.8 g'))
    C.run(a, 2.0); frames.append(tele(a, 'Road turning: 18 m radius at 11 m/s', 'heading change ~140 deg in 4 s'))
elif sc == 'vtol':
    a.set_command(dict(stability_mode='attitude_vs', collective=1.0, vertical_speed_m_s=2.0, brake=[0.]*4, engine=1.0))
    run_until(lambda: float(d.qpos[2]) - z0 > 0.3, 15); frames.append(tele(a, 'VTOL take-off: lift-off on the wheel fans', 'pods at 90 deg, fans facing down'))
    run_until(lambda: float(d.qpos[2]) - z0 > 10.0, 20); a.set_command(dict(vertical_speed_m_s=0.0)); C.run(a, 3.0); frames.append(tele(a, 'VTOL hover at ~10 m', 'thrust-to-weight 1.38; hover ~1.39 MW (take-off rating + buffer)'))
elif sc == 'roll':
    a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], wing='deploy', canard_fold='deployed', flap_deg=[30., 30.], stability_mode='attitude', pitch=0.0))
    run_until(lambda: float(a.vel_body()[0]) > 70, 40); a.set_command(dict(pitch=0.5))
    run_until(lambda: float(a.vel_body()[0]) > 84, 40); frames.append(tele(a, 'Take-off roll at 84 m/s: rotation not achieved', 'full nose-up demand + booster TVC -20 deg; needs ~27 kN m about the rear tyres, ~8-10 available'))
else:   # decel + turn, fans facing down
    a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
    th = 4.0; d.qpos[2] += 300.0; z0 = float(d.qpos[2]); d.qpos[3:7] = [math.cos(math.radians(th) / 2), 0, -math.sin(math.radians(th) / 2), 0]
    d.qvel[:] = 0.0; d.qvel[0] = 95.0
    for k in PODS:
        a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
        d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * a.fan.omega_for_thrust(0.05 * W / 4)
    a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power); mj.mj_forward(m, d)
    a.set_command(dict(stability_mode='attitude', pitch=0.4, collective=0.05, booster_throttle=[0., 0.], wheel_drive=[0.]*4, brake=[0.]*4, pod_tilt_deg=[90.]*4, flap_deg=[0., 0.]))
    st = dict(turn=False, hdg0=None, shots=set())
    def pilot():
        u = float(a.vel_body()[0]); z = float(d.qpos[2]); vz = float(d.qvel[2]); r = math.degrees(a.attitude()['roll'])
        a.set_command(dict(collective=float(np.clip(0.71 * (1 - min(1, (u / 95.0) ** 2)) / max(math.cos(math.radians(r)), 0.5) + 0.03 + 0.03 * (z0 - z) - 0.08 * vz, 0, 1))))
        if not st['turn'] and u < 60.0:
            st['turn'] = True; st['hdg0'] = math.degrees(a.attitude()['yaw_left']); a.set_command(dict(roll=30.0 / 45.0))
        if st['turn']:
            ph = math.radians(max(abs(r), 1.0)); a.set_command(dict(yaw=float(np.clip(math.degrees(9.80665 * math.tan(ph) / max(u, 15)) / 20.0, 0, 1))))
        return u
    t_start = float(d.time)
    for _ in range(int(40 / 0.05)):
        u = pilot(); C.run(a, 0.05); t = float(d.time) - t_start
        if 'a' not in st['shots'] and t > 0.2: st['shots'].add('a'); frames.append(tele(a, 'Fan braking 1/3: 95 m/s, fans facing down', 'nose held at 4 deg; boosters off'))
        if 'b' not in st['shots'] and u < 75: st['shots'].add('b'); frames.append(tele(a, 'Fan braking 2/3: decelerating through 75 m/s', 'ram drag of the wheel fans + body drag; nose attitude retained'))
        if 'c' not in st['shots'] and st['turn'] and abs(math.degrees(a.attitude()['roll'])) > 25: st['shots'].add('c'); frames.append(tele(a, 'Turning 1/2: 30 deg bank, decelerating', '90 deg turn begun at 60 m/s'))
        if 'd' not in st['shots'] and st['turn'] and abs(math.degrees(a.attitude()['yaw_left']) - st['hdg0']) > 45: st['shots'].add('d'); frames.append(tele(a, 'Turning 2/2: 45 deg into the 90 deg turn', 'speed bleeding off toward hover'))
        if 'e' not in st['shots'] and st['turn'] and abs(math.degrees(a.attitude()['yaw_left']) - st['hdg0']) > 89: st['shots'].add('e'); frames.append(tele(a, 'Turn complete: 90 deg, ending in hover', '480 m arc in ~29 s; altitude held'))
        if len(st['shots']) == 5: break
json.dump(frames, open(OUT, 'w'), default=float)
print(sc, [f['label'] for f in frames])
