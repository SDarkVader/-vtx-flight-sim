"""Rerun R1: take-off rolls on the plant with the hull lift and road suspension overlays (same schedule as T4:
full stick in rate_damping from 70 m/s; after 0.5 s wheels-off, attitude hold 5 deg nose-up)."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
tag = sys.argv[2]
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.}}}
P8 = {'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}}
BUF = {'buffer': {'position_m': {'v': [0.5, 0., 0.42]}}}
def mk(*names, extra):
    return overlays.load(*names, extra=extra)
OV = {'asflown_hull_susp': mk('hull_lift_v1', 'road_suspension_v1', extra=P6),
      'asflown_susp': mk('road_suspension_v1', extra=P6),
      'p8_hull_susp': mk('hull_lift_v1', 'road_suspension_v1', extra=P8),
      'p8_buf05_hull_susp': mk('hull_lift_v1', 'road_suspension_v1', extra={**P8, **BUF}),
      'r4_asflown_all': mk('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1', extra=P6),
      'r4_p8_all': mk('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1', extra=P8),
      'r4_p8_buf05_all': mk('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1', extra={**P8, **BUF}),
      'r4_p8_drive_only': mk('wheel_drive_limits_v1', extra=P8)}[tag]
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data
mp = a.mass_properties(); W = mp['mass_kg'] * 9.80665
print(tag, 'mass', round(mp['mass_kg'], 1), 'x_cg', round(mp['cg_body_m'][0], 3), 'config', a.P.config_sha256[:8]); sys.stdout.flush()
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
t0 = float(d.time); x0 = float(d.qpos[0])
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='rate_damping', pitch=0.0))
st = dict(rot=None, off=None, air_since=None, hold=False); log = []; f6 = np.zeros(6)
def watch(a):
    t = float(d.time) - t0; u = float(a.vel_body()[0]); th = math.degrees(a.attitude()['pitch_up']); z = float(d.qpos[2]); sup = a.support_count()
    S = {o['name']: o for o in a.aero_out['surfaces']}
    tyre = {}
    for i in range(d.ncon):
        c = d.contact[i]
        for g in (c.geom1, c.geom2):
            n = m.geom(g).name
            if n.startswith('tyre_'): mj.mj_contactForce(m, d, i, f6); tyre[n[5:]] = tyre.get(n[5:], 0) + f6[0]
    r = dict(t=round(t, 2), u=round(u, 1), pitch=round(th, 2), z=round(z, 3), sup=sup, a_w=round(S['wing_left'].get('alpha_deg', 0), 1),
             q=round(math.degrees(a.rates_body()[1]), 1), dem=round((a.fcc.last or {}).get('moment_demand', [0, 0, 0])[1], 2),
             lift=round(a.aero_out['force_body'][2]), hull=round(S['hull_lift']['pitch_force_n']) if 'hull_lift' in S else None, susp_all=[round(a.joint(f'pod_{k}_susp')[0], 3) for k in ('FL','FR','RL','RR')] if 'pod_FL_susp' in a.jid else None, spin=[round(abs(a.joint(f'pod_{k}_wheel')[1])) for k in ('FL','RL')],
             Nf=round(tyre.get('FL', 0) + tyre.get('FR', 0)), Nr=round(tyre.get('RL', 0) + tyre.get('RR', 0)),
             susp=[round(a.joint(f'pod_{k}_susp')[0], 3) for k in ('FL', 'RL')] if 'pod_FL_susp' in a.jid else None, crashed=a.crashed, x=round(float(d.qpos[0]) - x0),
             beta=round(math.degrees(math.atan2(-a.vel_body()[1], max(abs(u), 1e-3))), 2), roll=round(math.degrees(a.attitude()['roll']), 1))
    log.append(r)
    if st['rot'] is None and u >= 70: st['rot'] = t; a.set_command(dict(pitch=1.0))
    if st['rot'] is not None and 'rot1' not in st and th > 1.0: st['rot1'] = (round(t, 1), round(u, 1))
    if sup == 0:
        st['air_since'] = st['air_since'] if st['air_since'] is not None else t
        if st['off'] is None and t - st['air_since'] > 0.5:
            st['off'] = (round(st['air_since'], 1), round(u, 1), round(float(d.qpos[0]) - x0))
            a.set_command(dict(stability_mode='attitude', pitch=0.5)); st['hold'] = True
    else: st['air_since'] = None
    if st['off'] is not None and t - st['off'][0] > 15: return True
    return u > 125 or float(d.qpos[0]) > 3900 or a.crashed or abs(th) > 60 or (t > 150)
C.run(a, 160, every=0.1, stop=watch)
res = dict(tag=tag, config=a.P.config_sha256[:8], x_cg=round(mp['cg_body_m'][0], 3), rotation_pitch_gt_1deg=st.get('rot1'), wheels_off=st['off'],
           max_pitch=max(r['pitch'] for r in log), min_pitch=min(r['pitch'] for r in log), max_z=max(r['z'] for r in log), crashed=a.crashed,
           events=[e for e in a.events if e.get('event') in ('touchdown', 'hard_landing', 'collision')][-4:], end=log[-1])
json.dump(dict(res=res, log=log), open(f'{sys.argv[1]}/r1_{tag}.json', 'w'), default=float)
print(json.dumps(res, default=float))
