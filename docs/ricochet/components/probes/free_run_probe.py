"""Free acceleration run of RC-01 Concept A in the real plant (offline, isolated world, nothing live).

Spawned at the west edge of the isolated harbour basin (water 7.0 m over a 2.0 m bed), heading +x,
full throttle, controls centred, nothing held. Logs speed, height, trim, roll, yaw drift, ski immersion
and loads, thrust and fan rpm every 0.25 s for up to 40 s or until it leaves the basin.
Usage: python free_run_probe.py <worktree> <out.json> [load_case] [throttle] [wake 0/1]
"""
import json
import math
import sys
import time

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402

LC = sys.argv[3] if len(sys.argv) > 3 else 'LC-01'
THR = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
WAKE = (sys.argv[5] == '1') if len(sys.argv) > 5 else True
world = HarbourFleet(harbour_world()).world
WCFG = WaterEnvironmentConfig.from_dict(dict(water_level_m=world.harbour['waterLevelM'], wave_mode='still',
                                             wind_speed_mps=0.0, current_speed_mps=0.0, wake_enabled=WAKE,
                                             whirlpools_enabled=False))
c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case=LC, water_config=WCFG)
m, d = c.model, c.data
af, sp, ss = c.bids['airframe'], c.bids['sponson_port'], c.bids['sponson_stbd']
c.spawn(-180.0, 0.0, 7.0)
c.set_command(dict(throttle=THR))
rows = []
t0 = time.time()
n_log = int(0.25 / c.DT)
for i in range(int(40.0 / c.DT)):
    c.step()
    if i % n_log == 0:
        R = d.xmat[af].reshape(3, 3)
        eul = Rotation.from_matrix(R).as_euler('xyz', degrees=True)
        v_w = d.cvel[af]  # not used: use qvel of free joint
        vel = d.qvel[0:3]
        u = float((R.T @ vel)[0])
        cl = c.last_hydro.component_loads if c.last_hydro is not None else {}
        row = dict(t=round(d.time, 2), x=round(float(d.qpos[0]), 1), u=round(u, 2), vy=round(float((R.T @ vel)[1]), 2),
                   z=round(float(d.qpos[2]), 3), pitch=round(eul[1], 2), roll=round(eul[0], 2), yaw=round(eul[2], 2),
                   vol_h=cl.get('main_hull', {}).get('submerged_volume_m3', 0), vol_p=cl.get('sponson_port', {}).get('submerged_volume_m3', 0),
                   vol_s=cl.get('sponson_stbd', {}).get('submerged_volume_m3', 0),
                   Fz_p=round(float(d.xfrc_applied[sp, 2])), Fz_s=round(float(d.xfrc_applied[ss, 2])),
                   thrust=[round(x) for x in c.last_thrust_per_fan_n], rpm=[round(x) for x in c.last_fan_rpm],
                   munk_yaw=round(float(c.last_munk_moment_nm[2])), crashed=bool(c.crashed))
        rows.append(row)
        if i % (4 * n_log) == 0:
            print(row, flush=True)
        if abs(d.qpos[0]) > 190 or abs(d.qpos[1]) > 190 or abs(eul[0]) > 120:
            print('stop', row, flush=True)
            break
json.dump(dict(method=__doc__, load_case=LC, throttle=THR, wake=WAKE, rows=rows, wall_s=round(time.time() - t0, 1)),
          open(sys.argv[2], 'w'), indent=1)
