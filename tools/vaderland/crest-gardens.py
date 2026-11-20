"""Author the Crest Gardens park, arch and lamp positions on surveyed terrain."""
import json
import math
from pathlib import Path

import numpy as np

from drafting import Masonry
from streets import StreetIndex
from vtx.vaderland import PACK
from vtx.world import make_world

CENTER = [-200., 2210.]
HALF = [31., 23.]
X, Y = CENTER

def bake(world):
    arch = Masonry()
    terrain = world.terrain_z
    basin=[X+19.3,Y-5.4]
    trees = []
    lamps = []

    for i, (u,v,h) in enumerate([
        (-25,-17,10.1), (-15,-14,8.5), (-25,-5,9.2), (-22,13,12.4),
        (-12,17,9.0), (25,-16,9.8), (15,-13,8.8), (27,1.2,11.5),
        (24,14,12.0), (13,18,8.5), (-26,19,8.8), (28,20,10.2),
    ]):
        x,y=X+u,Y+v
        z=terrain(x,y)
        r=.19+h*.011
        if abs(x-basin[0])<8.25+r and abs(y-basin[1])<4.25+r:
            raise ValueError(f'Tree {i} intersects the reflecting basin')
        trunk=[[x+math.cos(t)*r,y+math.sin(t)*r,height] for t in np.arange(8)*math.tau/8
               for height in (z-.19,z+h*.66)]
        arch.hull(f'crest-gardens-tree-{i:02d}',trunk,'gardenBark')
        trees.append(dict(position=[x,y,z],height=h,turn=i*1.71,kind=i%3))

    for side in (-1,1):
        x=X+side*8.8
        for u,v in [(0,-19),(1,-7),(1,5),(0,19)]:
            sy=Y+v
            sx=x+side*u
            z=terrain(sx,sy)
            height=3.25+(u*.4)
            base=arch.box(f'crest-gardens-lamp-base-{side}-{v}',sx,sy,z-.12,z+.26,.28,.31,'gardenBronze')
            mast=arch.box(f'crest-gardens-lamp-mast-{side}-{v}',sx,sy,z+.19,z+height-.10,.092,.085,'gardenSteel',parent=base)
            y_axis=[sx-side*.18,sy,z+height-.12]
            arch.box(f'crest-gardens-lamp-glass-{side}-{v}',*y_axis[:2],z+height-.18,z+height,.26,.134,
                     'gardenWarm' if side==-1 else 'gardenPearl',parent=mast)
            lamps.append(dict(position=y_axis,range_m=12.5, color='#ffb663' if side==-1 else '#9ed9f5'))

    for bias in (-1,1):
        for v in (-12.5,12.):
            x,y=X+bias*15.2,Y+v
            z=terrain(x,y)
            arch.box(f'crest-gardens-bench-{bias}-{v}',x,y,z-.14,z+.49,1.91,.40,'gardenWood')

    # One climbable garden-side wall supports the actual canopy rim. The central
    # plaza path remains open under the vault.
    canopy_y=Y+7.8
    arch_datum=max(terrain(X+u,canopy_y) for u in (-22,0,22))
    def arch_top(u):
        return arch_datum+4.1+5.7*math.cos(math.pi*u/45)
    for u in (-22.,22.):
        for v in (-4.8,4.8):
            x,y=X+u,canopy_y+v
            bottom=terrain(x,y)
            footing=arch.box(f'crest-gardens-vault-base-{u}-{v}',x,y,bottom-.18,bottom+.44,.52,.64,'gardenStone')
            arch.hull(f'crest-gardens-vault-column-{u}-{v}',
                [[x+dx,y+dy,z] for z,wx,wy in [(bottom+.30,.29,.26),(arch_top(u)-.35,.49,.37)]
                  for dx in (-wx,wx) for dy in (-wy,wy)],'gardenSteel',parent=footing)
    for i,(u,v) in enumerate(zip(np.linspace(-22.,22.,17)[:-1],np.linspace(-22.,22.,17)[1:])):
        for side in (-1,1):
            arch.hull(f'crest-gardens-glass-{i}-{side}',
                [[X+t,cy,arch_top(t)+h] for t in (u,v) for cy in (canopy_y,canopy_y+5.1*side)
                  for h in (-.17,.05)],'gardenGlass',
                parent='crest-gardens-vault-column--22.0--4.8' if i==0 else f'crest-gardens-glass-{i-1}-{side}')
        for edge in (-4.8,0.,4.8):
            arch.hull(f'crest-gardens-rib-{i}-{edge}',
                [[X+t,canopy_y+edge+dy,arch_top(t)+z] for t in (u,v)
                 for dy in (-.18,.18) for z in (-.44,-.06)],'gardenBronze',parent=f'crest-gardens-glass-{i}--1')
            if edge==0 and i%2==0:
                x=X+(u+v)/2
                z=arch_top((u+v)/2)-.55
                arch.box(f'crest-gardens-rib-light-{i}',x,canopy_y,z-.045,z+.16,.65,.17,'gardenWarm',
                         parent=f'crest-gardens-rib-{i}-0.0')
                lamps.append(dict(position=[x,canopy_y,z],range_m=13.,color='#ffcb89'))

    # A shallow retained water feature occupies the sheltered east garden.
    water_z=max(terrain(basin[0]+dx,basin[1]+dy) for dx in (-7.9,0,7.9) for dy in (-3.9,0,3.9))+.42
    arch.box('crest-gardens-basin-liner',*basin,water_z-.79,water_z-.045,8.0,4.0,'gardenStone')
    for i,(dx,dy,hx,hy) in enumerate([(-8,0,.24,4.25),(8,0,.24,4.25),(0,-4,8.2,.24),(0,4,8.2,.24)]):
        arch.box(f'crest-gardens-basin-kerb-{i}',basin[0]+dx,basin[1]+dy,water_z-.78,water_z+.28,hx,hy,'gardenStone')

    legacy=StreetIndex(world)
    conflicts={o['id']:r for o in arch.solids if (r:=legacy.overlaps(o,headroom=5.))}
    if conflicts:raise ValueError(f'Crest Gardens overlaps an established road: {conflicts}')
    return dict(center=CENTER,half=HALF,canopy_y=canopy_y,solids=arch.solids,trees=trees,lamps=lamps,
        fountain=dict(center=[*basin,water_z],half=[7.74,3.73]),
        fog=[dict(center=[*basin,water_z+.56],spread=[6.3,3.1],size=[6.2,1.5],
                  drift=[1.3,-.20],count=22,tint='#91bac0'),
             dict(center=[X-20.8,Y+11.8,terrain(X-20.8,Y+11.8)+.81],spread=[7.7,4.4],size=[8.9,2.0],
                  drift=[1.6,.5],count=13,tint='#d9b58e')])

if __name__=='__main__':
    target=PACK/'crest-gardens-31.json'
    payload=bake(make_world('vaderland-30'))
    target.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(len(payload['solids']),'physical shapes',len(payload['trees']),'trees',len(payload['lamps']),'lights')
