"""Independent MuJoCo surface, approach, foundation and impact audit."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import mujoco as mj
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from vtx.world import make_world
from vtx.phantom.plant import PhantomAircraft, DT


def sample_grid(world, x0,y0,x1,y1):
    axis=np.linspace(-world.half,world.half,world.n)
    xs=np.r_[x0,axis[(axis>x0)&(axis<x1)],x1]
    ys=np.r_[y0,axis[(axis>y0)&(axis<y1)],y1]
    return [(x,y) for x in xs for y in ys]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--world',required=True)
    args=p.parse_args()
    world=make_world(args.world)
    plant=PhantomAircraft(world,'phantom-a10c',start_configuration='road')
    plant.spawn(-3885,0,0)
    up=np.array([0.,0.,-1.])
    gid=plant.gid['terrain']
    rng=np.random.default_rng(1897)
    errors=[]
    for x,y in rng.uniform(-7998,7998,(1000,2)):
        dist=mj.mj_rayHfield(plant.model,plant.data,gid,np.array([x,y,3000.]),up)
        errors.append(abs((3000.-dist)-world.terrain_z(x,y)) if dist>=0 else 9999.)
    row,col=np.unravel_index(world.heights.argmax(),world.heights.shape)
    peak_x=-world.half+col*world.half*2/(world.n-1)
    peak_y=-world.half+row*world.half*2/(world.n-1)
    hit_geom=np.array([-1],dtype=np.int32)
    summit_range=mj.mj_ray(plant.model,plant.data,np.array([peak_x,peak_y,3000.]),up,None,True,-1,hit_geom)
    peak=dict(x=peak_x,y=peak_y,terrain_m=float(world.heights.max()),ray_m=3000.-summit_range,
              geom=plant.model.geom(int(hit_geom[0])).name if summit_range>=0 else None,range_m=world.height_scale_m)
    approaches=[]
    for side in [-1,1]:
        # Check the complete 1 km corridor, not just its centreline.
        heights=world.heights[(np.abs(np.linspace(-world.half,world.half,world.n))<=500),:]
        band=heights[:,np.linspace(-world.half,world.half,world.n)*side>=3900]
        obstructions=[o['id'] for o in world.obstacles if
                      o['center'][0]*side+o['half'][0]>=3900 and
                      abs(o['center'][1])-o['half'][1]<=500]
        approaches.append(dict(side=side,ground_max_m=float(band.max()),width_m=1000,
                               length_m=world.half-3900,structures=obstructions))
    # Reuse the project's airborne cruise fixture. Only its choice of terrain
    # is injected: same wing-lock sequence, spool, pilot inputs and integrator.
    sys.path.insert(0,str(ROOT/'tools'/'phantom'))
    import a10c_airbrake_test as cruise_card
    with patch.object(cruise_card,'FlatWorld',return_value=world):
        airborne=cruise_card.build('off','cruise','phantom-a10c')
    airborne.data.qpos[0]=-7980.
    mj.mj_forward(airborne.model,airborne.data)
    fixes=[dict(t=0.,xyz=airborne.data.qpos[:3].tolist(),crashed=False)]
    start=airborne.data.time
    for _ in range(60):
        for _ in range(round(1/DT)):
            airborne.step()
        fixes.append(dict(t=airborne.data.time-start,xyz=airborne.data.qpos[:3].tolist(),crashed=bool(airborne.crashed)))
        if airborne.crashed or airborne.data.qpos[0]>-3885.:break
    # An intentionally bad descent into a high ridge. Contact must be with the
    # terrain geom, hundreds of metres above the infinite backup floor.
    x,y=-6500.,5900.
    plant.spawn(x,y,world.terrain_z(x,y)+15)
    plant.data.qvel[2]=-16.
    mj.mj_forward(plant.model,plant.data)
    events=[]
    for _ in range(round(2./DT)):
        plant.step()
        for c in plant.data.contact:
            if gid in c.geom:
                if not events:events.append(dict(t=plant.data.time,altitude_m=float(plant.data.qpos[2]),
                   geoms=[plant.model.geom(int(i)).name for i in c.geom]))
        if plant.crashed and events:break
    first_impact=dict(terrain_z=world.terrain_z(x,y),contacts=events,crashed=bool(plant.crashed))
    # The steep new ridge can deflect a tyre strike. Also test a severe impact
    # with the inverted fuselage using the aircraft's original damage threshold.
    plant.spawn(x,y,world.terrain_z(x,y)+38)
    plant.data.qpos[3:7]=[0.,1.,0.,0.];plant.data.qvel[2]=-37.
    mj.mj_forward(plant.model,plant.data)
    severe=[]
    for _ in range(round(2/DT)):
        plant.step()
        if plant.crashed:
            severe=[item for item in plant.events if item['event']=='collision'];break
    floating=[];stacks=0;spans=0
    by_id={o['id']:o for o in world.obstacles}
    span_data={s['name']:s for s in world.vaderland.get('spans',[])}
    from scipy.optimize import linprog
    def world_planes(obj):
        if obj['kind']=='mesh':
            p=np.array(obj['planes']);p[:,3]-=p[:,:3]@np.array(obj['center']);return p
        center=np.array(obj['center']);half=np.array(obj['half']);normals=np.vstack((np.eye(3),-np.eye(3)))
        return np.c_[normals,-normals@center-np.tile(half,2)]
    for o in world.obstacles:
        if o.get('hinge') or o.get('support')=='joint':
            other=by_id[o.get('hinge') or o['parent']];p=np.vstack((world_planes(o),world_planes(other)))
            joint=linprog([0,0,0,1],A_ub=np.c_[p[:,:3],-np.ones(len(p))],b_ub=-p[:,3],bounds=[(None,None)]*3+[(0,None)],method='highs')
            if not joint.success or joint.x[3]>.045:floating.append(dict(id=o['id'],parent=other['id'],joint_gap_m=None if not joint.success else float(joint.x[3])))
            stacks+=1;continue
        if o.get('support')=='stack':
            parent=by_id[o['parent']]
            bottom=o['center'][2]-o['half'][2]
            overlap=all(abs(o['center'][i]-parent['center'][i])<o['half'][i]+parent['half'][i] for i in [0,1])
            if not overlap or abs(bottom-parent['center'][2]-parent['half'][2])>.2:
                floating.append(dict(id=o['id'],reason='stack does not bear on parent'))
            stacks+=1
            continue
        if o.get('support')=='span':
            name=o['span'];x,y,z=o['center'];a,b,c=o['half']
            if 'bearings' in o:
                for oid in o['bearings']:
                    p=by_id[oid]
                    overlap=all(abs(o['center'][i]-p['center'][i])<o['half'][i]+p['half'][i] for i in (0,1))
                    underside=z-c
                    if o['kind']=='mesh':
                        # Evaluate the actual underside at each column head.
                        # A bowed canopy has different bearing elevations.
                        planes=np.asarray(o['planes']);low=planes[:,2]<-1e-8
                        xy=np.asarray(p['center'][:2])-o['center'][:2]
                        underside=z+np.max(-(planes[low,:2]@xy+planes[low,3])/planes[low,2])
                        overlap=overlap and np.all((planes[:,:2]@xy+planes[:,2]*(underside-z)+planes[:,3])<.002)
                    if not overlap or abs(underside-p['center'][2]-p['half'][2])>.2:
                        floating.append(dict(id=o['id'],reason='roof detached from '+oid))
            elif name in span_data:
                supports=[by_id[pid] for pid in span_data[name]['piers']]
                reach=min(np.hypot(x-p['center'][0],y-p['center'][1]) for p in supports)
                if reach>70 and world.terrain_z(x,y)<z-c-.35:
                    floating.append(dict(id=o['id'],reason='span exceeds supported reach',distance=float(reach)))
            elif name=='gallery':
                if any(abs(by_id['gallery-wall-'+str(i)]['center'][2]+by_id['gallery-wall-'+str(i)]['half'][2]-(z-c))>.5 for i in [-1,1]):
                    floating.append(dict(id=o['id'],reason='roof detached from wall'))
            else:
                piles=[p for p in world.obstacles if p['id'].startswith(name+'-pile-')]
                if len(piles)!=3 or any(p['center'][2]+p['half'][2]<z-c for p in piles):
                    floating.append(dict(id=o['id'],reason='pier deck detached from piles'))
            spans+=1
            continue
        x,y,z=o['center'];a,b,c=o['half']
        if o['kind']=='box': points=sample_grid(world,x-a,y-b,x+a,y+b)
        else:points=[(x,y)]
        # Minimum support prevents a skirt hovering even at its downhill corner.
        gap=z-c-min(world.terrain_z(px,py) for px,py in points)
        if gap>.08:floating.append(dict(id=o['id'],gap_m=gap))
    result=dict(world=world.environment_key,terrain_rays=len(errors),max_ray_error_m=max(errors),
                approaches=approaches,peak=peak,flight=fixes,impact=first_impact,inverted_impact=severe,unsupported=floating,
                structures_checked=len(world.obstacles),stacked_elements=stacks,span_elements=spans)
    (args.directory/'contacts.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ray error',max(errors),'approaches',approaches,'flight exit',fixes[-1],
          'impact',result['impact'],'unsupported',floating[:5])
    return bool(max(errors)>.002 or peak['geom']!='terrain' or abs(peak['ray_m']-peak['terrain_m'])>.002
                or any(a['structures'] or a['ground_max_m'] for a in approaches)
                or fixes[-1]['crashed'] or fixes[-1]['xyz'][0]<-3900 or not events or not severe or floating)


if __name__=='__main__':
    sys.exit(main())
