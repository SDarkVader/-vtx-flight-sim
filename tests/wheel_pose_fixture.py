"""Generate isolated MuJoCo ground truth for the browser wheel-fit test."""
import json
import math
import mujoco as mj
import numpy as np
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld

PODS = ('FL', 'FR', 'RL', 'RR')
cases = []
for variant in ('phantom-a10b', 'phantom-a10c'):
    for tilted in (False, True):
        aircraft = PhantomAircraft(TestWorld(), variant, start_configuration='road')
        aircraft.spawn(0, 0, 0)
        if tilted:
            aircraft.data.qpos[:3] = [23, -12, 6]
            root_q = np.array([.94, .1, -.13, .27]); root_q /= np.linalg.norm(root_q)
            aircraft.data.qpos[3:7] = root_q
            for i, pod in enumerate(PODS):
                aircraft.set_q(f'pod_{pod}', (1 if pod.endswith('L') else -1) * (math.pi / 2 - .12 * i))
                aircraft.set_q(f'pod_{pod}_susp', -.035 + .015 * i)
                aircraft.set_q(f'pod_{pod}_wheel', .3 * (i + 1))
                if f'pod_{pod}_steer' in aircraft.jid:
                    aircraft.set_q(f'pod_{pod}_steer', .17 if pod == 'FL' else -.21)
        mj.mj_forward(aircraft.model, aircraft.data)
        snapshot = aircraft.physical_snapshot()
        expected = {}
        for pod in PODS:
            body_id = aircraft.model.body(f'pod_{pod}_wheel').id
            expected[pod] = dict(position=aircraft.data.xpos[body_id].tolist(), quaternion_wxyz=aircraft.data.xquat[body_id].tolist())
        cases.append(dict(variant=variant, tilted=tilted, truth=dict(t_s=snapshot['t_s'], variant=snapshot['variant'], config_sha256=snapshot['config_sha256'], body_poses=snapshot['body_poses'], phantom=snapshot['phantom']), expected=expected))
print(json.dumps(cases))
