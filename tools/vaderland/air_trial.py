"""Record stock Phantom airborne-start tests through the two native air courses."""
import argparse
import gzip
import json
from pathlib import Path
import sys
from unittest.mock import patch

import mujoco as mj
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phantom'))
import a10c_airbrake_test as cruise
from vtx.phantom.plant import DT
from vtx.world import make_world


def test(world,course,out):
    with patch.object(cruise,'FlatWorld',return_value=world):
        aircraft=cruise.build('off','cruise')
    first=np.asarray(course['gates'][0]['center'])
    data=aircraft.data
    # Seed the established airborne cruise fixture upstream of the timing gate.
    data.qpos[:3]=first-[course['entry_lead_m']-9.,0.,0.]
    mj.mj_forward(aircraft.model,data)
    start=data.qpos[:3].tolist()
    contact_sensor=aircraft.contact_samples
    start_t=float(data.time)
    part=np.flatnonzero((aircraft.model.geom_contype==2)&(aircraft.model.geom_bodyid>0))
    max_ext=np.zeros(2)
    frames=[]
    the_run=world.timing.runs[course['name']]
    for i in range(round(20./DT)):
        aircraft.step()
        world.timing.sample(float(data.time), data.qpos[:3])
        rotations=data.geom_xmat[part].reshape(-1,3,3)
        centers=data.geom_xpos[part]+np.einsum('ijk,ik->ij',rotations,aircraft.model.geom_aabb[part,:3])
        extents=np.einsum('ijk,ik->ij',abs(rotations),aircraft.model.geom_aabb[part,3:])
        maximum=(abs(centers[:,1:]-first[1:])+extents[:,1:]).max(axis=0)
        max_ext=np.maximum(maximum,max_ext)
        if i%12==0 or the_run['laps']:
            snap=aircraft.physical_snapshot()
            frames.append({k:snap[k] for k in ('t_s','variant','config_sha256','body_poses',
                                              'phantom','provenance','propulsors','contact') if k in snap})
        assert not (aircraft.crashed or contact_sensor()), (course['name'],data.time,aircraft.events[-8:])
        if the_run['laps']:
            break
    assert the_run['laps']==1,(course['name'],the_run,data.qpos[:3])
    assert all(max_ext < (np.asarray(course['clear_bounds'][1])[1:]-first[1:])),max_ext
    out.mkdir(parents=True,exist_ok=True)
    (out/'motion.json.gz').write_bytes(gzip.compress(json.dumps(frames,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    result=dict(course=course['name'],variant=aircraft.variant,config=aircraft.P.config_sha256,
                start_position=start,elapsed_s=float(data.time)-start_t,
                timing=the_run,no_contact=True,occupied_half_extents_m=max_ext.tolist(),
                exit_speed_mps=float(np.linalg.norm(data.qvel[:3])))
    (out/'flight-proof.json').write_text(json.dumps(result,indent=2))
    print(result,flush=True)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('out',type=Path)
    cli.add_argument('--course',required=True)
    args=cli.parse_args()
    w=make_world('vaderland-29')
    test(w,next(c for c in w.vaderland['air_trials'] if c['name']==args.course),args.out)