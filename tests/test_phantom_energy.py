"""Phantom energy bus: supply limits thrust, SOC bounded, energy balance closes, fuel burn moves mass."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'phantom'))
import phantom_bench as B


def test_supply_restriction_limits_thrust_and_logs_unmet():
    r = B.power_limited('phantom')
    assert r['passed'] and r['soc_never_below_min'], r


def test_energy_balance_residual():
    r = B.energy_residual('phantom-fx')
    assert r['passed'] and r['generator_j'] > 0, r


def test_fuel_burn_moves_mass_and_inertia():
    r = B.mass_update('phantom-fx')
    assert r['passed'] and r['Izz_burned'] < r['Izz_full'] and r['cg_burned'] != r['cg_full']
