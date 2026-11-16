"""Headless diagnosis of the A10-C ground-roll veer. Usage: python diag.py <repo_root> case [key=value ...]
cases: base (take-off stance, drive 0.5, no boost, rate_damping) | attitude | pinned (pod tilt joints locked at 0: a
mechanical down-lock) | flat (wings out but no nose lift: tests the pitch coupling) | road (wings stowed) | full (drive 1, boost 1)
"""
import sys, math
root = sys.argv[1]; case = sys.argv[2]; opts = dict(a.split('=') for a in sys.argv[3:])
sys.path.insert(0, root + '/src')
import numpy as np, mujoco
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS, SIDE
from vtx.world import make_world

w = make_world('airport')
ov = {'suspension': {'nose_lift_m': {'v': 0.0}}} if case == 'flat' else None
a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road', overrides=ov)
x0 = -700.0; a.spawn(x0, 0.0, w.surface_z(x0, 0.0))
m, d = a.model, a.data
if case == 'pinned':
    for k in PODS:
        j = a.jid[f'pod_{k}']; m.jnt_range[j] = [-1e-5, 1e-5]
drive = float(opts.get('drive', 1.0 if case == 'full' else 0.5)); boost = float(opts.get('boost', 1.0 if case == 'full' else 0.0))
mode = 'attitude' if case == 'attitude' else opts.get('mode', 'rate_damping')
tmax = float(opts.get('t', 70)); umax = float(opts.get('umax', 46))
wings = case not in ('road',)
a.set_command(dict(brake=[1.0] * 4))
for _ in range(int(1.0 / DT)): a.step()
if wings:
    a.set_command(dict(wing='deploy', canard_fold='deployed', flap_deg=[30.0, 30.0]))
    for _ in range(int(10.0 / DT)): a.step()
a.set_command(dict(brake=[0.0] * 4, wheel_drive=[drive] * 4, booster_throttle=[boost, boost], stability_mode=mode, pitch=0.0, roll=0.0, yaw=0.0, collective=0.0))
t_go = float(d.time)
tyre_gid = {k: a.gid[f'tyre_{k}'] for k in PODS}
print(f'case={case} drive={drive} boost={boost} mode={mode} mass={float(sum(m.body_mass)):.0f} kg nose_lift={a.nose_lift:.3f} wings={a.wing_state} pitch={math.degrees(a.attitude()["pitch_up"]):.2f} deg')
print('   t     u    yaw    r(d/s)    y    | normal N FL FR RL RR | lateral N FL FR RL RR | pod tilt deg FL FR RL RR | servo Nm FL FR RL RR | toe deg FL FR RL RR | steer FL FR | hop frac')
hop = np.zeros(4); n_hop = 0
f6 = np.zeros(6)
def wheel_forces():
    N = np.zeros(4); Y = np.zeros(4)
    R = a.R(); left = R[:, 1]
    for i in range(d.ncon):
        c = d.contact[i]
        for j, k in enumerate(PODS):
            if c.geom1 == tyre_gid[k] or c.geom2 == tyre_gid[k]:
                mujoco.mj_contactForce(m, d, i, f6)
                fr = np.array(c.frame).reshape(3, 3)       # rows: normal, tangent1, tangent2 (world)
                fw = f6[0] * fr[0] + f6[1] * fr[1] + f6[2] * fr[2]
                sgn = -1.0 if c.geom1 == tyre_gid[k] else 1.0   # force on geom2 by geom1; make it the force on the tyre
                fw = sgn * fw
                N[j] += fw[2]; Y[j] += float(fw @ left)
    return N, Y
def toe_camber():
    R = a.R(); fwd = R[:, 0]; fh = np.array([fwd[0], fwd[1], 0]); fh /= np.linalg.norm(fh); lh = np.array([-fh[1], fh[0], 0])
    out = []
    for k in PODS:
        Rw = d.xmat[a.bids[f'pod_{k}_wheel']].reshape(3, 3); ax = Rw @ np.array([0, SIDE[k], 0.0])
        out.append(math.degrees(math.atan2(float(ax @ fh), float(ax @ lh))))   # + = axle points forward = wheel steered left (toe-in on the left side)
    return out
next_print = 0.0; crashed_at = None
while d.time - t_go < tmax and not a.crashed:
    a.step()
    if a.step_count % 20 == 0:
        N, Y = wheel_forces(); hop += (N < 1.0); n_hop += 1
    u = float(a.vel_body()[0])
    if d.time - t_go >= next_print:
        next_print += float(opts.get('dt', 1.0))
        N, Y = wheel_forces(); att = a.attitude(); r = a.rates_body()
        tilt = [math.degrees(a.joint(f'pod_{k}')[0]) * SIDE[k] for k in PODS]
        servo = [float(d.actuator_force[a.aid[f'act_pod_{k}']]) * SIDE[k] for k in PODS]
        toe = toe_camber()
        steer = [math.degrees(a.joint(f'pod_{k}_steer')[0]) for k in ('FL', 'FR')]
        print(f'{d.time - t_go:5.1f} {u:5.1f} {math.degrees(att["yaw_left"]):6.2f} {math.degrees(r[2]):6.2f} {float(d.qpos[1]):7.2f} | '
              + ' '.join(f'{v:5.0f}' for v in N) + ' | ' + ' '.join(f'{v:5.0f}' for v in Y) + ' | ' + ' '.join(f'{v:5.2f}' for v in tilt) + ' | '
              + ' '.join(f'{v:5.0f}' for v in servo) + ' | ' + ' '.join(f'{v:6.3f}' for v in toe) + ' | ' + ' '.join(f'{v:6.3f}' for v in steer) + ' | '
              + ' '.join(f'{v:4.2f}' for v in hop / max(n_hop, 1)))
    if u >= umax: break
print(f'END t={d.time - t_go:.1f} u={u:.1f} y={float(d.qpos[1]):.2f} yaw={math.degrees(a.attitude()["yaw_left"]):.2f} crashed={a.crashed} events={[e.get("event") for e in a.events][-6:]}')
