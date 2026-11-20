"""Author the West Approach race gantry and trackside sound towers."""
import gzip
import json

import numpy as np

from drafting import Masonry
from streets import StreetIndex
from vtx.cathedral import CathedralOfVelocity
from vtx.vaderland import PACK


def make_approach(world):
    route=next(r for r in world.vaderland['routes'] if r['name']=='Gallery west approach')
    points=np.asarray(route['points'])
    approach=points[(points[:,0]>2710)&(points[:,1]<-4319)]
    masonry=Masonry()
    speakers=[]

    def frame(station):
        def position(x):
            return np.array([x,np.interp(x,approach[:,0],approach[:,1])])
        point=position(station)
        axis=position(station+.8)-position(station-.8)
        axis/=np.linalg.norm(axis)
        normal=np.array([-axis[1],axis[0]])
        return np.r_[point,world.terrain_z(*point)],axis,normal

    def point(frame,s,n,h):
        origin,axis,normal=frame
        return origin+np.r_[s*axis+n*normal,h]

    def block(key,base,s,n,h,skin,parent=None):
        cloud=[point(base,i,j,k) for i in s for j in n for k in h]
        return masonry.hull('cathedral-west-'+key,cloud,skin,parent=parent)

    def member(key,a,b,thick,skin,parent):
        axis=(b-a)/np.linalg.norm(b-a)
        right=np.cross(axis,[0.,0.,1.])
        if np.linalg.norm(right)<.01:
            right=np.array([1.,0.,0.])
        right*=thick/np.linalg.norm(right)
        face=np.cross(axis,right)
        cloud=[end+i*right+j*face for end in (a,b) for i in (-1,1) for j in (-1,1)]
        return masonry.hull('cathedral-west-'+key,cloud,skin,parent=parent)

    def side(sign,left,right):
        return tuple(sorted((sign*left,sign*right)))

    gate=frame(2817.)
    columns=[]
    for sign,label in ((-1,'south'),(1,'north')):
        a=block(label+'-coffer-base',gate,(-6,6),side(sign,15.65,21.4),(-.78,.63),'cathedralStone')
        b=block(label+'-coffer',gate,(-3.85,4.),side(sign,16.25,20.3),(.61,3.4),'cathedralIron',a)
        col=block(label+'-high-tower',gate,(-1.45,1.45),side(sign,17.4,19.1),(3.35,14.25),'cathedralIron',b)
        columns.append(col)
        for j,(s,extent) in enumerate(((-5.3,2.7),(5.25,2.5))):
            member(label+'-raking-strut-'+str(j),point(gate,s,sign*19.1,.62),
                   point(gate,0.,sign*18.25,9.9+extent),.33,'cathedralIron',a)
        for j in range(4):
            lower=2.8+j*2.25
            block(label+'-amber-pickup-'+str(j),gate,(-1.51,-1.42),side(sign,17.58,18.38),
                  (lower+1,lower+2.3),'cathedralAmber',col)
        block(label+'-tower-tip',gate,(-.65,.65),side(sign,17.86,18.78),(14.15,14.95),
              'cathedralViolet',col)
    spans=[]
    for i,h in enumerate((10.5,13.6)):
        spans.append(member('crossbeam-'+str(i),point(gate,0.,-18.25,h),point(gate,0.,18.25,h),.35,
                            'cathedralIron',columns[0]))
    for j in range(10):
        a=-18.1+j*3.62
        member(f'truss-{j}',point(gate,0.,a,10.64+2.82*(j%2)),
               point(gate,0.,a+3.62,13.46-2.82*(j%2)),.19,'cathedralIron',spans[0])
        block(f'truss-pilot-{j}',gate,(-.38,-.29),(a+.50,a+2.9),(10.36,10.53),
              'cathedralAmber' if j in (0,1,8,9) else 'cathedralViolet',spans[0])
    placard=block('name-board',gate,(-.91,.02),(-8.08,8.08),(10.8,13.28),'cathedralIron',spans[0])
    name_board=point(gate,-1.17,0.,12.035).tolist()

    for i,(station,sign) in enumerate(((2756.,-1),(2779.,1),(2819.,1),(2840.,-1),(2880.,1))):
        base=frame(station)
        label=f'pa-{i}'
        foundation=block(label+'-foot',base,(-2.2,2.2),side(sign,22,26.1),(-1.08,.50),'cathedralStone')
        post=block(label+'-post',base,(-.52,.53),side(sign,23.31,24.4),(.47,5.97),'cathedralIron',foundation)
        case=block(label+'-cabinet',base,(-1.04,1.04),side(sign,22.95,24.73),(4.13,6.34),'cathedralIron',post)
        block(label+'-grille',base,(-.91,.91),side(sign,22.89,23.08),(4.23,6.23),'cathedralSpeaker',case)
        glow='cathedralAmber' if sign<0 else 'cathedralViolet'
        block(label+'-pilot',base,(-.78,.78),side(sign,22.84,23.01),(4.25,4.36),glow,case)
        speakers.append({'id':f'west-pa-{i}', 'position':point(base,0,sign*22.94,5.23).tolist(),
                         'direction':(-sign*base[2]).tolist(), 'channel':i%2})

        lane_side=side(sign,12.4,13.45)
        end=block(label+'-marker-base',base,(-.78,.78),lane_side,(-.4,.22),'cathedralStone')
        marker=block(label+'-marker',base,(-.57,.57),lane_side,(.20,1.86),'cathedralIron',end)
        block(label+'-lane-beacon',base,(-.624,-.54),side(sign,12.53,13.31),(1.34,1.69),glow,marker)

    streets=StreetIndex(world,[route])
    intruders={o['id']:hit for o in masonry.solids if (hit:=streets.overlaps(o,headroom=6.6))}
    if intruders:
        raise ValueError(intruders)
    return {'solids':masonry.solids,'approach':{'sign':name_board,
            'normal':gate[1].tolist(),'gantry':placard,'speakers':speakers}}


if __name__=='__main__':
    design=make_approach(CathedralOfVelocity())
    raw=json.dumps(design,separators=(',',':'),allow_nan=False).encode()
    (PACK/'cathedral-approach-24.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    print(len(design['solids']), 'surveyed approach hulls')
