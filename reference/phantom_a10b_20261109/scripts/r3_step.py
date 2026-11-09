"""R3 (from R2): per-physics-step log of the FL wheel event at t ~24.81 s: every contact touching the FL wheel or any
vehicle geom, its penetration and force, FL slide joint state, FL wheel spin."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
OV = overlays.load('hull_lift_v1', 'road_suspension_v1', extra={'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}, 'buffer': {'position_m': {'v': [0.5, 0., 0.42]}}})
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
t0 = float(d.time)
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='rate_damping', pitch=0.0))
st = {'rot': False}; rows = []; f6 = np.zeros(6)
jq = m.jnt_qposadr[m.joint('pod_FL_susp').id]; jv = m.jnt_dofadr[m.joint('pod_FL_susp').id]; wv = m.jnt_dofadr[m.joint('pod_FL_wheel').id]
tq = m.jnt_qposadr[m.joint('pod_FL').id]
def watch(a):
    t = float(d.time) - t0; u = float(a.vel_body()[0])
    if not st['rot'] and u >= 70: st['rot'] = True; a.set_command(dict(pitch=1.0))
    if 24.795 <= t <= 24.825:
        cons = []
        for i in range(d.ncon):
            c = d.contact[i]; n1, n2 = m.geom(c.geom1).name, m.geom(c.geom2).name
            if 'FL' in n1 + n2 or (m.geom_bodyid[c.geom1] != 0 and m.geom_bodyid[c.geom2] != 0):
                mj.mj_contactForce(m, d, i, f6); cons.append((n1, n2, round(float(c.dist), 4), round(float(f6[0]))))
        rows.append(dict(t=round(t, 4), q=round(float(d.qpos[jq]), 4), v=round(float(d.qvel[jv]), 3), spin=round(float(d.qvel[wv]), 1),
                         pod_tilt_deg=round(math.degrees(float(d.qpos[tq])), 3), act_force=round(float(d.qfrc_actuator[jv]), 1),
                         cons=cons, ncon=d.ncon))
    return t > 24.83 or a.crashed
C.run(a, 60, every=0.0025, stop=watch)
for r in rows: print(r)
