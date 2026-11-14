"""Component-by-component specification, structural rigidity, stability, drag, and paint tests for Concept A Pass 3."""

from __future__ import annotations

import json
import math
import struct

import mujoco as mj
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from vtx.ricochet.hull_geometry import CONCEPT_A_GLB, HullGeometryRegistry
from vtx.ricochet.mass_register import MassPropertiesRegister
from vtx.ricochet.plant import RicochetCraft
from vtx.ricochet.spec_math import (
    COMPONENT_RIGIDITY_SPECS,
    RC01_DESIGN_DRAFT_M,
    RC01_DESIGN_MASS_KG,
    RC01_MAX_STUDY_MASS_KG,
    canopy_and_craft_cd0,
    evaluate_mesh_curve_stability,
)
from vtx.water.datum import G_SI, WaterEnvironmentConfig
from vtx.water.lake_world import RicochetLakeWorld


@pytest.fixture(scope='module')
def lake_world() -> RicochetLakeWorld:
    return RicochetLakeWorld()


def _step_seconds(craft: RicochetCraft, seconds: float) -> None:
    n_steps = int(round(seconds / craft.DT))
    for _ in range(n_steps):
        craft.step()


def test_all_19_glb_nodes_strict_directed_2manifold_and_duct_clearance():
    bundle = HullGeometryRegistry.build_variant('concept_a')
    assert bundle.variant_id == 'concept_a'
    assert len(bundle.airframe_meshes) == 16  # + main_hull + 2 sponsons = 19 total nodes

    all_meshes = [
        bundle.main_hull.mesh,
        bundle.port_sponson.mesh,
        bundle.stbd_sponson.mesh,
        *[spec['mesh'] for spec in bundle.airframe_meshes.values()],
    ]
    assert len(all_meshes) == 19
    for wmesh in all_meshes:
        assert wmesh.is_watertight(), f'{wmesh.name} failed strict directed 2-manifold check'
        assert wmesh.gross_volume_m3 > 0.0, f'{wmesh.name} has non-positive volume'
        assert float(np.min(wmesh.face_areas_m2)) > 1e-10, f'{wmesh.name} has degenerate triangles'

    # Watertight main hull enclosed volume >= 1.8 m^3 RC-01 baseline margin
    assert bundle.main_hull.mesh.gross_volume_m3 >= 1.80

    # Tail pylon horizontal cross-arm must anchor into shroud barrel wall without invading O0.90m duct throat (y_inner = 0.33 m)
    tail_verts = bundle.airframe_meshes['tail_pylon_t_tail']['mesh'].vertices
    arm_pts = tail_verts[(np.abs(tail_verts[:, 1]) > 0.12) & (tail_verts[:, 2] < 1.80)]
    assert len(arm_pts) > 0
    assert float(np.max(np.abs(arm_pts[:, 1]))) < 0.325  # well shy of y = +/-0.330m inner airflow throat!

    duct_port_verts = bundle.airframe_meshes['duct_port']['mesh'].vertices
    assert float(np.min(duct_port_verts[:, 1])) < 0.275  # outer shroud barrel overlaps cleanly inside 0.288 m arm span


def test_aerodynamic_curved_canopy_and_nose_tip_drag_reduction(lake_world: RicochetLakeWorld):
    bundle = HullGeometryRegistry.build_variant('concept_a')
    canopy = bundle.airframe_meshes['canopy_glass']['mesh']
    assert canopy.bounds_max[2] >= 1.53
    assert (canopy.bounds_max[0] - canopy.bounds_min[0]) >= 2.50

    # Compound-curved teardrop windshield (x in [1.90, 2.75]) slopes gradually rather than vertical brick wall
    vv = getattr(canopy, '_visual_vertices', canopy.vertices)
    vn = getattr(canopy, '_visual_normals', None)
    assert vn is not None
    rake_zone = (vv[:, 0] >= 1.90) & (vv[:, 0] <= 2.75) & (vv[:, 2] >= 0.90)
    assert np.sum(rake_zone) > 20
    assert float(np.median(np.abs(vn[rake_zone, 0]))) < 0.72

    # Quantitative Hoerner / streamlined-body parasitic Cd0 improvement over flat boxy windshield
    blocky = canopy_and_craft_cd0(windshield_rake_deg=82.0, canopy_fineness_ratio=2.2)
    sleek = canopy_and_craft_cd0(windshield_rake_deg=24.0, canopy_fineness_ratio=4.0)
    assert blocky['cd_canopy_local'] > 0.40
    assert sleek['cd_canopy_local'] < 0.14
    assert blocky['cd_canopy_local'] / sleek['cd_canopy_local'] > 3.5
    assert (blocky['cd0_total'] - sleek['cd0_total']) / blocky['cd0_total'] > 0.20

    # Live plant aerodynamic force check at 28 m/s cruise speed: Concept A drag strictly below blocky baseline
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    drags = {}
    for hv in ('f03_baseline', 'concept_a'):
        c = RicochetCraft(lake_world, hull_variant=hv, load_case='LC-03', water_config=cfg)
        c.spawn(40.0, 0.0, 2.0)  # clear of water so pure aero forces are measured
        c.data.qvel[0] = 28.0
        mj.mj_forward(c.model, c.data)
        c._evaluate_and_cache_hydro(t=0.0, force_eval=True)
        f_aero, _ = c._compute_aero_and_propulsion()
        drags[hv] = -float(f_aero[0])
    assert drags['concept_a'] < drags['f03_baseline'] * 0.80


def test_crisp_seam_split_paint_and_explicit_normals(lake_world: RicochetLakeWorld):
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-03', water_config=cfg)
    vg = craft.visual_geometry()
    assert len(vg['meshes']) == 19
    assert vg['boxes'] == []
    assert all(m['pinned'] is True for m in vg['meshes'])

    main_hull_vis = next(m for m in vg['meshes'] if m['name'] == 'main_hull')
    assert 'normals' in main_hull_vis
    assert len(main_hull_vis['normals']) == len(main_hull_vis['vertices'])
    assert 'vertex_colors' in main_hull_vis

    # Every painted vertex color must be unblurred solid palette RGB (zero intermediate gradient smear)
    vc = np.asarray(main_hull_vis['vertex_colors'], dtype=np.float32).reshape(-1, 3)
    palette = np.array([
        [0.045, 0.052, 0.068],  # Satin carbon
        [0.025, 0.028, 0.036],  # Matte cockpit tub
        [0.910, 0.460, 0.012],  # VTX Racing Gold stripe & bow emblem
    ], dtype=np.float32)
    max_dev = float(np.max(np.min(np.linalg.norm(vc[:, None, :] - palette[None, :, :], axis=2), axis=1)))
    assert max_dev < 0.005

    # Verify GLB itself stores multi-primitive materials + COLOR_0 + NORMAL
    raw = CONCEPT_A_GLB.read_bytes()
    off = 12
    gltf = {}
    while off < len(raw):
        clen, ctype = struct.unpack('<II', raw[off:off + 8])
        if ctype == 0x4E4F534A:
            gltf = json.loads(raw[off + 8:off + 8 + clen].decode('utf-8'))
            break
        off += 8 + clen
    hull_node = next(n for n in gltf['nodes'] if n.get('name') == 'Ricochet_ConceptA_Hull_Cabin')
    prims = gltf['meshes'][hull_node['mesh']]['primitives']
    assert len(prims) >= 3  # carbon + gold + cockpit tub separate PBR primitives
    assert all('NORMAL' in p['attributes'] and 'COLOR_0' in p['attributes'] for p in prims)


def test_component_spec_rigidity_solid_rock_vs_elastic_flexure(lake_world: RicochetLakeWorld):
    specs = COMPONENT_RIGIDITY_SPECS

    # Solid floating rock components: rigid primary hull & aft empennage
    hull = specs['hull_girder']
    assert hull.is_rigid_primary is True
    assert hull.stiffness_n_per_m >= 3.0e7
    assert hull.first_mode_hz >= 35.0
    assert hull.max_elastic_deflection_m < 0.0015
    assert hull.safety_factor >= 10.0

    pylon = specs['tail_pylon_t_tail']
    duct = specs['duct_shroud_and_arm']
    canopy = specs['canopy_dome']
    for rigid_comp in (pylon, duct, canopy):
        assert rigid_comp.is_rigid_primary is True
        assert rigid_comp.first_mode_hz >= 18.0
        assert rigid_comp.safety_factor >= 3.0

    # Compliant bending components where materials allow: CFRP main wing & Ti+CFRP sponson strut assembly
    wing = specs['main_wing']
    assert wing.is_rigid_primary is False
    assert 3.5 <= wing.first_mode_hz <= 15.0
    assert 0.02 <= wing.max_elastic_deflection_m <= 0.15
    assert wing.safety_factor >= 2.0

    sponson = specs['sponson_strut_assembly']
    assert sponson.is_rigid_primary is False
    assert 3.5 <= sponson.first_mode_hz <= 10.0
    assert sponson.safety_factor >= 3.0

    # Live MuJoCo sponson flex telemetry across load cases: must flex smoothly in water and scale with load
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    flex_by_lc = {}
    for lc in ('LC-01', 'LC-03', 'LC-04'):
        craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case=lc, water_config=cfg)
        craft.spawn(40.0, 0.0, 0.0)
        _step_seconds(craft, 2.5)
        qp, _ = craft.joint('sponson_port_flex_z')
        qs, _ = craft.joint('sponson_stbd_flex_z')
        snap = craft.physical_snapshot()
        assert 'structural_rigidity' in snap
        assert snap['structural_rigidity']['hull_girder']['deflection_m'] < 0.0015
        assert snap['structural_rigidity']['sponson_strut_assembly']['utilization'] < 0.5
        assert 0.005 <= qp <= 0.030 and 0.005 <= qs <= 0.030
        flex_by_lc[lc] = 0.5 * (qp + qs)

    assert flex_by_lc['LC-04'] > flex_by_lc['LC-03'] > flex_by_lc['LC-01']


def test_hydrostatic_draft_envelope_and_side_stabiliser_immersion_across_load_cases(lake_world: RicochetLakeWorld):
    bundle = HullGeometryRegistry.build_variant('concept_a')
    mr = MassPropertiesRegister.for_load_case('LC-03')
    cg_z = float(mr.aggregate()['cg_vtx_m'][2])

    h900 = evaluate_mesh_curve_stability(
        bundle.main_hull.mesh.vertices,
        bundle.main_hull.mesh.faces,
        bundle.port_sponson.mesh.vertices,
        bundle.port_sponson.mesh.faces,
        sponson_mount_z_m=0.48,
        mass_kg=RC01_DESIGN_MASS_KG,
        cg_z_m=cg_z,
    )
    h1050 = evaluate_mesh_curve_stability(
        bundle.main_hull.mesh.vertices,
        bundle.main_hull.mesh.faces,
        bundle.port_sponson.mesh.vertices,
        bundle.port_sponson.mesh.faces,
        sponson_mount_z_m=0.48,
        mass_kg=RC01_MAX_STUDY_MASS_KG,
        cg_z_m=cg_z,
    )
    assert RC01_DESIGN_DRAFT_M - 0.015 <= h900['draft_m'] <= RC01_DESIGN_DRAFT_M + 0.015
    assert 0.35 <= h900['gm_hull_only_m'] <= 0.55
    assert h900['gm_total_m'] >= 10.0
    assert h900['sponson_immersion_m'] >= 0.15
    assert h1050['draft_m'] > h900['draft_m'] + 0.015

    # Coupled 400 Hz MuJoCo Archimedes settle across LC-01, LC-03, LC-04
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    drafts = {}
    for lc in ('LC-01', 'LC-03', 'LC-04'):
        craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case=lc, water_config=cfg)
        craft.spawn(40.0, 0.0, 0.0)
        _step_seconds(craft, 3.0)
        snap = craft.physical_snapshot()
        hydro = snap['hydrodynamics']
        weight_n = snap['mass_properties']['total_mass_kg'] * G_SI
        buoy_n = hydro['forces_world_n']['buoyancy'][2]
        am_z_n = abs(hydro['forces_world_n']['added_mass'][2])

        # Coupled 3-body added mass keeps rest equilibrium within 1% Archimedes exactness
        assert buoy_n == pytest.approx(weight_n, rel=0.01)
        assert am_z_n < 30.0
        assert abs(snap['pitch_deg']) < 1.5
        assert abs(snap['roll_deg']) < 0.25

        # Both side stabilisers must be submerged in water carrying substantial buoyancy (never in the air)
        comp = hydro['component_loads']
        assert comp['sponson_port']['buoyancy_z_n'] >= 550.0
        assert comp['sponson_stbd']['buoyancy_z_n'] >= 550.0
        drafts[lc] = hydro['draft_m']

    assert 0.54 <= drafts['LC-03'] <= 0.59
    assert drafts['LC-04'] > drafts['LC-03'] > drafts['LC-01']


def test_dynamic_roll_restoring_with_immersed_sponsons_and_full_throttle_pitch_stability(lake_world: RicochetLakeWorld):
    cfg = WaterEnvironmentConfig(wave_mode='still', wind_speed_mps=0.0)
    craft = RicochetCraft(lake_world, hull_variant='concept_a', load_case='LC-03', water_config=cfg)
    craft.spawn(40.0, 0.0, 0.0)
    _step_seconds(craft, 1.5)

    # 1. Inject +10 deg starboard-down roll perturbation directly and verify damped oscillatory recovery
    q_roll = Rotation.from_euler('xyz', [10.0, 0.0, 0.0], degrees=True).as_quat()
    craft.data.qpos[3:7] = [q_roll[3], q_roll[0], q_roll[1], q_roll[2]]
    craft.data.qvel[:] = 0.0
    mj.mj_forward(craft.model, craft.data)
    craft._evaluate_and_cache_hydro(t=float(craft.data.time), force_eval=True)
    assert craft.last_hydro.buoyancy_torque_world[0] < -2000.0

    roll_trace = []
    for _ in range(int(round(5.0 / craft.DT))):
        craft.step()
        roll_trace.append(craft.physical_snapshot()['roll_deg'])
    # Logarithmic roll decay: peak overshoot after first zero crossing < 8.5 deg, late envelope < 4.5 deg (no capsize)
    first_cross = next((i for i, r in enumerate(roll_trace) if r <= 0.0), 0)
    assert first_cross > 10 and first_cross < 500
    assert max(abs(r) for r in roll_trace[first_cross:600]) < 8.6
    assert max(abs(r) for r in roll_trace[-400:]) < 4.5
    assert not craft.physical_snapshot()['crashed']

    # 2. Full bollard forward throttle (2900 N aft pylon thrust) must accelerate cleanly without bow-dive capsize
    craft.set_command({'throttle': 1.0, 'elevator_deg': 0.0})
    _step_seconds(craft, 3.5)
    snap_surge = craft.physical_snapshot()
    assert snap_surge['velocity_body_mps'][0] > 4.0
    assert abs(snap_surge['pitch_deg']) < 4.5
    assert snap_surge['hydrodynamics']['submerged_volume_m3'] > 0.5
    assert not snap_surge['crashed']
