"""Lay the Night Velocity course through four existing open arterial streets."""
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from bake import landscape_light
from drafting import Masonry
from streets import StreetIndex
from vtx.vaderland import CrestPlaza


def build():
    world=CrestPlaza();m=Masonry();routes={r['name']:r for r in world.vaderland['routes']}
    sides=['Meridian Avenue','Terrace 10','North street 13','Terrace 3']
    streets=[np.array(routes[n]['points'],dtype=float) for n in sides]
    def street(i,station):
        p=streets[i];axis=1-i%2;value=np.interp(station,p[:,axis],p[:,1-axis])
        return np.array([value,station] if axis else [station,value])
    corners=[]
    for i in range(4):
        prev=(i-1)%4;road=(i if i%2==0 else prev);cross=(prev if i%2==0 else i)
        y=streets[cross][len(streets[cross])//2,1]
        for _ in range(12):p=street(road,y);y=street(cross,p[0])[1]
        corners.append(np.array([p[0],y]))
    # Different block shapes create a tighter turn towards the southern boulevard.
    radii=[137.,175.,155.,88.]
    signs=(1,1,-1,-1);points=[];curves=[]
    def at(i,s):return street(i,corners[i][1-i%2]+signs[i]*s)
    for i in range(4):
        j=(i+1)%4;n=1-i%2;delta=(corners[j][n]-corners[i][n])*signs[i]
        for s in np.linspace(radii[i],delta-radii[j],math.ceil((delta-radii[j]-radii[i])/12)):
            points.append(at(i,s))
        a=points[-1];b=at(j,radii[j]);p=corners[j];r=radii[j]
        d0=(a-at(i,delta-r-.8));d0/=np.linalg.norm(d0)
        d1=(at(j,r+.8)-b);d1/=np.linalg.norm(d1)
        ctrl0=a+.552285*r*d0;ctrl1=b-.552285*r*d1;curves.append(len(points)-1)
        for t in np.linspace(0,1,math.ceil(r/4))[1:-1]:
            points.append((1-t)**3*a+3*t*(1-t)**2*ctrl0+3*t*t*(1-t)*ctrl1+t**3*b)
    xy=np.round(np.vstack([points,points[:1]]),4);delta=np.linalg.norm(np.diff(xy,axis=0),axis=1)
    chain=np.r_[0.,np.cumsum(delta)];length=chain[-1]
    def on(s):
        s=s%length;j=min(len(delta)-1,np.searchsorted(chain,s,side='right')-1)
        t=(s-chain[j])/delta[j];return xy[j]*(1-t)+xy[j+1]*t,(xy[j+1]-xy[j])/delta[j]
    road=dict(name='Night Velocity Speedway',kind='speedway',width_m=27.,points=xy.tolist())
    alignment=StreetIndex(world,[road]);remove=set()
    for o in world.obstacles:
        if not alignment.overlaps(o,margin=.37,headroom=8.2):continue
        if o.get('role') in ('architecture','conifer',None):
            if o['id'].startswith(('meridian-','crest-','aviator-','plaza-')):raise ValueError('Protected landmark '+o['id'])
            remove.add(o['id'])
    for o in world.obstacles:
        if o.get('parent') in remove:remove.add(o['id'])
    gates=[]
    for f in (.073,.23,.42,.60,.78,.91):
        p,dr=on(length*f);gates.append(dict(center=[*p.round(4),round(world.terrain_z(*p),3)],normal=dr.round(7).tolist(),width_m=27.))
    piles=[];allroads=StreetIndex(world,[*routes.values(),road])
    others=[o for o in world.obstacles if o['id'] not in remove]
    centers=np.array([o['center'][:2] for o in others]);tree=cKDTree(centers)
    def clear(p):
        if allroads.overlaps(dict(kind='box',center=[*p,world.terrain_z(*p)+2.5],half=[1.1,1.1,3.]),margin=1.2):return False
        return all(np.any(abs(p-centers[k])>np.array(others[k]['half'][:2])+1.2) for k in tree.query_ball_point(p,110))
    for j,s in enumerate(np.arange(60.,length,76.)):
        p,dr=on(s);normal=np.array([-dr[1],dr[0]])
        for sign in (-1,1):
            for offset in (16.,20.,25.,32.,38.,44.):
                q=p+sign*normal*offset
                if not clear(q):continue
                x,y=q;z=world.terrain_z(x,y)
                foot=m.box(f'velocity-base-{j}-{sign}',x,y,z-1.1,z+.27,.65,.64,'blacksteel')
                mast=m.rings(f'velocity-light-{j}-{sign}',[(x,y,.34,.31,z+.25),(x,y,.22,.21,z+2.8),
                      (x+dr[0]*.57,y+dr[1]*.57,.22,.21,z+4.65)],'crestsilver',12,parent=foot)
                m.rings(f'velocity-lens-{j}-{sign}',[(x+dr[0]*.56,y+dr[1]*.56,.229,.22,z+4.43),
                      (x+dr[0]*.57,y+dr[1]*.57,.214,.21,z+4.68)],'lamplens',12,parent=mast)
                piles.append(dict(xyz=[x+dr[0]*.57,y+dr[1]*.57,z+4.69],sign=sign,station_m=round(s,2)));break
    config=dict(road=road['name'],length_m=round(length,2),streets=sides,corners=[p.tolist() for p in corners],
        timing=dict(name='Night Velocity',length_m=round(length,2),gates=gates),lights=piles)
    out=dict(removed=sorted(remove),solids=m.solids,route=road,speedway=config)
    p=Path(__file__).resolve().parents[2]/'inputs/vaderland/night-15.json'
    p.write_text(json.dumps(out,separators=(',',':'))+'\n')
    landscape_light(np.rint(world.heights*10),[o for o in others+m.solids if not o.get('motion')],
                    'relief-velocity.png',sun=(-.89,.46,.19))
    print('Lap metres',length,'light columns',len(piles),'removed',sorted(remove))


if __name__=='__main__':build()
