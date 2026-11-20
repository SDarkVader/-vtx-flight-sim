"""Physical clearance, real powered passes, moving geometry and departmental road receipts."""
import argparse,json,math,sys
from pathlib import Path
from unittest.mock import patch
import mujoco as mj
import numpy as np
from vtx.world import make_world
from vtx.phantom.plant import PhantomAircraft,DT
from airport_pass import probe
from drive_pass import sampled_route,run
from streets import inspect,StreetIndex
from scipy.optimize import linprog


def road(world,name,directory,tag,speed,extend=False,timed=False):
    routes=world.vaderland['routes']
    route=next(r for r in routes if r['name']==name)
    links=[(route,False)]
    if extend:
        ring=next(r for r in routes if r['name']==('Meridian Avenue' if tag=='plaza' else 'Terminal boulevard'))
        ends=[min(range(len(ring['points'])),key=lambda i:np.linalg.norm(np.array(p)-ring['points'][i])) for p in [route['points'][-1],route['points'][0]]]
        pts=ring['points'];i,j=ends
        a=pts[i:j+1] if i<=j else pts[i:]+pts[1:j+1]
        b=list(reversed(pts[j:i+1] if j<=i else pts[j:]+pts[1:i+1]))
        if tag=='plaza':
            y0,y1=route['points'][-1][1],route['points'][0][1]
            middle=[p for p in reversed(pts) if y1<p[1]<y0]
            back=[route['points'][-1],*middle,route['points'][0]]
        else:back=min([a,b],key=len)
        links.append((dict(ring,points=back),False))
    path=sampled_route(links);length=float(np.linalg.norm(np.diff(path[0],axis=0),axis=1).sum())
    lap_length=length;pace=None
    if extend:
        if timed:
            xy,width=path
            extra=math.ceil(len(xy)*.34)
            path=(np.vstack([xy,xy[1:extra]]),np.r_[width,width[1:extra]])
            length=float(np.linalg.norm(np.diff(path[0],axis=0),axis=1).sum())
        xy=path[0];dist=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        def pace(s):
            ahead=np.linspace(s,s+40,8);q=np.array([np.interp(ahead,dist,xy[:,j]) for j in (0,1)]).T
            ab,bc=np.diff(q,axis=0)[:-1],np.diff(q,axis=0)[1:]
            area=abs(ab[:,0]*bc[:,1]-ab[:,1]*bc[:,0]);den=np.linalg.norm(ab,axis=1)*np.linalg.norm(bc,axis=1)*np.linalg.norm(ab+bc,axis=1)
            curve=np.max(2*area/np.maximum(den,1e-5));return max(5.,math.sqrt(2.3/max(curve,.001)))
    result=run(world,3,length-4,speed,path=path,record_m=length*.45,pace=pace,closed=extend)
    if result.get('pose'):(directory/((tag+'-timed' if timed else tag)+'-pose.json')).write_text(json.dumps(result.pop('pose')))
    result.update(route_m=lap_length,closure_m=float(np.linalg.norm(links[0][0]['points'][0]-np.asarray(links[-1][0]['points'][-1]))))
    if timed:
        from copy import deepcopy
        crossings=[];timer=world.timing
        key='Meridian Operations' if tag=='circuit' else world.vaderland['civic_district']['course']['name']
        for sample in result['samples']:
            before=timer.runs[key]['next']
            timer.sample(sample['t_s'],sample['xyz_m'])
            if timer.runs[key]['next']!=before:crossings.append(deepcopy(timer.runs[key]))
        result.update(timing=timer.runs[key],crossings=crossings)
    return result


def flight(w,direction,closed,lateral=0.):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phantom'))
    import a10c_airbrake_test as cruise
    with patch.object(cruise,'FlatWorld',return_value=w):p=cruise.build('off','cruise','phantom-a10c')
    d=p.data;m=p.model
    d.qpos[:3]=[1000-direction*234,-325+lateral,18.6]
    if direction<0:
        quat=np.zeros(4);mj.mju_mulQuat(quat,np.array([0.,0.,0.,1.]),d.qpos[3:7].copy())
        d.qpos[3:7]=quat;d.qvel[:2]*=-1
    p.scenery.command(d,'west' if direction>0 else 'east',not closed,True)
    mj.mj_forward(m,d)
    start=d.time;course=[];frames=[];maxrad=0.;width=0.;inner=0
    ids=np.flatnonzero((m.geom_contype==2)&(m.geom_bodyid>0))
    for i in range(round(6/DT)):
        p.step()
        if i%4==0:
            pos=d.qpos[:3]
            frame=dict(t_s=float(d.time-start),position=pos.tolist(),quat=d.qpos[3:7].tolist())
            frames.append(frame)
            if i%20==0:course.append(dict(**frame,speed_m_s=float(np.linalg.norm(d.qvel[:3]))))
            if 966<pos[0]<1034:
                R=d.geom_xmat[ids].reshape(-1,3,3)
                c=d.geom_xpos[ids]+np.einsum('ijk,ik->ij',R,m.geom_aabb[ids,:3])
                dr=np.einsum('ijk,ik->ij',np.abs(R),m.geom_aabb[ids,3:])
                maxrad=max(maxrad,np.linalg.norm(abs(c[:,1:]-[-325,18])+dr[:,1:],axis=1).max());inner+=1
                width=max(width,float(np.max(abs(c[:,1]-pos[1])+dr[:,1])))
        if p.crashed or (d.qpos[0]-1000)*direction>217:break
    return dict(status='impact' if p.crashed else 'passed' if (d.qpos[0]-1000)*direction>217 else 'incomplete',
        direction=direction,lateral_m=lateral,occupied_half_width_m=width,closed=closed,variant=p.variant,config=p.P.config_sha256,trajectory=course,
        frames=frames,sim_elapsed_s=d.time-start,in_bore_samples=inner,occupied_radius_upper_bound_m=float(maxrad),
        collisions=[e for e in p.events if e.get('event')=='collision'])


def gates(w):
    plane=PhantomAircraft(w,'phantom-a10c',start_configuration='road');plane.spawn(-3800,0,0)
    m,d=plane.model,plane.data
    def cast(f,times,origin,ray):
        for k,opened in f.items():plane.scenery.command(d,k,opened,True)
        d.time=times;plane.scenery.apply(d);mj.mj_forward(m,d)
        return dict(doors=plane.scenery.doors(d),time=times,**probe(plane,origin,ray))
    probes=[]
    for west,east in [(True,True),(False,True),(True,False),(False,False)]:
        for dy,dz in [(0,0),(6,2),(-6,-2),(0,7)]:
            probes.append(cast(dict(west=west,east=east),0,[948.,-325+dy,18.+dz],[1.,0.,0.]))
    for k in ('west','east'):plane.scenery.command(d,k,True,True)
    plane.scenery.apply(d);mj.mj_forward(m,d)
    failures=[];n=0
    for radius in [0,3,6,8,10,11]:
        for a in np.arange(64)*math.tau/64:
            y=-325+radius*math.cos(a);z=18+radius*math.sin(a)
            p=probe(plane,[320.,y,z],[1.,0.,0.]);n+=1
            if 0<=p['distance_m']<1360:failures.append(p)
    # Compare the actual eight transformed leaves using native surveyed rays at several times.
    d.time=1.;plane.scenery.command(d,'west',False)
    partial=[]
    for t in (1.,2.,3.,4.,5.):
        d.time=t;plane.scenery.apply(d);mj.mj_forward(m,d)
        partial.append(dict(t=t,open=float(plane.scenery.doors(d)['west']),
                 **probe(plane,[948.,-325.,18.],[1.,0.,0.])))
    for k in ('west','east'):plane.scenery.command(d,k,True,True)
    for t in (0,15,30,60,90):
        if 'civic_district' in w.vaderland:
            points=[(-183,2290,70),(-190,2290,72),(-176,2290,72),(-175,2290,80),(-190,2290,66)]
            if w.vaderland['civic_district'].get('monument'):
                points=[(x,2270,z) for x in (-213,-205,-196,-186,-183,-174,-162,-153) for z in (48.,58.,69.,79.)]
            for x,y,z in points:
                probes.append(cast({},t,[x,y,z],[0.,1.,0.]))
    return dict(sweep_count=n,protected_radius_m=11,protected_axial_length_m=1360,failures=failures,probes=probes,travel=partial)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('out',type=Path);a.add_argument('world');a.add_argument('section');args=a.parse_args()
    w=make_world(args.world);s=args.section
    if s.startswith('flight'):result=flight(w,-1 if 'east' in s else 1,s=='flight-closed',
                                            (4 if 'east' in s else -4) if 'passing' in s else 0.)
    elif s=='speedway-motion':
        track=next(r for r in w.vaderland['routes'] if r['name']==w.vaderland['speedway']['road'])
        gate=w.vaderland['speedway']['timing']['gates'][0]
        xy,widths=sampled_route([(track,False)])
        i=int(np.argmin(np.linalg.norm(xy-np.asarray(gate['center'][:2]),axis=1)))-65
        frames=[]
        def record(plane):
            # At 400 Hz there is always a real native sample within 1.25 ms of a video timestamp.
            target=3+len(frames)/30
            if len(frames)<300 and plane.data.time+DT*.5>=target:
                snap=plane.physical_snapshot()
                frames.append(dict(time_s=snap['t_s'],bodies=snap['body_poses']))
        result=run(w,2,253,22,path=(xy[i:i+180],widths[i:i+180]),record_m=95,record_step=record)
        (args.out/'speedway-scale-pose.json').write_text(json.dumps(result.pop('pose')))
        result.update(frames=frames,frame_rate=30)
    elif s=='speedway':
        track=next(r for r in w.vaderland['routes'] if r['name']=='Night Velocity Speedway')
        gate=w.vaderland['speedway']['timing']['gates'][0]
        xy,widths=sampled_route([(track,False)]);i=int(np.argmin(np.linalg.norm(xy-np.array(gate['center'][:2]),axis=1)))
        i=max(1,i-35);xy=np.vstack((xy[i:-1],xy[:i+100]));widths=np.full(len(xy),track['width_m'])
        ds=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        def pace(s):
            p=np.stack([np.interp(s+np.array([0,25,50,75,100]),ds,xy[:,j]) for j in (0,1)],axis=1)
            a,b=np.diff(p,axis=0)[:-1],np.diff(p,axis=0)[1:];cross=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])
            k=np.max(2*cross/np.maximum(1e-8,np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)*np.linalg.norm(a+b,axis=1)))
            return math.sqrt(2.1/max(.001,k))
        result=run(w,2.,ds[-1]-4.,30.,path=(xy,widths),closed=True,pace=pace)
        for p in result['samples']:w.timing.sample(p['t_s'],p['xyz_m'])
        result['timing']=w.timing.runs['Night Velocity']
    elif s=='gates':result=gates(w)
    elif s=='streets':result=inspect(w)
    else:
        tag=s.removesuffix('-timed')
        name={'circuit':'Meridian Operations Circuit','plaza':w.vaderland.get('civic_district',{}).get('course',{}).get('name','Aviator Plaza')+' Circuit','hall':'Terminal operations hall'}[tag]
        result=road(w,name,args.out,tag,18 if tag=='circuit' else 9 if tag=='plaza' else 7,tag in ('circuit','plaza'),s.endswith('-timed'))
    (args.out/(s+'.json')).write_text(json.dumps(result,indent=2))
    print({k:v for k,v in result.items() if k in ['status','sim_elapsed_s','in_bore_samples','occupied_radius_upper_bound_m','route_m','closure_m','sweep_count','elapsed_s']})
    if s=='gates':print('blocked bore rays',len(result['failures']),result['failures'][:1])
