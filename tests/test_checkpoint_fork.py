"""An explicit checkpoint fork never rewrites later parent flight evidence."""
import gzip
import asyncio
import hashlib
import json
import numpy as np
import pytest
from fastapi import HTTPException
from vtx import live_server as server
from vtx.phantom.controls import PhantomAction


def diverged_flight(tmp_path, variant):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant=variant,environment='airport'))
    for _ in range(400):lab.integrate()
    if variant.startswith('phantom'):
        lab.accept_action(PhantomAction.model_validate({'schema':'phantom-fbw-1','authority':'manual','reason':'Pending at checkpoint','wing':'deploy'}))
    else:
        lab.accept_action(server.Action(authority='manual',reason='Pending at checkpoint',engine=.5,collective_deg=[2]*4,tilt_deg=[[0,0]]*4))
    lab.checkpoint(force=True)
    lab.checkpoint=lambda *args,**kwargs:None
    for _ in range(80):lab.integrate()
    if getattr(lab.aircraft,'is_phantom',False):lab.aircraft.step_log.close()
    lab.audit_file.close()
    return lab


@pytest.mark.parametrize('variant',['r6','phantom-a10c'])
def test_explicit_fork_preserves_parent_and_resumes_paused(tmp_path,variant,monkeypatch):
    original=diverged_flight(tmp_path,variant)
    parent=original.run_id;checkpoint=original.checkpoint_path.read_bytes()
    parent_files={p.name:p.read_bytes() for p in original.log_path.iterdir() if p.is_file()}
    restored=server.Laboratory(data_root=tmp_path)
    assert restored.recovery_blocked and not restored.active
    digest=hashlib.sha256(checkpoint).hexdigest()
    monkeypatch.setattr(server,'lab',restored)
    offer=asyncio.run(server.checkpoint_recovery())
    assert offer['fork_available'] and offer['run_id']==parent and offer['checkpoint_sha256']==digest
    assert offer['checkpoint_time_s']==pytest.approx(1.)
    with pytest.raises(HTTPException):restored.fork_checkpoint_continuation(parent,'0'*64)
    result=restored.fork_checkpoint_continuation(parent,digest)
    assert result['paused'] and result['run_id']!=parent and restored.active and restored.paused
    assert result['parent_run_id']==parent
    assert {p.name:p.read_bytes() for p in original.log_path.iterdir() if p.is_file()}==parent_files
    assert any(p.read_bytes()==checkpoint for p in (tmp_path/'pilot/checkpoint-history').glob('*.json'))
    assert restored.next_pending_action==0 and not restored.action_log[0].get('cancelled')
    metadata=json.loads((restored.log_path/'metadata.json').read_text(encoding='utf-8'))
    assert metadata['continuation']['checkpoint_sha256']==digest
    assert metadata['continuation']['parent_run_id']==parent
    listed=asyncio.run(server.runs())
    assert listed[0]['continuation']['parent_run_id']==parent
    parent_row=next(row for row in listed if row['run_id']==parent)
    assert parent_row['outcome']=='unfinished; evidence retained'
    assert parent_row['simulated_seconds'] is None and parent_row['decisions'] is None
    assert not (original.log_path/'summary.json').exists()
    assert {p.name:p.read_bytes() for p in original.log_path.iterdir() if p.is_file()}==parent_files
    oldpos=np.array(restored.aircraft.data.qpos)
    # A restart of the new segment remains paused and restores the same state.
    if getattr(restored.aircraft,'is_phantom',False):restored.aircraft.step_log.close()
    restored.audit_file.close()
    again=server.Laboratory(data_root=tmp_path)
    assert again.active and again.paused and again.run_id==result['run_id'],again.error
    np.testing.assert_allclose(again.aircraft.data.qpos,oldpos,rtol=0,atol=0)
    for _ in range(40):again.integrate()
    assert again.next_pending_action==1
    if getattr(again.aircraft,'is_phantom',False):
        path=again.log_path/'phantom_steps.csv.gz'
        again.aircraft.step_log.close();again.aircraft.step_log=None
        with gzip.open(path,'rt',encoding='utf-8') as f:lines=f.readlines()
        assert sum(line.startswith('t,x,y,z,') for line in lines)==1
        times=[float(line.split(',')[0]) for line in lines[1:]]
        assert times and min(times)>=result['checkpoint_time_s']-1e-6 and times==sorted(times)
    again.stop('End isolated fork test')


def test_fork_keeps_checkpoint_when_visual_is_incompatible(tmp_path):
    original=diverged_flight(tmp_path,'r6')
    state=json.loads(original.checkpoint_path.read_text(encoding='utf-8'))
    state['visual_identity']['sha256']='0'*64
    original.checkpoint_path.write_text(json.dumps(state),encoding='utf-8')
    before=original.checkpoint_path.read_bytes()
    restored=server.Laboratory(data_root=tmp_path)
    with pytest.raises(HTTPException,match='visual asset'):
        restored.fork_checkpoint_continuation(original.run_id,hashlib.sha256(before).hexdigest())
    assert original.checkpoint_path.read_bytes()==before and not restored.active


def test_fork_preserves_truncated_parent_gzip(tmp_path):
    original=diverged_flight(tmp_path,'phantom-a10c')
    telemetry=original.log_path/'phantom_steps.csv.gz'
    telemetry.write_bytes(telemetry.read_bytes()[:-8])
    before=telemetry.read_bytes();checkpoint=original.checkpoint_path.read_bytes()
    restored=server.Laboratory(data_root=tmp_path)
    result=restored.fork_checkpoint_continuation(original.run_id,hashlib.sha256(checkpoint).hexdigest())
    assert result['parent_run_id']==original.run_id and telemetry.read_bytes()==before
    restored.aircraft.step_log.close();restored.audit_file.close()


def test_interrupted_publish_preserves_parent_and_blocks_duplicate(tmp_path,monkeypatch):
    original=diverged_flight(tmp_path,'r6')
    checkpoint=original.checkpoint_path.read_bytes();digest=hashlib.sha256(checkpoint).hexdigest()
    parent_files={p.name:p.read_bytes() for p in original.log_path.iterdir() if p.is_file()}
    restored=server.Laboratory(data_root=tmp_path)
    real_replace=server.os.replace
    def fail_before_commit(source,target):
        if str(target)==str(restored.checkpoint_path):raise OSError('simulated interruption')
        return real_replace(source,target)
    monkeypatch.setattr(server.os,'replace',fail_before_commit)
    with pytest.raises(OSError,match='interruption'):
        restored.fork_checkpoint_continuation(original.run_id,digest)
    assert original.checkpoint_path.read_bytes()==checkpoint
    assert {p.name:p.read_bytes() for p in original.log_path.iterdir() if p.is_file()}==parent_files
    assert any(p.read_bytes()==checkpoint for p in (tmp_path/'pilot/checkpoint-history').glob('*.json'))
    transaction=json.loads((tmp_path/'pilot/fork-transactions'/f'{digest}.json').read_text())
    assert transaction['state']=='publish_started'
    with pytest.raises(HTTPException,match='transaction.*already exists'):
        restored.fork_checkpoint_continuation(original.run_id,digest)


def test_fork_preserves_partial_parent_event_log(tmp_path):
    original=diverged_flight(tmp_path,'r6')
    events=original.log_path/'events.jsonl'
    with events.open('a',encoding='utf-8') as f:f.write('{"kind":"partial')
    before=events.read_bytes();checkpoint=original.checkpoint_path.read_bytes()
    restored=server.Laboratory(data_root=tmp_path)
    result=restored.fork_checkpoint_continuation(original.run_id,hashlib.sha256(checkpoint).hexdigest())
    assert result['parent_run_id']==original.run_id and events.read_bytes()==before
    restored.audit_file.close()
