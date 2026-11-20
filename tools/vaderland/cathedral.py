"""Survey the Cathedral circuit and bake the west portal against the existing gallery."""
import gzip
import json
import math

import numpy as np

from drafting import Masonry
from streets import StreetIndex
from vtx.meridian_parallax import ParallaxInstrumentRoom
from vtx.vaderland import PACK


def alignment(world):
    roads={r['name']:r for r in world.vaderland['routes']}
    east=np.asarray(roads['Gallery east approach']['points'])
    west=np.asarray(roads['Gallery west approach']['points'])
    rim=np.asarray(roads['Sunset circuit']['points'][:207])

    def transition(a, u, d, v, t0, t1):
        distance=np.linalg.norm(d-a)
        b=a+distance*t0*u/np.linalg.norm(u)
        c=d-distance*t1*v/np.linalg.norm(v)
        t=np.linspace(0.,1.,max(16,math.ceil(distance/2.)))[:,None]
        return np.round((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d,5)

    def tie(name, points):
        return {'name':name, 'kind':'arterial','width_m':14.,'points':points.tolist()}

    e,r=179,172
    east_link=transition(east[e],east[e+1]-east[e-1],rim[r],rim[r-1]-rim[r+1],.72,.35)
    j,k=5,5
    west_link=transition(rim[j],rim[j-1]-rim[j+1],west[k],west[k+1]-west[k-1],.34,.34)

    sections=[
        (west[k:],21.5), (np.asarray(roads['Cut-and-cover gallery']['points']),21.5),
        (east[:e+1],21.5), (east_link,14.), (rim[j:r+1][::-1],26.), (west_link,14.),
    ]
    # The racing line and lane surfaces use the existing native terrain. Retain every branch.
    points=np.concatenate([xy[1:] for xy,_ in sections])
    widths=np.concatenate([np.full(len(xy)-1,width) for xy,width in sections])
    points=np.vstack([sections[0][0][0],points])
    widths=np.r_[widths[-1],widths]
    length=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
    def on(s):
        return np.array([np.interp(s,length,points[:,i]) for i in (0,1)])
    gates=[]
    for station in (180.,1050.,1590.,2040.,2875.,3490.,4290.):
        point=on(station)
        tangent=on(station+1.)-on(station-1.)
        tangent/=np.linalg.norm(tangent)
        gates.append({'center':[*point.round(5),round(world.terrain_z(*point),4)],
                      'normal':tangent.round(8).tolist(),
                      'width_m':float(widths[np.searchsorted(length,station)])})
    return {'links':[tie('Cathedral east return',east_link),tie('Cathedral west return',west_link)],
            'points':points.tolist(),'widths_m':widths.tolist(),
            'timing':{'name':'Cathedral of Velocity','length_m':round(length[-1],3),'gates':gates}}


def portal(world):
    gallery=world.vaderland['gallery']
    x0=gallery['portal_x_m'][0]
    y0=gallery['center'][1]
    level=gallery['floor_z_m']
    masonry=Masonry()

    def build(name, cloud, skin, parent=None):
        return masonry.hull('cathedral-'+name, np.asarray(cloud)+[x0,y0,level],skin,parent=parent)

    # Six increasingly tight steel-and-stone ribs key into grounded twin piers.
    # Their intrados stays entirely outside the original carriageway and above the bore.
    for i,(x,depth,span,height) in enumerate([(-42.,6.,18.1,20.7),(-32.,4.8,17.4,19.2),
                                              (-22.,4.8,16.8,17.9),(-12.,4.,16.0,16.6),
                                              (-4.8,4.,15.3,15.4),(4.,3.6,15.0,14.1)]):
        spring=3.4
        drops=[]
        for sign in (-1,1):
            outer=span+2.8
            earth=min(world.terrain_z(x0+x+dx,y0+sign*side)-level
                      for dx in (-depth*.53,depth*.53) for side in (span-.20,outer+.40))
            foot=build(f'foot-{i}-{sign}',[(x+dx,sign*side,z) for dx in (-depth*.53,depth*.53)
                       for side in (span-.20,outer+.40) for z in (earth-1.15,max(.28,earth+.21))],
                       'cathedralStone')
            pier=build(f'pier-{i}-{sign}',[(x+dx,sign*side,z) for dx in (-depth/2,depth/2)
                       for side in (span-.09,outer) for z in (max(.25,earth+.18),spring+.29)],'cathedralIron',foot)
            drops.append(pier)
            build(f'pier-lamp-{i}-{sign}',[(x+dx,sign*side,z) for dx in (-depth*.52,-depth*.49)
                  for side in (span+.28,span+.42) for z in (.91,spring+.17)],
                  'cathedralAmber' if sign<0 else 'cathedralViolet',pier)
        previous=drops[1]
        flank=2.7 if i==0 else 1.55
        for j in range(24):
            a,b=j*math.pi/24,(j+1)*math.pi/24
            def panel(t0,t1,xrange,rises):
                return [(x+d,(span+rise)*math.cos(t),spring+(height+rise)*math.sin(t))
                        for d in xrange for t in (t0,t1) for rise in rises]
            previous=build(f'arch-{i}-{j}',panel(a,b,(-depth/2,depth/2),(0.,flank)),
                           'cathedralIron' if i%2==0 else 'cathedralStone',previous)
            if j%3!=2:
                build(f'arc-lamp-{i}-{j}',panel(a+.012,b-.012,(-depth*.51,-depth*.498),(.16,.36)),
                      'cathedralAmber' if j%3==0 or i==0 else 'cathedralViolet',previous)
            if i==0:
                build(f'stone-frame-{j}',panel(a,b,(-depth*.42,depth*.39),(flank-.12,flank+.91)),
                      'cathedralStone',previous)
    anchor='cathedral-arch-0-11'
    build('crest-sign',[(-45.65+s,y,z) for s in (0.,.68) for y in (-4.75,4.75)
                         for z in (22.63,25.56)],'cathedralIron',anchor)
    return masonry.solids,{'portal_origin':[x0,y0,level],'sign':[x0-45.675,y0,level+24.19],
                           'bore':gallery,'name':'Cathedral of Velocity'}


def author(world):
    course=alignment(world)
    solids,visual=portal(world)
    streets=StreetIndex(world,[r for r in world.vaderland['routes'] if 'Gallery' in r['name'] or 'gallery' in r['name']]+course['links'])
    intruders={o['id']:hit for o in solids if (hit:=streets.overlaps(o,headroom=6.6))}
    if intruders:
        raise ValueError(intruders)
    return {'course':course,'solids':solids,'visual':visual}


if __name__=='__main__':
    design=author(ParallaxInstrumentRoom())
    raw=json.dumps(design,separators=(',',':'),allow_nan=False).encode()
    (PACK/'cathedral-22.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    print(design['course']['timing']['length_m'], 'metres and',len(design['solids']),'portal hulls')
