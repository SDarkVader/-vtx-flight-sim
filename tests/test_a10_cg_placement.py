"""Reversible A10 CG placement: numerical and no-double-count regression."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'phantom'))
from a10_cg_placement import assess
from vtx.phantom.params import Params
from vtx.phantom.ledger import PhantomLedger


@pytest.fixture
def fx():
    return PhantomLedger(Params('phantom-fx'))


def test_empty_changes_preserve_all_mass_properties(fx):
    result = assess(fx, [])
    assert result['delta']['mass_kg'] == pytest.approx(0)
    assert result['delta']['cg_m'] == pytest.approx([0, 0, 0], abs=1e-12)
    assert np.allclose(result['baseline']['inertia_about_cg_kg_m2'],
                       result['proposed']['inertia_about_cg_kg_m2'])


def test_forward_addition_matches_first_moment(fx):
    result = assess(fx, [dict(operation='add', id='provisional_controller',
                               mass_kg=8, position_m=[1.0, 0, 0.4])])
    mass = result['baseline']['mass_kg']
    old = result['baseline']['cg_m'][0]
    assert result['proposed']['cg_m'][0] == pytest.approx((mass*old + 8)/(mass+8))
    assert result['delta']['cg_m'][0] > 0


def test_mirrored_duct_actuators_preserve_lateral_cg(fx):
    result = assess(fx, [dict(operation='add', id='shutter_'+side,
                               mass_kg=2, position_m=[-1, y, 0.6])
                         for side, y in [('left', 0.7), ('right', -0.7)]])
    assert result['proposed']['cg_m'][1] == pytest.approx(result['baseline']['cg_m'][1])


def test_existing_hv_relocation_changes_cg_but_not_mass(fx):
    c = next(c for c in fx.components if c.id == 'hv_junction')
    new = [c.position_m[0]+0.4, c.position_m[1], c.position_m[2]]
    result = assess(fx, [dict(operation='relocate', id=c.id, position_m=new)])
    assert result['delta']['mass_kg'] == pytest.approx(0)
    assert result['delta']['cg_m'][0] == pytest.approx(c.mass_kg*0.4/result['baseline']['mass_kg'])
    assert np.linalg.eigvalsh(result['proposed']['inertia_about_cg_kg_m2']).min() > 0


def test_refuses_counting_existing_esc_twice(fx):
    with pytest.raises(ValueError, match='already in ledger'):
        assess(fx, [dict(operation='add', id='pod_FL_fan_motor_inverter',
                          mass_kg=4, position_m=[1.54, 1.25, 0.61])])


def test_refuses_moving_pod_relocation(fx):
    with pytest.raises(ValueError, match='only fixed airframe'):
        assess(fx, [dict(operation='relocate', id='pod_FL_fan_motor_inverter',
                          position_m=[1, 0, 0.5])])


def test_refuses_free_mass(fx):
    with pytest.raises(ValueError, match='positive'):
        assess(fx, [dict(operation='add', id='zero_kg_esc',
                          mass_kg=0, position_m=[0, 0, 0])])
