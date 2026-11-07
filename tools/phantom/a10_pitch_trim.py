"""Screen A10 longitudinal aerodynamic trim from the actual surface model.

This is a static lift/pitch calculation, not a flight or propulsion validation.
"""
import argparse
import json
import math
import numpy as np
from scipy.optimize import least_squares
from vtx.phantom.params import Params
from vtx.phantom.ledger import PhantomLedger
from vtx.phantom.surface_aero import SurfaceAero


def screen(speed, flap_deg=20):
    params = Params('phantom-fx', {'proposals': {'p6_drs_stabilator': {'v': 1.0}}})
    ledger = PhantomLedger(params)
    mass = ledger.mass_properties(ledger.configuration(pods='road', legs='retracted', wings='deployed', canards='deployed'))
    aero = SurfaceAero(params)
    weight = mass['mass_kg'] * params['atmosphere.gravity_m_s2']
    cg = np.asarray(mass['cg_m'])

    def forces(x):
        alpha, canard, stab = np.radians(x)
        state = {'wing_frac': {'left': 1., 'right': 1.}, 'wing_locked': {'left': True, 'right': True},
                 'flap': {'left': math.radians(flap_deg), 'right': math.radians(flap_deg)}, 'aileron': {'left': 0., 'right': 0.},
                 'canard_pitch': {'left': canard, 'right': canard},
                 'canard_deployed': {'left': True, 'right': True}, 'stab_te_up': stab}
        out = aero.compute(np.array([speed * math.cos(alpha), 0., -speed * math.sin(alpha)]), np.zeros(3), np.zeros(3), state)
        f = out['force_body']
        moment = out['moment_body'] - np.cross(cg, f)
        lift = -math.sin(alpha) * f[0] + math.cos(alpha) * f[2]
        return lift, float(moment[1]), out

    def residual(x):
        lift, pitch, _ = forces(x)
        return [(lift - weight) / weight, pitch / (weight * 2), x[1] / 1000, x[2] / 1000]

    bounds = ([-10, -20, -15], [20, 25, 25])
    # The stall model is nonlinear: one initial guess can settle in a local
    # minimum and incorrectly report that no lower-residual solution exists.
    candidates = [least_squares(residual, [alpha, canard, stab], bounds=bounds)
                  for alpha in (0, 8, 16) for canard in (-10, 10) for stab in (-10, 10)]
    result = min(candidates, key=lambda candidate: np.linalg.norm(candidate.fun))
    lift, pitch, out = forces(result.x)
    return {'speed_m_s': speed, 'flap_deg': flap_deg, 'mass_kg': mass['mass_kg'], 'cg_body_m': mass['cg_m'],
            'alpha_deg': result.x[0], 'canard_deg': result.x[1], 'stabilator_te_up_deg': result.x[2],
            'lift_n': lift, 'weight_n': weight, 'pitch_moment_cg_nm': pitch,
            'drag_body_n': -float(out['force_body'][0]), 'residual_norm': float(np.linalg.norm(result.fun[:2])),
            'surface_forces': out['surfaces'], 'hinge_moments': out['hinge_moments']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speed', type=float, nargs='+', default=[60, 70, 80, 90, 100])
    args = parser.parse_args()
    if any(v <= 0 for v in args.speed):
        parser.error('speeds must be positive')
    print(json.dumps([screen(v) for v in args.speed], indent=2))
