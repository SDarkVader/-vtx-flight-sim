import asyncio
import json
from fastapi import HTTPException
import pytest
import vtx.live_server as server


def test_provider_failure_preserves_the_active_run(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab=server.Laboratory()
    monkeypatch.setattr(server, 'lab', lab)
    lab.start(server.Mission(airframe_variant='phantom-fx', authority='colin', time_scale=.05))
    original=lab.run_id
    owner=asyncio.run(server.pilot_handover({'run_id':original,'pilot_id':'pilot-a','expected_epoch':0}))
    result=asyncio.run(server.pilot_failure({'run_id':original,'pilot_id':'pilot-a','pilot_epoch':owner['pilot_epoch'],'reason':'Provider stopped'}))
    assert result['run_id']==original and result['fallback']['state']=='unavailable'
    assert lab.active and lab.run_id==original and lab.authority=='colin'
    assert (lab.log_path/'events.jsonl').exists()
    lab.stop('test complete')


def test_stale_failure_cannot_reset_another_run(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab=server.Laboratory(); monkeypatch.setattr(server,'lab',lab)
    lab.start(server.Mission(airframe_variant='phantom-fx', authority='colin'))
    original=lab.run_id
    owner=asyncio.run(server.pilot_handover({'run_id':original,'pilot_id':'pilot-a','expected_epoch':0}))
    with pytest.raises(HTTPException):
        asyncio.run(server.pilot_failure({'run_id':'stale','pilot_id':'pilot-a','pilot_epoch':owner['pilot_epoch'],'reason':'Lost'}))
    assert lab.run_id==original and lab.active
    lab.stop('test complete')


def test_phantom_crash_preserves_ring_and_stops_run(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=server.Laboratory()
    lab.start(server.Mission(airframe_variant='phantom-fx',authority='manual'))
    original=lab.run_id
    crashed_aircraft=lab.aircraft
    monkeypatch.setattr(crashed_aircraft,'step',lambda: setattr(crashed_aircraft,'crashed',True))
    lab.integrate()
    folder=tmp_path/'evidence'/'flights'/original
    assert not lab.active and lab.run_id==original
    assert (folder/'crash_ring.npz').exists()
    assert json.loads((folder/'summary.json').read_text())['outcome']=='collision'
    assert json.loads((folder/'engineering_findings.json').read_text())['causal_analysis']=='Not assessed'


def test_findings_access_and_unknowns(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=server.Laboratory(); monkeypatch.setattr(server,'lab',lab)
    lab.start(server.Mission(airframe_variant='phantom-fx'))
    original=lab.run_id
    lab.reset_after_failure('Isolated finding check')
    data=asyncio.run(server.run_findings(original))
    assert data['pilot_summary']['run_id']==original
    assert data['engineering_findings']['causal_analysis']=='Not assessed'
    with pytest.raises(HTTPException): asyncio.run(server.run_findings('../bad'))
    lab.stop('test complete')


def test_historical_index_reads_summaries_without_changing_them(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    folder=tmp_path/'VTX'/'r6-live'/'evidence'/'flights'/'historic-run'
    folder.mkdir(parents=True)
    path=folder/'summary.json'
    original=json.dumps({'run_id':'historic-run','outcome':'historical flag','simulated_seconds':12.0})
    path.write_text(original,encoding='utf-8')
    result=asyncio.run(server.archive_runs())
    assert result['records'][0]['run_id']=='historic-run'
    assert result['records'][0]['recorded_outcome']=='historical flag'
    assert result['records'][0]['source']=='r6-live'
    assert path.read_text(encoding='utf-8')==original


@pytest.mark.parametrize('mode,expected_pods,expected_legs',[('vtol',90,0.52),('road',0,0)])
def test_phantom_start_configuration_actual_joints(tmp_path,monkeypatch,mode,expected_pods,expected_legs):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=server.Laboratory()
    lab.start(server.Mission(airframe_variant='phantom-fx',phantom={'start_configuration':mode},time_scale=.02))
    obs=lab.sensor_observation()
    assert obs['pod_tilt_deg']==pytest.approx([expected_pods]*4,abs=.1)
    assert obs['leg_extension_m']==pytest.approx([expected_legs]*4,abs=.01)
    assert obs['configuration']['config_sha256']=='70089ccace22e4ce1cfd28104654257fe4d03771c4f6b1faa3c89fce253247dd'
    lab.stop('test complete')


def test_wheel_pod_and_leg_commands_are_independent(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=server.Laboratory()
    lab.start(server.Mission(airframe_variant='phantom-fx',phantom={'start_configuration':'vtol'},time_scale=.02))
    obs=lab.sensor_observation()
    action=server.PhantomAction(schema='phantom-fbw-1',authority='manual',observation_id=obs['observation_id'],reason='Isolated pod articulation',pod_tilt_deg=[0]*4)
    lab.accept_action(action)
    for _ in range(30): lab.integrate()
    assert lab.aircraft.fcc.cmd['pod_tilt_deg']==[0]*4
    assert lab.aircraft.fcc.cmd['leg_extension_m']==pytest.approx([.52]*4)
    obs=lab.sensor_observation()
    lab.accept_action(server.PhantomAction(schema='phantom-fbw-1',authority='manual',observation_id=obs['observation_id'],reason='Isolated leg actuation',leg_extension_m=[0]*4))
    for _ in range(30): lab.integrate()
    assert lab.aircraft.fcc.cmd['pod_tilt_deg']==[0]*4
    assert lab.aircraft.fcc.cmd['leg_extension_m']==[0]*4
    lab.stop('test complete')
