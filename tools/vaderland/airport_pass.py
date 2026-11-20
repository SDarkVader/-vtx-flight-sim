"""Inspect runway continuity, terminal access, the open hangar and the physical stands."""
import argparse
import json
from pathlib import Path

import mujoco as mj
import numpy as np

from drive_pass import run, sampled_route
from vtx.aircraft import Aircraft
from vtx.live_server import landing_support
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world, MapPoint


def probe(plant,origin,direction):
    gid=np.array([-1],dtype=np.int32)
    d=mj.mj_ray(plant.model,plant.data,np.array(origin,float),np.array(direction,float),
                np.array([1,0,0,0,0,0],np.uint8),True,-1,gid)
    return dict(origin=origin,direction=direction,distance_m=d,
                geom=None if d<0 else plant.model.geom(int(gid[0])).name)


def survey(w,section):
    roads={r['name']:r for r in w.vaderland['routes']}
    if section=='strike':
        path=sampled_route([(dict(points=[[6.,-402.],[6.,-328.]],width_m=8.),False)])
        return run(w,2,70,10,path=path)
    if section in ('pickup','circle'):
        design=roads if 'Terminal pickup' in roads else {r['name']:r for r in make_world('vaderland-11').vaderland['routes']}
        segments=[(design['Terminal pickup'],False)] if section=='pickup' else [
            (design['West arrivals slip'],False),
            (dict(design['Arrivals circle'],points=design['Arrivals circle']['points'][:57]),False),
            (design['East arrivals slip'],True)]
        path=sampled_route(segments)
        length=float(np.linalg.norm(np.diff(path[0],axis=0),axis=1).sum())
        receipt=run(w,4,length-4,8 if section=='pickup' else 6,path=path,record_m=length*.50)
        receipt['route']='Covered terminal pickup' if section=='pickup' else 'West entrance to east exit via the arrivals circle'
        return receipt
    if section=='gangway':
        road=roads['Airport landing road']
        gangway=roads.get('Ricochet gangway',dict(points=[[205,-550],[205,-605]],width_m=4))
        path=sampled_route([(road,False),(gangway,False)])
        length=float(np.linalg.norm(np.diff(path[0],axis=0),axis=1).sum())
        result=run(w,length-170,length-5,6,path=path,record_m=length-26)
        result['route']='Airport road to rear pontoon'
        return result
    if section in ('road','hangar'):
        road=roads['Airport landing road'] if section=='road' else roads.get('North hangar passage',
            dict(points=[[-435,45],[137,45],[155,63],[184,79],[321,79]],width_m=14))
        path=sampled_route([(road,False)])
        length=float(np.linalg.norm(np.diff(path[0],axis=0),axis=1).sum())
        result=run(w,4,length-4,12 if section=='road' else 15,path=path,record_m=513 if section=='hangar' else None)
        result['route']=road.get('name','North hangar passage');return result
    plane=PhantomAircraft(w,'phantom-a10c',start_configuration='road')
    if section=='shells':
        plane.spawn(-3885,0,0)
        probes=[]
        columns=[(x,-300) for x in [0,36,53,67,75,80,85.8,89]]+[(0,-395),(30,-395),(0,-437),
                 (144,-319),(141,-376),(-175,-394),(222,-333),(116,-235)]
        rays=[([x,y,130.],[0.,0.,-1.]) for x,y in columns]
        rays.extend([([0,-406,4],[0,1.,0]),([0,-395,2.],[0,0.,1.]),([0,-400,4.],[1.,0.,0.])])
        for origin,direction in rays:probes.append(probe(plane,origin,direction))
        return dict(probes=probes,crown_site=landing_support(w,MapPoint(x_m=0,y_m=-300),'departure','phantom-a10c').valid)
    if section=='berths':
        from vtx.harbour_fleet import HarbourFleet
        fleet=HarbourFleet(w)
        plane.spawn(-3885,0,0)
        samples=[]
        for spec in fleet.world.structures:
            if not spec['id'].startswith('airport-'):continue
            x,y,z=spec['center']
            samples.append((spec['id'],[x,y,12.],[0.,0.,-1.]))
        samples.append(('gangway side',[210.,-580.,7.6],[-1.,0.,0.]))
        result=[]
        for name,origin,direction in samples:
            craft=probe(plane,origin,direction);boat=probe(fleet,origin,direction)
            result.append(dict(label=name,origin=origin,direction=direction,air=craft,marine=boat))
        return dict(probes=result,chart_level_m=w.harbour['waterLevelM'])
    if section=='geometry':
        plane.spawn(-3885,0,0)
        rays=[probe(plane,[85,45,2],d) for d in ([0,1,0],[0,-1,0],[0,0,1],[-1,0,0],[1,0,0])]
        sky=probe(plane,[85,45,110],[0,0,-1])
        floor=probe(plane,[85,45,5],[0,0,-1])
        return dict(interior=rays,roof=sky,floor=floor,roof_site=landing_support(w,MapPoint(x_m=85,y_m=45),
                    'departure','phantom-a10c').valid)
    aircraft=[('Phantom A10-C',plane),('Argon R6',Aircraft(w,airframe_variant='r6',gear_variant='critical-damping-proposal',
                rpm=1200.,fuel_kg=10.,engine_power_limit_kw=300.))]
    result={}
    for label,plant in aircraft:
        x,y=(0.,-300.) if section=='roof' else (546.,-154.)
        site=landing_support(w,MapPoint(x_m=x,y_m=y),'departure','phantom-a10c' if label.startswith('Phantom') else 'r6')
        plant.spawn(x,y,w.surface_z(x,y));touches=set()
        for _ in range(round(1./plant.model.opt.timestep)):
            plant.step()
            for contact in plant.data.contact:
                for gid in contact.geom:
                    if plant.model.geom_bodyid[gid]==0:touches.add(plant.model.geom(int(gid)).name)
        result[label]=dict(site_valid=site.valid,site_reason=site.reason,surface_z_m=site.terrain_z_m,
                           support_geoms=sorted(touches))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--world',required=True);p.add_argument('--section',choices=('road','hangar','gangway','geometry','pad','roof','berths','pickup','circle','shells','strike'),required=True)
    a=p.parse_args();r=survey(make_world(a.world),a.section)
    if 'pose' in r:
        (a.directory/(a.section+'-pose.json')).write_text(json.dumps(r.pop('pose')),encoding='utf-8')
    (a.directory/('airport-'+a.section+'.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print({k:v for k,v in r.items() if k!='samples'})
