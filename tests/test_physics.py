import json
from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from vtx.physics_model import (
    allocation_matrix,allocate_unconstrained,constrained_allocate,
    rigid_body_derivative,validate_configuration,
)

ROOT=Path(__file__).resolve().parent.parent
ROTOR=np.array([[2.6,0,2.31],[0,2.6,2.31],[-2.6,0,2.31],[0,-2.6,2.31]],float)

@pytest.mark.parametrize('cg',[[0,0,2.31],[.15,-.12,1.2],[-.25,.18,.8]])
@pytest.mark.parametrize('target',[[0,0,10526.13,0,0,0],[100,-80,10526.13,10,-20,90],[-140,30,10400,40,10,-80]])
def test_exact_wrench_equilibrium_for_synthetic_cg(cg,target):
    # A zero algebraic residual is NOT aircraft dynamic stability.
    A=allocation_matrix(ROTOR,np.array(cg,float))
    assert np.linalg.matrix_rank(A)==6
    forces=allocate_unconstrained(np.array(target,float),ROTOR,np.array(cg,float))
    np.testing.assert_allclose(A @ forces.flatten(),target,rtol=0,atol=1e-7)

def test_ideal_hover_zero_acceleration():
    mass=1073.0  # scenario mass budget, NOT measured vehicle mass
    cg=np.array([0.,0.,2.31])  # synthetic hover test only
    f=allocate_unconstrained(np.array([0,0,mass*9.81,0,0,0]),ROTOR,cg)
    dyn=rigid_body_derivative(np.zeros(3),np.zeros(3),Rotation.identity(),
       np.zeros(3),f,ROTOR,cg,mass,np.eye(3)*100,
       np.zeros(3),np.zeros(3),np.zeros(3),np.zeros(3))
    np.testing.assert_allclose(dyn['v_dot_m_s2'],np.zeros(3),atol=1e-12)
    np.testing.assert_allclose(dyn['omega_dot_body_rad_s2'],np.zeros(3),atol=1e-12)

def test_invalid_inertia_rejected():
    mass=1000.0
    with pytest.raises(ValueError,match='positive-definite'):
        rigid_body_derivative(np.zeros(3),np.zeros(3),Rotation.identity(),
           np.zeros(3),np.zeros((4,3)),ROTOR,np.zeros(3),mass,
           np.diag([1.,-1.,1.]),np.zeros(3),np.zeros(3),np.zeros(3),np.zeros(3))

def test_calibration_nulls_rejected():
    config=json.loads((ROOT/'inputs/vtx_calibration_required.json').read_text())
    with pytest.raises(ValueError,match='NOT CALIBRATED') as err:
        validate_configuration(config)
    assert 'cg_xyz_m' in str(err.value)
    assert 'thrust_vs_collective_map' in str(err.value)

def test_constrained_hover_with_illustrative_hardware_limit_only():
    # Pure mathematical benchmark: limit below is NOT a hardware specification.
    mass=1073.0
    cg=np.array([0.,0.,2.31])
    ans=constrained_allocate(np.array([0,0,mass*9.81,0,0,0]),ROTOR,cg,4000,20)
    assert ans['feasible'],ans['message']
    assert ans['max_tilt_deg'] < 1e-7


def test_too_small_hardware_thrust_cannot_hover():
    # An impossible limit must never be declared feasible.
    mass=1073.0
    cg=np.array([0.,0.,2.31])
    ans=constrained_allocate(np.array([0,0,mass*9.81,0,0,0]),ROTOR,cg,1000,20)
    assert not ans['feasible']
