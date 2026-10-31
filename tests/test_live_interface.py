"""Boundary tests only; these inputs are not claimed as piloted flights."""
from vtx.live_server import Action,Mission,Laboratory
from pydantic import ValidationError
from fastapi import HTTPException
import pytest

def test_pose_injection_rejected():
    with pytest.raises(ValidationError):
        Action(authority='manual',engine=0,collective_deg=[0]*4,tilt_deg=[[0,0]]*4,
               reason='Boundary bench',position=[0,0,100])

@pytest.mark.parametrize('field,value',[
    ('collective_deg',[0,0,0,31]),('tilt_deg',[[21,0]]*4),('engine',float('nan')),
])
def test_invalid_raw_actuation_rejected(field,value):
    data=dict(authority='manual',engine=0,collective_deg=[0]*4,tilt_deg=[[0,0]]*4,reason='Boundary bench')
    data[field]=value
    with pytest.raises(ValidationError):Action(**data)

def test_control_authority_and_observation_boundary():
    lab=Laboratory();lab.active=True;lab.authority='colin'
    cmd=dict(engine=0,collective_deg=[0]*4,tilt_deg=[[0,0]]*4,reason='Boundary bench')
    with pytest.raises(HTTPException):lab.accept_action(Action(authority='manual',**cmd))
    with pytest.raises(HTTPException):lab.accept_action(Action(authority='colin',observation_id=-1,**cmd))
    obs=lab.sensor_observation()
    accepted=lab.accept_action(Action(authority='colin',observation_id=obs['observation_id'],**cmd))
    assert accepted['accepted'] and accepted['apply_t_s']==pytest.approx(.02)
    assert not {'qpos','qvel','forces','cg','inertia','contact_manifold'}&obs.keys()

def test_no_time_indexed_route_command():
    with pytest.raises(ValidationError):
        Mission(departure=[0,0],destination=[30,20],waypoints=[[1,2],[3,4]])

def test_retry_archives_crash_and_preserves_learning(tmp_path,monkeypatch):
    import vtx.live_server as server
    import json,hashlib
    monkeypatch.setattr(server,'ROOT',tmp_path)
    lab=Laboratory()
    # A genuine finite-height rigid-body drop, solely a crash/retry bench check.
    started=lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18],authority='manual'))
    lab.aircraft.spawn(13.7,-28.4,4)
    for _ in range(3000):
        lab.integrate()
        if lab.aircraft.crashed:break
    assert lab.aircraft.crashed
    memory_hash=hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()
    first=started['run_id'];new=lab.retry({'authority':'manual','airframe_variant':'light'})
    old_dir=tmp_path/'evidence/flights'/first
    assert json.loads((old_dir/'summary.json').read_text())['outcome']=='collision'
    assert new['run_id']!=first
    assert lab.mission['departure']==[13.7,-28.4]
    assert not lab.aircraft.crashed and lab.aircraft.data.time==0
    assert hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()==memory_hash
    rows=[json.loads(l) for l in (lab.log_path/'events.jsonl').read_text().splitlines()]
    assert next(r for r in rows if r['kind']=='retry_lineage')['payload']['previous_run_id']==first
    with pytest.raises(HTTPException):lab.retry({'authority':'manual'})
    lab.stop('End isolated retry integration check')
    assert lab.sensor_observation()['active'] is False
