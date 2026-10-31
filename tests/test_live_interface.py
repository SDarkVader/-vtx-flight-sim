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

@pytest.mark.parametrize('fuel',[0.,-1.,110.1,float('nan'),float('inf')])
def test_invalid_fuel_loading_rejected(fuel):
    with pytest.raises(ValidationError):
        Mission(departure=[0,0],destination=[30,20],fuel_kg=fuel)

def test_selected_fuel_changes_real_mass_and_inertia(tmp_path,monkeypatch):
    import vtx.live_server as server
    import json,numpy as np
    monkeypatch.setattr(server,'ROOT',tmp_path)
    lab=Laboratory()
    mission=dict(departure=[13.7,-28.4],destination=[-45,18],authority='manual')
    lab.start(Mission(**mission))
    light=lab.aircraft.mass_properties()
    np.testing.assert_allclose(lab.aircraft.fuel_initial,[2.5]*4)
    assert lab.sensor_observation()['configuration']['initial_fuel_kg']==10.
    metadata=json.loads((lab.log_path/'metadata.json').read_text())
    assert metadata['request']['fuel_kg']==10.
    lab.stop('End isolated reduced-fuel mass check')
    lab.start(Mission(**mission,fuel_kg=60.))
    full=lab.aircraft.mass_properties()
    assert full['mass_kg']-light['mass_kg']==pytest.approx(50.)
    assert not np.allclose(full['cg_world_m'],light['cg_world_m'])
    assert not np.allclose(full['inertia_world_kg_m2'],light['inertia_world_kg_m2'])
    assert np.linalg.eigvalsh(light['inertia_world_kg_m2']).min()>0
    lab.stop('End isolated original-fuel mass check')

def test_retry_preserves_or_explicitly_changes_fuel(tmp_path,monkeypatch):
    import vtx.live_server as server
    import json,hashlib
    monkeypatch.setattr(server,'ROOT',tmp_path)
    lab=Laboratory()
    started=lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18],fuel_kg=20.))
    lab.stop('End isolated fuel-selection check')
    original=lab.log_path
    summary_bytes=(original/'summary.json').read_bytes()
    memory_hash=hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()
    preserved=lab.retry({'authority':'manual'})
    assert preserved['run_id']!=started['run_id']
    assert lab.aircraft.fuel_initial.sum()==pytest.approx(20.)
    lab.stop('End isolated fuel-preserving retry')
    changed=lab.retry({'authority':'manual','fuel_kg':10.})
    assert changed['run_id']!=preserved['run_id']
    assert lab.aircraft.fuel_initial.sum()==pytest.approx(10.)
    rows=[json.loads(l) for l in (lab.log_path/'events.jsonl').read_text().splitlines()]
    lineage=next(r['payload'] for r in rows if r['kind']=='retry_lineage')
    assert lineage['previous_fuel_kg']==20. and lineage['new_fuel_kg']==10.
    assert (original/'summary.json').read_bytes()==summary_bytes
    assert hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()==memory_hash
    lab.stop('End isolated reduced-fuel retry')
    # Historical metadata predating the fuel field always represented 60 kg.
    lab.retry_hint['request'].pop('fuel_kg')
    lab.retry({'authority':'manual'})
    assert lab.aircraft.fuel_initial.sum()==pytest.approx(60.)
    lab.stop('End isolated legacy fuel compatibility check')

def test_retry_archives_crash_and_preserves_learning(tmp_path,monkeypatch):
    import vtx.live_server as server
    import json,hashlib
    monkeypatch.setattr(server,'ROOT',tmp_path)
    lab=Laboratory()
    # Keep the original 60 kg drop fixture: the lighter 10 kg case can settle
    # without a body strike, which must not be relabelled a crash for this test.
    started=lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18],authority='manual',fuel_kg=60.))
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

def test_cabin_gimbal_accepts_yaw_and_legacy_controls():
    base=dict(authority='manual',engine=0,collective_deg=[0]*4,tilt_deg=[[0,0]]*4,reason='Cabin control bench')
    assert Action(**base,cabin_deg=[1,-2,180]).cabin_deg==[1,-2,180]
    assert Action(**base,cabin_deg=[1,-2]).cabin_deg==[1,-2,0.]
    with pytest.raises(ValidationError):Action(**base,cabin_deg=[0,0,181])


def test_cabin_level_assistance_uses_physical_joints():
    import numpy as np
    import mujoco as mj
    from scipy.spatial.transform import Rotation
    from vtx.aircraft import Aircraft
    aircraft=Aircraft()
    q=Rotation.from_euler('x',10,degrees=True).as_quat()
    aircraft.data.qpos[3:7]=[q[3],q[0],q[1],q[2]]
    mj.mj_forward(aircraft.model,aircraft.data)
    aircraft.engine_spool=1.
    aircraft.set_command(dict(engine=1.,collective_deg=[0.]*4,tilt_deg=[[0.,0.]]*4,cabin_deg=[0.,0.,90.],cabin_level=True))
    for _ in range(20):aircraft.step()
    assert aircraft.cabin_target[0]<0
    assert aircraft.cabin_target[2]>0
    assert aircraft.joint('cabin_x')[0]<0
    assert aircraft.joint('cabin_z')[0]>0
    assert np.isfinite(aircraft.data.qpos).all()
