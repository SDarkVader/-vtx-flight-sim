"""Join the north bank to the surveyed marine gangway and four existing berths."""
import json
from copy import copy, deepcopy

import numpy as np

from airfield import curve
from bake import PACK, landscape_light
from vtx.harbour_water import HarbourWorld
from vtx.vaderland import MeridianAirfield


def build():
    w=MeridianAirfield()
    before=copy(w)
    w.heights=w.heights.copy()
    chart=HarbourWorld(w)
    axis=np.linspace(-w.half,w.half,w.n)
    bank=[]
    # Meet the existing fixed deck at its landward end. Retain the old deep
    # bed under the finger piers and the flat airport corridor north of -500.
    for y,level in [(-560,2.8),(-540,8.2),(-520,4.3)]:
        row=int(np.searchsorted(axis,y))
        for col in np.flatnonzero((axis>=40)&(axis<=320)):
            x=axis[col]
            t=np.clip(min((x-40)/70,(320-x)/75),0,1)
            h=round(w.heights[row,col]*(1-t)+level*t,1)
            if h!=w.heights[row,col]:
                w.heights[row,col]=h
                bank.append([row,int(col),h])
    added=[];removed=set()
    def box(name,x,y,a,b,bottom,top,finish,role,**other):
        o=dict(id=name,kind='box',center=[float(x),float(y),round((bottom+top)/2,4)],
               half=[float(a),float(b),round((top-bottom)/2,4)],color='#42505a',
               landable=role in ('deck','dock'),role=role,finish=finish,**other)
        added.append(o)
        return name
    terminal_berths=[s for s in chart.structures if s['id'].startswith('airport-')]
    underlying=[]
    for s in terminal_berths:
        name=s['id'];x,y,z=s['center'];a,b,h=s['half_extents']
        if abs(round(s['yaw_deg']))==90:a,b=b,a
        if name.endswith('-pier'):
            oid='deck-'+name
            existing=next(o for o in w.obstacles if o['id']==oid)
            removed.add(oid);added.append(dict(deepcopy(existing),finish='jetty'))
        else:
            bearings=[]
            for i,t in enumerate((-.78,.78)):
                px=x+(a*t if a>b else 0);py=y+(b*t if b>a else 0)
                bottom=min(w.terrain_z(px+dx,py+dy) for dx,dy in ((0,0),(.3,.3),(-.3,-.3)))-.28
                if bottom>=z-h:bottom=z-h-.5
                bearings.append(box(name+'-bearing-'+str(i),px,py,.32,.34,bottom,z-h+.035,'pile','pier'))
            box('deck-'+name,x,y,a,b,z-h,z+h,'jetty','dock',support='span',span=name,bearings=bearings)
        underlying.append(name)
    # Open luggage and waiting shelter on the dry west shoulder. There is no
    # wall across the bay. All roof sections share the same two bearing lines.
    for i,(x,top) in enumerate([(116,13.1),(129,14.4),(142,15.7)]):
        bearings=[]
        for sign in (-1,1):
            y=-536.8+sign*4.4
            for side in (-1,1):
                px=x+side*5.7
                bottom=w.terrain_z(px,y)-.40
                bearings.append(box(f'landing-col-{i}-{sign}-{side}',px,y,.26,.30,bottom,top-.30,'quay-column','pier'))
        box('landing-shelter-'+str(i),x,-536.8,6.55,5.3,top-.33,top+.23,'quay-canopy','deck',
            support='span',span='Landing shelter',bearings=bearings)
    # The north apron and road retain their existing finish. A branching lay-by
    # at the landing leads to the shelter. The 4 m timber deck stays narrow.
    road=[(183.29,-500.22),(174,-510),(158,-518),(144,-523),(110,-524)]
    public=next(r for r in w.vaderland['routes'] if r['name']=='Airport landing road')
    cut=public['points'].index([183.29,-500.22])
    approach=public['points'][:cut]+curve([183.29,-500.22],[195,-508],[205,-522],[205,-540])
    routes=[dict(name='Airport Landing lay-by',kind='local',width_m=8,points=road),
            dict(name='Ricochet gangway',kind='boardwalk',width_m=4,deck_z_m=8.2,points=[[205,-540],[205,-605]]),
            dict(name='Rear pontoon',kind='boardwalk',width_m=4,deck_z_m=8.2,points=[[165.825,-605],[235.9,-605]])]
    for pier in w.harbour['docks']['piers']:
        if pier['id'].startswith('airport-'):
            px,py=chart.to_world(pier['center']);a=pier['length']/2
            routes.append(dict(name=pier['id'],kind='boardwalk',width_m=pier['width'],deck_z_m=8.2,
                               points=[[px,py+a],[px,py-a]]))
    plants=[];retired={}
    for o in w.obstacles:
        x,y,z=o['center']
        if o['kind']!='cylinder' or o.get('role') not in (None,'conifer') or not (32<x<330 and -580<y<-500):continue
        r=o.get('crown_radius_m',o['half'][0])
        xy=np.array([x,y]);points=np.asarray(road)
        delta=np.diff(points,axis=0);offset=xy-points[:-1]
        t=np.clip((offset*delta).sum(axis=1)/(delta*delta).sum(axis=1),0,1)
        if np.min(np.linalg.norm(offset-delta*t[:,None],axis=1))<4+r+.75 or (108-r<x<150+r and -543-r<y<-530+r):
            removed.add(o['id']);retired[o['id']]='lay-by or shelter';continue
        old=before.terrain_z(x,y)
        if abs(w.terrain_z(x,y)-old)>.01:
            raised=deepcopy(o);raised['center'][2]=round(z+w.terrain_z(x,y)-old,4)
            removed.add(o['id']);plants.append(raised)
    added.extend(plants)
    plan=dict(bank=bank,removed=sorted(removed),added=added,routes=routes,retired=retired,approach=approach,
              landing=dict(chart_structures=underlying,shelter=[129,-536.8],deck_z_m=8.2))
    (PACK/'landing-10.json').write_text(json.dumps(plan,separators=(',',':'))+'\n',encoding='utf-8')
    all_solids=[o for o in w.obstacles if o['id'] not in removed]+added
    landscape_light(np.rint(w.heights*10),all_solids,'relief-landing.png')
    print(len(bank),'changed grid samples,',len(retired),'intruding trees removed')


if __name__=='__main__':build()
