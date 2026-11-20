"""Compare the harbour presentation with the native fleet, harbour bed and wake."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import mujoco as mj

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from vtx.harbour_fleet import HarbourFleet
from vtx.harbour_session import _public_fleet
from vtx.world import make_world


def measure(world, directory):
    fleet=HarbourFleet(world)
    actor='ricochet-airport'
    marks=[];initial=fleet.public()
    fleet.release(actor)
    fleet.action(actor,dict(throttle=.77,rudder_deg=0.))
    start=time.perf_counter()
    for _ in range(900):
        fleet.step()
        if fleet.step_count%100==0:
            marks.append(dict(t_s=fleet.data.time,boats=[(b['id'],b['position'],b['speed_mps'],b['crashed']) for b in fleet.public()['boats']]))
    elapsed=time.perf_counter()-start
    before=fleet.data.qpos.copy()
    clock=fleet.water.sim_time_s
    durations=[]
    for _ in range(5):
        start=time.perf_counter()
        state=_public_fleet(fleet)
        durations.append((time.perf_counter()-start)*1000)
    if not np.array_equal(before,fleet.data.qpos) or clock!=fleet.water.sim_time_s:raise ValueError('Presentation changed physics')
    (directory/'fleet-state.json.gz').write_bytes(gzip.compress(json.dumps(state,separators=(',',':')).encode(),mtime=0))
    for boat in state['boats']:
        path=directory/('model-'+boat['id']+'.json.gz')
        path.write_bytes(gzip.compress(json.dumps(fleet.visual_geometry(boat['id']),separators=(',',':')).encode(),mtime=0))
    points=[];rng=np.random.default_rng(831)
    for boat in state['boats']:
        center=np.array(boat['position'][:2])
        origin=np.round(center/12)*12-48
        axis=np.arange(2.,96.,2.)
        xx,yy=np.meshgrid(origin[0]+axis,origin[1]+axis)
        samples=fleet.water.evaluate(xx,yy,eta_only=True)
        worst=np.argsort(np.where(samples.depth>.1,abs(samples.eta-state['water_level_m']),-1).ravel())[-18:]
        focus=np.column_stack((xx.ravel()[worst],yy.ravel()[worst]))
        random=center+rng.uniform(-38,38,(60,2))
        query=np.vstack((focus,random))
        sample=fleet.water.evaluate(*query.T,eta_only=True)
        for k,(p,eta,depth) in enumerate(zip(query,sample.eta,sample.depth)):
            points.append(dict(xy=p.tolist(),boat=boat['id'],lattice=k<len(focus),surface_m=float(eta),depth_m=float(depth)))
    for label,p in [('upper falls',[-4791.,4337.]),('airport runway',[0.,0.])]:
        sample=fleet.water.evaluate(*p,eta_only=True)
        points.append(dict(label=label,xy=p,lattice=False,surface_m=float(sample.eta),depth_m=float(sample.depth)))
    if not all(b['crashed'] is False for b in state['boats']):raise ValueError('Vessel collision during wake run')
    mesh_error=0.
    for patch in state.get('water_surface',{}).get('patches',[]):
        x,y=patch['origin'];xx,yy=np.meshgrid(np.arange(49)*2+x,np.arange(49)*2+y)
        truth=fleet.water.evaluate(xx,yy,eta_only=True)
        offsets=np.frombuffer(base64.b64decode(patch['offset_f32le']),'<f4').reshape(xx.shape)
        mesh_error=max(mesh_error,float(abs(offsets-np.where(truth.depth>0,truth.eta-state['water_level_m'],0)).max()))
    result=dict(world=world.environment_key,physics=state['physics'],configuration=fleet.water.config.to_dict(),
                step_wall_s=elapsed,sim_s=state['t_s'],snapshot_ms=durations,initial=initial['boats'][0]['position'],
                boat_positions=marks,native_state_sha256=hashlib.sha256(fleet.data.qpos.tobytes()+fleet.data.qvel.tobytes()).hexdigest(),
                maximum_encoded_error_m=mesh_error,water_level_m=state['water_level_m'],probes=points)
    # Exercise the other selectable vessel from its own berth, after saving
    # the common wake frame above. Both identities and models stay in place.
    second='ricochet-marina'
    fleet.action(actor,dict(throttle=0.,rudder_deg=0.))
    fleet.release(second);fleet.action(second,dict(throttle=.55,rudder_deg=0.))
    start_xy=np.asarray(next(b for b in state['boats'] if b['id']==second)['position'][:2])
    for _ in range(500):fleet.step()
    final=next(b for b in fleet.public()['boats'] if b['id']==second)
    result['second_berth']=dict(id=second,variant=final['variant'],duration_s=5.,crashed=final['crashed'],
        displacement_m=float(np.linalg.norm(np.asarray(final['position'][:2])-start_xy)),final_xyz_m=final['position'])
    structures=fleet.world.structures
    dock=structures[0];p=np.array(dock['center'])+[0,0,20.]
    gid=np.array([-1],np.int32)
    length=mj.mj_ray(fleet.model,fleet.data,p,np.array([0.,0.,-1.]),None,True,-1,gid)
    result['dock']=dict(id=dock['id'],dimensions_m=(2*np.array(dock['half_extents'])).tolist(),
        physical_geom=fleet.model.geom(int(gid[0])).name,ray_top_m=float(p[2]-length),
        specified_top_m=dock['center'][2]+dock['half_extents'][2])
    if final['crashed'] or result['second_berth']['displacement_m']<1:raise ValueError(result['second_berth'])
    (directory/'sound.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result['native_state_sha256'],elapsed,mesh_error, max(abs(p['surface_m']-state['water_level_m']) for p in points if p['depth_m']>.1))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--world',required=True)
    args=p.parse_args();measure(make_world(args.world),args.directory)
