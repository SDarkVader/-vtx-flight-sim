"""V1: controlled flight with variable velocity. Airborne at 95 m/s (A10-B physics: P6, 7 deg wing, hull lift,
suspension, drive limits). 'fans': pods vertical, wheel fans as lift + control effectors, boosters off -> decelerate,
then a banked turn at ~45 m/s. 'aero': same schedule with the fans off (pods stowed): surfaces only.
Test pilot: attitude mode (pitch hold), altitude hold on collective (fans case), roll stick for the turn."""
import sys, json, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
from vtx.phantom.geometry import PODS, SIDE
tag = sys.argv[2]
OV = overlays.load('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1',
                   extra={'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}})
a = C.plant('phantom-fx', OV, start_configuration='road'); m, d = a.model, a.data; P = a.P
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
M = a.mass_properties()['mass_kg']; W = M * 9.80665
# airborne initial condition: 300 m up, 95 m/s level, wings locked
d.qpos[2] += 300.0; d.qvel[:] = 0.0; d.qvel[0] = 95.0
fans = tag == 'fans'
if fans:                                               # pods vertical, fans pre-spun to share the weight, generator on its take-off rating
    for k in PODS:
        a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
        T0 = 0.25 * W / 4; om = a.fan.omega_for_thrust(T0)
        d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * om
    a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power)
mj.mj_forward(m, d)
z_ref = float(d.qpos[2]); c_trim = 0.25 if fans else 0.0
a.set_command(dict(stability_mode='attitude', pitch=0.0, roll=0.0, yaw=0.0, collective=c_trim, booster_throttle=[0., 0.], wheel_drive=[0.]*4, brake=[0.]*4,
                   pod_tilt_deg=[90.]*4 if fans else [0.]*4, flap_deg=[0., 0.], canard_pitch_deg=[0., 0.]))
log = []; st = dict(turn=False, t_turn=None)
def pilot(a):
    t = float(d.time); z = float(d.qpos[2]); vz = float(d.qvel[2]); u = float(a.vel_body()[0])
    att = a.attitude(); rb = a.rates_body()
    vb = a.vel_body(); beta = math.degrees(math.atan2(vb[1], max(abs(vb[0]), 1e-3)))
    alpha = math.degrees(math.atan2(-vb[2], max(abs(vb[0]), 1e-3)))
    cmd = {}
    if fans:   # altitude hold on collective (test pilot)
        cmd['collective'] = float(np.clip(c_trim + 0.02 * (z_ref - z) - 0.05 * vz + (1 - min(1, (u / 95.0) ** 2)) * 0.5, 0.0, 1.0))
    if not st['turn'] and (u < 45.0 or (not fans and t - log[0]['t'] > 20 if log else False)):
        st['turn'] = True; st['t_turn'] = t
        g_tan = 9.80665 * math.tan(math.radians(15.0))
        cmd.update(roll=1.0, yaw=float(np.clip(math.degrees(g_tan / max(u, 20.0)) / 20.0, 0, 1)))
    if cmd: a.set_command(cmd)
    b = a.bus.last or {}
    log.append(dict(t=round(t, 2), u=round(u, 2), z=round(z - z_ref, 2), pitch=round(math.degrees(att['pitch_up']), 2), alpha=round(alpha, 2),
                    roll=round(math.degrees(att['roll']), 2), beta=round(beta, 2), q=round(math.degrees(rb[1]), 1), r=round(math.degrees(rb[2]), 1),
                    heading=round(math.degrees(att['yaw_left']), 2), coll=round(a.fcc.cmd['collective'], 3),
                    fanT=[round(s.get('thrust_n', 0)) for s in a.fan_state], ram=[round(s.get('ram_drag_n', 0)) for s in a.fan_state],
                    dem=[round(x, 2) for x in (a.fcc.last or {}).get('moment_demand', [0, 0, 0])],
                    bus_kw=round(b.get('delivered_w', 0) / 1e3), soc=round(a.bus.soc, 3), unmet_kw=round(b.get('unmet_w', 0) / 1e3)))
    return abs(att['pitch_up']) > math.radians(60) or abs(att['roll']) > math.radians(80) or a.crashed or (st['t_turn'] and t - st['t_turn'] > 25)
C.run(a, 80, every=0.05, stop=pilot)
json.dump(log, open(f'{sys.argv[1]}/v1_{tag}.json', 'w'))
L = log; t0 = L[0]['t']
def at(t): return min(L, key=lambda r: abs(r['t'] - t))
print(f'== {tag}: duration {L[-1]["t"]-t0:.1f} s, turn started at {(st["t_turn"] or 0)-t0:.1f} s, end reason pitch {L[-1]["pitch"]} roll {L[-1]["roll"]}')
for tt in (0, 2, 5, 10, 15, 20, 25, 30, 40, 50):
    if t0 + tt <= L[-1]['t']:
        r = at(t0 + tt); print('  t+%4.0f u %6.1f z %+7.1f pitch %+6.1f alpha %+6.1f roll %+6.1f beta %+6.1f hdg %+7.1f coll %.2f fanT %s ram %s bus %s kW soc %.3f unmet %s' %
                                 (tt, r['u'], r['z'], r['pitch'], r['alpha'], r['roll'], r['beta'], r['heading'], r['coll'], r['fanT'], r['ram'], r['bus_kw'], r['soc'], r['unmet_kw']))
dec = [(L[i]['u'] - L[i+20]['u']) / (L[i+20]['t'] - L[i]['t']) / 9.80665 for i in range(0, len(L) - 20, 20)]
print('  peak decel %.2f g; max |beta| %.1f deg; max |pitch| %.1f deg; min z %+.1f m' % (max(dec) if dec else 0, max(abs(r['beta']) for r in L), max(abs(r['pitch']) for r in L), min(r['z'] for r in L)))
