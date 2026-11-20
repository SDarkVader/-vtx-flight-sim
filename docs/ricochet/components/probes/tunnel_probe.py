"""Wind-tunnel probe of the real Ricochet Concept A plant (offline, isolated world, nothing live).

The airframe free joint is re-pinned every 400 Hz step so the hull cannot move; airflow is a wind
vector set from airspeed V, angle of attack alpha and sideslip beta (body frame == world frame,
heading 0, level). Control surfaces and fan rotors stay free and are driven by the plant's own
servos/motors. Reports the plant's unclipped hinge moments (last_aero_detail['hinge_moments']).
"""
import json
import math
import sys
import time

import mujoco as mj
import numpy as np

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402

world = HarbourFleet(harbour_world()).world
DUR_S = 2.5
SURF = {
    'rudder': ('rudder_deg', 30.0, 'beta', (0.0, 8.0, -8.0)),
    'elevator': ('elevator_deg', 20.0, 'alpha', (0.0, 10.0, -5.0)),
    'aileron': ('aileron_deg', 25.0, 'alpha', (0.0, 10.0)),
}
rows = []
t0 = time.time()
for v in (20.0, 35.0, 50.0, 65.0):
    for thr in (0.0, 1.0):
        for surf, (chan, dmax, angle_kind, angles) in SURF.items():
            for ang in angles:
                for sign in (+1.0, -1.0):
                    c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a')
                    c.spawn(100.0, 100.0, 8.0)
                    bid = c.bids['airframe']
                    jid = int(c.model.body_jntadr[bid])
                    qa, da = int(c.model.jnt_qposadr[jid]), int(c.model.jnt_dofadr[jid])
                    q_pin = c.data.qpos[qa:qa + 7].copy()
                    a = math.radians(ang) if angle_kind == 'alpha' else 0.0
                    b = math.radians(ang) if angle_kind == 'beta' else 0.0
                    wind = [-v * math.cos(a) * math.cos(b), -v * math.sin(b), v * math.sin(a)]
                    c.set_command(dict(throttle=thr, **{chan: sign * dmax}))
                    n = int(round(DUR_S / c.DT))
                    tail = []
                    for i in range(n):
                        c.set_wind(wind)
                        c.data.qpos[qa:qa + 7] = q_pin
                        c.data.qvel[da:da + 6] = 0.0
                        c.step()
                        if i >= n - 40:  # last 0.1 s: steady state
                            tail.append(dict(c.last_aero_detail.get('hinge_moments', {})))
                    keys = tail[-1].keys()
                    steady = {k: round(float(np.mean([t[k] for t in tail])), 2) for k in keys}
                    cs = c.control_surface_telemetry()
                    rows.append(dict(V=v, throttle=thr, surface=surf, command=sign * dmax,
                                     angle_kind=angle_kind, angle_deg=ang, steady_hm_nm=steady,
                                     achieved_deg=cs[surf]['achieved_deg'],
                                     fan_rpm=[round(x) for x in c.last_fan_rpm]))
                    key = 'aileron_port' if surf == 'aileron' else surf
                    print(f'V={v:4.0f} thr={thr:.0f} {surf:8s} {sign*dmax:+5.0f} {angle_kind}={ang:+5.1f}: '
                          f'HM={steady.get(key, 0):8.2f} N m  achieved={cs[surf]["achieved_deg"]:+6.2f} deg  rpm={rows[-1]["fan_rpm"]}', flush=True)
json.dump(dict(method=__doc__, rows=rows, wall_s=round(time.time() - t0, 1)), open(sys.argv[2], 'w'), indent=1)
