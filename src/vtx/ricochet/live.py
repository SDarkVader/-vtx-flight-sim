"""Live server adapter for RicochetCraft & RicochetLakeWorld.

Keeps Ricochet-specific schemas, telemetry, water environment controls, and run
export helpers cleanly decoupled from `src/vtx/live_server.py`.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

import mujoco as mj
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.spatial.transform import Rotation

from vtx.ricochet.plant import RicochetCraft
from vtx.water.datum import WaterEnvironmentConfig
from vtx.water.lake_world import RicochetLakeWorld

RICOCHET_VARIANTS = ('ricochet-rc01-f03', 'ricochet-concept-a', 'ricochet-rc01-dev')


def is_ricochet_variant(variant: str | None) -> bool:
    return bool(variant and variant in RICOCHET_VARIANTS)


def hull_variant_for_airframe(airframe_variant: str | None) -> str:
    if airframe_variant == 'ricochet-concept-a':
        return 'concept_a'
    return 'f03'


class RicochetAction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)

    schema_id: Literal['ricochet-1'] = Field(default='ricochet-1', alias='schema')
    authority: Literal['colin', 'manual'] = 'manual'
    expected_run_id: str | None = None
    observation_id: int | None = None
    pilot_id: str | None = None
    pilot_epoch: int | None = None
    pilot_run_id: str | None = None
    reason: str = Field(default='ricochet operator command', max_length=256)
    throttle: float = Field(default=0.0, ge=0.0, le=1.0)
    differential_thrust: float = Field(default=0.0, ge=-1.0, le=1.0)
    rudder_deg: float = Field(default=0.0, ge=-30.0, le=30.0)
    elevator_deg: float = Field(default=0.0, ge=-20.0, le=20.0)
    aileron_deg: float = Field(default=0.0, ge=-25.0, le=25.0)
    reverse_bucket: float = Field(default=0.0, ge=0.0, le=1.0)


def make_aircraft(
    world: Any,
    airframe_variant: str = 'ricochet-rc01-f03',
    water_config: WaterEnvironmentConfig | None = None,
    load_case: str = 'LC-03',
    wind_world_mps: list[float] | tuple[float, float, float] | None = None,
) -> RicochetCraft:
    if not isinstance(world, RicochetLakeWorld):
        raise ValueError('Ricochet craft requires the ricochet_lake environment')
    cfg = water_config or WaterEnvironmentConfig()
    if wind_world_mps is not None and any(abs(float(x)) > 1e-6 for x in wind_world_mps):
        wx, wy = float(wind_world_mps[0]), float(wind_world_mps[1])
        spd = math.hypot(wx, wy)
        deg = math.degrees(math.atan2(wy, wx)) % 360.0
        cfg = WaterEnvironmentConfig(**{**cfg.to_dict(), 'wind_speed_mps': spd, 'wind_direction_deg': deg})
    craft = RicochetCraft(
        world=world,
        variant=airframe_variant,
        hull_variant=hull_variant_for_airframe(airframe_variant),
        load_case=load_case,
        water_config=cfg,
    )
    return craft


def sensor_observation(lab: Any) -> dict[str, Any]:
    p: RicochetCraft = lab.aircraft
    d = p.data
    m = p.model
    bid = p.bids['airframe']
    q = d.xquat[bid]
    euler = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_euler('xyz', degrees=True)
    vel = np.zeros(6, dtype=np.float64)
    mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_BODY, bid, vel, 0)
    rot = d.xmat[bid].reshape(3, 3)
    vel_body = rot.T @ vel[3:]
    pos = d.xpos[bid]
    clearance = p.ground_clearance()
    noise = lab.sensor_rng.normal

    hydro = p.last_hydro.to_telemetry_dict() if p.last_hydro else {}
    obs = dict(
        observation_id=lab.obs_id,
        t_s=round(float(d.time), 3),
        wall_utc=datetime.now(timezone.utc).isoformat(),
        action_schema='ricochet-1',
        command_mode='hold_until_changed',
        gnss_xy_m=np.round(pos[:2] + noise(0, 0.015, 2), 2).tolist(),
        baro_m=round(float(pos[2] + noise(0, 0.01)), 3),
        radar_clearance_m=round(float(clearance + noise(0, 0.005)), 3) if clearance is not None else None,
        attitude_xyz_deg=np.round(euler + noise(0, 0.008, 3), 3).tolist(),
        gyro_world_deg_s=np.round(np.degrees(vel[:3]) + noise(0, 0.008, 3), 3).tolist(),
        gnss_velocity_mps=np.round(vel[3:] + noise(0, 0.005, 3), 3).tolist(),
        body_velocity_mps=np.round(vel_body, 3).tolist(),
        shaft_torque_nm=[round(v['torque_nm'], 1) for v in p.rotors],
        engine_shaft_kw=round(p.power['engine_w'] / 1000.0, 2),
        fuel_kg=np.round(p.fuel, 4).tolist(),
        command=dict(p.command),
        hydrodynamics=hydro,
        attachment_loads=p.attachment_loads(),
        mass_properties=p.mass_properties(),
        water_config=p.water_config.to_dict(),
        water_conservation=p.water_field.shallow.conservation_metrics(),
        warning_lamps=(['IMPACT'] if p.crashed else []) + (['SHALLOW_KEEL_CLEARANCE'] if clearance is not None and clearance < 0.2 else []),
        configuration=dict(
            airframe_revision=p.provenance['revision'],
            airframe_variant=p.variant,
            hull_variant=p.hull_bundle.variant_id,
            hull_geometry_sha256=p.provenance['hull_geometry_sha256'],
            solver_version=p.provenance['solver_version'],
            load_case=p.mass_register.load_case,
        ),
        scheduler_backlog_s=round(lab.clock_lag_s, 3),
        mission=lab.mission,
        authority=lab.authority,
        active=lab.active,
        paused=lab.paused,
        time_scale=lab.time_scale,
        sensor_status='Ricochet LAKE MuJoCo 400 Hz + HybridWaterField telemetry (provisional calibration)',
    )
    return obs


def integrate(lab: Any) -> None:
    p: RicochetCraft = lab.aircraft
    while lab.next_pending_action < len(lab.action_log):
        row = lab.action_log[lab.next_pending_action]
        if row.get('cancelled'):
            lab.next_pending_action += 1
            continue
        if p.data.time < row['apply_t_s']:
            break
        lab.next_pending_action += 1
        if row['issued']['authority'] != lab.authority:
            row['cancelled'] = True
            lab.log('control_cancelled', dict(sequence=row['sequence'], reason='Control authority changed before application'))
            continue
        cmd = {k: row['issued'][k] for k in p.command if k in row['issued']}
        p.set_command(cmd)
        row['applied'] = True
        lab.log('control_applied', dict(sequence=row['sequence'], requested=cmd, applied_sim_t_s=float(p.data.time)))
    p.step()
    if p.data.time - lab.last_audit_t >= 0.05:
        lab.last_audit_t = float(p.data.time)
        lab.log('physics_audit', p.physical_snapshot())
        lab.sensor_observation()
        lab.checkpoint()


def water_frame(world: Any, aircraft: Any | None = None) -> dict[str, Any] | None:
    """Compact elevation sample grid + conservation stats for Three.js water surface animation."""
    if not isinstance(world, RicochetLakeWorld):
        return None
    wf = getattr(aircraft, 'water_field', None)
    if wf is None:
        return None
    # Sample 41x25 subset over the whole 2000x1200 m lake so Three.js PlaneGeometry updates in <1 ms
    t_s = float(aircraft.data.time) if aircraft is not None else 0.0
    g = wf.elevation_grid(nx=41, ny=25, t=t_s)
    return {
        'nx': int(g['nx']),
        'ny': int(g['ny']),
        'x_min_m': float(-g['half_x']),
        'x_max_m': float(g['half_x']),
        'y_min_m': float(-g['half_y']),
        'y_max_m': float(g['half_y']),
        'water_level_m': float(g['water_level_m']),
        't_s': round(t_s, 4),
        'elevation_m': g['eta'],
        'water_config': wf.config.to_dict(),
        'conservation': wf.shallow.conservation_metrics(),
    }


def export_run_bundle(lab: Any) -> dict[str, Any]:
    p = lab.aircraft
    if not getattr(p, 'is_ricochet', False):
        raise ValueError('Water test export is only available when RicochetCraft is loaded')
    return {
        'run_id': lab.run_id,
        'active': lab.active,
        'paused': lab.paused,
        'time_scale': lab.time_scale,
        'exported_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {
            'key': getattr(lab.world, 'environment_key', 'ricochet_lake'),
            'id': lab.world.id,
            'version': lab.world.version,
        },
        'water_config': p.water_config.to_dict(),
        'random_seed': p.water_config.wave_seed,
        'geometry_hash': p.provenance['hull_geometry_sha256'],
        'solver_version': p.provenance['solver_version'],
        'provenance': p.provenance,
        'mass_properties': p.mass_properties(),
        'water_conservation': p.water_field.shallow.conservation_metrics(),
        'telemetry': p.physical_snapshot(),
        'recent_decisions': [{k: v for k, v in a.items() if k != 'observation'} for a in lab.action_log[-32:]],
    }
