"""Test 3 (static, from T1/T2 telemetry): tail-strike angle, max nose-up authority about the rear tyre contact,
rotation speed vs CG / wing incidence / wing area. Live A10 build 70089cca geometry."""
import sys, math, json, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp as C
from vtx.phantom.params import Params
from vtx.phantom.surface_aero import SurfaceAero
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
a = C.plant('phantom-fx', P6, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.])); C.run(a, 2.5)
Rb = a.R(); org = d.xpos[a.bids['airframe']].copy()
# rear contact point and ground
f6 = np.zeros(6); rear = []
for i in range(d.ncon):
    c = d.contact[i]
    for gi in (c.geom1, c.geom2):
        if m.geom(gi).name.startswith('tyre_R'): rear.append(np.array(c.pos))
Pr = np.mean(rear, axis=0); zg = Pr[2]
xr_b = (Rb.T @ (Pr - org))[0]; zr_b = (Rb.T @ (Pr - org))[2]
# tail strike: lowest non-tyre vehicle geometry behind the rear contact (geom AABB corners, world frame)
veh = set(range(1, m.nbody)); worst = (90, None)
for gi in range(m.ngeom):
    if m.geom_bodyid[gi] == 0 or m.geom(gi).name.startswith(('tyre_', 'foot_')) or m.geom_contype[gi] == 0 and m.geom_conaffinity[gi] == 0: continue
    c = m.geom_aabb[gi][:3]; hs = m.geom_aabb[gi][3:]; R = d.geom_xmat[gi].reshape(3, 3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = d.geom_xpos[gi] + R @ (c + hs * [sx, sy, sz]); dx = (Pr - p) @ (Rb @ [1, 0, 0])
                if dx > 0.05:
                    ang = math.degrees(math.atan2(p[2] - zg, dx))
                    if ang < worst[0]: worst = (ang, m.geom(gi).name, round(dx, 2), round(p[2] - zg, 2))
print('rear contact body x', round(xr_b, 3), '| tail-strike angle (collision geoms)', round(worst[0], 1), 'deg at', worst[1:])
P = a.P; mp = a.mass_properties(); M = mp['mass_kg']; W = M * 9.80665; xcg = mp['cg_body_m'][0]; zcg = mp['cg_body_m'][2]
print('mass', round(M, 1), 'x_cg', round(xcg, 3), 'weight moment about rear contact', round(W * (xcg - xr_b)), 'N m')
def nose_up_about_rear(SA, V, pitch_deg, can_deg, stab_te_up_deg, flap_deg, a_acc=0.0):
    th = math.radians(pitch_deg); vb = np.array([V * math.cos(th), 0, -V * math.sin(th)])
    st = dict(wing_frac=dict(left=1., right=1.), wing_locked=dict(left=True, right=True), flap=dict(left=math.radians(flap_deg), right=math.radians(flap_deg)),
              aileron=dict(left=0., right=0.), canard_pitch=dict(left=math.radians(can_deg), right=math.radians(can_deg)),
              canard_deployed=dict(left=True, right=True), stab_te_up=math.radians(stab_te_up_deg))
    r = SA.compute(vb, np.zeros(3), np.zeros(3), st); Pp = np.array([xr_b, 0, zr_b])
    Mn = -(r['moment_body'] - np.cross(Pp, r['force_body']))[1]       # nose-up about the rear contact (body frame, level)
    per = {}
    for s, o in zip(SA.surfaces, [x for x in r['surfaces'] if not x['name'].startswith(('flap', 'aileron', 'body'))]):
        per[s.name.replace('_left', '').replace('_right', '')] = per.get(s.name.replace('_left', '').replace('_right', ''), 0) - np.cross(s.ac - Pp, o['force_n'])[1]
    return Mn, r['force_body'][2], per
def need(xcg_, Mtot):
    return W * (xcg_ - xr_b) - Mtot
# booster nose-down and acceleration nose-up from T1 telemetry
bt = -1100.0; acc = 1.0
rows = []
for tag, ov in (('as flown (70089cca)', P6), ('P8 wing incidence 7 deg', {'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}})):
    SA = SurfaceAero(Params('phantom-fx', ov))
    for law, can, stab in (('attitude law (demand 0.209)', 3.1, 9.1), ('full stick (demand 1.0)', 15.0, 21.0), ('max deflection', 14.0, 18.0)):
        res = []
        for V in (40, 60, 70, 80, 100, 120):
            Mn, Fz, per = nose_up_about_rear(SA, V, 0.0, can, stab, 30.0 if V <= 75 else 0.0)
            Mx = Mn + bt + M * acc * (zcg - zr_b)
            res.append((V, round(Mx), round(W * (xcg - xr_b)), round(Fz), {k: round(v) for k, v in per.items()}))
        Vrot = next((r[0] for r in res if r[1] >= r[2]), None)
        print(f'\n[{tag} | {law}] canard {can} deg, stab TE-up {stab} deg; rotation speed:', Vrot)
        for r in res: print('   V', r[0], 'nose-up', r[1], 'vs weight', r[2], 'aero lift', r[3], r[4])
# CG sensitivity: move the 311 kg nose buffer aft
for xb in (1.80, 1.0, 0.5, -0.06):
    xc = xcg + 311.3 * (xb - 1.80) / M
    f = (xc - P['pods.hinge_x_rear_m']) / (P['pods.hinge_x_front_m'] - P['pods.hinge_x_rear_m'])
    print(f'buffer at x {xb:+.2f}: x_cg {xc:+.3f}  weight moment {W*(xc-xr_b):7.0f} N m  hover front share {f:.3f}  rear pod load {(1-f)*W/2:6.0f} N of {a.fan.thrust_max:.0f} N max')
