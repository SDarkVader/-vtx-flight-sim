"""Gimbal disturbance benches; not a simulated or real flight demonstration."""
import math
import numpy as np
import mujoco as mj
import pytest
from scipy.spatial.transform import Rotation
from vtx.aircraft import Aircraft
from vtx.live_server import Action


def cabin_motion(powered, body_rate_deg_s=0):
    p=Aircraft(rpm=1200,fuel_kg=10,airframe_variant='r6',engine_power_limit_kw=300)
    p.spawn(0,0,200)
    p.model.opt.gravity[:]=0  # isolated attitude disturbance, not a flight
    tilt=10 if powered else 0
    q=Rotation.from_euler('x',tilt,degrees=True).as_quat()
    p.data.qpos[3:7]=[q[3],*q[:3]]
    p.data.qvel[p.vadr['cabin_x']]=math.radians(20 if powered else 2)
    p.data.qvel[4]=math.radians(body_rate_deg_s)
    mj.mj_forward(p.model,p.data)
    p.engine_spool=1 if powered else 0
    p.command['engine']=1 if powered else 0
    p.command['cabin_level']=True
    angles=[];rates=[]
    for i in range(1600):
        p.step()
        if i%20==0:
            rotation=p.data.xmat[p.bids['cabin']].reshape(3,3)
            angles.append(math.degrees(math.acos(np.clip(rotation[2,2],-1,1))))
            velocity=np.zeros(6)
            mj.mj_objectVelocity(p.model,p.data,mj.mjtObj.mjOBJ_XBODY,p.bids['cabin'],velocity,0)
            rates.append(math.degrees(np.linalg.norm(velocity[:2])))
    return p,angles,rates


@pytest.mark.parametrize('body_rate',[0,3])
def test_powered_gimbal_damps_disturbance_and_recovers_level(body_rate):
    p,angles,rates=cabin_motion(True,body_rate)
    assert max(rates)<30
    assert np.mean(rates[-10:])<.2
    assert np.mean(angles[-10:])<.3
    assert max(abs(p.joint('cabin_'+a)[0]) for a in 'xy')<=math.radians(15.1)
    assert all(abs(t['applied_nm'])<=t['limit_nm']+1e-9 for t in p.actuator_telemetry['cabin'].values())
    assert p.energy['servo_j']>0


def test_unpowered_joint_damping_reduces_motion_without_engine_energy():
    p,angles,rates=cabin_motion(False)
    assert rates[0]>1.9
    assert np.mean(rates[-10:])<.2
    assert p.energy['engine_j']==0
    assert p.energy['servo_j']==0
    # Passive damping slows drift; it does not promise active leveling.
    assert angles[-1]>1


def test_travel_limit_is_reported_instead_of_claiming_level():
    p=Aircraft()
    p.spawn(0,0,30)
    q=Rotation.from_euler('x',30,degrees=True).as_quat()
    p.data.qpos[3:7]=[q[3],*q[:3]]
    mj.mj_forward(p.model,p.data)
    p.command['cabin_level']=True
    p.step()
    assert p.cabin_level_limited


def test_leveling_is_default_and_can_be_explicitly_disabled():
    base=dict(authority='manual',reason='Test cabin mode',engine=0,
              collective_deg=[0]*4,tilt_deg=[[0,0]]*4)
    assert Action(**base).cabin_level is True
    assert Action(**base,cabin_level=False).cabin_level is False
