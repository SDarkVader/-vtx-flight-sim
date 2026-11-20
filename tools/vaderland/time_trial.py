"""Run a timed ground course with a controller against the stock simulator offline."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from drive_pass import make_world, run, sampled_route


def course_path(world, race):
    catalog = world.vaderland
    name = race['course']
    if name == 'Cathedral of Velocity':
        cathedral = catalog['cathedral']
        return np.asarray(cathedral['points']), np.asarray(cathedral['widths_m'])
    road_name = catalog['speedway']['road'] if name == 'Night Velocity' else name
    road = next(r for r in catalog['routes'] if r['name'] == road_name)
    return sampled_route([(road, False)])


def time_trial(world, course_name, speed):
    selected = next((e for e in world.vaderland['time_trials'] if e['course'] == course_name), None)
    if selected is None:
        raise ValueError(f'Unknown ground time trial: {course_name}')
    timing = next(c for c in world.timing.courses if c['name'] == course_name)
    xy, widths = course_path(world, selected)
    if not np.allclose(xy[0], xy[-1]):
        raise ValueError(f'{course_name} has no closed physical route')
    chain = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    def nearest(point):
        return chain[np.argmin(np.linalg.norm(xy-point, axis=1))]
    origin = nearest(selected['spawn'])
    gate = nearest(timing['gates'][0]['center'][:2])
    finish = gate + chain[-1] + 8.
    repeats = math.ceil(finish/chain[-1])
    path = (np.vstack([xy,*[xy[1:]]*(repeats-1)]),np.r_[widths,np.tile(widths[1:],repeats-1)])

    def sample(plant):
        world.timing.sample(plant.data.time, plant.data.qpos[:3])

    trace = run(world, origin, finish, speed, path=path, closed=True, record_step=sample)
    trace['course'] = course_name
    trace['timing'] = world.timing.runs[course_name]
    return trace


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--course', required=True)
    parser.add_argument('--speed', type=float, default=10., help='requested pace in m/s')
    args = parser.parse_args()
    if not math.isfinite(args.speed) or args.speed <= 0.:
        parser.error('pace must be positive and finite')
    result = time_trial(make_world('vaderland-27'), args.course, args.speed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result['course'],result['status'],result['timing'],result['max_centre_offset_m'])
    if not result['timing']['laps'] or result['collisions']:
        raise SystemExit(1)