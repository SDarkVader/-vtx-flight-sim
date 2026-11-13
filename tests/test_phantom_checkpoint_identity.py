"""Checkpoint identity must not silently change Phantom physics on reconnect."""
import json
import pytest
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


def test_checkpoint_from_another_build_is_set_aside_not_blocking(tmp_path):
    """A checkpoint written by different software is kept (renamed), its evidence untouched, the sortie recorded as
    interrupted for that reason, and the laboratory starts clean instead of blocking every mission."""
    original = Laboratory(data_root=tmp_path)
    original.start(Mission(airframe_variant='phantom-a10b'))
    original.checkpoint(force=True)
    run_id = original.run_id
    original.aircraft.step_log.close()
    original.audit_file.close()
    checkpoint = original.checkpoint_path
    saved = json.loads(checkpoint.read_text(encoding='utf-8'))
    saved['runtime_source_sha256'] = 'f' * 64
    checkpoint.write_text(json.dumps(saved), encoding='utf-8')
    before = checkpoint.read_bytes()
    evidence = tmp_path / 'evidence/flights' / run_id
    events_before = (evidence / 'events.jsonl').read_bytes()
    recovered = Laboratory(data_root=tmp_path)
    assert not recovered.recovery_blocked and not recovered.active and recovered.error is None
    assert not checkpoint.exists()
    aside = list(checkpoint.parent.glob('live-flight-checkpoint.from-build-ffffffff-*.json'))
    assert len(aside) == 1 and aside[0].read_bytes() == before                      # kept byte for byte
    assert (evidence / 'events.jsonl').read_bytes() == events_before                 # evidence untouched
    summary = json.loads((evidence / 'summary.json').read_text())
    assert summary['outcome'] == 'interrupted' and 'different software build' in summary['reason']
    assert summary['checkpoint_set_aside']['path'] == str(aside[0])
    assert run_id in recovered.recovery_notice and 'ffffffff' in recovered.recovery_notice
    recovered.start(Mission(airframe_variant='phantom-a10b'))                        # no longer blocked
    assert recovered.active and recovered.run_id != run_id
    recovered.stop('Isolated checkpoint test completed')
