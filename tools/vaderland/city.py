"""Lay out the airport forecourt and the connected northern city terrace."""
import json
from pathlib import Path
import sys
import numpy as np
from scipy.ndimage import gaussian_filter

from bake import AXIS, HALF, PACK, ROOT, STEP, X, Y, smooth, landscape_light
sys.path.insert(0,str(ROOT/'src'))
from vtx.world import TestWorld


def build(terrain=None):
    if terrain is None:terrain=np.load(PACK/'geography-01.npz')['height_dm']
    z=terrain.astype(float)/10
    xs=[-3100,-2640,-2200,-1690,-1200,-770,-390,0,400,830,1260,1680,2200,2640,2900]
    ys=[640,1040,1400,1770,2130,2520,2900,3310,3760,4230,4670,5120,5580]
    # The mountain wards climb the foothill. Smoothing the existing terrace
    # suppresses local spikes without cutting hundreds of metres out of the rim.
    grade=gaussian_filter(z,10)
    blend=(1-smooth(0,200,np.maximum.reduce([xs[0]-X,X-xs[-1],ys[0]-Y,Y-ys[-1]])))
    z+=(grade-z)*blend
    z=np.rint(z*10)/10
    survey=object.__new__(TestWorld)
    survey.heights=z;survey.n=len(z);survey.half=HALF
    features,roads,places=[],[],[]
    def warp(x,y):
        # Follow the north terrace around the skirts of both massifs. Streets
        # straighten through the financial centre and bend out towards the rim.
        t=float(smooth(850,4930,y))
        outer=min(1,abs(x)/3000)
        return [round(x+t*(1-outer)*180*np.sin(y/660+x/900),2),
                round(y+t*(90*np.sin(x/500)-650*outer**1.6),2)]
    def terrace_street(x0,y0,x1,y1):
        n=int(np.ceil(np.hypot(x1-x0,y1-y0)/80))+1
        return [warp(x,y) for x,y in zip(np.linspace(x0,x1,n),np.linspace(y0,y1,n))]
    def road(name,width,points,kind='street'):
        roads.append(dict(name=name,width_m=width,points=points,kind=kind))
    for i,x in enumerate(xs):
        road('Meridian Avenue' if x==0 else f'North street {i+1}',70 if x==0 else 46 if i%4==0 else 25,
             terrace_street(x,ys[0],x,ys[-1 if i%3!=1 else -2]))
    for j,y in enumerate(ys):
        left=xs[1] if j>=9 and j%2 else xs[0]
        right=xs[-2] if j>=7 and j%2 else xs[-1]
        road('Exchange Boulevard' if j==5 else f'Terrace {j+1}',58 if j in (2,5,9) else 27,
             terrace_street(left,y,right,y))
    for x in [-1200,0,1260]:
        road('Airfield north access',30,[[x,40],[x,ys[0]]])
    road('Forecourt approach',22,[[-600,-83],[-600,-302],[-340,-302],[-165,-270],[-110,-252]])
    def ground_range(x,y,a,b):
        i0,i1=np.searchsorted(AXIS,[x-a,x+a])
        j0,j1=np.searchsorted(AXIS,[y-b,y+b])
        samples=[survey.terrain_z(u,v) for u in (x-a,x+a) for v in (y-b,y+b)]
        if i0<i1 and j0<j1:
            samples.extend([z[j0:j1,i0:i1].min(),z[j0:j1,i0:i1].max()])
        return min(samples),max(samples)
    def mass(name,x,y,a,b,height,style,*,kind='box',base=None,parent=None,landable=True):
        low,high=ground_range(x,y,a,b)
        bottom,top=(low-.6,high+height) if base is None else (base-.15,base+height)
        feature=dict(id=name,kind=kind,center=[round(x,2),round(y,2),round((bottom+top)/2,3)],
           half=[round(a,2),round(b,2),round((top-bottom)/2,3)],color=style,role='architecture',landable=landable)
        if parent:feature.update(support='stack',parent=parent)
        features.append(feature)
        return top
    rng=np.random.default_rng(7211)
    tones=['#34454e','#384351','#4b4b4e','#45565b','#524d46','#424e56','#375055']
    for i,(west,east) in enumerate(zip(xs,xs[1:])):
        for j,(south,north) in enumerate(zip(ys,ys[1:])):
            cx,cy=(west+east)/2,(north+south)/2
            core=np.exp(-((cx+180)/1250)**2-((cy-2400)/1350)**2)
            if (i*7+j*3)%13==0:continue   # parks and breaks in the roofline
            for k,(fx,fy) in enumerate([(0.30,.30),(.69,.64),(.30,.73)]):
                if k==2 and (core<.15 or (i+j)%3==0):continue
                x=west+(east-west)*fx+rng.uniform(-10,10)
                y=south+(north-south)*fy+rng.uniform(-10,10)
                if j>=10 and (i in (0,1,12,13) or (i+j+k)%3!=0):continue
                x,y=warp(x,y)
                a,b=rng.uniform(16,45),rng.uniform(17,41)
                height=5+rng.uniform(3,16)+core*rng.uniform(38,200)
                ident=f'ward-{i:02}-{j:02}-{k}'
                palette=rng.choice(tones)
                rounded=(i+2*j+k)%5==0
                kind='cylinder' if rounded else 'box'
                if rounded:b=a
                # Real podiums, stepped shoulders and different roof heights
                # give each ward depth at street level as well as on the horizon.
                top=mass(ident,x,y,a,b,min(13,height*.35),palette,kind=kind)
                shift=0 if rounded else a*.13
                top=mass(ident+'-body',x+shift,y,a*.73,b*.74,height,palette,
                         kind=kind,base=top,parent=ident)
                if height>52:
                    mass(ident+'-crown',x+shift,y,a*.48,b*.51,6+height*.19,'#535c63',
                         kind=kind,base=top,parent=ident+'-body')
                elif not rounded and (i+j)%3==0:
                    mass(ident+'-loft',x+shift,y+b*.24,a*.61,b*.26,4.3,'#47545a',
                         base=top,parent=ident+'-body')
    # The primary landmarks are metric stacks of ordinary architectural solids.
    # The crown, narrow spine and rooftop markings all have supporting mass.
    for i,(x,y,h) in enumerate([(-90,2280,289),(96,2300,257)]):
        name=f'exchange-{i+1}'
        top=mass(name,x,y,38,49,h,'#233745')
        top=mass(name+'-shoulder',x,y,24,35,38,'#52616b',base=top,parent=name)
        mass(name+'-spire',x+8,y,6,7,37,'#bb9152',base=top,parent=name+'-shoulder',landable=False)
    top=mass('airport-rotunda',0,-300,86,86,26,'#2e404a',kind='cylinder')
    top=mass('airport-rotunda-drum',0,-300,72,72,14,'#445663',kind='cylinder',base=top,parent='airport-rotunda')
    mass('airport-rotunda-crown',0,-300,59,59,6,'#263742',kind='cylinder',base=top,parent='airport-rotunda-drum')
    for side in (-1,1):
        mass(f'concourse-{side}',side*148,-310,64,27,14,'#43535c')
        mass(f'arrivals-{side}',side*230,-293,22,22,10,'#465660',kind='cylinder')
    mass('signal-tower',116,-235,8,8,63,'#4b5964',kind='cylinder')
    tower_top=next(o['center'][2]+o['half'][2] for o in features if o['id']=='signal-tower')
    mass('signal-tower-cab',116,-235,13,13,7,'#343445',kind='cylinder',base=tower_top,parent='signal-tower')
    places.extend([dict(name='Vaderland VTX',point=[0,-300]),dict(name='Meridian Exchange',point=[0,2280]),
                  dict(name='Crown Terrace',point=[-770,4670])])
    return z,dict(obstacles=features,routes=roads,places=places)


if __name__=='__main__':
    z,city=build()
    np.savez_compressed(PACK/'city-02.npz',height_dm=np.rint(z*10).astype('<u2'))
    landscape_light(np.rint(z*10),city['obstacles'],'relief-city.png')
    (PACK/'city-02.json').write_text(json.dumps(city,separators=(',',':'))+'\n',encoding='utf-8')
    print(len(city['obstacles']),'masses',len(city['routes']),'streets')
