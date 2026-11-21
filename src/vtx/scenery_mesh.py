"""Static convex architecture authored by the environment, in world metres."""
import math
from xml.etree import ElementTree as ET

import numpy as np


def add_static_mesh(asset, worldbody, obstacle, **contact):
    name='scenery-'+obstacle['id']
    vertices=' '.join(str(value) for vertex in obstacle['vertices'] for value in vertex)
    faces=' '.join(str(value) for face in obstacle['faces'] for value in face)
    ET.SubElement(asset,'mesh',name=name,vertex=vertices,face=faces)
    if 'friction' in obstacle and 'friction' not in contact:
        # A wet ramp is slicker than a hull; MuJoCo otherwise takes the larger of the two frictions.
        contact=dict(contact,friction=f"{float(obstacle['friction'])} 0.005 0.0001",priority='1')
    if 'solref' in obstacle and 'solref' not in contact:
        # A floating, anchored ramp gives under a hull; a stiffer contact would be a 16 g wall strike.
        contact=dict(contact,solref=' '.join(str(float(v)) for v in obstacle['solref']),priority='1')
    position=obstacle['center']
    parent=worldbody
    if motion:=obstacle.get('motion'):
        key='environment-'+motion['name']
        parent=worldbody.find(f"body[@name='{key}']")
        if parent is None:
            parent=ET.SubElement(worldbody,'body',name=key,mocap='true',pos=' '.join(map(str,motion['origin'])))
        position=[p-q for p,q in zip(position,motion['origin'])]
        contact['mass']='0'
    ET.SubElement(parent,'geom',type='mesh',mesh=name,pos=' '.join(map(str,position)),**contact)


def finish_scenery(root,worldbody):
    bodies=[b for b in worldbody.findall('body') if b.get('mocap')=='true' and b.get('name','').startswith('environment-')]
    if not bodies:return
    # Preserve the original vehicle body order, joint addresses and zero-inertia scenery.
    for b in bodies:worldbody.remove(b);worldbody.append(b)
    size=root.find('size')
    if size is None:size=ET.SubElement(root,'size')
    size.set('nuserdata','6')


class MovingScenery:
    """World-owned kinematics. Native integration state preserves door targets and travel on resume."""
    def __init__(self,model,data,world):
        specs={o['motion']['name']:o['motion'] for o in world.obstacles if 'motion' in o}
        parts=[(model.body_mocapid[model.body('environment-'+name).id],s) for name,s in specs.items()]
        self.parts=[(i,s) for i,s in parts if not s.get('walk')]
        walkers=[(i,s) for i,s in parts if s.get('walk')]
        self.pedestrians=None
        if walkers:
            ids,people=zip(*walkers)
            self.pedestrians=(np.asarray(ids),np.asarray([p['center'] for p in people]),
                np.asarray([p['a'] for p in people]),np.asarray([p['b'] for p in people]),
                np.asarray([p['phase'] for p in people]),math.tau/np.asarray([p['period_s'] for p in people]),
                np.asarray([p['heights'] for p in people]),np.arange(len(ids)))
        self.apply(data)

    def doors(self,data):
        return {name:1-self.closure(data,i) for i,name in enumerate(('west','east'))}

    def closure(self,d,index):
        start,target,stamp=d.userdata[3*index:3*index+3]
        travel=min(abs(target-start),max(0.,(d.time-stamp)/4))
        return start+math.copysign(travel,target-start)

    def command(self,d,door,opened,snap=False):
        i=('west','east').index(door);target=0. if opened else 1.
        current=self.closure(d,i)
        d.userdata[3*i:3*i+3]=[target if snap else current,target,d.time]
        self.apply(d)

    def apply(self,d,scene_time=None):
        t=float(d.time if scene_time is None else scene_time);doors=self.doors(d);orbit=None
        if self.pedestrians is not None:
            ids,center,a,b,phase,rates,levels,rows=self.pedestrians
            theta=phase+t*rates
            co=np.cos(theta)[:,None];si=np.sin(theta)[:,None]
            d.mocap_pos[ids,:2]=center+a*co+b*si
            u=(theta/math.tau%1)*levels.shape[1];k=u.astype(int);f=u-k
            d.mocap_pos[ids,2]=levels[rows,k]*(1-f)+levels[rows,(k+1)%levels.shape[1]]*f
            direction=-a*si+b*co
            yaw=np.arctan2(direction[:,1],direction[:,0])*.5
            d.mocap_quat[ids,0]=np.cos(yaw)
            d.mocap_quat[ids,3]=np.sin(yaw)
        for i,s in self.parts:
            if 'door' in s:
                a=s['travel_rad']*doors[s['door']]/2
                d.mocap_quat[i]=[math.cos(a),math.sin(a),0.,0.]
            elif 'orbit' in s:
                if orbit is None:
                    cx,cy,rx,ry=s['orbit'];phase=math.tau*t/s['period_s'];co,si=math.cos(phase),math.sin(phase)
                    yaw=math.atan2(ry*co,-rx*si)-math.pi/2
                    orbit=(cx+rx*co,cy+ry*si,math.cos(yaw),math.sin(yaw),math.cos(yaw/2),math.sin(yaw/2),math.sin(s['strides']*phase))
                x,y,c,sn,cq,sq,gait=orbit;ox,oy,z=s['origin'];dx=ox-s['root'][0];dy=oy-s['root'][1]
                d.mocap_pos[i]=[x+c*dx-sn*dy,y+sn*dx+c*dy,z]
                tilt=s['swing_rad']*gait/2;ct,st=math.cos(tilt),math.sin(tilt)
                d.mocap_quat[i]=[cq*ct,cq*st,sq*st,sq*ct]
            else:
                a=math.pi*t/s['period_s'];d.mocap_quat[i]=[math.cos(a),0.,0.,math.sin(a)]


def native_scenery(model,data,world):
    return MovingScenery(model,data,world) if model.nmocap else None
