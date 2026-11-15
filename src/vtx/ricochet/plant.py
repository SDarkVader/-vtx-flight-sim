"""Authoritative MuJoCo rigid-body plant for Ricochet RC-01 coupled to HybridWaterField.

MuJoCo remains the sole 400 Hz rigid-body integrator (`DT = 0.0025 s`). The
hybrid open-water + shallow-water solver and 3D watertight mesh hydrodynamics
compute separated buoyancy, resistance, dynamic lift/planing, added mass,
damping, and wave excitation forces and apply them physically via
`d.xfrc_applied` on the main hull and instrumented sponson bodies.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from typing import Any

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from vtx.ricochet.concept_a_builder import (
    AILERON_AXIS_PORT,
    AILERON_AXIS_STBD,
    AILERON_HINGE_PORT_VTX,
    AILERON_HINGE_STBD_VTX,
    ELEVATOR_AXIS,
    ELEVATOR_HINGE_VTX,
    FAN_CENTER_PORT_VTX,
    REVERSE_BUCKET_AXIS,
    REVERSE_BUCKET_HINGE_PORT_VTX,
    REVERSE_BUCKET_HINGE_STBD_VTX,
    RUDDER_AXIS,
    RUDDER_HINGE_VTX,
)
from vtx.ricochet.hull_geometry import (
    SPONSON_PORT_MOUNT_VTX_M,
    SPONSON_RADII_M,
    SPONSON_STBD_MOUNT_VTX_M,
    HullVariantBundle,
    HullGeometryRegistry,
)
from vtx.ricochet.mass_register import MassPropertiesRegister
from vtx.ricochet.spec_math import canopy_and_craft_cd0, compute_structural_loads_snapshot
from vtx.water.datum import (
    G_SI,
    RHO_AIR_ISA,
    HydroCalibrationProfile,
    WaterEnvironmentConfig,
)
from vtx.water.hydrodynamics import HydroBreakdown, evaluate_components_hydrodynamics, evaluate_mesh_hydrodynamics
from vtx.water.shallow_water import HybridWaterField

DT = 0.0025
SOLVER_VERSION = 'ricochet-mujoco-hybrid-1.0'

# Authoritative mechanical control surface limits & servo slew rates for Ricochet RC-01
RICOCHET_SURFACE_LIMITS: dict[str, dict[str, Any]] = {
    'throttle': {'min': 0.0, 'max': 1.0, 'unit': 'fraction', 'rate_per_s': 2.5},
    'differential_thrust': {'min': -1.0, 'max': 1.0, 'unit': 'fraction', 'rate_per_s': 4.0},
    'rudder_deg': {'min': -30.0, 'max': 30.0, 'unit': 'deg', 'rate_deg_s': 120.0},
    'elevator_deg': {'min': -20.0, 'max': 20.0, 'unit': 'deg', 'rate_deg_s': 100.0},
    'aileron_deg': {'min': -25.0, 'max': 25.0, 'unit': 'deg', 'rate_deg_s': 120.0},
    'reverse_bucket': {'min': 0.0, 'max': 1.0, 'unit': 'fraction', 'rate_per_s': 2.2, 'max_deg': 85.0},
}

# Physical articulated child bodies mounted onto airframe via real MuJoCo hinge joints
ARTICULATED_CHILD_SPECS: tuple[dict[str, Any], ...] = (
    {
        'body': 'fan_rotor_port',
        'pos': FAN_CENTER_PORT_VTX,
        'joint': 'fan_rotor_port_hinge',
        'axis': (1.0, 0.0, 0.0),
        'limited': False,
        'range_deg': None,
        'damping': 0.02,
        'armature': 0.02,
        'mass': 4.2,
        'diaginertia': (0.11, 0.06, 0.06),
        'actuator_type': 'motor',
        'actuator_name': 'fan_motor_port',
        'ctrlrange': (-220.0, 220.0),
        'forcerange': (-200.0, 200.0),
        'dummy_size': 0.16,
    },
    {
        'body': 'fan_rotor_stbd',
        'pos': (FAN_CENTER_PORT_VTX[0], -FAN_CENTER_PORT_VTX[1], FAN_CENTER_PORT_VTX[2]),
        'joint': 'fan_rotor_stbd_hinge',
        'axis': (-1.0, 0.0, 0.0),  # counter-rotating
        'limited': False,
        'range_deg': None,
        'damping': 0.02,
        'armature': 0.02,
        'mass': 4.2,
        'diaginertia': (0.11, 0.06, 0.06),
        'actuator_type': 'motor',
        'actuator_name': 'fan_motor_stbd',
        'ctrlrange': (-220.0, 220.0),
        'forcerange': (-200.0, 200.0),
        'dummy_size': 0.16,
    },
    {
        'body': 'aileron_port',
        'pos': AILERON_HINGE_PORT_VTX,
        'joint': 'aileron_port_hinge',
        'axis': AILERON_AXIS_PORT,
        'limited': True,
        'range_deg': (-25.0, 25.0),
        'damping': 1.2,
        'armature': 0.05,
        'mass': 2.2,
        'diaginertia': (0.12, 0.03, 0.13),
        'actuator_type': 'servo',
        'actuator_name': 'aileron_port_servo',
        'kp': 360.0,
        'kv': 18.0,
        'forcerange': (-260.0, 260.0),
        'dummy_size': 0.05,
    },
    {
        'body': 'aileron_stbd',
        'pos': AILERON_HINGE_STBD_VTX,
        'joint': 'aileron_stbd_hinge',
        'axis': AILERON_AXIS_STBD,
        'limited': True,
        'range_deg': (-25.0, 25.0),
        'damping': 1.2,
        'armature': 0.05,
        'mass': 2.2,
        'diaginertia': (0.12, 0.03, 0.13),
        'actuator_type': 'servo',
        'actuator_name': 'aileron_stbd_servo',
        'kp': 360.0,
        'kv': 18.0,
        'forcerange': (-260.0, 260.0),
        'dummy_size': 0.05,
    },
    {
        'body': 'elevator',
        'pos': ELEVATOR_HINGE_VTX,
        'joint': 'elevator_hinge',
        'axis': ELEVATOR_AXIS,
        'limited': True,
        'range_deg': (-20.0, 20.0),
        'damping': 1.4,
        'armature': 0.06,
        'mass': 2.8,
        'diaginertia': (0.20, 0.04, 0.22),
        'actuator_type': 'servo',
        'actuator_name': 'elevator_servo',
        'kp': 400.0,
        'kv': 20.0,
        'forcerange': (-300.0, 300.0),
        'dummy_size': 0.05,
    },
    {
        'body': 'rudder',
        'pos': RUDDER_HINGE_VTX,
        'joint': 'rudder_hinge',
        'axis': RUDDER_AXIS,
        'limited': True,
        'range_deg': (-30.0, 30.0),
        'damping': 1.4,
        'armature': 0.06,
        'mass': 2.2,
        'diaginertia': (0.08, 0.09, 0.03),
        'actuator_type': 'servo',
        'actuator_name': 'rudder_servo',
        'kp': 400.0,
        'kv': 20.0,
        'forcerange': (-300.0, 300.0),
        'dummy_size': 0.05,
    },
    {
        'body': 'reverse_bucket_port',
        'pos': REVERSE_BUCKET_HINGE_PORT_VTX,
        'joint': 'reverse_bucket_port_hinge',
        'axis': REVERSE_BUCKET_AXIS,
        'limited': True,
        'range_deg': (0.0, 85.0),
        'damping': 1.8,
        'armature': 0.08,
        'mass': 1.8,
        'diaginertia': (0.04, 0.05, 0.05),
        'actuator_type': 'servo',
        'actuator_name': 'reverse_bucket_port_servo',
        'kp': 440.0,
        'kv': 22.0,
        'forcerange': (-360.0, 360.0),
        'dummy_size': 0.05,
    },
    {
        'body': 'reverse_bucket_stbd',
        'pos': REVERSE_BUCKET_HINGE_STBD_VTX,
        'joint': 'reverse_bucket_stbd_hinge',
        'axis': REVERSE_BUCKET_AXIS,
        'limited': True,
        'range_deg': (0.0, 85.0),
        'damping': 1.8,
        'armature': 0.08,
        'mass': 1.8,
        'diaginertia': (0.04, 0.05, 0.05),
        'actuator_type': 'servo',
        'actuator_name': 'reverse_bucket_stbd_servo',
        'kp': 440.0,
        'kv': 22.0,
        'forcerange': (-360.0, 360.0),
        'dummy_size': 0.05,
    },
)

CHILD_BODY_POS_BY_NAME: dict[str, tuple[float, float, float]] = {
    spec['body']: tuple(float(v) for v in spec['pos'])
    for spec in ARTICULATED_CHILD_SPECS
}


def _parallel_axis_tensor(mass_kg: float, pos: np.ndarray, local_diag: np.ndarray) -> np.ndarray:
    r2 = float(np.dot(pos, pos))
    return np.diag(local_diag) + mass_kg * (r2 * np.eye(3) - np.outer(pos, pos))


def _subtract_child_inertias(
    total_mass_kg: float,
    cg_vtx_m: np.ndarray,
    inertia_com_kg_m2: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Subtract articulated child bodies + virtual cabin from airframe inertial so vehicle total matches register."""
    m_tot = float(total_mass_kg)
    cg = np.asarray(cg_vtx_m, dtype=np.float64)
    i_origin = np.asarray(inertia_com_kg_m2, dtype=np.float64) + m_tot * (
        float(np.dot(cg, cg)) * np.eye(3) - np.outer(cg, cg)
    )
    children = [(float(s['mass']), np.asarray(s['pos'], dtype=np.float64), np.asarray(s['diaginertia'], dtype=np.float64)) for s in ARTICULATED_CHILD_SPECS]
    children.append((0.01, np.array([1.20, 0.0, 0.90], dtype=np.float64), np.array([0.001, 0.001, 0.001], dtype=np.float64)))

    m_sub = 0.0
    mr_sub = np.zeros(3, dtype=np.float64)
    i_sub = np.zeros((3, 3), dtype=np.float64)
    for mc, pc, idc in children:
        m_sub += mc
        mr_sub += mc * pc
        i_sub += _parallel_axis_tensor(mc, pc, idc)

    m_af = max(m_tot - m_sub, 20.0)
    cg_af = (m_tot * cg - mr_sub) / m_af
    i_af_origin = i_origin - i_sub
    i_af = i_af_origin - m_af * (float(np.dot(cg_af, cg_af)) * np.eye(3) - np.outer(cg_af, cg_af))
    return m_af, cg_af, 0.5 * (i_af + i_af.T)


def is_ricochet_variant(name: str | None) -> bool:
    if not name:
        return False
    return str(name).strip().lower() in (
        'ricochet',
        'ricochet-rc01',
        'ricochet-rc01-f03',
        'ricochet-rc01-dev',
        'ricochet-concept-a',
    )


def _body_state(d: mj.MjData, bid: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract world (xipos_com, rot_3x3, vel_com, omega, acc_com, alpha) for a MuJoCo body."""
    pos_origin = d.xpos[bid].copy()
    xipos = d.xipos[bid].copy()
    rot = d.xmat[bid].reshape(3, 3).copy()
    # cvel is 6D spatial velocity [ang(3), lin_com(3)] around subtree_com in world-oriented frame at xipos
    cvel = d.cvel[bid]
    omega = cvel[:3].copy()
    # Exact point velocity of body origin / CoM in world frame:
    vel_com = cvel[3:].copy()
    cacc = d.cacc[bid]
    alpha = cacc[:3].copy()
    acc_com = cacc[3:].copy()
    return pos_origin, xipos, rot, vel_com, omega, acc_com, alpha


def build_ricochet_mujoco_model(
    world,
    mass_reg: MassPropertiesRegister,
    hull_bundle: HullVariantBundle,
    ignore_scenery_collisions: bool = False,
) -> tuple[mj.MjModel, str]:
    """Build MuJoCo XML + binary hfield data sharing exact world geometry and datum."""
    xml = ET.Element('mujoco', model='vtx_ricochet_rc01')
    ET.SubElement(xml, 'compiler', angle='degree', coordinate='local', inertiafromgeom='false')
    ET.SubElement(xml, 'option', timestep=str(DT), gravity=f'0 0 -{G_SI}', integrator='implicitfast')

    default = ET.SubElement(xml, 'default')
    ET.SubElement(default, 'geom', friction='0.35 0.02 0.01', solref='0.02 1', solimp='0.9 0.95 0.002')

    asset = ET.SubElement(xml, 'asset')
    if hasattr(world, 'nx') and hasattr(world, 'ny'):
        nx, ny = int(world.nx), int(world.ny)
        hx, hy = float(world.half_x), float(world.half_y)
        z_min = float(world.z_min)
        z_max = float(world.z_max)
        z_span = max(z_max - z_min + 2.0, 20.0)
        hfield_base = 5.0
    else:
        nx = ny = int(world.n)
        hx = hy = float(world.half)
        z_min = 0.0
        z_span = 70.0
        hfield_base = 2.0

    ET.SubElement(
        asset,
        'hfield',
        name='terrain',
        nrow=str(ny),
        ncol=str(nx),
        size=f'{hx} {hy} {z_span} {hfield_base}',
    )

    def _add_mesh_asset(asset_name: str, wmesh) -> None:
        verts_str = ' '.join(f'{v[0]:.5f} {v[1]:.5f} {v[2]:.5f}' for v in wmesh.vertices)
        faces_str = ' '.join(f'{int(f[0])} {int(f[1])} {int(f[2])}' for f in wmesh.faces)
        ET.SubElement(asset, 'mesh', name=asset_name, vertex=verts_str, face=faces_str)

    # Pin MuJoCo rigid-body mesh assets directly to the authoritative hydrodynamic geometry
    _add_mesh_asset('main_hull_mesh', hull_bundle.main_hull.mesh)
    _add_mesh_asset('sponson_port_mesh', hull_bundle.port_sponson.mesh)
    _add_mesh_asset('sponson_stbd_mesh', hull_bundle.stbd_sponson.mesh)
    for part_key, spec in getattr(hull_bundle, 'airframe_meshes', {}).items():
        if spec.get('pin_to_mujoco'):
            _add_mesh_asset(f'{part_key}_mesh', spec['mesh'])

    wb = ET.SubElement(xml, 'worldbody')
    ET.SubElement(
        wb,
        'geom',
        name='terrain',
        type='hfield',
        hfield='terrain',
        pos=f'0 0 {z_min}',
        contype='1',
        conaffinity='2',
        friction='0.45 0.02 0.01',
    )

    if not ignore_scenery_collisions:
        # Static collidable marina piers, quay, breakwater, and mooring buoys matching world.public()
        for s in getattr(world, 'structures', []):
            if not s.get('collidable', True):
                continue
            cx, cy, cz = s['center']
            sx, sy, sz = s['half_extents']
            yaw = float(s.get('yaw_deg', 0.0))
            ET.SubElement(
                wb,
                'geom',
                name=f"struct_{s['id']}",
                type='box',
                pos=f'{cx} {cy} {cz}',
                size=f'{sx} {sy} {sz}',
                euler=f'0 0 {yaw}',
                contype='1',
                conaffinity='2',
                friction='0.5 0.02 0.01',
            )
        for b in getattr(world, 'buoys', []):
            if not b.get('collidable', True):
                continue
            r = float(b['radius_m'])
            h = float(b['height_m'])
            wl = float(getattr(world, 'water_level', 0.0))
            ET.SubElement(
                wb,
                'geom',
                name=f"buoy_{b['id']}",
                type='cylinder',
                pos=f"{b['x']} {b['y']} {wl + 0.15}",
                size=f'{r} {0.5 * h}',
                contype='1',
                conaffinity='2',
                friction='0.2 0.01 0.01',
            )

    # Core airframe rigid body (freejoint + aggregated core mass minus child articulated bodies)
    core_agg = mass_reg.aggregate(include_sponsons=False)
    core_m, core_cg, inert = _subtract_child_inertias(
        core_agg['total_mass_kg'],
        core_agg['cg_vtx_m'],
        core_agg['inertia_vtx_kg_m2'],
    )
    # MuJoCo fullinertia order: Ixx, Iyy, Izz, Ixy, Ixz, Iyz
    fullinertia = (
        f'{inert[0,0]:.4f} {inert[1,1]:.4f} {inert[2,2]:.4f} '
        f'{inert[0,1]:.4f} {inert[0,2]:.4f} {inert[1,2]:.4f}'
    )

    af = ET.SubElement(wb, 'body', name='airframe', pos='0 0 0')
    ET.SubElement(af, 'freejoint', name='root')
    ET.SubElement(
        af,
        'inertial',
        pos=f'{core_cg[0]:.5f} {core_cg[1]:.5f} {core_cg[2]:.5f}',
        mass=f'{core_m:.4f}',
        fullinertia=fullinertia,
    )

    # Main hull physical collider pinned directly to main_hull_mesh (zero hardcoded proxy capsules)
    ET.SubElement(
        af,
        'geom',
        name='main_hull_geom',
        type='mesh',
        mesh='main_hull_mesh',
        contype='2',
        conaffinity='1',
        friction='0.28 0.01 0.01',
    )
    pinned_airframe_parts = [
        (part_key, spec)
        for part_key, spec in getattr(hull_bundle, 'airframe_meshes', {}).items()
        if spec.get('pin_to_mujoco')
    ]
    if pinned_airframe_parts:
        for part_key, spec in pinned_airframe_parts:
            if str(spec.get('body', 'airframe')) != 'airframe':
                continue
            off = spec.get('offset', [0.0, 0.0, 0.0])
            ET.SubElement(
                af,
                'geom',
                name=f'{part_key}_geom',
                type='mesh',
                mesh=f'{part_key}_mesh',
                pos=f'{float(off[0]):.4f} {float(off[1]):.4f} {float(off[2]):.4f}',
                contype='2',
                conaffinity='1',
                friction='0.25 0.01 0.01',
            )
    else:
        ET.SubElement(
            af,
            'geom',
            name='wing_port_geom',
            type='box',
            pos='0.02 2.80 1.15',
            size='0.75 2.00 0.06',
            euler='2.0 0 0',
            contype='2',
            conaffinity='1',
        )
        ET.SubElement(
            af,
            'geom',
            name='wing_stbd_geom',
            type='box',
            pos='0.02 -2.80 1.15',
            size='0.75 2.00 0.06',
            euler='-2.0 0 0',
            contype='2',
            conaffinity='1',
        )
        ET.SubElement(
            af,
            'geom',
            name='tail_pylon_geom',
            type='capsule',
            fromto='-1.75 0 1.02 -2.62 0 2.30',
            size='0.12',
            contype='2',
            conaffinity='1',
        )
    ET.SubElement(af, 'site', name='cg_site', pos=f'{core_cg[0]:.5f} {core_cg[1]:.5f} {core_cg[2]:.5f}')
    # Virtual cabin site for camera & compatibility with cabin telemetry queries
    cabin = ET.SubElement(af, 'body', name='cabin', pos='1.20 0 0.90')
    ET.SubElement(cabin, 'inertial', pos='0 0 0', mass='0.01', diaginertia='0.001 0.001 0.001')

    # Articulated twin ducted fan rotors + primary/reverse control surfaces via MuJoCo hinge joints
    child_mesh_parts: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for part_key, spec in pinned_airframe_parts:
        bname = str(spec.get('body', 'airframe'))
        if bname != 'airframe':
            child_mesh_parts.setdefault(bname, []).append((part_key, spec))

    actuator_el = ET.Element('actuator')
    for spec in ARTICULATED_CHILD_SPECS:
        bname = spec['body']
        px, py, pz = spec['pos']
        cb = ET.SubElement(af, 'body', name=bname, pos=f'{px:.5f} {py:.5f} {pz:.5f}')
        ixx, iyy, izz = spec['diaginertia']
        ET.SubElement(
            cb,
            'inertial',
            pos='0 0 0',
            mass=f"{spec['mass']:.4f}",
            diaginertia=f'{ixx:.5f} {iyy:.5f} {izz:.5f}',
        )
        ax, ay, az = spec['axis']
        jnt_attrs = {
            'name': spec['joint'],
            'type': 'hinge',
            'pos': '0 0 0',
            'axis': f'{ax:.6f} {ay:.6f} {az:.6f}',
            'limited': 'true' if spec['limited'] else 'false',
            'damping': f"{spec['damping']:.4f}",
            'armature': f"{spec['armature']:.4f}",
        }
        if spec['limited'] and spec['range_deg'] is not None:
            r0, r1 = spec['range_deg']
            jnt_attrs['range'] = f'{r0:.3f} {r1:.3f}'
        ET.SubElement(cb, 'joint', **jnt_attrs)

        attached = child_mesh_parts.get(bname, [])
        is_rotor = bname.startswith('fan_rotor_')
        if attached:
            for part_key, pspec in attached:
                poff = pspec.get('offset', [px, py, pz])
                dx = float(poff[0]) - float(px)
                dy = float(poff[1]) - float(py)
                dz = float(poff[2]) - float(pz)
                ET.SubElement(
                    cb,
                    'geom',
                    name=f'{part_key}_geom',
                    type='mesh',
                    mesh=f'{part_key}_mesh',
                    pos=f'{dx:.5f} {dy:.5f} {dz:.5f}',
                    contype='0' if is_rotor else '2',
                    conaffinity='0' if is_rotor else '1',
                    friction='0.22 0.01 0.01',
                )
        else:
            ET.SubElement(
                cb,
                'geom',
                name=f'{bname}_geom',
                type='sphere',
                size=f"{spec['dummy_size']:.3f}",
                contype='0',
                conaffinity='0',
            )

        fmin, fmax = spec['forcerange']
        if spec['actuator_type'] == 'motor':
            cmin, cmax = spec['ctrlrange']
            ET.SubElement(
                actuator_el,
                'motor',
                name=spec['actuator_name'],
                joint=spec['joint'],
                ctrllimited='true',
                ctrlrange=f'{cmin:.3f} {cmax:.3f}',
                forcelimited='true',
                forcerange=f'{fmin:.3f} {fmax:.3f}',
            )
        else:
            r0_deg, r1_deg = spec['range_deg']
            r0_rad, r1_rad = math.radians(r0_deg), math.radians(r1_deg)
            ET.SubElement(
                actuator_el,
                'position',
                name=spec['actuator_name'],
                joint=spec['joint'],
                kp=f"{spec['kp']:.2f}",
                kv=f"{spec['kv']:.2f}",
                ctrllimited='true',
                ctrlrange=f'{r0_rad:.6f} {r1_rad:.6f}',
                forcelimited='true',
                forcerange=f'{fmin:.3f} {fmax:.3f}',
            )

    # Instrumented port & starboard sponsons mounted via stiff flex joints to measure attachment loads
    if hull_bundle.variant_id == 'concept_a':
        from vtx.ricochet.hull_geometry import SPONSON_CONCEPT_A_MOUNT_VTX_M, SPONSON_CONCEPT_A_STBD_MOUNT_VTX_M
        from vtx.ricochet.spec_math import COMPONENT_RIGIDITY_SPECS
        _sp_spec = COMPONENT_RIGIDITY_SPECS['sponson_strut_assembly']
        _sp_k = f'{_sp_spec.stiffness_n_per_m:.1f}'
        _sp_c = f'{max(_sp_spec.damping_ns_per_m, 950.0):.1f}'
        sponson_specs = [
            ('sponson_port', SPONSON_CONCEPT_A_MOUNT_VTX_M),
            ('sponson_stbd', SPONSON_CONCEPT_A_STBD_MOUNT_VTX_M),
        ]
    else:
        _sp_k = '28000'
        _sp_c = '600'
        sponson_specs = [
            ('sponson_port', SPONSON_PORT_MOUNT_VTX_M),
            ('sponson_stbd', SPONSON_STBD_MOUNT_VTX_M),
        ]
    for sname, spos in sponson_specs:
        sb = ET.SubElement(af, 'body', name=sname, pos=f'{spos[0]:.4f} {spos[1]:.4f} {spos[2]:.4f}')
        ET.SubElement(sb, 'inertial', pos='0 0 0', mass='12.0', diaginertia='0.8 1.6 1.6')
        ET.SubElement(
            sb,
            'joint',
            name=f'{sname}_flex_z',
            type='slide',
            axis='0 0 1',
            limited='true',
            range='-0.06 0.06',
            stiffness=_sp_k,
            damping=_sp_c,
        )
        ET.SubElement(sb, 'site', name=f'{sname}_mount', pos='0 0 0')
        ET.SubElement(
            sb,
            'geom',
            name=f'{sname}_geom',
            type='mesh',
            mesh=f'{sname}_mesh',
            contype='2',
            conaffinity='1',
        )

    xml.append(actuator_el)
    sensor = ET.SubElement(xml, 'sensor')
    ET.SubElement(sensor, 'force', name='sponson_port_force', site='sponson_port_mount')
    ET.SubElement(sensor, 'force', name='sponson_stbd_force', site='sponson_stbd_mount')
    ET.SubElement(sensor, 'torque', name='sponson_port_torque', site='sponson_port_mount')
    ET.SubElement(sensor, 'torque', name='sponson_stbd_torque', site='sponson_stbd_mount')

    text = ET.tostring(xml, encoding='unicode')
    model = mj.MjModel.from_xml_string(text)
    if hasattr(world, 'nx') and hasattr(world, 'ny'):
        model.hfield_data[:] = ((world.heights - world.z_min) / z_span).ravel()
    else:
        model.hfield_data[:] = (world.heights / 70.0).ravel()
    return model, text


class RicochetCraft:
    """Ricochet RC-01 MuJoCo vehicle plant coupled to VTX HybridWaterField."""

    is_ricochet = True
    is_phantom = False
    DT = DT
    SOLVER_VERSION = SOLVER_VERSION

    # Provisional actuator/aerodynamic caps until wind-tunnel / bollard-pull testing
    MAX_THRUST_PER_FAN_N = 1450.0  # 2,900 N total forward bollard thrust (~0.33 T/W ratio)

    def __init__(
        self,
        world,
        variant: str = 'ricochet-rc01-dev',
        hull_variant: str = 'f03_baseline',
        load_case: str = 'LC-03',
        water_config: WaterEnvironmentConfig | None = None,
        calibration: HydroCalibrationProfile | None = None,
        subdivide_levels: int = 0,
        hydro_stride: int = 1,
        ignore_scenery_collisions: bool = False,
        concept_a_glb_path: str | None = None,
    ):
        self.world = world
        self.variant = variant
        self.airframe_variant = variant
        self.hull_variant = hull_variant
        self.hydro_stride = max(1, int(hydro_stride))
        self.ignore_scenery_collisions = bool(ignore_scenery_collisions)
        self.calibration = calibration or HydroCalibrationProfile()
        self.hull_bundle = HullGeometryRegistry.build_variant(
            variant_id=hull_variant,
            subdivide_levels=subdivide_levels,
            concept_a_glb_path=concept_a_glb_path,
        )
        self.mass_register = MassPropertiesRegister.for_load_case(
            load_case=load_case,
            sponson_z_m=0.48 if self.hull_bundle.variant_id == 'concept_a' else 0.42,
        )
        self.water_config = water_config or WaterEnvironmentConfig()
        self.water_field = HybridWaterField(world, self.water_config)

        self.model, self.xml = build_ricochet_mujoco_model(
            world,
            self.mass_register,
            self.hull_bundle,
            ignore_scenery_collisions=self.ignore_scenery_collisions,
        )
        self.data = mj.MjData(self.model)

        self.bids = {
            'airframe': mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_BODY, 'airframe'),
            'cabin': mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_BODY, 'cabin'),
            'sponson_port': mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_BODY, 'sponson_port'),
            'sponson_stbd': mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_BODY, 'sponson_stbd'),
        }
        for spec in ARTICULATED_CHILD_SPECS:
            self.bids[spec['body']] = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_BODY, spec['body'])

        self.jids: dict[str, int] = {}
        for i in range(self.model.njnt):
            jname = mj.mj_id2name(self.model, mj.mjtObj.mjOBJ_JOINT, i)
            if jname:
                self.jids[jname] = i

        self.aids: dict[str, int] = {}
        for i in range(self.model.nu):
            aname = mj.mj_id2name(self.model, mj.mjtObj.mjOBJ_ACTUATOR, i)
            if aname:
                self.aids[aname] = i

        self._sensor_slices = self._map_sensors()

        # Compatibility attributes expected by Laboratory / dashboard
        self.command = {
            'throttle': 0.0,
            'differential_thrust': 0.0,
            'rudder_deg': 0.0,
            'elevator_deg': 0.0,
            'aileron_deg': 0.0,
            'reverse_bucket': 0.0,
        }
        self._targets = dict(self.command)
        self.stability_assist = 0.0
        self.wind = self._wind_vector_from_config()
        self.fuel_initial = np.array([10.0], dtype=np.float64)
        self.fuel = np.array([10.0], dtype=np.float64)
        self.rotors = [
            {'side': 'port', 'torque_nm': 0.0, 'aero_torque_nm': 0.0, 'omega_rad_s': 0.0, 'rpm': 0.0, 'thrust_n': 0.0, 'shaft_power_w': 0.0, 'reverser_frac': 0.0, 'spool_fraction': 0.0},
            {'side': 'stbd', 'torque_nm': 0.0, 'aero_torque_nm': 0.0, 'omega_rad_s': 0.0, 'rpm': 0.0, 'thrust_n': 0.0, 'shaft_power_w': 0.0, 'reverser_frac': 0.0, 'spool_fraction': 0.0},
        ]
        self.power = {'engine_w': 0.0, 'propulsion_w': 0.0, 'servo_w': 0.0, 'total_w': 0.0}
        self.energy = {'remaining_kwh': 20.0, 'consumed_kwh': 0.0, 'fuel_burn_kg_s': 0.0}
        self.events: list[dict[str, Any]] = []
        self.flags: set[str] = set()
        self.crashed = False
        self.max_alt = 0.0
        self.max_impact_n = 0.0
        self.max_gear_load_n = 0.0
        self.max_nongear_impact_n = 0.0
        self.step_count = 0
        self.last_collision: dict[str, Any] | None = None
        self.last_hydro: HydroBreakdown | None = None
        self._prev_hydro_f: dict[int, np.ndarray] = {}
        self._curr_hydro_f: dict[int, np.ndarray] = {}
        self.last_propulsion_n = np.zeros(3, dtype=np.float64)
        self.last_propulsion_torque_nm = np.zeros(3, dtype=np.float64)
        self.last_aero_force_n = np.zeros(3, dtype=np.float64)
        self.last_aero_torque_nm = np.zeros(3, dtype=np.float64)
        self.last_aero_detail: dict[str, Any] = {'surfaces': {}, 'hinge_moments': {}}
        self._last_aero_munk_nm = np.zeros(3, dtype=np.float64)
        self.last_munk_moment_nm = np.zeros(3, dtype=np.float64)
        self.last_cn_yaw = 0.0
        self.last_cn_beta = 0.095
        self.last_fan_rpm = [0.0, 0.0]
        self.last_thrust_per_fan_n = [0.0, 0.0]
        self._last_fan_motor_torque_nm = [0.0, 0.0]
        self._last_fan_aero_torque_nm = [0.0, 0.0]
        self._last_servo_saturated: dict[str, bool] = {}
        self._last_applied_flood_kg = 0.0
        self._last_whirlpool_hazard = (
            self.world.whirlpool_hazard_at(0.0, 0.0, config=self.water_config)
            if hasattr(self.world, 'whirlpool_hazard_at')
            else {}
        )

        self._apply_mass_to_mujoco()

    def _map_sensors(self) -> dict[str, tuple[int, int]]:
        slices = {}
        for i in range(self.model.nsensor):
            name = mj.mj_id2name(self.model, mj.mjtObj.mjOBJ_SENSOR, i)
            adr = int(self.model.sensor_adr[i])
            dim = int(self.model.sensor_dim[i])
            slices[name] = (adr, dim)
        return slices

    def _wind_vector_from_config(self) -> np.ndarray:
        spd = float(self.water_config.wind_speed_mps)
        ang = math.radians(float(self.water_config.wind_direction_deg))
        return np.array([spd * math.cos(ang), spd * math.sin(ang), 0.0], dtype=np.float64)

    def _apply_mass_to_mujoco(self) -> None:
        agg = self.mass_register.aggregate(include_sponsons=False)
        bid = self.bids['airframe']
        m_af, cg_af, iner = _subtract_child_inertias(
            agg['total_mass_kg'],
            agg['cg_vtx_m'],
            agg['inertia_vtx_kg_m2'],
        )
        self.model.body_mass[bid] = m_af
        self.model.body_ipos[bid] = np.asarray(cg_af, dtype=np.float64)
        # Recompute principal inertia + orientation in MuJoCo (body_inertia + body_iquat)
        eigvals, eigvecs = np.linalg.eigh(0.5 * (iner + iner.T))
        if np.linalg.det(eigvecs) < 0.0:
            eigvecs[:, 0] = -eigvecs[:, 0]
        eigvals = np.maximum(eigvals, 1.0)
        self.model.body_inertia[bid] = eigvals
        q_xyzw = Rotation.from_matrix(eigvecs).as_quat()
        self.model.body_iquat[bid] = np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]], dtype=np.float64)
        # Preserve live rigid-body state across mj_setConst (which resets qpos -> qpos0)
        qpos_saved = self.data.qpos.copy()
        qvel_saved = self.data.qvel.copy()
        act_saved = self.data.act.copy() if self.model.na > 0 else None
        ctrl_saved = self.data.ctrl.copy() if self.model.nu > 0 else None
        time_saved = float(self.data.time)
        mj.mj_setConst(self.model, self.data)
        self.data.qpos[:] = qpos_saved
        self.data.qvel[:] = qvel_saved
        if act_saved is not None:
            self.data.act[:] = act_saved
        if ctrl_saved is not None:
            self.data.ctrl[:] = ctrl_saved
        self.data.time = time_saved
        mj.mj_forward(self.model, self.data)
        self._last_applied_flood_kg = float(self.mass_register.flood_water_kg)

    def update_mass_properties(
        self,
        load_case: str | None = None,
        total_mass_kg: float | None = None,
        cg_shift_vtx_m: list[float] | tuple[float, float, float] | None = None,
        passenger_aboard: bool | None = None,
        passenger_mass_kg: float | None = None,
        payload_mass_kg: float | None = None,
        ballast_mass_kg: float | None = None,
        ballast_x_m: float | None = None,
        ballast_y_m: float | None = None,
        waterproof: bool | None = None,
        flood_water_kg: float | None = None,
        bilge_pump: bool = False,
    ) -> dict[str, Any]:
        if bilge_pump:
            flood_water_kg = 0.0
        if load_case is not None and load_case.upper() != self.mass_register.load_case:
            prev_ballast = self.mass_register.ballast_mass_kg if ballast_mass_kg is None else ballast_mass_kg
            prev_bx = self.mass_register.ballast_x_m if ballast_x_m is None else ballast_x_m
            prev_by = self.mass_register.ballast_y_m if ballast_y_m is None else ballast_y_m
            prev_wp = self.mass_register.waterproof if waterproof is None else waterproof
            prev_fw = self.mass_register.flood_water_kg if flood_water_kg is None else flood_water_kg
            self.mass_register = MassPropertiesRegister.for_load_case(
                load_case=load_case,
                passenger_aboard=passenger_aboard,
                passenger_mass_kg=passenger_mass_kg,
                payload_mass_kg=payload_mass_kg,
                sponson_z_m=0.48 if self.hull_bundle.variant_id == 'concept_a' else 0.42,
                ballast_mass_kg=prev_ballast,
                ballast_x_m=prev_bx,
                ballast_y_m=prev_by,
                waterproof=prev_wp,
            )
            self.mass_register.flood_water_kg = max(0.0, float(prev_fw))
            if total_mass_kg is not None or cg_shift_vtx_m is not None:
                self.mass_register.set_runtime_override(
                    total_mass_kg=total_mass_kg,
                    cg_shift_vtx_m=cg_shift_vtx_m,
                )
        else:
            self.mass_register.set_runtime_override(
                total_mass_kg=total_mass_kg,
                cg_shift_vtx_m=cg_shift_vtx_m,
                passenger_aboard=passenger_aboard,
                passenger_mass_kg=passenger_mass_kg,
                payload_mass_kg=payload_mass_kg,
                ballast_mass_kg=ballast_mass_kg,
                ballast_x_m=ballast_x_m,
                ballast_y_m=ballast_y_m,
                waterproof=waterproof,
                flood_water_kg=flood_water_kg,
            )
        self._apply_mass_to_mujoco()
        return self.mass_properties()

    def update_water_config(self, payload: dict[str, Any] | WaterEnvironmentConfig) -> WaterEnvironmentConfig:
        cfg = self.water_field.reconfigure(payload)
        self.water_config = cfg
        self.wind = self._wind_vector_from_config()
        return cfg

    def set_wind(self, wind) -> None:
        self.wind = np.asarray(wind, dtype=np.float64)

    def spawn(self, x: float, y: float, z: float, yaw_deg: float = 0.0, roll_deg: float = 0.0, pitch_deg: float = 0.0) -> None:
        if self.mass_register.flood_water_kg > 1e-6 or self._last_applied_flood_kg > 1e-6:
            self.mass_register.flood_water_kg = 0.0
            self._apply_mass_to_mujoco()
        mj.mj_resetData(self.model, self.data)
        # When spawning at surface_z (or accidentally passed submerged lakebed terrain_z)
        # over navigable water, initialize near calm draft; explicit elevated drop z (> wl + 0.05) stays verbatim.
        wl = float(self.water_config.water_level_m)
        bed = float(self.world.terrain_z(x, y))
        target_draft = 0.56 if self.hull_bundle.variant_id == 'concept_a' else 0.37
        if bed < wl - 0.25 and (abs(z - max(bed, wl)) < 0.05 or z <= wl - 0.05):
            spawn_z = max(bed + 0.02, wl - target_draft)
        else:
            spawn_z = max(z, bed + 0.02)
        self.data.qpos[0:3] = np.array([float(x), float(y), spawn_z], dtype=np.float64)
        rot = Rotation.from_euler('xyz', [roll_deg, pitch_deg, yaw_deg], degrees=True)
        qx, qy, qz, qw = rot.as_quat()
        self.data.qpos[3:7] = np.array([qw, qx, qy, qz], dtype=np.float64)
        self.data.qvel[:] = 0.0
        self.data.qfrc_applied[:] = 0.0
        self.data.xfrc_applied[:] = 0.0
        self.data.ctrl[:] = 0.0
        self._targets = dict(self.command)
        self.fuel[:] = self.fuel_initial[:]
        self.energy = {'remaining_kwh': 20.0, 'consumed_kwh': 0.0, 'fuel_burn_kg_s': 0.0}
        self.power = {'engine_w': 0.0, 'propulsion_w': 0.0, 'servo_w': 0.0, 'total_w': 0.0}
        self.last_fan_rpm = [0.0, 0.0]
        self.last_thrust_per_fan_n = [0.0, 0.0]
        self._last_fan_motor_torque_nm = [0.0, 0.0]
        self._last_fan_aero_torque_nm = [0.0, 0.0]
        self._last_servo_saturated.clear()
        self.step_count = 0
        self.crashed = False
        self.max_impact_n = 0.0
        self.events.clear()
        self.flags.clear()
        self._prev_hydro_f.clear()
        self._curr_hydro_f.clear()
        self.water_field._vessel_wake['active'] = False
        self._last_whirlpool_hazard = (
            self.world.whirlpool_hazard_at(float(x), float(y), config=self.water_config)
            if hasattr(self.world, 'whirlpool_hazard_at')
            else {}
        )
        mj.mj_forward(self.model, self.data)
        # Populate initial hydrostatic state telemetry cleanly at t=0
        self._evaluate_and_cache_hydro(t=float(self.data.time), force_eval=True)

    def set_command(self, cmd: dict[str, Any]) -> None:
        for key, lim in RICOCHET_SURFACE_LIMITS.items():
            val = cmd.get(key)
            if val is not None:
                self.command[key] = float(np.clip(float(val), float(lim['min']), float(lim['max'])))

    def _slew_targets(self, dt: float) -> None:
        """Rate-limit actuator targets toward self.command using physical servo/throttle slew limits."""
        for key, lim in RICOCHET_SURFACE_LIMITS.items():
            rate = float(lim.get('rate_deg_s', lim.get('rate_per_s', 100.0)))
            max_delta = rate * dt
            cur = float(self._targets[key])
            des = float(self.command[key])
            delta = float(np.clip(des - cur, -max_delta, max_delta))
            self._targets[key] = float(np.clip(cur + delta, float(lim['min']), float(lim['max'])))

    def _apply_actuator_controls(self, u_rel_mps: float) -> tuple[list[float], list[float]]:
        """Drive physical MuJoCo control servos and fan rotor motors; return (tau_motor, tau_aero_drag)."""
        d = self.data
        # Position servos (target joint angles in radians)
        ail_deg = float(self._targets['aileron_deg'])
        elev_deg = float(self._targets['elevator_deg'])
        rud_deg = float(self._targets['rudder_deg'])
        rev_deg = 85.0 * float(self._targets['reverse_bucket'])

        servo_targets_rad = {
            'aileron_port_servo': math.radians(-ail_deg),  # +aileron_deg = right roll => port TE down (-q)
            'aileron_stbd_servo': math.radians(+ail_deg),  # +aileron_deg = right roll => stbd TE up (+q)
            'elevator_servo': math.radians(elev_deg),
            'rudder_servo': math.radians(rud_deg),
            'reverse_bucket_port_servo': math.radians(rev_deg),
            'reverse_bucket_stbd_servo': math.radians(rev_deg),
        }
        has_power = float(self.fuel[0]) > 1e-4
        if has_power:
            for aname, tgt_rad in servo_targets_rad.items():
                aid = self.aids.get(aname, -1)
                if aid >= 0:
                    d.ctrl[aid] = float(tgt_rad)
        else:
            # No electrical/propulsive energy: hold neutral bias / lose active hold torque
            for aname in servo_targets_rad:
                aid = self.aids.get(aname, -1)
                if aid >= 0:
                    jname = aname.replace('_servo', '_hinge')
                    d.ctrl[aid] = float(self.joint(jname)[0])

        # Twin ducted fan motors driven by physical motor torque vs aerodynamic blade drag
        fan_diam_m = 0.90
        ct_fan = 0.24
        omega_max = 2.0 * math.pi * math.sqrt(
            self.MAX_THRUST_PER_FAN_N / (ct_fan * RHO_AIR_ISA * (fan_diam_m ** 4))
        )
        k_q = 95.0 / (omega_max ** 2)
        inflow_lapse = max(0.55, min(1.05, 1.0 - 0.18 * (max(u_rel_mps, 0.0) / 45.0)))
        throt = float(self._targets['throttle'])
        diff = float(self._targets['differential_thrust'])
        scales = [
            throt * max(0.0, 1.0 - 0.5 * diff),
            throt * max(0.0, 1.0 + 0.5 * diff),
        ]

        tau_motors = [0.0, 0.0]
        tau_aeros = [0.0, 0.0]
        for idx, (jname, aname, sc) in enumerate((
            ('fan_rotor_port_hinge', 'fan_motor_port', scales[0]),
            ('fan_rotor_stbd_hinge', 'fan_motor_stbd', scales[1]),
        )):
            _, omega_i = self.joint(jname)
            tau_aero_i = k_q * omega_i * abs(omega_i) + 0.04 * omega_i
            tau_aeros[idx] = float(tau_aero_i)
            jid = self.jids.get(jname, -1)
            if jid >= 0:
                dadr = int(self.model.jnt_dofadr[jid])
                d.qfrc_applied[dadr] -= float(tau_aero_i)

            if not has_power:
                tau_cmd = 0.0
            elif throt > 0.01:
                omega_ref = omega_max * math.sqrt(max(sc * inflow_lapse, 0.0))
                if omega_ref < 94.25 and throt > 0.01:
                    omega_ref = 94.25 * max(0.0, min(1.0, sc / max(throt, 1e-6)))
                tau_ff = k_q * omega_ref * abs(omega_ref) + 0.04 * omega_ref
                # Fast, smooth electric direct-drive speed governor capped at physical torque/power limit
                max_tau_by_power = 68000.0 / max(abs(omega_i), 120.0)
                tau_lim = min(200.0, max_tau_by_power)
                tau_cmd = float(np.clip(tau_ff + 2.2 * (omega_ref - omega_i), -tau_lim, tau_lim))
            else:
                # Idle coast-down with light regenerative drag
                tau_cmd = float(np.clip(-0.45 * omega_i, -45.0, 45.0))

            aid = self.aids.get(aname, -1)
            if aid >= 0:
                d.ctrl[aid] = tau_cmd
            tau_motors[idx] = tau_cmd

        self._last_fan_motor_torque_nm = tau_motors
        self._last_fan_aero_torque_nm = tau_aeros
        return tau_motors, tau_aeros

    def _compute_aero_and_propulsion(self) -> tuple[np.ndarray, np.ndarray]:
        d = self.data
        bid = self.bids['airframe']
        _, xipos, rot, vel_w, omega_w, _, _ = _body_state(d, bid)
        v_air_w = vel_w - self.wind
        v_air_b = rot.T @ v_air_w
        omega_b = rot.T @ omega_w
        u, v, w = float(v_air_b[0]), float(v_air_b[1]), float(v_air_b[2])
        speed = math.sqrt(u * u + v * v + w * w)
        r_cg = self.model.body_ipos[bid]

        # Read achieved MuJoCo joint positions & rotor angular speeds (zero synthetic shortcuts)
        _, omega_fan_p = self.joint('fan_rotor_port_hinge')
        _, omega_fan_s = self.joint('fan_rotor_stbd_hinge')
        q_ail_p, qd_ail_p = self.joint('aileron_port_hinge')
        q_ail_s, qd_ail_s = self.joint('aileron_stbd_hinge')
        q_elev, qd_elev = self.joint('elevator_hinge')
        q_rud, qd_rud = self.joint('rudder_hinge')
        q_rev_p, _ = self.joint('reverse_bucket_port_hinge')
        q_rev_s, _ = self.joint('reverse_bucket_stbd_hinge')

        fan_diam_m = 0.90
        fan_y_arm = 0.78
        fan_z_pos = 1.56
        ct_fan = 0.24

        rps_p = omega_fan_p / (2.0 * math.pi)
        rps_s = omega_fan_s / (2.0 * math.pi)
        rev_frac_p = float(np.clip(q_rev_p / math.radians(85.0), 0.0, 1.0))
        rev_frac_s = float(np.clip(q_rev_s / math.radians(85.0), 0.0, 1.0))

        t_gross_p = ct_fan * RHO_AIR_ISA * rps_p * abs(rps_p) * (fan_diam_m ** 4)
        t_gross_s = ct_fan * RHO_AIR_ISA * rps_s * abs(rps_s) * (fan_diam_m ** 4)
        t_port = t_gross_p * (1.0 - 1.55 * rev_frac_p)
        t_stbd = t_gross_s * (1.0 - 1.55 * rev_frac_s)
        self.last_thrust_per_fan_n = [float(t_port), float(t_stbd)]

        rpm_port = abs(omega_fan_p) * 30.0 / math.pi
        rpm_stbd = abs(omega_fan_s) * 30.0 / math.pi
        self.last_fan_rpm = [float(rpm_port), float(rpm_stbd)]

        f_prop_b = np.array([
            t_port + t_stbd,
            0.0,
            0.06 * (abs(t_gross_p) * rev_frac_p + abs(t_gross_s) * rev_frac_s),
        ], dtype=np.float64)
        z_arm = fan_z_pos - float(r_cg[2])
        m_prop_b = np.array([
            0.0,  # Direct rotor motor/drag reaction torque flows physically through MuJoCo rotor hinge joints!
            z_arm * (t_port + t_stbd),
            (t_stbd - t_port) * fan_y_arm,
        ], dtype=np.float64)

        # Aerodynamic wing, winglets & T-tail evaluated at per-surface local airflow v_local = v_air_b + omega_b x r_s
        s_wing = 15.50
        b_wing = 9.60
        if self.hull_bundle.variant_id == 'concept_a':
            cd0_craft = canopy_and_craft_cd0(windshield_rake_deg=24.0, canopy_fineness_ratio=4.0)['cd0_total']
            hull_drag_area = 1.15 + 0.05 * s_wing
        else:
            cd0_craft = canopy_and_craft_cd0(windshield_rake_deg=82.0, canopy_fineness_ratio=2.2)['cd0_total']
            hull_drag_area = 1.8 + 0.08 * s_wing

        # Fan slipstream wash over aft tail/rudder/elevator
        slip_speed = max(0.0, math.sqrt(max(t_gross_p + t_gross_s, 0.0) / (2.0 * RHO_AIR_ISA * math.pi * (0.45 ** 2))))

        def _local_flow(ac_vtx: tuple[float, float, float], has_slipstream: bool = False) -> tuple[np.ndarray, np.ndarray, float, float, float]:
            arm = np.asarray(ac_vtx, dtype=np.float64) - r_cg
            v_loc = v_air_b + np.cross(omega_b, arm)
            if has_slipstream:
                v_loc = np.array([v_loc[0] + 0.55 * slip_speed, v_loc[1], v_loc[2]], dtype=np.float64)
            spd_l = float(np.linalg.norm(v_loc))
            q_loc = 0.5 * RHO_AIR_ISA * spd_l * spd_l
            alpha_l = math.atan2(-v_loc[2], max(abs(v_loc[0]), 0.8)) if spd_l > 0.3 else 0.0
            beta_l = math.atan2(v_loc[1], max(abs(v_loc[0]), 0.5)) if spd_l > 0.3 else 0.0
            return arm, v_loc, q_loc, alpha_l, beta_l

        # Base fuselage / hull / full-wing lift & drag
        q_dyn = 0.5 * RHO_AIR_ISA * speed * speed
        alpha = math.atan2(-w, max(abs(u), 0.8)) if speed > 0.3 else 0.0
        beta = math.atan2(v, max(abs(u), 0.5)) if speed > 0.3 else 0.0
        cl_wing = 0.25 + 4.2 * alpha
        cd_wing = cd0_craft + 0.048 * cl_wing * cl_wing
        f_lift_wing = q_dyn * s_wing * cl_wing * (1.0 if u >= -0.2 else 0.2)
        f_hull_wing_b = np.array([
            -0.5 * RHO_AIR_ISA * abs(u) * u * hull_drag_area - q_dyn * s_wing * cd_wing * np.sign(u),
            -0.5 * RHO_AIR_ISA * abs(v) * v * 3.8,
            f_lift_wing - 0.5 * RHO_AIR_ISA * abs(w) * w * 4.5,
        ], dtype=np.float64)

        # Multi-surface local forces & lever-arm moments driven strictly by achieved MuJoCo joint angles
        f_surf_total_b = np.zeros(3, dtype=np.float64)
        m_surf_total_b = np.zeros(3, dtype=np.float64)
        surfaces_telemetry: dict[str, dict[str, float]] = {}
        hinge_moments: dict[str, float] = {}

        # Aileron port (+Y, TE down for -q_ail_p => +Fz) & stbd (-Y, TE up for +q_ail_s => -Fz)
        for side, ac_pt, j_name, q_rad, qd_rad, sign_label in (
            ('port', AILERON_HINGE_PORT_VTX, 'aileron_port_hinge', q_ail_p, qd_ail_p, 1.0),
            ('stbd', AILERON_HINGE_STBD_VTX, 'aileron_stbd_hinge', q_ail_s, qd_ail_s, -1.0),
        ):
            arm, v_loc, q_loc, a_loc, _ = _local_flow(ac_pt, has_slipstream=False)
            s_ail = 0.72
            c_ail = 0.42
            fz = -2.2 * q_loc * s_ail * q_rad
            fx = -0.18 * q_loc * s_ail * (q_rad * q_rad) * (1.0 if v_loc[0] >= 0.0 else -1.0)
            f_vec = np.array([fx, 0.0, fz], dtype=np.float64)
            f_surf_total_b += f_vec
            m_surf_total_b += np.cross(arm, f_vec)
            hm = -0.055 * q_loc * s_ail * c_ail * (0.4 * a_loc + 0.75 * q_rad)
            hinge_moments[f'aileron_{side}'] = round(float(hm), 3)
            surfaces_telemetry[f'aileron_{side}'] = {
                'deflection_deg': round(math.degrees(q_rad), 3),
                'rate_deg_s': round(math.degrees(qd_rad), 2),
                'q_loc_pa': round(float(q_loc), 2),
                'alpha_loc_deg': round(math.degrees(a_loc), 2),
                'lift_z_n': round(float(fz), 2),
            }
            jid = self.jids.get(j_name, -1)
            if jid >= 0:
                d.qfrc_applied[int(self.model.jnt_dofadr[jid])] += float(np.clip(hm, -45.0, 45.0))

        # T-tail Elevator (x=-3.14 m; +q moves TE UP => -Fz tail down => -My nose up)
        arm_el, v_loc_el, q_el, a_el, _ = _local_flow(ELEVATOR_HINGE_VTX, has_slipstream=True)
        s_elev = 1.15
        c_elev = 0.36
        fz_el = -2.35 * q_el * s_elev * q_elev
        fx_el = -0.22 * q_el * s_elev * (q_elev * q_elev)
        f_el = np.array([fx_el, 0.0, fz_el], dtype=np.float64)
        f_surf_total_b += f_el
        m_surf_total_b += np.cross(arm_el, f_el)
        hm_el = -0.065 * q_el * s_elev * c_elev * (0.45 * a_el + 0.80 * q_elev)
        hinge_moments['elevator'] = round(float(hm_el), 3)
        surfaces_telemetry['elevator'] = {
            'deflection_deg': round(math.degrees(q_elev), 3),
            'rate_deg_s': round(math.degrees(qd_elev), 2),
            'q_loc_pa': round(float(q_el), 2),
            'alpha_loc_deg': round(math.degrees(a_el), 2),
            'lift_z_n': round(float(fz_el), 2),
        }
        jid_el = self.jids.get('elevator_hinge', -1)
        if jid_el >= 0:
            d.qfrc_applied[int(self.model.jnt_dofadr[jid_el])] += float(np.clip(hm_el, -55.0, 55.0))

        # Rudder on swept tail pylon (x=-2.59 m; +q moves TE PORT +Y => -Fy stbd force => +Mz left yaw)
        arm_rd, v_loc_rd, q_rd, _, b_rd = _local_flow(RUDDER_HINGE_VTX, has_slipstream=True)
        s_rud = 1.15
        c_rud = 0.44
        cn_beta = 0.095
        cn_r = -0.18
        cn_dr = 0.14
        r_hat = omega_b[2] * (0.5 * b_wing) / max(speed, 2.0)
        cn_yaw = cn_beta * math.sin(beta) + cn_r * r_hat + cn_dr * q_rud
        fy_rud = -2.45 * q_rd * s_rud * q_rud
        fy_fin = q_rd * s_rud * 1.45 * math.sin(b_rd) * (-0.5)
        f_rd = np.array([-0.20 * q_rd * s_rud * (q_rud * q_rud), fy_rud + fy_fin, 0.0], dtype=np.float64)
        f_surf_total_b += f_rd
        m_surf_total_b += np.cross(arm_rd, f_rd)
        hm_rd = -0.065 * q_rd * s_rud * c_rud * (-0.45 * b_rd + 0.80 * q_rud)
        hinge_moments['rudder'] = round(float(hm_rd), 3)
        surfaces_telemetry['rudder'] = {
            'deflection_deg': round(math.degrees(q_rud), 3),
            'rate_deg_s': round(math.degrees(qd_rud), 2),
            'q_loc_pa': round(float(q_rd), 2),
            'beta_loc_deg': round(math.degrees(b_rd), 2),
            'side_y_n': round(float(fy_rud + fy_fin), 2),
        }
        jid_rd = self.jids.get('rudder_hinge', -1)
        if jid_rd >= 0:
            d.qfrc_applied[int(self.model.jnt_dofadr[jid_rd])] += float(np.clip(hm_rd, -55.0, 55.0))

        # Directional weathercock yaw stiffness + rotational aero damping
        yaw_weathercock = q_rd * s_wing * b_wing * (cn_beta * math.sin(beta)) * 0.18
        aero_damp_m = -np.array([120.0 * omega_b[0], 180.0 * omega_b[1], 160.0 * omega_b[2]], dtype=np.float64)

        # Pure aerodynamic slender-body Munk moment (rho_air = 1.225 kg/m^3); water Kirchhoff-Munk torque is computed inside hydrodynamics.py
        ma_air_diag = np.array([0.8, 3.8, 4.5], dtype=np.float64)
        aero_munk_b = -np.cross(v_air_b, ma_air_diag * v_air_b)
        self._last_aero_munk_nm = aero_munk_b
        hydro_munk_b = self.last_hydro.munk_torque_body if self.last_hydro is not None else np.zeros(3, dtype=np.float64)
        self.last_munk_moment_nm = aero_munk_b + hydro_munk_b
        self.last_cn_yaw = float(cn_yaw)
        self.last_cn_beta = float(cn_beta)

        f_aero_b = f_hull_wing_b + f_surf_total_b
        m_aero_b = m_surf_total_b + np.array([0.0, 0.0, yaw_weathercock], dtype=np.float64) + aero_damp_m + aero_munk_b

        f_prop_w = rot @ f_prop_b
        m_prop_w = rot @ m_prop_b
        f_aero_w = rot @ f_aero_b
        m_aero_w = rot @ m_aero_b

        self.last_propulsion_n = f_prop_w
        self.last_propulsion_torque_nm = m_prop_w
        self.last_aero_force_n = f_aero_w
        self.last_aero_torque_nm = m_aero_w
        self.last_aero_detail = {
            'force_body_n': [round(float(x), 3) for x in f_aero_b],
            'moment_body_nm': [round(float(x), 3) for x in m_aero_b],
            'surfaces': surfaces_telemetry,
            'hinge_moments': hinge_moments,
            'dynamic_pressure_pa': round(float(q_dyn), 2),
            'alpha_deg': round(math.degrees(alpha), 2),
            'beta_deg': round(math.degrees(beta), 2),
        }

        tau_m0, tau_m1 = self._last_fan_motor_torque_nm
        tau_a0, tau_a1 = self._last_fan_aero_torque_nm
        p_prop_w = abs(omega_fan_p * tau_m0) + abs(omega_fan_s * tau_m1)
        # Estimate servo power draw from actuator forces
        p_servo_w = 0.0
        for spec in ARTICULATED_CHILD_SPECS:
            if spec['actuator_type'] != 'servo':
                continue
            aid = self.aids.get(spec['actuator_name'], -1)
            jid = self.jids.get(spec['joint'], -1)
            if aid >= 0 and jid >= 0:
                af = float(d.actuator_force[aid])
                qd_j = float(d.qvel[int(self.model.jnt_dofadr[jid])])
                p_servo_w += abs(af * qd_j) + 0.06 * abs(af)
                fmax = abs(float(spec['forcerange'][1]))
                self._last_servo_saturated[spec['body']] = abs(af) >= 0.98 * fmax

        self.power = {
            'engine_w': round(float(p_prop_w), 2),
            'propulsion_w': round(float(p_prop_w), 2),
            'servo_w': round(float(p_servo_w), 2),
            'total_w': round(float(p_prop_w + p_servo_w), 2),
        }
        self.rotors[0].update({
            'side': 'port',
            'torque_nm': round(float(tau_m0), 3),
            'aero_torque_nm': round(float(tau_a0), 3),
            'omega_rad_s': round(float(omega_fan_p), 3),
            'rpm': round(float(rpm_port), 1),
            'thrust_n': round(float(t_port), 2),
            'shaft_power_w': round(float(omega_fan_p * tau_m0), 2),
            'reverser_frac': round(float(rev_frac_p), 4),
            'spool_fraction': round(float(np.clip(abs(omega_fan_p) / 545.0, 0.0, 1.0)), 4),
        })
        self.rotors[1].update({
            'side': 'stbd',
            'torque_nm': round(float(tau_m1), 3),
            'aero_torque_nm': round(float(tau_a1), 3),
            'omega_rad_s': round(float(omega_fan_s), 3),
            'rpm': round(float(rpm_stbd), 1),
            'thrust_n': round(float(t_stbd), 2),
            'shaft_power_w': round(float(omega_fan_s * tau_m1), 2),
            'reverser_frac': round(float(rev_frac_s), 4),
            'spool_fraction': round(float(np.clip(abs(omega_fan_s) / 545.0, 0.0, 1.0)), 4),
        })

        return f_prop_w + f_aero_w, m_prop_w + m_aero_w

    def _evaluate_and_cache_hydro(
        self,
        t: float,
        force_eval: bool = False,
        ext_force_m: np.ndarray | None = None,
        ext_torque_m: np.ndarray | None = None,
    ) -> None:
        d = self.data
        if force_eval or (self.step_count % self.hydro_stride == 0):
            bid_m = self.bids['airframe']
            bid_p = self.bids['sponson_port']
            bid_s = self.bids['sponson_stbd']

            pos_m, xipos_m, rot_m, vel_m, om_m, acc_m, al_m = _body_state(d, bid_m)
            pos_p, xipos_p, rot_p, vel_p, om_p, acc_p, al_p = _body_state(d, bid_p)
            pos_s, xipos_s, rot_s, vel_s, om_s, acc_s, al_s = _body_state(d, bid_s)

            # Evaluate non-inertial hydro forces first, then couple rigid-assembly virtual mass (M_tot + Ma_tot)^{-1}
            g_w = self.water_config.g_m_s2
            bd_m = evaluate_mesh_hydrodynamics(
                self.hull_bundle.main_hull,
                pos_m,
                rot_m,
                vel_m,
                om_m,
                acc_m,
                al_m,
                xipos_m,
                self.water_field,
                t,
                calibration=self.calibration,
                rho_water=self.water_config.rho_water_kg_m3,
                nu_water=self.water_config.nu_water_m2_s,
                g=g_w,
                include_inertial_am=False,
            )
            bd_p = evaluate_mesh_hydrodynamics(
                self.hull_bundle.port_sponson,
                pos_p,
                rot_p,
                vel_p,
                om_p,
                acc_p,
                al_p,
                xipos_p,
                self.water_field,
                t,
                calibration=self.calibration,
                rho_water=self.water_config.rho_water_kg_m3,
                nu_water=self.water_config.nu_water_m2_s,
                g=g_w,
                include_inertial_am=False,
            )
            bd_s = evaluate_mesh_hydrodynamics(
                self.hull_bundle.stbd_sponson,
                pos_s,
                rot_s,
                vel_s,
                om_s,
                acc_s,
                al_s,
                xipos_s,
                self.water_field,
                t,
                calibration=self.calibration,
                rho_water=self.water_config.rho_water_kg_m3,
                nu_water=self.water_config.nu_water_m2_s,
                g=g_w,
                include_inertial_am=False,
            )

            m_p = float(self.model.body_mass[bid_p])
            m_s = float(self.model.body_mass[bid_s])
            core_bids = [
                int(b) for b in range(1, self.model.nbody)
                if b not in (bid_p, bid_s)
            ]
            m_m = sum(float(self.model.body_mass[b]) for b in core_bids)
            xipos_core = (
                sum(float(self.model.body_mass[b]) * self.data.xipos[b] for b in core_bids)
                / max(m_m, 1e-6)
            )
            m_tot = m_m + m_p + m_s
            x_com_w = (m_m * xipos_core + m_p * xipos_p + m_s * xipos_s) / max(m_tot, 1e-6)
            ext_f_m = np.zeros(3, dtype=np.float64) if ext_force_m is None else np.asarray(ext_force_m, dtype=np.float64)
            ext_t_m = np.zeros(3, dtype=np.float64) if ext_torque_m is None else np.asarray(ext_torque_m, dtype=np.float64)
            f_free_tot = (
                bd_m.total_force_world + bd_p.total_force_world + bd_s.total_force_world
                + ext_f_m + np.array([0.0, 0.0, -m_tot * g_w], dtype=np.float64)
            )
            t_free_tot = (
                bd_m.total_torque_world + np.cross(xipos_m - x_com_w, bd_m.total_force_world)
                + np.cross(xipos_core - x_com_w, np.array([0.0, 0.0, -m_m * g_w]))
                + bd_p.total_torque_world + np.cross(xipos_p - x_com_w, bd_p.total_force_world + np.array([0.0, 0.0, -m_p * g_w]))
                + bd_s.total_torque_world + np.cross(xipos_s - x_com_w, bd_s.total_force_world + np.array([0.0, 0.0, -m_s * g_w]))
                + ext_t_m + np.cross(xipos_m - x_com_w, ext_f_m)
            )
            zero3 = np.zeros(3, dtype=np.float64)
            ma_m, ia_m, aw_m, _, warea_m = getattr(bd_m, '_am_data', (zero3, zero3, zero3, 0.0, 0.0))
            ma_p, ia_p, aw_p, _, warea_p = getattr(bd_p, '_am_data', (zero3, zero3, zero3, 0.0, 0.0))
            ma_s, ia_s, aw_s, _, warea_s = getattr(bd_s, '_am_data', (zero3, zero3, zero3, 0.0, 0.0))
            w_tot = warea_m + warea_p + warea_s
            aw_tot = (warea_m * aw_m + warea_p * aw_p + warea_s * aw_s) / w_tot if w_tot > 1e-9 else zero3

            r_m_b = rot_m.T @ (xipos_core - x_com_w)
            r_p_b = rot_m.T @ (xipos_p - x_com_w)
            r_s_b = rot_m.T @ (xipos_s - x_com_w)

            def _par_scalar(mv: float, rv: np.ndarray) -> np.ndarray:
                return np.array([mv * (rv[1]**2 + rv[2]**2), mv * (rv[0]**2 + rv[2]**2), mv * (rv[0]**2 + rv[1]**2)], dtype=np.float64)

            def _par_vec(mv: np.ndarray, rv: np.ndarray) -> np.ndarray:
                return np.array([mv[2] * rv[1]**2 + mv[1] * rv[2]**2, mv[2] * rv[0]**2 + mv[0] * rv[2]**2, mv[1] * rv[0]**2 + mv[0] * rv[1]**2], dtype=np.float64)

            i_core_b = np.zeros(3, dtype=np.float64)
            for cb in core_bids:
                mc = float(self.model.body_mass[cb])
                rc_b = rot_m.T @ (self.data.xipos[cb] - x_com_w)
                i_core_b += np.asarray(self.model.body_inertia[cb], dtype=np.float64) + _par_scalar(mc, rc_b)

            i_tot_b = (
                i_core_b
                + np.asarray(self.model.body_inertia[bid_p], dtype=np.float64)
                + np.asarray(self.model.body_inertia[bid_s], dtype=np.float64)
                + _par_scalar(m_p, r_p_b) + _par_scalar(m_s, r_s_b)
            )
            ma_tot = ma_m + ma_p + ma_s
            ia_tot = ia_m + ia_p + ia_s + _par_vec(ma_m, r_m_b) + _par_vec(ma_p, r_p_b) + _par_vec(ma_s, r_s_b)

            a_veh_b = (rot_m.T @ f_free_tot - m_tot * (rot_m.T @ aw_tot)) / np.maximum(m_tot + ma_tot, 1e-6)
            alpha_veh_b = (rot_m.T @ t_free_tot) / np.maximum(i_tot_b + ia_tot, 1e-6)

            for bd_i, ma_i, ia_i, aw_i, r_i_b in (
                (bd_m, ma_m, ia_m, aw_m, r_m_b),
                (bd_p, ma_p, ia_p, aw_p, r_p_b),
                (bd_s, ma_s, ia_s, aw_s, r_s_b),
            ):
                if float(np.sum(ma_i) + np.sum(ia_i)) <= 0.0:
                    continue
                a_i_rel_b = a_veh_b + np.cross(alpha_veh_b, r_i_b) + rot_m.T @ (aw_tot - aw_i)
                f_am_in = rot_m @ (-ma_i * a_i_rel_b)
                t_am_in = rot_m @ (-ia_i * alpha_veh_b)
                bd_i.added_mass_force_world = bd_i.added_mass_force_world + f_am_in
                bd_i.added_mass_torque_world = bd_i.added_mass_torque_world + t_am_in
                bd_i.total_force_world = bd_i.total_force_world + f_am_in
                bd_i.total_torque_world = bd_i.total_torque_world + t_am_in

            self._prev_hydro_f = dict(self._curr_hydro_f) if self._curr_hydro_f else {
                bid_m: np.concatenate([bd_m.total_force_world, bd_m.total_torque_world]),
                bid_p: np.concatenate([bd_p.total_force_world, bd_p.total_torque_world]),
                bid_s: np.concatenate([bd_s.total_force_world, bd_s.total_torque_world]),
            }
            self._curr_hydro_f = {
                bid_m: np.concatenate([bd_m.total_force_world, bd_m.total_torque_world]),
                bid_p: np.concatenate([bd_p.total_force_world, bd_p.total_torque_world]),
                bid_s: np.concatenate([bd_s.total_force_world, bd_s.total_torque_world]),
            }

            # Also assemble whole-vehicle combined breakdown referred to main-hull CoM for telemetry
            tot_vol = bd_m.submerged_volume_m3 + bd_p.submerged_volume_m3 + bd_s.submerged_volume_m3
            tot_area = bd_m.wetted_area_m2 + bd_p.wetted_area_m2 + bd_s.wetted_area_m2
            if tot_vol > 1e-9:
                cob_w = (
                    bd_m.submerged_volume_m3 * bd_m.centre_of_buoyancy_world
                    + bd_p.submerged_volume_m3 * bd_p.centre_of_buoyancy_world
                    + bd_s.submerged_volume_m3 * bd_s.centre_of_buoyancy_world
                ) / tot_vol
            else:
                cob_w = bd_m.centre_of_buoyancy_world.copy()
            cob_b = rot_m.T @ (cob_w - pos_m)

            # Transfer sponson moments about main CoM xipos_m for vehicle-level sum
            arm_p = xipos_p - xipos_m
            arm_s = xipos_s - xipos_m

            def comb(f_attr: str, t_attr: str) -> tuple[np.ndarray, np.ndarray]:
                fp = getattr(bd_p, f_attr)
                fs = getattr(bd_s, f_attr)
                fm = getattr(bd_m, f_attr)
                tm = getattr(bd_m, t_attr)
                tp = getattr(bd_p, t_attr) + np.cross(arm_p, fp)
                ts = getattr(bd_s, t_attr) + np.cross(arm_s, fs)
                return fm + fp + fs, tm + tp + ts

            b_f, b_t = comb('buoyancy_force_world', 'buoyancy_torque_world')
            r_f, r_t = comb('resistance_force_world', 'resistance_torque_world')
            l_f, l_t = comb('dynamic_lift_force_world', 'dynamic_lift_torque_world')
            a_f, a_t = comb('added_mass_force_world', 'added_mass_torque_world')
            d_f, d_t = comb('damping_force_world', 'damping_torque_world')
            w_f, w_t = comb('wave_force_world', 'wave_torque_world')

            tot_gross = (
                self.hull_bundle.main_hull.mesh.gross_volume_m3
                + self.hull_bundle.port_sponson.mesh.gross_volume_m3
                + self.hull_bundle.stbd_sponson.mesh.gross_volume_m3
            )
            self.last_hydro = HydroBreakdown(
                submerged_volume_m3=tot_vol,
                wetted_area_m2=tot_area,
                centre_of_buoyancy_world=cob_w,
                centre_of_buoyancy_body=cob_b,
                waterline_z_world_mean=bd_m.waterline_z_world_mean,
                draft_m=max(bd_m.draft_m, bd_p.draft_m, bd_s.draft_m),
                freeboard_min_m=bd_m.freeboard_min_m,
                submergence_ratio=float(np.clip(tot_vol / max(tot_gross, 1e-6), 0.0, 1.0)),
                ground_clearance_m=bd_m.ground_clearance_m,
                mean_water_depth_m=bd_m.mean_water_depth_m,
                buoyancy_force_world=b_f,
                buoyancy_torque_world=b_t,
                resistance_force_world=r_f,
                resistance_torque_world=r_t,
                dynamic_lift_force_world=l_f,
                dynamic_lift_torque_world=l_t,
                added_mass_force_world=a_f,
                added_mass_torque_world=a_t,
                damping_force_world=d_f,
                damping_torque_world=d_t,
                wave_force_world=w_f,
                wave_torque_world=w_t,
                total_force_world=b_f + r_f + l_f + a_f + d_f + w_f,
                total_torque_world=b_t + r_t + l_t + a_t + d_t + w_t,
                munk_torque_body=rot_m.T @ (
                    rot_m @ bd_m.munk_torque_body
                    + rot_p @ bd_p.munk_torque_body
                    + rot_s @ bd_s.munk_torque_body
                ),
                component_loads={
                    'main_hull': {'submerged_volume_m3': round(bd_m.submerged_volume_m3, 5), 'buoyancy_z_n': round(float(bd_m.buoyancy_force_world[2]), 2)},
                    'sponson_port': {'submerged_volume_m3': round(bd_p.submerged_volume_m3, 5), 'buoyancy_z_n': round(float(bd_p.buoyancy_force_world[2]), 2)},
                    'sponson_stbd': {'submerged_volume_m3': round(bd_s.submerged_volume_m3, 5), 'buoyancy_z_n': round(float(bd_s.buoyancy_force_world[2]), 2)},
                },
            )

    def control_surface_telemetry(self) -> dict[str, Any]:
        """Commanded vs achieved MuJoCo joint positions/rates and limits for all primary/reverse surfaces."""
        q_ail_p, qd_ail_p = self.joint('aileron_port_hinge')
        q_ail_s, qd_ail_s = self.joint('aileron_stbd_hinge')
        q_elev, qd_elev = self.joint('elevator_hinge')
        q_rud, qd_rud = self.joint('rudder_hinge')
        q_rev_p, qd_rev_p = self.joint('reverse_bucket_port_hinge')
        q_rev_s, qd_rev_s = self.joint('reverse_bucket_stbd_hinge')
        ail_eff_deg = 0.5 * (math.degrees(q_ail_s) - math.degrees(q_ail_p))
        ail_rate_deg_s = 0.5 * (math.degrees(qd_ail_s) - math.degrees(qd_ail_p))
        rev_p_deg = math.degrees(q_rev_p)
        rev_s_deg = math.degrees(q_rev_s)
        rev_frac = float(np.clip(0.5 * (rev_p_deg + rev_s_deg) / 85.0, 0.0, 1.0))

        return {
            'rudder': {
                'commanded_deg': round(float(self.command['rudder_deg']), 3),
                'target_deg': round(float(self._targets['rudder_deg']), 3),
                'achieved_deg': round(math.degrees(q_rud), 3),
                'rate_deg_s': round(math.degrees(qd_rud), 2),
                'min_deg': -30.0,
                'max_deg': 30.0,
                'saturated': bool(self._last_servo_saturated.get('rudder', False)),
            },
            'elevator': {
                'commanded_deg': round(float(self.command['elevator_deg']), 3),
                'target_deg': round(float(self._targets['elevator_deg']), 3),
                'achieved_deg': round(math.degrees(q_elev), 3),
                'rate_deg_s': round(math.degrees(qd_elev), 2),
                'min_deg': -20.0,
                'max_deg': 20.0,
                'saturated': bool(self._last_servo_saturated.get('elevator', False)),
            },
            'aileron': {
                'commanded_deg': round(float(self.command['aileron_deg']), 3),
                'target_deg': round(float(self._targets['aileron_deg']), 3),
                'achieved_deg': round(ail_eff_deg, 3),
                'port_achieved_deg': round(math.degrees(q_ail_p), 3),
                'stbd_achieved_deg': round(math.degrees(q_ail_s), 3),
                'rate_deg_s': round(ail_rate_deg_s, 2),
                'min_deg': -25.0,
                'max_deg': 25.0,
                'saturated': bool(
                    self._last_servo_saturated.get('aileron_port', False)
                    or self._last_servo_saturated.get('aileron_stbd', False)
                ),
            },
            'reverse_bucket': {
                'commanded_frac': round(float(self.command['reverse_bucket']), 4),
                'target_frac': round(float(self._targets['reverse_bucket']), 4),
                'achieved_frac': round(rev_frac, 4),
                'port_achieved_deg': round(rev_p_deg, 3),
                'stbd_achieved_deg': round(rev_s_deg, 3),
                'rate_deg_s': round(0.5 * (math.degrees(qd_rev_p) + math.degrees(qd_rev_s)), 2),
                'min_deg': 0.0,
                'max_deg': 85.0,
                'saturated': bool(
                    self._last_servo_saturated.get('reverse_bucket_port', False)
                    or self._last_servo_saturated.get('reverse_bucket_stbd', False)
                ),
            },
        }

    def step(self) -> None:
        """Advance coupled SWE/wave field and 400 Hz MuJoCo rigid-body step."""
        d = self.data
        t = float(d.time)
        bid_af = self.bids['airframe']

        # Slew control targets smoothly toward held commands and clear external/joint forces
        self._slew_targets(DT)
        d.qfrc_applied[:] = 0.0
        d.xfrc_applied[:] = 0.0

        _, _, rot_af, vel_af_w, _, _, _ = _body_state(d, bid_af)
        u_rel = float((rot_af.T @ (vel_af_w - self.wind))[0])
        self._apply_actuator_controls(u_rel)

        # Compute aerodynamic (per-surface local airflow) + ducted-fan propulsion forces
        # from achieved MuJoCo joint positions & rotor angular speeds before virtual-mass hydro solve
        f_ap, m_ap = self._compute_aero_and_propulsion()

        # Advance water solver step cleanly
        self.water_field.step(DT)
        self._evaluate_and_cache_hydro(
            t=t,
            force_eval=(self.step_count == 0),
            ext_force_m=f_ap,
            ext_torque_m=m_ap,
        )
        if self.last_hydro is not None:
            self.last_munk_moment_nm = self._last_aero_munk_nm + self.last_hydro.munk_torque_body

        # Interpolate within hydro_stride if > 1 (alpha = 1 when hydro_stride == 1)
        sub_phase = (self.step_count % self.hydro_stride + 1) / float(self.hydro_stride)
        for bid, w_curr in self._curr_hydro_f.items():
            w_prev = self._prev_hydro_f.get(bid, w_curr)
            w_interp = (1.0 - sub_phase) * w_prev + sub_phase * w_curr
            # Safety guard against numerical blowup in extreme crashes
            w_interp[:3] = np.clip(w_interp[:3], -8.0e4, 8.0e4)
            w_interp[3:] = np.clip(w_interp[3:], -8.0e4, 8.0e4)
            d.xfrc_applied[bid] = w_interp

        d.xfrc_applied[bid_af, :3] += f_ap
        d.xfrc_applied[bid_af, 3:] += m_ap

        mj.mj_step(self.model, d)
        self.step_count += 1

        # Fuel & energy depletion strictly tied to propulsion + servo shaft work
        p_tot_w = float(self.power.get('total_w', 0.0))
        fuel_burn_kg_s = p_tot_w * 1.15e-7
        self.fuel[0] = max(0.0, float(self.fuel[0]) - fuel_burn_kg_s * DT)
        consumed_kwh = float(self.energy.get('consumed_kwh', 0.0)) + p_tot_w * DT / 3_600_000.0
        self.energy['consumed_kwh'] = round(consumed_kwh, 6)
        self.energy['remaining_kwh'] = round(max(0.0, 20.0 - consumed_kwh), 6)
        self.energy['fuel_burn_kg_s'] = round(fuel_burn_kg_s, 6)

        if self.fuel[0] <= 1e-4:
            self.flags.add('FUEL_EXHAUSTED')
        else:
            self.flags.discard('FUEL_EXHAUSTED')
        if not self.mass_register.waterproof:
            self.flags.add('HULL_BREACHED')
        else:
            self.flags.discard('HULL_BREACHED')
        if any(self._last_servo_saturated.values()):
            self.flags.add('SERVO_SATURATED')
        else:
            self.flags.discard('SERVO_SATURATED')

        # Track contacts & ground clearance
        alt = float(d.xpos[bid_af, 2])
        self.max_alt = max(self.max_alt, alt)
        for ci in range(d.ncon):
            cf = np.zeros(6, dtype=np.float64)
            mj.mj_contactForce(self.model, d, ci, cf)
            n_force = float(np.linalg.norm(cf[:3]))
            self.max_impact_n = max(self.max_impact_n, n_force)
            self.max_gear_load_n = self.max_impact_n

        # Couple simulated vessel motion -> SWE momentum & Kelvin wake + whirlpool/bilge status
        bid_m = bid_af
        pos_m = d.xpos[bid_m]
        rot_m = d.xmat[bid_m].reshape(3, 3)
        vel_m = np.zeros(6, dtype=np.float64)
        mj.mj_objectVelocity(self.model, d, mj.mjtObj.mjOBJ_BODY, bid_m, vel_m, 0)
        heading_rad = math.atan2(float(rot_m[1, 0]), float(rot_m[0, 0]))
        if self.last_hydro is not None:
            hydro_react_xy = (
                float(self.last_hydro.resistance_force_world[0] + self.last_hydro.dynamic_lift_force_world[0] + self.last_hydro.damping_force_world[0]),
                float(self.last_hydro.resistance_force_world[1] + self.last_hydro.dynamic_lift_force_world[1] + self.last_hydro.damping_force_world[1]),
            )
            draft_now = float(self.last_hydro.draft_m)
            sub_vol_now = float(self.last_hydro.submerged_volume_m3)
        else:
            hydro_react_xy = (0.0, 0.0)
            draft_now = 0.0
            sub_vol_now = 0.0
        self.water_field.apply_vessel_disturbance(
            x=float(pos_m[0]),
            y=float(pos_m[1]),
            heading_rad=heading_rad,
            vx_world=float(vel_m[3]),
            vy_world=float(vel_m[4]),
            heave_rate_mps=float(vel_m[5]),
            draft_m=draft_now,
            submerged_vol_m3=sub_vol_now,
            hydro_reaction_xy=hydro_react_xy,
            fan_thrust_n=float(self.last_thrust_per_fan_n[0] + self.last_thrust_per_fan_n[1]),
            dt=DT,
            t_s=float(d.time),
        )
        self._last_whirlpool_hazard = (
            self.world.whirlpool_hazard_at(float(pos_m[0]), float(pos_m[1]), config=self.water_config)
            if hasattr(self.world, 'whirlpool_hazard_at')
            else {}
        )
        self._update_bilge_flooding(DT, rot_m)

    def _update_bilge_flooding(self, dt: float, rot_m: np.ndarray) -> None:
        """Progressive Torricelli water ingress when hull waterproof seal is disabled."""
        if self.mass_register.waterproof or self.last_hydro is None:
            return
        if self.last_hydro.submerged_volume_m3 <= 1e-4 or self.last_hydro.mean_water_depth_m <= 0.05:
            return
        rho_w = float(self.water_config.rho_water_kg_m3)
        enclosed_vol = float(
            self.hull_bundle.main_hull.mesh.gross_volume_m3
            + self.hull_bundle.port_sponson.mesh.gross_volume_m3
            + self.hull_bundle.stbd_sponson.mesh.gross_volume_m3
        )
        flood_cap_kg = 0.92 * enclosed_vol * rho_w
        if self.mass_register.flood_water_kg >= flood_cap_kg - 1e-4:
            return
        roll_deg = float(Rotation.from_matrix(rot_m).as_euler('xyz', degrees=True)[0])
        in_core = bool(self._last_whirlpool_hazard.get('in_core', False))
        h_seam = max(0.08, float(self.last_hydro.draft_m))
        overtop = (
            max(0.0, 0.14 - float(self.last_hydro.freeboard_min_m))
            + 0.55 * max(0.0, abs(roll_deg) - 10.0) / 30.0
            + (0.45 if in_core else 0.0)
        )
        dm_dt = rho_w * 0.095 * math.sqrt(2.0 * G_SI * max(h_seam + overtop, 0.02))
        new_flood = min(flood_cap_kg, float(self.mass_register.flood_water_kg) + dm_dt * dt)
        self.mass_register.flood_water_kg = new_flood
        if abs(new_flood - self._last_applied_flood_kg) >= 8.0 or (
            new_flood >= flood_cap_kg - 1e-3 and abs(new_flood - self._last_applied_flood_kg) > 1e-3
        ):
            self._apply_mass_to_mujoco()

    def attachment_loads(self) -> dict[str, Any]:
        """Read physical joint forces & torques on port/stbd sponson hangers from MuJoCo sensors."""
        out = {}
        for side in ('port', 'stbd'):
            f_slice = self._sensor_slices.get(f'sponson_{side}_force')
            t_slice = self._sensor_slices.get(f'sponson_{side}_torque')
            f_vec = self.data.sensordata[f_slice[0]:f_slice[0] + f_slice[1]] if f_slice else np.zeros(3)
            t_vec = self.data.sensordata[t_slice[0]:t_slice[0] + t_slice[1]] if t_slice else np.zeros(3)
            out[f'sponson_{side}'] = {
                'force_n': [round(float(x), 3) for x in f_vec],
                'torque_nm': [round(float(x), 3) for x in t_vec],
            }
        return out

    def ground_clearance(self) -> float | None:
        if self.last_hydro is not None:
            return float(self.last_hydro.ground_clearance_m)
        bid = self.bids['airframe']
        pos = self.data.xpos[bid]
        return float(pos[2] - self.world.terrain_z(float(pos[0]), float(pos[1])))

    def joint(self, name: str) -> tuple[float, float]:
        jid = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_JOINT, name)
        if jid < 0:
            return 0.0, 0.0
        qadr = int(self.model.jnt_qposadr[jid])
        dadr = int(self.model.jnt_dofadr[jid])
        return float(self.data.qpos[qadr]), float(self.data.qvel[dadr])

    def mass_properties(self) -> dict[str, Any]:
        agg = self.mass_register.aggregate(include_sponsons=True)
        enclosed_vol = float(
            self.hull_bundle.main_hull.mesh.gross_volume_m3
            + self.hull_bundle.port_sponson.mesh.gross_volume_m3
            + self.hull_bundle.stbd_sponson.mesh.gross_volume_m3
        )
        max_buoy_kg = enclosed_vol * float(self.water_config.rho_water_kg_m3)
        agg['mujoco_total_mass_kg'] = round(float(np.sum(self.model.body_mass)), 4)
        agg['enclosed_volume_m3'] = round(enclosed_vol, 5)
        agg['max_buoyancy_kg'] = round(max_buoy_kg, 2)
        agg['reserve_buoyancy_kg'] = round(max_buoy_kg - float(agg['total_mass_kg']), 2)
        return agg

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            'revision': 'RC01-LAKE-1',
            'physics_revision': f"ricochet-{self.hull_bundle.variant_id}-{self.SOLVER_VERSION}",
            'render_asset': f"pinned://ricochet/{self.hull_bundle.variant_id}/{self.hull_bundle.main_hull.mesh.geometry_sha256[:12]}",
            'airframe_variant': self.variant,
            'hull_variant': self.hull_bundle.variant_id,
            'hull_provenance': self.hull_bundle.provenance,
            'hull_geometry_sha256': self.hull_bundle.main_hull.mesh.geometry_sha256,
            'pinned_mujoco_meshes': self.verify_pinned_geometry(),
            'solver_version': self.SOLVER_VERSION,
            'model_xml_sha256': hashlib.sha256(self.xml.encode('utf-8')).hexdigest(),
            'calibration': self.calibration.to_dict(),
        }

    def verify_pinned_geometry(self) -> dict[str, Any]:
        """Verify MuJoCo collision meshes match the hydrodynamic hull/sponson/surface meshes in body frame."""
        checks = {}
        mapping: dict[str, tuple[str, Any, np.ndarray, str]] = {
            'main_hull_mesh': ('main_hull_geom', self.hull_bundle.main_hull.mesh, np.zeros(3), 'airframe'),
            'sponson_port_mesh': ('sponson_port_geom', self.hull_bundle.port_sponson.mesh, np.zeros(3), 'sponson_port'),
            'sponson_stbd_mesh': ('sponson_stbd_geom', self.hull_bundle.stbd_sponson.mesh, np.zeros(3), 'sponson_stbd'),
        }
        for part_key, spec in getattr(self.hull_bundle, 'airframe_meshes', {}).items():
            if spec.get('pin_to_mujoco'):
                mapping[f'{part_key}_mesh'] = (
                    f'{part_key}_geom',
                    spec['mesh'],
                    np.asarray(spec.get('offset', [0.0, 0.0, 0.0]), dtype=np.float64),
                    str(spec.get('body', 'airframe')),
                )
        for mesh_name, (geom_name, wmesh, expected_off, body_name) in mapping.items():
            mid = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_MESH, mesh_name)
            gid = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_GEOM, geom_name)
            if mid < 0 or gid < 0:
                raise RuntimeError(f'MuJoCo model is missing pinned mesh/geom asset {mesh_name!r}/{geom_name!r}')
            vadr = int(self.model.mesh_vertadr[mid])
            vnum = int(self.model.mesh_vertnum[mid])
            fnum = int(self.model.mesh_facenum[mid])
            mj_verts = self.model.mesh_vert[vadr:vadr + vnum]
            gq = self.model.geom_quat[gid]  # w, x, y, z
            gp = self.model.geom_pos[gid]
            bpos = np.asarray(CHILD_BODY_POS_BY_NAME.get(body_name, (0.0, 0.0, 0.0)), dtype=np.float64)
            mj_body = Rotation.from_quat([gq[1], gq[2], gq[3], gq[0]]).apply(mj_verts) + bpos + gp - expected_off
            vmin_err = float(np.max(np.abs(mj_body.min(axis=0) - wmesh.vertices.min(axis=0))))
            vmax_err = float(np.max(np.abs(mj_body.max(axis=0) - wmesh.vertices.max(axis=0))))
            checks[mesh_name] = {
                'pinned': (vnum == wmesh.vertices.shape[0] and fnum == wmesh.faces.shape[0] and vmin_err < 1e-4 and vmax_err < 1e-4),
                'body': body_name,
                'vertices': vnum,
                'faces': fnum,
                'geometry_sha256': wmesh.geometry_sha256,
                'bbox_max_err_m': round(max(vmin_err, vmax_err), 6),
            }
        return checks

    def visual_geometry(self) -> dict[str, Any]:
        """Export the exact physics-pinned mesh triangles + structural appendages for Three.js rendering."""
        def _mesh_dict(
            body_name: str,
            wmesh,
            color: str,
            *,
            part_name: str | None = None,
            material_role: str = 'hull_default',
            offset: list[float] | None = None,
            pinned: bool = True,
        ) -> dict[str, Any]:
            vis_v = getattr(wmesh, '_visual_vertices', None)
            vis_f = getattr(wmesh, '_visual_faces', None)
            vis_n = getattr(wmesh, '_visual_normals', None)
            vis_c = getattr(wmesh, '_visual_colors_rgb', None)
            use_v = vis_v if vis_v is not None else wmesh.vertices
            use_f = vis_f if vis_f is not None else wmesh.faces
            vc = vis_c if vis_c is not None else getattr(wmesh, '_vertex_colors_rgb', None)
            out = {
                'body': body_name,
                'name': part_name or wmesh.name,
                'sha256': wmesh.geometry_sha256,
                'vertices': np.round(use_v, 4).ravel().tolist(),
                'faces': use_f.astype(int).ravel().tolist(),
                'color': color,
                'material_role': material_role,
                'offset': offset or [0.0, 0.0, 0.0],
                'pinned': bool(pinned),
            }
            if vc is not None:
                out['vertex_colors'] = np.round(vc, 3).ravel().tolist()
            if vis_n is not None:
                out['normals'] = np.round(vis_n, 4).ravel().tolist()
            return out

        role_colors = {
            'carbon_satin': '#1e232a',
            'vtx_gold': '#f4b41a',
            'titanium_strut': '#8b95a5',
            'canopy_glass': '#385873',
            'cockpit_detail': '#171b22',
            'avionics_glow': '#38bdf8',
            'fan_rotor': '#64748b',
        }
        airframe_meshes = getattr(self.hull_bundle, 'airframe_meshes', {})
        if airframe_meshes:
            meshes = [
                _mesh_dict('airframe', self.hull_bundle.main_hull.mesh, role_colors['carbon_satin'], part_name='main_hull', material_role='carbon_satin', pinned=True),
                _mesh_dict('sponson_port', self.hull_bundle.port_sponson.mesh, role_colors['carbon_satin'], part_name='sponson_port', material_role='carbon_satin', pinned=True),
                _mesh_dict('sponson_stbd', self.hull_bundle.stbd_sponson.mesh, role_colors['carbon_satin'], part_name='sponson_stbd', material_role='carbon_satin', pinned=True),
            ]
            for part_key, spec in airframe_meshes.items():
                role = str(spec.get('material_role', 'carbon_satin'))
                bname = str(spec.get('body', 'airframe'))
                raw_off = [float(x) for x in spec.get('offset', [0.0, 0.0, 0.0])]
                if bname == 'airframe':
                    local_off = raw_off
                else:
                    bpos = CHILD_BODY_POS_BY_NAME.get(bname, (0.0, 0.0, 0.0))
                    local_off = [round(raw_off[0] - bpos[0], 5), round(raw_off[1] - bpos[1], 5), round(raw_off[2] - bpos[2], 5)]
                meshes.append(
                    _mesh_dict(
                        bname,
                        spec['mesh'],
                        role_colors.get(role, '#1e232a'),
                        part_name=part_key,
                        material_role=role,
                        offset=local_off,
                        pinned=bool(spec.get('pin_to_mujoco', False)),
                    )
                )
            boxes = []
        else:
            meshes = [
                _mesh_dict('airframe', self.hull_bundle.main_hull.mesh, '#dfe7ee'),
                _mesh_dict('sponson_port', self.hull_bundle.port_sponson.mesh, '#ff7a18'),
                _mesh_dict('sponson_stbd', self.hull_bundle.stbd_sponson.mesh, '#ff7a18'),
            ]
            boxes = [
                {'body': 'airframe', 'name': 'wing_port', 'pos': [0.02, 2.80, 1.15], 'half': [0.75, 2.00, 0.06], 'euler_deg': [2.0, 0.0, 0.0], 'color': '#cfd9e2'},
                {'body': 'airframe', 'name': 'wing_stbd', 'pos': [0.02, -2.80, 1.15], 'half': [0.75, 2.00, 0.06], 'euler_deg': [-2.0, 0.0, 0.0], 'color': '#cfd9e2'},
                {'body': 'airframe', 'name': 'tail_pylon', 'pos': [-2.18, 0.0, 1.66], 'half': [0.46, 0.10, 0.68], 'euler_deg': [0.0, -28.0, 0.0], 'color': '#3a4654'},
                {'body': 'airframe', 'name': 'h_tail', 'pos': [-2.62, 0.0, 2.28], 'half': [0.36, 1.25, 0.05], 'euler_deg': [0.0, 0.0, 0.0], 'color': '#cfd9e2'},
                {'body': 'airframe', 'name': 'duct_port', 'pos': [-2.22, 1.22, 1.70], 'half': [0.22, 0.32, 0.32], 'euler_deg': [0.0, 0.0, 0.0], 'color': '#f59e0b'},
                {'body': 'airframe', 'name': 'duct_stbd', 'pos': [-2.22, -1.22, 1.70], 'half': [0.22, 0.32, 0.32], 'euler_deg': [0.0, 0.0, 0.0], 'color': '#f59e0b'},
            ]
            if self.hull_bundle.variant_id != 'concept_a':
                boxes.append({'body': 'airframe', 'name': 'cabin_canopy', 'pos': [0.84, 0.0, 1.30], 'half': [0.85, 0.42, 0.22], 'euler_deg': [0.0, 0.0, 0.0], 'color': '#263848'})

        return {
            'hull_variant': self.hull_bundle.variant_id,
            'geometry_sha256': self.hull_bundle.main_hull.mesh.geometry_sha256,
            'meshes': meshes,
            'boxes': boxes,
        }

    def physical_snapshot(self) -> dict[str, Any]:
        d = self.data
        bid = self.bids['airframe']
        pos = d.xpos[bid]
        quat = d.xquat[bid]  # w, x, y, z
        euler = Rotation.from_quat([quat[1], quat[2], quat[3], quat[0]]).as_euler('xyz', degrees=True)
        vel = np.zeros(6, dtype=np.float64)
        mj.mj_objectVelocity(self.model, d, mj.mjtObj.mjOBJ_BODY, bid, vel, 0)
        rot = d.xmat[bid].reshape(3, 3)
        vel_body = rot.T @ vel[3:]

        hydro = self.last_hydro.to_telemetry_dict() if self.last_hydro else {}
        body_poses = {}
        for name, b in self.bids.items():
            bp = d.xpos[b]
            bq = d.xquat[b]
            body_poses[name] = {
                'position': [round(float(x), 4) for x in bp],
                'quaternion_wxyz': [round(float(bq[0]), 6), round(float(bq[1]), 6), round(float(bq[2]), 6), round(float(bq[3]), 6)],
                'position_m': [round(float(x), 4) for x in bp],
                'quaternion_xyzw': [round(float(bq[1]), 6), round(float(bq[2]), 6), round(float(bq[3]), 6), round(float(bq[0]), 6)],
            }

        att = self.attachment_loads()
        v_air_w = vel[3:] - self.wind
        q_dyn_snap = 0.5 * RHO_AIR_ISA * float(np.dot(v_air_w, v_air_w))
        aero_b_snap = rot.T @ self.last_aero_force_n
        sp_p_q, _ = self.joint('sponson_port_flex_z')
        sp_s_q, _ = self.joint('sponson_stbd_flex_z')
        hull_hz = float(self.last_hydro.component_loads.get('main_hull', {}).get('buoyancy_z_n', 0.0)) if self.last_hydro else 0.0
        rigidity = compute_structural_loads_snapshot(
            aero_force_body_n=aero_b_snap,
            sponson_port_z_force_n=float(att['sponson_port']['force_n'][2]),
            sponson_stbd_z_force_n=float(att['sponson_stbd']['force_n'][2]),
            hull_hydro_z_n=hull_hz,
            fan_thrust_port_n=float(self.last_thrust_per_fan_n[0]),
            fan_thrust_stbd_n=float(self.last_thrust_per_fan_n[1]),
            dynamic_pressure_pa=q_dyn_snap,
            sponson_port_deflection_m=sp_p_q,
            sponson_stbd_deflection_m=sp_s_q,
        )

        joints_q = {n: round(float(self.joint(n)[0]), 6) for n in self.jids if n != 'root'}
        ctrl_surf = self.control_surface_telemetry()
        mp = self.mass_properties()
        actuator_state = {}
        for spec in ARTICULATED_CHILD_SPECS:
            aid = self.aids.get(spec['actuator_name'], -1)
            actuator_state[spec['actuator_name']] = {
                'ctrl': round(float(d.ctrl[aid]), 5) if aid >= 0 else 0.0,
                'force_nm': round(float(d.actuator_force[aid]), 3) if aid >= 0 else 0.0,
                'saturated': bool(self._last_servo_saturated.get(spec['body'], False)),
            }

        return {
            # VTX standard engineering fields
            't_s': round(float(d.time), 4),
            'variant': self.variant,
            'body_poses': body_poses,
            'provenance': self.provenance,
            'events': list(self.events[-20:]),
            'joints': joints_q,
            'mass': mp,
            'propulsors': [dict(r) for r in self.rotors],
            'aero': dict(
                self.last_aero_detail,
                force_world_n=[round(float(x), 2) for x in self.last_aero_force_n],
                moment_world_nm=[round(float(x), 2) for x in self.last_aero_torque_nm],
                cn_yaw=round(float(self.last_cn_yaw), 5),
                cn_beta_per_rad=round(float(self.last_cn_beta), 4),
            ),
            'power': dict(self.power),
            'energy': dict(self.energy),
            'command': dict(self.command),
            'targets': {k: round(float(v), 4) for k, v in self._targets.items()},
            'actuators': actuator_state,
            'fuel_kg': [round(float(x), 4) for x in self.fuel],
            'environment': {
                'wind_world_mps': [round(float(x), 4) for x in self.wind],
                'water_config': self.water_config.to_dict(),
            },
            'contact': {
                'count': int(d.ncon),
                'max_contact_force_n': round(float(self.max_impact_n), 2),
            },
            'flags': sorted(self.flags),
            'crashed': self.crashed,
            'mechanical_energy_j': round(float(d.energy[0] + d.energy[1]), 3),
            # Ricochet marine/amphibious telemetry fields
            'ricochet': True,
            'airframe_variant': self.variant,
            'hull_variant': self.hull_bundle.variant_id,
            'position_world_m': [round(float(x), 5) for x in pos],
            'quaternion_xyzw': [round(float(quat[1]), 6), round(float(quat[2]), 6), round(float(quat[3]), 6), round(float(quat[0]), 6)],
            'attitude_xyz_deg': [round(float(x), 4) for x in euler],
            'roll_deg': round(float(euler[0]), 4),
            'pitch_deg': round(float(euler[1]), 4),
            'yaw_deg': round(float(euler[2]), 4),
            'velocity_world_mps': [round(float(x), 4) for x in vel[3:]],
            'velocity_body_mps': [round(float(x), 4) for x in vel_body],
            'omega_world_rad_s': [round(float(x), 5) for x in vel[:3]],
            'hydrodynamics': hydro,
            'propulsion_force_world_n': [round(float(x), 2) for x in self.last_propulsion_n],
            'aero_force_world_n': [round(float(x), 2) for x in self.last_aero_force_n],
            'cg_body_m': [round(float(x), 4) for x in self.model.body_ipos[bid]],
            'cb_body_m': hydro.get('centre_of_buoyancy_body_m', [0.0, 0.0, 0.0]),
            'cn_yaw': round(float(self.last_cn_yaw), 5),
            'cn_beta_per_rad': round(float(self.last_cn_beta), 4),
            'munk_moment_nm': [round(float(x), 2) for x in self.last_munk_moment_nm],
            'munk_yaw_nm': round(float(self.last_munk_moment_nm[2]), 2),
            'fan_rpm': [round(float(x), 1) for x in self.last_fan_rpm],
            'thrust_per_fan_n': [round(float(x), 2) for x in self.last_thrust_per_fan_n],
            'control_surfaces': ctrl_surf,
            'surface_limits': RICOCHET_SURFACE_LIMITS,
            'attachment_loads': att,
            'structural_rigidity': rigidity,
            'water_conservation': self.water_field.shallow.conservation_metrics(),
            'water_config': self.water_config.to_dict(),
            'mass_properties': mp,
            'whirlpool_hazard': dict(self._last_whirlpool_hazard),
            'vessel_wake': self.water_field.get_wake_state(),
            'contacts': int(d.ncon),
            'max_impact_n': round(float(self.max_impact_n), 2),
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            'time': float(self.data.time),
            'qpos': self.data.qpos.tolist(),
            'qvel': self.data.qvel.tolist(),
            'ctrl': self.data.ctrl.tolist(),
            'step_count': int(self.step_count),
            'command': dict(self.command),
            'targets': dict(self._targets),
            'fuel': self.fuel.tolist(),
            'energy': dict(self.energy),
            'flags': sorted(self.flags),
            'water_config': self.water_config.to_dict(),
            'mass_load_case': self.mass_register.load_case,
            'passenger_aboard': self.mass_register.passenger_aboard,
            'passenger_mass_kg': self.mass_register.passenger_mass_kg,
            'payload_mass_kg': self.mass_register.payload_mass_kg,
            'ballast_mass_kg': self.mass_register.ballast_mass_kg,
            'ballast_x_m': self.mass_register.ballast_x_m,
            'ballast_y_m': self.mass_register.ballast_y_m,
            'waterproof': self.mass_register.waterproof,
            'flood_water_kg': self.mass_register.flood_water_kg,
        }

    def restore_state(self, st: dict[str, Any]) -> None:
        self.update_water_config(st['water_config'])
        self.update_mass_properties(
            load_case=st['mass_load_case'],
            passenger_aboard=st['passenger_aboard'],
            passenger_mass_kg=st['passenger_mass_kg'],
            payload_mass_kg=st['payload_mass_kg'],
            ballast_mass_kg=st.get('ballast_mass_kg'),
            ballast_x_m=st.get('ballast_x_m'),
            ballast_y_m=st.get('ballast_y_m'),
            waterproof=st.get('waterproof'),
            flood_water_kg=st.get('flood_water_kg', 0.0),
        )
        self.data.time = float(st['time'])
        self.data.qpos[:] = np.asarray(st['qpos'], dtype=np.float64)
        self.data.qvel[:] = np.asarray(st['qvel'], dtype=np.float64)
        if 'ctrl' in st and len(st['ctrl']) == self.model.nu:
            self.data.ctrl[:] = np.asarray(st['ctrl'], dtype=np.float64)
        self.step_count = int(st['step_count'])
        self.command.update(st['command'])
        self._targets.update(st.get('targets', st['command']))
        if 'fuel' in st:
            self.fuel[:] = np.asarray(st['fuel'], dtype=np.float64)
        if 'energy' in st:
            self.energy.update(st['energy'])
        if 'flags' in st:
            self.flags = set(st['flags'])
        mj.mj_forward(self.model, self.data)
        self._evaluate_and_cache_hydro(t=float(self.data.time), force_eval=True)
