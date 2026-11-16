"""Take-off roll with battery-assisted wheel drive. Full-thrust schedule otherwise (wings, canards, flaps 30, attitude
hold, rotate at 55 m/s). Cases: jets on/off x hub-motor rating multiplier (torque and power scaled together).
Usage: python wheelpower.py <repo_root> <jets 0|1> <mult> [mode]"""
import sys, math
root = sys.argv[1]; jets = int(sys.argv[2]); mult = float(sys.argv[3]); mode = sys.argv[4] if len(sys.argv) > 4 else 'auto'
sys.path.insert(0, root + '/src')
import numpy as np, mujoco
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS
from vtx.world import make_world
w = make_world('airport')
ov = {'pods': {'hub_motor_torque_nm': {'v': 600.0 * mult}, 'hub_motor_power_w': {'v': 60000.0 * mult}}}
a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road', overrides=ov)
x0 = -700.0; a.spawn(x0, 0.0, w.surface_z(x0, 0.0)); m, d = a.model, a.data; z0 = float(d.qpos[2])
tyre = {k: a.gid[f'tyre_{k}'] for k in PODS}; f6 = np.zeros(6)
def loads():
    N = np.zeros(4); X = np.zeros(4); fwd = a.R()[:, 0]
    for i in range(d.ncon):
        c = d.contact[i]
        for j, k in enumerate(PODS):
            if c.geom1 == tyre[k] or c.geom2 == tyre[k]:
                mujoco.mj_contactForce(m, d, i, f6); fr = np.array(c.frame).reshape(3, 3)
                fw = (f6[0] * fr[0] + f6[1] * fr[1] + f6[2] * fr[2]) * (-1.0 if c.geom1 == tyre[k] else 1.0)
                N[j] += fw[2]; X[j] += float(fw @ fwd)
    return N, X
a.set_command(dict(brake=[1.0] * 4))
for _ in range(int(1.0 / DT)): a.step()
a.set_command(dict(wing='deploy', canard_fold='deployed', flap_deg=[30.0, 30.0]))
for _ in range(int(10.0 / DT)): a.step()
soc0 = a.bus.soc; E0 = dict(a.bus.energy)
a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[float(jets), float(jets)], stability_mode=mode, pitch=0.0, roll=0.0, yaw=0.0, collective=0.0))
t_go = float(d.time); rotated = False; off = None; nxt = 0.0; peak_buf = 0.0; peak_hub = 0.0; max_slip = 0.0; hub = 0.0; clear_since = None; max_y = 0.0; max_yaw = 0.0
print(f'jets={jets} hub rating x{mult}: {600*mult:.0f} N m, {60*mult:.0f} kW per wheel; mode={mode}; buffer soc0={soc0:.3f}')
print('   t     u   pitch   x m   yaw    y  | N FL FR RL RR | tractive X FL FR RL RR | wheel slip % | hub kW | gen kW | buffer kW | soc | jets N')
while d.time - t_go < 60.0 and not a.crashed:
    a.step(); u = float(a.vel_body()[0]); t = d.time - t_go
    if not rotated and u >= 55.0:
        rotated = True; a.set_command(dict(pitch=0.7))
    if a.support_count() == 0:
        clear_since = t if clear_since is None else clear_since
    else:
        clear_since = None
    if off is None and clear_since is not None and t - clear_since >= 1.0 and float(d.qpos[2]) - z0 > 1.0 and float(d.qvel[2]) > 0:
        off = (round(clear_since, 1), round(u, 1), round(float(d.qpos[0]) - x0), round(a.bus.soc, 4)); a.set_command(dict(wheel_drive=[0.0] * 4))
    if off is None:
        max_y = max(max_y, abs(float(d.qpos[1]))); max_yaw = max(max_yaw, abs(math.degrees(a.attitude()['yaw_left'])))
    if a.step_count % 4 == 0:
        L = a.bus.last; peak_buf = max(peak_buf, L.get('buffer_w', 0)); 
        hub = sum(abs(a.wheel_drive_torque(a.fcc.cmd)[i] * a.joint(f'pod_{k}_wheel')[1]) for i, k in enumerate(PODS)) / 0.9; peak_hub = max(peak_hub, hub)
        slips = [(abs(a.joint(f'pod_{k}_wheel')[1]) * 0.55 - u) / max(u, 2.0) for k in PODS]; max_slip = max(max_slip, max(slips)) if u > 5 else max_slip
    if t >= nxt and off is None:
        nxt += 2.0; N, X = loads(); L = a.bus.last
        slips = [(abs(a.joint(f'pod_{k}_wheel')[1]) * 0.55 - u) / max(u, 2.0) * 100 for k in PODS]
        jet = sum(s.get('thrust_n', 0) for s in a.booster_state)
        print(f'{t:5.1f} {u:5.1f} {math.degrees(a.attitude()["pitch_up"]):6.2f} {float(d.qpos[0]) - x0:6.0f} {math.degrees(a.attitude()["yaw_left"]):6.2f} {float(d.qpos[1]):6.2f} | ' + ' '.join(f'{v:5.0f}' for v in N) + ' | ' + ' '.join(f'{v:5.0f}' for v in X)
              + ' | ' + ' '.join(f'{v:4.1f}' for v in slips) + f' | {hub/1000:6.0f} | {L.get("generator_w",0)/1000:6.0f} | {L.get("buffer_w",0)/1000:7.0f} | {a.bus.soc:.3f} | {jet:5.0f}')
    if off and t - off[0] > 8.0: break
E = a.bus.energy
print(f'LIFT-OFF (t s, u m/s, x m, soc)={off} crashed={a.crashed} end: u={u:.1f} climb={float(d.qvel[2]):.1f} m/s h={float(d.qpos[2]) - z0:.1f} m | on the ground: max |y| {max_y:.1f} m, max |yaw| {max_yaw:.2f} deg | peak buffer {peak_buf/1000:.0f} kW, peak hub {peak_hub/1000:.0f} kW, max slip {max_slip*100:.1f} %, '
      f'buffer energy out {(E["buffer_out_j"]-E0["buffer_out_j"])/3.6e6:.2f} kWh, generator {(E["generator_j"]-E0["generator_j"])/3.6e6:.2f} kWh, fuel {(E["fuel_kg"]-E0["fuel_kg"]) + float(a.fuel_initial.sum()-a.fuel.sum()) - (E["fuel_kg"]-E0["fuel_kg"]):.2f} kg total burned')
