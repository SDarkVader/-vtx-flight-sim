"""Flown parents remain distinct from the integrated runtime and the current A10-C."""
import asyncio
import json

import pytest
from fastapi import HTTPException
from vtx import live_server
from vtx.phantom import identity
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


@pytest.mark.parametrize(('variant', 'environment', 'model_sha'), [
    ('phantom-a10c-runway-20261112', 'airport', '1e04c9e9f82fe55fe6aae60ce3aaf15520c0ea593ea4658389259ac86a0e8d39'),
    ('phantom-a10c-runway-20261112', 'sandbox', '5994a751799875c2d2fa07bcca5862e6a72d59965865893ac97a7a575b0aeb92'),
    ('phantom-a10c-vtol-20261112', 'airport', '1e04c9e9f82fe55fe6aae60ce3aaf15520c0ea593ea4658389259ac86a0e8d39'),
])
def test_flown_candidate_model_and_parent_identity(variant, environment, model_sha):
    aircraft = PhantomAircraft(make_world(environment), variant, start_configuration='road')
    result = identity.verify(aircraft, runtime_source_sha256=live_server.RUNTIME_SOURCE_SHA256)
    assert result['verified'] and 'promotion pending' in result['status']
    assert aircraft.provenance['model_xml_sha256'] == model_sha
    assert aircraft.fcc.cmd['stability_mode'] == 'rate_damping'
    assert aircraft.provenance['flight_revision']['evidence']
    assert not identity.verify(aircraft, runtime_source_sha256='0' * 64)['verified']


def test_selecting_and_checkpointing_candidate_retains_identity(tmp_path, monkeypatch):
    lab = live_server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)
    variant = 'phantom-a10c-runway-20261112'
    view = asyncio.run(live_server.model_preview({'airframe_variant': variant,
                                                   'start_configuration': 'road', 'departure': [-700, 0]}))
    assert view['observation']['configuration']['airframe_variant'] == variant
    assert view['observation']['configuration']['identity']['verified']
    lab.start(live_server.Mission(airframe_variant=variant, environment='airport',
                                  departure=[-700, 0], phantom={'start_configuration': 'road'}))
    lab.checkpoint(force=True)
    checkpoint = json.loads(lab.checkpoint_path.read_text(encoding='utf-8'))
    assert checkpoint['flight_revision_registry_sha256'] == lab.aircraft.provenance['flight_revision']['registry_sha256']
    lab.aircraft.step_log.close()
    lab.audit_file.close()
    # A changed registry cannot silently reclassify the retained run.
    checkpoint['flight_revision_registry_sha256'] = '0' * 64
    lab.checkpoint_path.write_text(json.dumps(checkpoint), encoding='utf-8')
    before = lab.checkpoint_path.read_bytes()
    restored = live_server.Laboratory(data_root=tmp_path)
    assert restored.recovery_blocked and not restored.active
    assert 'registry' in restored.error
    assert lab.checkpoint_path.read_bytes() == before
    with pytest.raises(HTTPException):
        restored.start(live_server.Mission(airframe_variant='phantom-a10c'))


def test_schematic_is_an_explicit_candidate_dependency(monkeypatch):
    aircraft = PhantomAircraft(make_world('airport'), 'phantom-a10c-runway-20261112', start_configuration='road')
    descriptor = aircraft.provenance['flight_revision']['suspension_schematic']
    assert descriptor['schema'] == 1
    assert identity.verify(aircraft, runtime_source_sha256=live_server.RUNTIME_SOURCE_SHA256)['suspension_schematic'] == descriptor
    original_hash = identity.asset_sha256
    monkeypatch.setattr(identity, 'asset_sha256', lambda uri: None if uri == descriptor['asset'] else original_hash(uri))
    result = identity.verify(aircraft, runtime_source_sha256=live_server.RUNTIME_SOURCE_SHA256)
    assert not result['verified']
    assert any(item['field'] == 'suspension_schematic' for item in result['mismatches'])


def test_schematic_cannot_change_without_candidate_identity_change():
    aircraft = PhantomAircraft(make_world('airport'), 'phantom-a10c-vtol-20261112', start_configuration='road')
    aircraft.provenance['flight_revision']['suspension_schematic']['label'] = 'Unrecorded visual change'
    result = identity.verify(aircraft, runtime_source_sha256=live_server.RUNTIME_SOURCE_SHA256)
    assert not result['verified']
    assert any(item['field'] == 'suspension_schematic' for item in result['mismatches'])
