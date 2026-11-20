"""Audit Meridian flight gate volumes against the existing city and terrain."""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from vtx.vaderland import PACK
from vtx.world import MapPoint, make_world


def corridor(world, start, end, y, z, half_width, half_height):
    low=np.array([start,y-half_width,z-half_height])
    high=np.array([end,y+half_width,z+half_height])
    limits=list(zip(low,high))
    for shape in world.obstacles:
        center=np.array(shape['center'])
        half=np.array(shape['half'])
        if np.any(center+half<low) or np.any(center-half>high):
            continue
        if shape['kind']!='mesh':
            raise ValueError(f"Air corridor crosses {shape['id']}")
        planes=np.asarray(shape['planes'])
        b=planes[:,:3]@center-planes[:,3]
        if linprog([0.,0.,0.],A_ub=planes[:,:3],b_ub=b,bounds=limits,method='highs').success:
            raise ValueError(f"Air corridor crosses {shape['id']}")
    lattice=np.linspace(-world.half,world.half,world.n)
    i,j=(np.searchsorted(lattice,p)+[-1,1] for p in
         ((low[0],high[0]),(low[1],high[1])))
    if np.max(world.heights[j[0]:j[1],i[0]:i[1]])>=low[2]:
        raise ValueError('Air corridor crosses terrain')
    return [low.tolist(),high.tolist()]


def make_air(world):
    x,y=world.vaderland['parallax']['point'][:2]
    details=[
        ('Meridian High Line','Meridian Skyline',[-560.,-260.,x,420.,710.],
         383.,80.,42.,(-530.,1460.),70.),
        ('Parallax Thread','Parallax Exchange',[x-145.,x,x+85.],
         world.vaderland['parallax']['passage_height_m'],24.,14.,(-300.,1950.),28.),
    ]
    data=[]
    for name,zone,stations,z,width,height,spawn,lead in details:
        assert world.validate(MapPoint(x_m=spawn[0],y_m=spawn[1]),'departure').valid
        # Extra half-width and half-height are surveyed around every gate for
        # the aircraft envelope, not counted as extra valid timing aperture.
        bounds=corridor(world,stations[0]-lead,stations[-1]+30.,y,z,width/2+5.,height/2+4.)
        data.append(dict(name=name,zone=zone,spawn=list(spawn),length_m=stations[-1]-stations[0],
             clear_bounds=bounds,entry_lead_m=lead,
             gates=[dict(center=[i,y,z],normal=[1.,0.,0.],right=[0.,1.,0.],
                         up=[0.,0.,1.],width_m=width,height_m=height) for i in stations]))
    return data


if __name__=='__main__':
    data=make_air(make_world('vaderland-28'))
    (PACK/'meridian-air-29.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print([(x['name'],x['length_m'],x['clear_bounds']) for x in data])