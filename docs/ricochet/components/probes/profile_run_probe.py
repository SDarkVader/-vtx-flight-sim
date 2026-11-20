"""Free acceleration run of RC-01 Concept A with the rc01-real-components profile (offline, isolated, nothing live).

Same basin and spawn as free_run_probe.py (west edge of the isolated harbour, water 7.0 m over a 2.0 m bed,
heading +x, still water). Full throttle, flight controls centred, ski collective incidence held at the value
given. Nothing is clamped or held: the craft is free in all six axes. Logs speed, height, trim, roll, yaw,
hull immersion, each ski's regime / wetted length / normal force / hinge moment against its actuator rating,
the surface actuator loads and the capsize flag every 0.25 s.
Usage: python profile_run_probe.py <worktree> <out.json> <ski_incidence_deg> [throttle] [seconds] [overrides_json]
"""
import json
import math
import sys
import time

from scipy.spatial.transform import Rotation

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402

SKI = float(sys.argv[3])
THR = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
SECS = float(sys.argv[5]) if len(sys.argv) > 5 else 40.0
OVR = json.loads(sys.argv[6]) if len(sys.argv) > 6 else None
world = HarbourFleet(harbour_world()).world
WCFG = WaterEnvironmentConfig.from_dict(dict(water_level_m=world.harbour['waterLevelM'], wave_mode='still',
                                             wind_speed_mps=0.0, current_speed_mps=0.0, wake_enabled=True,
                                             whirlpools_enabled=False))
c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-01', water_config=WCFG,
                  profile='rc01-real-components-v1', profile_overrides=OVR)
m, d = c.model, c.data
af = c.bids['airframe']
c.spawn(-180.0, 0.0, 7.0)
c.set_command(dict(throttle=THR, ski_incidence_deg=SKI))
env_ski = c.profile['_ski_env']
rows = []
t0 = time.time()
n_log = int(0.25 / c.DT)
peak = {'ski_hinge_nm': 0.0, 'ski_normal_n': 0.0}
for i in range(int(SECS / c.DT)):
    c.step()
    for s, tel in c.last_ski_telemetry.items():
        peak['ski_hinge_nm'] = max(peak['ski_hinge_nm'], abs(float(tel.get('hinge_moment_nm', 0.0))))
        peak['ski_normal_n'] = max(peak['ski_normal_n'], abs(float(tel.get('normal_force_n', 0.0))))
    if i % n_log == 0:
        R = d.xmat[af].reshape(3, 3)
        eul = Rotation.from_matrix(R).as_euler('xyz', degrees=True)
        vb = R.T @ d.qvel[0:3]
        cl = c.last_hydro.component_loads if c.last_hydro is not None else {}
        row = dict(t=round(d.time, 2), x=round(float(d.qpos[0]), 1), u=round(float(vb[0]), 2), vy=round(float(vb[1]), 2),
                   z=round(float(d.qpos[2]), 3), pitch=round(eul[1], 2), roll=round(eul[0], 2), yaw=round(eul[2], 2),
                   vol_h=cl.get('main_hull', {}).get('submerged_volume_m3', 0),
                   vol_p=cl.get('sponson_port', {}).get('submerged_volume_m3', 0),
                   vol_s=cl.get('sponson_stbd', {}).get('submerged_volume_m3', 0),
                   thrust=[round(x) for x in c.last_thrust_per_fan_n],
                   ski={s: {k: tel.get(k) for k in ('regime', 'incidence_deg', 'wetted_length_m', 'normal_force_n', 'hinge_moment_nm',
                                                    'cv', 'fin_side_n', 'added_inertia_kg_m2')}
                        for s, tel in c.last_ski_telemetry.items()},
                   act_load={k: round(v, 1) for k, v in c._act_load_nm.items()},
                   flags=sorted(c.flags))
        rows.append(row)
        if i % (8 * n_log) == 0:
            print(json.dumps({k: row[k] for k in ('t', 'x', 'u', 'z', 'pitch', 'roll', 'yaw', 'vol_h', 'flags')}), flush=True)
        if abs(d.qpos[0]) > 190 or abs(d.qpos[1]) > 190 or c.capsized:
            print('stop', json.dumps(row), flush=True)
            break
json.dump(dict(method=__doc__, ski_incidence_deg=SKI, throttle=THR, overrides=OVR, ski_actuator_envelope=env_ski,
               peak=peak, above_rated_s=c._act_above_rated_s, rows=rows, wall_s=round(time.time() - t0, 1)),
          open(sys.argv[2], 'w'), indent=1, default=str)
print('peak', peak, 'above_rated_s', c._act_above_rated_s, 'wall', round(time.time() - t0, 1))
