"""Physical validation, numerical convergence, and operational test suite for Ricochet Lake & RicochetCraft."""

from __future__ import annotations

import math

import mujoco as mj
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from vtx.ricochet.hull_geometry import (
    CONCEPT_A_GLB,
    HullGeometryRegistry,
)
from vtx.ricochet.mass_register import axial_f03_to_vtx, polar_f03_to_vtx


def _make_closed_box_mesh(name: str, center: tuple[float, float, float], half_extents: tuple[float, float, float]) -> WatertightMesh:
    cx, cy, cz = center
    hx, hy, hz = half_extents
    verts = np.array([
        [cx - hx, cy - hy, cz - hz],
        [cx + hx, cy - hy, cz - hz],
        [cx + hx, cy + hy, cz - hz],
        [cx - hx, cy + hy, cz - hz],
        [cx - hx, cy - hy, cz + hz],
        [cx + hx, cy - hy, cz + hz],
        [cx + hx, cy + hy, cz + hz],
        [cx - hx, cy + hy, cz + hz],
    ], dtype=np.float64)
    faces = np.array([
        [0, 2, 1], [0, 3, 2],  # bottom (-Z)
        [4, 5, 6], [4, 6, 7],  # top (+Z)
        [0, 1, 5], [0, 5, 4],  # -Y
        [3, 7, 6], [3, 6, 2],  # +Y
        [0, 4, 7], [0, 7, 3],  # -X
        [1, 2, 6], [1, 6, 5],  # +X
    ], dtype=np.int32)
    return WatertightMesh(name=name, vertices=verts, faces=faces, source_id='test_box')
from vtx.ricochet.plant import DT, RicochetCraft
from vtx.ricochet.scenarios import SCENARIO_CATALOG, run_ricochet_scenario
from vtx.water.datum import G_SI, RHO_FRESHWATER_15C, VERTICAL_DATUM, WaterEnvironmentConfig
from vtx.water.hydrodynamics import (
    HullComponentMesh,
    WatertightMesh,
    evaluate_mesh_hydrodynamics,
)
from vtx.water.lake_world import RicochetLakeWorld
from vtx.water.open_water import OpenWaterWaveField, solve_dispersion_wavenumber
from vtx.water.shallow_water import HybridWaterField, ShallowWaterSolver


@pytest.fixture(scope='module')
def lake_world() -> RicochetLakeWorld:
    return RicochetLakeWorld(seed=41031)


def _step_craft(craft: RicochetCraft, seconds: float) -> None:
    steps = max(1, int(round(seconds / DT)))
    for _ in range(steps):
        craft.step()


def test_lake_world_geometry_datum_and_structures(lake_world: RicochetLakeWorld):
    assert lake_world.half_x == pytest.approx(1000.0)
    assert lake_world.half_y == pytest.approx(600.0)
    assert VERTICAL_DATUM['name'] == 'VTX-MLD-SI'
    assert VERTICAL_DATUM['units'] == 'm'

    # Deep central basin & graded shallow-water shelves
    assert lake_world.water_depth(40.0, 0.0) >= 10.0
    assert 0.4 <= lake_world.water_depth(-360.0, 220.0) <= 2.5
    assert lake_world.terrain_z(40.0, 0.0) <= -10.0
    assert lake_world.z_min <= -10.0
    assert lake_world.terrain_z(-920.0, 0.0) > 1.0  # Dry outer bank

    # Marina, finger piers, breakwater, quay, buoys, ramps, test zones present
    kinds = {s['kind'] for s in lake_world.structures}
    assert {'quay', 'pier', 'breakwater'} <= kinds
    assert len(lake_world.buoys) >= 6
    assert len(lake_world.ramps) >= 1
    zone_ids = {z['id'] for z in lake_world.zones}
    assert {'deep_basin', 'acceleration_lane', 'turning_basin', 'shallow_shelf', 'runup_beach', 'sheltered_marina'} <= zone_ids

    pub = lake_world.public()
    assert pub['environment'] == 'ricochet_lake'
    assert pub['nx'] == lake_world.nx and pub['ny'] == lake_world.ny


def test_archimedes_equilibrium_and_center_of_buoyancy_analytical(lake_world: RicochetLakeWorld):
    # Analytical box half-immersed at z = 0
    box = _make_closed_box_mesh('unit_barge', center=(0.0, 0.0, 0.0), half_extents=(2.0, 1.0, 0.5))
    assert box.is_watertight()
    assert box.gross_volume_m3 == pytest.approx(8.0, rel=1e-6)

    comp = HullComponentMesh(component_id='unit_barge', mesh=box)
    wf = HybridWaterField(lake_world, WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    eye = np.eye(3)
    zero = np.zeros(3)

    # Place at z = 0.0 in deep basin (x=40, y=0) -> exactly bottom half [-0.5, 0] submerged
    pos = np.array([40.0, 0.0, 0.0])
    bd = evaluate_mesh_hydrodynamics(
        comp, pos, eye, zero, zero, zero, zero, pos, wf, t=0.0
    )
    assert bd.submerged_volume_m3 == pytest.approx(4.0, rel=1e-4)
    assert bd.buoyancy_force_world[2] == pytest.approx(4.0 * RHO_FRESHWATER_15C * G_SI, rel=1e-3)
    # CoB of bottom half z in [-0.5, 0.0] is at z = -0.25 m
    assert bd.centre_of_buoyancy_world == pytest.approx([40.0, 0.0, -0.25], abs=1e-4)

    # Full 400 Hz coupled MuJoCo Archimedes settle for RicochetCraft (Concept A)
    craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-03',
                          water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    craft.spawn(40.0, 0.0, 0.0)
    _step_craft(craft, 5.5)
    snap = craft.physical_snapshot()
    weight_n = snap['mass_properties']['total_mass_kg'] * G_SI
    buoy_z = snap['hydrodynamics']['forces_world_n']['buoyancy'][2]
    assert buoy_z == pytest.approx(weight_n, rel=0.02)
    assert abs(snap['velocity_world_mps'][2]) < 0.05


def test_mass_cg_inertia_sensitivity_and_runtime_override(lake_world: RicochetLakeWorld):
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    c_light = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-01', water_config=cfg)
    c_light.spawn(40.0, 0.0, 0.0)
    _step_craft(c_light, 2.5)
    s_light = c_light.physical_snapshot()

    c_heavy = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-04', water_config=cfg)
    c_heavy.spawn(40.0, 0.0, 0.0)
    _step_craft(c_heavy, 2.5)
    s_heavy = c_heavy.physical_snapshot()

    # Heavier load case must displace more water volume & ride deeper
    assert s_heavy['mass_properties']['total_mass_kg'] > s_light['mass_properties']['total_mass_kg'] + 100.0
    assert s_heavy['hydrodynamics']['submerged_volume_m3'] > s_light['hydrodynamics']['submerged_volume_m3'] + 0.10
    assert s_heavy['hydrodynamics']['draft_m'] > s_light['hydrodynamics']['draft_m']

    # Forward CG shift (+0.45 m in +X bow direction) pitches bow down (+Y MuJoCo pitch rotation > 0)
    pitch_nominal = s_light['pitch_deg']
    mp = c_light.update_mass_properties(cg_shift_vtx_m=[0.45, 0.0, 0.0])
    assert mp['cg_vtx_m'][0] > c_light.mass_register.aggregate()['cg_vtx_m'][0] - 1e-6
    _step_craft(c_light, 2.0)
    assert c_light.physical_snapshot()['pitch_deg'] > pitch_nominal + 1.0


def test_static_roll_and_pitch_restoring_and_waterline_continuity(lake_world: RicochetLakeWorld):
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-03', water_config=cfg)
    craft.spawn(40.0, 0.0, 0.0)
    _step_craft(craft, 1.5)

    # Apply 10 deg roll (+X) disturbance directly to MuJoCo body orientation -> restoring torque must oppose
    q_roll = Rotation.from_euler('xyz', [10.0, 0.0, 0.0], degrees=True).as_quat()
    craft.data.qpos[3:7] = [q_roll[3], q_roll[0], q_roll[1], q_roll[2]]
    craft.data.qvel[:] = 0.0
    mj.mj_forward(craft.model, craft.data)
    craft._evaluate_and_cache_hydro(t=float(craft.data.time), force_eval=True)
    assert craft.last_hydro.buoyancy_torque_world[0] < -50.0  # Restores starboard-down roll back toward upright

    # Smooth wet/dry force sweep across waterline (no abrupt jump at z = 0)
    box = _make_closed_box_mesh('sweep_box', center=(0.0, 0.0, 0.5), half_extents=(1.5, 0.6, 0.5))
    comp = HullComponentMesh(component_id='sweep_box', mesh=box)
    wf = HybridWaterField(lake_world, cfg)
    eye, zero = np.eye(3), np.zeros(3)
    zs = np.linspace(0.08, -0.12, 41)
    bz = []
    for z in zs:
        p = np.array([40.0, 0.0, float(z)])
        bd = evaluate_mesh_hydrodynamics(comp, p, eye, zero, zero, zero, zero, p, wf, t=0.0)
        bz.append(bd.buoyancy_force_world[2])
    diffs = np.abs(np.diff(bz))
    # With step dz = 0.005 m across 1.5*2 * 0.6*2 = 3.6 m^2 plan area, theoretical dF = rho*g*A*dz ~ 176 N
    assert np.max(diffs) < 250.0
    assert bz[0] == pytest.approx(0.0, abs=1e-6)
    assert bz[-1] > 4000.0


def test_open_water_dispersion_and_seed_repeatability(lake_world: RicochetLakeWorld):
    # Linear dispersion check omega^2 = g k tanh(k h)
    T = 4.0
    omega = 2.0 * math.pi / T
    depth = 10.0
    k = solve_dispersion_wavenumber(omega, depth, g=G_SI)
    assert G_SI * k * math.tanh(k * depth) == pytest.approx(omega * omega, rel=1e-7)

    cfg = WaterEnvironmentConfig(
        wave_mode='irregular',
        wave_height_m=0.45,
        wave_period_s=3.8,
        wave_direction_deg=170.0,
        wave_seed=918273,
    )
    f1 = OpenWaterWaveField(cfg)
    f2 = OpenWaterWaveField(cfg)
    f3 = OpenWaterWaveField(WaterEnvironmentConfig(**{**cfg.to_dict(), 'wave_seed': 111222}))

    xs = np.linspace(-50.0, 50.0, 11)
    ys = np.zeros_like(xs)
    zs = np.full_like(xs, -0.5)
    s1 = f1.evaluate(xs, ys, zs, t=2.25)
    s2 = f2.evaluate(xs, ys, zs, t=2.25)
    s3 = f3.evaluate(xs, ys, zs, t=2.25)

    np.testing.assert_allclose(s1.eta, s2.eta, atol=0.0, rtol=0.0)
    np.testing.assert_allclose(s1.velocity, s2.velocity, atol=0.0, rtol=0.0)
    assert np.max(np.abs(s1.eta - s3.eta)) > 0.02

    # Craft repeatability on identical seed
    c1 = RicochetCraft(lake_world, hull_variant='concept_a', water_config=cfg)
    c2 = RicochetCraft(lake_world, hull_variant='concept_a', water_config=cfg)
    c1.spawn(40.0, 0.0, 0.0)
    c2.spawn(40.0, 0.0, 0.0)
    _step_craft(c1, 1.0)
    _step_craft(c2, 1.0)
    np.testing.assert_allclose(c1.data.qpos, c2.data.qpos, atol=1e-12)


def test_swe_c_property_wet_dry_stability_and_mass_conservation(lake_world: RicochetLakeWorld):
    # 1. Exact lake-at-rest C-property over variable bathymetry & banks (zero wind, zero current)
    cfg_calm = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0, current_speed_mps=0.0)
    swe = ShallowWaterSolver(lake_world, cfg_calm)
    for _ in range(100):
        swe.step(0.01)
    metrics_calm = swe.conservation_metrics()
    assert metrics_calm['relative_mass_error'] < 1e-12
    assert metrics_calm['max_speed_mps'] < 1e-10
    assert np.min(swe.h) >= 0.0

    # 2. Wind-driven shoreline run-up/retreat + water level shift + open-basin current
    cfg_wind = WaterEnvironmentConfig(
        water_level_m=0.20,
        wave_mode='irregular',
        wind_speed_mps=14.0,
        wind_direction_deg=25.0,
        current_speed_mps=0.6,
        current_direction_deg=10.0,
    )
    swe2 = ShallowWaterSolver(lake_world, cfg_wind)
    wet_before = swe2.conservation_metrics()['wet_cells']
    # Induce a local water surge near shallow western shelf & let run-up/retreat evolve
    mask = (np.abs(swe2.xs[None, :] + 730.0) < 40.0) & (np.abs(swe2.ys[:, None] + 110.0) < 40.0)
    swe2.h[mask] += 0.35
    swe2._expected_volume_m3 = float(np.sum(swe2.h) * swe2.cell_area)
    for _ in range(200):
        swe2.step(0.025)
    m2 = swe2.conservation_metrics()
    assert np.all(np.isfinite(swe2.h)) and np.min(swe2.h) >= 0.0
    assert m2['relative_mass_error'] < 1e-10
    assert m2['max_speed_mps'] < 5.0
    assert m2['wet_cells'] >= wet_before - 50


def test_mesh_resolution_and_timestep_convergence(lake_world: RicochetLakeWorld):
    wf = HybridWaterField(lake_world, WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    eye, zero = np.eye(3), np.zeros(3)
    pos = np.array([40.0, 0.0, -0.05])
    # Mesh resolution convergence on Concept A hull (subdivide 0 vs 1 vs 2)
    b0 = HullGeometryRegistry.build_variant('concept_a', subdivide_levels=0)
    b1 = HullGeometryRegistry.build_variant('concept_a', subdivide_levels=1)
    assert b0.main_hull.mesh.faces.shape[0] * 4 == b1.main_hull.mesh.faces.shape[0]

    h0 = evaluate_mesh_hydrodynamics(b0.main_hull, pos, eye, zero, zero, zero, zero, pos, wf, 0.0)
    h1 = evaluate_mesh_hydrodynamics(b1.main_hull, pos, eye, zero, zero, zero, zero, pos, wf, 0.0)
    rel_vol_diff = abs(h1.submerged_volume_m3 - h0.submerged_volume_m3) / max(h1.submerged_volume_m3, 1e-6)
    assert rel_vol_diff < 0.025

    # Timestep convergence: DT (400 Hz) vs sub-stepped 2*800 Hz trajectory on free heave drop
    c_coarse = RicochetCraft(lake_world, hull_variant='concept_a',
                             water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    c_fine = RicochetCraft(lake_world, hull_variant='concept_a',
                           water_config=WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    c_coarse.spawn(40.0, 0.0, 0.0)
    c_fine.spawn(40.0, 0.0, 0.0)
    c_coarse.data.qpos[2] += 0.25
    c_fine.data.qpos[2] += 0.25
    mj.mj_forward(c_coarse.model, c_coarse.data)
    mj.mj_forward(c_fine.model, c_fine.data)

    z_c, z_f = [], []
    # Run 0.5 s at 400 Hz vs halved MuJoCo model timestep (800 Hz)
    c_fine.model.opt.timestep = DT * 0.5
    for _ in range(200):
        c_coarse.step()
        z_c.append(float(c_coarse.data.qpos[2]))
        c_fine.step()
        c_fine.step()
        z_f.append(float(c_fine.data.qpos[2]))
    rms_z = float(np.sqrt(np.mean((np.array(z_c) - np.array(z_f)) ** 2)))
    assert rms_z < 0.03


def test_mujoco_mesh_pinning_coordinate_transform_and_f03_vs_concept_a(lake_world: RicochetLakeWorld):
    # Coordinate mapping check: F03 +Y Starboard -> VTX -Y Starboard, F03 -Y Port -> VTX +Y Port
    assert polar_f03_to_vtx([1.0, 3.8, 0.42]).tolist() == pytest.approx([1.0, -3.8, 0.42])
    assert polar_f03_to_vtx([1.0, -3.8, 0.42]).tolist() == pytest.approx([1.0, 3.8, 0.42])
    assert axial_f03_to_vtx([1.0, 2.0, 3.0]).tolist() == pytest.approx([-1.0, 2.0, -3.0])

    assert CONCEPT_A_GLB.is_file()
    cfg = WaterEnvironmentConfig(wave_mode='regular', wave_height_m=0.30, wave_period_s=3.5, wave_direction_deg=180.0)
    results = {}
    for variant in ('f03', 'concept_a'):
        craft = RicochetCraft(lake_world, hull_variant=variant, load_case='LC-03', water_config=cfg)
        pinned = craft.verify_pinned_geometry()
        for k, entry in pinned.items():
            assert entry['pinned'] is True, f'{variant} {k} failed MuJoCo pinning: {entry}'
            assert entry['bbox_max_err_m'] < 1e-4

        craft.spawn(40.0, 0.0, 0.0)
        pitches = []
        for _ in range(800):  # 2.0 s
            craft.step()
            pitches.append(craft.physical_snapshot()['pitch_deg'])
        snap = craft.physical_snapshot()
        results[variant] = {'snap': snap, 'pitch_std': float(np.std(pitches))}

    # Concept A GLB must enclose open cockpit tub + transparent glass canopy roof >= 1.54 m
    ca_bundle = HullGeometryRegistry.build_variant('concept_a')
    ca_mesh = ca_bundle.main_hull.mesh
    assert ca_mesh.is_watertight()
    assert ca_bundle.airframe_meshes['canopy_glass']['mesh'].bounds_max[2] >= 1.53

    # Both hulls float stably and yield distinct geometry-driven responses under identical loading & waves
    for variant, r in results.items():
        assert r['snap']['hydrodynamics']['submerged_volume_m3'] > 0.35
        assert np.isfinite(r['pitch_std'])
    assert results['f03']['snap']['hydrodynamics']['wetted_area_m2'] != pytest.approx(
        results['concept_a']['snap']['hydrodynamics']['wetted_area_m2'], abs=1e-2
    )


def test_published_planing_and_resistance_benchmark_trend(lake_world: RicochetLakeWorld):
    """Sanity check against Savitsky/Froude resistance & planing lift trend (real-time approximation, not CFD)."""
    bundle = HullGeometryRegistry.build_variant('concept_a')
    wf = HybridWaterField(lake_world, WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0))
    # Trim +4.0 deg bow-up (-Y pitch rotation in right-handed Z-up +X forward body axes)
    rot_trim = Rotation.from_euler('y', -4.0, degrees=True).as_matrix()
    pos = np.array([40.0, 0.0, -0.22])
    zero = np.zeros(3)

    drags = []
    lifts = []
    for speed in (4.0, 8.0, 12.0):
        bd = evaluate_mesh_hydrodynamics(
            bundle.main_hull,
            pos,
            rot_trim,
            np.array([speed, 0.0, 0.0]),
            zero,
            zero,
            zero,
            pos,
            wf,
            t=0.0,
        )
        drags.append(-float(bd.resistance_force_world[0]))
        lifts.append(float(bd.dynamic_lift_force_world[2]))

    # Drag opposes forward motion (+X) and dynamic lift is strictly positive & grows monotonically with speed^2
    assert drags[0] > 0.0 and drags[1] > drags[0] and drags[2] > drags[1]
    assert lifts[0] > 0.0 and lifts[1] > lifts[0] * 2.5 and lifts[2] > lifts[1] * 1.8


def test_all_eight_operational_ricochet_scenarios():
    catalog = SCENARIO_CATALOG
    assert len(catalog) == 8

    durations = {
        '1_empty_static_flotation': 2.0,
        '2_unoccupied_stowed_waves': 2.0,
        '3_passenger_aboard_underway': 2.5,
        '4_accel_decel': 5.0,
        '5_turning_lateral_drift': 3.5,
        '6_head_following_beam_waves': 2.0,
        '7_shallow_water_operation': 2.0,
        '8_docking_and_ramp_recovery': 11.5,
    }
    summaries = {}
    for sid in catalog:
        res = run_ricochet_scenario(sid, hull_variant='concept_a', duration_override_s=durations[sid])
        summaries[sid] = res
        telem = res['telemetry']
        assert len(telem) >= 10
        fin = telem[-1]
        assert all(np.isfinite(fin['position_world_m']))
        assert res['water_conservation']['relative_mass_error'] < 1e-10
        assert 'buoyancy' in fin['forces_world_n']
        assert 'sponson_port' in fin['attachment_loads']

    assert summaries['1_empty_static_flotation']['summary']['final_speed_mps'] < 0.25
    assert summaries['3_passenger_aboard_underway']['summary']['peak_speed_mps'] > 2.0
    assert summaries['4_accel_decel']['summary']['final_speed_mps'] < summaries['4_accel_decel']['summary']['peak_speed_mps']
    yaw_rates = [abs(math.degrees(r['omega_world_rad_s'][2])) for r in summaries['5_turning_lateral_drift']['telemetry']]
    assert max(yaw_rates) > 5.0
    assert summaries['7_shallow_water_operation']['telemetry'][-1]['mean_water_depth_m'] < 3.0
    assert summaries['8_docking_and_ramp_recovery']['summary']['max_contact_force_n'] > 100.0


def test_islands_whirlpool_fields_and_navigable_bypasses(lake_world: RicochetLakeWorld):
    assert len(lake_world.islands) == 3
    for isl in lake_world.islands:
        assert isl['z_peak_actual_m'] > 1.5
        assert isl['sign_title'] and len(isl['sign_lines']) >= 1
        moat_x = isl['x'] + isl['radius_m'] + 35.0
        assert lake_world.water_depth(moat_x, isl['y']) >= 1.5

    assert len(lake_world.whirlpools) == 2
    alpha, bravo = lake_world.whirlpools
    assert alpha['spin'] * bravo['spin'] == -1

    # Clear deep-water spawn has no active whirlpool hazard
    clear_hz = lake_world.whirlpool_hazard_at(40.0, 0.0)
    assert clear_hz['in_influence'] is False
    assert clear_hz['swirl_mps'] == 0.0

    # Near core throat of whirlpool_alpha exhibits strong orbital swirl, inward suction, and depression
    throat_hz = lake_world.whirlpool_hazard_at(alpha['x'] + alpha['r_core_m'], alpha['y'])
    assert throat_hz['in_influence'] is True
    assert throat_hz['in_core'] is True
    assert throat_hz['swirl_mps'] > 3.0
    assert throat_hz['suction_mps'] > 1.0
    assert throat_hz['funnel_drop_m'] < -0.5

    # Disabled whirlpools suppress both hazard metrics and free-surface funnel depression
    wf_on = HybridWaterField(lake_world, WaterEnvironmentConfig(wave_mode='still', whirlpools_enabled=True))
    wf_off = HybridWaterField(lake_world, WaterEnvironmentConfig(wave_mode='still', whirlpools_enabled=False))
    wx, wy = alpha['x'] + alpha['r_core_m'], alpha['y']
    s_on = wf_on.evaluate(wx, wy, t=0.0)
    s_off = wf_off.evaluate(wx, wy, t=0.0)
    assert float(s_on.eta) < -0.45
    assert abs(float(s_off.eta)) < 1e-6
    assert np.hypot(float(s_on.velocity[0]), float(s_on.velocity[1])) > 3.0
    assert np.hypot(float(s_off.velocity[0]), float(s_off.velocity[1])) < 1e-6


def test_dynamic_kelvin_wake_and_momentum_disturbance(lake_world: RicochetLakeWorld):
    wf = HybridWaterField(
        lake_world,
        WaterEnvironmentConfig(wave_mode='still', whirlpools_enabled=False, wake_enabled=True, current_speed_mps=0.0),
    )
    for step_idx in range(15):
        wf.apply_vessel_disturbance(
            x=40.0 + step_idx * 0.11,
            y=0.0,
            heading_rad=0.0,
            vx_world=11.0,
            vy_world=0.0,
            heave_rate_mps=0.0,
            draft_m=0.38,
            submerged_vol_m3=0.9,
            hydro_reaction_xy=(-1200.0, 0.0),
            fan_thrust_n=2800.0,
            dt=0.01,
            t_s=step_idx * 0.01,
        )
        wf.step(0.01)
    wake = wf.get_wake_state()
    assert wake['active'] is True
    assert wake['speed_mps'] == pytest.approx(11.0)

    # Kelvin diverging wake ripples appear astern inside the ~19.47 deg wedge
    astern_etas = [abs(float(wf.evaluate(41.5 - d, 0.35 * d, t=0.14).eta)) for d in (8.0, 14.0, 20.0)]
    assert max(astern_etas) > 5e-3
    assert wf.shallow.conservation_metrics()['relative_mass_error'] < 1e-10

    wf_muted = HybridWaterField(
        lake_world,
        WaterEnvironmentConfig(wave_mode='still', whirlpools_enabled=False, wake_enabled=False),
    )
    wf_muted.apply_vessel_disturbance(
        x=40.0,
        y=0.0,
        heading_rad=0.0,
        vx_world=11.0,
        vy_world=0.0,
        heave_rate_mps=0.0,
        draft_m=0.38,
        submerged_vol_m3=0.9,
        hydro_reaction_xy=(-1200.0, 0.0),
        fan_thrust_n=2800.0,
        dt=0.01,
        t_s=0.14,
    )
    assert abs(float(wf_muted.evaluate(32.0, 2.8, t=0.14).eta)) < 1e-8


def test_waterproof_flotation_breached_sinking_bilge_recovery_and_ballast_trim(lake_world: RicochetLakeWorld):
    craft = RicochetCraft(world=lake_world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-03')
    sponson_items = [c for c in craft.mass_register.active_items() if 'sponson' in c.component_id]
    assert sponson_items and all(c.cg_f03_m[2] == pytest.approx(0.48) for c in sponson_items)

    # 1. Sealed waterproof craft floats with positive reserve buoyancy
    craft.spawn(40.0, 0.0, 0.0)
    _step_craft(craft, 0.5)
    mp_sealed = craft.mass_properties()
    z_sealed = float(craft.data.xpos[craft.bids['airframe'], 2])
    assert mp_sealed['waterproof'] is True
    assert mp_sealed['flood_water_kg'] == pytest.approx(0.0)
    assert mp_sealed['reserve_buoyancy_kg'] > 1500.0
    assert craft.last_hydro is not None and craft.last_hydro.freeboard_min_m > 0.0
    assert z_sealed > -0.80

    # 2. Unsealing hull causes Torricelli bilge ingress while floating in water
    craft.update_mass_properties(waterproof=False)
    _step_craft(craft, 0.5)
    mp_breach = craft.mass_properties()
    assert mp_breach['waterproof'] is False
    assert mp_breach['flood_water_kg'] > 50.0

    # 3. Heavy flooded bilge exceeds max buoyancy -> negative reserve buoyancy & hull sinks below waterline
    craft.update_mass_properties(waterproof=False, flood_water_kg=2250.0)
    _step_craft(craft, 1.0)
    mp_swamped = craft.mass_properties()
    z_swamped = float(craft.data.xpos[craft.bids['airframe'], 2])
    assert mp_swamped['reserve_buoyancy_kg'] < 0.0
    assert z_swamped < z_sealed - 0.15

    # 4. Re-sealing + activating bilge pump drains water & restores positive buoyancy / floatation
    craft.update_mass_properties(waterproof=True, bilge_pump=True)
    _step_craft(craft, 0.8)
    mp_rescued = craft.mass_properties()
    z_rescued = float(craft.data.xpos[craft.bids['airframe'], 2])
    assert mp_rescued['flood_water_kg'] == pytest.approx(0.0)
    assert mp_rescued['reserve_buoyancy_kg'] > 1500.0
    assert z_rescued > z_swamped + 0.10

    # 5. Trim ballast longitudinal shift tilts pitch angle predictably (+X forward -> negative/+Y pitch-down in X-fwd Z-up)
    craft.spawn(40.0, 0.0, 0.0)
    craft.update_mass_properties(ballast_mass_kg=180.0, ballast_x_m=1.4)
    _step_craft(craft, 0.5)
    pitch_fwd = Rotation.from_quat(craft.data.xquat[craft.bids['airframe']][[1, 2, 3, 0]]).as_euler('xyz', degrees=True)[1]

    craft.spawn(40.0, 0.0, 0.0)
    craft.update_mass_properties(ballast_mass_kg=180.0, ballast_x_m=-1.4)
    _step_craft(craft, 0.5)
    pitch_aft = Rotation.from_quat(craft.data.xquat[craft.bids['airframe']][[1, 2, 3, 0]]).as_euler('xyz', degrees=True)[1]
    assert pitch_fwd > pitch_aft + 0.8

