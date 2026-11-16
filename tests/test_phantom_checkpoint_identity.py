"""Checkpoint identity must not silently change Phantom physics on reconnect."""
import json
import pytest
from fastapi import HTTPException
from vtx.live_server import Laboratory, Mission


@pytest.mark.parametrize(('variant', 'p6', 'expected'), [
    ('phantom-fx', False, 'b835295b7b806fcb785f01a8776b6715d73790f48ac5134cb8d594e6d389ebde'),
    ('phantom-fx', True, '70089ccace22e4ce1cfd28104654257fe4d03771c4f6b1faa3c89fce253247dd'),
    ('phantom-a10b', None, '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'),
])
def test_phantom_resume_retains_exact_configuration(tmp_path, variant, p6, expected):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant=variant, phantom={'p6_enabled': p6}))
    original.checkpoint(force=True)
    run_id = original.run_id
    original.aircraft.step_log.close()
    original.audit_file.close()
    restored = Laboratory(data_root=tmp_path)
    assert restored.active and restored.paused and restored.run_id == run_id
    assert restored.aircraft.P.config_sha256 == expected
    restored.stop('Isolated checkpoint test completed')


@pytest.mark.parametrize('field', ['config_sha256'])
def test_checkpoint_identity_mismatch_blocks_replacement(tmp_path, field):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant='phantom-a10b'))
    original.checkpoint(force=True)
    original.aircraft.step_log.close()
    original.audit_file.close()
    checkpoint = original.checkpoint_path
    saved = json.loads(checkpoint.read_text(encoding='utf-8'))
    saved[field] = '0' * 64
    checkpoint.write_text(json.dumps(saved), encoding='utf-8')
    before = checkpoint.read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert 'differs' in recovered.error
    assert checkpoint.read_bytes() == before


@pytest.mark.parametrize('source_hash', ['f' * 64, None])
def test_unverified_runtime_preserves_checkpoint_and_blocks_replacement(tmp_path, source_hash):
    """A missing or different runtime cannot resume, rename, or replace the flight."""
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant='phantom-a10b'))
    original.checkpoint(force=True)
    run_id = original.run_id
    original.aircraft.step_log.close()
    original.audit_file.close()
    checkpoint = original.checkpoint_path
    saved = json.loads(checkpoint.read_text(encoding='utf-8'))
    if source_hash is None:
        saved.pop('runtime_source_sha256')
    else:
        saved['runtime_source_sha256'] = source_hash
    checkpoint.write_text(json.dumps(saved), encoding='utf-8')
    before = checkpoint.read_bytes()
    evidence = tmp_path / 'evidence/flights' / run_id
    events_before = (evidence / 'events.jsonl').read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert checkpoint.read_bytes() == before
    assert not list(checkpoint.parent.glob('live-flight-checkpoint.from-build-*.json'))
    assert (evidence / 'events.jsonl').read_bytes() == events_before
    assert not (evidence / 'summary.json').exists()
    assert ('f' * 64 if source_hash else 'no runtime source fingerprint') in recovered.error
    assert str(checkpoint) in recovered.error
    with pytest.raises(HTTPException) as error:
        recovered.start(Mission(airframe_variant='phantom-a10b'))
    assert getattr(error.value, 'status_code', None) == 409


@pytest.mark.parametrize(('variant', 'missing'), [
    ('r6', 'airframe_variant'), ('r6', 'gear_variant'), ('r6', 'environment'),
    ('phantom-a10b', 'airframe_variant'), ('phantom-a10b', 'environment'),
])
def test_checkpoint_with_missing_identity_or_environment_is_preserved(tmp_path, variant, missing):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant=variant, environment='sandbox'))
    original.checkpoint(force=True)
    if getattr(original.aircraft, 'is_phantom', False):
        original.aircraft.step_log.close()
    original.audit_file.close()
    metadata_path = original.log_path / 'metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    state = json.loads(original.checkpoint_path.read_text(encoding='utf-8'))
    if missing == 'environment':
        metadata['request']['environment'] = None
        state['mission'].pop('environment_key', None)
        state['mission'].pop('environment', None)
    else:
        metadata['request'].pop(missing)
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
    original.checkpoint_path.write_text(json.dumps(state), encoding='utf-8')
    before = original.checkpoint_path.read_bytes()
    events_before = (original.log_path / 'events.jsonl').read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert ('environment' if missing == 'environment' else 'variant') in recovered.error
    assert original.checkpoint_path.read_bytes() == before
    assert (original.log_path / 'events.jsonl').read_bytes() == events_before


@pytest.mark.parametrize('variant', ['r6', 'phantom-a10b'])
def test_checkpoint_visual_mismatch_is_preserved(tmp_path, variant):
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant=variant))
    original.checkpoint(force=True)
    if getattr(original.aircraft, 'is_phantom', False):
        original.aircraft.step_log.close()
    original.audit_file.close()
    state = json.loads(original.checkpoint_path.read_text(encoding='utf-8'))
    state['visual_identity']['sha256'] = '0' * 64
    original.checkpoint_path.write_text(json.dumps(state), encoding='utf-8')
    before = original.checkpoint_path.read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert 'visual asset' in recovered.error
    assert original.checkpoint_path.read_bytes() == before
