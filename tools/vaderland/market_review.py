"""Record native wall, roof, street furniture and commuter positions in the market district."""
import argparse
import json
from pathlib import Path

import mujoco as mj
import numpy as np

from airport_pass import probe
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


def audit(out, environment):
    world=make_world(environment)
    p=PhantomAircraft(world,'phantom-a10c',start_configuration='road')
    p.spawn(-3885,0,0)
    area=world.vaderland['quarter']
    tests=[]
    full={o['id']:o for o in world.obstacles}
    for lot in area['lots'][::22]:
        xy=np.array(lot['door']);n=np.array(lot['front'])
        h=lot['datum']+2.55
        tests.append(dict(label=lot['id']+' entry glazing',**probe(p,[*(xy+n*3.25),h],[*-n,0.])))
        x,y=lot['xy']
        tests.append(dict(label=lot['id']+' vertical',**probe(p,[x,y,700.],[0,0,-1])))
    for o in world.obstacles:
        if o['id'].startswith('market-kiosk-') and o['id'].endswith('-counter'):
            x,y,z=o['center']
            tests.append(dict(label=o['id']+' roof',**probe(p,[x,y,z+20],[0,0,-1])))
    (out/'airport-shells.json').write_text(json.dumps(dict(probes=tests),indent=2))
    ref=area['stalls'][0];camera=[*ref['xy'],ref['z']+2]
    subjects=[s for s in area['people'] if np.linalg.norm(np.array(s['center'])-camera[:2])<160]
    heads=[];max_gap=0.
    for t in [0.,3.25,12.,17.25,34.]:
        p.scenery.apply(p.data,scene_time=t);mj.mj_kinematics(p.model,p.data)
        for spec in subjects:
            name=spec['name'];bid=p.model.body('environment-'+name).id
            root=p.data.xpos[bid].copy();index=area['people'].index(spec)
            speed=np.linalg.norm(-np.array(spec['a'])*np.sin(spec['phase']+t*2*np.pi/spec['period_s'])+
                                  np.array(spec['b'])*np.cos(spec['phase']+t*2*np.pi/spec['period_s']))*2*np.pi/spec['period_s']
            bob=abs(np.cos(t*(5.1+index%4*.28)+index*1.63))*.01*min(1,speed/1.33)
            h=spec['height_m'];dir_world=p.data.xmat[bid].reshape(3,3)[:,0]
            head=root+dir_world*(.015*h)+[0,0,(.837+bob)*h]
            max_gap=max(max_gap,abs(root[2]-world.terrain_z(*root[:2])))
            heads.append(dict(time=t,name=name,head=head.tolist()))
    (out/'market-people.json').write_text(json.dumps(dict(camera=camera,heads=heads,native_foot_max_m=max_gap)))
    print(len(tests),'native survey rays,',len(subjects),'local residents,',len(heads),'head positions, gap m',max_gap)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('out',type=Path)
    parser.add_argument('--world',default='vaderland-16')
    args=parser.parse_args();audit(args.out,args.world)
