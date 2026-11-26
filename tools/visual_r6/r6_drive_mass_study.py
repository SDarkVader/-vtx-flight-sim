"""Offline drive-component mass study: re-fly the recorded A-to-B sortie with real-part masses.

usage: python r6_drive_mass_study.py <checkout_root> <config.json> <out.json> [seconds]

config.json: {"name": str,
              "fan_edits": [{"body": "airframe"|"nacelle", "kg": +add / -remove, "at_F1": [x, y, z], "part": str}]}
Each fan edit is written for fan 1 and repeated for fans 2-4 by rotating its position 90 degrees about z
(fan j sits at 90*(j-1) degrees); "nacelle" means that fan's own nacelle body.

The edits change body mass, centre of mass and inertia of the MuJoCo model in memory, after the
aircraft is built and before it is spawned, then the unmodified r6_physics_replay.py pilot flies the
sortie. model.xml on disk is never touched. Positions are airframe-frame rest coordinates (z up).
"""
from __future__ import annotations

import json
import math
import runpy
import sys
from pathlib import Path

root, config_path, out_path = sys.argv[1:4]
seconds = sys.argv[4] if len(sys.argv) > 4 else '150'
sys.path.insert(0, root + '/src')

import mujoco as mj  # noqa: E402
import numpy as np  # noqa: E402
import vtx.aircraft as aircraft_module  # noqa: E402

CONFIG = json.load(open(config_path))
APPLIED = []


def _rz(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])


def add_point_mass(m, rest, bid, kg, r_world):
    """Add (or remove, kg < 0) a point mass at rest-world position r_world to body bid."""
    xpos, xmat = rest.xpos[bid], rest.xmat[bid].reshape(3, 3)
    r = xmat.T @ (np.asarray(r_world, float) - xpos)            # body frame
    M, c = float(m.body_mass[bid]), m.body_ipos[bid].copy()
    q = m.body_iquat[bid]
    R = np.zeros(9)
    mj.mju_quat2Mat(R, q)
    R = R.reshape(3, 3)
    Ic = R @ np.diag(m.body_inertia[bid]) @ R.T
    M2 = M + kg
    if M2 <= 0:
        raise ValueError(f'body {bid} mass would become {M2}')
    c2 = (M * c + kg * r) / M2

    def shift(mass, p):
        o = p - c2
        return mass * (np.eye(3) * (o @ o) - np.outer(o, o))
    I2 = Ic + shift(M, c) + shift(kg, r)
    w, V = np.linalg.eigh(I2)
    if np.linalg.det(V) < 0:
        V[:, 0] *= -1
    q2 = np.zeros(4)
    mj.mju_mat2Quat(q2, V.flatten())
    m.body_mass[bid], m.body_ipos[bid], m.body_inertia[bid], m.body_iquat[bid] = M2, c2, np.maximum(w, 1e-9), q2


def mass_properties(m, d):
    mass = float(m.body_mass.sum())
    com = np.sum(m.body_mass[:, None] * d.xipos, axis=0) / mass
    inertia = np.zeros((3, 3))
    for i in range(m.nbody):
        rot = d.ximat[i].reshape(3, 3)
        o = d.xipos[i] - com
        inertia += rot @ np.diag(m.body_inertia[i]) @ rot.T + m.body_mass[i] * (np.eye(3) * (o @ o) - np.outer(o, o))
    return mass, com, inertia


_original_init = aircraft_module.Aircraft.__init__


def patched_init(self, *a, **k):
    _original_init(self, *a, **k)
    m = self.model
    rest = mj.MjData(m)
    mj.mj_forward(m, rest)
    before = mass_properties(m, rest)
    for j in range(1, 5):
        rot = _rz(90 * (j - 1))
        for e in CONFIG.get('fan_edits', []):
            body = 'airframe' if e['body'] == 'airframe' else f'nacelle{j}'
            at = rot @ np.array(e['at_F1'], float)
            add_point_mass(m, rest, self.bids[body] if body in self.bids else mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, body), e['kg'], at)
            APPLIED.append(dict(fan=j, body=body, kg=e['kg'], at=[round(float(v), 4) for v in at], part=e.get('part', '')))
    mj.mj_setConst(m, mj.MjData(m))
    after_d = mj.MjData(m)
    mj.mj_forward(m, after_d)
    after = mass_properties(m, after_d)
    self._drive_study = dict(
        mass_before_kg=round(before[0], 3), mass_after_kg=round(after[0], 3),
        com_before_m=[round(float(v), 4) for v in before[1]], com_after_m=[round(float(v), 4) for v in after[1]],
        inertia_diag_before=[round(float(v), 2) for v in np.diag(before[2])],
        inertia_diag_after=[round(float(v), 2) for v in np.diag(after[2])])
    aircraft_module._LAST = self


aircraft_module.Aircraft.__init__ = patched_init
replay = str(Path(__file__).with_name('r6_physics_replay.py'))
sys.argv = [replay, root, 'r6', 'historical', out_path, seconds]
runpy.run_path(replay, run_name='__main__')

result = json.load(open(out_path))
p = aircraft_module._LAST
trace = result['trace']
hover = [r for r in trace if r['phase'] in ('climb', 'transit') and r['clear'] and r['clear'] > 9.0]
result['drive_study'] = dict(config=CONFIG, applied=APPLIED, **p._drive_study,
                             max_engine_kw=max(r['shaft_kw'] for r in trace),
                             mean_hover_kw=round(sum(r['shaft_kw'] for r in hover) / len(hover), 2) if hover else None,
                             min_rpm_after_spool=min((r['rpm'] for r in trace if r['phase'] != 'spool'), default=None))
json.dump(result, open(out_path, 'w'), indent=1)
print(json.dumps(result['drive_study'] | {k: result[k] for k in ('outcome', 'distance_to_B_m', 'max_attitude_deg', 'simulated_s')}, indent=1))
