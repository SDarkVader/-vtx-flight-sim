"""Drive both canyon abutments with a stock A10-C using only ordinary pilot inputs."""
import argparse
import json
import math
from pathlib import Path
import sys

import mujoco as mj
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.phantom.plant import DT, PhantomAircraft
from vtx.world import make_world


def route(world):
    roads = {r['name']: r for r in world.vaderland['routes']}
    return sampled_route([(roads['Canyon climb'],False),(roads['Falls bridge'],True),(roads['Scree pass'],False)])


def sampled_route(segments):
    points = []
    widths = []
    for road,reverse in segments:
        xy = np.asarray(road['points'])
        if reverse:
            xy = xy[::-1]
        for a, b in zip(xy, xy[1:]):
            count = max(1, math.ceil(np.linalg.norm(b - a) / 2))
            points.extend(np.linspace(a, b, count, endpoint=False))
            widths.extend([road['width_m']] * count)
    return np.array([*points, xy[-1]]), np.array([*widths, widths[-1]])


def run(world, origin_m, finish_m, target_speed, path=None, record_m=None, pace=None, closed=False,
        record_step=None, variant='phantom-a10c'):
    xy, widths = route(world) if path is None else path
    distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    direction = 1 if finish_m > origin_m else -1
    sample = lambda s: np.array([np.interp(s, distance, xy[:, k]) for k in (0, 1)])
    index = cKDTree(xy)
    plane = PhantomAircraft(world, variant, start_configuration='road')
    p = sample(origin_m)
    tangent = sample(origin_m + 2 * direction) - p
    tangent /= np.linalg.norm(tangent)
    normal = np.array([-tangent[1], tangent[0]])
    z = world.terrain_z(*p)
    slope = (world.terrain_z(*(p + tangent)) - world.terrain_z(*(p - tangent))) / 2
    cant = (world.terrain_z(*(p + normal)) - world.terrain_z(*(p - normal))) / 2
    heading = math.atan2(tangent[1], tangent[0])
    plane.spawn(*p, z)
    plane.data.qpos[3:7] = Rotation.from_euler('ZYX', [heading, -math.atan(slope), math.atan(cant)]).as_quat(scalar_first=True)
    mj.mj_forward(plane.model, plane.data)

    result = []
    bridge_contacts = set()
    contacted_decks=set()
    pose=None
    air_time = longest_air = 0.
    step_count = round(.1 / DT)
    wheelbase = abs(plane.L.bodies['pod_FL_wheel'].anchor[0] - plane.L.bodies['pod_RL_wheel'].anchor[0])
    max_steer = math.radians(plane.P['effectors.steering.max_deg'])
    lateral_limit = plane.P['effectors.steering.lat_accel_max_g'] * 9.80665
    status = 'timeout'
    chain=origin_m
    for k in range(int((abs(finish_m - origin_m) / max(4, target_speed * .25) + 30) * 10)):
        p = plane.data.qpos[:2].copy()
        offset, j = index.query(p)
        if closed:
            nearby=index.query_ball_point(p,max(float(offset)+3.,7.))
            local=[k for k in nearby if abs(distance[k]-chain)<32.]
            if local:
                j=min(local,key=lambda q:np.linalg.norm(xy[q]-p));offset=float(np.linalg.norm(xy[j]-p))
        chain = distance[j]
        speed = float(np.linalg.norm(plane.data.qvel[:2]))
        forward = plane.R()[:2, 0].copy()
        forward /= max(1e-12, np.linalg.norm(forward))
        aim = sample(chain + direction * np.clip(4. + speed * .85, 8., 22.)) - p
        turn = 2 * (forward[0] * aim[1] - forward[1] * aim[0]) / max(4., aim @ aim)
        steering_limit = min(max_steer, math.atan(wheelbase * lateral_limit / max(speed * speed, 1.)))
        yaw = np.clip(-math.atan(wheelbase * turn) / steering_limit, -1., 1.)
        reference=target_speed if pace is None else min(target_speed,pace(chain))
        effort = np.clip(.125 + .28 * (reference - speed), -1., 1.)
        plane.set_command(dict(yaw=float(yaw), wheel_drive=[max(0., effort)] * 4, brake=[max(0., -effort)] * 4))
        for _ in range(step_count):
            plane.step()
            if record_step is not None:
                record_step(plane)
            support = plane.support_count()
            air_time = 0. if support else air_time + DT
            longest_air = max(longest_air, air_time)
            if 1800 < chain < 2650:
                for c in plane.data.contact:
                    for gid in c.geom:
                        if plane.model.geom_bodyid[gid] == 0:
                            name = plane.model.geom(int(gid)).name
                            if name and name.startswith('Falls bridge-deck'):
                                bridge_contacts.add(name)
        if k % 5 == 0:
            result.append(dict(t_s=round(plane.data.time, 3), chain_m=round(chain, 2), centre_offset_m=round(offset, 2),
                lane_half_m=widths[j] / 2, xyz_m=plane.data.qpos[:3].round(4).tolist(),
                speed_m_s=round(speed, 3), tyre_contacts=support))
        if path is not None:
            for contact in plane.data.contact:
                for gid in contact.geom:
                    if plane.model.geom_bodyid[gid]==0:
                        name=plane.model.geom(int(gid)).name
                        if name and name.startswith(('deck-airport','stand-')):contacted_decks.add(name)
        if pose is None and record_m is not None and (chain-record_m)*direction>=0:
            pose=plane.physical_snapshot()
        if plane.crashed:
            status = 'crash'; break
        if (finish_m - chain) * direction <= 0:
            status = 'complete'; break
        if offset > widths[j] / 2 + 2:
            status = 'left roadway'; break
        if k > 150 and len(result) > 20 and abs(chain-result[-21]['chain_m']) < 2:
            status = 'stalled'; break
    receipt=dict(world=world.environment_key, variant=plane.variant, config=plane.P.config_sha256,
                requested_speed_m_s=target_speed, origin_m=origin_m, finish_m=finish_m,
                status=status, reached_m=round(chain, 2), elapsed_s=round(plane.data.time, 3),
                bridge_deck_contacts=len(bridge_contacts), longest_unsupported_s=round(longest_air, 3),
                max_centre_offset_m=max(s['centre_offset_m'] for s in result), samples=result,
                collisions=[e for e in plane.events if e.get('event')=='collision'])
    if path is not None:receipt['contacted_decks']=sorted(contacted_decks)
    if pose is not None:receipt['pose']=pose
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--world', required=True)
    parser.add_argument('--from-m', type=float, required=True)
    parser.add_argument('--to-m', type=float, required=True)
    parser.add_argument('--speed', type=float, required=True)
    args = parser.parse_args()
    trace = run(make_world(args.world), args.from_m, args.to_m, args.speed)
    args.output.write_text(json.dumps(trace, indent=2), encoding='utf-8')
    print({key:value for key,value in trace.items() if key not in ('samples','collisions')})
