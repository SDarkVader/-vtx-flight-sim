"""Run a bounded, isolated R6 hover check using the recorded Argon control gains.

The test owns its Laboratory and evidence directory. It never attaches to an
existing server or sortie. The result is simulated flight evidence, not a
validation of the physical aircraft.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.aircraft import DT
from vtx.live_server import Action, Laboratory, Mission


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    lab = Laboratory(data_root=out)
    mission = Mission(authority='manual', airframe_variant='r6', gear_variant='critical-damping-proposal',
                      reference_rpm=1200, fuel_kg=10, engine_power_limit_kw=300,
                      label='Isolated R6 Argon hover integration check')
    lab.start(mission)
    p = lab.aircraft
    sample = []
    integrals = [0., 0., 0.]
    last_control = -1.
    last_t = 0.
    spool_done = None
    origin = None
    result = 'duration limit'
    while lab.active and p.data.time < 35:
        if p.data.time - last_control >= .05 - DT / 2:
            obs = lab.sensor_observation()
            t = obs['t_s']; dtime = clamp(t-last_t, 0, .1); last_t = t; last_control = float(p.data.time)
            attitude = obs['attitude_xyz_deg']; rates = obs['gyro_world_deg_s']
            clearance = obs['radar_clearance_m']
            if clearance is None or 'IMPACT' in obs['warning_lamps'] or max(abs(x) for x in attitude[:2]) > 15:
                result = 'instrument or attitude abort'
                break
            rpm = sum(obs['rotor_rpm']) / 4
            tilt_feedback = max(math.hypot(*x) for x in obs['tilt_feedback_deg'])
            if spool_done is None and rpm >= 1180 and tilt_feedback <= 1.2:
                spool_done = t; origin = obs['gnss_xy_m'][:]
            if spool_done is None:
                collective = [0.] * 4; tilt = [[0., 0.] for _ in range(4)]
            else:
                roll, pitch, yaw = attitude; wx, wy, wz = rates
                vx, vy, vz = obs['gnss_velocity_mps']; x, y = obs['gnss_xy_m']
                target = min(2., 1.15*(t-spool_done)); vz_ff = 1.15 if target < 2 else 0.
                if clearance > .14:
                    integrals[0] = clamp(integrals[0]+roll*dtime, -1.8, 1.8)
                    integrals[1] = clamp(integrals[1]+pitch*dtime, -1.8, 1.8)
                    integrals[2] = clamp(integrals[2]+(target-clearance)*dtime, -1.2, 1.2)
                pitch_des = clamp(-.32*(x-origin[0])-.45*vx,-2.5,2.5) if clearance>.34 else 0.
                roll_des = clamp(.32*(y-origin[1])+.45*vy,-2.5,2.5) if clearance>.34 else 0.
                mean = clamp(16.98+1.15*(target-clearance)+1.65*(vz_ff-vz)+.35*integrals[2],14.5,18.65)
                ur = clamp(-.62*(roll-roll_des)-.32*wx-.24*integrals[0],-3.5,3.5)
                up = clamp(-.62*(pitch-pitch_des)-.32*wy-.24*integrals[1],-3.5,3.5)
                collective = [clamp(c,0,30) for c in [mean-up,mean+.70+ur,mean+up,mean-.70-ur]]
                uy = clamp(-.85*yaw-.55*wz,-4,4)
                tilt = [[-uy,0],[0,-uy],[uy,0],[0,uy]]
            lab.accept_action(Action(authority='manual', expected_run_id=lab.run_id,
                observation_id=obs['observation_id'], reason='Isolated Argon hover integration check',
                engine=1., collective_deg=collective, tilt_deg=tilt))
            sample.append(dict(t_s=t, clearance_m=clearance, rpm=rpm, attitude_deg=attitude,
                               position_m=obs['gnss_xy_m'], collective_deg=collective))
            if clearance >= 1.5 and t > (spool_done or 0) + 2:
                result = 'airborne clearance reached'
                break
        lab.integrate()
    if not lab.active:
        result = 'collision or run stopped'
    run_id = lab.run_id
    if lab.active:
        lab.stop('Isolated hover check completed: '+result)
    report = dict(result=result, run_id=run_id, variant=p.airframe_variant,
                  revision=p.provenance['revision'], physics_revision=p.provenance['physics_revision'],
                  render_asset=p.provenance['render_asset'], max_radar_clearance_m=max((x['clearance_m'] for x in sample),default=None),
                  spool_done_s=spool_done, samples=sample,
                  limitations='Simulation only; not an autonomous navigation or aircraft certification claim.')
    (out/'hover_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'samples'},indent=2))
    return result == 'airborne clearance reached'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, help='New evidence directory; must not already exist')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.out) else 1)
