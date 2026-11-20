"""Author convex scenery in metres. Triangles and support planes are shared by Blender and MuJoCo."""
import math
import numpy as np
from scipy.spatial import ConvexHull


class Masonry:
    def __init__(self):
        self.solids=[]

    def hull(self,name,points,skin,*,parent=None,**attrs):
        points=np.unique(np.round(np.asarray(points,dtype=float),5),axis=0)
        shell=ConvexHull(points)
        points=points[shell.vertices]
        low=points.min(axis=0);high=points.max(axis=0);center=(high+low)/2
        vertices=(points-center).round(6);shell=ConvexHull(vertices)
        faces=[]
        for (a,b,c),plane in zip(shell.simplices,shell.equations):
            if np.dot(np.cross(vertices[b]-vertices[a],vertices[c]-vertices[a]),plane[:3])<0:b,c=c,b
            faces.append([int(a),int(b),int(c)])
        obj=dict(id=name,kind='mesh',role='architecture',color='#40505a',finish='shell',
             landable=attrs.pop('landable',False),skin=skin,center=center.round(6).tolist(),half=((high-low)/2).round(6).tolist(),
             vertices=vertices.tolist(),faces=faces,planes=np.unique(shell.equations.round(9),axis=0).tolist(),**attrs)
        if parent:obj.update(support='joint',parent=parent)
        self.solids.append(obj)
        return name

    def rings(self,name,levels,skin,n=33,**attrs):
        # Each level is centre X/Y, two radii, height and optional azimuth.
        pts=[]
        for x,y,a,b,z,*phase in levels:
            ang=phase[0] if phase else 0
            for i in range(n):
                t=(i+.23)*math.tau/n
                u=a*math.cos(t);v=b*math.sin(t)
                pts.append([x+u*math.cos(ang)-v*math.sin(ang),y+u*math.sin(ang)+v*math.cos(ang),z])
        return self.hull(name,pts,skin,**attrs)

    def box(self,name,x,y,z1,z2,a,b,skin,**attrs):
        return self.hull(name,[[x+i*a,y+j*b,z] for i in (-1,1) for j in (-1,1) for z in (z1,z2)],skin,**attrs)
