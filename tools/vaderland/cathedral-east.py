"""Bake Lantern Paddock and its first timed quarry circuit off the Cathedral bypass."""
import gzip
import json
import math

import numpy as np
from scipy.interpolate import CubicSpline

from drafting import Masonry
from parallax_court_review import intersect
from streets import StreetIndex, footprint
from vtx.vaderland import PACK
from vtx.vertical_loops import CathedralVerticalLoops
from vtx.world import MapPoint


PADDOCK = 'Lantern Paddock'
QUARRY = 'Lantern Quarry'
GOLD = '#f4b060'
LILAC = '#a88df6'


def curve(name, width, anchors, color, kind='experimental', closed=False):
    points = np.asarray(anchors, dtype=float)
    length = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    smooth = CubicSpline(length, points, bc_type='periodic' if closed else 'not-a-knot')
    samples = smooth(np.linspace(0, length[-1], math.ceil(length[-1]/2.)+1))
    return dict(name=name, width_m=width, kind=kind, edge_color=color, points=samples.round(5).tolist())


def join(route, x):
    p = np.asarray(route['points'])
    return [x, float(np.interp(x, p[:,0], p[:,1]))]


def earthworks(world):
    # New pads and banks are confined to the parcel between the switchback
    # return and Sunset. The landscaped rim tapers out before the old routes.
    step = 2*world.half/(world.n-1)
    def cell(x):
        return round((x+world.half)/step)
    changes = []
    start_z = world.terrain_z(4160.,-3860.)
    def blend(distance,flat,falloff):
        f=np.clip((abs(distance)-flat)/falloff,0.,1.)
        return 1. - f*f*(3.-2.*f)
    for j in range(cell(-3900),cell(-3700)+1):
        y = -world.half+j*step
        for i in range(cell(3900),cell(4420)+1):
            x = -world.half+i*step
            rise = 0.
            for cx,cy,rx,ry,height in ((4035,-3787,113,59,5.8),
                                         (4208,-3794,102,49,5.6),
                                         (4308,-3780,66,82,3.7),
                                         (4121,-3736,65,41,-1.3)):
                r2 = ((x-cx)/rx)**2+((y-cy)/ry)**2
                rise += height*max(0.,1-r2)**3
            grade = blend(x-4160.,60.,35.)*blend(y+3860.,20.,22.)
            rise = round((1-grade)*rise+grade*(start_z-world.heights[j,i]),4)
            if abs(rise)>.001:
                world.heights[j,i] += rise
                changes.append([j,i,round(float(world.heights[j,i]),5)])
    return changes


def length_of(points):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]


def course(world, road, first):
    points = np.asarray(road['points'])
    chain = length_of(points)
    finish = chain[-1]
    at = lambda s: np.array([np.interp(s%finish,chain,p) for p in points.T])
    gates = []
    for shift in (0.,.24,.50,.78):
        s = first+shift*finish
        xy = at(s)
        tangent = at(s+1.)-at(s-1.)
        tangent /= np.linalg.norm(tangent)
        gates.append(dict(center=[*xy.round(6),world.terrain_z(*xy)],
                          normal=tangent.round(8).tolist(),width_m=road['width_m']))
    return dict(name=road['name'],length_m=round(float(finish),3),gates=gates)


def footing(masonry, world, name, x, y, half_x, half_y, top, skin='eastStone'):
    ground = min(world.terrain_z(x+a*half_x,y+b*half_y) for a in (-1,1) for b in (-1,1))
    key = masonry.box('east-'+name,x,y,ground-1.25,top,half_x,half_y,skin)
    return key


def roof(masonry, name, x, y, z, a, b, rise, parent):
    front = z
    back = z+rise
    return masonry.hull('east-'+name,
       [(x+i*a*(1.02 if k==0 else 1),y+j*b,(front if j==-1 else back)+k*.66)
        for i in (-1,1) for j in (-1,1) for k in (0,1)],'eastSteel',parent=parent)


def workshops(world,masonry):
    signs = []
    for k,x in enumerate((3906.,3942.,3978.,4014.,4050.)):
        y = -3892.5
        z = max(world.terrain_z(x+i*16,y+j*11) for i in (-1,1) for j in (-1,1))+.15
        stone = footing(masonry,world,f'workshop-{k}-slab',x,y,16.,11.,z,'eastApron')
        back = masonry.box(f'east-workshop-{k}-rear',x,y+10.05,z-.08,z+9.34,16.,.96,'eastSteel',parent=stone)
        for side in (-1,1):
            pier = masonry.box(f'east-workshop-{k}-side-{side}',x+side*14.8,y-.35,z-.08,z+8.2,1.17,10.62,'eastSteel',parent=stone)
            masonry.box(f'east-workshop-{k}-beacon-{side}',x+side*14.8,y-11.05,z+.42,z+6.05,.35,.20,'eastGold',parent=pier)
        top = roof(masonry,f'workshop-{k}-roof',x,y,7.5+z,16.45,11.2,1.47,back)
        masonry.box(f'east-workshop-{k}-header',x,y-10.55,z+6.8,z+8.1,15.95,.47,'eastSteel',parent=top)
        masonry.box(f'east-workshop-{k}-lamp',x,y-7.9,z+7.61,z+8.02,11.6,.22,'eastCream',parent=top)
        masonry.box(f'east-workshop-{k}-bench',x,y+7.7,z-.06,z+1.18,8.9,1.56,'eastSteel',parent=stone)
        for n in range(3):
            masonry.box(f'east-workshop-{k}-locker-{n}',x+(n-1)*7.,y+9.24,z+1.15,z+3.49,
                         2.18,.54,'eastViolet' if n==1 else 'eastAmberGlass',parent=back)
        signs.append(dict(label=f'WORKSHOP {k+1:02d}',point=[x,y-11.13,z+7.13],width=15.,height=1.,normal='south'))
        approach = []
        for ramp_y,end in ((-3921.,False),(-3903.38,True)):
            for ramp_x in (x-11.7,x+11.7):
                ramp_z = z+.014 if end else world.terrain_z(ramp_x,ramp_y)-.14
                approach.extend(((ramp_x,ramp_y,ramp_z),(ramp_x,ramp_y,ramp_z-1.)))
        masonry.hull(f'east-workshop-{k}-roll-on',approach,'eastApron',parent=stone)
    return signs


def terrace(world,masonry):
    x,y=4111.,-3971.
    z=max(world.terrain_z(x+i*44,y+j*13) for i in (-1,1) for j in (-1,1))+.38
    base=footing(masonry,world,'terrace-base',x,y,44,13,z)
    parent=base
    for j in range(6):
        aft=25-j*3.6
        cy=y+(25-aft)*.5
        step=masonry.box(f'east-terrace-tier-{j}',x,cy,z+(j-.35)*.67,z+(j+1)*.67,
                          43.8-j*.7,aft/2,'eastStone',parent=parent)
        masonry.box(f'east-terrace-stair-lamp-{j}',x,cy-aft/2+.04,z+(j+.33)*.67,z+(j+.57)*.67,
                    41.7-j*.7,.14,'eastGold' if j%2==0 else 'eastViolet',parent=step)
        parent=step
    for j,dx in enumerate((-37.,-18.5,0.,18.5,37.)):
        pole=masonry.box(f'east-terrace-pillar-{j}',x+dx,y+10.,z+3.3,z+12.6,1.1,1.08,'eastSteel',parent=parent)
        masonry.box(f'east-terrace-pillar-light-{j}',x+dx,y+8.96,z+4.2,z+11.65,.36,.16,'eastGold',parent=pole)
    top=roof(masonry,'terrace-shroud',x,y,11.9+z,47,13.8,.83,pole)
    masonry.box('east-terrace-stadium-strip',x,y-12.8,z+11.72,z+12.31,46.6,.22,'eastViolet',parent=top)
    return dict(label='LANTERN PADDOCK',point=[x,y+14.01,z+12.95],width=37.,height=2.1,normal='north')


def race_control(world,masonry):
    x,y=4162.,-3897.
    z=max(world.terrain_z(x+a*35,y+b*15) for a in (-1,1) for b in (-1,1))+.18
    base=footing(masonry,world,'control-foundation',x,y,35.,16.,z,'eastStone')
    low=masonry.hull('east-control-podium',[(x+a*s,y+b*t,z+h) for a in (-1,1) for b in (-1,1)
                     for s,t,h in ((34.8,15.8,-.1),(30.5,13.4,7.))],
                     'eastSteel',parent=base)
    glass=masonry.hull('east-control-box',[(x+a*s,y+b*t,z+h) for a in (-1,1) for b in (-1,1)
                      for s,t,h in ((23.9,11.7,6.9),(29.,13.1,15.4))],
                      'eastAmberGlass',parent=low)
    top=roof(masonry,'control-roof',x,y,z+14.93,33.6,16.,1.4,glass)
    for j in range(9):
        xx=x-24.+6*j
        masonry.hull(f'east-control-rib-{j}',[(xx+a*.32,y+b*r,z+h) for a in (-1,1) for b in (-1,1)
                     for r,h in ((11.75,7.),(13.19,15.45))],'eastSteel',parent=glass)
    for side in (-1,1):
        masonry.box(f'east-control-cornice-{side}',x,y+side*15.4,z+15.04+(1.4 if side==1 else 0),
                    z+15.55+(1.4 if side==1 else 0),32.8,.35,'eastGold',parent=top)
    return dict(label='LANTERN QUARRY',point=[x,y-15.98,z+5.0],width=42.,height=3.15,normal='south')


def quarry_edges(world,masonry,road):
    rng=np.random.default_rng(8753)
    outcrops=((4013,-3787,22,14,7), (4055,-3782,24,16,9), (4091,-3797,14,9,5),
              (4168,-3795,16,12,6), (4202,-3785,25,16,10), (4238,-3792,18,14,7),
              (4268,-3782,13,9,5), (4285,-3791,7,6,3), (3994,-3811,8,6,4),
              (4020,-3762,8,5,3), (4216,-3759,9,6,3), (4077,-3819,10,7,4),
              (4102,-3797,9,7,4), (4173,-3815,10,6,4), (4270,-3759,8,6,3))
    for i,(x,y,a,b,h) in enumerate(outcrops):
        ground=world.terrain_z(x,y)
        points=[]
        for angle in np.arange(9)*math.tau/9:
            r=rng.uniform(.73,1.15)
            dx,dy=a*math.cos(angle)*r,b*math.sin(angle)*r
            bottom=min(ground,world.terrain_z(x+dx,y+dy))-1.5
            points.extend(((x+dx,y+dy,bottom),
                           (x+.71*dx+2,y+.69*dy-1,ground+h*rng.uniform(.51,1.11))))
        masonry.hull(f'east-quarry-face-{i}',points,'eastBasalt')
    xy=np.asarray(road['points'])
    length=length_of(xy)
    for i,station in enumerate(np.linspace(22.,length[-1]-22.,26)):
        k=np.searchsorted(length,station)
        p=xy[k]
        u=xy[k+2]-xy[k-2]
        across=np.array([-u[1],u[0]])/np.linalg.norm(u)
        side=1. if i%2 else -1.
        x,y=p+side*10.4*across
        z=world.terrain_z(x,y)
        stem=footing(masonry,world,f'quarry-marker-{i}',x,y,.40,.40,z+1.37,'eastSteel')
        masonry.box(f'east-quarry-stud-{i}',x,y,z+1.11,z+1.40,.41,.41,
                    'eastGold' if i%3 else 'eastViolet',parent=stem)


def gantry(world,masonry,timing):
    gx,gy,_ = timing['gates'][0]['center']
    z=world.terrain_z(gx,gy)
    reach=9.2
    top=z+7.5
    for side in (-1,1):
        y=gy+side*reach
        base=footing(masonry,world,f'timing-base-{side}',gx,y,1.5,1.4,z+.42)
        pole=masonry.box(f'east-timing-pole-{side}',gx,y,z+.31,top,1.1,.86,'eastSteel',parent=base)
        masonry.box(f'east-timing-light-{side}',gx-1.11,y,z+.9,top-.42,.18,.42,'eastViolet',parent=pole)
    masonry.box('east-timing-rail',gx,gy,top-1.22,top+.62,1.16,reach+1.15,'eastSteel',parent=pole)
    return dict(label='LANTERN QUARRY',point=[gx-1.25,gy,top-.21],width=17.2,height=1.55,normal='west')


def route_metrics(world, road):
    xy=np.asarray(road['points'])
    ds=np.diff(length_of(xy))
    rise=np.diff([world.terrain_z(*p) for p in xy])
    n=np.diff(xy,axis=0)/ds[:,None]
    ang=np.abs(np.arctan2(n[1:,0]*n[:-1,1]-n[1:,1]*n[:-1,0],np.sum(n[1:]*n[:-1],axis=1)))
    turning=ang>1e-5
    radius=(ds[1:]+ds[:-1])[turning]/(2*ang[turning])
    return dict(length_m=round(float(ds.sum()),3),max_grade_pct=round(float(max(abs(rise/ds))*100),3),
                min_radius_m=round(float(radius.min()),2),width_m=road['width_m'])


def bake(world):
    legacy=StreetIndex(world)
    terrain=earthworks(world)
    roads={r['name']:r for r in world.vaderland['routes']}
    access=roads['Cathedral Switchback access']
    sunset=roads['Sunset circuit']
    lanes=[
        curve('Paddock Link',13.,[join(access,3731.),(3749.,-4122.),(3780.,-4018.),
                           (3835.,-3955.),(3900.,-3930.),(4040.,-3930.),(4271.,-3930.),
                           (4392.,-3903.),(4434.,-3834.),(4453.,-3723.),join(sunset,4498.)],GOLD),
        curve(QUARRY,13.,[(4000.,-3844.),(4115.,-3861.),(4242.,-3854.),(4319.,-3827.),
                  (4335.,-3781.),(4302.,-3743.),(4233.,-3722.),(4158.,-3743.),
                  (4066.,-3726.),(3992.,-3733.),(3943.,-3766.),(3943.,-3810.),(4000.,-3844.)],
                  LILAC,'quarry',closed=True),
    ]
    quarry=lanes[1]
    before=[p for p in quarry['points'][:100] if 4060<p[0]<4070]
    stop=before[0]
    lanes.append(curve('Quarry Pit Exit',9.,[join(lanes[0],4072.),(4083.,-3914.),(4078.,-3882.),stop],GOLD))
    # Clear arrival pockets to the open sides of the workshop bays.
    for x in (3906,3942,3978,4014,4050):
        lanes.append(dict(name=f'Workshop apron {x}',kind='experimental',width_m=24.,edge_color=GOLD,
                    points=[join(lanes[0],x),[x,-3904.7]]))
    timing=course(world,quarry,191.)
    masonry=Masonry()
    signs=[*workshops(world,masonry),terrace(world,masonry),race_control(world,masonry),
              gantry(world,masonry,timing)]
    quarry_edges(world,masonry,quarry)
    existing=StreetIndex(world,[*world.vaderland['routes'],*lanes[:3]])
    if obstructed := {o['id']:hit for o in masonry.solids if (hit:=existing.overlaps(o,headroom=5.6))}:
        raise ValueError(f'Road clearance: {obstructed}')
    hulls={o['id']:o for o in masonry.solids}
    if floating := [o['id'] for o in masonry.solids if o.get('parent')
                    and not intersect(o,hulls[o['parent']])]:
        raise ValueError(f'Structure joints: {floating}')
    for j,i,_ in terrain:
        xy=[-world.half+i*20.,-world.half+j*20.]
        influence=dict(kind='box',center=[*xy,world.terrain_z(*xy)+1.],half=[21.,21.,2.])
        if hit:=legacy.overlaps(influence):
            raise ValueError(f'Earthworks approach existing road: {xy} {hit}')
    available=[p for p in quarry['points'][:100] if 4100<p[0]<4170
               and world.validate(MapPoint(x_m=p[0],y_m=p[1]),'departure').valid]
    if not available:
        raise ValueError('Quarry start has no valid supported departure')
    paddock=dict(name=PADDOCK,point=[4050.,-3930.],signs=signs,course=timing,
                  spawn=available[0],quarry=route_metrics(world,quarry),
                  entry=lanes[0]['points'][0],sunset=lanes[0]['points'][-1])
    return dict(terrain=terrain,roads=lanes,solids=masonry.solids,paddock=paddock)


if __name__=='__main__':
    result=bake(CathedralVerticalLoops())
    data=json.dumps(result,separators=(',',':'),allow_nan=False).encode()
    (PACK/'cathedral-east-27.json.gz').write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
    print(result['paddock']['quarry'], 'earthwork cells',len(result['terrain']),
          'native solids',len(result['solids']))