"""Phantom live integration boundaries (isolated data root; not piloted flights)."""
import json
import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from vtx.live_server import Mission, Laboratory, Action, mission_dump, parse_action
from vtx.phantom.controls import PhantomAction

DEP = dict(departure=[13.7, -28.4], destination=[-45, 18], authority='manual')


def test_legacy_mission_dump_has_no_phantom_key():
    d = mission_dump(Mission(**DEP))
    assert 'phantom' not in d
    assert d == {k: v for k, v in Mission(**DEP).model_dump().items() if k != 'phantom'}


def test_action_dispatch_by_schema():
    a = parse_action({'schema': 'phantom-fbw-1', 'authority': 'manual', 'reason': 'bench', 'collective': 0.2})
    assert isinstance(a, PhantomAction)
    legacy = parse_action({'authority': 'manual', 'engine': 0, 'collective_deg': [0] * 4, 'tilt_deg': [[0, 0]] * 4, 'reason': 'bench'})
    assert isinstance(legacy, Action)


def test_validation_errors_keep_body_loc():
    with pytest.raises(RequestValidationError) as e:
        parse_action({'schema': 'phantom-fbw-1', 'authority': 'manual', 'reason': 'bench', 'collective': 2.0})
    assert e.value.errors()[0]['loc'][0] == 'body'
    with pytest.raises(RequestValidationError):
        parse_action({'schema': 'phantom-fbw-1', 'authority': 'manual', 'reason': 'bench', 'position': [0, 0, 1]})


@pytest.mark.parametrize('variant', ['phantom', 'phantom-fx'])
def test_phantom_sortie_start_action_stop(tmp_path, monkeypatch, variant):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    import vtx.live_server as server
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    lab = Laboratory()
    lab.start(Mission(**DEP, airframe_variant=variant, phantom={'load_state': 'FX-C'} if variant == 'phantom-fx' else None))
    assert getattr(lab.aircraft, 'is_phantom', False)
    obs = lab.sensor_observation()
    assert obs['action_schema'] == 'phantom-fbw-1' and 'lease_remaining_s' in obs
    assert not any(k in json.dumps(obs) for k in ('qpos', 'qvel', 'xfrc'))
    with pytest.raises(HTTPException) as e:
        lab.accept_action(Action(authority='manual', engine=0, collective_deg=[0] * 4, tilt_deg=[[0, 0]] * 4, reason='legacy on phantom'))
    assert e.value.status_code == 409
    lab.accept_action(parse_action({'schema': 'phantom-fbw-1', 'authority': 'manual', 'reason': 'bench idle', 'collective': 0.0,
                                    'observation_id': obs['observation_id']}))
    for _ in range(200):
        lab.integrate()
    lab.checkpoint()
    assert lab.checkpoint_path.exists() and json.loads(lab.checkpoint_path.read_text())['schema'] == 'phantom-1'
    lab.stop('End isolated phantom boundary check')
    for f in ('metadata.json', 'events.jsonl', 'summary.json', 'phantom_parameters.json', 'phantom_ledger.json', 'phantom_steps.csv.gz'):
        assert (lab.log_path / f).exists(), f
    s = json.loads((lab.log_path / 'summary.json').read_text())
    assert s['phantom']['variant'] == variant
    assert 'phantom' in json.loads((lab.log_path / 'metadata.json').read_text())['request'] or variant == 'phantom'
