"""Repeat a short A10 FX-A spawn/climb experiment in a separate data root.

This is an open-loop experiment using the Phantom's attitude/vertical-speed
mode, not a demonstration of a conversational pilot or general flight stability.
Existing flight sessions and their data roots are never accessed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import numpy as np
from vtx.live_server import Laboratory, Mission
from vtx.phantom.controls import PhantomAction


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',required=True,help='Separate directory for retained experiment evidence')
    parser.add_argument('--seconds',type=float,default=12.0)
    args=parser.parse_args()
    if args.seconds <= 0: parser.error('--seconds must be positive')
    root=Path(args.data_root).resolve();root.mkdir(parents=True,exist_ok=True)
    for ignore in (False,True):
        data_root=root/('scenery_off' if ignore else 'scenery_on')
        # Never replace a prior unfinished test; Laboratory recovers its checkpoint.
        os.environ['VTX_DATA_ROOT']=str(data_root)
        lab=Laboratory()
        if lab.active or lab.recovery_blocked:
            raise RuntimeError(f'{data_root} has a flight requiring recovery; choose another data root')
        mission=Mission(airframe_variant='phantom-fx',phantom={'load_state':'FX-A'},
                        ignore_scenery_collisions=ignore)
        run=lab.start(mission)['run_id'];p=lab.aircraft
        spawn=[float(v) for v in p.data.qpos[:3]];surface=float(lab.flight_world.surface_z(0,0))
        start=float(p.data.qpos[2]);max_height=0.;max_horizontal=0.
        obs=lab.sensor_observation()
        lab.accept_action(PhantomAction(schema='phantom-fbw-1',authority='manual',
            observation_id=obs['observation_id'],reason='Isolated FX-A vertical climb test',
            stability_mode='attitude_vs',engine=1,collective=.6,vertical_speed_m_s=1,brake=[0]*4))
        while p.data.time<args.seconds and not p.crashed:
            lab.integrate()
            max_height=max(max_height,float(p.data.qpos[2]-start))
            max_horizontal=max(max_horizontal,float(np.linalg.norm(p.data.qpos[:2]-spawn[:2])))
        result=dict(ignore_scenery_collisions=ignore,run_id=run,spawn_m=spawn,ground_m=surface,
            elapsed_s=float(p.data.time),max_height_gain_m=max_height,
            final_height_gain_m=float(p.data.qpos[2]-start),max_horizontal_distance_m=max_horizontal,
            final_speed_m_s=float(np.linalg.norm(p.data.qvel[:3])),airborne=bool(p.airborne),
            crashed=bool(p.crashed),events=p.events[-5:])
        print(json.dumps(result),flush=True)
        lab.stop('Isolated readiness experiment complete')


if __name__=='__main__': main()
