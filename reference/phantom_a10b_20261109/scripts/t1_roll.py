"""Test 1: instrumented take-off roll, live A10 build 70089cca. Pitch moments about the rear tyre contact."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp as C
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
ov = None if (len(sys.argv) > 2 and sys.argv[2] == 'noP6') else P6
a = C.plant('phantom-fx', ov, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='attitude', pitch=0.0))
g = 9.80665; ab = a.bids['airframe']; rotated = False; rows = []; prev = None
def nose_up(r, F, P):   # nose-up moment about P, around the body lateral axis
    M = np.cross(r - P, F); return float(-(M @ (a.R() @ np.array([0, 1., 0]))))
def snap():
    global prev
    Rb = a.R(); mp = a.mass_properties(); cg = np.array(mp['cg_world_m']); M = mp['mass_kg']
    tyres = {}
    f6 = np.zeros(6)
    for i in range(d.ncon):
        c = d.contact[i]
        for gi in (c.geom1, c.geom2):
            n = m.geom(gi).name
            if n.startswith('tyre_'):
                mj.mj_contactForce(m, d, i, f6)
                fw = c.frame.reshape(3, 3).T @ f6[:3]
                if gi == c.geom1: fw = -fw
                t = tyres.setdefault(n[5:], dict(fz=0.0, pos=np.zeros(3), F=np.zeros(3)))
                t['fz'] += fw[2]; t['F'] += fw; t['pos'] = np.array(c.pos)
    rear = [t['pos'] for k, t in tyres.items() if k.startswith('R')]
    P = np.mean(rear, axis=0) if rear else cg
    comp = {}
    comp['weight'] = nose_up(cg, np.array([0, 0, -M*g]), P)
    org = d.xpos[ab]
    for s, o in zip(a.aero.surfaces, [x for x in a.aero_out['surfaces'] if not x['name'].startswith(('flap', 'aileron', 'body'))]):
        comp['aero_'+s.name] = nose_up(org + Rb @ s.ac, Rb @ np.array(o['force_n']), P)
    flap = 0.0
    for o in a.aero_out['surfaces']:
        if o['name'].startswith(('flap', 'aileron')) and o.get('locked'):
            st = a.aero.strips[o['name']]; flap += nose_up(org + Rb @ st['pos'], Rb @ np.array(o['force_n']), P)
        if o['name'] == 'body':
            comp['aero_body_drag'] = nose_up(org + Rb @ a.aero.body_centre, Rb @ np.array(o['force_n']), P)
    comp['aero_flap_ail'] = flap
    bt = 0.0; dang = math.radians(a.P['proposals.p3_booster_vector_angle_deg'])
    for j, s in enumerate(('left', 'right')):
        b = a.bids[f'booster_{s}_rotor']; bt += nose_up(d.xpos[b], a.booster_state[j].get('thrust_n', 0)*(Rb @ np.array([math.cos(dang), 0, math.sin(dang)])), P)
    comp['boosters'] = bt
    comp['fans'] = sum(nose_up(d.xpos[a.bids[f'pod_{k}_fan']], a.fan_state[i].get('thrust_n', 0)*a.pod_axis(k), P) for i, k in enumerate(C.PODS if hasattr(C,'PODS') else ['FL','FR','RL','RR']))
    v = d.subtree_linvel[ab].copy(); t = float(d.time)
    acc = (v - prev[1])/(t - prev[0]) if prev else np.zeros(3); prev = (t, v)
    comp['inertia_(-ma)'] = nose_up(cg, -M*acc, P)
    front_tyre = {k: t['F'] for k, t in tyres.items() if k.startswith('F')}
    comp['front_tyres'] = sum(nose_up(tyres[k]['pos'], f, P) for k, f in front_tyre.items())
    fl = a.fcc.last or {}
    return dict(t=round(t, 2), u=round(float(a.vel_body()[0]), 1), pitch=round(math.degrees(a.attitude()['pitch_up']), 2),
                Nf=round(sum(t['fz'] for k, t in tyres.items() if k.startswith('F'))), Nr=round(sum(t['fz'] for k, t in tyres.items() if k.startswith('R'))),
                demand=round(fl.get('moment_demand', [0, 0, 0])[1], 3), canard_deg=[round(math.degrees(a.joint(f'canard_{s}')[0]), 1) for s in ('left',)],
                stab_deg=round(math.degrees(a.stab_te_up), 1) if a.p6 else None,
                x_cg_minus_x_rear=round(float((Rb.T @ (cg - P))[0]), 3), h_cg=round(float(cg[2]-P[2]), 3),
                M={k: round(v_) for k, v_ in comp.items()}, M_sum_ex_front=round(sum(v_ for k, v_ in comp.items() if k != 'front_tyres')))
def watch(a):
    global rotated
    s = snap(); rows.append(s)
    if not rotated and s['u'] >= 70: rotated = True; a.set_command(dict(pitch=1.0))
    return s['u'] > 118 or float(d.qpos[0]) > 3900
C.run(a, 90, every=0.5, stop=watch)
json.dump(rows, open(sys.argv[1] + f'/t1_{"noP6" if ov is None else "P6"}.json', 'w'))
for s in rows[::6] + rows[-1:]:
    print(s['t'], s['u'], 'pitch', s['pitch'], 'Nf', s['Nf'], 'Nr', s['Nr'], 'dem', s['demand'], 'can', s['canard_deg'], 'stab', s['stab_deg'], '| sum', s['M_sum_ex_front'])
print('geometry: x_cg - x_rear', rows[-1]['x_cg_minus_x_rear'], 'h_cg', rows[-1]['h_cg'])
for s in (rows[len(rows)//3], rows[-1]): print(s['u'], json.dumps(s['M']))
