import math,json
import mujoco as mj,numpy as np
from vtx.aircraft import Aircraft,DT
from vtx.training_assist import assisted_collective

def moment_for(rate,level):
 p=Aircraft(rpm=1200,fuel_kg=10,engine_power_limit_kw=300)
 p.spawn(0,0,10)
 for i,sign in enumerate([1,-1,1,-1],1):
  p.data.qvel[p.vadr[f'rotor{i}_spin']]=sign*1200*2*math.pi/60
 mj.mj_forward(p.model,p.data)
 p.pitch=np.array(assisted_collective([10.]*4,rate,level));p.refresh_aero()
 center=p.data.xpos[p.bids['airframe']].copy();moment=np.zeros(3)
 for i in range(4):
  bid=p.bids[f'rotor{i+1}'];axis=p.data.xmat[bid].reshape(3,3)[:,2];force=p.rotors[i]['thrust_n']*axis
  moment+=np.cross(p.data.xpos[bid]-center,force)
 return {'rate_deg_s':rate,'level':level,'collective_deg':p.pitch.tolist(),'aero_moment_nm':moment.tolist()}
print(json.dumps([moment_for(rate,level) for rate in ([10,0,0],[0,10,0]) for level in (0,.5,1)],indent=2))
