"""Lay out Aviator Plaza and its actual avenue block, tower frontages and loop."""
import json,math
import numpy as np
from bake import PACK,landscape_light
from drafting import Masonry
from aviator import statue
from airfield import curve
from streets import StreetIndex
from vtx.vaderland import MeridianOperations


def build():
    w=MeridianOperations();m=Masonry();cx,cy=-183.,2325.;z=31.2
    roads={r['name']:r for r in w.vaderland['routes']}
    def onroad(name,y):
        q=np.array(roads[name]['points']);return [float(np.interp(y,q[:,1],q[:,0])),y]
    east1=onroad('Meridian Avenue',2246);east2=onroad('Meridian Avenue',2402)
    west1=onroad('North street 7',2246);west2=onroad('North street 7',2402)
    loop=[east1,[-247,2246]]+curve([-247,2246],[-292,2246],[-306,2257],[-306,2290])[1:]
    loop+=[[-306,2363]]+curve([-306,2363],[-306,2391],[-285,2402],[-254,2402])[1:]+[east2]
    rlist=[dict(name='Aviator Plaza Circuit',kind='street',width_m=13.,points=loop),
           dict(name='Exchange market street',kind='street',width_m=10.,points=[west1,[-305,2246],[-242,2246]]),
           dict(name='Archive street',kind='street',width_m=10.,points=[west2,[-310,2402],[-248,2402]])]
    bank=[]
    for row,y in enumerate(np.linspace(-8000,8000,w.n)):
        if abs(y-cy)>200:continue
        for col,x in enumerate(np.linspace(-8000,8000,w.n)):
            dist=max(0,abs(x-cx)-117,abs(y-cy)-74)
            if dist>=51:continue
            blend=max(0,1-dist/51);blend*=blend*(3-2*blend)
            h=round(float(w.heights[row,col]+blend*(z-w.heights[row,col])),2)
            if abs(h-w.heights[row,col])>.001:w.heights[row,col]=h;bank.append([row,col,h])
    def terrace(name,x,y,a,b):
        return min(w.terrain_z(x+u,y+v) for u in (-a,0,a) for v in (-b,0,b))-.48
    base=m.rings('plaza-compass',[(cx,cy,23,23,z-.22),(cx,cy,23.15,23.15,z+.14),(cx,cy,22.85,22.85,z+.32)],'pavestone',65)
    parent=base
    for j in range(4):
        r=18.6-j*1.25
        parent=m.rings('civic-dais-'+str(j),[(cx,cy,r,r,z+.30+j*.41),(cx,cy,r-.2,r-.2,z+.74+j*.41)],'sandstone',49,parent=parent)
    plinth=m.rings('civic-monument',[(cx,cy,10.1,10.1,z+1.95),(cx,cy,9,9,z+3.1),
        (cx,cy,7.20,7.2,z+9.45),(cx,cy,7.6,7.6,z+10.0)],'basalt',17,parent=parent)
    bearing=m.rings('civic-turntable',[(cx,cy,8.3,8.3,z+9.96),(cx,cy,8.65,8.65,z+10.42),
             (cx,cy,8.2,8.2,z+10.67)],'brightbronze',49,parent=plinth)
    monument=statue(m,cx,cy,z+10.67)
    # Six real families of commercial and civic towers, set on surveyed frontages.
    towers=[(-110,2442,27,24,279,'twist'),(-269,2438,27,22,182,'lantern'),(104,2301,35,44,354,'exchange'),
            (246,2360,40,32,235,'sail'),(126,2207,23,22,163,'flute'),(306,2442,22,25,196,'twist'),
            (-132,2180,24,23,167,'sail'),(-266,2182,29,25,149,'flute'),(-505,2337,32,34,199,'lantern'),
            (-552,2400,32,32,170,'sail'),(257,2191,22,20,143,'lantern'),(311,2262,17,21,126,'flute')]
    bounds=[]
    for k,(x,y,a,b,h,style) in enumerate(towers):
        g=terrace('tower',x,y,a+4,b+4);name='meridian-'+style+'-'+str(k)
        bounds.append((x,y,a+7,b+7))
        n={'twist':8,'sail':7,'exchange':8,'lantern':25,'flute':17}[style]
        def level(t):
            width={'twist':1-.39*t,'sail':1-.64*t,'exchange':1-.60*t,'lantern':.88+.17*math.sin(math.pi*t)-.31*t,'flute':1-.55*t}[style]
            return (x+(a*.40*t*t if style=='sail' else 0),y,a*width,b*width,
                    g+10.7+h*t,(.04+.70*t if style=='twist' else .18 if style=='exchange' else .02))
        podium=m.rings(name+'-arcade',[(x,y,a+3,b+4,g),(x,y,a+5,b+5,g+2.2),
                 (x,y,a+4,b+4,g+9.9),(x,y,a+3,b+3,g+10.75)],'store',n,landable=True)
        tiers=8 if style=='twist' else 5 if style=='lantern' else 3
        p=podium
        for j in range(tiers):
            p=m.rings(name+'-floor-'+str(j),[level(j/tiers),level((j+1)/tiers)],style,n,parent=p,landable=True)
        if style=='exchange':
            for sign in (-1,1):
                q=g+h+10.65
                m.hull(name+'-v-fin-'+str(sign),[[x+sign*u,y+v,height] for u,v,height in
                     [(0,-8,q),(0,8,q),(a*.36,-9,q),(a*.36,9,q),(a*.18,-5,q+31),
                      (a*.18,5,q+31),(a*.72,-3,q+53),(a*.72,3,q+53)]],'gold',parent=p)
        if style=='lantern':
            end=level(1)
            m.rings(name+'-beacon',[(x,y,end[2]*.80,end[3]*.80,end[4]-.02),(x,y,end[2]*.80,end[3]*.80,end[4]+7),
                    (x,y,end[2]*.70,end[3]*.70,end[4]+9)],'beacon',n,parent=p)
    # Open arcades on the north of the square, with four public-facing doors and separate footways.
    for j,label in enumerate(('Archive','Exchange','Market','Observatory')):
        x=-263+j*46;y=2382
        g=terrace(label,x,y,15,8)
        m.box('plaza-shop-'+label,x,y,g,g+8.2,16.4,6.5,'store')
        for s in [-1,1]:
            m.rings('plaza-arcade-'+label+str(s),[(x+s*14.6,y-10,.4,.4,g-.1),(x+s*14.6,y-10,.38,.38,g+5.15)],
                    'brightbronze',13)
        m.box('plaza-canopy-'+label,x,y-7.4,g+4.92,g+5.30,16.3,3.1,'walnut',parent='plaza-shop-'+label)
    for j,(x,y) in enumerate([(-265,2284),(-239,2280),(-128,2280),(-102,2284),(-258,2357),(-109,2357)]):
        footing=m.rings('plaza-planter-'+str(j),[(x,y,4.3,3.35,z-.10),(x,y,4.45,3.48,z+.36),(x,y,4.2,3.3,z+.57)],'pavestone',27)
        m.solids.append(dict(id='plaza-linden-'+str(j),kind='cylinder',center=[x,y,z+5.62],half=[.25,.25,5.10],
            support='joint',parent=footing,role='conifer',crown_radius_m=3.6,finish='fir',species=1,color='#495f40',landable=False))
        for side in (-1,1):
            bx=x+side*5.8
            foot=m.box(f'plaza-seat-base-{j}-{side}',bx,y,z-.10,z+.37,.34,1.5,'basalt')
            m.box(f'plaza-bench-{j}-{side}',bx,y,z+.34,z+.50,.50,2.08,'walnut',parent=foot)
    remove=set()
    for o in w.obstacles:
        x,y,_=o['center'];a,b,_=o['half']
        if abs(x-cx)<131+a and abs(y-cy)<90+b and o.get('role')=='architecture':remove.add(o['id'])
        if o['id'].startswith('exchange-') or o['id'].startswith(('ward-06-04','ward-07-04')):remove.add(o['id'])
        if o.get('role')=='architecture' and any(abs(x-p)<a+u and abs(y-q)<b+v for p,q,u,v in bounds):remove.add(o['id'])
    # Dependent storeys of old podiums are removed with their foundations.
    for o in w.obstacles:
        if o.get('parent') in remove:remove.add(o['id'])
    allroads=StreetIndex(w,rlist)
    for o in w.obstacles:
        x,y,_=o['center'];rad=o.get('crown_radius_m',o['half'][0])
        if (o.get('role') in ('conifer',None) and o['kind']=='cylinder' and -620<x<410 and 2100<y<2540 and
          (abs(x-cx)<132+rad and abs(y-cy)<86+rad or allroads.overlaps(o,margin=1.2) or
           any(abs(x-p)<u+rad and abs(y-q)<v+rad for p,q,u,v in bounds))):remove.add(o['id'])
    from racing import course
    trial=course(w,'Aviator Plaza',rlist[0],roads['Meridian Avenue'],[.09,.36,.61,.83])
    data=dict(removed=sorted(remove),solids=m.solids,bank=bank,routes=rlist,civic=dict(plaza=[cx,cy,z],
        size_m=[213,134],course=trial,towers=[dict(x=t[0],y=t[1],style=t[-1]) for t in towers],statue=monument))
    (PACK/'civic-13.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    landscape_light(np.rint(w.heights*10),[o for o in w.obstacles if o['id'] not in remove]+m.solids,'relief-civic.png')
    print('land',len(bank),'removed',len(remove),'physical features',len(m.solids))
if __name__=='__main__':build()
