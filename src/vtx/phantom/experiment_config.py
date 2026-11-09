"""Explicit, bounded Phantom parameter changes for a named experiment."""
from __future__ import annotations

import copy
import math

from .params import Params

# Bounds constrain experimental input; they are not design limits or validated hardware ratings.
PARAMETERS = {
    'buffer.position_m': (-4.0, 4.0, 3),
    'structure.harness_position_m': (-4.0, 4.0, 3),
    'boosters.position_m': (-4.0, 4.0, 3),
    'buffer.energy_j': (1e6, 1e10, 0),
    'structure.console_mass_kg': (0.01, 1000.0, 0),
    'pods.rotor_inertia_kg_m2': (0.001, 100.0, 0),
    'aero.wing_cd0': (0.0, 2.0, 0),
    'aero.wing_oswald_e': (0.05, 1.5, 0),
    'aero.canard_cd0': (0.0, 2.0, 0),
    'fbw.attitude_gain': (0.0, 10.0, 2),
    'fbw.rate_damping_gain_s': (0.0, 10.0, 3),
    'wing_actuators.slide_kp_n_m': (1.0, 1e7, 0),
    'effectors.canard_rate_deg_s': (0.1, 360.0, 0),
    'effectors.steering.rack_force_n': (1.0, 100000.0, 0),
}


def parameter_catalogue(variant):
    params = Params(variant)
    result = []
    for name, (lower, upper, count) in PARAMETERS.items():
        try:
            node = params.node(name)
        except KeyError:
            continue
        result.append(dict(name=name, value=node['v'], unit=node['u'], label=node['l'],
                           source=node['s'], minimum=lower, maximum=upper, length=count))
    return result


def build_overrides(variant, base_overrides, changes):
    result = copy.deepcopy(base_overrides or {})
    params = Params(variant, overrides=base_overrides)
    for name, value in (changes or {}).items():
        if name not in PARAMETERS:
            raise ValueError(f'Parameter is not available for experiments: {name}')
        lower, upper, count = PARAMETERS[name]
        values = value if isinstance(value, list) else [value]
        if (count and (not isinstance(value, list) or len(value) != count)) or (not count and isinstance(value, list)):
            raise ValueError(f'{name} requires {count} values' if count else f'{name} requires one number')
        if any(type(x) not in (int, float) or not math.isfinite(x) or not lower <= x <= upper for x in values):
            raise ValueError(f'{name} values must be finite numbers from {lower} to {upper}')
        try:
            node = copy.deepcopy(params.node(name))
        except KeyError as exc:
            raise ValueError(f'{name} is not present in {variant}') from exc
        if not isinstance(node, dict) or not {'v', 'u', 'l', 's'} <= node.keys():
            raise ValueError(f'{name} does not identify a parameter value')
        node['v'] = value
        node['l'] = 'SYNTHETIC_UNVALIDATED'
        node['s'] = 'Explicit experiment override; original source: ' + str(node['s'])
        target = result
        parts = name.split('.')
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = node
    return result or None
