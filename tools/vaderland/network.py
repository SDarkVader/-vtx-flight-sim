"""Survey the two perimeter roads, coastal viaduct, canyon, circuit and proving field."""
import json
import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree

from bake import AXIS, HALF, PACK, STEP, X, Y, grid_water, smooth, landscape_light
from city import TestWorld


def samples(controls,interval=8):
    control=np.asarray(controls,dtype=float)
    s=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(control,axis=0),axis=1))]
    uv=np.linspace(0,s[-1],int(np.ceil(s[-1]/interval))+1)
    xy=CubicSpline(s,control,bc_type='natural')(uv)
    return xy,np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]


def build(terrain=None,city=None,refine=False):
    world=object.__new__(TestWorld)
    if terrain is None:terrain=np.load(PACK/'city-02.npz')['height_dm']
    world.heights=terrain.astype(float)/10
    world.n=len(AXIS);world.half=HALF
    z=world.heights
    chart=json.loads((PACK/'coast-01.json').read_text())
    wet=grid_water(chart)
    routes=[];objects=[];places=[];streams=[];spans=[]
    def cut(xy,profile,width,transition):
        margin=width/2+transition+2*STEP
        low,high=xy.min(axis=0)-margin,xy.max(axis=0)+margin
        i0,j0=np.searchsorted(AXIS,low)
        i1,j1=np.searchsorted(AXIS,high)
        xx,yy=X[j0:j1,i0:i1],Y[j0:j1,i0:i1]
        distance,index=cKDTree(xy).query(np.column_stack((xx.ravel(),yy.ravel())))
        distance,index=distance.reshape(xx.shape),index.reshape(xx.shape)
        blend=1-smooth(width/2,width/2+transition,distance)
        sub=z[j0:j1,i0:i1]
        sub+=(profile[index]-sub)*blend
    def street(name,controls,width=22,kind='arterial',start=None,end=None):
        xy,s=samples(controls)
        h=gaussian_filter1d([world.terrain_z(x,y) for x,y in xy],18,mode='nearest')
        for target,distance in [(start,s),(end,s[-1]-s)]:
            if target is not None:h+=(target-h)*(1-smooth(0,420,distance))
        # Profiles are measured in metres of chainage, not map-grid indices.
        grade_limit=.18 if refine and kind=='track' else .095
        for i in range(1,len(h)):h[i]=np.clip(h[i],h[i-1]-grade_limit*(s[i]-s[i-1]),h[i-1]+grade_limit*(s[i]-s[i-1]))
        if end is not None:
            h[-1]=end
            for i in range(len(h)-2,-1,-1):h[i]=np.clip(h[i],h[i+1]-grade_limit*(s[i+1]-s[i]),h[i+1]+grade_limit*(s[i+1]-s[i]))
        h[np.abs(xy[:,1])<510]=0
        cut(xy,h,width+24,140 if refine else 65)
        routes.append(dict(name=name,kind=kind,width_m=width,points=np.round(xy,2).tolist()))
        return xy,s
    def solid(name,kind,x,y,a,b,bottom,top,role,**kwargs):
        o=dict(id=name,kind=kind,center=[round(x,3),round(y,3),round((top+bottom)/2,4)],
               half=[round(a,3),round(b,3),round((top-bottom)/2,4)],color='#635f61',
               landable=role=='deck',role=role,**kwargs)
        objects.append(o);return o
    def support(name,x,y,r,top,role='pier'):
        floor=min(world.terrain_z(x+u,y+v) for u,v in [(0,0),(r,0),(-r,0),(0,r),(0,-r)])
        return solid(name,'cylinder',x,y,r,r,floor-2,top,role)
    def viaduct(name,controls,width,top):
        xy,s=samples(controls,interval=4)
        thickness=2.8
        # Overlapping round deck units describe the actual swept road volume.
        # No angled boxes or decorative span over a solid heightfield.
        for i,(x,y) in enumerate(xy):
            solid(f'{name}-deck-{i}','cylinder',x,y,width/2,width/2,top-thickness,top,'deck',support='span',span=name)
        stations=np.linspace(0,s[-1],int(np.ceil(s[-1]/66))+1)
        piers=[]
        for i,station in enumerate(stations):
            x,y=xy[np.argmin(abs(s-station))]
            if world.terrain_z(x,y)<top-thickness-.4:
                pier=support(f'{name}-pier-{i}',x,y,3.4,top-thickness+.2)
                piers.append(pier['id'])
        routes.append(dict(name=name,kind='viaduct',width_m=width-1,deck_z_m=top,points=np.round(xy[::3],2).tolist()+
                           ([np.round(xy[-1],2).tolist()] if (len(xy)-1)%3 else [])))
        spans.append(dict(name=name,piers=piers,max_station_spacing_m=float(np.max(np.diff(stations))),top_m=top))
    # Two genuinely separate perimeter crossings of the airport's extended
    # centreline. The approaches stay unobstructed, including the pavement.
    street('East perimeter',[(2900,1040),(3660,1030),(4320,840),(4610,380),(4650,-270),
                   (4380,-790),(3560,-1160),(2680,-1590),(2310,-2200),(2210,-2840),(2590,-3340),(3260,-3650)])
    street('West perimeter',[(-3100,1400),(-4000,1440),(-4610,960),(-4830,410),(-4800,-240),
                  (-4530,-740),(-3760,-980),(-2920,-900),(-2200,-665),(-1700,-750)],end=55)
    street('Terminal shore road',[(-600,-83),(-870,-175),(-1300,-350),(-1550,-520),(-1700,-750)],end=55)
    viaduct('Sound crossing',[(-1700,-750),(-1810,-1150),(-2100,-1610),(-2210,-2060),
                   (-2010,-2520),(-1690,-2830),(-1500,-3200)],21,55)
    street('South shore road',[(-1500,-3200),(-1130,-3270),(-560,-3110),(120,-3160),
                   (840,-3370),(1650,-3440),(2490,-3330),(3260,-3650)],start=55)
    street('Airport landing road',[(-600,-83),(-370,-245),(0,-449),(190,-510),(205,-550)],width=14)
    # The circuit is founded on the southeastern bench. Its long timing straight
    # feeds a broad rising arc and a progressively tighter pair of return bends.
    street('Sunset circuit',[(3260,-3650),(3980,-3650),(5150,-3650),(6030,-3640),
           (6550,-3480),(6890,-3070),(6900,-2620),(6700,-2280),(6280,-2150),
           (5870,-2300),(5620,-2580),(5300,-2510),(5020,-2180),(4720,-2110),
           (4480,-2330),(4540,-2690),(4340,-2990),(3900,-3090),(3480,-3260),(3260,-3650)],26,'express')
    # A level 600 m cut-and-cover gallery with two open ends. The terrain is
    # excavated down to carriageway level before the sidewalls and roof are laid.
    tunnel_y=-4350.;floor=146.;roof=floor+6.8
    xy,s=samples([(2670,tunnel_y),(3840,tunnel_y)])
    cut(xy,np.full_like(s,floor),35,70)
    street('Gallery west approach',[(3260,-3650),(2900,-3760),(2600,-4050),(2670,tunnel_y),(2900,tunnel_y)],18,start=None,end=floor)
    street('Gallery east approach',[(3500,tunnel_y),(3840,tunnel_y),(4220,-4270),(4510,-4090),(4650,-3810),(4800,-3650)],18,start=floor)
    cut(xy,np.full_like(s,floor),32,38)
    for side in [-1,1]:
        solid(f'gallery-wall-{side}','box',3200,tunnel_y+side*9.8,300,1.2,floor-2,roof+.12,'wall')
    solid('gallery-roof','box',3200,tunnel_y,300,11,floor+6.6,roof+1.6,'deck',support='span',span='gallery')
    routes.append(dict(name='Cut-and-cover gallery',kind='tunnel',width_m=17.2,points=[[2900,tunnel_y],[3500,tunnel_y]]))
    # Flat proving apron plus an approach shared with the circuit. Retain the
    # actual gradient outside the site's earthwork shoulders.
    test_x,test_y=4900,-4890
    distance=np.maximum(abs(X-test_x)-425,abs(Y-test_y)-245)
    z+=(179.-z)*(1-smooth(0,145,distance))
    street('Proving ground access',[(4220,-4270),(4300,-4620),(4530,-4820),(4900,-4890)],15,end=179.)
    routes.append(dict(name='Proving apron',kind='apron',width_m=490,points=[[4475,-4890],[5325,-4890]]))
    # A stepped streambed runs out through the west boundary north of the
    # approach. Its two falls are sections of the physical sloping bed.
    river_control=[(-5580,6410),(-5290,5680),(-5220,4880),(-4860,4490),(-4770,4240),
                   (-4860,3690),(-5160,3220),(-5130,2860),(-5070,2500),(-5310,2060),
                   (-5700,1760),(-6310,1710),(-7090,1460),(-8000,1360)]
    xy,s=samples(river_control)
    high_to_low=20+.033*(s[-1]-s)+170*(1-smooth(2280,2350,s))+115*(1-smooth(3840,3900,s))
    cut(xy,high_to_low,70,410 if refine else 185)
    streams.append(dict(name='Twin Falls',width_m=46,points=np.round(xy[::2],2).tolist()))
    # A straight, open-underneath canyon crossing connects to an off-road pass.
    cy=3200.;cx=float(xy[np.argmin(abs(xy[:,1]-cy)),0])
    west,east=cx-290,cx+290
    deck=round(max(world.terrain_z(west,cy),world.terrain_z(east,cy))+3)
    street('Canyon climb',[(-3100,3310),(-3530,3510),(-3950,3610),(-4270,3450),
           (east+260,3200),(east,3200)],18,end=deck)
    street('Scree pass',[(west,3200),(west-260,3200),(-6080,3500),(-6430,3970),
                    (-6770,4130),(-7050,4520)],11,'track',start=deck)
    viaduct('Falls bridge',[(west,cy),(east,cy)],15,deck)
    # Link the eastern ridge crests across the bowl, with grounded approaches
    # at each end. The climbing road and the low perimeter remain alternatives.
    ridge_controls=[(5230,2670),(5470,2350),(5750,1790),(6150,1550),(6520,1620),(6750,1900),(6750,2330)]
    ridge_xy,_=samples(ridge_controls)
    crown=round(max(world.terrain_z(x,y) for x,y in ridge_xy)+6)
    street('Crown ascent',[(2900,2520),(3350,2750),(3700,3180),(4050,3330),(4390,3120),
                  (4600,2700),(4880,2460),(5090,2500),(5230,2670)],18,end=crown)
    street('Eastern descent',[(6750,2330),(7020,2610),(7350,2540),(7480,2060),
         (7210,1670),(6650,1480),(6100,1080),(5570,940),(4870,790),(4320,840)],18,start=crown)
    viaduct('Crown viaduct',ridge_controls,24,crown)
    # The existing vertical piers each gain bed-founded pilings. Aircraft and
    # boats encounter the same metre dimensions at the two original moorings.
    for pier in chart['docks']['piers']:
        x=chart['origin'][0]+pier['center'][0];y=chart['origin'][1]-pier['center'][1]
        floor=chart['waterLevelM']
        solid('deck-'+pier['id'],'box',x,y,pier['width']/2,pier['length']/2,floor,floor+1.2,'dock',support='span',span=pier['id'])
        for j,offset in enumerate([-27,0,27]):support(pier['id']+f'-pile-{j}',x,y+offset,.58,floor+.3)
    # A waterfront pavilion sits on its upland quay. Tiered ordinary masses
    # are placeholders for future district assets.
    for i,(x,y,a,b,h) in enumerate([(1050,-1150,52,23,14),(1120,-1150,22,23,22),(1157,-1150,14,22,37)]):
        bottom=min(world.terrain_z(x+u,y+v) for u in [-a,0,a] for v in [-b,0,b])-3
        top=max(world.terrain_z(x+u,y+v) for u in [-a,0,a] for v in [-b,0,b])+h
        solid(f'quay-pavilion-{i}','box',x,y,a,b,bottom,top,'architecture')
    places.extend([dict(name='Twin Falls',point=[-4770,4240]),dict(name='Sound Crossing',point=[-2120,-1830]),
       dict(name='Lantern Gallery',point=[3200,-4350]),dict(name='Proving grounds',point=[4900,-4890]),
       dict(name='Sunset Circuit',point=[5660,-3650]),dict(name='Crown Viaduct',point=[6150,1550])])
    # The baked geometry cannot move the inherited runway or raise a crossing.
    z[abs(Y)<=500]=0
    z[:]=np.rint(z*10)/10
    # Re-survey every inherited pine after excavation; remove any occupying a
    # carriageway, a new stream bed or a physical support.
    original=json.loads((PACK/'groves-01.json').read_text())
    positions=[];widths=[]
    if city is None:city=json.loads((PACK/'city-02.json').read_text())
    for r in routes+city['routes']+streams:
        p=np.array(r['points'])
        for a,b in zip(p,p[1:]):
            section=np.linspace(a,b,max(2,int(np.linalg.norm(b-a)/12)+1))
            positions.extend(section);widths.extend([r['width_m']/2]*len(section))
    tree=cKDTree(positions);widths=np.array(widths)
    kept=[]
    def plant(o):
        x,y,cz=o['center'];r,_,hh=o['half']
        d,nearest=tree.query([x,y],k=4)
        if any(d<widths[nearest]+r+2):return
        i,j=np.rint((np.array([x,y])+HALF)/STEP).astype(int)
        if wet[j,i]:return
        foot=min(world.terrain_z(x+dx,y+dy) for dx,dy in [(0,0),(r,0),(-r,0),(0,r),(0,-r)])
        o['center'][2]=round(foot+hh-.5,3)
        kept.append(o)
    for o in original:plant(o)
    rng=np.random.default_rng(1975)
    for i in range(1050):
        cx,cy=[(-5520,2820),(-6260,3600),(-5900,5280),(4630,2700),(6560,1720),
               (-4760,-3630),(-2760,-6110),(2350,-3900)][i%8]
        x,y=np.round(rng.normal((cx,cy),(255,120)),1)
        height=round(rng.uniform(12,27),1);radius=round(.14*height,2)
        plant(dict(id=f'grove-{i}',kind='cylinder',center=[x,y,0],half=[radius,radius,height/2],
                   color=rng.choice(['#294331','#344d3b','#243c34']),landable=False))
    return np.rint(z*10).astype('<u2'),dict(routes=routes,obstacles=objects,places=places,streams=streams,spans=spans,groves=kept)


if __name__=='__main__':
    z,network=build()
    np.savez_compressed(PACK/'routes-03.npz',height_dm=z)
    city=json.loads((PACK/'city-02.json').read_text())
    landscape_light(z,city['obstacles']+network['obstacles']+network['groves'],'relief-routes.png')
    (PACK/'routes-03.json').write_text(json.dumps(network,separators=(',',':'))+'\n',encoding='utf-8')
    print('Routes',len(network['routes']),'contact solids',len(network['obstacles']))
