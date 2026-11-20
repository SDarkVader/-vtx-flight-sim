"""Drive the real road plant on the survey, then inspect the gallery and the marine fleet."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

import mujoco as mj
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from vtx.world import make_world
from vtx.phantom.plant import PhantomAircraft, DT
from vtx.harbour_fleet import HarbourFleet


def drive(w,origin,heading,seconds,road,exit_x=None,floor=None):
    a=PhantomAircraft(w,'phantom-a10c',start_configuration='road')
    x,y=origin;a.spawn(x,y,w.terrain_z(x,y) if floor is None else floor)
    a.data.qpos[3:7]=[math.cos(heading/2),0,0,math.sin(heading/2)]
    mj.mj_forward(a.model,a.data)
    a.set_command(dict(brake=[0.]*4,wheel_drive=[.8]*4))
    track=[];contacts=set();p=np.array(road['points']);ab=np.diff(p,axis=0)
    for _ in range(seconds):
        for _ in range(round(1/DT)):
            a.step()
            for contact in a.data.contact:
                for id_ in contact.geom:
                    if a.model.geom_bodyid[id_]==0:contacts.add(a.model.geom(int(id_)).name)
        xyz=a.data.qpos[:3].copy()
        offsets=xyz[:2]-p[:-1]
        t=np.clip(np.sum(offsets*ab,axis=1)/np.maximum(np.sum(ab**2,axis=1),1e-12),0,1)
        lateral=np.min(np.linalg.norm(offsets-t[:,None]*ab,axis=1))
        track.append(dict(t=a.data.time,xyz=xyz.tolist(),speed=float(np.linalg.norm(a.data.qvel[:2])),
                     lateral_m=float(lateral),wheel_support=a.support_count(),crashed=bool(a.crashed)))
        if a.crashed or (exit_x is not None and xyz[0]>=exit_x):break
    return dict(origin=origin,heading_rad=heading,road=road['name'],width_m=road['width_m'],
                displacement_m=float(np.linalg.norm(a.data.qpos[:2]-origin)),samples=track,contacts=sorted(contacts))


def harbour(w):
    start=time.perf_counter()
    fleet=HarbourFleet(w)
    compiled=time.perf_counter()-start
    boat='ricochet-airport'
    def fix():
        craft=next(b for b in fleet.public()['boats'] if b['id']==boat)
        return {k:craft[k] for k in ('position','speed_mps','heading_rad','crashed','dockedAt','variant')}
    initial=fix()
    fleet.release(boat)
    fleet.action(boat,dict(throttle=.30,rudder_deg=0.))
    track=[]
    start=time.perf_counter()
    for i in range(500):
        fleet.step()
        if i%50==49:track.append(fix())
    return dict(world_sha256=fleet.world_sha256,compile_s=compiled,wall_s=time.perf_counter()-start,
                t_sim_s=5.,initial=initial,final=track[-1],samples=track,
                displacement_m=float(np.linalg.norm(np.array(track[-1]['position'][:2])-initial['position'][:2])))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--world',required=True)
    parser.add_argument('--marine',action='store_true')
    args=parser.parse_args()
    w=make_world(args.world)
    if args.marine:
        result=harbour(w)
        (args.directory/'marine.json').write_text(json.dumps(result,indent=2))
        print('Marine',result['final'],result['displacement_m'],result['wall_s'])
        return result['final']['crashed'] or result['displacement_m']<1
    roads={r['name']:r for r in w.vaderland['routes']}
    boulevard=roads['Exchange Boulevard'];p=np.array(boulevard['points'])
    i=np.argmin(abs(p[:,0]+920))
    delta=p[i+1]-p[i]
    city=drive(w,p[i].tolist(),math.atan2(delta[1],delta[0]),10,boulevard)
    result=dict(city=city)
    if 'Cut-and-cover gallery' in roads:
        bridge=roads['Falls bridge']
        start=np.array(bridge['points'][0])
        end=np.array(bridge['points'][-1])
        result['bridge']=drive(w,[float(start[0]-27),float(start[1])],0,47,bridge,float(end[0]+24))
        # Start on its straight western apron and retain the complete crossing.
        gallery=dict(roads['Cut-and-cover gallery'],points=[[2840,-4350],[3560,-4350]])
        result['tunnel']=drive(w,[2845.,-4350.],0,50,gallery,3520.)
        a=PhantomAircraft(w,'phantom-a10c',start_configuration='road')
        chamber=w.vaderland.get('gallery')
        impact_y=-4350 if chamber is None else chamber['center'][1]+chamber['clear_width_m']/2-3.25
        floor=w.terrain_z(3200,impact_y);a.spawn(3200,impact_y,floor)
        a.data.qvel[1]=14. if chamber is None else 24.;mj.mj_forward(a.model,a.data)
        hit=None
        for _ in range(round(2./DT)):
            a.step()
            for contact in a.data.contact:
                names=[a.model.geom(int(k)).name for k in contact.geom]
                if any(name.startswith('gallery-wall') for name in names):
                    hit=names;break
            if hit:break
        result['side_impact']=dict(geoms=hit,position=a.data.qpos[:3].tolist(),elapsed=a.data.time)
        # Vertical cross-section from inside the clear opening, and at two real
        # open ends. Ray cast hits the ceiling only inside the 600 m gallery.
        section=[]
        for xx in [2870,3000,3400,3530]:
            gid=np.array([-1],dtype=np.int32)
            dist=mj.mj_ray(a.model,a.data,np.array([xx,-4350,floor+.1]),np.array([0.,0.,1.]),
                           np.array([1,0,0,0,0,0],dtype=np.uint8),True,-1,gid)
            section.append(dict(x=xx,distance_m=dist,geom=a.model.geom(int(gid[0])).name if dist>=0 else None))
        result['section']=section
    (args.directory/'traversal.json').write_text(json.dumps(result,indent=2))
    print({k:({'end':v['samples'][-1],'distance':v['displacement_m']} if 'samples' in v else v) for k,v in result.items()})
    failed=city['samples'][-1]['crashed'] or city['displacement_m']<50 or max(s['lateral_m'] for s in city['samples'])>boulevard['width_m']/2
    if 'tunnel' in result:
        failed|=(result['tunnel']['samples'][-1]['xyz'][0]<3520 or result['tunnel']['samples'][-1]['crashed'] or
                 not result['side_impact']['geoms'] or [q['geom'] for q in result['section']]!=[None,'gallery-roof','gallery-roof',None])
        crossing=result['bridge']
        failed|=(crossing['samples'][-1]['crashed'] or crossing['samples'][-1]['xyz'][0]<end[0]+24 or
                 not any('Falls bridge-deck' in name for name in crossing['contacts']))
    return failed


if __name__=='__main__':
    sys.exit(main())
