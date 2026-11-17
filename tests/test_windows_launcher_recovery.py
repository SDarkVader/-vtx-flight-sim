"""Offline fixtures for version identification and lossless launch recovery."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_busy_server_checks_selector_as_well_as_entrypoint(tmp_path):
    module = load('check_airport_server')
    (tmp_path / 'inputs').mkdir(); (tmp_path / 'public').mkdir()
    (tmp_path / 'inputs/flight_revisions.json').write_text(json.dumps({'integrated_runtime_sha256': 'runtime'}))
    (tmp_path / 'public/app.js').write_bytes(b'app')
    (tmp_path / 'public/model-selector.js').write_bytes(b'new selector')
    responses = {'/api/world': b'{"environment":"airport","harbour":{"id":"lake"}}',
                 '/api/view': b'{"runtime_source_sha256":"runtime","active":true}',
                 '/app.js': b'app', '/model-selector.js': b'old selector'}
    with pytest.raises(ValueError, match='model-selector'):
        module.check_server(root=tmp_path, reader=responses.__getitem__)
    responses['/model-selector.js'] = b'new selector'
    assert module.check_server(root=tmp_path, reader=responses.__getitem__)['active'] is True


def test_frontend_incompatible_idle_selection_is_preserved_twice(tmp_path, monkeypatch):
    module = load('prepare_windows_launch')
    runtime = json.loads((ROOT / 'inputs/flight_revisions.json').read_text())['integrated_runtime_sha256']
    monkeypatch.setattr(module, 'server_frontend_manifest', lambda: {'sha256': 'new'})
    pilot = tmp_path / 'pilot'; pilot.mkdir()
    payload = json.dumps({'runtime_source_sha256': runtime, 'server_frontend_identity': {'sha256': 'old'}}).encode()
    selection = pilot / 'inspection-selection.json'; selection.write_bytes(payload)
    archive = module.prepare(tmp_path)
    assert (archive / selection.name).read_bytes() == payload
    assert (archive / ('original-' + selection.name)).read_bytes() == payload
    assert not selection.exists()


def test_matching_selection_and_checkpoint_are_left_untouched(tmp_path, monkeypatch):
    module = load('prepare_windows_launch')
    runtime = json.loads((ROOT / 'inputs/flight_revisions.json').read_text())['integrated_runtime_sha256']
    monkeypatch.setattr(module, 'server_frontend_manifest', lambda: {'sha256': 'same'})
    pilot = tmp_path / 'pilot'; pilot.mkdir()
    payload = json.dumps({'runtime_source_sha256': runtime, 'server_frontend_identity': {'sha256': 'same'}}).encode()
    for name in ('inspection-selection.json', 'live-flight-checkpoint.json'):
        (pilot / name).write_bytes(payload)
    assert module.prepare(tmp_path) is None
    assert all(file.read_bytes() == payload for file in pilot.iterdir())
