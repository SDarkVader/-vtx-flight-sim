"""Probe solid land, genuinely open spans and the physical four-lane gallery."""
import argparse
import json
from pathlib import Path
import sys

import mujoco as mj
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from vtx.aircraft import Aircraft
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world
from roads import sections


def ray(plane,start,direction):
    gid=np.full(1,-1,np.int32)
    length=mj.mj_ray(plane.model,plane.data,np.asarray(start,float),np.asarray(direction,float),
                     np.array([1,0,0,0,0,0],np.uint8),True,-1,gid)
    return dict(distance_m=None if length<0 else float(length),
                geom=None if length<0 else plane.model.geom(int(gid[0])).name)


def snow(world, start, angle_deg, length, width):
    # Sample both edges of the open snowy eastern face. Empty space alone
    # does not make this line usable by a ski vehicle.
    trees=cKDTree([o['center'][:2] for o in world.obstacles])
    heading=np.deg2rad(angle_deg)
    tangent=np.array([np.cos(heading),np.sin(heading)])
    xy=np.array(start)+np.arange(0.,length+1,5.)[:,None]*tangent
    side=np.array([-tangent[1],tangent[0]])*(width/2)
    z=np.array([[world.terrain_z(*p) for p in xy+offset] for offset in (-side,side*0,side)])
    return dict(ends_m=[[*xy[0],z[1,0]],[*xy[-1],z[1,-1]]],length_m=length,width_m=width,
                elevation_change_m=abs(z[1,-1]-z[1,0]),max_grade_pct=100*abs(np.diff(z,axis=1)/5).max(),
                max_crossfall_pct=100*np.max(abs(z[0]-z[2]))/width,
                nearest_obstacle_centre_m=float(trees.query(xy)[0].min()),physical_material='native heightfield')


def inspect(world):
    plane=PhantomAircraft(world,'phantom-a10c',start_configuration='road')
    plane.spawn(-3885,0,0)
    probes=[]
    def check(label,origin,direction,kind,mesh='terrain'):
        result=ray(plane,origin,direction)
        probes.append(dict(label=label,origin=list(origin),direction=list(direction),client_mesh=mesh,**result))
        if kind is not None and result['geom']!=kind: raise ValueError((label,result,kind))
        return result
    for label,x,y in [('upper waterfall',-4791,4337),('western mountain',-6687,6031),
                       ('east ridge',6007,5373),('summit face',-6852,6471),('canyon west bank',-5147,3511)]:
        slope=np.array([world.terrain_z(x+1,y)-world.terrain_z(x-1,y),
                        world.terrain_z(x,y+1)-world.terrain_z(x,y-1)])
        direction=np.r_[slope/np.linalg.norm(slope),0.]
        point=np.array([x,y,world.terrain_z(x,y)])
        # Stay on the same exposed face at launch, even where the valley bends.
        start=point-32*direction
        if world.terrain_z(*start[:2])>=start[2]:start=point-5*direction
        check(label,start,direction,'terrain')
    check('summit above',[-6900,6480,3500],[0,0,-1],'terrain')
    # The deck crosses a gorge; the bay half way between two piers is open.
    check('bridge underside',[-5192.8,3200,156],[0,0,1],'Falls bridge-deck-main','bridge')
    check('bridge entered laterally',[-5192.8,3180,182],[0,1,0],'Falls bridge-deck-main','bridge')
    check('pier flank',[-5163.8,3180,149],[0,1,0],'Falls bridge-pier-5','bridge')
    g=world.vaderland['gallery'];y=g['center'][1];z=g['floor_z_m']+2
    for name,direction,geom in [('north wall',[0,1,0],'gallery-wall-1'),('south wall',[0,-1,0],'gallery-wall--1'),
                                ('solid ceiling',[0,0,1],'gallery-roof')]:
        check(name,[3200,y,z],direction,geom,'gallery')
    check('cover from the sky',[3200,y,z+60],[0,0,-1],'gallery-earth-cover','gallery')
    for end in g['portal_x_m']:
        p=[end+(-4 if end<3200 else 4),y,z]
        check('open sky outside portal '+str(end),p,[0,0,1],None,'gallery')
        if probes[-1]['geom'] is not None:raise ValueError(probes[-1])
    for offset in g['lane_centres_m']:
        result=check('through bore '+str(offset),[2878,y+offset,z],[1,0,0],None,'gallery')
        if result['distance_m'] is not None and result['distance_m']<645:raise ValueError(result)

    collisions=[]
    for vehicle,plant,probe in [('Phantom A10-C',plane,probes[0]),
                               ('R6',Aircraft(world,gear_variant='critical-damping-proposal',rpm=1200.,fuel_kg=10.,
                                    airframe_variant='r6',engine_power_limit_kw=300.),probes[1])]:
        x,y,z=probe['origin'];direction=np.array(probe['direction'])
        plant.spawn(x,y,z)
        plant.data.qvel[:3]=direction*48
        mj.mj_forward(plant.model,plant.data)
        hit=None
        for _ in range(round(1.6/plant.model.opt.timestep)):
            plant.step()
            for c in plant.data.contact:
                names=[plant.model.geom(int(i)).name for i in c.geom]
                if 'terrain' in names:
                    hit=dict(contact=names,t_s=float(plant.data.time),xyz_m=c.pos.tolist());break
            if hit:break
        if hit is None:raise ValueError(vehicle+' passed through the face')
        collisions.append(dict(model=vehicle,face=probe['label'],inbound_m_s=48,**hit))
    before=make_world('vaderland-06')
    ids={o['id'] for o in world.obstacles}
    if len(ids)!=len(world.obstacles):raise ValueError('Duplicate scenery identity')
    roads=[r for r in world.vaderland['routes'] if r.get('lanes_each_way')==2]
    lines=np.vstack([sections(r) for r in roads])
    road_tree=cKDTree(lines)
    intruders=[]
    for o in world.obstacles:
        x,y,z=o['center'];a,b,c=o['half']
        if o['id'].startswith('gallery-') or not(2510<x<4910 and -4550<y<-3530):continue
        if o['kind']=='cylinder' and road_tree.query([x,y])[0]<10.75+a:
            if abs(z-world.terrain_z(x,y))<c+5:intruders.append(o['id'])
        elif o['kind']=='box':
            if np.any((abs(lines[:,0]-x)<=a+10.75)&(abs(lines[:,1]-y)<=b+10.75)):
                intruders.append(o['id'])
    removed=sorted({o['id'] for o in before.obstacles}-ids)
    if intruders:raise ValueError(('Obstructed traffic corridor',intruders))
    return dict(probes=probes,horizontal_impacts=collisions,
                snow=dict(eastern_face=snow(world,[7360.,5340.],43.2,240,24),
                          open_shelf=snow(world,[5860.,5960.],33.75,80,16)),
                removed_gallery_objects=removed,obstructions_in_widened_road=intruders)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();result=inspect(make_world('vaderland-07'))
    (args.directory/'clearance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(len(result['probes']),'rays',result['horizontal_impacts'],result['snow'])
