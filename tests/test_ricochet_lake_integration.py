"""End-to-end server API, schema, checkpoint restoration, and regression integration tests for Ricochet Lake."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
from fastapi import HTTPException

import vtx.live_server as live_server
from vtx.live_server import Action, Laboratory, Mission, mission_dump, parse_action
from vtx.phantom.controls import PhantomAction
from vtx.ricochet.mass_register import DEFAULT_REGISTER_VERSION, LEGACY_REGISTER_VERSION
from vtx.ricochet.plant import RicochetCraft
from vtx.water.lake_world import RicochetLakeWorld


def test_ricochet_server_routes_controls_mission_and_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)

    # 1. Switch to ricochet_lake with Concept A
    env_res = asyncio.run(live_server.set_environment({
        'environment': 'ricochet_lake',
        'airframe_variant': 'ricochet-concept-a',
    }))
    assert env_res['ok'] is True
    assert env_res['world']['environment'] == 'ricochet_lake'
    assert env_res['view']['environment']['key'] == 'ricochet_lake'
    assert env_res['view']['rendering_truth']['ricochet'] is True
    assert 'water_frame' in env_res['view']
    assert len(env_res['view']['water_frame']['elevation_m']) == 25
    assert env_res['view']['observation']['water_config']['wave_mode'] == 'irregular'
    assert env_res['view']['observation']['water_config']['wave_height_m'] > 0.0
    lp = env_res['view']['water_frame'].get('local_patch')
    assert lp is not None and lp['nx'] == 65 and lp['ny'] == 65
    assert len(lp['elevation_m']) == 65 and len(lp['u_mps']) == 65 and len(lp['v_mps']) == 65

    # 2. Pinned geometry endpoint matches Concept A SHA-256 and supports ?variant=
    model_payload = asyncio.run(live_server.get_water_model())
    assert model_payload['hull_variant'] == 'concept_a'
    assert model_payload['geometry_sha256'] == env_res['view']['observation']['configuration']['hull_geometry_sha256']
    assert len(model_payload['meshes']) == 25
    assert all(m.get('pinned') is True for m in model_payload['meshes'])
    assert model_payload['boxes'] == []
    f03_model = asyncio.run(live_server.get_water_model(variant='ricochet-rc01-f03'))
    assert f03_model['hull_variant'] == 'f03_baseline'
    assert len(f03_model['boxes']) >= 14
    with pytest.raises(HTTPException) as bad_var_exc:
        asyncio.run(live_server.get_water_model(variant='not-a-ricochet-hull'))
    assert bad_var_exc.value.status_code == 422
    truth = env_res['view']['rendering_truth']
    for key in ('cg_body_m', 'cb_body_m', 'cn_yaw', 'cn_beta_per_rad', 'munk_moment_nm', 'fan_rpm', 'aero', 'mass', 'propulsors'):
        assert key in truth

    # 3. Update wave, wind, current & water level live
    cfg_res = asyncio.run(live_server.update_water_config({
        'water_level_m': 0.35,
        'wave_mode': 'irregular',
        'wave_height_m': 0.55,
        'wave_period_s': 4.2,
        'wave_direction_deg': 180.0,
        'wind_speed_mps': 6.0,
        'wind_direction_deg': 210.0,
        'current_speed_mps': 0.8,
        'current_direction_deg': 90.0,
    }))
    assert cfg_res['ok'] is True
    assert cfg_res['water_frame']['water_level_m'] == pytest.approx(0.35)
    assert cfg_res['water_config']['wave_mode'] == 'irregular'

    # 4. Water state endpoint returns 41x25 grid
    wf = asyncio.run(live_server.get_water_state())
    assert wf['nx'] == 41 and wf['ny'] == 25

    # 5. Update mass, CG, passenger state, fuel_state & propulsion_installation
    mp_res = asyncio.run(live_server.update_water_mass({
        'passenger_aboard': False,
        'payload_mass_kg': 45.0,
        'cg_shift_vtx_m': [0.15, 0.0, 0.02],
        'propulsion_installation': 'fuel_cell_paired',
        'fuel_state': 'nominal',
    }))
    assert mp_res['ok'] is True
    assert mp_res['mass_properties']['passenger_aboard'] is False
    assert mp_res['mass_properties']['payload_mass_kg'] == pytest.approx(45.0)
    assert mp_res['mass_properties']['propulsion_installation'] == 'fuel_cell_paired'
    assert mp_res['mass_properties']['fuel_state'] == 'nominal'
    assert mp_res['mass_properties']['fuel_mass_kg'] == pytest.approx(10.0)
    assert mp_res['observation']['propulsion_installation'] == 'fuel_cell_paired'
    assert mp_res['observation']['fuel_state'] == 'nominal'
    with pytest.raises(HTTPException) as bad_inst_exc:
        asyncio.run(live_server.update_water_mass({'propulsion_installation': 'energy_pack_alternate'}))
    assert bad_inst_exc.value.status_code == 422

    # 6. Model preview switch to F03 baseline
    preview_res = asyncio.run(live_server.model_preview({
        'environment': 'ricochet_lake',
        'airframe_variant': 'ricochet-rc01-f03',
        'departure': [40.0, 0.0],
    }))
    assert preview_res['observation']['configuration']['hull_variant'] == 'f03_baseline'

    # 7. Start Ricochet Lake mission (defaults to LC-01), reject legacy action with 409, accept ricochet-1
    mission_res = lab.start(Mission(
        environment='ricochet_lake',
        airframe_variant='ricochet-concept-a',
        departure=[40.0, 0.0],
        destination=[350.0, 0.0],
        authority='manual',
        time_scale=1.0,
    ))
    run_id = mission_res['run_id']
    start_view = lab.view()
    # #start must spawn buoyant on lake water surface, never underwater on lakebed
    assert start_view['rendering_truth']['body_poses']['airframe']['position'][2] > -1.0
    assert start_view['rendering_truth']['hydrodynamics']['freeboard_min_m'] > 0.15

    # Pilot sensor observation exposes full ROM + loading contract + achieved surfaces without leaking raw truth solver internals
    pilot_obs = start_view['observation']
    assert pilot_obs['load_case'] == 'LC-01'
    assert pilot_obs['register_version'] == DEFAULT_REGISTER_VERSION
    assert pilot_obs['fuel_state'] == 'dry'
    assert pilot_obs['propulsion_installation'] == 'baseline_pack'
    assert pilot_obs['propulsion_off'] is False
    assert pilot_obs['configuration']['load_case'] == 'LC-01'
    assert pilot_obs['configuration']['register_version'] == DEFAULT_REGISTER_VERSION
    assert pilot_obs['command_mode'] == 'hold_until_changed'
    assert 'surface_limits' in pilot_obs and 'rudder_deg' in pilot_obs['surface_limits']
    assert 'control_surfaces' in pilot_obs and 'rudder' in pilot_obs['control_surfaces']
    assert 'hydrodynamics' not in pilot_obs
    assert 'structural_rigidity' not in pilot_obs
    assert 'inertia_vtx_kg_m2' not in pilot_obs.get('mass_properties', {})

    legacy_act = parse_action({
        'authority': 'manual',
        'engine': 1.0,
        'collective_deg': [0, 0, 0, 0],
        'tilt_deg': [[0, 0], [0, 0], [0, 0], [0, 0]],
        'reason': 'Legacy schema rejection test',
    })
    with pytest.raises(HTTPException) as bad_exc:
        lab.accept_action(legacy_act)
    assert bad_exc.value.status_code == 409

    rico_act = parse_action({
        'schema': 'ricochet-1',
        'authority': 'manual',
        'expected_run_id': run_id,
        'throttle': 0.65,
        'rudder_deg': 12.0,
        'reverse_bucket': 0.0,
        'reason': 'Integration test forward turn',
    })
    lab.accept_action(rico_act)
    for _ in range(80):
        lab.integrate()
    assert lab.aircraft.command['throttle'] == pytest.approx(0.65)
    assert lab.aircraft.command['rudder_deg'] == pytest.approx(12.0)

    # Partial update holds omitted channels + resolves ambiguous/qualitative/clamped commands
    ambig_act = parse_action({
        'schema': 'ricochet-1',
        'authority': 'manual',
        'expected_run_id': run_id,
        'rudder': 'hard port',
        'elevator': 'nose up 50 deg',
        'aileron': [-10.0, 10.0],
        'reason': 'Ambiguous pilot control normalization test',
    })
    lab.accept_action(ambig_act)
    for _ in range(15):
        lab.integrate()
    assert lab.aircraft.command['throttle'] == pytest.approx(0.65)  # held from prior command!
    assert lab.aircraft.command['rudder_deg'] == pytest.approx(30.0)  # +Z yaw port
    assert lab.aircraft.command['elevator_deg'] == pytest.approx(20.0)  # clamped cleanly to stop
    assert lab.aircraft.command['aileron_deg'] == pytest.approx(10.0)

    text_act = parse_action({
        'schema': 'ricochet-1',
        'authority': 'manual',
        'expected_run_id': run_id,
        'text': 'half throttle, gentle starboard rudder, reverse deploy 40%',
        'reason': 'Natural-language text pilot command',
    })
    lab.accept_action(text_act)
    for _ in range(15):
        lab.integrate()
    assert lab.aircraft.command['throttle'] == pytest.approx(0.50)
    assert lab.aircraft.command['rudder_deg'] == pytest.approx(-7.5)
    assert lab.aircraft.command['reverse_bucket'] == pytest.approx(0.40)
    assert lab.aircraft.command['elevator_deg'] == pytest.approx(20.0)  # still held!

    # 8. Export bundle contains full reproducibility metadata
    bundle = asyncio.run(live_server.export_water_run())
    for required_key in ('run_id', 'water_config', 'random_seed', 'geometry_hash', 'solver_version', 'mass_properties', 'telemetry'):
        assert required_key in bundle
    json.dumps(bundle, allow_nan=False)

    # 9. Checkpoint persistence preserves ricochet_lake & craft state
    lab.checkpoint(force=True)
    if lab.audit_file:
        lab.audit_file.close()
        lab.audit_file = None
    restored = Laboratory(data_root=tmp_path)
    assert restored.active is True
    assert restored.world.environment_key == 'ricochet_lake'
    assert restored.aircraft.hull_bundle.variant_id == 'concept_a'
    restored.stop('Integration test complete')
    monkeypatch.setattr(live_server, 'lab', restored)

    # 10. Regression safety: airport R6 & sandbox Phantom remain intact
    air_res = asyncio.run(live_server.set_environment({'environment': 'airport', 'airframe_variant': 'r6'}))
    assert air_res['view']['environment']['key'] == 'airport'
    sand_res = asyncio.run(live_server.set_environment({'environment': 'sandbox', 'airframe_variant': 'phantom-a10b'}))
    assert sand_res['view']['environment']['key'] == 'sandbox'


def test_frontend_ricochet_assets_present():
    root = Path(__file__).resolve().parent.parent / 'public'
    html = (root / 'index.html').read_text(encoding='utf-8')
    app_js = (root / 'app.js').read_text(encoding='utf-8')
    lake_js = (root / 'vtx-env' / 'ricochet-lake.js').read_text(encoding='utf-8')

    assert 'env-ricochet' in html
    assert 'ricochet_lake' in html
    assert 'ricochet-concept-a' in html
    assert 'ricochet-panel' in html
    assert 'ricochet-lake.js' in app_js
    assert 'updateWaterSurface' in app_js
    assert 'animateRicochetWater' in app_js
    assert 'createRicochetPanel' in lake_js
    for marker in (
        'vaderland_caldera_rim',
        'vaderland_dock_yard',
        'rico-load-case',
        'LC-MAX',
        'rico-propulsion-installation',
        'rico-fuel-state',
        'rico-loading-meta',
        'syncMassPropertiesUI',
        'rico-waterproof',
        'rico-bilge-pump',
        'rico-ballast-kg',
        'rico-whirlpool-int',
        'ricochet_local_water_patch',
        'rico-cmd-text',
        'rico-surface-feedback',
    ):
        assert marker in lake_js
    assert 'ricochet_kelvin_wake' not in lake_js
    assert 'fp.rotation.x' not in app_js
    minimap_js = (root / 'vtx-env' / 'tactical-minimap.js').read_text(encoding='utf-8')
    assert 'world.islands' in minimap_js and 'world.whirlpools' in minimap_js
    assert (root / 'assets' / 'ricochet-concept-a.glb').is_file()


def test_ricochet_whirlpool_wake_ballast_waterproof_endpoints(tmp_path, monkeypatch):
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)

    asyncio.run(live_server.set_environment({
        'environment': 'ricochet_lake',
        'airframe_variant': 'ricochet-concept-a',
    }))

    cfg_res = asyncio.run(live_server.update_water_config({
        'whirlpools_enabled': True,
        'whirlpool_intensity': 1.6,
        'wake_enabled': True,
    }))
    assert cfg_res['ok'] is True
    assert cfg_res['water_config']['whirlpools_enabled'] is True
    assert cfg_res['water_config']['whirlpool_intensity'] == pytest.approx(1.6)
    assert cfg_res['water_frame']['whirlpools']
    assert 'vessel_wake' in cfg_res['water_frame']

    # Unseal hull with trim ballast and integrate briefly so bilge flooding triggers warning lamps
    mp_res = asyncio.run(live_server.update_water_mass({
        'ballast_mass_kg': 160.0,
        'ballast_x_m': -1.2,
        'waterproof': False,
    }))
    assert mp_res['mass_properties']['ballast_mass_kg'] == pytest.approx(160.0)
    assert mp_res['mass_properties']['waterproof'] is False
    for _ in range(100):
        lab.aircraft.step()
    obs_breach = lab.sensor_observation()
    assert 'HULL_UNSEALED' in obs_breach['warning_lamps']
    assert 'FLOODING' in obs_breach['warning_lamps']

    # Activate bilge pump + restore watertight seal
    pump_res = asyncio.run(live_server.update_water_mass({
        'waterproof': True,
        'bilge_pump': True,
    }))
    assert pump_res['mass_properties']['waterproof'] is True
    assert pump_res['mass_properties']['flood_water_kg'] == pytest.approx(0.0)

    # Near whirlpool_alpha (-10, -235), model preview / step observes whirlpool capture/shear hazard & warning lamp
    preview_wp = asyncio.run(live_server.model_preview({
        'environment': 'ricochet_lake',
        'airframe_variant': 'ricochet-concept-a',
        'departure': [-15.0, -235.0],
    }))
    obs_whirl = preview_wp['observation']
    assert obs_whirl['whirlpool_hazard']['in_influence'] is True
    assert {'WHIRLPOOL_CAPTURE', 'WHIRLPOOL_SHEAR'} & set(obs_whirl['warning_lamps'])


def test_laboratory_ricochet_complete_persistence_determinism_and_v1_limitations(tmp_path, monkeypatch):
    orig_root = tmp_path / 'orig'
    rest_root = tmp_path / 'rest'
    v1_root = tmp_path / 'v1'

    monkeypatch.setenv('VTX_DATA_ROOT', str(orig_root))
    lab_orig = Laboratory(data_root=orig_root)
    mission = Mission(
        environment='ricochet_lake',
        airframe_variant='ricochet-concept-a',
        departure=[40.0, 0.0],
        destination=[350.0, 0.0],
        authority='manual',
        ricochet_load_case='LC-01',
        water_config={
            'wave_mode': 'irregular',
            'wave_height_m': 0.45,
            'wave_period_s': 3.8,
            'wave_direction_deg': 170.0,
            'wave_seed': 41031,
            'wind_speed_mps': 6.0,
            'wind_direction_deg': 200.0,
            'current_speed_mps': 0.70,
            'current_direction_deg': 60.0,
            'wake_enabled': True,
            'whirlpools_enabled': True,
        },
    )
    started = lab_orig.start(mission)
    run_id = started['run_id']
    lab_orig.accept_action(parse_action({
        'schema': 'ricochet-1',
        'authority': 'manual',
        'expected_run_id': run_id,
        'throttle': 0.68,
        'differential_thrust': 0.20,
        'rudder_deg': 15.0,
        'elevator_deg': 2.5,
        'reason': 'Persistence phase 1 manoeuvre',
    }))
    for _ in range(400):  # t1 = 1.0 s
        lab_orig.integrate()
    assert lab_orig.aircraft.data.time == pytest.approx(1.0, abs=1e-12)

    lab_orig.checkpoint(force=True)
    if lab_orig.audit_file:
        lab_orig.audit_file.close()
        lab_orig.audit_file = None

    shutil.copytree(orig_root, rest_root)
    lab_orig.audit_file = (lab_orig.log_path / 'events.jsonl').open('a', encoding='utf-8')

    lab_rest = Laboratory(data_root=rest_root)
    assert lab_rest.active is True
    assert lab_rest.paused is True
    assert lab_rest.run_id == run_id
    assert lab_rest.recovery_notice is None
    assert lab_rest.aircraft.legacy_checkpoint_limitations == []
    lab_rest.paused = False

    # Run both uninterrupted and restored Laboratory instances from t1=1.0 s to t2=2.0 s
    for _ in range(100):
        lab_orig.integrate()
        lab_rest.integrate()

    act2 = {
        'schema': 'ricochet-1',
        'authority': 'manual',
        'expected_run_id': run_id,
        'throttle': 0.45,
        'rudder_deg': -12.0,
        'reverse_bucket': 0.35,
        'reason': 'Persistence phase 2 manoeuvre',
    }
    lab_orig.accept_action(parse_action(act2))
    lab_rest.accept_action(parse_action(act2))
    for _ in range(300):  # t2 = 2.0 s
        lab_orig.integrate()
        lab_rest.integrate()

    ao = lab_orig.aircraft
    ar = lab_rest.aircraft
    assert ao.data.time == pytest.approx(2.0, abs=1e-12)
    assert ar.data.time == pytest.approx(2.0, abs=1e-12)
    assert abs(ar.water_field.sim_time_s - ao.water_field.sim_time_s) < 1e-12
    assert abs(ar.water_field._swe_accum_s - ao.water_field._swe_accum_s) < 1e-12
    assert np.max(np.abs(ar.data.qpos - ao.data.qpos)) < 1e-9
    assert np.max(np.abs(ar.data.qvel - ao.data.qvel)) < 1e-9
    assert np.max(np.abs(ar.data.qacc_warmstart - ao.data.qacc_warmstart)) < 1e-9
    assert np.max(np.abs(ar.water_field.shallow.h - ao.water_field.shallow.h)) < 1e-9
    assert np.max(np.abs(ar.water_field.shallow.hu - ao.water_field.shallow.hu)) < 1e-9
    assert np.max(np.abs(ar.water_field.shallow.hv - ao.water_field.shallow.hv)) < 1e-9
    assert ar.water_field._vessel_wake == ao.water_field._vessel_wake

    so = ao.physical_snapshot()
    sr = ar.physical_snapshot()
    assert sr['t_s'] == so['t_s']
    assert sr['position_world_m'] == pytest.approx(so['position_world_m'], abs=1e-9)
    assert sr['velocity_world_mps'] == pytest.approx(so['velocity_world_mps'], abs=1e-9)
    assert sr['hydrodynamics']['submerged_volume_m3'] == pytest.approx(so['hydrodynamics']['submerged_volume_m3'], abs=1e-9)
    lab_orig.stop('Uninterrupted persistence check done')
    lab_rest.stop('Restored persistence check done')

    # Historical v1 checkpoint restoration into Laboratory preserves rc01-lc-v1 semantics & reports limitations
    lab_v1 = Laboratory(data_root=v1_root)
    lab_v1.start(Mission(
        environment='ricochet_lake',
        airframe_variant='ricochet-concept-a',
        departure=[40.0, 0.0],
        destination=[350.0, 0.0],
        authority='manual',
    ))
    for _ in range(40):
        lab_v1.integrate()
    lab_v1.checkpoint(force=True)
    v1_run_id = lab_v1.run_id
    if lab_v1.audit_file:
        lab_v1.audit_file.close()
        lab_v1.audit_file = None

    meta_path = v1_root / 'evidence' / 'flights' / v1_run_id / 'metadata.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta['request'].pop('ricochet_load_case', None)
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    v1_ref_craft = RicochetCraft(
        RicochetLakeWorld(),
        variant='ricochet-concept-a',
        hull_variant='concept_a',
        load_case='LC-03',
        register_version=LEGACY_REGISTER_VERSION,
    )
    cp_data = json.loads(lab_v1.checkpoint_path.read_text(encoding='utf-8'))
    cp_data['model_xml_sha256'] = v1_ref_craft.provenance['model_xml_sha256']
    plant_v1 = cp_data['plant']
    for k in (
        'checkpoint_version',
        'water_field',
        'qacc_warmstart',
        'act',
        'qfrc_applied',
        'xfrc_applied',
        'register_version',
        'load_case',
        'fuel_state',
        'fuel_mass_kg',
        'propulsion_installation',
        'propulsion_off',
    ):
        plant_v1.pop(k, None)
    plant_v1['mass_load_case'] = 'LC-03'
    lab_v1.checkpoint_path.write_text(json.dumps(cp_data), encoding='utf-8')

    restored_v1 = Laboratory(data_root=v1_root)
    assert restored_v1.active is True
    assert restored_v1.aircraft.mass_register.register_version == LEGACY_REGISTER_VERSION
    assert restored_v1.aircraft.mass_register.load_case == 'LC-03'
    assert restored_v1.aircraft.mass_properties()['total_mass_kg'] == pytest.approx(900.0)
    assert restored_v1.recovery_notice is not None
    assert 'shallow-water' in restored_v1.recovery_notice
    assert 'rc01-lc-v1' in restored_v1.recovery_notice
    restored_v1.stop('Legacy v1 limitation check done')


def test_r6_and_phantom_isolation_and_422_compatibility(tmp_path, monkeypatch):
    dep = dict(departure=[13.7, -28.4], destination=[-45, 18], authority='manual')
    m_dep = Mission(**dep)
    dumped_model = m_dep.model_dump()
    dumped_fn = mission_dump(m_dep)
    assert 'water_config' not in dumped_model and 'ricochet_load_case' not in dumped_model
    assert 'water_config' not in dumped_fn and 'ricochet_load_case' not in dumped_fn
    assert 'phantom' not in dumped_fn

    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    monkeypatch.setattr(live_server, 'ROOT', tmp_path)
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)

    # Incompatible (environment, airframe_variant) rejections with HTTP 422 before mutating state
    orig_aircraft = lab.aircraft
    orig_world = lab.world
    orig_gen = lab.preview_generation

    for bad_mission in (
        Mission(environment='airport', airframe_variant='ricochet-concept-a', departure=[40.0, 0.0], destination=[350.0, 0.0]),
        Mission(environment='sandbox', airframe_variant='ricochet-rc01-f03', departure=[40.0, 0.0], destination=[350.0, 0.0]),
        Mission(environment='ricochet_lake', airframe_variant='r6', departure=[40.0, 0.0], destination=[350.0, 0.0]),
        Mission(environment='ricochet_lake', airframe_variant='phantom-a10b', departure=[40.0, 0.0], destination=[350.0, 0.0]),
    ):
        with pytest.raises(HTTPException) as exc:
            lab.start(bad_mission)
        assert exc.value.status_code == 422
        assert lab.aircraft is orig_aircraft
        assert lab.world is orig_world
        assert lab.preview_generation == orig_gen

    for bad_preview in (
        {'environment': 'airport', 'airframe_variant': 'ricochet-concept-a'},
        {'environment': 'sandbox', 'airframe_variant': 'ricochet-rc01-f03'},
        {'environment': 'ricochet_lake', 'airframe_variant': 'r6'},
        {'environment': 'ricochet_lake', 'airframe_variant': 'phantom-fx'},
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(live_server.model_preview(bad_preview))
        assert exc.value.status_code == 422
        assert lab.aircraft is orig_aircraft
        assert lab.world is orig_world
        assert lab.preview_generation == orig_gen

    for bad_env_req in (
        {'environment': 'airport', 'airframe_variant': 'ricochet-concept-a'},
        {'environment': 'ricochet_lake', 'airframe_variant': 'r6'},
        {'environment': 'ricochet_lake', 'airframe_variant': 'phantom-a10b'},
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(live_server.set_environment(bad_env_req))
        assert exc.value.status_code == 422
        assert lab.aircraft is orig_aircraft
        assert lab.world is orig_world
        assert lab.preview_generation == orig_gen

    # Non-Ricochet model_preview from ricochet_lake without explicit environment switches cleanly to airport
    asyncio.run(live_server.set_environment({'environment': 'ricochet_lake', 'airframe_variant': 'ricochet-concept-a'}))
    assert lab.world.environment_key == 'ricochet_lake'
    prev_r6 = asyncio.run(live_server.model_preview({'airframe_variant': 'r6'}))
    assert prev_r6['environment']['key'] == 'airport'
    assert prev_r6['observation']['configuration']['airframe_variant'] == 'r6'

    asyncio.run(live_server.set_environment({'environment': 'ricochet_lake', 'airframe_variant': 'ricochet-rc01-f03'}))
    prev_ph = asyncio.run(live_server.model_preview({'airframe_variant': 'phantom-a10b'}))
    assert prev_ph['environment']['key'] == 'airport'
    assert prev_ph['observation']['configuration']['airframe_variant'] == 'phantom-a10b'

    # Full preservation of all R6 & Phantom variants across environments, controls, checkpoints, and retries
    r6_variants = ('r6', 'r6_variator', 'light', 'baseline')
    phantom_variants = ('phantom-a10b', 'phantom-fx', 'phantom', 'phantom-a9', 'phantom-fx-a9')

    for env_key in ('airport', 'sandbox'):
        v_root = tmp_path / f'r6_{env_key}'
        monkeypatch.setenv('VTX_DATA_ROOT', str(v_root))
        v_lab = Laboratory(data_root=v_root)
        for var in r6_variants:
            v_lab.start(Mission(**dep, environment=env_key, airframe_variant=var))
            assert v_lab.world.environment_key == env_key
            assert v_lab.aircraft.airframe_variant == var
            meta = json.loads((v_lab.log_path / 'metadata.json').read_text(encoding='utf-8'))
            assert 'water_config' not in meta['request'] and 'ricochet_load_case' not in meta['request']
            obs = v_lab.sensor_observation()
            assert v_lab.accept_action(Action(
                authority='manual',
                observation_id=obs['observation_id'],
                engine=0.5,
                collective_deg=[2.0] * 4,
                tilt_deg=[[0.0, 0.0]] * 4,
                reason='R6 isolation check',
            ))['accepted']
            for _ in range(10):
                v_lab.integrate()
            if var == 'r6':
                v_lab.checkpoint(force=True)
                if v_lab.audit_file:
                    v_lab.audit_file.close()
                    v_lab.audit_file = None
                v_rest = Laboratory(data_root=v_root)
                assert v_rest.active and v_rest.aircraft.airframe_variant == var
                v_rest.stop('R6 check done')
                ret = v_rest.retry({'authority': 'manual'})
                assert ret['run_id'] and v_rest.aircraft.airframe_variant == var
                v_rest.stop('R6 retry done')
                v_lab = v_rest
            else:
                v_lab.stop('R6 variant check done')

    ph_root = tmp_path / 'phantom_iso'
    monkeypatch.setenv('VTX_DATA_ROOT', str(ph_root))
    v_lab = Laboratory(data_root=ph_root)
    for var in phantom_variants:
        v_lab.start(Mission(**dep, environment='airport', airframe_variant=var))
        assert getattr(v_lab.aircraft, 'is_phantom', False)
        assert v_lab.aircraft.variant == var
        meta = json.loads((v_lab.log_path / 'metadata.json').read_text(encoding='utf-8'))
        assert 'water_config' not in meta['request'] and 'ricochet_load_case' not in meta['request']
        obs = v_lab.sensor_observation()
        assert v_lab.accept_action(PhantomAction(
            schema='phantom-fbw-1',
            authority='manual',
            observation_id=obs['observation_id'],
            collective=0.1,
            reason='Phantom isolation check',
        ))['accepted']
        for _ in range(10):
            v_lab.integrate()
        if var == 'phantom-a10b':
            v_lab.checkpoint(force=True)
            if getattr(v_lab.aircraft, 'step_log', None):
                v_lab.aircraft.step_log.close()
            if v_lab.audit_file:
                v_lab.audit_file.close()
                v_lab.audit_file = None
            v_rest = Laboratory(data_root=ph_root)
            assert v_rest.active and v_rest.aircraft.variant == var
            v_rest.stop('Phantom check done')
            ret = v_rest.retry({'authority': 'manual'})
            assert ret['run_id'] and v_rest.aircraft.variant == var
            v_rest.stop('Phantom retry done')
            v_lab = v_rest
        else:
            v_lab.stop('Phantom variant check done')
