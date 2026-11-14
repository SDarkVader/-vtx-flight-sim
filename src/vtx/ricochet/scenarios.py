"""Repeatable Ricochet RC-01 physical water test scenarios on RicochetLakeWorld.

All 8 operational scenarios execute full 400 Hz MuJoCo rigid-body integration
coupled with HybridWaterField and geometry-resolved hydrodynamics, recording
6-DOF motion, displaced volume, waterline, trim, freeboard, wetted area,
itemized force/moment channels, and MuJoCo sponson attachment loads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable

import numpy as np

from vtx.ricochet.plant import RicochetCraft
from vtx.water.datum import WaterEnvironmentConfig
from vtx.water.lake_world import RicochetLakeWorld


@dataclass
class ScenarioSpec:
    scenario_id: str
    title: str
    load_case: str
    spawn_xy: tuple[float, float]
    yaw_deg: float
    duration_s: float
    water_config: WaterEnvironmentConfig
    command_fn: Callable[[float, RicochetCraft], dict[str, Any]] | None = None
    sample_interval_s: float = 0.05


def _scenario_catalog() -> dict[str, ScenarioSpec]:
    return {
        '1_empty_static_flotation': ScenarioSpec(
            scenario_id='1_empty_static_flotation',
            title='Empty-payload static flotation (no passenger, zero thrust)',
            load_case='LC-01',
            spawn_xy=(0.0, 0.0),
            yaw_deg=0.0,
            duration_s=4.0,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0),
            command_fn=lambda t, c: {'throttle': 0.0, 'rudder_deg': 0.0, 'reverse_bucket': 0.0},
        ),
        '2_unoccupied_stowed_waves': ScenarioSpec(
            scenario_id='2_unoccupied_stowed_waves',
            title='Unoccupied stowed vehicle in directional waves (zero thrust)',
            load_case='LC-02',
            spawn_xy=(40.0, 0.0),
            yaw_deg=0.0,
            duration_s=5.0,
            water_config=WaterEnvironmentConfig(
                wave_mode='regular',
                wave_height_m=0.45,
                wave_period_s=3.8,
                wave_direction_deg=155.0,
                wind_speed_mps=4.0,
                wind_direction_deg=155.0,
            ),
            command_fn=lambda t, c: {'throttle': 0.0, 'rudder_deg': 0.0},
        ),
        '3_passenger_aboard_underway': ScenarioSpec(
            scenario_id='3_passenger_aboard_underway',
            title='Passenger aboard underway (LC-03 steady cruise)',
            load_case='LC-03',
            spawn_xy=(-300.0, 0.0),
            yaw_deg=0.0,
            duration_s=6.0,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=2.0),
            command_fn=lambda t, c: {'throttle': 0.55, 'rudder_deg': 0.0, 'elevator_deg': 0.0},
        ),
        '4_accel_decel': ScenarioSpec(
            scenario_id='4_accel_decel',
            title='Acceleration & reverse-bucket deceleration run',
            load_case='LC-03',
            spawn_xy=(-300.0, 0.0),
            yaw_deg=0.0,
            duration_s=7.0,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=1.5),
            command_fn=lambda t, c: (
                {'throttle': 0.85, 'reverse_bucket': 0.0}
                if t < 3.5
                else {'throttle': 0.55, 'reverse_bucket': 1.0}
            ),
        ),
        '5_turning_lateral_drift': ScenarioSpec(
            scenario_id='5_turning_lateral_drift',
            title='High-rate turning & lateral drift in turning basin',
            load_case='LC-03',
            spawn_xy=(350.0, 180.0),
            yaw_deg=0.0,
            duration_s=6.5,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=2.0),
            command_fn=lambda t, c: (
                {'throttle': 0.70, 'differential_thrust': 0.0, 'rudder_deg': 0.0}
                if t < 2.0
                else {'throttle': 0.70, 'differential_thrust': 0.65, 'rudder_deg': 25.0}
            ),
        ),
        '6_head_following_beam_waves': ScenarioSpec(
            scenario_id='6_head_following_beam_waves',
            title='Directional wave response (configurable heading vs wave angle)',
            load_case='LC-03',
            spawn_xy=(50.0, 0.0),
            yaw_deg=0.0,
            duration_s=5.0,
            water_config=WaterEnvironmentConfig(
                wave_mode='regular',
                wave_height_m=0.50,
                wave_period_s=3.5,
                wave_direction_deg=180.0,  # Head waves for yaw=0
                wind_speed_mps=5.0,
            ),
            command_fn=lambda t, c: {'throttle': 0.40, 'rudder_deg': 0.0},
        ),
        '7_shallow_water_operation': ScenarioSpec(
            scenario_id='7_shallow_water_operation',
            title='Shallow-water test shelf operation (-0.65 to -3.1 m depth)',
            load_case='LC-03',
            spawn_xy=(-360.0, 220.0),
            yaw_deg=0.0,
            duration_s=6.0,
            water_config=WaterEnvironmentConfig(
                wave_mode='regular',
                wave_height_m=0.25,
                wave_period_s=3.2,
                wave_direction_deg=180.0,
                wind_speed_mps=3.0,
            ),
            command_fn=lambda t, c: {'throttle': 0.50, 'rudder_deg': 0.0},
        ),
        '8_docking_and_ramp_recovery': ScenarioSpec(
            scenario_id='8_docking_and_ramp_recovery',
            title='Sheltered marina approach & 1:14 recovery ramp beaching',
            load_case='LC-03',
            spawn_xy=(-798.0, -110.0),  # 20 m east of ramp waterline (-818, -110) heading west (-X)
            yaw_deg=180.0,
            duration_s=9.0,
            water_config=WaterEnvironmentConfig(
                wave_mode='irregular',
                wave_height_m=0.25,
                wave_period_s=3.5,
                wave_direction_deg=180.0,
                wind_speed_mps=2.0,
            ),
            command_fn=lambda t, c: (
                {'throttle': 0.58, 'rudder_deg': 0.0, 'reverse_bucket': 0.0}
                if t < 6.8
                else {'throttle': 0.0, 'reverse_bucket': 0.0}
            ),
        ),
    }


SCENARIO_CATALOG = _scenario_catalog()


def run_ricochet_scenario(
    scenario_id: str,
    hull_variant: str = 'f03_baseline',
    water_override: WaterEnvironmentConfig | None = None,
    yaw_override_deg: float | None = None,
    seed: int = 41031,
    duration_override_s: float | None = None,
) -> dict[str, Any]:
    """Execute one Ricochet scenario and return self-contained reproducible evidence bundle."""
    if scenario_id not in SCENARIO_CATALOG:
        raise KeyError(f'Unknown scenario {scenario_id!r}. Available: {sorted(SCENARIO_CATALOG)}')

    spec = SCENARIO_CATALOG[scenario_id]
    world = RicochetLakeWorld(seed=seed)
    wcfg = water_override if water_override is not None else WaterEnvironmentConfig.from_dict({
        **spec.water_config.to_dict(),
        'wave_seed': seed,
    })

    craft = RicochetCraft(
        world=world,
        hull_variant=hull_variant,
        load_case=spec.load_case,
        water_config=wcfg,
    )
    yaw_0 = spec.yaw_deg if yaw_override_deg is None else float(yaw_override_deg)
    sx, sy = spec.spawn_xy
    craft.spawn(sx, sy, world.surface_z(sx, sy), yaw_deg=yaw_0)

    total_t = float(duration_override_s if duration_override_s is not None else spec.duration_s)
    steps = max(1, int(round(total_t / craft.DT)))
    sample_stride = max(1, int(round(spec.sample_interval_s / craft.DT)))

    records: list[dict[str, Any]] = []
    for k in range(steps + 1):
        t = k * craft.DT
        if k % sample_stride == 0 or k == steps:
            snap = craft.physical_snapshot()
            hydro = snap.get('hydrodynamics') or {}
            forces = hydro.get('forces_world_n') or {}
            torques = hydro.get('torques_world_nm') or {}
            records.append({
                't_s': snap['t_s'],
                'position_world_m': snap['position_world_m'],
                'attitude_xyz_deg': snap['attitude_xyz_deg'],
                'velocity_world_mps': snap['velocity_world_mps'],
                'velocity_body_mps': snap['velocity_body_mps'],
                'omega_world_rad_s': snap['omega_world_rad_s'],
                'submerged_volume_m3': hydro.get('submerged_volume_m3', 0.0),
                'waterline_z_world_m': hydro.get('waterline_z_world_m', 0.0),
                'draft_m': hydro.get('draft_m', 0.0),
                'freeboard_min_m': hydro.get('freeboard_min_m', 0.0),
                'wetted_area_m2': hydro.get('wetted_area_m2', 0.0),
                'forces_world_n': forces,
                'torques_world_nm': torques,
                'attachment_loads': snap.get('attachment_loads', {}),
                'contacts': snap.get('contacts', 0),
                'mean_water_depth_m': hydro.get('mean_water_depth_m', 0.0),
                'ground_clearance_m': hydro.get('ground_clearance_m', 0.0),
            })
        if k == steps:
            break
        if spec.command_fn is not None:
            craft.set_command(spec.command_fn(t, craft))
        craft.step()

    speeds = [float(np.linalg.norm(r['velocity_world_mps'])) for r in records]
    rolls = [abs(float(r['attitude_xyz_deg'][0])) for r in records]
    pitches = [abs(float(r['attitude_xyz_deg'][1])) for r in records]
    vols = [float(r['submerged_volume_m3']) for r in records]
    cons = craft.water_field.shallow.conservation_metrics()

    bundle = {
        'schema': 'vtx.ricochet.run_export.v1',
        'scenario_id': spec.scenario_id,
        'title': spec.title,
        'seed': int(seed),
        'world': {'environment_key': world.environment_key, 'seed': world.seed, 'datum': 'VTX-MLD-SI'},
        'water_config': wcfg.to_dict(),
        'provenance': craft.provenance,
        'mass_properties': craft.mass_properties(),
        'hull_summary': craft.hull_bundle.summary(),
        'water_conservation': cons,
        'summary': {
            'samples': len(records),
            'duration_s': records[-1]['t_s'],
            'peak_speed_mps': max(speeds) if speeds else 0.0,
            'final_speed_mps': speeds[-1] if speeds else 0.0,
            'max_abs_roll_deg': max(rolls) if rolls else 0.0,
            'max_abs_pitch_deg': max(pitches) if pitches else 0.0,
            'final_submerged_volume_m3': vols[-1] if vols else 0.0,
            'final_trim_deg': records[-1]['attitude_xyz_deg'][1] if records else 0.0,
            'final_freeboard_m': records[-1]['freeboard_min_m'] if records else 0.0,
            'final_position_m': records[-1]['position_world_m'] if records else [0, 0, 0],
            'max_contact_force_n': round(craft.max_impact_n, 3),
        },
        'telemetry': records,
    }
    return bundle
