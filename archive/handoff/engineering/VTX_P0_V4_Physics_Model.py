"""VTX P0-V4 physical modelling harness. NOT flight-control software.

Exact 6-axis force/moment allocation and a rigid-body 6-DOF plant.
All unmeasured aircraft properties must be specified explicitly. The model refuses to
run a VTX manoeuvre when CG, inertia, rotor dynamic limits or load maps are unknown.

Run:
    python VTX_P0_V4_Physics_Model.py --self-test
    python VTX_P0_V4_Physics_Model.py --validate VTX_P0_V4_Required_Inputs.json

Inputs must be based on physical component measurements, validated CAD properties,
CFD / wind-tunnel measurements and actuator system identification, not guesses.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation

G = 9.81  # m/s2, nominal standard gravity
ROTOR_XY_M = np.array([[2.6, 0], [0, 2.6], [-2.6, 0], [0, -2.6]], dtype=float)


def cross_matrix(r: np.ndarray) -> np.ndarray:
    x, y, z = r
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=float)


def allocation_matrix(rotor_centres: np.ndarray, cg: np.ndarray) -> np.ndarray:
    """A @ [F1xyz,...,F4xyz] = [net force XYZ, net torque XYZ about CG]."""
    points = np.asarray(rotor_centres, dtype=float)
    center = np.asarray(cg, dtype=float)
    if points.shape != (4, 3) or center.shape != (3,):
        raise ValueError("Expected four XYZ fan centres and an XYZ centre of gravity")
    a = np.zeros((6, 12))
    for i, point in enumerate(points):
        a[:3, 3*i:3*i+3] = np.eye(3)
        a[3:, 3*i:3*i+3] = cross_matrix(point - center)
    return a


def allocate_unconstrained(target_wrench: np.ndarray,
                           rotor_centres: np.ndarray,
                           cg: np.ndarray) -> np.ndarray:
    """Minimum Euclidean force-norm exact wrench solution, if A has rank 6.

    No assumption that this mathematical solution can be produced by real rotors.
    """
    a = allocation_matrix(rotor_centres, cg)
    w = np.asarray(target_wrench, dtype=float)
    if w.shape != (6,):
        raise ValueError("Wrench must contain Fx Fy Fz Mx My Mz")
    if np.linalg.matrix_rank(a) < 6:
        raise ValueError("No rank-6 wrench solution with this rotor geometry")
    f = a.T @ np.linalg.solve(a @ a.T, w)
    return f.reshape(4, 3)


def force_to_azimuth_and_tilt(f: np.ndarray) -> tuple[float, float, float]:
    """Requested T [N], inclination from +Z [rad], azimuth in XY plane [rad]."""
    x, y, z = map(float, f)
    t = float(np.linalg.norm(f))
    if not np.isfinite(t) or z < 0:
        raise ValueError("Unphysical negative axial rotor force")
    return t, float(np.arctan2(np.hypot(x, y), z)), float(np.arctan2(y, x))


def constrained_allocate(target_wrench: np.ndarray, rotor_centres: np.ndarray,
                         cg: np.ndarray, max_thrust_n: float,
                         max_tilt_deg: float) -> dict:
    """Constrained quasi-static allocator; axial-thrust and tilt-cone constraints.

    A successful residual check is ONLY static feasibility. No torque reaction,
    actuator rates, gyros, whirl, propwash or failure modes are incorporated here.
    """
    if max_thrust_n <= 0 or not (0 < max_tilt_deg < 90):
        raise ValueError("Provide verified positive thrust limit and tilt travel")
    w = np.asarray(target_wrench, float)
    a = allocation_matrix(rotor_centres, cg)
    c = np.tan(np.deg2rad(max_tilt_deg))
    initial = allocate_unconstrained(w, rotor_centres, cg).reshape(-1)
    constraints = [{'type': 'eq', 'fun': lambda x: a @ x - w}]
    for i in range(4):
        start = 3*i
        constraints.append({'type': 'ineq', 'fun':
            lambda x, k=start: c*x[k+2] - np.hypot(x[k], x[k+1])})
        constraints.append({'type': 'ineq', 'fun':
            lambda x, k=start: max_thrust_n - np.linalg.norm(x[k:k+3])})
    bounds = [(None, None), (None, None), (0, None)]*4
    result = minimize(lambda x: 0.5*x@x, initial, jac=lambda x: x,
                      method='SLSQP', constraints=constraints, bounds=bounds,
                      options={'maxiter': 1500, 'ftol': 1.e-10})
    x = result.x.reshape(4, 3)
    residual = a @ x.reshape(-1)-w
    max_tilt = max(force_to_azimuth_and_tilt(f)[1] for f in x)
    accepted = bool(np.linalg.norm(residual) < 1.e-5 and
                    max_tilt <= np.deg2rad(max_tilt_deg)+1.e-6 and
                    np.max(np.linalg.norm(x, axis=1)) <= max_thrust_n+1.e-5)
    return {'feasible': accepted, 'optimizer_success': bool(result.success),
            'rotor_forces_body_n': x.tolist(),
            'force_moment_residual': residual.tolist(),
            'max_rotor_thrust_n': float(np.max(np.linalg.norm(x, axis=1))),
            'max_tilt_deg': float(np.rad2deg(max_tilt)),
            'message': result.message}


def rigid_body_derivative(position_m: np.ndarray, velocity_world_m_s: np.ndarray,
                          attitude_body_to_world: Rotation, omega_body_rad_s: np.ndarray,
                          rotor_forces_body_n: np.ndarray, rotor_centres_m: np.ndarray,
                          cg_m: np.ndarray, mass_kg: float, inertia_about_cg: np.ndarray,
                          aero_force_world_n: np.ndarray, aero_moment_body_nm: np.ndarray,
                          rotor_reaction_moment_body_nm: np.ndarray,
                          gyro_moment_body_nm: np.ndarray) -> dict:
    """Newton-Euler rigid-body 6-DOF state derivatives, with explicit external terms.

    Aerodynamic, rotor reaction and rotor gyroscopic moment inputs must derive from
    real data/models. Supplying zero is valid ONLY as a labelled ideal benchmark.
    """
    inertia = np.asarray(inertia_about_cg, dtype=float)
    omega = np.asarray(omega_body_rad_s, dtype=float)
    forces = np.asarray(rotor_forces_body_n, dtype=float)
    if mass_kg <= 0 or inertia.shape != (3, 3) or min(np.linalg.eigvalsh(inertia)) <= 0:
        raise ValueError('Need positive mass and positive-definite CG inertia tensor')
    a = allocation_matrix(rotor_centres_m, cg_m)
    forces_torques = a @ forces.reshape(-1)
    force_body, mechanical_moment_body = forces_torques[:3], forces_torques[3:]
    acceleration_world = (attitude_body_to_world.apply(force_body) + aero_force_world_n)/mass_kg + np.array([0., 0., -G])
    torque = mechanical_moment_body + aero_moment_body_nm + rotor_reaction_moment_body_nm + gyro_moment_body_nm
    omega_dot = np.linalg.solve(inertia, torque - np.cross(omega, inertia @ omega))
    return {
        'p_dot_m_s': np.asarray(velocity_world_m_s, dtype=float),
        'v_dot_m_s2': acceleration_world,
        'omega_dot_body_rad_s2': omega_dot,
        'q_kinematics_body_rad_s': omega,
        'net_force_body_n': force_body,
        'net_moment_body_nm': torque,
    }


REQUIRED_FIELDS = {
    'mass_kg', 'cg_xyz_m', 'inertia_about_cg_kg_m2', 'rotor_centres_xyz_m',
    'rotor_rotation_directions', 'rotor_shaft_inertias_kg_m2',
    'rotor_speed_rad_s', 'thrust_vs_collective_map', 'torque_vs_collective_map',
    'thrust_transient_response', 'tilt_actuator_response', 'max_rotor_thrust_n',
    'max_rotor_tilt_deg', 'aerodynamic_force_moment_model',
    'controller_gains', 'gimbal_mass_and_inertia',
}


def validate_configuration(obj: dict) -> None:
    missing = sorted(k for k in REQUIRED_FIELDS if obj.get(k) is None)
    if missing:
        raise ValueError('NOT CALIBRATED. Missing measured/validated inputs:\n  - '+'\n  - '.join(missing))
    c = np.asarray(obj['cg_xyz_m'], dtype=float)
    j = np.asarray(obj['inertia_about_cg_kg_m2'], dtype=float)
    pts = np.asarray(obj['rotor_centres_xyz_m'], dtype=float)
    if c.shape != (3,) or pts.shape != (4, 3):
        raise ValueError('Wrong CG or rotor-centre dimensions')
    if j.shape != (3, 3) or min(np.linalg.eigvalsh(j)) <= 0:
        raise ValueError('Measured inertia tensor must be symmetric positive definite')
    if not np.allclose(j, j.T, atol=1e-9):
        raise ValueError('Inertia tensor is not symmetric')
    if obj['mass_kg'] <= 0:
        raise ValueError('Mass must be positive')


def self_test() -> None:
    """Synthetic algebra tests only. Numbers here are not VTX calibration."""
    # Known VTX geometric XY fan radius, synthetic coordinates and various test CGs.
    xyz = np.column_stack((ROTOR_XY_M, np.array([2.31]*4)))
    targets = [np.array([0, 0, 10, 0, 0, 0],float),
               np.array([3, -2, 10, 5, -7, 2],float),
               np.array([-3, 1, 12, -4, 3, -5],float)]
    for center in ([0, 0, 2.31], [.2, -.3, 1.23], [.1, -.1, 0.5]):
        cg = np.asarray(center,float)
        a = allocation_matrix(xyz,cg)
        assert np.linalg.matrix_rank(a) == 6
        for w in targets:
            f = allocate_unconstrained(w,xyz,cg)
            assert np.allclose(a @ f.ravel(),w,rtol=0,atol=1e-10)
    # Exact hover equilibrium for an ideal non-rotating aircraft at the chosen origin.
    m = 1073.0  # P0-V4 *target budget* (not actual weighed aircraft)
    cg = np.array([0.,0.,2.31])  # synthetic CG at rotor plane, not VTX measurement
    f = allocate_unconstrained(np.array([0.,0.,m*G,0.,0.,0.]),xyz,cg)
    plant = rigid_body_derivative(np.zeros(3),np.zeros(3),Rotation.identity(),
        np.zeros(3), f, xyz,cg,m,np.eye(3),
        np.zeros(3),np.zeros(3),np.zeros(3),np.zeros(3))
    assert np.allclose(plant['v_dot_m_s2'],np.zeros(3),atol=1e-12)
    assert np.allclose(plant['omega_dot_body_rad_s2'],np.zeros(3),atol=1e-12)
    # Three-axis rotational rate + actuator lag characteristic condition:
    # J*tau*s^3 + J*s^2 + Kd*s + Kp. Stable for J,Kp,Kd,tau>0 iff Kd>tau*Kp.
    for j, kp, kd, tau in [(1, 12, 5, .1),(100, 200, 25,.1),(1,12,1,.2)]:
        roots = np.roots([j*tau,j,kd,kp])
        analytic = (kd > tau*kp)
        assert bool(np.all(roots.real < -1.e-9)) == analytic
    print('PASSED: rank-6 geometry, arbitrary-CG force/moment residuals,')
    print('ideal hover Newton-Euler acceleration, 3rd-order lag stability screen.')
    print('NOT a VTX stability result: aircraft inertia and rotor response are unavailable.')


def main() -> None:
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test',action='store_true')
    group.add_argument('--validate',type=Path,metavar='CONFIG_JSON')
    args=ap.parse_args()
    if args.self_test:
        self_test()
    else:
        with args.validate.open() as stream:
            data=json.load(stream)
        validate_configuration(data)
        print('Required physical-property fields are populated and structurally valid.')
        print('Actual time-domain simulation additionally requires characterised rotor and aerodynamic functions.')

if __name__=='__main__':
    main()
