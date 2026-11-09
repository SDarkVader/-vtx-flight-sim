"""Test 5 (from T4): who carries the load after 'lift-off' with 7 deg incidence? Log every ground contact by geom."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp as C
OV = {'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}}
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
t0 = float(d.time); W = a.mass_properties()['mass_kg'] * 9.80665
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='rate_damping', pitch=0.0))
rows = []; f6 = np.zeros(6); st = {'rot': False}
def watch(a):
    t = float(d.time) - t0; u = float(a.vel_body()[0])
    if not st['rot'] and u >= 70: st['rot'] = True; a.set_command(dict(pitch=1.0))
    if u > 85:
        cf = {}
        for i in range(d.ncon):
            c = d.contact[i]; g1, g2 = c.geom1, c.geom2
            if m.geom_bodyid[g1] != 0 and m.geom_bodyid[g2] != 0: continue
            g = g2 if m.geom_bodyid[g1] == 0 else g1
            mj.mj_contactForce(m, d, i, f6); n = m.geom(g).name or f'g{g}'
            cf[n] = cf.get(n, 0) + round(f6[0])
        Fb = a.aero_out['force_body']; Rb = a.R(); Fw = Rb @ Fb
        legs = [round(a.joint(f'leg_{k}')[0], 3) for k in ('FL', 'FR', 'RL', 'RR')]
        rows.append(dict(t=round(t, 2), u=round(u, 1), pitch=round(math.degrees(a.attitude()['pitch_up']), 2), z=round(float(d.qpos[2]), 3),
                         aero_up=round(Fw[2]), W=round(W), contacts=cf, legs=legs, fan_T=[round(s.get('thrust_n', 0)) for s in a.fan_state],
                         boost_up=round(sum(s.get('thrust_n', 0) for s in a.booster_state) * (Rb @ [1, 0, 0])[2])))
    return a.crashed or (rows and rows[-1]['pitch'] < -10) or u > 125
C.run(a, 80, every=0.05, stop=watch)
json.dump(rows, open(sys.argv[1] + '/t5.json', 'w'))
hull = [r for r in rows if any(not k.startswith(('tyre_', 'foot_')) for k in r['contacts'])]
print('samples', len(rows), '| samples with non-tyre ground contact', len(hull))
for r in rows[::8] + rows[-6:]:
    print('t%6.2f u%6.1f pitch%6.2f z%6.3f aero_up%6d W%d boost_up%5d fans%s legs%s contacts %s' % (r['t'], r['u'], r['pitch'], r['z'], r['aero_up'], r['W'], r['boost_up'], r['fan_T'], r['legs'], r['contacts']))
