"""Real MuJoCo experiment execution must not touch the live laboratory."""
import asyncio
import numpy as np
import vtx.live_server as server
from vtx.experiments import ExperimentRequest


def test_experiment_runs_real_physics_and_isolates_live_sortie(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    live = server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, 'lab', live)
    live.start(server.Mission(airframe_variant='r6'))
    live.paused = True
    run_id = live.run_id
    qpos = live.aircraft.data.qpos.copy()
    routes = {(r.path, method): r.endpoint for r in server.app.routes if hasattr(r, 'endpoint') for method in (getattr(r, 'methods', None) or [])}
    async def exercise():
        spec = ExperimentRequest(airframe_variant='phantom-a10b', start_configuration='road',
            duration_s=.3, schedule=[{'at_s': 0, 'action': {'wheel_drive': [.2]*4, 'brake': [0]*4}}])
        created = await routes[('/api/experiments', 'POST')](spec)
        experiment_id = created['id']
        for _ in range(300):
            state = await routes[('/api/experiments/{experiment_id}', 'GET')](experiment_id)
            if state['status'] in ('completed', 'error', 'aborted', 'crashed'):
                break
            await asyncio.sleep(.02)
        assert state['status'] == 'completed', state
        assert state['progress_s'] >= .3 and state['run_id'] != run_id
        response = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](experiment_id, 'phantom_parameters.json')
        import json
        assert json.loads(response.path.read_text(encoding='utf-8'))['config_sha256'] == '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'
        ledger = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](experiment_id, 'phantom_ledger.json')
        mass = json.loads(ledger.path.read_text(encoding='utf-8'))['actual_start_mass_properties']
        assert mass['mass_kg'] > 0 and len(mass['cg_body_m']) == 3 and len(mass['inertia_body_kg_m2']) == 3
        events = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](experiment_id, 'events.jsonl')
        assert 'control_applied' in events.path.read_text(encoding='utf-8')
        export = await routes[('/api/experiments/{experiment_id}/export', 'GET')](experiment_id)
        import io, zipfile
        data = b''.join([chunk async for chunk in export.body_iterator])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            assert 'request.json' in names
            assert any(name.endswith('/events.jsonl') for name in names)
            assert any(name.endswith('/phantom_parameters.json') for name in names)
            assert not any('pilot-before' in name for name in names)
        historical = ExperimentRequest(airframe_variant='phantom-fx', p6_enabled=False, duration_s=.1)
        second = await routes[('/api/experiments', 'POST')](historical)
        for _ in range(300):
            prior = await routes[('/api/experiments/{experiment_id}', 'GET')](second['id'])
            if prior['status'] in ('completed', 'error', 'aborted', 'crashed'):
                break
            await asyncio.sleep(.02)
        assert prior['status'] == 'completed', prior
        params = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](second['id'], 'phantom_parameters.json')
        assert json.loads(params.path.read_text(encoding='utf-8'))['config_sha256'] == 'b835295b7b806fcb785f01a8776b6715d73790f48ac5134cb8d594e6d389ebde'
        modified = ExperimentRequest(airframe_variant='phantom-a10b', duration_s=.1,
            experimental_overrides={'buffer.position_m': [1.2, 0, .42]})
        third = await routes[('/api/experiments', 'POST')](modified)
        for _ in range(300):
            changed = await routes[('/api/experiments/{experiment_id}', 'GET')](third['id'])
            if changed['status'] in ('completed', 'error', 'aborted', 'crashed'):
                break
            await asyncio.sleep(.02)
        assert changed['status'] == 'completed', changed
        params = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](third['id'], 'phantom_parameters.json')
        snapshot = json.loads(params.path.read_text(encoding='utf-8'))
        assert snapshot['config_sha256'] != '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'
        assert snapshot['parameters']['buffer']['position_m']['v'] == [1.2, 0, .42]
        assert snapshot['parameters']['buffer']['position_m']['l'] == 'SYNTHETIC_UNVALIDATED'
        from fastapi import HTTPException
        import pytest
        for bad in [ExperimentRequest(airframe_variant='phantom-a10b', p6_enabled=False),
                    ExperimentRequest(airframe_variant='r6', experimental_overrides={'buffer.position_m': [1, 0, 0]}),
                    ExperimentRequest(airframe_variant='phantom-a10b', experimental_overrides={'unknown': 1}),
                    ExperimentRequest(airframe_variant='phantom-a10b', duration_s=.1,
                                      schedule=[{'at_s': .1, 'action': {}}])]:
            with pytest.raises(HTTPException) as error:
                await routes[('/api/experiments', 'POST')](bad)
            assert error.value.status_code == 422
        pending = await routes[('/api/experiments', 'POST')](ExperimentRequest(duration_s=10))
        await routes[('/api/experiments/{experiment_id}/abort', 'POST')](pending['id'])
        for _ in range(300):
            stopped = await routes[('/api/experiments/{experiment_id}', 'GET')](pending['id'])
            if stopped['status'] in ('completed', 'error', 'aborted', 'crashed'):
                break
            await asyncio.sleep(.02)
        assert stopped['status'] == 'aborted', stopped
        guarded = ExperimentRequest(airframe_variant='phantom-a10b', start_configuration='vtol',
            duration_s=8, max_attitude_deg=1,
            schedule=[{'at_s': 0, 'action': {'collective': .65, 'roll': 1, 'brake': [0]*4}}])
        fourth = await routes[('/api/experiments', 'POST')](guarded)
        for _ in range(300):
            result = await routes[('/api/experiments/{experiment_id}', 'GET')](fourth['id'])
            if result['status'] in ('completed', 'error', 'aborted', 'crashed'):
                break
            await asyncio.sleep(.02)
        assert result['status'] == 'aborted' and 'roll or pitch' in result['abort_reason'], result
        guard_events = await routes[('/api/experiments/{experiment_id}/files/{name}', 'GET')](fourth['id'], 'events.jsonl')
        assert 'experiment_abort_condition' in guard_events.path.read_text(encoding='utf-8')
        history = await routes[('/api/experiments', 'GET')]()
        assert {experiment_id, second['id'], third['id'], pending['id'], fourth['id']} <= {item['id'] for item in history['experiments']}
    asyncio.run(exercise())
    assert live.active and live.run_id == run_id
    np.testing.assert_array_equal(live.aircraft.data.qpos, qpos)
    live.stop('End isolation test')


def test_runtime_identity_includes_nested_phantom_source(tmp_path):
    source = tmp_path / 'vtx'
    (source / 'phantom').mkdir(parents=True)
    (source / 'live_server.py').write_text('runtime', encoding='utf-8')
    plant = source / 'phantom' / 'plant.py'
    plant.write_text('plant version one', encoding='utf-8')
    before = server.runtime_source_sha256(source)
    plant.write_text('plant version two', encoding='utf-8')
    assert server.runtime_source_sha256(source) != before


def test_experiment_override_validation_preserves_original():
    from vtx.phantom.experiment_config import build_overrides, parameter_catalogue
    from vtx.phantom.params import Params
    import pytest
    baseline = Params('phantom-a10b')
    changes = build_overrides('phantom-a10b', None, {'buffer.position_m': [1.2, 0, .42]})
    modified = Params('phantom-a10b', overrides=changes)
    assert modified.config_sha256 != baseline.config_sha256
    assert baseline['buffer.position_m'] == [1.8, 0.0, .42]
    assert modified['buffer.position_m'] == [1.2, 0, .42]
    assert modified.label('buffer.position_m') == 'SYNTHETIC_UNVALIDATED'
    assert any(item['name'] == 'buffer.position_m' for item in parameter_catalogue('phantom-a10b'))
    for invalid in ({'buffer.position_m': [99, 0, 0]}, {'buffer.position_m': [1, 2]},
                    {'aero.wing_cd0': float('nan')}, {'proposals.p6_drs_stabilator': 0}):
        with pytest.raises(ValueError):
            build_overrides('phantom-a10b', None, invalid)
