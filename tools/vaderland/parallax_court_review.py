"""Measure the authored Parallax Court against the preserved streets and native geometry."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from airport_pass import probe
from parallax_review import planes
from streets import StreetIndex, footprint, segment_distance
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


def intersect(a, b):
    hull = np.vstack((planes(a), planes(b)))
    return linprog(np.zeros(3), A_ub=hull[:, :3], b_ub=-hull[:, 3],
                   bounds=[(None, None)]*3, method='highs').success


def audit(out):
    out.mkdir(parents=True, exist_ok=True)
    w = make_world('vaderland-20')
    court = w.vaderland['parallax_court']
    solids = {o['id']: o for o in w.obstacles}
    added = [o for o in w.obstacles if o['id'].startswith('court-')]
    detached = []
    for shape in added:
        parent = shape.get('parent')
        if parent:
            if not intersect(shape, solids[parent]):
                detached.append(shape['id'])
        else:
            floor = min(w.terrain_z(*xy) for xy in footprint(shape))
            if shape['center'][2]-shape['half'][2] > floor + .03:
                detached.append(shape['id'])
    columns = [o for o in added if o['id'].startswith('court-column-')]
    canopy = [o for o in added if o['id'].startswith('court-canopy-')]
    detached.extend(c['id'] for c in columns if not any(intersect(c, panel) for panel in canopy))

    # This route follows the alley from the avenue into the centre of the forecourt.
    walk = np.array([[14.8,2355.9],[45.0,2354.95],[58.7,2354.55],[60.8,2366.6],
                     [61.4,2375.0],[66.6,2379.1],[70.1,2379.52]])
    relevant = [o for o in w.obstacles if 0 < o['center'][0] < 125 and 2310 < o['center'][1] < 2440]
    blockers = []
    pedestrian_half_width = 1.05
    for a, b in zip(walk, walk[1:]):
        for o in relevant:
            bottom = o['center'][2]-o['half'][2]
            if bottom > max(w.terrain_z(*a),w.terrain_z(*b))+2.55:
                continue
            dist, _ = segment_distance(a,b,footprint(o))
            if dist < pedestrian_half_width:
                blockers.append(dict(id=o['id'], distance_m=float(dist), start=a.tolist(), end=b.tolist()))
    streets = StreetIndex(w)
    road_obstructions = {s['id']: r for s in added if (r := streets.overlaps(s))}

    plane = PhantomAircraft(w, 'phantom-a10c', start_configuration='road')
    plane.spawn(-3885,0,0)
    native = []
    door = np.asarray(court['door'])
    u,v = np.array(court['axis']),np.array(court['front'])
    def cast(xy,z,direction,length):
        native.append(dict(**probe(plane,[*xy,z],direction),range_m=length,label='Parallax Court surfaces'))
    for s in np.linspace(-20,20,21)+.21:
        for d in (1.7,4.8,7.2,9.74,12.7,18.5):
            xy = door+u*s+v*d
            cast(xy,47.3,[0,0,-1],18.5)
            cast(xy,w.terrain_z(*xy)+.22,[0,0,1],18.)
    for bed in court['beds']:
        x,y,z = bed['point']
        cast([x+.3,y+.1],z+2.0,[0,0,-1],3.3)

    result=dict(solids=len(added), floating=detached, road_infringements=road_obstructions,
                walking_line=walk.tolist(), walking_width_m=2*pedestrian_half_width,
                walking_obstructions=blockers, ray_count=len(native))
    (out/'court-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'architecture-rays.json').write_text(json.dumps(native),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if detached or road_obstructions or blockers:
        raise SystemExit('Parallax Court geometry audit failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path)
    audit(parser.parse_args().out)
