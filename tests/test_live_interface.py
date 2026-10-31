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
