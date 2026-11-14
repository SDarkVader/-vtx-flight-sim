"""End-to-end server API, schema, checkpoint restoration, and regression integration tests for Ricochet Lake."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

import vtx.live_server as live_server
from vtx.live_server import Laboratory, Mission, parse_action


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

    # 2. Pinned geometry endpoint matches Concept A SHA-256
    model_payload = asyncio.run(live_server.get_water_model())
    assert model_payload['hull_variant'] == 'concept_a'
    assert model_payload['geometry_sha256'] == env_res['view']['observation']['configuration']['hull_geometry_sha256']
    assert len(model_payload['meshes']) == 19
    assert all(m.get('pinned') is True for m in model_payload['meshes'])
    assert model_payload['boxes'] == []
    truth = env_res['view']['rendering_truth']
    for key in ('cg_body_m', 'cb_body_m', 'cn_yaw', 'cn_beta_per_rad', 'munk_moment_nm', 'fan_rpm'):
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

    # 5. Update mass, CG & passenger state
    mp_res = asyncio.run(live_server.update_water_mass({
        'passenger_aboard': False,
        'payload_mass_kg': 45.0,
        'cg_shift_vtx_m': [0.15, 0.0, 0.02],
    }))
    assert mp_res['ok'] is True
    assert mp_res['mass_properties']['passenger_aboard'] is False
    assert mp_res['mass_properties']['payload_mass_kg'] == pytest.approx(45.0)

    # 6. Model preview switch to F03 baseline
    preview_res = asyncio.run(live_server.model_preview({
        'environment': 'ricochet_lake',
        'airframe_variant': 'ricochet-rc01-f03',
        'departure': [40.0, 0.0],
    }))
    assert preview_res['observation']['configuration']['hull_variant'] == 'f03_baseline'

    # 7. Start Ricochet Lake mission, reject legacy action with 409, accept ricochet-1
    mission_res = lab.start(Mission(
        environment='ricochet_lake',
        airframe_variant='ricochet-concept-a',
        departure=[40.0, 0.0],
        destination=[350.0, 0.0],
        authority='manual',
        time_scale=1.0,
        ricochet_load_case='LC-03',
    ))
    run_id = mission_res['run_id']

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
    assert 'createRicochetPanel' in lake_js
    assert (root / 'assets' / 'ricochet-concept-a.glb').is_file()
