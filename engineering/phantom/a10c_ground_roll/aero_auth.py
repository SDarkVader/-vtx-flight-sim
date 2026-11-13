"""Aerodynamic yaw/roll authority on the ground: rudders at full travel, differential canards, vs tyre forces."""
import sys, math
root = sys.argv[1]; sys.path.insert(0, root + '/src')
import numpy as np
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world
w = make_world('airport'); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
cg = np.array(a.mass_properties()['cg_body_m'])
def run(V, canard=(0.0, 0.0), rudder=0.0):
    st = dict(wing_frac={'left': 1.0, 'right': 1.0}, wing_locked={'left': True, 'right': True}, flap={'left': math.radians(30), 'right': math.radians(30)},
              aileron={'left': 0.0, 'right': 0.0}, canard_pitch={'left': math.radians(canard[0]), 'right': math.radians(canard[1])},
              canard_deployed={'left': True, 'right': True}, stab_te_up=a.stab_te_up, rudder=math.radians(rudder))
    pitch = math.radians(3.7)
    vb = np.array([V * math.cos(pitch), 0.0, -V * math.sin(pitch)])      # body sees the wind from ahead and slightly below at 3.7 deg nose-up on the ground
    out = a.aero.compute(vb, np.zeros(3), np.zeros(3), st)
    F = out['force_body']; M = out['moment_body'] - np.cross(cg, F)      # moment about the CG
    return F, M, out
print(f'CG body {cg.round(3)}; canard area each {a.aero.surfaces[2].area:.3f} m2 at x={a.aero.surfaces[2].ac[0]} y=+-{abs(a.aero.surfaces[2].ac[1]):.2f}; fin area each {a.P["aero.fin_area_each_m2"]} m2 at {a.P["aero.fin_position_m"]}')
print(' V m/s  q Pa | baseline Fz N (lift+)  My Nm | rudder 25 deg: Fy N  yaw Mz Nm | canards +10/-10 deg: roll Mx Nm  yaw Mz Nm  Fz N | canards +10/+10: Fz N  My Nm')
for V in (20, 30, 40, 50, 60, 80):
    F0, M0, _ = run(V); Fr, Mr, _ = run(V, rudder=25.0); Fc, Mc, _ = run(V, canard=(10.0, -10.0)); Fs, Ms, _ = run(V, canard=(10.0, 10.0))
    q = 0.5 * a.P['atmosphere.density_kg_m3'] * V * V
    print(f'{V:5.0f} {q:6.0f} | {F0[2]:8.0f} {M0[1]:8.0f} | {Fr[1]-F0[1]:7.0f} {Mr[2]-M0[2]:8.0f} | {Mc[0]-M0[0]:8.0f} {Mc[2]-M0[2]:8.0f} {Fc[2]-F0[2]:6.0f} | {Fs[2]-F0[2]:7.0f} {Ms[1]-M0[1]:8.0f}')
print('for scale: one rear tyre at its friction limit (about 5 kN) at x=-1.59 m from the hinge line -> about', round(5000*abs(-1.59-cg[0])), 'Nm of yaw about the CG')
