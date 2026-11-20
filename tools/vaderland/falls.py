"""Survey the Twin Falls bed, abutments and forest from the frozen Meridian terrain."""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from bake import AXIS, HALF, PACK, ROOT, STEP, X, Y, landscape_light, smooth
from roads import sections

sys.path.insert(0, str(ROOT / 'src'))
from vtx.vaderland import LanternGallery, Meridian


def chain(xy):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]


def project(xy, points):
    """Cross-section station and signed offset, in metres, on a densely sampled line."""
    _, ix = cKDTree(xy).query(points)
    direction = xy[np.minimum(ix+1,len(xy)-1)] - xy[np.maximum(ix-1,0)]
    direction /= np.linalg.norm(direction, axis=1)[:,None]
    delta = points-xy[ix]
    return (chain(xy)[ix]+(delta*direction).sum(axis=1),
            direction[:,0]*delta[:,1]-direction[:,1]*delta[:,0])


def build():
    w = Meridian()
    before = w.heights.copy()
    roads = {r['name']: r for r in w.vaderland['routes']}
    stream = w.vaderland['streams'][0]
    river = sections(stream)
    river_tree = cKDTree(river)
    river_stations = chain(river)
    # All terrain edits are restricted to the crossing and the two adjacent falls.
    i0,i1 = np.searchsorted(AXIS,[-6230,-3990])
    j0,j1 = np.searchsorted(AXIS,[2485,4855])
    sl = np.s_[j0:j1,i0:i1]
    patch = w.heights[sl]
    pts = np.column_stack((X[sl].ravel(),Y[sl].ravel()))
    station, side = project(river,pts)
    s = station.reshape(patch.shape)
    d = np.abs(side.reshape(patch.shape))
    # Two real rock lips with pools downstream. Elevation always falls toward
    # the sea, including the previously uphill reach south of the viaduct.
    bed = (317.25-.01885*s - 101.*smooth(2280,2310,s)
           - 33.*smooth(3160,3480,s) - 31.*smooth(3810,3850,s))
    active = smooth(1840,2040,s)*(1-smooth(4030,4230,s))
    bank = 24+4*np.sin(s/89)+2.4*np.sin(s/34)
    shoulder = 67+17*np.sin(s/133+side.reshape(patch.shape)*.004)
    escarpment = 31+15*np.sin(s/123)+7*np.cos(s/74)
    shelf = bed + .015*np.maximum(d-bank,0) + escarpment*smooth(bank+8,shoulder+36,d)
    weight = active*(1-smooth(shoulder+40,230,d))
    patch += (shelf-patch)*weight

    top = roads['Falls bridge']['deck_z_m']
    for key,sign,grade in [('Canyon climb',-1,.089),('Scree pass',1,.166)]:
        road = roads[key]
        path = sections(road)
        if sign < 0:
            path=path[::-1]
        s,cross = project(path,pts)
        length = np.maximum(s-46.,0.)
        road_z = top+sign*grade*(length-32.*(1-np.exp(-length/32.)))
        # Keep the established straight roll's level entry and transition over
        # the next 32 m. The old 88 m stamp ended abruptly on rising ground.
        weight = ((1-smooth(295,525,s))*smooth(-21,-5,s)
                  *(1-smooth(road['width_m']/2+24,112,np.abs(cross))))
        patch += ((road_z-patch.ravel())*weight).reshape(patch.shape)
    np.around(patch,1,out=patch)
    delta = np.rint((w.heights-before)*10).astype(np.int16)
    j,i = np.nonzero(delta)
    np.savez_compressed(PACK/'falls-06.npz',row=j.astype(np.uint16),col=i.astype(np.uint16),change_dm=delta[j,i])

    removed,added = [],[]
    def add(oid, kind, xy, a, b, bottom, ceiling, role, color, **other):
        added.append(dict(id=oid,kind=kind,center=[*map(float,xy),round((bottom+ceiling)/2,5)],
                          half=[float(a),float(b),round((ceiling-bottom)/2,5)],role=role,
                          landable=role=='deck',color=color,**other))

    for o in w.obstacles:
        x,y,z=o['center']; a,b,c=o['half']
        if o.get('span')=='Falls bridge':
            removed.append(o['id'])
        elif o['id'].startswith('Falls bridge-pier-'):
            removed.append(o['id'])
            bottom=min(w.terrain_z(x+dx,y+dy) for dx,dy in ((0,0),(a,0),(-a,0),(0,a),(0,-a)))-2
            add(o['id'],'cylinder',(x,y),a,a,bottom,top-4.24,'pier','#68716e')
            add(o['id']+'-cap','box',(x,y),4.6,6.65,top-4.3,top-2.75,'pier','#697378',support='stack',parent=o['id'])
        elif o['kind']=='cylinder' and not o.get('role') and -6250<x<-3980 and 2450<y<4870:
            foot=min(w.terrain_z(x+dx,y+dy) for dx,dy in ((0,0),(a,0),(-a,0),(0,a),(0,-a)))
            if abs(z-c-(foot-.55))>.3:
                removed.append(o['id'])
                dist,_=river_tree.query([x,y])
                if dist>32+a:
                    added.append(dict(o,center=[x,y,round(foot-.55+c,4)]))
    x0,y=roads['Falls bridge']['points'][0]
    x1,_=roads['Falls bridge']['points'][-1]
    mid=((x0+x1)/2,y)
    add('Falls bridge-deck-main','box',mid,(x1-x0)/2+4,7.5,top-2.8,top,'deck','#525e64',support='span',span='Falls bridge')
    for sign in (-1,1):
        add('Falls bridge-edge-'+str(sign),'box',(mid[0],y+sign*7.25),(x1-x0)/2,.25,top-.04,top+.64,'wall','#827e70',support='stack',parent='Falls bridge-deck-main')

    # Place collision trunks on the actual bank, keeping shoulders and the
    # channel clear. The trees have separate measured crown and trunk widths.
    rng=np.random.default_rng(608)
    roads_xy=np.vstack([sections(roads[n]) for n in ('Canyon climb','Falls bridge','Scree pass')])
    road_tree=cKDTree(roads_xy)
    grove_xy=np.array([o['center'][:2] for o in w.obstacles if o['kind']=='cylinder' and not o.get('role')])
    existing=cKDTree(grove_xy)
    accepted=[]
    for k in range(1550):
        at=rng.uniform(2080,4000)
        p=np.array([np.interp(at,river_stations,river[:,col]) for col in (0,1)])
        p+=rng.normal(0,[141,93])
        x,y=p
        dist,_=river_tree.query(p)
        if not 37<dist<265 or road_tree.query(p)[0]<19 or existing.query(p)[0]<7:
            continue
        if any(np.linalg.norm(p-q)<8 for q in accepted[-220:]): continue
        gz=w.terrain_z(x,y)
        steep=np.hypot(w.terrain_z(x+6,y)-w.terrain_z(x-6,y),w.terrain_z(x,y+6)-w.terrain_z(x,y-6))/12
        if steep>1.0: continue
        height=round(rng.uniform(11,29),2);radius=round(height*.019,3)
        bottom=min(w.terrain_z(x+u,y+v) for u,v in ((radius,0),(-radius,0),(0,radius),(0,-radius)))-.35
        add(f'falls-fir-{k}','cylinder',np.round(p,2),radius,radius,bottom,bottom+height,'conifer',
            rng.choice(['#4b5a47','#354b42','#465747','#667057','#3b5146']),crown_radius_m=round(height*rng.uniform(.13,.19),2))
        accepted.append(p)
    excluded=set(removed)
    objects=[o for o in w.obstacles if o['id'] not in excluded]+added
    vegetation=[o for o in objects if o['kind']=='cylinder' and o.get('role') in (None,'conifer')
                and -6250<o['center'][0]<-3980 and 2450<o['center'][1]<4870]
    clearance_trees=[(cKDTree(sections(roads[n])),roads[n]) for n in ('Canyon climb','Scree pass','Falls bridge')]
    obsolete={}
    for o in vegetation:
        x,y,z=o['center'];a,b,c=o['half']
        if river_tree.query([x,y])[0]<stream['width_m']/2+a:
            obsolete[o['id']]='stream bed'
        for tree,r in clearance_trees:
            distance,idx=tree.query([x,y])
            if distance>=r['width_m']/2+a+.55: continue
            road_level=r.get('deck_z_m',w.terrain_z(*tree.data[idx]))
            if z-c<road_level+4 and z+c>road_level-2.8:
                obsolete[o['id']]='carriageway or deck'
    xy=np.array([o['center'][:2] for o in vegetation])
    for i,j in sorted(cKDTree(xy).query_pairs(12)):
        a,b=vegetation[i],vegetation[j]
        if a['id'] in obsolete or b['id'] in obsolete:continue
        if (np.linalg.norm(xy[i]-xy[j])<a['half'][0]+b['half'][0]
                and abs(a['center'][2]-b['center'][2])<a['half'][2]+b['half'][2]):
            smaller=min((a,b),key=lambda o:(o['half'][2],o['id']))
            obsolete[smaller['id']]='overlapping tree solids'
    original_ids={o['id'] for o in w.obstacles}
    removed+=sorted((original_ids & obsolete.keys())-excluded)
    added=[o for o in added if o['id'] not in obsolete]
    result=dict(removed=removed,added=added,clearance_removals=obsolete)
    (PACK/'falls-06.json').write_text(json.dumps(result,separators=(',',':'))+'\n',encoding='utf-8')
    replaced=set(removed)
    retained=[o for o in w.obstacles if o['id'] not in replaced]
    landscape_light(np.rint(w.heights*10),retained+added,'relief-falls.png')
    gallery=LanternGallery()
    landscape_light(np.rint(gallery.heights*10),gallery.obstacles,'relief-gallery.png')
    print(np.count_nonzero(delta),'changed terrain samples;',sum(o.get('role')=='conifer' for o in added),
          'new conifers;',len(removed),'replaced solids;',len(obsolete),'clearance removals')


if __name__=='__main__':
    build()
