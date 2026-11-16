"""Measure the simulated tyre's lateral force vs toe angle: road stance, rolling at ~30 m/s, front wheels steered in
opposite directions (toe) by a fixed small angle while the FCC steering law is bypassed."""
import sys, math
root = sys.argv[1]; sys.path.insert(0, root + '/src')
import numpy as np, mujoco
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS
from vtx.world import make_world
w = make_world('airport'); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
a.spawn(-700.0, 0.0, w.surface_z(-700.0, 0.0)); m, d = a.model, a.data
a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, stability_mode='rate_damping'))
while float(a.vel_body()[0]) < 30.0: a.step()
a.set_command(dict(wheel_drive=[0.25] * 4))
a.effector_update = lambda dt, c, v: None          # hold whatever steer targets we set
tyre = {k: a.gid[f'tyre_{k}'] for k in PODS}; f6 = np.zeros(6)
def lat():
    Y = {k: 0.0 for k in PODS}; N = {k: 0.0 for k in PODS}; left = a.R()[:, 1]; npts = {k: 0 for k in PODS}
    for i in range(d.ncon):
        c = d.contact[i]
        for k in PODS:
            if c.geom1 == tyre[k] or c.geom2 == tyre[k]:
                mujoco.mj_contactForce(m, d, i, f6); fr = np.array(c.frame).reshape(3, 3)
                fw = (f6[0] * fr[0] + f6[1] * fr[1] + f6[2] * fr[2]) * (-1.0 if c.geom1 == tyre[k] else 1.0)
                Y[k] += float(fw @ left); N[k] += float(fw[2]); npts[k] += 1
    return Y, N, npts
print('toe per front wheel (deg) | u m/s | lateral N FL FR | normal N FL FR | contacts FL FR | F_lat/N | implied stiffness N per rad (FL)')
for toe_deg in (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0):
    a.targets['pod_FL_steer'] = -math.radians(toe_deg); a.targets['pod_FR_steer'] = math.radians(toe_deg)   # toe-out pair
    for _ in range(int(1.5 / DT)): a.step()
    acc = np.zeros(2); accN = np.zeros(2); n = 0
    for _ in range(int(0.5 / DT)):
        a.step()
        if a.step_count % 4 == 0:
            Y, N, npts = lat(); acc += [Y['FL'], Y['FR']]; accN += [N['FL'], N['FR']]; n += 1
    Y = acc / n; N = accN / n
    st = [math.degrees(a.joint(f'pod_{k}_steer')[0]) for k in ('FL', 'FR')]
    print(f'{toe_deg:6.3f} (actual {st[0]:6.3f} {st[1]:6.3f}) | {float(a.vel_body()[0]):5.1f} | {Y[0]:7.0f} {Y[1]:7.0f} | {N[0]:6.0f} {N[1]:6.0f} | {npts["FL"]} {npts["FR"]} | {abs(Y[0])/max(N[0],1):.2f} | {abs(Y[0])/max(math.radians(abs(st[0])),1e-9):.3g}')
