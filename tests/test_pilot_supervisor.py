"""Exercise real child-process failure against an isolated flight server."""
import asyncio
import json
import sys
import time
from urllib.error import URLError
import vtx.live_server as server
from vtx.live_server import Laboratory, Mission
from tools.pilot_supervisor import Supervisor

ADAPTER = r'''
import json,sys
for line in sys.stdin:
    state=json.loads(line)
    obs=state['observation']
    out={'type':'action','action':{'observation_id':obs['observation_id'],
        'reason':'Following: '+(state['objective'] or {}).get('text','no objective'),'engine':0.4,
        'collective_deg':[0,0,0,0],'tilt_deg':[[0,0]]*4}}
    print(json.dumps(out),flush=True)
'''

def step_until(sup, condition):
    for _ in range(250):
        assert sup.tick()
        if condition(): return
        time.sleep(.01)
    raise AssertionError(f'condition not reached; state={sup.state}')

def test_adapter_death_failover_preserves_flight_and_objective(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    objective=asyncio.run(server.set_objective({'text':'Take us to the airport'}))
    def call(base,path,data=None):
        if path == "/api/view": return lab.view()
        if path == "/api/observe": return lab.sensor_observation()
        if path == "/api/pilot/handover": return asyncio.run(server.pilot_handover(data))
        if path == "/api/pilot/failure": return asyncio.run(server.pilot_failure(data))
        if path == "/api/action": return lab.accept_action(server.parse_action(data))
        raise AssertionError(path)
    specs=[{'id':'model-a','command':[sys.executable,'-u','-c',ADAPTER]},
           {'id':'model-b','command':[sys.executable,'-u','-c',ADAPTER]}]
    sup=Supervisor('local',run,specs,call=call)
    try:
        step_until(sup,lambda:len(lab.action_log)>0)
        assert lab.pilot_owner=='model-a'
        sup.provider.process.kill();sup.provider.process.wait(timeout=5)
        step_until(sup,lambda:lab.pilot_owner=='model-b' and len(lab.action_log)>1)
        assert lab.active and lab.run_id==run and lab.objective==objective
        assert lab.action_log[-1]['decision']=='Following: Take us to the airport'
        assert lab.fallback_status is None  # replacement has taken over
        text=(lab.log_path/'events.jsonl').read_text(encoding='utf-8')
        assert 'pilot_provider_failed' in text and 'model-a' in text
        assert 'unavailable' in text  # ground state cannot claim stable hold
    finally:
        sup.close();lab.stop('supervisor test complete')

def test_disconnect_is_not_provider_failure(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    down=[False]
    def call(base,path,data=None):
        if down[0]: raise URLError('temporary disconnect')
        if path == "/api/view": return lab.view()
        if path == "/api/observe": return lab.sensor_observation()
        if path == "/api/pilot/handover": return asyncio.run(server.pilot_handover(data))
        if path == "/api/pilot/failure": return asyncio.run(server.pilot_failure(data))
        if path == "/api/action": return lab.accept_action(server.parse_action(data))
        raise AssertionError(path)
    sup=Supervisor('local',run,[{'id':'model-a','command':[sys.executable,'-u','-c',ADAPTER]}],call=call)
    try:
        step_until(sup,lambda:len(lab.action_log)>0)
        pid=sup.provider.process.pid;epoch=sup.epoch
        down[0]=True
        try: sup.tick()
        except URLError: pass
        down[0]=False
        assert sup.tick() and sup.provider.process.pid==pid and sup.epoch==epoch
        assert lab.pilot_owner=='model-a' and lab.fallback_status is None
    finally:
        sup.close();lab.stop('reconnect test complete')


def test_lost_handover_response_still_reports_child_exit(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id'];lost=[True]
    def call(base,path,data=None):
        if path == '/api/view': return lab.view()
        if path == '/api/pilot/handover':
            result=asyncio.run(server.pilot_handover(data))
            if lost[0]:
                lost[0]=False
                raise URLError('response lost after handover')
            return result
        if path == '/api/pilot/failure': return asyncio.run(server.pilot_failure(data))
        if path == '/api/observe': return lab.sensor_observation()
        if path == '/api/action': return lab.accept_action(server.parse_action(data))
        raise AssertionError(path)
    sup=Supervisor('local',run,[{'id':'model-a','command':[sys.executable,'-u','-c',ADAPTER]}],call=call)
    try:
        try: sup.tick()
        except URLError: pass
        assert lab.pilot_owner=='model-a' and sup.epoch is None
        sup.provider.process.kill();sup.provider.process.wait(timeout=5)
        assert sup.tick() and sup.failure is not None
        assert not sup.tick() and sup.state=='providers_exhausted'
        assert lab.fallback_status['state']=='unavailable' and lab.active
    finally:
        sup.close();lab.stop('lost handover response test complete')


def test_provider_reports_real_connection_failure_and_replacement_takes_over(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    objective=asyncio.run(server.set_objective({'text':'Hold here'}))
    def call(base,path,data=None):
        if path == '/api/view': return lab.view()
        if path == '/api/observe': return lab.sensor_observation()
        if path == '/api/pilot/handover': return asyncio.run(server.pilot_handover(data))
        if path == '/api/pilot/failure': return asyncio.run(server.pilot_failure(data))
        if path == '/api/action': return lab.accept_action(server.parse_action(data))
        raise AssertionError(path)
    broken="import sys,json,time\nsys.stdin.readline()\nprint(json.dumps({'type':'failure','reason':'AI provider disconnected'}),flush=True)\ntime.sleep(10)"
    specs=[{'id':'model-a','command':[sys.executable,'-u','-c',broken]},
           {'id':'model-b','command':[sys.executable,'-u','-c',ADAPTER]}]
    sup=Supervisor('local',run,specs,call=call)
    try:
        step_until(sup,lambda:lab.pilot_owner=='model-b' and len(lab.action_log)>0)
        assert lab.objective==objective and lab.active
        assert 'AI provider disconnected' in (lab.log_path/'events.jsonl').read_text(encoding='utf-8')
    finally:
        sup.close();lab.stop('provider failure message test complete')
