"""Find solid obstructions within each road's swept width and vertical traffic space."""
import itertools
import math
from collections import defaultdict

import numpy as np
from scipy.spatial import ConvexHull, cKDTree


def footprint(o):
    """Horizontal shape of the actual solid. Canopy foliage is checked separately."""
    x,y,_=o['center'];a,b,_=o['half']
    if o['kind']=='mesh':
        v=np.array(o['vertices'])[:,:2]+[x,y]
        return v[ConvexHull(v).vertices]
    if o['kind']=='box':
        return np.array([[x-a,y-b],[x+a,y-b],[x+a,y+b],[x-a,y+b]])
    radius=o.get('crown_radius_m',a)
    angles=np.arange(20)*math.tau/20
    return np.array([x+radius*np.cos(angles), y+radius*np.sin(angles)]).T


def segment_distance(a,b,poly):
    """Distance between a finite road segment and a convex polygon, including intersections."""
    v=np.roll(poly,-1,axis=0)-poly
    cross=lambda s,t:s[...,0]*t[...,1]-s[...,1]*t[...,0]
    d=b-a
    h=cross(v,a-poly);s=cross(v,d)
    flat=np.abs(s)<1e-10
    if not np.any(flat&(h<0)):
        lo=max(0.,float(np.max(-h[s>1e-10]/s[s>1e-10],initial=0)))
        hi=min(1.,float(np.min(-h[s < -1e-10]/s[s < -1e-10],initial=1)))
        if lo<=hi:return 0.,(lo+hi)*.5
    def offsets(pt):
        t=np.clip(((pt-poly)*v).sum(axis=1)/np.maximum(1e-14,(v*v).sum(axis=1)),0,1)
        return np.min(np.linalg.norm(pt-poly-t[:,None]*v,axis=1))
    t=np.clip(((poly-a)@d)/max(d@d,1e-14),0,1)
    q=np.linalg.norm(poly-a-t[:,None]*d,axis=1)
    i=int(q.argmin())
    return min((q[i],t[i]),(offsets(a),0.),(offsets(b),1.))


class StreetIndex:
    def __init__(self,world,routes=None):
        self.w=world; starts=[];ends=[];self.roads=[];ids=[]
        for r in routes if routes is not None else world.vaderland['routes']:
            k=len(self.roads);self.roads.append(r)
            for a,b in zip(r['points'],r['points'][1:]):
                a=np.array(a);b=np.array(b)
                length=np.linalg.norm(b-a)
                if length<.001:continue
                q=np.linspace(a,b,math.ceil(length/16)+1)
                starts.extend(q[:-1]);ends.extend(q[1:]);ids.extend([k]*(len(q)-1))
        self.a=np.array(starts);self.b=np.array(ends);self.ids=np.asarray(ids)
        self.tree=cKDTree((self.a+self.b)/2)
        self.widths=np.array([r['width_m']/2 for r in self.roads])
        # The proving apron is a wide area, so index it independently.
        self.wide=np.flatnonzero(self.widths[self.ids]>60)
    def overlaps(self,o,margin=.3,headroom=4.85):
        poly=footprint(o);xy=np.array(o['center'][:2]);radius=np.max(np.linalg.norm(poly-xy,axis=1))
        near=self.tree.query_ball_point(xy,radius+60+9+margin)
        candidates=np.unique(np.r_[near,self.wide].astype(int))
        ctr=(self.a[candidates]+self.b[candidates])/2
        candidates=candidates[np.linalg.norm(ctr-xy,axis=1)<radius+self.widths[self.ids[candidates]]+9+margin]
        if not len(candidates):return {}
        bottom=o['center'][2]-o['half'][2];top=o['center'][2]+o['half'][2]
        found={}
        for i in candidates:
            r=self.roads[self.ids[i]]
            if 'deck_z_m' in r and (top<r['deck_z_m']+.06 or bottom>r['deck_z_m']+headroom):continue
            dist,t=segment_distance(self.a[i],self.b[i],poly)
            clearance=float(dist-r['width_m']/2)
            if clearance>=margin:continue
            p=self.a[i]+t*(self.b[i]-self.a[i])
            z=r.get('deck_z_m')
            if z is None:z=self.w.terrain_z(*p)
            if top<z+.07 or bottom>z+headroom:continue
            if r['name'] not in found or clearance<found[r['name']]['edge_gap_m']:
                found[r['name']]=dict(edge_gap_m=round(clearance,3),xy=p.round(2).tolist(),road_z_m=round(float(z),3))
        return found


def road_ends(world):
    index=StreetIndex(world);result=[]
    for rid,road in enumerate(index.roads):
        pts=np.array(road['points'])
        if np.linalg.norm(pts[0]-pts[-1])<1:continue
        for end in (0,-1):
            xy=pts[end];z=road.get('deck_z_m',world.terrain_z(*xy));nearest=(math.inf,None)
            for i in index.tree.query_ball_point(xy,96):
                other=index.ids[i]
                if other==rid:continue
                r=index.roads[other];d=index.b[i]-index.a[i]
                t=np.clip((xy-index.a[i])@d/max(1e-8,d@d),0,1);point=index.a[i]+t*d
                if abs(r.get('deck_z_m',world.terrain_z(*point))-z)>1.4:continue
                gap=float(np.linalg.norm(point-xy)-r['width_m']/2)
                if gap<nearest[0]:nearest=(gap,r['name'])
            if nearest[0]>road['width_m']/2:
                result.append(dict(road=road['name'],end=end,xy=xy.tolist(),nearest=nearest[1],gap_m=round(nearest[0],2) if math.isfinite(nearest[0]) else None))
    return result


def inspect(world):
    index=StreetIndex(world);hits={}
    for o in world.obstacles:
        if o.get('role') in ('deck','dock','cover'):continue
        issues=index.overlaps(o)
        if issues:hits[o['id']]=issues
    return hits


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    from vtx.world import make_world
    p=argparse.ArgumentParser();p.add_argument('world');p.add_argument('output',type=Path);a=p.parse_args()
    hits=inspect(make_world(a.world));a.output.write_text(json.dumps(hits,indent=2))
    places=defaultdict(list)
    for name,road in hits.items():
        for r in road:places[r].append(name)
    for r,names in places.items():print(r,len(names),', '.join(names[:8]))
