"""Run the Lantern Islet race offline with ordinary Ricochet helm inputs."""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

from vtx.harbour_session import _public_fleet, _restart_boat
from vtx.harbour_trial import LanternTrialFleet
from vtx.world import make_world


BOAT = 'ricochet-marina'


def run_trial(out, pace, *, seconds=210., full_fleet=True, environment='vaderland-28'):
    world = make_world(environment)
    vessels = None if full_fleet else [
        dict(id=BOAT,name='Ricochet - Lantern Marina',
             variant='ricochet-concept-a',berth_id='lantern-marina-ricochet')
    ]
    fleet = LanternTrialFleet(world,vessels=vessels)
    fleet.select(BOAT)
    fleet = _restart_boat(world,fleet,{'boatId':BOAT,'timeTrial':True})
    print('Staged Ricochet',fleet._pose(BOAT)[:2],flush=True)
    out.mkdir(parents=True,exist_ok=True)
    for boat_id in fleet.crafts:
        (out/f'model-{boat_id}.json.gz').write_bytes(gzip.compress(
            json.dumps(fleet.visual_geometry(boat_id)).encode(),mtime=0))
    (out/'fleet-state.json.gz').write_bytes(gzip.compress(
        json.dumps(_public_fleet(fleet)).encode(),mtime=0))
    p = np.asarray(fleet.trial['points'])
    distances = np.r_[0.,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    length = distances[-1]
    distances=np.r_[distances[:-1]-length,distances[:-1],distances+length]
    p=np.vstack([p[:-1],p[:-1],p])
    at=lambda s:np.array([np.interp(s,distances,axis) for axis in p.T])
    progress = 7.
    rows = []
    status = 'time limit'
    checkpoint_verified = False
    for n in range(math.ceil(seconds*10)):
        xyz,h,velocity = fleet._pose(BOAT)
        speed = np.linalg.norm(velocity[3:5])
        local = np.flatnonzero(abs(distances-progress)<28.)
        delta = np.linalg.norm(p[local]-xyz[:2],axis=1)
        progress = distances[local[delta.argmin()]]
        lookahead = min(25.,11.+speed*1.2)
        target = at(progress+lookahead)-xyz[:2]
        bearing = math.atan2(target[1],target[0])
        drift=math.atan2(velocity[4],velocity[3])-h
        drift=math.remainder(drift,math.tau)*min(1.,max(0.,(speed-1.)/3.))
        demand = math.remainder(bearing-h-.68*np.clip(drift,-.7,.7),math.tau)
        rudder = float(np.clip(100.*demand-28.*velocity[2],-30.,30.))
        arc = progress%length
        goal = min(pace,pace*.78 if 555.<arc<688. else pace)
        throttle = float(np.clip(.27+.13*(goal-speed),.09,.86))
        differential = float(np.clip(.63*demand-.26*velocity[2],-.65,.65))
        fleet.action(BOAT,dict(throttle=throttle,rudder_deg=rudder,differential_thrust=differential))
        for j in range(10):
            fleet.step()
        race=fleet.race_clocks[BOAT].runs[fleet.trial['name']]
        if n%5==0:
            rows.append(dict(t_s=float(fleet.data.time),position=xyz.tolist(),heading_rad=h,
                 chain_m=float(progress),offset_m=float(delta.min()),speed_mps=float(speed),
                 next_gate=race['next'],foul=fleet.race_fouls[BOAT]))
        if n%100==0:
            print(n*.1,'chain',round(progress,2),'speed',round(speed,2),'offset',round(float(delta.min()),2),
                  'gate',race['next'],'foul',fleet.race_fouls[BOAT],flush=True)
        if race['next']>=3 and not checkpoint_verified:
            saved=fleet.serialize()
            restored=LanternTrialFleet.restore(world,saved)
            assert restored.public()['lantern_trial']==fleet.public()['lantern_trial']
            before=fleet.data.qpos.copy()
            assert np.array_equal(restored.data.qpos,before)
            restored.step()
            fleet.step()
            assert np.array_equal(restored.data.qpos,fleet.data.qpos)
            assert restored.public()['lantern_trial']==fleet.public()['lantern_trial']
            checkpoint_verified=True
        if race['laps']:
            status='complete'
            break
        if fleet.crafts[BOAT].crashed or delta.min()>28. or fleet.race_fouls[BOAT]:
            status='left course or fouled'
            break
    receipt=dict(status=status,world=world.environment_key,boat=BOAT,pace=pace,
        vessel_count=len(fleet.crafts),physics=fleet.dynamics_id,
        checkpoint_verified=checkpoint_verified,race=fleet.public()['lantern_trial']['runs'][BOAT],
        rows=rows)
    (out/'trial.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(status,receipt['race'],flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path)
    parser.add_argument('--pace',type=float,default=9.0)
    parser.add_argument('--seconds',type=float,default=205.0)
    parser.add_argument('--single',action='store_true')
    parser.add_argument('--world',default='vaderland-28')
    args=parser.parse_args()
    if not (math.isfinite(args.pace) and math.isfinite(args.seconds) and args.pace>0 and args.seconds>0):
        parser.error('Trial duration and pace must be positive and finite')
    receipt=run_trial(args.out,args.pace,seconds=args.seconds,full_fleet=not args.single,environment=args.world)
    if receipt['status']!='complete':
        raise SystemExit(1)
