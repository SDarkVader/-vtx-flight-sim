"""Diagnostic: why do the skis get driven past their -3 deg stop during the bench sweep's 'ski differential +4' hold?

Same isolated basin, spawn and profile as export_rig.py (craft at rest, still water, throttle 0, nothing live).
Commands ski collective 10 deg, then differential +4 deg, and logs every 10 ms: both ski joints, actuator target /
force / rated & peak, each ski's hydro telemetry, and the airframe heave / roll / pitch.
Usage: python ski_collapse_probe.py <worktree> <out.json>
"""
import json
import math
import sys

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402

world = HarbourFleet(harbour_world()).world
WCFG = WaterEnvironmentConfig.from_dict(dict(water_level_m=world.harbour['waterLevelM'], wave_mode='still',
                                             wind_speed_mps=0.0, current_speed_mps=0.0, wake_enabled=False,
                                             whirlpools_enabled=False))
c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-01', water_config=WCFG,
                  profile='rc01-real-components-v1')
m, d = c.model, c.data
c.spawn(-180.0, 0.0, 7.0)
af = c.bids['airframe']
env = c.profile['_ski_env']
rows = []
BASE = dict(throttle=0.0, differential_thrust=0.0, rudder_deg=0.0, elevator_deg=0.0, aileron_deg=0.0,
            reverse_bucket=0.0, ski_incidence_deg=0.0, ski_differential_deg=0.0)
if len(sys.argv) > 3 and sys.argv[3] == 'full':  # replay export_rig.py's bench sequence up to the ski differential holds
    plan = [(0.6, {}), (1.0, dict(aileron_deg=25.0)), (1.2, dict(aileron_deg=-25.0)), (0.8, {}),
            (1.0, dict(elevator_deg=20.0)), (1.2, dict(elevator_deg=-20.0)), (0.8, {}),
            (1.2, dict(rudder_deg=30.0)), (1.5, dict(rudder_deg=-30.0)), (1.0, {}),
            (1.8, dict(reverse_bucket=1.0)), (1.8, {}), (1.4, dict(ski_incidence_deg=10.0)),
            (1.2, dict(ski_incidence_deg=10.0, ski_differential_deg=4.0)), (1.4, dict(ski_incidence_deg=10.0, ski_differential_deg=-4.0))]
    LOG_FROM = 14.0
else:
    plan = [(1.5, dict(ski_incidence_deg=0.0)), (1.6, dict(ski_incidence_deg=10.0)),
            (2.5, dict(ski_incidence_deg=10.0, ski_differential_deg=4.0)), (1.5, dict(ski_incidence_deg=10.0))]
    LOG_FROM = 0.0
print('water level', world.harbour['waterLevelM'])
t = 0.0
for dur, cmd in plan:
    cmd = dict(BASE, **cmd)
    c.set_command(dict(cmd))
    for i in range(int(round(dur / c.DT))):
        c.step()
        t += c.DT
        if i % 4 == 0 and t >= LOG_FROM:
            R = d.xmat[af].reshape(3, 3)
            eul = Rotation.from_matrix(R).as_euler('xyz', degrees=True)
            row = dict(t=round(t, 3), cmd=cmd, z=round(float(d.xpos[af][2]), 4), roll=round(eul[0], 3), pitch=round(eul[1], 3),
                       vz=round(float(d.qvel[2]), 4))
            for side in ('port', 'stbd'):
                j = c.jids[f'ski_{side}_incidence']
                a = c.aids[f'ski_{side}_actuator']
                row[side] = dict(
                    q=round(math.degrees(float(d.qpos[m.jnt_qposadr[j]])), 3),
                    target=round(math.degrees(float(d.ctrl[a])), 3),
                    act_force=round(float(d.actuator_force[a]), 1),
                    hydro_hinge=round(float(c._act_load_nm.get(f'ski_{side}_actuator', 0.0)), 1),
                    tel={k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.last_ski_telemetry.get(side, {}).items()
                         if not isinstance(v, (list, dict))},
                )
            rows.append(row)
json.dump(dict(method=__doc__, ski_env=env, ski_servo=c.profile['_ski_servo'], rows=rows), open(sys.argv[2], 'w'), indent=1,
          default=str)
for r in rows[::10]:
    print(r['t'], r['cmd'], 'z', r['z'], 'roll', r['roll'], 'pitch', r['pitch'],
          '| P q', r['port']['q'], 'tgt', r['port']['target'], 'F', r['port']['act_force'], 'hinge', r['port']['hydro_hinge'],
          r['port']['tel'].get('regime'), '| S q', r['stbd']['q'], 'F', r['stbd']['act_force'], 'hinge', r['stbd']['hydro_hinge'])
print('ski env', env, 'servo', c.profile['_ski_servo'])
