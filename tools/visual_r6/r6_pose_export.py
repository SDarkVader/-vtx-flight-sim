"""Export R6 body poses (relative to the airframe) from the physics model for a set of duct tilts.

usage: python r6_pose_export.py <out.json> [tilt_deg]
Kinematic only: sets nacelle joint angles, runs mj_forward, never steps or writes anything else.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r6_unified as u  # noqa: E402
import mujoco as mj  # noqa: E402
import numpy as np  # noqa: E402

out = sys.argv[1]
tilt = math.radians(float(sys.argv[2]) if len(sys.argv) > 2 else 20.0)
ac = u.build_aircraft()
m, d = ac.model, ac.data
root = mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, 'airframe')


def poses():
    mj.mj_forward(m, d)
    ra, pa = d.xmat[root].reshape(3, 3), d.xpos[root]
    qc = np.array(d.xquat[root]) * [1, -1, -1, -1]
    res = {}
    for name in u.BODY_CONTAINERS:
        b = mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, name)
        q = np.zeros(4)
        mj.mju_mulQuat(q, qc, d.xquat[b])
        res[name] = dict(pos=(ra.T @ (d.xpos[b] - pa)).tolist(), quat_wxyz=q.tolist())
    return res


def set_tilt(x, y):
    for i in range(1, 5):
        d.qpos[ac.qadr[f'nacelle{i}_x']] = x
        d.qpos[ac.qadr[f'nacelle{i}_y']] = y


def set_joints(values):
    for name, v in values.items():
        d.qpos[ac.qadr[name]] = v


result = {'rest': poses()}
for label, (x, y) in {'tilt_x': (tilt, 0.0), 'tilt_y': (0.0, tilt),
                      'tilt_diag': (tilt / math.sqrt(2), tilt / math.sqrt(2)),
                      'tilt_neg_diag': (-tilt / math.sqrt(2), -tilt / math.sqrt(2))}.items():
    set_tilt(x, y)
    result[label] = poses()
set_tilt(0.0, 0.0)
# Every other articulation at its extremes (joint ranges from the physics model).
spin = {f'{k}{i}_spin': math.radians(37.0) for k in ('rotor', 'shaft') for i in range(1, 5)}
gear_full = {f'gear{i}_stroke': 0.25 for i in range(1, 7)}
cabin = {'cabin_x': math.radians(15.0), 'cabin_y': -math.radians(15.0), 'cabin_z': math.radians(90.0)}
for label, values in {'spin_37': spin, 'gear_full_stroke': gear_full, 'cabin_extreme': cabin}.items():
    set_joints(values)
    result[label] = poses()
    set_joints({k: 0.0 for k in values})
set_joints({f'shaft{i}_spin': math.pi for i in range(1, 5)})
result['shaft_half_turn'] = poses()
set_joints({f'shaft{i}_spin': 0.0 for i in range(1, 5)})
set_tilt(tilt / math.sqrt(2), -tilt / math.sqrt(2))
set_joints({**spin, **gear_full, **cabin})
result['combined_extreme'] = poses()
set_joints({k: 0.0 for k in {**spin, **gear_full, **cabin}})
set_tilt(0.0, 0.0)
result['meta'] = dict(tilt_deg=math.degrees(tilt), model_xml_sha256=__import__('hashlib').sha256(ac.xml.encode()).hexdigest())
json.dump(result, open(out, 'w'), indent=1)
print('poses', list(result))
