"""Check Parallax's building joints, approach volume and baseline aircraft passage offline."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import mujoco as mj
import numpy as np
from scipy.optimize import linprog

from airport_pass import probe
from vtx.phantom.plant import DT, PhantomAircraft
from vtx.world import make_world

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phantom'))
import a10c_airbrake_test as cruise


def flight(world, axis, direction, offset):
    with patch.object(cruise, 'FlatWorld', return_value=world):
        plane = cruise.build('off', 'cruise')
    model, data = plane.model, plane.data
    data.qpos[:3] = axis + [-direction * 160., offset, 0.]
    if direction < 0:
        quat = np.zeros(4)
        mj.mju_mulQuat(quat, np.array([0., 0., 0., 1.]), data.qpos[3:7].copy())
        data.qpos[3:7] = quat
        data.qvel[:2] *= -1
    mj.mj_forward(model, data)

    start = data.time
    frames, contacts = [], set()
    occupied_half_width, occupied_half_height = 0., 0.
    parts = np.flatnonzero((model.geom_contype == 2) & (model.geom_bodyid > 0))
    for i in range(round(4.3 / DT)):
        plane.step()
        for contact in data.contact:
            ids = [model.geom(int(j)).name for j in contact.geom]
            contacts.update(name for name in ids if name.startswith('parallax-'))
        if i % 4 == 0:
            pos = data.qpos[:3]
            frames.append(dict(time_s=float(data.time - start), position=pos.tolist(),
                               quaternion_wxyz=data.qpos[3:7].tolist()))
            if abs(pos[0] - axis[0]) < 17.:
                rotations = data.geom_xmat[parts].reshape(-1, 3, 3)
                centers = data.geom_xpos[parts] + np.einsum('ijk,ik->ij', rotations, model.geom_aabb[parts, :3])
                extents = np.einsum('ijk,ik->ij', abs(rotations), model.geom_aabb[parts, 3:])
                occupied = (abs(centers[:, 1:] - axis[1:]) + extents[:, 1:]).max(axis=0)
                occupied_half_width = max(occupied_half_width, float(occupied[0]))
                occupied_half_height = max(occupied_half_height, float(occupied[1]))
        if plane.crashed or (data.qpos[0] - axis[0]) * direction >= 160.:
            break
    return dict(direction=direction, offset_m=offset, config=plane.P.config_sha256,
                crossed=bool((data.qpos[0] - axis[0]) * direction >= 160.),
                crashed=bool(plane.crashed), feature_contacts=sorted(contacts), frames=frames,
                occupied_half_width_m=occupied_half_width, occupied_half_height_m=occupied_half_height,
                collisions=[e for e in plane.events if e.get('event') == 'collision'])


def planes(obj):
    center = np.asarray(obj['center'])
    if obj['kind'] == 'mesh':
        p = np.asarray(obj['planes']).copy()
        p[:, 3] -= p[:, :3] @ center
        return p
    normals = np.vstack((np.eye(3), -np.eye(3)))
    return np.c_[normals, -normals @ center - np.tile(obj['half'], 2)]


def review(directory):
    directory.mkdir(parents=True, exist_ok=True)
    world = make_world('vaderland-19')
    landmark = world.vaderland['parallax']
    axis = np.array([*landmark['point'][:2], landmark['passage_height_m']])
    shapes = {o['id']: o for o in world.obstacles}
    added = [o for o in world.obstacles if o['id'].startswith('parallax-')]
    detached = []
    for o in added:
        parent = shapes[o['parent']]
        hull = np.vstack((planes(o), planes(parent)))
        joint = linprog(np.zeros(3), A_ub=hull[:, :3], b_ub=-hull[:, 3],
                        bounds=[(None, None)] * 3, method='highs')
        if not joint.success:
            detached.append(o['id'])

    # Certify a continuous rectangular envelope, in addition to sampling the native collider.
    # For non-mesh scenery the actual solid is contained by the bounds used here.
    half = np.array([140., 17., 11.])
    center = axis + [-20., 0, 0]
    limits = list(zip(center - half, center + half))
    overlaps = []
    for o in world.obstacles:
        bbox = np.asarray(o['half'])
        if np.any(abs(np.asarray(o['center']) - center) > half + bbox):
            continue
        hull = planes(o)
        if linprog(np.zeros(3), A_ub=hull[:, :3], b_ub=-hull[:, 3], bounds=limits, method='highs').success:
            overlaps.append(o['id'])
    # The ground is a triangle interpolation of this lattice. Include the bounding cells.
    grid = np.linspace(-world.half, world.half, world.n)
    i = np.searchsorted(grid, [limits[0][0], limits[0][1]]) + [-1, 1]
    j = np.searchsorted(grid, [limits[1][0], limits[1][1]]) + [-1, 1]
    max_terrain = float(np.max(world.heights[j[0]:j[1], i[0]:i[1]]))

    plane = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    plane.spawn(-3885, 0, 0)
    rays = []
    for sign in (-1, 1):
        for y in (-31.4, -28.7, -26.2, -22.7, -16.8, -8.6, .3, 8.6, 16.8, 22.7, 26.2, 28.7, 31.4):
            for z in (-43.3, -27.7, -10.8, .4, 10.8, 28.7, 43.5, 53.1):
                start = axis + [-sign * 160., y, z]
                r = probe(plane, start.tolist(), [sign, 0, 0])
                rays.append(dict(**r, range_m=320., label='Parallax direction and clearance'))
    for y in (-31.1, -27.1, -.4, 27.1, 31.1):
        for x in (-6.3, .7, 5.1):
            r = probe(plane, (axis + [x, y, 90.]).tolist(), [0, 0, -1])
            rays.append(dict(**r, range_m=190., label='Parallax roof silhouette'))
    (directory / 'architecture-rays.json').write_text(json.dumps(rays), encoding='utf-8')

    passes = [flight(world, axis, direction, lateral) for direction, lateral in ((1, 0.), (-1, 0.), (1, 27.))]
    (directory / 'parallax-flight.json').write_text(json.dumps(passes), encoding='utf-8')
    summary = dict(axis_m=axis.tolist(), certified_box_m=(2*half).tolist(),
                   certified_bounds_m=limits, terrain_upper_bound_m=max_terrain,
                   added_solids=len(added), structural_joints_failed=detached, overlap=overlaps, native_rays=len(rays),
                   flights=[{k: v for k, v in r.items() if k != 'frames'} for r in passes])
    (directory / 'parallax-clearance.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if (detached or overlaps or max_terrain >= limits[2][0]
            or not all(r['crossed'] and not r['crashed'] and not r['feature_contacts'] for r in passes[:2])
            or not passes[2]['feature_contacts']):
        raise SystemExit('Parallax clearance or contact check failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    review(parser.parse_args().directory)
