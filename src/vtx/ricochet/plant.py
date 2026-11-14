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

    # Core airframe rigid body (freejoint + aggregated core mass & parallel-axis inertia)
    core_agg = mass_reg.aggregate(include_sponsons=False)
    core_m = max(core_agg['total_mass_kg'], 50.0)
    core_cg = core_agg['cg_vtx_m']
    inert = np.asarray(core_agg['inertia_vtx_kg_m2'], dtype=np.float64)
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
        self.mass_register = MassPropertiesRegister.for_load_case(load_case=load_case)
        self.hull_bundle = HullGeometryRegistry.build_variant(
            variant_id=hull_variant,
            subdivide_levels=subdivide_levels,
            concept_a_glb_path=concept_a_glb_path,
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
        self.stability_assist = 0.0
        self.wind = self._wind_vector_from_config()
        self.fuel_initial = np.array([10.0], dtype=np.float64)
        self.fuel = np.array([10.0], dtype=np.float64)
        self.rotors = [{'torque_nm': 0.0}, {'torque_nm': 0.0}]
        self.power = {'engine_w': 0.0}
        self.energy = {'remaining_kwh': 20.0}
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
        self._last_aero_munk_nm = np.zeros(3, dtype=np.float64)
        self.last_munk_moment_nm = np.zeros(3, dtype=np.float64)
        self.last_cn_yaw = 0.0
        self.last_cn_beta = 0.095
        self.last_fan_rpm = [0.0, 0.0]
        self.last_thrust_per_fan_n = [0.0, 0.0]

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
        self.model.body_mass[bid] = max(agg['total_mass_kg'], 20.0)
        self.model.body_ipos[bid] = np.asarray(agg['cg_vtx_m'], dtype=np.float64)
        iner = np.asarray(agg['inertia_vtx_kg_m2'], dtype=np.float64)
        # Recompute principal inertia + orientation in MuJoCo (body_inertia + body_iquat)
        eigvals, eigvecs = np.linalg.eigh(0.5 * (iner + iner.T))
        if np.linalg.det(eigvecs) < 0.0:
            eigvecs[:, 0] = -eigvecs[:, 0]
        eigvals = np.maximum(eigvals, 1.0)
        self.model.body_inertia[bid] = eigvals
        q_xyzw = Rotation.from_matrix(eigvecs).as_quat()
        self.model.body_iquat[bid] = np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]], dtype=np.float64)
        mj.mj_setConst(self.model, self.data)
        mj.mj_forward(self.model, self.data)

    def update_mass_properties(
        self,
        load_case: str | None = None,
        total_mass_kg: float | None = None,
        cg_shift_vtx_m: list[float] | tuple[float, float, float] | None = None,
        passenger_aboard: bool | None = None,
        passenger_mass_kg: float | None = None,
        payload_mass_kg: float | None = None,
    ) -> dict[str, Any]:
        if load_case is not None and load_case.upper() != self.mass_register.load_case:
            self.mass_register = MassPropertiesRegister.for_load_case(
                load_case=load_case,
                passenger_aboard=passenger_aboard,
                passenger_mass_kg=passenger_mass_kg,
                payload_mass_kg=payload_mass_kg,
            )
        else:
            self.mass_register.set_runtime_override(
                total_mass_kg=total_mass_kg,
                cg_shift_vtx_m=cg_shift_vtx_m,
                passenger_aboard=passenger_aboard,
                passenger_mass_kg=passenger_mass_kg,
                payload_mass_kg=payload_mass_kg,
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
        mj.mj_resetData(self.model, self.data)
        # When spawning at surface_z over navigable water, initialize near calm draft
        # instead of dropping from air; explicit elevated drop z (> wl + 0.05) stays verbatim.
        wl = float(self.water_config.water_level_m)
        bed = float(self.world.terrain_z(x, y))
        target_draft = 0.56 if self.hull_bundle.variant_id == 'concept_a' else 0.37
        if bed < wl - 0.25 and abs(z - max(bed, wl)) < 0.05:
            spawn_z = max(bed + 0.02, wl - target_draft)
        else:
            spawn_z = max(z, bed + 0.02)
        self.data.qpos[0:3] = np.array([float(x), float(y), spawn_z], dtype=np.float64)
        rot = Rotation.from_euler('xyz', [roll_deg, pitch_deg, yaw_deg], degrees=True)
        qx, qy, qz, qw = rot.as_quat()
        self.data.qpos[3:7] = np.array([qw, qx, qy, qz], dtype=np.float64)
        self.data.qvel[:] = 0.0
        self.data.xfrc_applied[:] = 0.0
        self.step_count = 0
        self.crashed = False
        self.max_impact_n = 0.0
        self.events.clear()
        self.flags.clear()
        self._prev_hydro_f.clear()
        self._curr_hydro_f.clear()
        mj.mj_forward(self.model, self.data)
        # Populate initial hydrostatic state telemetry cleanly at t=0
        self._evaluate_and_cache_hydro(t=float(self.data.time), force_eval=True)

    def set_command(self, cmd: dict[str, Any]) -> None:
        if 'throttle' in cmd:
            self.command['throttle'] = float(np.clip(cmd['throttle'], 0.0, 1.0))
        if 'differential_thrust' in cmd:
            self.command['differential_thrust'] = float(np.clip(cmd['differential_thrust'], -1.0, 1.0))
        if 'rudder_deg' in cmd:
            self.command['rudder_deg'] = float(np.clip(cmd['rudder_deg'], -30.0, 30.0))
        if 'elevator_deg' in cmd:
            self.command['elevator_deg'] = float(np.clip(cmd['elevator_deg'], -20.0, 20.0))
        if 'aileron_deg' in cmd:
            self.command['aileron_deg'] = float(np.clip(cmd['aileron_deg'], -25.0, 25.0))
        if 'reverse_bucket' in cmd:
            val = cmd['reverse_bucket']
            self.command['reverse_bucket'] = float(np.clip(float(val), 0.0, 1.0))

    def _compute_aero_and_propulsion(self) -> tuple[np.ndarray, np.ndarray]:
        d = self.data
        bid = self.bids['airframe']
        _, xipos, rot, vel_w, omega_w, _, _ = _body_state(d, bid)
        v_air_w = vel_w - self.wind
        v_air_b = rot.T @ v_air_w
        u, v, w = float(v_air_b[0]), float(v_air_b[1]), float(v_air_b[2])
        speed = math.sqrt(u * u + v * v + w * w)

        # Documented twin aft Ø0.90 m ducted fans at (-2.05, +0.78/-0.78, 1.56) in VTX body frame
        fan_diam_m = 0.90
        fan_y_arm = 0.78
        fan_z_pos = 1.56
        throt = self.command['throttle']
        diff = self.command['differential_thrust']
        rev = self.command['reverse_bucket']
        dir_sign = 1.0 - 1.55 * rev  # reverse bucket directs ~55% net astern
        # Momentum/inflow thrust lapse with airspeed u (m/s)
        inflow_lapse = max(0.55, min(1.05, 1.0 - 0.18 * (max(u, 0.0) / 45.0)))
        t_port = self.MAX_THRUST_PER_FAN_N * inflow_lapse * throt * max(0.0, 1.0 - 0.5 * diff) * dir_sign
        t_stbd = self.MAX_THRUST_PER_FAN_N * inflow_lapse * throt * max(0.0, 1.0 + 0.5 * diff) * dir_sign
        self.last_thrust_per_fan_n = [float(t_port), float(t_stbd)]
        # Fan RPM from actuator-disk scaling T ~ C_T * rho * n^2 * D^4 (C_T ~ 0.24 for ducted 9-blade)
        ct_fan = 0.24
        rpm_port = 60.0 * math.sqrt(abs(t_port) / (ct_fan * RHO_AIR_ISA * (fan_diam_m ** 4))) if abs(t_port) > 1.0 else (900.0 if throt > 0.01 else 0.0)
        rpm_stbd = 60.0 * math.sqrt(abs(t_stbd) / (ct_fan * RHO_AIR_ISA * (fan_diam_m ** 4))) if abs(t_stbd) > 1.0 else (900.0 if throt > 0.01 else 0.0)
        self.last_fan_rpm = [float(rpm_port), float(rpm_stbd)]

        f_prop_b = np.array([t_port + t_stbd, 0.0, 0.0], dtype=np.float64)
        # Yaw moment from differential thrust (r_y = +/-0.78 m), pitch-down from pylon thrust (z=1.56 m),
        # and counter-rotating fan differential roll reaction torque
        r_cg = self.model.body_ipos[bid]
        z_arm = fan_z_pos - float(r_cg[2])
        m_prop_b = np.array([
            (t_port - t_stbd) * 0.08,
            z_arm * (t_port + t_stbd),
            (t_stbd - t_port) * fan_y_arm,
        ], dtype=np.float64)

        # Aerodynamic wing, winglets & T-tail (S_ref = 15.5 m^2, b = 9.60 m)
        q_dyn = 0.5 * RHO_AIR_ISA * speed * speed
        alpha = math.atan2(-w, max(abs(u), 0.8)) if speed > 0.3 else 0.0
        beta = math.atan2(v, max(abs(u), 0.5)) if speed > 0.3 else 0.0
        cl_wing = 0.25 + 4.2 * alpha
        s_wing = 15.50
        b_wing = 9.60
        if self.hull_bundle.variant_id == 'concept_a':
            cd0_craft = canopy_and_craft_cd0(windshield_rake_deg=24.0, canopy_fineness_ratio=4.0)['cd0_total']
            hull_drag_area = 1.15 + 0.05 * s_wing
        else:
            cd0_craft = canopy_and_craft_cd0(windshield_rake_deg=82.0, canopy_fineness_ratio=2.2)['cd0_total']
            hull_drag_area = 1.8 + 0.08 * s_wing
        cd_wing = cd0_craft + 0.048 * cl_wing * cl_wing
        f_lift_aero = q_dyn * s_wing * cl_wing * (1.0 if u >= -0.2 else 0.2)
        f_aero_b = np.array([
            -0.5 * RHO_AIR_ISA * abs(u) * u * hull_drag_area - q_dyn * s_wing * cd_wing * np.sign(u),
            -0.5 * RHO_AIR_ISA * abs(v) * v * 3.8,
            f_lift_aero - 0.5 * RHO_AIR_ISA * abs(w) * w * 4.5,
        ], dtype=np.float64)

        # Directional stability Cn (tail pylon at x=-2.05 m + winglets) & slipstream-augmented control
        v_slip = max(abs(u), 5.0 * throt)
        rud_rad = math.radians(self.command['rudder_deg'])
        elev_rad = math.radians(self.command['elevator_deg'])
        ail_rad = math.radians(self.command['aileron_deg'])

        q_tail = 0.5 * RHO_AIR_ISA * (u * u + 0.65 * v_slip * v_slip)
        omega_b = rot.T @ omega_w
        # Cn = Cn_beta * (+beta_port) + Cn_r * r_hat + Cn_dr * rudder (weathercock restoring yaw into relative wind; +v_y is port)
        cn_beta = 0.095
        cn_r = -0.18
        cn_dr = 0.14
        r_hat = omega_b[2] * (0.5 * b_wing) / max(speed, 2.0)
        cn_yaw = cn_beta * math.sin(beta) + cn_r * r_hat + cn_dr * rud_rad
        yaw_weathercock = q_tail * s_wing * b_wing * (cn_beta * math.sin(beta)) * 0.25
        yaw_rudder = 2.6 * q_tail * 1.15 * rud_rad * 2.85
        pitch_elev = -2.4 * q_tail * 1.10 * elev_rad * 3.10
        roll_ail = 1.8 * 0.5 * RHO_AIR_ISA * max(speed, 1.0) ** 2 * 1.6 * ail_rad * 3.2
        aero_damp_m = -np.array([120.0 * omega_b[0], 180.0 * omega_b[1], 160.0 * omega_b[2]], dtype=np.float64)

        # Pure aerodynamic slender-body Munk moment (rho_air = 1.225 kg/m^3); water Kirchhoff-Munk torque is computed inside hydrodynamics.py
        ma_air_diag = np.array([0.8, 3.8, 4.5], dtype=np.float64)
        aero_munk_b = -np.cross(v_air_b, ma_air_diag * v_air_b)
        self._last_aero_munk_nm = aero_munk_b
        hydro_munk_b = self.last_hydro.munk_torque_body if self.last_hydro is not None else np.zeros(3, dtype=np.float64)
        self.last_munk_moment_nm = aero_munk_b + hydro_munk_b
        self.last_cn_yaw = float(cn_yaw)
        self.last_cn_beta = float(cn_beta)

        m_aero_b = np.array([roll_ail, pitch_elev, yaw_rudder + yaw_weathercock], dtype=np.float64) + aero_damp_m + aero_munk_b

        f_prop_w = rot @ f_prop_b
        m_prop_w = rot @ m_prop_b
        f_aero_w = rot @ f_aero_b
        m_aero_w = rot @ m_aero_b

        self.last_propulsion_n = f_prop_w
        self.last_propulsion_torque_nm = m_prop_w
        self.last_aero_force_n = f_aero_w
        self.last_aero_torque_nm = m_aero_w
        self.power['engine_w'] = float((abs(t_port) + abs(t_stbd)) * max(abs(u), 6.0))
        self.rotors[0]['torque_nm'] = float(t_port * 0.18)
        self.rotors[1]['torque_nm'] = float(t_stbd * 0.18)

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

            m_m = float(self.model.body_mass[bid_m])
            m_p = float(self.model.body_mass[bid_p])
            m_s = float(self.model.body_mass[bid_s])
            m_tot = m_m + m_p + m_s
            x_com_w = (m_m * xipos_m + m_p * xipos_p + m_s * xipos_s) / max(m_tot, 1e-6)
            ext_f_m = np.zeros(3, dtype=np.float64) if ext_force_m is None else np.asarray(ext_force_m, dtype=np.float64)
            ext_t_m = np.zeros(3, dtype=np.float64) if ext_torque_m is None else np.asarray(ext_torque_m, dtype=np.float64)
            f_free_tot = (
                bd_m.total_force_world + bd_p.total_force_world + bd_s.total_force_world
                + ext_f_m + np.array([0.0, 0.0, -m_tot * g_w], dtype=np.float64)
            )
            t_free_tot = (
                bd_m.total_torque_world + np.cross(xipos_m - x_com_w, bd_m.total_force_world + np.array([0.0, 0.0, -m_m * g_w]))
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

            r_m_b = rot_m.T @ (xipos_m - x_com_w)
            r_p_b = rot_m.T @ (xipos_p - x_com_w)
            r_s_b = rot_m.T @ (xipos_s - x_com_w)

            def _par_scalar(mv: float, rv: np.ndarray) -> np.ndarray:
                return np.array([mv * (rv[1]**2 + rv[2]**2), mv * (rv[0]**2 + rv[2]**2), mv * (rv[0]**2 + rv[1]**2)], dtype=np.float64)

            def _par_vec(mv: np.ndarray, rv: np.ndarray) -> np.ndarray:
                return np.array([mv[2] * rv[1]**2 + mv[1] * rv[2]**2, mv[2] * rv[0]**2 + mv[0] * rv[2]**2, mv[1] * rv[0]**2 + mv[0] * rv[1]**2], dtype=np.float64)

            i_tot_b = (
                np.asarray(self.model.body_inertia[bid_m], dtype=np.float64)
                + np.asarray(self.model.body_inertia[bid_p], dtype=np.float64)
                + np.asarray(self.model.body_inertia[bid_s], dtype=np.float64)
                + _par_scalar(m_m, r_m_b) + _par_scalar(m_p, r_p_b) + _par_scalar(m_s, r_s_b)
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

    def step(self) -> None:
        """Advance coupled SWE/wave field and 400 Hz MuJoCo rigid-body step."""
        d = self.data
        t = float(d.time)

        # Compute aerodynamic + ducted-fan propulsion forces first so coupled virtual-mass solves cleanly
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
        d.xfrc_applied[:] = 0.0
        for bid, w_curr in self._curr_hydro_f.items():
            w_prev = self._prev_hydro_f.get(bid, w_curr)
            w_interp = (1.0 - sub_phase) * w_prev + sub_phase * w_curr
            # Safety guard against numerical blowup in extreme crashes
            w_interp[:3] = np.clip(w_interp[:3], -8.0e4, 8.0e4)
            w_interp[3:] = np.clip(w_interp[3:], -8.0e4, 8.0e4)
            d.xfrc_applied[bid] = w_interp

        d.xfrc_applied[self.bids['airframe'], :3] += f_ap
        d.xfrc_applied[self.bids['airframe'], 3:] += m_ap

        mj.mj_step(self.model, d)
        self.step_count += 1

        # Track contacts & ground clearance
        alt = float(d.xpos[self.bids['airframe'], 2])
        self.max_alt = max(self.max_alt, alt)
        for ci in range(d.ncon):
            cf = np.zeros(6, dtype=np.float64)
            mj.mj_contactForce(self.model, d, ci, cf)
            n_force = float(np.linalg.norm(cf[:3]))
            self.max_impact_n = max(self.max_impact_n, n_force)
            self.max_gear_load_n = self.max_impact_n

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
        agg['mujoco_total_mass_kg'] = round(float(np.sum(self.model.body_mass)), 4)
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
        """Verify MuJoCo collision meshes match the hydrodynamic hull/sponson meshes in body frame."""
        checks = {}
        mapping = {
            'main_hull_mesh': ('main_hull_geom', self.hull_bundle.main_hull.mesh, np.zeros(3)),
            'sponson_port_mesh': ('sponson_port_geom', self.hull_bundle.port_sponson.mesh, np.zeros(3)),
            'sponson_stbd_mesh': ('sponson_stbd_geom', self.hull_bundle.stbd_sponson.mesh, np.zeros(3)),
        }
        for part_key, spec in getattr(self.hull_bundle, 'airframe_meshes', {}).items():
            if spec.get('pin_to_mujoco'):
                mapping[f'{part_key}_mesh'] = (
                    f'{part_key}_geom',
                    spec['mesh'],
                    np.asarray(spec.get('offset', [0.0, 0.0, 0.0]), dtype=np.float64),
                )
        for mesh_name, (geom_name, wmesh, expected_off) in mapping.items():
            mid = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_MESH, mesh_name)
            gid = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_GEOM, geom_name)
            if mid < 0 or gid < 0:
                raise RuntimeError(f'MuJoCo model is missing pinned mesh/geom asset {mesh_name!r}/{geom_name!r}')
            vadr = int(self.model.mesh_vertadr[mid])
            vnum = int(self.model.mesh_vertnum[mid])
            fadr = int(self.model.mesh_faceadr[mid])
            fnum = int(self.model.mesh_facenum[mid])
            mj_verts = self.model.mesh_vert[vadr:vadr + vnum]
            gq = self.model.geom_quat[gid]  # w, x, y, z
            gp = self.model.geom_pos[gid]
            mj_body = Rotation.from_quat([gq[1], gq[2], gq[3], gq[0]]).apply(mj_verts) + gp - expected_off
            vmin_err = float(np.max(np.abs(mj_body.min(axis=0) - wmesh.vertices.min(axis=0))))
            vmax_err = float(np.max(np.abs(mj_body.max(axis=0) - wmesh.vertices.max(axis=0))))
            checks[mesh_name] = {
                'pinned': (vnum == wmesh.vertices.shape[0] and fnum == wmesh.faces.shape[0] and vmin_err < 1e-4 and vmax_err < 1e-4),
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
                meshes.append(
                    _mesh_dict(
                        'airframe',
                        spec['mesh'],
                        role_colors.get(role, '#1e232a'),
                        part_name=part_key,
                        material_role=role,
                        offset=list(spec.get('offset', [0.0, 0.0, 0.0])),
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

        return {
            'ricochet': True,
            'crashed': self.crashed,
            'events': list(self.events),
            'provenance': self.provenance,
            't_s': round(float(d.time), 4),
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
            'body_poses': body_poses,
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
            'attachment_loads': att,
            'structural_rigidity': rigidity,
            'water_conservation': self.water_field.shallow.conservation_metrics(),
            'water_config': self.water_config.to_dict(),
            'mass_properties': self.mass_properties(),
            'contacts': int(d.ncon),
            'max_impact_n': round(float(self.max_impact_n), 2),
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            'time': float(self.data.time),
            'qpos': self.data.qpos.tolist(),
            'qvel': self.data.qvel.tolist(),
            'step_count': int(self.step_count),
            'command': dict(self.command),
            'water_config': self.water_config.to_dict(),
            'mass_load_case': self.mass_register.load_case,
            'passenger_aboard': self.mass_register.passenger_aboard,
            'passenger_mass_kg': self.mass_register.passenger_mass_kg,
            'payload_mass_kg': self.mass_register.payload_mass_kg,
        }

    def restore_state(self, st: dict[str, Any]) -> None:
        self.update_water_config(st['water_config'])
        self.update_mass_properties(
            load_case=st['mass_load_case'],
            passenger_aboard=st['passenger_aboard'],
            passenger_mass_kg=st['passenger_mass_kg'],
            payload_mass_kg=st['payload_mass_kg'],
        )
        self.data.time = float(st['time'])
        self.data.qpos[:] = np.asarray(st['qpos'], dtype=np.float64)
        self.data.qvel[:] = np.asarray(st['qvel'], dtype=np.float64)
        self.step_count = int(st['step_count'])
        self.command.update(st['command'])
        mj.mj_forward(self.model, self.data)
        self._evaluate_and_cache_hydro(t=float(self.data.time), force_eval=True)
