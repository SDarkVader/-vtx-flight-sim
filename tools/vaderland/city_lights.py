"""Build the three Meridian Avenue roof structures from surveyed bearing surfaces in metres."""
import gzip
import json
import math

import numpy as np

from drafting import Masonry
from vtx.vaderland import MarketQuarter, PACK


def author():
    world = MarketQuarter()
    structures = {o['id']: o for o in world.obstacles}
    lots = {s['id'].removesuffix('-shops'): s for s in world.vaderland['quarter']['lots']}
    masonry = Masonry()
    places = []

    def site(lot_id, deck_name, title, axis=None):
        deck = structures[lot_id + '-' + deck_name]
        lot = lots[lot_id]
        center = np.asarray(deck['center'][:2])
        u = np.asarray(axis if axis is not None else lot['axis'], dtype=float)
        u /= np.linalg.norm(u)
        v = np.array([-u[1], u[0]])
        if axis is None and v @ lot['front'] < 0:
            v = -v
        top = deck['center'][2] + deck['half'][2]
        places.append(dict(name=title, point=center.round(4).tolist(), roof_m=round(top,4), support=deck['id']))

        def point(x,y,z):
            return [*(center + u*x + v*y), top+z]

        def solid(name, coords, finish, parent=deck['id'], **kwargs):
            return masonry.hull(name,[point(*p) for p in coords],finish,parent=parent,**kwargs)

        return solid, point, deck['id']

    make, _, roof = site('market-block-13','roof','Exchange Wintergarden')
    def arch_height(u):
        return 3.2 + 12.4*math.sin(math.pi*(u+20)/40)**.78 + 2.7*(u+20)/40

    def canopy_section(u, width=9.3):
        h=arch_height(u)
        return [[u,-width,h-1.65],[u,width,h],[u,width,h+.85],[u,-width,h-.80]]

    glass = make('wintergarden-gallery',
                 [[x,y,z] for x in (-15.5,15.5) for y in (-7.5,7.5) for z in (-.06,7.35)],
                 'city17atrium')
    for j,x in enumerate((-18.6,-12.,0.,12.,18.6)):
        h=arch_height(x)
        for side in (-1,1):
            v=side*8.7
            lean = .018 if abs(x)>18 else .095
            make(f'wintergarden-frame-{j}-{side}',
                 [[x+dx+a,v+dv+b,z] for dx,dv,z in
                  [(0.,0.,-.06),(-x*lean*.55,-side*.45,h*.64),(-x*lean,0.,h+(.79 if side>0 else -.86))]
                  for a in (-.39,.39) for b in (-.40,.40)],'city17titanium')
    previous = None
    for i,(a,b) in enumerate(zip(np.linspace(-19.7,19.7,17)[:-1],np.linspace(-19.7,19.7,17)[1:])):
        panel=make(f'wintergarden-vault-{i}',canopy_section(a)+canopy_section(b),'city17soffit',
                   previous or 'wintergarden-frame-0-1')
        def band(v,z0,z1,depth):
            return [[x,v+d,arch_height(x)+z] for x in (a,b) for d in (0.,depth) for z in (z0,z1)]
        eave=make(f'wintergarden-eave-{i}',band(9.24,.12,.98,.24),'city17brass',panel)
        make(f'wintergarden-light-{i}',band(9.47,.13,.23,.035),'lamplens',eave)
        if -16.1<a and b<16.1:
            for side in (-1,1):
                v=side*8.65
                pane=make(f'wintergarden-clerestory-{i}-{side}',
                     [[x,v+t,z] for x in (a,b) for t in (-.10,.10)
                      for z in (7.10,arch_height(x)+(-1.58 if side<0 else -.02))],
                     'city17atrium',panel)
                make(f'wintergarden-mullion-{i}-{side}',
                     [[a+dx,v+dy,z] for dx in (-.078,.078) for dy in (-.13,.13)
                      for z in (7.10,arch_height(a)+(-1.58 if side<0 else -.02))],
                     'city17brass',pane)
        previous=panel
    make('wintergarden-mezzanine',[[x,y,z] for x in (-15.55,15.55) for y in (-7.55,7.55)
         for z in (3.85,4.12)],'city17soffit',glass)

    make, _, roof = site('market-block-24','cap','Northlight Relay',axis=(.94,.342))
    feet=[]
    for side in (-1,1):
        foot=make(f'northlight-abutment-{side}',
             [[side*x,y,z] for x0,x1,z,depth in [(3.5,7.8,-.12,2.2),(8.3,13.7,8.0,1.55),(10.9,14.5,16.65,1.4)]
              for x in (x0,x1) for y in (-depth,depth)],'city17titanium')
        feet.append(foot)
        make(f'northlight-buttress-{side}',
             [[side*x,y,z] for x0,x1,z,depth in [(9.8,11.1,-35.,.6),(9.1,12.4,-13.,1.15),
                                                  (4.9,8.0,1.2,1.52)]
              for x in (x0,x1) for y in (-depth,depth)],'city17brass',foot)
    # A true annulus built from convex sectors leaves the opening clear in both renderers.
    def rim(a,b,ri,ro,y0,y1):
        return [[math.cos(t)*r,y,16.2+math.sin(t)*r*1.10]
                for t in (a,b) for r in (ri,ro) for y in (y0,y1)]
    for i in range(40):
        a=i*math.tau/40; b=(i+1)*math.tau/40
        # Number clockwise from the east spring so each segment bears through its neighbour.
        parent=feet[1] if i==0 else f'northlight-rim-{i-1}'
        ring=make(f'northlight-rim-{i}',rim(a,b,10.55,14.,-1.25,1.25),'city17titanium',parent)
        make(f'northlight-reveal-{i}',rim(a,b,10.50,11.26,-1.29,-1.22),'city17brass',ring)
        if i%5==0:
            coords=[[math.cos(t)*r,y,16.2+math.sin(t)*r*1.10]
                    for t,r in [(a,13.95),(a+.13,13.95),(a+.52,11.13),(a+.38,11.13)]
                    for y in (-1.46,-1.18)]
            make(f'northlight-blade-{i}',coords,'city17brass',ring)
        if i%10 not in (2,3):
            make(f'northlight-guide-{i}',rim(a+.012,b-.012,11.42,11.58,-1.30,-1.23),
                 'city17signal' if i%10==5 else 'lamplens',ring)

    make, point, roof=site('market-block-52','cap','Vesper Observatory')
    def circular(levels,n=32):
        return [[r*math.cos(t),r*math.sin(t),h] for r,h in levels for t in np.arange(n)*math.tau/n]
    base=make('vesper-foot',circular([(7.6,-.10),(8.9,1.38)]),'city17soffit')
    drum=make('vesper-reading-room',circular([(8.2,1.27),(8.2,7.05)]),'city17atrium',base)
    curb=make('vesper-bearing',circular([(8.65,6.83),(9.05,7.62)]),'city17brass',drum)
    origin=point(0,0,7.51)
    motion=dict(name='vesper-sunshade',origin=origin,period_s=240.)
    collar=make('vesper-turntable',circular([(8.8,7.48),(9.10,8.02)]),'blacksteel',curb,motion=motion)
    for i in range(9):
        angle=i*math.tau/9
        parent=collar
        for j in range(4):
            def cross(s):
                a=angle+.69*s
                r=8.90-5.65*s*s
                h=7.91+8.8*math.sin(s*math.pi*.49)
                return [[(r+dr)*math.cos(a+da),(r+dr)*math.sin(a+da),h+dh]
                        for dr in (-.46,.30) for da,dh in [(-.126,0.),(.125,.56)]]
            parent=make(f'vesper-vane-{i}-{j}',cross(j/4)+cross((j+1)/4),
                        'city17brass' if i%3==0 else 'city17titanium',parent,motion=motion)
    for entry,motif in zip(places,('swept gallery','open optical crown','rotating sunshade')):
        entry['form']=motif
    return dict(places=places, solids=masonry.solids)


if __name__=='__main__':
    data=author()
    raw=json.dumps(data,separators=(',',':'),allow_nan=False).encode()
    (PACK/'city-lights-17.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    print(len(data['solids']),[p['name'] for p in data['places']])
