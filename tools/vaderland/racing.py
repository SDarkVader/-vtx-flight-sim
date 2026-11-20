"""Survey directed timing lines along a physically connected lap."""
import numpy as np


def course(world,name,road,return_road,stations):
    loop=np.array(road['points'],dtype=float)
    b=np.array(return_road['points']);a=int(np.argmin(np.linalg.norm(b-loop[-1],axis=1)));c=int(np.argmin(np.linalg.norm(b-loop[0],axis=1)))
    if np.linalg.norm(b[0]-b[-1])<.01:
        left=b[a:c+1] if a<=c else np.vstack([b[a:],b[1:c+1]])
        right=(b[c:a+1] if c<=a else np.vstack([b[c:],b[1:a+1]]))[::-1]
        tail=min([left,right],key=len)
    else:
        tail=b[(b[:,1]>min(loop[0,1],loop[-1,1]))&(b[:,1]<max(loop[0,1],loop[-1,1]))]
        if loop[-1,1]>loop[0,1]:tail=tail[::-1]
    xy=np.vstack([loop,tail,loop[:1]]);xy=xy[np.r_[True,np.linalg.norm(np.diff(xy,axis=0),axis=1)>.001]]
    dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    def at(s):return np.array([np.interp(s,dist,xy[:,j]) for j in (0,1)])
    gates=[]
    for fraction in stations:
        s=dist[-1]*fraction;p=at(s);d=at(s+1)-at(s-1);d/=np.linalg.norm(d)
        gates.append(dict(center=[*p.round(4),round(world.terrain_z(*p),3)],normal=d.round(7).tolist(),width_m=road['width_m']))
    return dict(name=name,length_m=round(dist[-1],2),gates=gates)
