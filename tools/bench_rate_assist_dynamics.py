import math,json
import numpy as np,mujoco as mj
from vtx.aircraft import Aircraft

def run(level,axis):
 p=Aircraft(rpm=1200,fuel_kg=10,engine_power_limit_kw=300);p.spawn(0,0,20);p.stability_assist=level;p._bench_apply_experimental_assist=True;p.engine_spool=1.;p.pitch[:]=10
 p.set_command(dict(engine=1.,collective_deg=[10.]*4,tilt_deg=[[0.,0.]]*4,cabin_deg=[0.,0.,0.],cabin_level=True))
 p.data.qvel[3+axis]=math.radians(10)
 for i,sign in enumerate([1,-1,1,-1],1):
  p.data.qvel[p.vadr[f'rotor{i}_spin']]=sign*1200*2*math.pi/60
  p.data.qvel[p.vadr[f'shaft{i}_spin']]=sign*6016*2*math.pi/60
 mj.mj_forward(p.model,p.data)
 vals=[]
 for step in range(400):
  p.step()
  if step in [0,199,399]:
   vel=np.zeros(6);mj.mj_objectVelocity(p.model,p.data,mj.mjtObj.mjOBJ_XBODY,p.bids['airframe'],vel,1)
   vals.append(dict(t=round(float(p.data.time),3),rate_deg_s=round(math.degrees(vel[axis]),3),clearance=round(float(p.data.qpos[2]),3),pitch=[round(float(x),3) for x in p.pitch]))
 return dict(assist=level,axis=['roll','pitch'][axis],observations=vals,crashed=p.crashed)
print(json.dumps([run(level,axis) for axis in range(2) for level in [0,.5,1]],indent=2))
