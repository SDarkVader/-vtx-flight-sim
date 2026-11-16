"""Repeatable Ricochet RC-01 physical water test scenarios on RicochetLakeWorld.

All 8 operational scenarios execute full 400 Hz MuJoCo rigid-body integration
coupled with HybridWaterField and geometry-resolved hydrodynamics, recording
6-DOF motion, displaced volume, waterline, trim, freeboard, wetted area,
itemized force/moment channels, and MuJoCo sponson attachment loads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from vtx.ricochet.mass_register import (
    DEFAULT_REGISTER_VERSION,
    PROPULSION_INSTALLATION_SPECS,
    PROPULSION_INSTALLATIONS,
    MassPropertiesRegister,
    compare_propulsion_installations,
)
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
    register_version: str = DEFAULT_REGISTER_VERSION
    fuel_state: str | None = 'dry'
    propulsion_installation: str | None = None
    propulsion_off: bool = False
    notes: str = ''


LC04_PROPULSION_SUBCASES: dict[str, dict[str, Any]] = {
    inst: dict(PROPULSION_INSTALLATION_SPECS[inst], load_case='LC-04', propulsion_installation=inst)
    for inst in PROPULSION_INSTALLATIONS
}


def _scenario_catalog() -> dict[str, ScenarioSpec]:
    return {
        '1_empty_static_flotation': ScenarioSpec(
            scenario_id='1_empty_static_flotation',
            title='Empty-payload static flotation without passenger (LC-03, zero thrust)',
            load_case='LC-03',
            spawn_xy=(0.0, 0.0),
            yaw_deg=0.0,
            duration_s=4.0,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0),
            command_fn=lambda t, c: {'throttle': 0.0, 'rudder_deg': 0.0, 'reverse_bucket': 0.0},
            fuel_state='dry',
            notes='LC-03 empty-payload flotation without passenger; supports declared fuel states',
        ),
        '2_unoccupied_stowed_waves': ScenarioSpec(
            scenario_id='2_unoccupied_stowed_waves',
            title='Unoccupied stowed vehicle in directional waves (LC-02, propulsion off)',
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
            command_fn=lambda t, c: {
                'throttle': 0.0,
                'differential_thrust': 0.0,
                'rudder_deg': 0.0,
                'elevator_deg': 0.0,
                'aileron_deg': 0.0,
                'reverse_bucket': 0.0,
            },
            propulsion_off=True,
            notes='LC-02 unoccupied and stowed, propulsion off/stowed, motion caused solely by water',
        ),
        '3_passenger_aboard_underway': ScenarioSpec(
            scenario_id='3_passenger_aboard_underway',
            title='Passenger aboard underway (LC-01 steady cruise)',
            load_case='LC-01',
            spawn_xy=(-300.0, 0.0),
            yaw_deg=0.0,
            duration_s=6.0,
            water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=2.0),
            command_fn=lambda t, c: {'throttle': 0.55, 'rudder_deg': 0.0, 'elevator_deg': 0.0},
        ),
        '4_accel_decel': ScenarioSpec(
            scenario_id='4_accel_decel',
            title='Acceleration & reverse-bucket deceleration run (LC-01)',
            load_case='LC-01',
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
            title='High-rate turning & lateral drift in turning basin (LC-01)',
            load_case='LC-01',
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
            title='Directional wave response (LC-01 configurable heading vs wave angle)',
            load_case='LC-01',
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
            title='Shallow-water test shelf operation (LC-01, -0.65 to -3.1 m depth)',
            load_case='LC-01',
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
            title='Sheltered marina approach & 1:14 recovery ramp beaching (LC-01)',
            load_case='LC-01',
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


def _configure_craft_register(
    craft: RicochetCraft,
    load_case: str,
    register_version: str,
    fuel_state: str | None = None,
    fuel_mass_kg: float | None = None,
    propulsion_installation: str | None = None,
    propulsion_off: bool | None = None,
) -> None:
    """Apply explicit loading-contract fields onto craft.mass_register and MuJoCo."""
    sponson_z = 0.48 if craft.hull_bundle.variant_id == 'concept_a' else 0.42
    craft.mass_register = MassPropertiesRegister.for_load_case(
        load_case=load_case,
        sponson_z_m=sponson_z,
        register_version=register_version,
        fuel_state=fuel_state,
        fuel_mass_kg=fuel_mass_kg,
        propulsion_installation=propulsion_installation,  # type: ignore[arg-type]
        propulsion_off=propulsion_off,
    )
    craft._apply_mass_to_mujoco()


def run_ricochet_scenario(
    scenario_id: str,
    hull_variant: str = 'f03_baseline',
    water_override: WaterEnvironmentConfig | None = None,
    yaw_override_deg: float | None = None,
    seed: int = 41031,
    duration_override_s: float | None = None,
    load_case_override: str | None = None,
    register_version: str | None = None,
    fuel_state: str | None = None,
    fuel_mass_kg: float | None = None,
    propulsion_installation: str | None = None,
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

    lc = load_case_override or spec.load_case
    ver = register_version or spec.register_version
    f_state = spec.fuel_state if fuel_state is None else fuel_state
    p_inst = spec.propulsion_installation if propulsion_installation is None else propulsion_installation

    craft = RicochetCraft(
        world=world,
        hull_variant=hull_variant,
        load_case=lc,
        water_config=wcfg,
    )
    if (
        ver != craft.mass_register.register_version
        or f_state != craft.mass_register.fuel_state
        or fuel_mass_kg is not None
        or (p_inst is not None and p_inst != craft.mass_register.propulsion_installation)
        or spec.propulsion_off != craft.mass_register.propulsion_off
    ):
        _configure_craft_register(
            craft,
            load_case=lc,
            register_version=ver,
            fuel_state=f_state,
            fuel_mass_kg=fuel_mass_kg,
            propulsion_installation=p_inst,
            propulsion_off=spec.propulsion_off if load_case_override is None else None,
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
        if spec.command_fn is not None and not craft.mass_register.propulsion_off:
            craft.set_command(spec.command_fn(t, craft))
        elif craft.mass_register.propulsion_off:
            craft.set_command({'throttle': 0.0, 'differential_thrust': 0.0})
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
        'load_case': craft.mass_register.load_case,
        'register_version': craft.mass_register.register_version,
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
            'load_case': craft.mass_register.load_case,
            'register_version': craft.mass_register.register_version,
            'propulsion_off': craft.mass_register.propulsion_off,
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


def run_propulsion_installation_comparison(
    hull_variant: str = 'concept_a',
    passenger_aboard: bool = True,
    fuel_state: str | None = 'dry',
    fuel_mass_kg: float | None = None,
    water_config: WaterEnvironmentConfig | None = None,
    duration_s: float = 3.0,
    seed: int = 41031,
    spawn_xy: tuple[float, float] = (40.0, 0.0),
    simulate: bool = True,
) -> dict[str, Any]:
    """Run LC-04 side-by-side comparison across the three mutually exclusive F02 installations.

    Compares ``baseline_pack``, ``fuel_cell_paired``, and ``energy_pack_alternate`` on exact
    mass/CG/3x3-inertia shifts and (when ``simulate=True``) coupled 400 Hz hydrostatic/motion
    trim equilibrium on ``RicochetLakeWorld``.
    """
    sponson_z = 0.48 if str(hull_variant).strip().lower().startswith('concept_a') else 0.42
    analytic = compare_propulsion_installations(
        load_case='LC-04',
        passenger_aboard=passenger_aboard,
        sponson_z_m=sponson_z,
        fuel_state=fuel_state,
        fuel_mass_kg=fuel_mass_kg,
    )
    if not simulate:
        return {
            'schema': 'vtx.ricochet.lc04_comparison.v1',
            'simulated': False,
            **analytic,
        }

    world = RicochetLakeWorld(seed=seed)
    wcfg = water_config or WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0, wave_seed=seed)
    steps = max(1, int(round(float(duration_s) / 0.0025)))
    sx, sy = spawn_xy
    sim_results: dict[str, dict[str, Any]] = {}

    for inst in PROPULSION_INSTALLATIONS:
        inst_entry = analytic['installations'][inst]
        craft = RicochetCraft(
            world=world,
            hull_variant=hull_variant,
            load_case='LC-04',
            water_config=wcfg,
        )
        craft.mass_register = MassPropertiesRegister.for_load_case(
            load_case='LC-04',
            passenger_aboard=passenger_aboard,
            sponson_z_m=sponson_z,
            fuel_state=inst_entry['fuel_state'],
            fuel_mass_kg=inst_entry['fuel_mass_kg'],
            propulsion_installation=inst,
        )
        craft._apply_mass_to_mujoco()
        craft.spawn(sx, sy, world.surface_z(sx, sy), yaw_deg=0.0)
        for _ in range(steps):
            craft.step()
        snap = craft.physical_snapshot()
        hydro = snap.get('hydrodynamics') or {}
        sim_results[inst] = {
            'subcase_id': inst_entry['subcase_id'],
            'total_mass_kg': snap['mass_properties']['total_mass_kg'],
            'cg_f03_m': snap['mass_properties']['cg_f03_m'],
            'inertia_diag_vtx_kg_m2': snap['mass_properties']['inertia_diag_vtx_kg_m2'],
            'draft_m': hydro.get('draft_m', 0.0),
            'submerged_volume_m3': hydro.get('submerged_volume_m3', 0.0),
            'freeboard_min_m': hydro.get('freeboard_min_m', 0.0),
            'pitch_deg': snap.get('pitch_deg', 0.0),
            'roll_deg': snap.get('roll_deg', 0.0),
            'attachment_loads': snap.get('attachment_loads', {}),
            'status': 'provisional_unverified',
        }

    return {
        'schema': 'vtx.ricochet.lc04_comparison.v1',
        'simulated': True,
        'hull_variant': hull_variant,
        'duration_s': float(duration_s),
        **analytic,
        'simulation': sim_results,
    }
