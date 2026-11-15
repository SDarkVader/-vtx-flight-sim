"""A run records server public files without claiming browser cache attestation."""
import asyncio
import json
import os
from pathlib import Path

import pytest
from vtx import frontend_identity as frontend
from vtx import live_server as server


def make_public(tmp_path,monkeypatch):
    root=tmp_path/'public-fixture';root.mkdir()
    (root/'index.html').write_text('<script>v1</script>',encoding='utf-8')
    (root/'assets').mkdir()
    (root/'assets'/'aircraft.glb').write_bytes(b'glTF sample')
    monkeypatch.setattr(frontend,'PUBLIC_ROOT',root)
    return root


def test_manifest_tracks_paths_and_freshly_reads_identical_stat_files(tmp_path):
    root=tmp_path/'assets';root.mkdir()
    path=root/'app.js';path.write_bytes(b'alpha')
    first=frontend.server_frontend_manifest(root)
    original=path.stat()
    path.write_bytes(b'omega')
    os.utime(path,ns=(original.st_atime_ns,original.st_mtime_ns))
    # Fresh verification hashes file bytes even when size and timestamp match.
    second=frontend.server_frontend_manifest(root)
    assert first['sha256']!=second['sha256']
    assert second['files']['app.js']['sha256']!=first['files']['app.js']['sha256']
    assert second['browser_loaded_verified'] is False
    (root/'environment.js').write_text('new',encoding='utf-8')
    assert frontend.server_frontend_manifest(root)['sha256']!=second['sha256']


@pytest.mark.parametrize('variant',['r6','phantom-a10c'])
def test_run_and_checkpoint_record_public_tree_and_block_changed_restore(tmp_path,monkeypatch,variant):
    root=make_public(tmp_path,monkeypatch)
    lab=server.Laboratory(data_root=tmp_path/'workspace')
    lab.start(server.Mission(airframe_variant=variant,environment='sandbox'))
    lab.checkpoint(force=True)
    metadata=json.loads((lab.log_path/'metadata.json').read_text(encoding='utf-8'))
    state=json.loads(lab.checkpoint_path.read_text(encoding='utf-8'))
    selection=json.loads(lab.inspection_path.read_text(encoding='utf-8'))
    expected=state['server_frontend_identity']
    assert metadata['server_frontend_identity']==expected==selection['server_frontend_identity']
    assert expected['browser_loaded_verified'] is False
    assert 'index.html' in expected['files'] and 'assets/aircraft.glb' in expected['files']
    if getattr(lab.aircraft,'is_phantom',False):lab.aircraft.step_log.close()
    lab.audit_file.close()
    before=lab.checkpoint_path.read_bytes()
    events_before=(lab.log_path/'events.jsonl').read_bytes()
    (root/'index.html').write_text('<script>changed</script>',encoding='utf-8')
    recovered=server.Laboratory(data_root=tmp_path/'workspace')
    assert recovered.recovery_blocked and not recovered.active
    assert 'frontend assets differ' in recovered.error
    assert 'changed index.html' in recovered.error
    assert lab.checkpoint_path.read_bytes()==before
    assert (lab.log_path/'events.jsonl').read_bytes()==events_before


def test_unverified_inspection_selection_is_retained(tmp_path,monkeypatch):
    root=make_public(tmp_path,monkeypatch)
    lab=server.Laboratory(data_root=tmp_path/'workspace')
    monkeypatch.setattr(server,'lab',lab)
    asyncio.run(server.model_preview({'airframe_variant':'r6','departure':[-700,0]}))
    before=lab.inspection_path.read_bytes()
    (root/'index.html').unlink()
    recovered=server.Laboratory(data_root=tmp_path/'workspace')
    assert recovered.recovery_blocked and not recovered.inspection_selection_known
    assert 'frontend assets differ' in recovered.error
    assert 'missing index.html' in recovered.error
    assert lab.inspection_path.read_bytes()==before


def test_checkpoint_reuses_start_snapshot_without_rehashing_during_physics(tmp_path,monkeypatch):
    root=make_public(tmp_path,monkeypatch)
    lab=server.Laboratory(data_root=tmp_path/'workspace')
    lab.start(server.Mission(airframe_variant='r6'))
    initial=lab.server_frontend_identity
    (root/'index.html').write_text('changed after start',encoding='utf-8')
    def no_disk_hash():raise AssertionError('checkpoint tried to hash frontend assets')
    monkeypatch.setattr(server,'server_frontend_manifest',no_disk_hash)
    lab.checkpoint(force=True)
    state=json.loads(lab.checkpoint_path.read_text(encoding='utf-8'))
    assert state['server_frontend_identity']==initial
    lab.audit_file.close()


def test_historical_run_does_not_gain_a_made_up_frontend_identity(tmp_path,monkeypatch):
    lab=server.Laboratory(data_root=tmp_path/'workspace');monkeypatch.setattr(server,'lab',lab)
    evidence=lab.data_root/'evidence/flights/old-run';evidence.mkdir(parents=True)
    (evidence/'metadata.json').write_text(json.dumps({'run_id':'old-run'}),encoding='utf-8')
    result=asyncio.run(server.recorded_frontend_identity('old-run'))
    assert result['captured'] is False and result['identity'] is None
