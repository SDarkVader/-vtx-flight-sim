"""V3 / TB on the phantom-a10b variant. 'turn_wb': wing-borne 90 deg turn at ~90 m/s, 45 deg bank, fans off, boosters on.
'turn_fan': fans facing down, decelerating from 95 m/s, 30 deg bank turn from 60 m/s, nose held at 4 deg.
'takeoff': standing start, no brakes, wings deployed from 0 m/s (guarded), attitude 5 deg from 70 m/s, climb."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom.geometry import PODS, SIDE
mode = sys.argv[2]
a = C.plant('phantom-a10b', None, start_configuration='road'); m, d = a.model, a.data; P = a.P
print(mode, 'config', P.config_sha256[:8], 'mass', round(a.mass_properties()['mass_kg'], 1)); sys.stdout.flush()
W = a.mass_properties()['mass_kg'] * 9.80665; log = []; st = dict(t0=None, hdg0=None, turn=None, done=None, off=None)
def rec(a, extra=None):
    t = float(d.time); att = a.attitude(); vb = a.vel_body(); b = a.bus.last or {}
    r = dict(t=round(t, 2), u=round(float(vb[0]), 2), z=round(float(d.qpos[2]), 2), x=round(float(d.qpos[0]), 1), y=round(float(d.qpos[1]), 1),
             pitch=round(math.degrees(att['pitch_up']), 2), roll=round(math.degrees(att['roll']), 2), hdg=round(math.degrees(att['yaw_left']), 2),
             alpha=round(math.degrees(math.atan2(-vb[2], max(abs(vb[0]), 1e-3))), 2), beta=round(math.degrees(math.atan2(vb[1], max(abs(vb[0]), 1e-3))), 2),
             sup=a.support_count(), dem=[round(x, 2) for x in (a.fcc.last or {}).get('moment_demand', [0, 0, 0])],
             tvc=[round(math.degrees(x), 1) for x in a.tvc], rud=round(math.degrees(a.rudder), 1), fanT=[round(s.get('thrust_n', 0)) for s in a.fan_state],
             bus_kw=round(b.get('delivered_w', 0) / 1e3), unmet=round(b.get('unmet_w', 0) / 1e3))
    if extra: r.update(extra)
    log.append(r); return r
def airborne(V0, theta, fans):
    a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
    d.qpos[2] += 300.0; d.qpos[3:7] = [math.cos(math.radians(theta) / 2), 0, -math.sin(math.radians(theta) / 2), 0]
    d.qvel[:] = 0.0; d.qvel[0] = V0
    if fans:
        for k in PODS:
            a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
            d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * a.fan.omega_for_thrust(0.05 * W / 4)
    a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power)
    mj.mj_forward(m, d)
if mode == 'turn_wb':
    airborne(90.0, 3.5, False); z_ref = float(d.qpos[2])
    a.set_command(dict(stability_mode='attitude', pitch=0.35, collective=0.0, booster_throttle=[1., 1.], wheel_drive=[0.]*4, brake=[0.]*4, pod_tilt_deg=[0.]*4, flap_deg=[0., 0.]))
    def pilot(a):
        r = rec(a); t = r['t']
        if st['t0'] is None: st['t0'] = t
        if st['turn'] is None and t - st['t0'] > 3.0:
            st['turn'] = t; st['hdg0'] = r['hdg']; a.set_command(dict(roll=1.0))
        if st['turn'] is not None:
            # pitch attitude raised with bank to hold altitude (test pilot), yaw rate commanded for coordination
            ph = math.radians(max(abs(r['roll']), 1.0)); a.set_command(dict(pitch=float(np.clip(0.35 + 0.05 * (z_ref - r['z']) + 0.3 * (1 / math.cos(ph) - 1), -1, 1)),
                                                                            yaw=float(np.clip(math.degrees(9.80665 * math.tan(ph) / max(r['u'], 20)) / 20.0, 0, 1))))
            if st['done'] is None and abs(r['hdg'] - st['hdg0']) >= 90.0: st['done'] = t
        return abs(r['pitch']) > 60 or abs(r['roll']) > 80 or a.crashed or (st['done'] and t > st['done'] + 2) or t - st['t0'] > 90
elif mode == 'turn_fan':
    airborne(95.0, 4.0, True); z_ref = float(d.qpos[2])
    a.set_command(dict(stability_mode='attitude', pitch=0.4, collective=0.05, booster_throttle=[0., 0.], wheel_drive=[0.]*4, brake=[0.]*4, pod_tilt_deg=[90.]*4, flap_deg=[0., 0.]))
    def pilot(a):
        r = rec(a); t = r['t']; vz = float(d.qvel[2])
        if st['t0'] is None: st['t0'] = t
        a.set_command(dict(collective=float(np.clip(0.71 * (1 - min(1, (r['u'] / 95.0) ** 2)) / max(math.cos(math.radians(r['roll'])), 0.5) + 0.03 + 0.03 * (z_ref - r['z']) - 0.08 * vz, 0, 1))))
        if st['turn'] is None and r['u'] < 60.0:
            st['turn'] = t; st['hdg0'] = r['hdg']; a.set_command(dict(roll=30.0 / 45.0))
        if st['turn'] is not None:
            ph = math.radians(max(abs(r['roll']), 1.0)); a.set_command(dict(yaw=float(np.clip(math.degrees(9.80665 * math.tan(ph) / max(r['u'], 15)) / 20.0, 0, 1))))
            if st['done'] is None and abs(r['hdg'] - st['hdg0']) >= 90.0: st['done'] = t
        return abs(r['pitch']) > 60 or abs(r['roll']) > 80 or a.crashed or (st['done'] and t > st['done'] + 2) or t - st['t0'] > 60
else:   # takeoff
    a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], wing='deploy', canard_fold='deployed', flap_deg=[30., 30.], stability_mode='attitude', pitch=0.0))
    def pilot(a):
        r = rec(a, dict(state=a.wing_state['left'])); t = r['t']
        if st['t0'] is None: st['t0'] = t; st['x0'] = r['x']
        if st['turn'] is None and r['u'] >= 70.0: st['turn'] = t; a.set_command(dict(pitch=0.5))
        if st['off'] is None and r['sup'] == 0 and r['u'] > 40:
            st['off'] = (round(t - st['t0'], 1), r['u'], round(r['x'] - st['x0']))
        if st['off'] is not None and r['sup'] == 0: a.set_command(dict(wheel_drive=[0.]*4))
        return abs(r['pitch']) > 60 or a.crashed or (st['off'] and t - st['t0'] > st['off'][0] + 30) or r['x'] > 3900 or t - st['t0'] > 150
C.run(a, 200, every=0.05, stop=pilot)
json.dump(dict(st={k: v for k, v in st.items()}, log=log), open(f'{sys.argv[1]}/v3_{mode}.json', 'w'), default=float)
L = log; t0 = L[0]['t']
if mode.startswith('turn'):
    tt = st['turn']; seg = [r for r in L if tt and r['t'] >= tt and (st['done'] is None or r['t'] <= st['done'])]
    if seg:
        import numpy as np
        xy = np.array([[r['x'], r['y']] for r in seg]); arc = float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))
        print(f"  turn: heading change {seg[-1]['hdg']-seg[0]['hdg']:+.1f} deg in {seg[-1]['t']-seg[0]['t']:.1f} s; arc {arc:.0f} m; speed {seg[0]['u']:.1f}->{seg[-1]['u']:.1f} m/s; "
              f"bank max {max(abs(r['roll']) for r in seg):.1f}; |beta| max {max(abs(r['beta']) for r in seg):.1f}; pitch {min(r['pitch'] for r in seg):+.1f}..{max(r['pitch'] for r in seg):+.1f}; "
              f"alt change {seg[-1]['z']-seg[0]['z']:+.1f} m; completed 90: {st['done'] is not None}")
    else:
        print('  no turn segment', L[-1])
else:
    print('  liftoff', st['off'], '| max height', round(max(r['z'] for r in L) - L[0]['z'], 1), '| pitch range', min(r['pitch'] for r in L), max(r['pitch'] for r in L),
          '| end', {k: L[-1][k] for k in ('u', 'pitch', 'z', 'sup', 'dem', 'tvc')})
    wl = [r for r in L if r.get('state') == 'locked']
    print('  wings locked at', (wl[0]['t'] - t0, wl[0]['u']) if wl else None)
for r in L[::max(1, len(L) // 14)]:
    print('   t+%5.1f u %6.1f z %+7.1f pitch %+6.1f alpha %+6.1f roll %+6.1f beta %+5.1f hdg %+7.1f sup %d dem %s tvc %s rud %+5.1f fanT %s bus %d' %
          (r['t'] - t0, r['u'], r['z'] - L[0]['z'], r['pitch'], r['alpha'], r['roll'], r['beta'], r['hdg'], r['sup'], r['dem'], r['tvc'], r['rud'], r['fanT'], r['bus_kw']))
