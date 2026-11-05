"""Recorded objectives and decisions are reviewable without stopping a flight."""
import asyncio
import gzip
import json
import pytest
import vtx.live_server as server
from vtx.live_server import Action, Laboratory, Mission, read_decision_timeline


def test_active_and_ended_run_timeline(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path));lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    try:
        goal=asyncio.run(server.set_objective({'run_id':run,'text':'Hold here'}))
        obs=lab.sensor_observation()
        lab.accept_action(Action(authority='colin',observation_id=obs['observation_id'],reason='Spool gently',
                                 engine=.3,collective_deg=[0]*4,tilt_deg=[[0,0]]*4))
        result=asyncio.run(server.runs());assert result[0]['run_id']==run and result[0]['active']
        timeline=asyncio.run(server.timeline(run));assert lab.active
        assert [e['kind'] for e in timeline['events']]==['objective_changed','pilot_decision']
        assert timeline['events'][0]['detail']['objective']==goal
        assert timeline['events'][1]['detail']['decision']=='Spool gently'
        assert 'observation' not in timeline['events'][1]['detail']
        lab.stop('Review test complete')
        timeline=asyncio.run(server.timeline(run))
        assert timeline['events'][-1]['kind']=='sortie_end'
        assert asyncio.run(server.runs())[0]['run_id']==run
    finally:
        if lab.active:lab.stop('cleanup')


def test_bounded_gzip_timeline_retains_latest_events(tmp_path):
    path=tmp_path/'events.jsonl.gz'
    rows=[{'kind':'objective_changed','t_s':i,'payload':{'objective':{'text':str(i)}}} for i in range(5)]
    rows.insert(2,{'kind':'physics_audit','t_s':0,'payload':{'large':'telemetry'}})
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    result=read_decision_timeline(path,limit=2)
    assert result['truncated'] and result['total_events']==5
    assert [e['detail']['objective']['text'] for e in result['events']]==['3','4']


def test_timeline_rejects_invalid_or_missing_run(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path));lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    with pytest.raises(server.HTTPException) as invalid:asyncio.run(server.timeline('../other'))
    assert invalid.value.status_code==422
    with pytest.raises(server.HTTPException) as missing:asyncio.run(server.timeline('missing-run'))
    assert missing.value.status_code==404


def test_live_log_partial_final_line_is_ignored(tmp_path):
    path=tmp_path/'events.jsonl'
    path.write_text(json.dumps({'kind':'objective_changed','t_s':1,'payload':{'objective':{'text':'Hold'}}})+'\n'+
                    json.dumps({'kind':'physics_audit','payload':{'t_s':1}})+'\n'+
                    '{"kind":"physics_audit","payload":',encoding='utf-8')
    assert read_decision_timeline(path)['total_events']==1
    assert server.read_replay_frames(path)['total_frames']==1
