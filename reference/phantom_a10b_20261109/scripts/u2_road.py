"""U2: road turning on the plant (A10-B physics): yaw stick vs differential wheel drive (skid steer), 10 and 20 m/s."""
import sys, math, numpy as np
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
OV = overlays.load('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1', extra={'proposals': {'p6_drs_stabilator': {'v': 1.}}})
def run(v_target, how):
    a = C.plant('phantom-fx', OV, start_configuration='road'); d = a.data
    a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4)); 
    while float(a.vel_body()[0]) < v_target: C.run(a, 0.1)
    a.set_command(dict(wheel_drive=[0.15]*4))
    if how == 'yaw_stick':
        a.set_command(dict(yaw=1.0, stability_mode='rate_damping'))
    else:   # skid steer: right wheels drive, left wheels brake (pods FL, FR, RL, RR)
        a.set_command(dict(wheel_drive=[0.0, 1.0, 0.0, 1.0], brake=[0.6, 0.0, 0.6, 0.0]))
    psi0 = a.attitude()['yaw_left']; t0 = float(d.time); rates = []
    for _ in range(40):
        C.run(a, 0.1); rates.append(math.degrees(a.rates_body()[2]))
    u = float(a.vel_body()[0]); dpsi = math.degrees(a.attitude()['yaw_left'] - psi0)
    ay = math.radians(np.mean(rates[-10:])) * u / 9.81
    print(f'{how:10s} from {v_target:4.0f} m/s: heading change {dpsi:+7.1f} deg in 4 s, yaw rate (last 1 s) {np.mean(rates[-10:]):+6.2f} deg/s, speed now {u:5.1f} m/s, lateral accel ~{ay:+.2f} g')
for v in (10.0, 20.0):
    for how in ('yaw_stick', 'skid'):
        run(v, how)
