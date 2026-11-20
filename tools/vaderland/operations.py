"""Design the occupied control cabin and full-scale terminal departmental hall."""
import json,math
import numpy as np
from bake import PACK
from drafting import Masonry
from vtx.vaderland import MeridianArrivals


def build():
    world=MeridianArrivals()
    m=Masonry();removed={'airport-rotunda','signal-tower-cab'}
    # Keep the 46 m original crown and the building's load-bearing ground ring.
    # Full-height opposite openings lead onto the arrivals curb and the airfield apron.
    walls=[];cab=[]
    def perimeter(name,x,y,r0,r1,z0,z1,thick,count,skip,skin,parent):
        ids=[]
        for j in range(count):
            if j in skip:continue
            angles=[(j+k)*math.tau/count for k in (0,1)]
            points=[[x+(r-t)*math.cos(a),y+(r-t)*math.sin(a),z] for a in angles
                    for r,z in ((r0,z0),(r1,z1)) for t in (0,thick)]
            ids.append(m.hull(f'{name}-{j:02}',points,skin,parent=parent))
        return ids
    walls=perimeter('operations-facade',0,-300,81,81,-.35,14.62,.55,64,{14,15,16,17,46,47,48,49},'hallglass',None)
    cab=perimeter('operations-cab',116,-235,9.55,10.90,90.45,96.13,.16,32,set(),'cabglass','tower-bearing')
    # Limit the new long-span ceiling's support claim to actual bearing walls.
    # The four existing wings remain self-founded and structurally independent.
    new_parents={'rotunda-low-eave':walls[0],'tower-cab-roof':cab[0]}
    desk=m.box('operations-control-console',116,-231.60,90.48,91.14,.92,.38,'desk',parent='tower-bearing')
    # Furniture and partitions sit outside the through-hall and the reserved clear survey rectangle.
    m.box('engineering-return',54,-303,-.20,8.6,.45,12,'stone')
    m.box('engineering-south-wall',37,-331,-.20,8.6,16.8,.44,'stone')
    m.box('compliance-return',-54,-305,-.20,7.8,.45,11,'stone')
    m.box('compliance-desk',-32,-316,-.09,1.0,5.4,.88,'desk')
    m.box('dispatch-desk',-26,-274,-.09,1.0,6.4,.88,'desk')
    for x in (-19,19):
        for y in (-350,-250):
            m.rings(f'hall-pier-{x}-{y}',[(x,y,.95,.95,-.46),(x,y,.76,.76,1.9),
                (x,y,.67,.67,12.5),(x,y,1.65,1.65,14.62)],'stone',23)
    from annex import build as annex
    from finch import install
    from pathlib import Path
    import sys
    campus=annex(m);moves=install(m,Path(sys.argv[1]))
    from streets import StreetIndex
    ring=next(r for r in world.vaderland['routes'] if r['name']=='Terminal boulevard')
    for idx in (0,-1):
        xy=np.array(campus['access']['points'][idx]);campus['access']['points'][idx]=min(ring['points'],key=lambda p:np.linalg.norm(xy-p))
    service_index=StreetIndex(world,[campus['access']])
    for o in world.obstacles:
        x,y,_=o['center'];r=o.get('crown_radius_m',o['half'][0])
        if o['kind']=='cylinder' and (o.get('role') in (None,'conifer')) and (
             (abs(x-1000)<46+r and abs(y+340)<24+r) or (abs(x-1000)<35+r and abs(y+455)<52+r)
             or (320-r<x<1680+r and abs(y+325)<11.5+r and o['center'][2]+o['half'][2]>6.5)
             or bool(service_index.overlaps(o,margin=1.35))):
            removed.add(o['id'])
    replaced={}
    for o in world.obstacles:
        name=o['id']
        if name.startswith('Falls bridge-edge-'):
            # The 18 m approach fans into the 14 m deck before its first two side kerbs.
            obj=dict(o);obj['center']=o['center'][:];obj['half']=o['half'][:]
            obj['center'][0]-=4.;obj['half'][0]-=4.;replaced[name]=obj
        elif name.startswith('pickup-canopy-'):
            vs=np.array(o['vertices'])+o['center'];vs[:,1]=-395+(vs[:,1]+395)*1.32
            m.hull(name,vs,'canopy',support='span',span=name,bearings=o['bearings'])
            removed.add(name)
        elif name.startswith('pickup-column-'):
            obj=dict(o);obj['center']=o['center'][:];obj['center'][1]=round(-395+1.32*(obj['center'][1]+395),5)
            replaced[name]=obj
    # The old painted west entrance curved into the edge of the tunnel before reaching the portal.
    changes={}
    for name,portal,side in [('Gallery west approach',2900.,-1),('Gallery east approach',3500.,1)]:
        r=next(r for r in world.vaderland['routes'] if r['name']==name)
        pts=np.array(r['points'])
        station=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
        d=station[-1]-station if side<0 else station
        weight=np.clip((d-23)/67,0,1);weight*=weight*(3-2*weight)
        pts[:,1]=-4350+(pts[:,1]+4350)*weight
        changes[name]=dict(r,points=pts.round(4).tolist())
    from airfield import curve
    ring_road=next(r for r in world.vaderland['routes'] if r['name']=='Arrivals circle')
    link=next(r for r in world.vaderland['routes'] if r['name']=='Pickup link')
    entry=min(ring_road['points'],key=lambda pt:np.linalg.norm(np.array(pt)-[16.5,-420.]))
    changes['Pickup link']=dict(link,points=curve(entry,[28,-416],[30,-412],[30,-407])+[[30.,-395.]])
    link_index=StreetIndex(world,[changes['Pickup link']])
    for tree in world.obstacles:
        x,y,_=tree['center']
        if tree['kind']=='cylinder' and tree.get('role') in (None,'conifer') and abs(x)<60 and -460<y<-380 and link_index.overlaps(tree,margin=.8):removed.add(tree['id'])
    boulevard=next(r for r in world.vaderland['routes'] if r['name']=='Terminal boulevard')
    north=min(boulevard['points'],key=lambda pt:np.linalg.norm(np.array(pt)-[0,-177.]))
    through=dict(name='Terminal operations hall',kind='indoor',width_m=8.6,points=[[6.,-395.],[6.,-382.],[5.,-371.],[0.,-348.],[0.,-220.],north])
    old=next(r for r in world.vaderland['routes'] if r['name']=='Forecourt approach')
    west=min(boulevard['points'],key=lambda pt:np.linalg.norm(np.array(pt)-[-331,-302]))
    changes['Forecourt approach']=dict(old,points=[old['points'][0],old['points'][1],west])
    westlink=dict(name='West service apron lane',kind='taxi',width_m=12.,points=[[-1200,40],[-1030,54],[-780,61],[-560,55],[-435,45]])
    eastlink=dict(name='East service apron lane',kind='taxi',width_m=12.,points=[[321,79],[460,93],[730,98],[967,66],[1260,40]])
    opened=StreetIndex(world,[through,westlink,eastlink,changes['Forecourt approach']])
    for tree in world.obstacles:
        x,y,_=tree['center']
        if -1250<x<1300 and -440<y<160 and tree['kind']=='cylinder' and tree.get('role') in (None,'conifer') and opened.overlaps(tree,margin=.8):removed.add(tree['id'])
    from racing import course
    trial=course(world,'Meridian Operations',campus['access'],ring,[.15,.38,.56,.78,.96])
    plan=dict(removed=sorted(removed),solids=m.solids,replaced=replaced,parents=new_parents,
       routes=[through,westlink,eastlink,campus['access']],revised_routes=changes,operations=dict(annex=campus,course=trial,staff_moves=moves,
       terminal_asset='meridian-open-terminal.glb',windows=cab,facade=walls,
       engineering=dict(center=[34,-302],clear_m=[36,46,14.55]),
       tower=dict(center=[116,-235],floor_m=90.50,station=[116,-232.66,90.50],heading_rad=math.pi),
       compliance=dict(center=[1000.,-342.2],radii=[3.2,1.12],period_s=28.0),
       hall_width_m=2*81*math.sin(math.pi/16),hall_height_m=14.55))
    (PACK/'operations-12.json').write_text(json.dumps(plan,separators=(',',':'))+'\n')
    print('walls',len(walls),'control panes',len(cab),'native solids',len(m.solids))
if __name__=='__main__':build()
