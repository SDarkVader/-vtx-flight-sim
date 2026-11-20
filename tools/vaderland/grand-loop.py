"""Bake an eased, larger-radius Grand Loop on its existing approach and run-out."""
import gzip
import json
import math
from pathlib import Path
import runpy

import numpy as np
from scipy.integrate import solve_ivp

from drafting import Masonry
from vtx.vaderland import PACK
from vtx.world import make_world

# Reuse the existing gantry authoring and driven-envelope survey.
LEGACY = runpy.run_path(str(Path(__file__).with_name('vertical-loops.py')))
GRAVITY = LEGACY['GRAVITY']
REFERENCE_MPS = 34.4
LOOP_LOAD = 2.27
CROWN_LOAD = .62
EASE_SCALE = 495.
EASE_RATE = 25.
RADIUS_FLOOR_M = 20.
SHOULDER_RISE_M = .85


def loop_profile(track):
    old=np.asarray(track['stations'])
    begin=old[track['loop_in']]
    end=old[track['loop_out']]
    slope=(old[track['loop_in'],1]-old[0,1])/(old[track['loop_in'],0]-old[0,0])
    def angle(u):
        return 2*np.pi*u**2*(3-2*u)
    def ode(u,state):
        theta=angle(u)
        low=.5-.5*np.cos(theta)
        load=LOOP_LOAD-(LOOP_LOAD-CROWN_LOAD)*low**5
        v2=REFERENCE_MPS**2-2*GRAVITY*state[1]
        raw=v2/(GRAVITY*(load-np.cos(theta)))
        delta=raw-RADIUS_FLOOR_M
        radius=RADIUS_FLOOR_M+.5*(delta+np.hypot(delta,10.))
        ds=radius*12*np.pi*u*(1-u)+EASE_SCALE*np.exp(-EASE_RATE*min(u,1-u))
        return [ds*np.cos(theta),ds*np.sin(theta),ds]
    solution=solve_ivp(ode,(0,1),[0.,0.,0.],rtol=1e-9,atol=1e-9,dense_output=True,max_step=.002)
    u=np.linspace(0,1,4001)
    x,z,s=solution.sol(u)
    # Preserve the exact tie points and horizontal tangents of both existing roads.
    x *= (end[0]-begin[0])/x[-1]
    z -= z[-1]*np.square(s/s[-1])*(3-2*s/s[-1])
    planar=np.r_[0.,np.cumsum(np.hypot(np.diff(x),np.diff(z)))]
    u0=planar/planar[-1]
    drift=end[1]-begin[1]-slope*planar[-1]
    phase=2*np.pi*u0
    y=slope*planar + drift*(u0-np.sin(phase)/(2*np.pi))
    # Move the climbing and descending limbs apart without adding a bend at either tie.
    y+=4.8*np.sin(phase)*(np.cos(phase)-1.)
    path=np.array([x,y,z]).T+begin
    path[-1]=end
    chain=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))]
    ss=np.linspace(0,chain[-1],math.ceil(chain[-1]/.60)+1)
    stations=np.column_stack([np.interp(ss,chain,array) for array in path.T])
    vx,vz=np.gradient(stations[:,[0,2]],ss,axis=0).T
    norms=np.column_stack((-vz,np.zeros(len(vz)),vx))
    norms /= np.linalg.norm(norms,axis=1)[:,None]
    norms[[0,-1]]=[0,0,1]
    return stations,norms

def sections(points,normals,banks,width,shoulder):
    half=width/2
    return np.stack([points+[0,y,0]+(banks*d)[:,None]*normals for y,d in [
        (-half,shoulder),(-.62*half,0.),(.62*half,0.),(half,shoulder)]],axis=1)

def build(world):
    track=world.vaderland['vertical_loops'][0]
    source=np.asarray(track['stations'])
    oldnormal=np.asarray(track['normals'])
    lb=track['loop_in']
    rb=track['loop_out']
    loop,normal=loop_profile(track)
    points=np.vstack((source[:lb],loop,source[rb+1:]))
    normals=np.vstack((oldnormal[:lb],normal,oldnormal[rb+1:]))
    original_cross=np.asarray(track['cross_sections'])
    bank=np.clip(np.sum((original_cross[:,0]-source)*oldnormal,axis=1)/(.39*track['width_m']/2),0,1)
    banks=np.r_[bank[:lb],np.ones(len(loop)),bank[rb+1:]]
    cross=sections(points,normals,banks,track['width_m'],SHOULDER_RISE_M)
    m=Masonry()
    # Adjacent convex slabs share the same section exactly at every joint.
    for i in range(len(points)-1):
        for j in range(3):
            hull=[]
            for k in (i,i+1):
                for vertex in cross[k,j:j+2]:
                    hull.extend((vertex,vertex-.75*normals[k]))
            m.hull(f'vertical-loop-full-deck-{i:04d}-{j}',hull,
                   'loopBed' if j==1 else 'loopBank')
            m.solids[-1]['role']='deck'
    gate=int(np.argmin(abs(points[:,0]-(points[0,0]+82.))))
    sign=LEGACY['fittings'](m,world,'full',points,loop,normal,track['width_m'],points[gate])
    result=dict(track,sign=sign,stations=points.round(6).tolist(),normals=normals.round(7).tolist(),
                cross_sections=cross.round(5).tolist(),loop_out=lb+len(loop)-1,
                loop_length_m=float(np.linalg.norm(np.diff(loop,axis=0),axis=1).sum()),
                height_m=float(loop[:,2].max()-loop[0,2]),nominal_entry_kph=REFERENCE_MPS*3.6)
    peak_i=int(np.argmax(loop[:,2]))
    dxz=np.diff(loop[:,[0,2]],axis=0)
    theta=np.unwrap(np.arctan2(dxz[:,1],dxz[:,0]))
    radius=np.linalg.norm(dxz[peak_i-1:peak_i+1],axis=1).mean()/(theta[peak_i]-theta[peak_i-1])
    result['crown_radius_m']=float(radius)
    middle=(loop[0,0]+loop[-1,0])/2
    first=int(np.argmin(abs(loop[:peak_i,0]-middle)))
    second=peak_i+int(np.argmin(abs(loop[peak_i:,0]-loop[first,0])))
    result['projected_crossover_edge_gap_m']=float(loop[second,1]-loop[first,1]-track['width_m'])
    route={**next(r for r in world.vaderland['routes'] if r['name']==track['name']),
           'points':points[:-1:3,:2].round(5).tolist()+[points[-1,:2].round(5).tolist()]}
    return dict(track=result,route=route,solids=m.solids)

if __name__ == '__main__':
    world = make_world('vaderland-29')
    design = build(world)
    track = design['track']
    envelope = tuple(np.asarray(track[k]) for k in ('stations','cross_sections','normals'))
    nearby = [o for o in world.obstacles if not o['id'].startswith('vertical-loop-full-')
              and 3620 < o['center'][0] < 4550 and -4310 < o['center'][1] < -4000]
    LEGACY['check_clearance'](design['solids'] + nearby, {'full': envelope})
    if track['projected_crossover_edge_gap_m'] < 3.:
        raise ValueError('Climbing and descending deck edges have less than 3 m plan clearance')
    payload = json.dumps(design,separators=(',',':'),allow_nan=False).encode()
    target = PACK / 'grand-loop-30.json.gz'
    target.write_bytes(gzip.compress(payload,mtime=0))
    print({k: round(track[k],3) for k in ('loop_length_m','height_m','crown_radius_m','projected_crossover_edge_gap_m')})
