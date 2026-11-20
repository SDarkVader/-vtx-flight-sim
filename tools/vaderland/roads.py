"""Measure the finished road profiles, connections and clear width in world coordinates."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from vtx.world import make_world


def sections(road):
    points = np.array(road['points'])
    pieces = []
    for a, b in zip(points, points[1:]):
        length = np.linalg.norm(b-a)
        if length > .001:
            pieces.extend(np.linspace(a, b, int(np.ceil(length/6)), endpoint=False))
    return np.array([*pieces, points[-1]])


def measure(world):
    roads = world.vaderland['routes']
    points = [sections(road) for road in roads]
    trees = [cKDTree(p) for p in points]
    graph = [set() for _ in roads]
    report = []
    for i, (road, xy) in enumerate(zip(roads, points)):
        distances = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
        z = np.array([world.terrain_z(x,y) for x,y in xy])
        road_z = np.full_like(z, road['deck_z_m']) if 'deck_z_m' in road else z
        if 'deck_z_m' in road:
            clearance = float(np.max(road_z-2.8-z))
        else:
            clearance = None
        grade = np.abs(np.diff(road_z)/np.diff(distances))
        # Curvature at 30 metre intervals is stable on both straight city grids
        # and tightly surveyed circuit arcs. Three points define the actual radius.
        stations = np.arange(0, distances[-1], 30.)
        c = np.array([np.interp(stations, distances, xy[:,j]) for j in (0,1)]).T
        ab, bc = np.diff(c,axis=0)[:-1], np.diff(c,axis=0)[1:]
        twice_area = abs(ab[:,0]*bc[:,1]-ab[:,1]*bc[:,0])
        denom = 2*np.maximum(twice_area,1e-12)
        radius = np.linalg.norm(ab,axis=1)*np.linalg.norm(bc,axis=1)*np.linalg.norm(ab+bc,axis=1)/denom
        for j in range(i):
            d, k = trees[j].query(xy)
            threshold = (road['width_m']+roads[j]['width_m'])/2
            near = np.where(d<threshold)[0]
            if len(near):
                other = roads[j]
                za = road_z[near]
                if 'deck_z_m' in other:
                    zb = np.full_like(za, other['deck_z_m'])
                else:
                    zb = [world.terrain_z(*points[j][n]) for n in k[near]]
                if np.any(np.abs(za-zb)<.8):
                    graph[i].add(j)
                    graph[j].add(i)
        ix = int(np.argmax(grade))
        report.append(dict(name=road['name'],width_m=road['width_m'],length_m=round(distances[-1],1),
            grade_p95_pct=round(float(np.percentile(grade,95))*100,2),max_grade_pct=round(float(grade[ix])*100,2),
            max_grade_at=xy[ix].round(1).tolist(),min_radius_m=round(float(min(radius)),1) if len(radius) and min(radius)<10000 else None,
            underdeck_clearance_max_m=None if clearance is None else round(clearance,1)))
    seen = set()
    groups = []
    for i in range(len(roads)):
        if i in seen:continue
        group = set()
        pending = [i]
        while pending:
            k = pending.pop()
            if k not in group:
                group.add(k)
                pending.extend(graph[k]-group)
        seen.update(group)
        groups.append([roads[k]['name'] for k in sorted(group)])
    for i, row in enumerate(report):
        row['connections']=[roads[j]['name'] for j in sorted(graph[i])]
    return dict(world=world.environment_key,total_length_km=round(sum(r['length_m'] for r in report)/1000,2),
                components=groups,roads=report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--world',required=True)
    args=p.parse_args()
    result=measure(make_world(args.world))
    (args.directory/'roads.json').write_text(json.dumps(result,indent=2))
    print('Components',list(map(len,result['components'])),'route km',result['total_length_km'])
    for r in sorted(result['roads'],key=lambda x:-x['max_grade_pct'])[:12]:
        print(r['name'],r['grade_p95_pct'],r['max_grade_pct'],r['max_grade_at'])
