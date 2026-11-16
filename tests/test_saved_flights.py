"""Save, switch environment and aircraft, restart, then continue the same flight."""
import asyncio
import json
import numpy as np
import pytest
from fastapi import HTTPException
from vtx import live_server as server
from vtx.phantom.controls import PhantomAction


@pytest.mark.parametrize('variant', ['r6', 'phantom-a10c'])
def test_saved_flight_survives_switch_and_restart(tmp_path, monkeypatch, variant):
    original = server.Laboratory(data_root=tmp_path)
    original.start(server.Mission(airframe_variant=variant, environment='airport', departure=[-700, 0],
        phantom={'start_configuration': 'road'} if variant.startswith('phantom') else None))
    for _ in range(120):
        original.integrate()
    if variant.startswith('phantom'):
        action = PhantomAction.model_validate({'schema':'phantom-fbw-1','authority':'manual',
            'reason':'Saved control patch','wing':'deploy'})
    else:
        action = server.Action(authority='manual',reason='Saved control patch',engine=.6,
            collective_deg=[3,3,3,3],tilt_deg=[[0,0]]*4)
    original.accept_action(action)
    run_id=original.run_id
    old_time=float(original.aircraft.data.time)
    original.save_flight_for_switching(run_id)
    saved=original.saved_flights_path/(run_id+'.json')
    before=saved.read_bytes()
    assert not original.active and not original.checkpoint_path.exists()
    assert not (original.log_path/'summary.json').exists()

    restarted=server.Laboratory(data_root=tmp_path)
    assert not restarted.active and saved.read_bytes()==before
    assert not (original.log_path/'summary.json').exists()
    assert restarted.saved_flights()[0]['variant']==variant
    monkeypatch.setattr(server,'lab',restarted)
    asyncio.run(server.set_environment({'environment':'sandbox'}))
    asyncio.run(server.model_preview({'environment':'sandbox','airframe_variant':'phantom-a10b',
        'start_configuration':'road','departure':[-700,0]}))
    assert restarted.world.environment_key=='sandbox'
    result=restarted.restore_saved_flight(run_id)
    assert result['paused'] and restarted.active and restarted.paused
    assert restarted.world.environment_key=='airport' and restarted.run_id==run_id
    assert restarted.aircraft.data.time==pytest.approx(old_time)
    assert restarted.next_pending_action==0 and not restarted.action_log[0].get('cancelled')
    assert not saved.exists()
    assert [p.read_bytes() for p in (tmp_path/'pilot/checkpoint-history').glob('*.json')]==[before]

    # Resume both copies offline and compare their physical continuation.
    original.active=True
    original.checkpoint=lambda *args,**kwargs:None
    restarted.checkpoint=lambda *args,**kwargs:None
    for _ in range(120):
        original.integrate();restarted.integrate()
    np.testing.assert_allclose(restarted.aircraft.data.qpos,original.aircraft.data.qpos,rtol=1e-8,atol=1e-7)
    np.testing.assert_allclose(restarted.aircraft.data.qvel,original.aircraft.data.qvel,rtol=1e-8,atol=1e-7)
    assert restarted.next_pending_action==1
    restarted.stop('End isolated saved-flight test')


def test_incompatible_saved_flight_is_not_replaced(tmp_path):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant='r6'))
    run_id=lab.run_id
    lab.save_flight_for_switching(run_id)
    saved=lab.saved_flights_path/(run_id+'.json')
    state=json.loads(saved.read_text(encoding='utf-8'))
    state['runtime_source_sha256']='f'*64
    saved.write_text(json.dumps(state),encoding='utf-8')
    before=saved.read_bytes()
    with pytest.raises(HTTPException,match='requires runtime'):
        lab.restore_saved_flight(run_id)
    assert not lab.active and saved.read_bytes()==before
    assert not lab.checkpoint_path.exists()


@pytest.mark.parametrize('failure', ['selection', 'archive'])
def test_post_restore_io_failure_reports_the_paused_restoration(tmp_path,monkeypatch,failure):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant='r6'))
    run_id=lab.run_id
    lab.save_flight_for_switching(run_id)
    saved=lab.saved_flights_path/(run_id+'.json')
    original=saved.read_bytes()
    if failure=='selection':
        def fail_selection(*args,**kwargs):raise OSError('injected selection failure')
        monkeypatch.setattr(lab,'_remember_inspection_selection',fail_selection)
    else:
        real_rename=type(saved).rename
        def fail_archive(path,*args,**kwargs):
            if path==saved:raise OSError('injected archive failure')
            return real_rename(path,*args,**kwargs)
        monkeypatch.setattr(type(saved),'rename',fail_archive)
    result=lab.restore_saved_flight(run_id)
    assert result['restored'] and result['paused'] and 'injected' in result['warning']
    assert lab.active and lab.paused and lab.run_id==run_id
    assert lab.checkpoint_path.read_bytes()==original
    assert lab.recovery_notice==result['warning']
    retained=([saved] if saved.exists() else list((tmp_path/'pilot/checkpoint-history').glob('*.json')))
    assert any(path.read_bytes()==original for path in retained)
    lab.audit_file.close()


@pytest.mark.parametrize('variant', ['r6', 'phantom-a10c'])
def test_recovery_refuses_to_append_behind_newer_evidence(tmp_path, variant):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant=variant))
    for _ in range(400):lab.integrate()
    lab.checkpoint(force=True)
    # Simulate evidence flushed after the last durable checkpoint and a crash.
    lab.checkpoint=lambda *args,**kwargs:None
    for _ in range(80):lab.integrate()
    if getattr(lab.aircraft,'is_phantom',False):lab.aircraft.step_log.close()
    lab.audit_file.close()
    checkpoint_before=lab.checkpoint_path.read_bytes()
    events=lab.log_path/'events.jsonl';events_before=events.read_bytes()
    recovered=server.Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert 'extends beyond the checkpoint' in recovered.error
    assert lab.checkpoint_path.read_bytes()==checkpoint_before
    assert events.read_bytes()==events_before
    assert not (lab.log_path/'summary.json').exists()
