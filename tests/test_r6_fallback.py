"""Failure handover and controller state, using isolated simulator data."""
import asyncio
import pytest
from fastapi import HTTPException
import vtx.live_server as server
from vtx.live_server import Action, Laboratory, Mission
from vtx.r6_hold import R6HoldController


def test_ground_failure_reports_unavailable_and_preserves_flight(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    objective=asyncio.run(server.set_objective({'text':'Take us to the airport'}))
    pilot=asyncio.run(server.pilot_handover({'run_id':run,'pilot_id':'model-a','expected_epoch':0}))
    obs=lab.sensor_observation()
    lab.accept_action(Action(authority='colin',pilot_id='model-a',pilot_epoch=pilot['pilot_epoch'],
        pilot_run_id=run,observation_id=obs['observation_id'],reason='Spool',engine=.4,
        collective_deg=[0]*4,tilt_deg=[[0,0]]*4))
    for _ in range(20):lab.integrate()
    assert lab.aircraft.command['engine']==.4
    result=asyncio.run(server.pilot_failure({'run_id':run,'pilot_id':'model-a',
        'pilot_epoch':pilot['pilot_epoch'],'reason':'Provider failed'}))
    assert result['fallback']['state']=='unavailable'
    assert result['objective']==objective and lab.run_id==run and lab.active
    assert lab.aircraft.command['engine']==.4
    with pytest.raises(HTTPException):
        asyncio.run(server.pilot_failure({'run_id':run,'pilot_id':'model-a',
            'pilot_epoch':pilot['pilot_epoch'],'reason':'Old provider'}))
    lab.stop('Fallback test complete')


def test_hold_snapshot_round_trip():
    obs=dict(configuration=dict(airframe_variant='r6',reference_rpm=1200,engine_power_limit_kw=300),
             warning_lamps=[],radar_clearance_m=9.7,gear_compression_m=[0]*6,
             rotor_rpm=[1200]*4,gnss_xy_m=[2,3],attitude_xyz_deg=[0,0,0],
             gnss_velocity_mps=[0,0,0],gyro_world_deg_s=[0,0,0],t_s=20)
    hold=R6HoldController(obs)
    next_obs={**obs,'t_s':20.05,'gnss_xy_m':[2.2,3.1]}
    hold.decide(next_obs)
    restored=R6HoldController.restore(hold.snapshot())
    assert restored.snapshot()==hold.snapshot()
    assert restored.decide({**next_obs,'t_s':20.1})==hold.decide({**next_obs,'t_s':20.1})


def test_airborne_failure_and_checkpoint_keep_hold_and_objective(tmp_path,monkeypatch):
    import mujoco as mj
    import math
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    goal=asyncio.run(server.set_objective({'text':'Fly to B'}))
    owner=asyncio.run(server.pilot_handover({'run_id':run,'pilot_id':'model-a','expected_epoch':0}))
    p=lab.aircraft;p.data.qpos[2]=10
    for i in range(1,7):p.data.qpos[p.qadr[f'gear{i}_stroke']]=0
    for i in range(1,5):p.data.qvel[p.vadr[f'rotor{i}_spin']]=1200*2*math.pi/60
    mj.mj_forward(p.model,p.data)
    lab.last_obs=None;lab.last_sensor_t=-1
    result=asyncio.run(server.pilot_failure({'run_id':run,'pilot_id':'model-a',
        'pilot_epoch':owner['pilot_epoch'],'reason':'Injected failure'}))
    assert result['fallback']['state']=='active' and result['objective']==goal
    assert lab.fallback_controller is not None
    snapshot=lab.fallback_controller.snapshot()
    lab.checkpoint(force=True);lab.audit_file.close();lab.audit_file=None
    recovered=Laboratory()
    assert recovered.run_id==run and recovered.paused and recovered.objective==goal
    assert recovered.fallback_controller.snapshot()==snapshot
    assert recovered.fallback_status['state']=='active'
    monkeypatch.setattr(server,'lab',recovered)
    pending=asyncio.run(server.pilot_handover({'run_id':run,'pilot_id':'model-b',
                                                'expected_epoch':recovered.pilot_epoch}))
    assert pending['pending'] and recovered.fallback_controller is not None
    assert recovered.pilot_owner=='r6-deterministic-hold' and recovered.pending_pilot=='model-b'
    command=dict(authority='colin',pilot_id='model-b',pilot_epoch=pending['pilot_epoch'],
                 pilot_run_id=run,reason='Continue flight',engine=1,
                 collective_deg=[17]*4,tilt_deg=[[0,0]]*4)
    with pytest.raises(HTTPException):
        recovered.accept_action(Action(observation_id=-1,**command))
    assert recovered.fallback_controller is not None
    obs=recovered.sensor_observation()
    recovered.accept_action(Action(observation_id=obs['observation_id'],**command))
    assert recovered.pilot_owner=='model-b' and recovered.pending_pilot is None
    assert recovered.fallback_controller is None and recovered.objective==goal
    recovered.stop('Fallback checkpoint test complete')
