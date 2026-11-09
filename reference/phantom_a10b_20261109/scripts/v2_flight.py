"""V2 (from V1): trimmed start (pitch 4 deg at 95 m/s, level path), fans facing down (pods 90 deg), nose held at constant
attitude while decelerating (boosters off), altitude held on collective; banked turn below 45 m/s.
'newlaw': A10-B physics + control_effectors_v1 (wing-borne law); 'oldlaw': same physics, hover-tuned law."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
from vtx.phantom.geometry import PODS, SIDE
tag = sys.argv[2]
names = ['hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1'] + (['control_effectors_v1'] if tag == 'newlaw' else [])
OV = overlays.load(*names, extra={'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}})
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data; P = a.P
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
W = a.mass_properties()['mass_kg'] * 9.80665
TH = 4.0; V0 = 95.0
d.qpos[2] += 300.0; d.qpos[3:7] = [math.cos(math.radians(TH) / 2), 0, -math.sin(math.radians(TH) / 2), 0]
d.qvel[:] = 0.0; d.qvel[0] = V0
for k in PODS:
    a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
    d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * a.fan.omega_for_thrust(0.05 * W / 4)
a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power)
mj.mj_forward(m, d)
print(tag, 'config', P.config_sha256[:8], 'initial pitch', round(math.degrees(a.attitude()['pitch_up']), 2))
z_ref = float(d.qpos[2])
a.set_command(dict(stability_mode='attitude', pitch=TH / 10.0, roll=0.0, yaw=0.0, collective=0.05, booster_throttle=[0., 0.], wheel_drive=[0.]*4, brake=[0.]*4,
                   pod_tilt_deg=[90.]*4, flap_deg=[0., 0.], canard_pitch_deg=[0., 0.]))
log = []; st = dict(turn=None)
def pilot(a):
    t = float(d.time); z = float(d.qpos[2]); vz = float(d.qvel[2]); u = float(a.vel_body()[0])
    att = a.attitude(); vb = a.vel_body(); rb = a.rates_body()
    cmd = dict(collective=float(np.clip(0.71 * (1 - min(1, (u / V0) ** 2)) + 0.03 + 0.03 * (z_ref - z) - 0.08 * vz, 0.0, 1.0)))
    if st['turn'] is None and u < 45.0:
        st['turn'] = t; cmd.update(roll=0.8, yaw=float(np.clip(math.degrees(9.80665 * math.tan(math.radians(12.0)) / max(u, 20.0)) / 20.0, 0, 1)))
    a.set_command(cmd)
    b = a.bus.last or {}
    log.append(dict(t=round(t, 2), u=round(u, 2), z=round(z - z_ref, 2), pitch=round(math.degrees(att['pitch_up']), 2),
                    alpha=round(math.degrees(math.atan2(-vb[2], max(abs(vb[0]), 1e-3))), 2), roll=round(math.degrees(att['roll']), 2),
                    beta=round(math.degrees(math.atan2(vb[1], max(abs(vb[0]), 1e-3))), 2), hdg=round(math.degrees(att['yaw_left']), 2),
                    q=round(math.degrees(rb[1]), 1), coll=round(a.fcc.cmd['collective'], 3), dem=[round(x, 2) for x in (a.fcc.last or {}).get('moment_demand', [0, 0, 0])],
                    fanT=[round(s.get('thrust_n', 0)) for s in a.fan_state], ram=[round(s.get('ram_drag_n', 0)) for s in a.fan_state],
                    bus_kw=round(b.get('delivered_w', 0) / 1e3), unmet_kw=round(b.get('unmet_w', 0) / 1e3), soc=round(a.bus.soc, 3)))
    return abs(att['pitch_up']) > math.radians(60) or abs(att['roll']) > math.radians(80) or a.crashed or (st['turn'] is not None and t - st['turn'] > 30) or t > 120
C.run(a, 130, every=0.05, stop=pilot)
json.dump(log, open(f'{sys.argv[1]}/v2_{tag}.json', 'w'))
L = log; t0 = L[0]['t']
for tt in (0, 0.5, 1, 2, 4, 6, 8, 10, 15, 20, 25, 30, 40, 50, 60):
    if t0 + tt <= L[-1]['t']:
        r = min(L, key=lambda r: abs(r['t'] - t0 - tt))
        print('  t+%4.1f u %6.1f z %+7.1f pitch %+6.2f alpha %+6.2f roll %+6.1f beta %+5.1f hdg %+7.1f coll %.2f dem %s fanT %s bus %4d kW unmet %d' %
              (tt, r['u'], r['z'], r['pitch'], r['alpha'], r['roll'], r['beta'], r['hdg'], r['coll'], r['dem'], r['fanT'], r['bus_kw'], r['unmet_kw']))
dec = [(L[i]['u'] - L[i+20]['u']) / (L[i+20]['t'] - L[i]['t']) / 9.80665 for i in range(0, len(L) - 20, 20)]
print(f'  end t+{L[-1]["t"]-t0:.1f}s: turn at t+{(st["turn"] or t0)-t0:.1f}s; peak decel {max(dec):.2f} g; pitch range {min(r["pitch"] for r in L):+.1f}..{max(r["pitch"] for r in L):+.1f}; |beta| max {max(abs(r["beta"]) for r in L):.1f}; z range {min(r["z"] for r in L):+.1f}..{max(r["z"] for r in L):+.1f}')
