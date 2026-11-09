"""A10 reversible CG/inertia placement screen. No live flight or geometry edits."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import numpy as np


def vector(x, name):
    a = np.asarray(x, float)
    if a.shape != (3,) or not np.isfinite(a).all():
        raise ValueError(f"{name}: expected three finite SI coordinates")
    return a


def tensor(x, name):
    if x is None:
        return np.zeros((3, 3), float)  # point-mass screen, not hardware inertia
    a = np.asarray(x, float)
    if a.shape != (3, 3) or not np.isfinite(a).all():
        raise ValueError(f"{name}: expected finite 3x3 inertia")
    if not np.allclose(a, a.T, atol=1e-9) or np.linalg.eigvalsh(a).min() < -1e-9:
        raise ValueError(f"{name}: inertia must be symmetric positive semidefinite")
    return a


def shift(m, r):
    return m * (float(r @ r) * np.eye(3) - np.outer(r, r))


def assess(ledger, changes, *, configuration=None, fuel_kg=None, occupants=None):
    """Apply provisional add/relocate operations to a real ledger configuration.

    add: {operation, id, mass_kg, position_m, inertia_at_cg_kg_m2?}
    relocate: {operation, id, position_m}; only existing fixed airframe records.
    This never mutates ledger, geometry, controls, or the live aircraft.
    """
    if not isinstance(changes, list):
        raise ValueError("changes must be a list")
    q = ledger.configuration() if configuration is None else configuration
    b = ledger.mass_properties(q, fuel_kg=fuel_kg, occupants=occupants)
    m0 = float(b['mass_kg'])
    r0 = vector(b['cg_m'], 'baseline CG')
    j0 = tensor(b['inertia_about_cg_kg_m2'], 'baseline tensor')
    m, first, origin = m0, m0 * r0, j0 + shift(m0, r0)
    existing = {c.id: c for c in ledger.components}
    seen, applied = set(), []
    for i, item in enumerate(changes):
        if not isinstance(item, dict):
            raise ValueError(f"change {i}: expected object")
        op, cid = item.get('operation'), item.get('id')
        if op not in ('add', 'relocate') or not isinstance(cid, str) or not cid.strip():
            raise ValueError(f"change {i}: operation add/relocate and id required")
        if cid in seen:
            raise ValueError(f"{cid}: duplicate operation")
        seen.add(cid)
        r = vector(item.get('position_m'), f"{cid}.position_m")
        if op == 'add':
            if cid in existing:
                raise ValueError(f"{cid}: already in ledger; no double counting")
            if set(item) - {'operation', 'id', 'mass_kg', 'position_m', 'inertia_at_cg_kg_m2'}:
                raise ValueError(f"{cid}: unexpected add fields")
            dm = float(item.get('mass_kg', float('nan')))
            if not math.isfinite(dm) or dm <= 0:
                raise ValueError(f"{cid}: mass must be positive and finite")
            local = tensor(item.get('inertia_at_cg_kg_m2'), f"{cid}.inertia")
            m += dm
            first += dm * r
            origin += local + shift(dm, r)
            applied.append(dict(operation=op, id=cid, mass_kg=dm, position_m=r.tolist(),
                                point_mass_inertia_assumed='inertia_at_cg_kg_m2' not in item))
        else:
            if set(item) != {'operation', 'id', 'position_m'}:
                raise ValueError(f"{cid}: relocation must only specify id and new position")
            if cid not in existing:
                raise ValueError(f"{cid}: unknown component")
            c = existing[cid]
            if c.body != 'airframe' or 'fuel' in c.tags or c.id.startswith('occupant_'):
                raise ValueError(f"{cid}: only fixed airframe equipment can relocate")
            old = vector(c.position_m, f"{cid}.previous_position")
            first += c.mass_kg * (r - old)
            origin += shift(c.mass_kg, r) - shift(c.mass_kg, old)
            applied.append(dict(operation=op, id=cid, mass_kg=c.mass_kg,
                                from_position_m=old.tolist(), position_m=r.tolist()))
    cg = first / m
    inertia = origin - shift(m, cg)
    inertia = 0.5 * (inertia + inertia.T)
    if np.linalg.eigvalsh(inertia).min() <= 0:
        raise ValueError("resulting physical inertia is not positive definite")
    xf, xr = ledger.p['pods.hinge_x_front_m'], ledger.p['pods.hinge_x_rear_m']
    if xf <= xr:
        raise ValueError("invalid front/rear pod stations")
    f0, f1 = (r0[0] - xr) / (xf - xr), (cg[0] - xr) / (xf - xr)
    return dict(model='mass-property screen; NOT CFD, FEA or flight validation',
                variant=ledger.p.variant, config_sha256=ledger.p.config_sha256,
                source_status='SYNTHETIC_UNVALIDATED',
                baseline=dict(mass_kg=m0, cg_m=r0.tolist(),
                              inertia_about_cg_kg_m2=j0.tolist(), front_pod_share=f0),
                proposed=dict(mass_kg=m, cg_m=cg.tolist(),
                              inertia_about_cg_kg_m2=inertia.tolist(), front_pod_share=f1),
                delta=dict(mass_kg=m-m0, cg_m=(cg-r0).tolist(),
                           front_pod_share=f1-f0), changes=applied,
                limitations=['No component fit or swept collision test',
                             'Added components default to point-mass inertia',
                             'Hover support share is not a flight-control margin',
                             'No wingborne trim, CFD, thermal or power validation'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--variant', choices=('phantom', 'phantom-fx'), default='phantom-fx')
    ap.add_argument('--changes', required=True, type=Path)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--occupants', type=int, choices=(1, 2), default=2)
    ap.add_argument('--fuel-kg', type=float)
    ap.add_argument('--pods', choices=('vtol', 'road'), default='vtol')
    ap.add_argument('--legs', choices=('extended', 'retracted'), default='extended')
    ap.add_argument('--wings', choices=('stowed', 'deployed'), default='stowed')
    ap.add_argument('--canards', choices=('folded', 'deployed'), default='folded')
    args = ap.parse_args()
    from vtx.phantom.params import Params
    from vtx.phantom.ledger import PhantomLedger
    ledger = PhantomLedger(Params(args.variant))
    q = ledger.configuration(pods=args.pods, legs=args.legs,
                             wings=args.wings, canards=args.canards)
    inp = json.loads(args.changes.read_text(encoding='utf-8'))
    result = assess(ledger, inp['changes'], configuration=q, fuel_kg=args.fuel_kg,
                    occupants=args.occupants)
    result['scenario'] = dict(pods=args.pods, legs=args.legs,
                              wings=args.wings, canards=args.canards,
                              occupants=args.occupants, fuel_kg=args.fuel_kg)
    output = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    print(output, end='')


if __name__ == '__main__':
    main()
