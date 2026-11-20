"""Run one unmodified A10-C per lane and compare their simultaneous swept envelopes."""
import argparse
import json
import math
from pathlib import Path
import sys

import mujoco as mj
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from vtx.phantom.plant import DT, PhantomAircraft
from vtx.world import make_world


def envelope(plane, ids):
    model,data=plane.model,plane.data
    rotation=data.geom_xmat[ids].reshape(-1,3,3)
    center=data.geom_xpos[ids]+np.einsum('ijk,ik->ij',rotation,model.geom_aabb[ids,:3])
    radius=np.einsum('ijk,ik->ij',np.abs(rotation),model.geom_aabb[ids,3:])
    return np.array([(center-radius).min(axis=0),(center+radius).max(axis=0)])


def drive(world, lane, directory):
    chamber=world.vaderland['gallery']
    offset=chamber['lane_centres_m'][lane]
    heading=1 if offset>0 else -1
    y=chamber['center'][1]+offset
    x=chamber['portal_x_m'][0]-20 if heading==1 else chamber['portal_x_m'][1]+20
    plane=PhantomAircraft(world,'phantom-a10c',start_configuration='road')
    plane.spawn(x,y,world.terrain_z(x,y))
    plane.data.qpos[3:7]=[1.,0.,0.,0.] if heading==1 else [0.,0.,0.,1.]
    mj.mj_forward(plane.model,plane.data)
    ids=np.flatnonzero((plane.model.geom_bodyid>0)&((plane.model.geom_contype|plane.model.geom_conaffinity)>0))
    initial=envelope(plane,ids)
    samples=[]
    pose=None
    for i in range(round(68/DT)):
        if i%round(.05/DT)==0:
            vx=plane.data.qvel[0]*heading
            yaw=math.atan2(plane.R()[1,0]*heading,plane.R()[0,0]*heading)
            correction=.062*(plane.data.qpos[1]-y)*heading+3.0*yaw
            effort=np.clip(.14+.35*(14.-vx),-1.,1.)
            plane.set_command(dict(yaw=float(np.clip(correction,-1,1)),wheel_drive=[max(0.,effort)]*4,brake=[max(0.,-effort)]*4))
        plane.step()
        if i%round(.01/DT)==0:
            samples.append(np.r_[plane.data.time,plane.data.qpos[:3],envelope(plane,ids).ravel(),plane.support_count()])
        if pose is None and (plane.data.qpos[0]-3200)*heading>=0:
            pose=plane.physical_snapshot()
        if plane.crashed or (plane.data.qpos[0]-x)*heading>640: break
    np.savez_compressed(directory/f'lane-{lane}.npz',samples=np.array(samples))
    if pose:
        (directory/f'lane-{lane}-pose.json').write_text(json.dumps(pose),encoding='utf-8')
    return dict(lane=lane,offset_m=offset,heading='east' if heading==1 else 'west',variant=plane.variant,
                config=plane.P.config_sha256,road_pose_enclosing_size_m=(initial[1]-initial[0]).tolist(),
                seconds=plane.data.time,final_xyz_m=plane.data.qpos[:3].tolist(),
                displacement_m=abs(plane.data.qpos[0]-x),crashed=bool(plane.crashed),
                collisions=[e for e in plane.events if e['event']=='collision'])


def compare(world, directory):
    g=world.vaderland['gallery']
    c=g['center'][1]
    runs=[json.loads((directory/f'lane-{i}.json').read_text()) for i in range(4)]
    traces=[np.load(directory/f'lane-{i}.npz')['samples'] for i in range(4)]
    for run,trace in zip(runs,traces):
        inside=trace[(trace[:,1]>=g['portal_x_m'][0])&(trace[:,1]<=g['portal_x_m'][1])]
        offset=run['offset_m']
        run['min_lane_edge_clearance_m']=float(min((inside[:,5]-(c+offset-g['lane_width_m']/2)).min(),
            ((c+offset+g['lane_width_m']/2)-inside[:,8]).min()))
        run['min_roof_clearance_m']=float((g['ceiling_z_m']-inside[:,9]).min())
        run['min_wall_clearance_m']=float(min((inside[:,5]-(c-g['clear_width_m']/2)).min(),
            ((c+g['clear_width_m']/2)-inside[:,8]).min()))
        run['minimum_wheel_support_in_bore']=int(inside[:,10].min())
    common=min(map(len,traces))
    q=np.stack([trace[:common] for trace in traces])
    simultaneous=q[:, :,4].max(axis=0)<=q[:,:,7].min(axis=0)
    if not np.any(simultaneous):raise ValueError('Four vehicles did not pass abreast')
    gaps=q[1:,:,5]-q[:-1,:,8]
    at=int(np.flatnonzero(simultaneous)[len(np.flatnonzero(simultaneous))//2])
    report=dict(world=world.environment_key,geometry=g,runs=runs,sampling_interval_s=.01,
        all_four_longitudinal_overlap_s=float(simultaneous.sum()*.01),
        seconds_at_four_abreast=float(q[0,at,0]),positions_at_four_abreast=q[:,at,1:4].tolist(),
        min_clear_between_vehicle_bounds_m=float(gaps[:,simultaneous].min()),
        min_clear_between_opposing_bounds_m=float(gaps[1,simultaneous].min()),
        min_lateral_gap_entire_run_m=float(gaps.min()))
    (directory/'traffic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('four abreast',report['all_four_longitudinal_overlap_s'],'s; minimum lateral space',
          report['min_clear_between_vehicle_bounds_m'],'m; minimum headroom',min(r['min_roof_clearance_m'] for r in runs))
    return all(not r['crashed'] and r['displacement_m']>=640 and r['min_lane_edge_clearance_m']>0 for r in runs) and gaps.min()>0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path);p.add_argument('--lane',type=int,choices=range(4))
    args=p.parse_args();w=make_world('vaderland-07')
    if args.lane is None:sys.exit(not compare(w,args.directory))
    result=drive(w,args.lane,args.directory)
    (args.directory/f'lane-{args.lane}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result)
