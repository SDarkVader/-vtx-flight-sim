"""R2 (from R1): is the 508 deg/s pitch-rate spike at lift-off physical? High-rate log of the p8_buf05 run around wheels-off:
suspension travel vs limits, joint-limit constraint forces, contact forces, body rates."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
OV = overlays.load('hull_lift_v1', 'road_suspension_v1', extra={'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}, 'buffer': {'position_m': {'v': [0.5, 0., 0.42]}}})
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
t0 = float(d.time)
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='rate_damping', pitch=0.0))
sj = {k: m.joint(f'pod_{k}_susp').id for k in ('FL', 'FR', 'RL', 'RR')}
rows = []; st = {'rot': False}; f6 = np.zeros(6)
def watch(a):
    t = float(d.time) - t0; u = float(a.vel_body()[0])
    if not st['rot'] and u >= 70: st['rot'] = True; a.set_command(dict(pitch=1.0))
    if t >= 24.3:
        lim = {}
        for i in range(d.nefc):
            if d.efc_type[i] == mj.mjtConstraint.mjCNSTR_LIMIT_JOINT:
                j = d.efc_id[i]; nm = m.joint(j).name; lim[nm] = round(float(d.efc_force[i]))
        tyre = {}
        for i in range(d.ncon):
            c = d.contact[i]
            for g in (c.geom1, c.geom2):
                n = m.geom(g).name
                if n.startswith('tyre_'): mj.mj_contactForce(m, d, i, f6); tyre[n[5:]] = tyre.get(n[5:], 0) + round(f6[0])
        rows.append(dict(t=round(t, 3), u=round(u, 1), pitch=round(math.degrees(a.attitude()['pitch_up']), 2), w_deg_s=np.round(np.degrees(a.rates_body()), 1).tolist(),
                         susp={k: round(float(d.qpos[m.jnt_qposadr[j]]), 4) for k, j in sj.items()}, susp_v={k: round(float(d.qvel[m.jnt_dofadr[j]]), 2) for k, j in sj.items()},
                         limits=lim, tyres=tyre, z=round(float(d.qpos[2]), 3), hull=round(next(o for o in a.aero_out['surfaces'] if o['name'] == 'hull_lift')['pitch_force_n'])))
    return t > 25.3 or a.crashed
C.run(a, 60, every=0.01, stop=watch)
json.dump(rows, open(sys.argv[1] + '/r2.json', 'w'))
pk = max(rows, key=lambda r: abs(r['w_deg_s'][1]))
print('peak |q|', pk['w_deg_s'], 'at t', pk['t'])
i = rows.index(pk)
for r in rows[max(0, i - 12):i + 6]:
    print(r['t'], 'pitch', r['pitch'], 'w', r['w_deg_s'], 'z', r['z'], 'susp', r['susp'], 'v', r['susp_v'], 'lim', r['limits'], 'tyres', r['tyres'])
