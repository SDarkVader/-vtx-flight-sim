"""Towing-tank probe of RC-01 Concept A in the real plant (offline, isolated world, nothing live).

The airframe is towed at speed V along world +x: x, y and heading are held each 400 Hz step, while heave,
pitch and roll stay free, so it finds its own running height/trim and the skis their own immersion.
Still air, so airspeed == water speed. Heading offset psi (nose left +) gives sideslip beta = -psi.
At each V: settle at psi = 0, then psi = +3 and +6 deg. Reports the yaw / roll moment and side force
about the whole-vehicle CG from every applied wrench (hydro hull + each ski + aero/propulsion), the
Kirchhoff-Munk parts, ski immersion and vertical load, and running trim/height.
Usage: python towing_probe.py <worktree> <out.json> [load_case] [throttle]
"""
import json
import math
import sys
import time

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402

LC = sys.argv[3] if len(sys.argv) > 3 else 'LC-01'
THR = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402

fleet = HarbourFleet(harbour_world())
world = fleet.world
# Same water the harbour fleet gives its crafts (level 7.0 m over a 2.0 m bed, still, wake on)
WCFG = WaterEnvironmentConfig.from_dict(dict(water_level_m=world.harbour['waterLevelM'], wave_mode='still',
                                             wind_speed_mps=0.0, current_speed_mps=0.0,
                                             wake_enabled=False,  # captive tow: a held hull would dig its own wake hole
                                             whirlpools_enabled=False))
c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case=LC, water_config=WCFG)
m, d = c.model, c.data
af, sp, ss = c.bids['airframe'], c.bids['sponson_port'], c.bids['sponson_stbd']
jid = int(m.body_jntadr[af])
qa, da = int(m.jnt_qposadr[jid]), int(m.jnt_dofadr[jid])
X0, Y0 = 0.0, 0.0  # open water in the isolated harbour fixture (water level 7.0, bed 2.0)


def hold(V, psi):
    d.qpos[qa:qa + 2] = (X0, Y0)
    w, x, y, z = d.qpos[qa + 3:qa + 7]
    roll, pitch, _ = Rotation.from_quat([x, y, z, w]).as_euler('xyz')
    qx, qy, qz, qw = Rotation.from_euler('xyz', [roll, pitch, psi]).as_quat()
    d.qpos[qa + 3:qa + 7] = (qw, qx, qy, qz)
    d.qvel[da:da + 2] = (V, 0.0)
    d.qvel[da + 5] = 0.0  # no yaw rate (body z ~ world z at small roll/pitch)


def wrench_about_cg():
    cg = d.subtree_com[af].copy()
    F, M = np.zeros(3), np.zeros(3)
    parts = {}
    for b in range(1, m.nbody):
        f, t = d.xfrc_applied[b, :3], d.xfrc_applied[b, 3:]
        if not np.any(f) and not np.any(t):
            continue
        mb = t + np.cross(d.xipos[b] - cg, f)
        F += f
        M += mb
        parts[mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, b)] = (f.copy(), mb.copy())
    return F, M, parts


rows = []
t0 = time.time()
for V in (0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0):
    c.spawn(X0, Y0, 7.0)  # fresh start per speed: a capsize at one speed must not carry into the next
    c.set_command(dict(throttle=THR))
    capsized = False
    for psi_deg, dur in ((0.0, 7.0), (3.0, 2.5), (6.0, 2.5), (0.0, 2.5)):
        if capsized:
            break
        psi = math.radians(psi_deg)
        n = int(dur / c.DT)
        acc = []
        for i in range(n):
            v_now = V * min(1.0, c.data.time / 3.0)  # 3 s speed ramp, no impulsive start
            hold(v_now, psi)
            c.step()
            if i >= n - 80:  # last 0.2 s
                F, M, parts = wrench_about_cg()
                R = d.xmat[af].reshape(3, 3)
                eul = Rotation.from_matrix(R).as_euler('xyz', degrees=True)
                cl = (c.last_hydro.component_loads if c.last_hydro is not None else {})
                acc.append(dict(
                    Fx=F[0], Fy=F[1], Fz=F[2], Mx=M[0], My=M[1], Mz=M[2],
                    Mz_hull=parts.get('airframe', (np.zeros(3), np.zeros(3)))[1][2],
                    Mz_port=parts.get('sponson_port', (np.zeros(3), np.zeros(3)))[1][2],
                    Mz_stbd=parts.get('sponson_stbd', (np.zeros(3), np.zeros(3)))[1][2],
                    Fz_port=d.xfrc_applied[sp, 2], Fz_stbd=d.xfrc_applied[ss, 2],
                    Fy_port=d.xfrc_applied[sp, 1], Fy_stbd=d.xfrc_applied[ss, 1],
                    Mz_aero_prop=float((c.last_aero_torque_nm + c.last_propulsion_torque_nm)[2]),
                    munk_hydro_z=float(c.last_hydro.munk_torque_body[2]) if c.last_hydro is not None else 0.0,
                    munk_aero_z=float(c._last_aero_munk_nm[2]),
                    vol_hull=cl.get('main_hull', {}).get('submerged_volume_m3', 0.0),
                    vol_port=cl.get('sponson_port', {}).get('submerged_volume_m3', 0.0),
                    vol_stbd=cl.get('sponson_stbd', {}).get('submerged_volume_m3', 0.0),
                    z=d.qpos[qa + 2], roll=eul[0], pitch=eul[1],
                ))
        mean = {k: float(np.mean([a[k] for a in acc])) for k in acc[0]}
        mean['pitch_std'] = float(np.std([a['pitch'] for a in acc]))
        mean['z_std'] = float(np.std([a['z'] for a in acc]))
        row = dict(V=V, psi_deg=psi_deg, **{k: round(v, 3) for k, v in mean.items()})
        capsized = abs(row['roll']) > 60.0 or abs(row['pitch']) > 45.0
        row['capsized'] = capsized
        rows.append(row)
        print(f"V={V:4.0f} psi={psi_deg:+4.1f} z={row['z']:.3f}+-{row['z_std']:.3f} pitch={row['pitch']:+6.2f} roll={row['roll']:+6.2f} "
              f"vol h/p/s={row['vol_hull']:.3f}/{row['vol_port']:.3f}/{row['vol_stbd']:.3f} Fz p/s={row['Fz_port']:7.0f}/{row['Fz_stbd']:7.0f} "
              f"Fx={row['Fx']:7.0f} Fy={row['Fy']:7.0f} Mz={row['Mz']:8.0f} [hull {row['Mz_hull']:7.0f} p {row['Mz_port']:6.0f} s {row['Mz_stbd']:6.0f}] "
              f"Mx={row['Mx']:7.0f} munk h/a={row['munk_hydro_z']:7.0f}/{row['munk_aero_z']:5.0f}", flush=True)
json.dump(dict(method=__doc__, load_case=LC, throttle=THR, rows=rows, wall_s=round(time.time() - t0, 1)),
          open(sys.argv[2], 'w'), indent=1)

