"""Phantom hover-feasibility sweep (design-space screening, not a flight result).

For each design point the REAL simulator ledger is rebuilt (Params overrides -> PhantomLedger) so
mass and CG are exactly what the sim would fly. Motors are re-sized to the per-pod peak power the
point needs (12.1 kW/kg, research s2/s9), and the mass is iterated to a fixed point.
Criteria (research s9): collective reserve T_max_total >= 1.20 W; per-pod margin: each pod's
T_max >= 1.30 x its own CG-determined hover share; hover electrical power <= generator (take-off
rating) + buffer peak; usable hover minutes from buffer energy and the 5-min take-off rating.
Every point is a DESIGN PROPOSAL (SYNTHETIC_UNVALIDATED). Costs reported: mass, CG, power, look.

Usage: PYTHONPATH=src python tools/phantom/phantom_feasibility.py [--out evidence/phantom/phantom_feasibility.json]
"""
from __future__ import annotations
import argparse, itertools, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.phantom.params import Params
from vtx.phantom.ledger import PhantomLedger, pod_shares
from vtx.phantom.propulsion import DuctedFan

S = 'SYNTHETIC_UNVALIDATED'


def q(v, u, s='feasibility sweep design proposal'):
    return {'v': v, 'u': u, 'l': S, 's': s}


def evaluate(variant, wheel_r, fan_r, fm, sigma, n_gen, gen_to_w, buffer_kwh, wh_kg, kw_kg_peak, occupants=None, fuel_kg=None, iters=12):
    P0 = Params(variant)
    g = P0['atmosphere.gravity_m_s2']; rho = P0['atmosphere.density_kg_m3']
    hub = max(0.11, 0.27 * fan_r)
    A = math.pi * (fan_r ** 2 - hub ** 2)
    motor_peak = P0['pods.motor_power_peak_w']
    for _ in range(iters):
        ov = {'pods': {'tyre_radius_m': q(wheel_r, 'm'), 'fan_r_tip_m': q(fan_r, 'm'), 'fan_r_hub_m': q(hub, 'm'), 'fm_open': q(fm, '-'), 'duct_sigma': q(sigma, '-'),
                       'motor_power_peak_w': q(motor_peak, 'W'), 'motor_inverter_mass_kg': q(motor_peak / 12100.0, 'kg'),
                       'hinge_z_m': q(wheel_r + 0.06, 'm'), 'motor_torque_peak_nm': q(motor_peak / (0.97 * 230 / fan_r), 'N m')},
              'generators': {'count': q(n_gen, '-'), 'takeoff_power_each_w': q(max(gen_to_w, 600000.0), 'W'), 'positions_m': q([[-1.75, 0.0, 0.55]] if n_gen == 1 else [[-1.75, 0.4, 0.55], [-1.75, -0.4, 0.55]], 'm')},
              'buffer': {'energy_j': q(buffer_kwh * 3.6e6, 'J'), 'specific_energy_wh_kg': q(wh_kg, 'Wh/kg')}}
        P = Params(variant, ov)
        L = PhantomLedger(P, occupants)
        mp = L.mass_properties(None, fuel_kg=fuel_kg)
        W = mp['mass_kg'] * g
        f, r = pod_shares(P, mp['cg_m'][0])
        t_need = 1.30 * max(f, r) * W                      # per-pod sizing thrust
        t_need = max(t_need, 1.20 * W / 4)
        p_need = t_need ** 1.5 / (fm * math.sqrt(2 * rho * A))
        if abs(p_need - motor_peak) < 500:
            break
        motor_peak = p_need
    fan = DuctedFan.pod(P)
    eta = P['pods.motor_efficiency'] * P['pods.inverter_efficiency']
    hover_e = sum(fan.hover_power(s * W) for s in (f, f, r, r)) / eta + 25000
    peak_e = sum(fan.hover_power(1.2 * s * W) for s in (f, f, r, r)) / eta + 25000
    bm = buffer_kwh * 1000 / wh_kg
    gen = n_gen * max(gen_to_w, 600000.0); gen_cont = n_gen * 600000.0
    buf_peak = bm * kw_kg_peak * 1000
    deficit = max(0.0, hover_e - gen)
    hover_min = min(5.0, (0.8 * buffer_kwh * 3.6e6 / deficit / 60) if deficit > 0 else 99)
    ok = (4 * fan.thrust_max >= 1.20 * W and fan.thrust_max >= 1.30 * max(f, r) * W * 0.999 and peak_e <= gen + buf_peak and hover_min >= 2.0)
    return dict(feasible=bool(ok), wheel_diameter_m=2 * wheel_r, fan_diameter_m=2 * fan_r, disk_total_m2=4 * A, fm_open=fm, sigma=sigma,
                generators=n_gen, generator_takeoff_w=gen, generator_cont_w=gen_cont, buffer_kwh=buffer_kwh, buffer_mass_kg=bm,
                mass_kg=mp['mass_kg'], cg_x_m=mp['cg_m'][0], pod_share_front_rear=[f, r], motor_peak_w=motor_peak,
                thrust_max_pod_n=fan.thrust_max, tw_collective=4 * fan.thrust_max / W, tw_worst_pod=fan.thrust_max / (max(f, r) * W),
                hover_electrical_w=hover_e, peak_electrical_w=peak_e, tw_generator_only=(gen * eta * fm * math.sqrt(2 * rho * 4 * A)) ** (2 / 3) / W,
                usable_hover_min=hover_min, disk_loading_n_m2=W / (4 * A),
                look_cost='none' if wheel_r <= 0.36 else f'wheels {2 * wheel_r:.2f} m vs 0.72 m (+{(wheel_r / 0.36 - 1) * 100:.0f}% diameter), fenders redrawn',
                label='DESIGN PROPOSAL, SYNTHETIC_UNVALIDATED')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'evidence/phantom/phantom_feasibility.json')); a = ap.parse_args()
    pts = []
    pts.append(dict(name='phantom as drawn, lift motors re-sized to the margin need (mass diverges)', **evaluate('phantom', 0.36, 0.245, 0.80, 1.0, 2, 600000, 12, 182, 3.0)))
    grid = itertools.product([(0.36, 0.245), (0.45, 0.35), (0.55, 0.45), (0.60, 0.50)], [0.80, 0.90], [1, 2], [600000, 900000], [40, 80])
    for (wr, fr), fm, ng, gto, kwh in grid:
        pts.append(dict(name=f'sweep wheel {2*wr:.2f} fan {2*fr:.2f} FM {fm} gen {ng}x{gto/1e3:.0f}kW buf {kwh} kWh',
                        **evaluate('phantom-fx', wr, fr, fm, 1.2 if fm >= 0.9 else 1.0, ng, gto, kwh, 257, 3.858)))
    pts.append(dict(name='phantom-fx FX-A (selected)', **evaluate('phantom-fx', 0.55, 0.45, 0.90, 1.2, 1, 900000, 80, 257, 3.858)))
    pts.append(dict(name='phantom-fx FX-C load (1 occ, 60 kg fuel)', **evaluate('phantom-fx', 0.55, 0.45, 0.90, 1.2, 1, 900000, 80, 257, 3.858, occupants=1, fuel_kg=60)))
    out = dict(schema='phantom-feasibility-1', criteria='T_max total >= 1.20 W; each pod >= 1.30 x own share; peak electrical <= generator TO + buffer peak; >= 2 min usable hover',
               points=pts, feasible=[p['name'] for p in pts if p['feasible']])
    Path(a.out).write_text(json.dumps(out, indent=1))
    for p in pts:
        if p['feasible'] or 'FX' in p['name'] or 'drawn' in p['name']:
            print(f"{p['name'][:70]:70s} ok={p['feasible']!s:5s} m={p['mass_kg']:.0f} cg={p['cg_x_m']:+.2f} TW={p['tw_collective']:.2f}/{p['tw_worst_pod']:.2f} P={p['hover_electrical_w']/1e3:.0f}kW hov={p['usable_hover_min']:.1f}min")
    print(len(out['feasible']), 'feasible of', len(pts))


if __name__ == '__main__':
    main()
