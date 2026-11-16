"""Do the canards keep the A10-C straight on take-off? Full-thrust take-off schedule (full drive, both boosters, wings and
flaps out, attitude hold, rotate at 55 m/s) with the canards: deployed under the flight computer | folded | held at -20 deg
(full nose-down) | held at +25 deg (full nose-up). Logs wheel loads, pitch, track; then a yaw-stick pulse (+0.3 for 1.5 s)
at 60 m/s to measure how much steering the aircraft has left when the wing is carrying most of the weight.
Usage: python takeoff.py <repo_root> <case> [pulse=0.3]"""
import sys, math
root = sys.argv[1]; case = sys.argv[2]; opts = dict(a.split('=') for a in sys.argv[3:])
sys.path.insert(0, root + '/src')
import numpy as np, mujoco
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS, SIDE
from vtx.world import make_world
w = make_world('airport'); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
x0 = -700.0; a.spawn(x0, 0.0, w.surface_z(x0, 0.0)); m, d = a.model, a.data; z0 = float(d.qpos[2])
tyre = {k: a.gid[f'tyre_{k}'] for k in PODS}; f6 = np.zeros(6)
def loads():
    N = np.zeros(4); Y = np.zeros(4); left = a.R()[:, 1]
    for i in range(d.ncon):
        c = d.contact[i]
        for j, k in enumerate(PODS):
            if c.geom1 == tyre[k] or c.geom2 == tyre[k]:
                mujoco.mj_contactForce(m, d, i, f6); fr = np.array(c.frame).reshape(3, 3)
                fw = (f6[0] * fr[0] + f6[1] * fr[1] + f6[2] * fr[2]) * (-1.0 if c.geom1 == tyre[k] else 1.0)
                N[j] += fw[2]; Y[j] += float(fw @ left)
    return N, Y
a.set_command(dict(brake=[1.0] * 4)); 
for _ in range(int(1.0 / DT)): a.step()
canard_fold = 'folded' if case == 'folded' else 'deployed'
trim = {'deployed': [0.0, 0.0], 'folded': [0.0, 0.0], 'down': [-20.0, -20.0], 'up': [25.0, 25.0]}[case]
a.set_command(dict(wing='deploy', canard_fold=canard_fold, flap_deg=[30.0, 30.0], canard_pitch_deg=trim))
for _ in range(int(10.0 / DT)): a.step()
a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0], stability_mode='attitude', pitch=0.0, roll=0.0, yaw=0.0, collective=0.0))
t_go = float(d.time); pulse = float(opts.get('pulse', 0.3)); pulse_t = None; rotated = False; off = None
print(f'case={case} canard_fold={canard_fold} trim={trim} nose_lift={a.nose_lift:.2f} pitch={math.degrees(a.attitude()["pitch_up"]):.2f}')
print('   t     u   pitch  yaw   r(d/s)   y   | N FL FR RL RR | lat FL FR RL RR | canard L R deg | canard Fz N | steer FL FR | tilt RL RR | note')
nxt = 0.0
while d.time - t_go < 40.0 and not a.crashed:
    a.step(); u = float(a.vel_body()[0]); t = d.time - t_go
    if not rotated and u >= 55.0:
        rotated = True; a.set_command(dict(pitch=0.7))
    if pulse_t is None and u >= 60.0 and not rotated:
        pass
    if pulse_t is None and u >= 60.0:
        pulse_t = t; a.set_command(dict(yaw=pulse))
    if pulse_t is not None and t - pulse_t >= 1.5 and a.fcc.cmd['yaw'] != 0.0:
        a.set_command(dict(yaw=0.0))
    if off is None and a.support_count() == 0 and float(d.qpos[2]) - z0 > 0.5:
        off = (t, u, float(d.qpos[0]) - x0, float(d.qpos[1]), math.degrees(a.attitude()['yaw_left'])); a.set_command(dict(wheel_drive=[0.0] * 4))
    if t >= nxt or (pulse_t is not None and t - pulse_t < 4.0 and abs(t - round(t * 2) / 2) < DT / 2):
        nxt += 2.0
        N, Y = loads(); att = a.attitude(); r = a.rates_body()
        cz = sum(s['force_n'][2] for s in a.aero_out['surfaces'] if s['name'].startswith('canard') and s.get('active'))
        can = [math.degrees(a.joint(f'canard_{s}')[0]) for s in ('left', 'right')]
        st = [math.degrees(a.joint(f'pod_{k}_steer')[0]) for k in ('FL', 'FR')]
        tilt = [math.degrees(a.joint(f'pod_{k}')[0]) * SIDE[k] for k in ('RL', 'RR')]
        note = 'PULSE' if pulse_t is not None and t - pulse_t < 1.5 else ('rotate' if rotated and off is None else ('AIRBORNE' if off else ''))
        print(f'{t:5.1f} {u:5.1f} {math.degrees(att["pitch_up"]):6.2f} {math.degrees(att["yaw_left"]):6.2f} {math.degrees(r[2]):6.2f} {float(d.qpos[1]):6.2f} | '
              + ' '.join(f'{v:5.0f}' for v in N) + ' | ' + ' '.join(f'{v:5.0f}' for v in Y) + f' | {can[0]:6.1f} {can[1]:6.1f} | {cz:6.0f} | {st[0]:6.2f} {st[1]:6.2f} | {tilt[0]:5.2f} {tilt[1]:5.2f} | {note}')
    if off and t - off[0] > 6.0: break
print(f'LIFT-OFF: {off}  crashed={a.crashed}  final yaw={math.degrees(a.attitude()["yaw_left"]):.2f} y={float(d.qpos[1]):.2f}')
