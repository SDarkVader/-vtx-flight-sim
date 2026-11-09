"""U1: static pitch and yaw moment about the CG vs alpha / beta (plant aero), A10-A vs A10-B physics; control power available."""
import sys, math, json, numpy as np
sys.path.insert(0, '/home/user/-vtx-flight-sim/src')
from vtx.phantom import overlays
from vtx.phantom.params import Params
from vtx.phantom.surface_aero import SurfaceAero
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.}}}
CFG = {'A10-A (70089cca)': P6, 'A10-A + hull lift': overlays.load('hull_lift_v1', extra=P6)}
a = PhantomAircraft(TestWorld(), 'phantom-fx', overrides=P6); mp = a.mass_properties(); cg = np.array(mp['cg_body_m'])
print('CG body', np.round(cg, 3))
def st(P, can=0.0, stab=None, flap=0.0, ail=0.0):
    return dict(wing_frac=dict(left=1., right=1.), wing_locked=dict(left=True, right=True), flap=dict(left=math.radians(flap), right=math.radians(flap)),
                aileron=dict(left=math.radians(ail), right=math.radians(-ail)), canard_pitch=dict(left=math.radians(can), right=math.radians(can)),
                canard_deployed=dict(left=True, right=True), stab_te_up=math.radians(P['proposals.p6_stab_rest_te_up_deg'] if stab is None else stab))
def moments(SA, P, V, al, be, **k):
    a_, b_ = math.radians(al), math.radians(be)
    v = V * np.array([math.cos(a_) * math.cos(b_), math.sin(b_), -math.sin(a_) * math.cos(b_)])
    r = SA.compute(v, np.zeros(3), np.zeros(3), st(P, **k))
    M = r['moment_body'] - np.cross(cg, r['force_body'])
    return -M[1], M[2], M[0], r['force_body']        # nose-up pitch, yaw (+z), roll (+x), force
out = {}
for name, ov in CFG.items():
    P = Params('phantom-fx', ov); SA = SurfaceAero(P); out[name] = {}
    for V in (60.0, 95.0):
        q = 0.5 * 1.225 * V * V
        rows = []
        for al in (-4, 0, 4, 8, 12, 16):
            m0 = moments(SA, P, V, al, 0)[0]
            up = moments(SA, P, V, al, 0, can=25.0, stab=-4.0)[0]     # max nose-up: canards +25 (stall-limited), stab TE-down to the travel stop
            dn = moments(SA, P, V, al, 0, can=-20.0, stab=36.0)[0]    # max nose-down: canards -20, stab TE-up 36 deg
            rows.append(dict(alpha=al, M_free_Nm=round(m0), ctrl_up_Nm=round(up - m0), ctrl_down_Nm=round(dn - m0)))
        yaw = []
        for be in (0, 2, 5, 10):
            _, n, l, F = moments(SA, P, V, 2.0, be)
            yaw.append(dict(beta=be, N_Nm=round(n), L_Nm=round(l), Fy=round(F[1])))
        d = 2.0
        Cn_b = (moments(SA, P, V, 2.0, d)[1] - moments(SA, P, V, 2.0, -d)[1]) / (2 * math.radians(d)) / (q * 3.934 * 4.858)
        Cm_a = (moments(SA, P, V, 4.0, 0)[0] - moments(SA, P, V, 0.0, 0)[0]) / math.radians(4) / (q * 3.934 * 0.872)
        out[name][V] = dict(Cm_alpha=round(Cm_a, 3), Cn_beta=round(Cn_b, 4), pitch=rows, yaw=yaw)
        print(f'\n[{name}] V {V:.0f} m/s  Cm_a {Cm_a:+.2f}/rad  Cn_b {Cn_b:+.4f}/rad (+ = weathercock stable; yaw axis sign checked below)')
        for r in rows: print('   alpha %+3d  free M %7d  | control: max nose-up %+7d, max nose-down %+7d N m' % (r['alpha'], r['M_free_Nm'], r['ctrl_up_Nm'], r['ctrl_down_Nm']))
        for y in yaw: print('   beta %+3d  N %7d  L %7d  Fy %7d' % (y['beta'], y['N_Nm'], y['L_Nm'], y['Fy']))
json.dump(out, open(sys.argv[1] + '/u1.json', 'w'), default=str)
