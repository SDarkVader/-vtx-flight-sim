from __future__ import annotations

import hashlib
import json

import pytest

import vtx.live_server as server


def make_record(tmp_path, monkeypatch):
    run=tmp_path/'flight-1';run.mkdir()
    xml=b'<mujoco/>';(run/'model.xml').write_bytes(xml)
    model=hashlib.sha256(xml).hexdigest();config='b'*64;asset='/assets/phantom-a10b-visual.glb';visual='c'*64
    mission={'environment_key':'airport','environment':'stage1-extended-airfield-recovery','environment_version':'4',
             'environment_identity':{'scheme':'vtx-world-v1','seed':41031,'displayed_world_sha256':'a'*64}}
    airframe={'airframe_variant':'phantom-a10c','model_xml_sha256':model,'config_sha256':config,'render_asset':asset}
    meta={'run_id':run.name,'mission':mission,'airframe':airframe}
    identity={'variant':'phantom-a10c','model_xml_sha256':model,'config_sha256':config,'render_asset':asset,'render_asset_sha256':visual}
    (run/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    (run/'aircraft_identity.json').write_text(json.dumps(identity),encoding='utf-8')
    monkeypatch.setattr(server,'asset_sha256',lambda uri:visual if uri==asset else None)
    return run,meta,identity


def test_recorded_world_and_asset_identity_are_returned_without_mutation(tmp_path,monkeypatch):
    run,meta,identity=make_record(tmp_path,monkeypatch)
    before={p.name:p.read_bytes() for p in run.iterdir()}
    context=server.recorded_replay_context(run)
    assert context['environment']=={'key':'airport','id':'stage1-extended-airfield-recovery','version':'4',
                                    'seed':41031,'displayed_world_sha256':'a'*64}
    assert context['visual']['status']=='server-asset-matches-record'
    assert context['visual']['browser_loaded_verified'] is False
    assert {p.name:p.read_bytes() for p in run.iterdir()}==before


@pytest.mark.parametrize('damage',['missing-world-fingerprint','wrong-run','wrong-model','wrong-asset',
                                   'changed-file','wrong-config','unsafe-asset','missing-identity'])
def test_missing_or_mismatched_recorded_dependencies_are_not_substituted(tmp_path,monkeypatch,damage):
    run,meta,identity=make_record(tmp_path,monkeypatch)
    if damage=='missing-world-fingerprint':del meta['mission']['environment_identity']['displayed_world_sha256']
    elif damage=='wrong-run':meta['run_id']='another-flight'
    elif damage=='wrong-model':identity['model_xml_sha256']='d'*64
    elif damage=='wrong-asset':identity['render_asset_sha256']='d'*64
    elif damage=='changed-file':(run/'model.xml').write_bytes(b'changed')
    elif damage=='wrong-config':identity['config_sha256']='d'*64
    elif damage=='unsafe-asset':meta['airframe']['render_asset']='/assets/../other.glb'
    elif damage=='missing-identity':(run/'aircraft_identity.json').unlink()
    (run/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    if damage!='missing-identity':(run/'aircraft_identity.json').write_text(json.dumps(identity),encoding='utf-8')
    context=server.recorded_replay_context(run)
    if damage=='missing-world-fingerprint':assert context['environment'] is None
    elif damage=='wrong-run':assert context=={'environment':None,'visual':None}
    else:assert context['visual'] is None


def test_r6_replay_uses_recorded_start_snapshot_not_current_selection(tmp_path,monkeypatch):
    run,meta,identity=make_record(tmp_path,monkeypatch)
    (run/'aircraft_identity.json').unlink()
    meta['airframe']['airframe_variant']='r6-argon-20261103'
    del meta['airframe']['config_sha256']
    meta['server_frontend_identity']={'scheme':'vtx-server-public-tree-v1',
        'files':{identity['render_asset'].lstrip('/'):{'sha256':identity['render_asset_sha256']}}}
    (run/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    context=server.recorded_replay_context(run)
    assert context['visual']['variant']=='r6-argon-20261103'
    assert context['visual']['config_sha256'] is None
    assert context['visual']['identity_source']=='server-frontend-snapshot'
    meta['server_frontend_identity']['files'].clear()
    (run/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    assert server.recorded_replay_context(run)['visual'] is None
