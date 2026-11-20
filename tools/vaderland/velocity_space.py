"""Survey road-to-air transitions and the volume available above the existing race surface."""
import argparse
import json
from pathlib import Path

import numpy as np

from airport_pass import probe
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


def measure(world):
    road = next(road for road in world.vaderland['routes'] if road['name'] == world.vaderland['speedway']['road'])
    points = np.asarray(road['points'])
    stations = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    aircraft = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    aircraft.spawn(-3885, 0, 0)

    def point(station):
        return np.array([np.interp(station, stations, points[:, i]) for i in range(2)])

    climbs = []
    for station in [500, 950, 1250, 1800, 3100, 4850, 5300, 6000, 7950]:
        centre = point(station)
        along = point(station + 5) - centre
        along /= np.linalg.norm(along)
        across = np.array([-along[1], along[0]])
        for rise in [.22, .42, .75]:
            direction = np.r_[along, rise]
            direction /= np.linalg.norm(direction)
            length = 600 * np.hypot(1, rise)
            hits = []
            for offset in np.arange(-9, 10, 1.5):
                xy = centre + offset * across
                p = [*xy, world.terrain_z(*xy) + 1.8]
                ray = probe(aircraft, p, direction.tolist())
                if 0 <= ray['distance_m'] < length:
                    hits.append(dict(offset_m=offset, distance_m=ray['distance_m'], feature=ray['geom']))
            climbs.append(dict(station_m=station, start_xy=centre.tolist(), horizontal_m=600,
                               gain_m=round(600*rise, 1), sampled_width_m=18, rays=13, obstructions=hits))

    # A 100 m overhead reserve on the public carriageway can take experimental course design later.
    # Sample the native colliders under every strip, including the approach and the rollout.
    reserves = []
    for start in [1400, 3200, 4950, 5350, 7750]:
        grades = []
        hits = []
        count = 0
        for s in np.arange(start, start + 441, 5):
            mid = point(s)
            fwd = point(s+1) - mid
            fwd /= np.linalg.norm(fwd)
            left = np.array([-fwd[1], fwd[0]])
            for off in np.arange(-9, 10, 3):
                xy = mid + off * left
                z = world.terrain_z(*xy)
                ray = probe(aircraft, [*xy, z+.15], [0, 0, 1])
                count += 1
                if 0 <= ray['distance_m'] < 100:
                    hits.append(dict(station_m=int(s), cross_m=int(off), geom=ray['geom'], height_m=round(ray['distance_m'], 3)))
                grades.append(abs(world.terrain_z(*(xy+fwd)) - z))
        reserves.append(dict(start_station_m=start, end_station_m=start+440, midpoint_xy=point(start+220).tolist(),
                             length_m=440, width_m=18, overhead_m=100, vertical_rays=count,
                             maximum_sampled_longitudinal_grade=max(grades), obstructions=hits))
    return dict(world=world.environment_key, climbs=climbs, overhead_reserves=reserves)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--world', default='vaderland-15')
    args = p.parse_args()
    result = measure(make_world(args.world))
    args.output.write_text(json.dumps(result, indent=2))
    print(sum(not r['obstructions'] for r in result['climbs']), 'clear climb fans')
    print([(r['start_station_m'], len(r['obstructions'])) for r in result['overhead_reserves']])
