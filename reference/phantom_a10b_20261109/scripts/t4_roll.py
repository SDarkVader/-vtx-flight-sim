"""Test 4: dynamic take-off rolls (from T3): full stick in rate_damping at 70 m/s; variants by override."""
import sys, json, math, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
tag = sys.argv[2]
OV = {'asflown': {'proposals': {'p6_drs_stabilator': {'v': 1.}}},
      'p8_7deg': {'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}},
      'p8_7deg_buf05': {'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}, 'buffer': {'position_m': {'v': [0.5, 0., 0.42]}}}}[tag]
a = C.plant('phantom-fx', OV, start_configuration='road'); d = a.data
mp = a.mass_properties(); print(tag, 'mass', round(mp['mass_kg'], 1), 'x_cg', round(mp['cg_body_m'][0], 3), 'config', a.P.config_sha256[:8]); sys.stdout.flush()
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
t0 = float(d.time); x0 = float(d.qpos[0])
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='rate_damping', pitch=0.0))
st = dict(rot=None, off=None, air_since=None, after=[]); log = []
def watch(a):
    t = float(d.time) - t0; u = float(a.vel_body()[0]); th = math.degrees(a.attitude()['pitch_up']); z = float(d.qpos[2]); sup = a.support_count()
    w = next((o for o in a.aero_out['surfaces'] if o['name'] == 'wing_left'), {})
    r = dict(t=round(t, 2), u=round(u, 1), pitch=round(th, 2), z=round(z, 2), sup=sup, alpha_wing=round(w.get('alpha_deg', 0), 1), q=round(math.degrees(a.rates_body()[1]), 1),
             dem=round((a.fcc.last or {}).get('moment_demand', [0, 0, 0])[1], 2), lift=round(a.aero_out['force_body'][2]), crashed=a.crashed, x=round(float(d.qpos[0]) - x0))
    log.append(r)
    if st['rot'] is None and u >= 70: st['rot'] = t; a.set_command(dict(pitch=1.0))
    if st['rot'] is not None and 'rot_pitch1' not in st and th > 1.0: st['rot_pitch1'] = (round(t, 1), round(u, 1))
    if sup == 0:
        st['air_since'] = st['air_since'] if st['air_since'] is not None else t
        if st['off'] is None and t - st['air_since'] > 0.5: st['off'] = (round(st['air_since'], 1), round(u, 1), round(float(d.qpos[0]) - x0))
    else: st['air_since'] = None
    if st['off'] is not None and t - st['off'][0] > 12: return True
    return u > 125 or float(d.qpos[0]) > 3900 or a.crashed
C.run(a, 100, every=0.1, stop=watch)
res = dict(tag=tag, rotation_start_pitch_gt_1deg=st.get('rot_pitch1'), liftoff=st['off'], max_pitch=max(r['pitch'] for r in log), crashed=a.crashed, events=[e for e in a.events][-5:])
if st['off']:
    air = [r for r in log if r['t'] >= st['off'][0]]
    res['after_liftoff'] = [(r['t'], r['u'], r['pitch'], r['alpha_wing'], r['z'], r['q'], r['sup']) for r in air[::10]]
else:
    res['end'] = log[-1]
json.dump(dict(res=res, log=log), open(f'{sys.argv[1]}/t4_{tag}.json', 'w'), default=float)
print(json.dumps(res, default=float))
