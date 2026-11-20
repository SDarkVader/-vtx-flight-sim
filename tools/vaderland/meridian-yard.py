"""Survey and bake the Meridian Handling Yard on the east side of Exchange Boulevard."""
import gzip
import json
import math

import numpy as np

from drafting import Masonry
from streets import StreetIndex
from vtx.cathedral import CathedralRaceApproach
from vtx.vaderland import PACK


CENTER = (1065.,2599.)


def oval(name,width,radius,straight):
    x,y=CENTER
    stations=max(12,math.ceil(math.pi*radius/1.65))
    cuts=max(6,math.ceil(2*straight/1.65))
    points=[]
    for side,theta in ((1,-math.pi/2),(-1,math.pi/2)):
        y_start=y-side*radius
        points.extend((u,y_start) for u in np.linspace(x-side*straight,x+side*straight,cuts,endpoint=False))
        points.extend((x+side*straight+radius*math.cos(a),y+radius*math.sin(a))
                      for a in np.linspace(theta,theta+math.pi,stations,endpoint=False))
    return dict(name=name,kind='experimental',width_m=width,
                points=np.round([*points,points[0]],5).tolist())


def positions(route):
    p=np.array(route['points'])
    return p,np.r_[0.,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]


def timing(world,route):
    p,chain=positions(route)
    def at(s):
        return np.array([np.interp(s,chain,p[:,k]) for k in (0,1)])
    gates=[]
    for s in (42.,42+chain[-1]*.25,42+chain[-1]*.50,42+chain[-1]*.75):
        s=s%chain[-1]
        pt=at(s); tangent=at(s+.80)-at(s-.80)
        tangent/=np.linalg.norm(tangent)
        gates.append({'center':[*pt.round(5),round(world.terrain_z(*pt),4)],
                      'normal':tangent.round(8).tolist(),'width_m':route['width_m']})
    return dict(name=route['name'],length_m=round(chain[-1],3),gates=gates)


def tie(name,width,a,b,c,d):
    s=np.linspace(0.,1.,80)[:,None]
    p=(1-s)**3*a+3*(1-s)**2*s*b+3*(1-s)*s*s*c+s**3*d
    return dict(name=name,kind='experimental',width_m=width,points=p.round(5).tolist())


def fittings(world):
    m=Masonry()
    def base(name,x,y,a,b,skin):
        ground=min(world.terrain_z(x+i*a,y+j*b) for i in (-1,1) for j in (-1,1))
        return m.box('yard-'+name,x,y,ground-.58,ground+.25,a,b,skin),ground

    def timing_board(key,x,y):
        foot,z=base(key+'-pad',x,y,1.23,3.53,'yardStone')
        post=m.box('yard-'+key+'-mount',x,y,z+.22,z+3.07,.42,.62,'yardMetal',parent=foot)
        m.box('yard-'+key+'-console',x,y,z+1.82,z+4.04,.41,3.26,'yardMetal',parent=post)
        return [x-.56,y,z+2.93]

    boards=[timing_board('wide-timing',1067.,2548.),timing_board('precision-timing',1080.,2593.)]
    # Low markers have a clearance margin from the opposing swept envelopes.
    for label,rows,skin in (
        ('wide',[(1027,2552),(1114,2551),(1152,2600),(1113,2644),(1018,2644),(973,2599)],'yardAmber'),
        ('precision',[(1040,2576),(1091,2576),(1091,2624),(1040,2624)],'yardTeal'),
    ):
        for i,(x,y) in enumerate(rows):
            key=f'{label}-marker-{i}'
            foot,z=base(key,x,y,.75,.75,'yardStone')
            post=m.box('yard-'+key+'-post',x,y,z+.23,z+1.95,.36,.36,'yardMetal',parent=foot)
            for j,(lo,hi) in enumerate(((.48,.67),(1.41,1.62))):
                m.box(f'yard-{key}-lamp-{j}',x,y,z+lo,z+hi,.371,.371,skin,parent=post)

    # A small equipment shelter sits outside the wider loop's eastern arc.
    for i,x in enumerate((1150.,1161.)):
        foot,z=base(f'shelter-{i}-base',x,2556.,1.6,1.6,'yardStone')
        post=m.box(f'yard-shelter-{i}-post',x,2556.,z+.23,z+4.9,.43,1.15,'yardMetal',parent=foot)
        m.box(f'yard-shelter-{i}-lamp',x,2556.,z+2.05,z+2.24,.45,1.17,'yardAmber',parent=post)
        if i==0: left,z0=post,z
    eave=min(z,z0)+4.9
    roof=m.box('yard-shelter-roof',1155.5,2556.,eave-.10,eave+.55,7.05,4.2,'yardMetal',parent=left)
    m.box('yard-shelter-edge',1155.5,2551.8,eave-.04,eave+.12,6.99,.11,'yardTeal',parent=roof)
    return m.solids,boards


def make_yard(world):
    outer=oval('Handling Loop',16.,35.,41.)
    inner=oval('Precision Loop',5.6,16.5,29.)
    y0=2564.
    y1=CENTER[1]-16.5
    boulevard=next(r for r in world.vaderland['routes'] if r['name']=='Exchange Boulevard')
    xy=np.asarray(boulevard['points'])
    start=np.array([958.,np.interp(958.,xy[:,0],xy[:,1])])
    boulevard_join=tie('Handling Yard Access',12.,start,start+[40,-3.72],
                        np.array([1004.,y0]),np.array([1041.,y0]))
    precision_in=tie('Precision Entry',5.6,np.array([1027.,y0]),np.array([1045.,y0]),
                      np.array([1047.,y1]),np.array([1063.,y1]))
    precision_out=tie('Precision Exit',5.6,np.array([1089.,CENTER[1]+16.5]),np.array([1074.,CENTER[1]+16.5]),
                       np.array([1065.,2634.]),np.array([1044.,2634.]))
    roads=[outer,inner,boulevard_join,precision_in,precision_out]
    for route,tint in zip(roads,('#d6a26b','#81e3e0','#d6a26b','#81e3e0','#81e3e0')):
        route['edge_color']=tint
    index=StreetIndex(world,roads)
    neighbor=lambda o: 900<o['center'][0]<1275 and 2460<o['center'][1]<2720
    legacy_hits={o['id']:hit for o in world.obstacles if neighbor(o)
                 and (hit:=index.overlaps(o,headroom=4.85))}
    if legacy_hits:raise ValueError(legacy_hits)
    solid,boards=fittings(world)
    combined=StreetIndex(world,[boulevard,*roads])
    novel_hits={o['id']:hit for o in solid if (hit:=combined.overlaps(o,headroom=4.85))}
    if novel_hits:raise ValueError(novel_hits)
    return {'solids':solid,'roads':roads,'yard':{'point':[1065.,2599.],
            'courses':[timing(world,outer),timing(world,inner)],'boards':boards,
            'access':start.tolist()}}


if __name__=='__main__':
    design=make_yard(CathedralRaceApproach())
    raw=json.dumps(design,separators=(',',':'),allow_nan=False).encode()
    (PACK/'meridian-yard-25.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    print([(x['name'],x['length_m']) for x in design['yard']['courses']],len(design['solids']),'hulls')
