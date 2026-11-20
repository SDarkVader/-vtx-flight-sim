"""Survey the Lantern Islet time trial through real harbour water."""
import argparse
import json
import math

import numpy as np
from scipy.interpolate import CubicSpline

from vtx.harbour_water import HarbourWorld
from vtx.vaderland import PACK
from vtx.world import make_world


ANCHORS = [
    (3870., 550.), (3818., 541.), (3740., 550.), (3664., 597.),
    (3618., 665.), (3624., 726.), (3679., 772.), (3753., 791.),
    (3833., 780.), (3890., 758.), (3894., 713.), (3894., 654.),
    (3900., 600.), (3870., 550.),
]
GATE_REQUESTS = [(55.,32.), (158.,36.), (252.,38.), (335.,34.),
                 (434.,32.), (528.,31.), (604.,18.), (675.,23.)]
POST_RADIUS = .68


def surveyed_trial(source):
    water = HarbourWorld(source)
    level = water.harbour['waterLevelM']
    points = np.asarray([water.to_world(p) for p in ANCHORS])
    polygon_length = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    spline = CubicSpline(polygon_length, points, bc_type='periodic')
    points = spline(np.linspace(0, polygon_length[-1], math.ceil(polygon_length[-1]/1.3)+1))
    length = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    at = lambda s: np.array([np.interp(s % length[-1], length, p) for p in points.T])

    def tangent(s):
        delta = at(s+1.)-at(s-1.)
        return delta/np.linalg.norm(delta)

    structures = [o for o in water.structures if 330 < o['center'][0] < 1050 and -1450 < o['center'][1] < -920]
    existing = []
    for o in source.obstacles:
        x,y,z = o['center']
        a,b,c = o['half']
        if x+a>380 and x-a<850 and y+b>-1390 and y-b<-990 and z-c<level+2:
            existing.append(dict(center=o['center'],half_extents=o['half'],yaw_deg=0.,id=o['id']))
    structures.extend(existing)

    def inspect(samples, clearance):
        samples = np.asarray(samples)
        depths = level-water.terrain_z_array(samples[:,0], samples[:,1])
        if not np.all(water.mask(samples[:,0], samples[:,1])) or float(min(depths))<2.7:
            i=int(np.argmin(depths))
            raise ValueError(f'Water depth or shoreline {samples[i].tolist()} {min(depths):.2f} m')
        gap = math.inf
        ids = []
        for s in structures:
            d = samples - s['center'][:2]
            t = math.radians(s['yaw_deg'])
            d = d @ [[math.cos(t),-math.sin(t)],[math.sin(t),math.cos(t)]]
            edges = np.maximum(abs(d)-s['half_extents'][:2],0.)
            to = float(np.linalg.norm(edges,axis=1).min())
            gap=min(gap,to)
            if to<clearance:
                ids.append((s['id'],round(to,2)))
        if ids:
            raise ValueError(f'Existing marine obstructions: {ids}')
        return float(min(depths)),gap

    lane = []
    for s in np.arange(0.,length[-1],1.7):
        p=at(s)
        n=tangent(s)
        cross=np.array([-n[1],n[0]])
        lane.extend(p+cross*k for k in (-5.5,0.,5.5))
    depth,gap=inspect(lane,2.6)
    gates, solids = [], []
    for i, (station, width) in enumerate(GATE_REQUESTS):
        p=at(station)
        n=tangent(station)
        lateral=np.array([-n[1],n[0]])
        endcaps=[]
        for side in (-1,1):
            xy=p+side*(width/2+POST_RADIUS)*lateral
            inspect([xy+[u,v] for u,v in ((0.,0.),(-1.,0.),(1.,0.),(0.,1.),(0.,-1.))],1.65)
            base=water.terrain_z(*xy)-1.1
            top=level+(4.9 if i==0 else 3.42)
            key=f'sound-gate-{i+1}-{side}'
            col='#68e3ee' if side==1 else '#ffb05f'
            solids.append(dict(id=key,kind='cylinder',role='race-mark',
                center=[*xy.round(5),(base+top)/2],half=[POST_RADIUS,POST_RADIUS,(top-base)/2],
                color=col,landable=False))
            endcaps.append(key)
        inspect(np.linspace(p-lateral*width/2,p+lateral*width/2,24),1.6)
        gates.append(dict(center=[*p.round(6),level],normal=n.round(9).tolist(),
                          width_m=width,marks=endcaps,station_m=station))
    start=at(7.)
    heading=tangent(7.)
    cross=np.array([-heading[1],heading[0]])
    inspect([start+heading*u+cross*v for u in (-12.,0.,12.) for v in (-8.,0.,8.)],4.)
    d=np.gradient(points, axis=0)
    curvature=np.abs((d[:-1,0]*d[1:,1]-d[:-1,1]*d[1:,0])) / np.linalg.norm(d[:-1],axis=1)**3
    radius=float(1./np.max(curvature))
    return dict(id='lantern-islet-trial', name='Lantern Islet Trial', length_m=round(float(length[-1]),3),
        position=start.round(6).tolist(), heading_rad=math.atan2(heading[1],heading[0]),
        points=points[::3].round(5).tolist()+[points[-1].round(5).tolist()],
        gates=gates,solids=solids,median_width_m=float(np.median([g['width_m'] for g in gates])),
        min_turn_radius_m=round(radius,2),nominal_corridor_min_depth_m=round(depth,3),
        nominal_corridor_min_structure_gap_m=round(gap,3), working_start_m=7.)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(PACK/'lantern-islet-28.json'))
    args=parser.parse_args()
    trial=surveyed_trial(make_world('vaderland-27'))
    with open(args.output,'w',encoding='utf-8',newline='\n') as file:
        json.dump(trial,file,sort_keys=True,separators=(',',':'),allow_nan=False)
        file.write('\n')
    print(trial['length_m'],trial['min_turn_radius_m'],trial['nominal_corridor_min_depth_m'],
          trial['nominal_corridor_min_structure_gap_m'],[x['width_m'] for x in trial['gates']])