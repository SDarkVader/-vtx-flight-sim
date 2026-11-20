"""Build the airport aprons, terminal roof sections and public access from survey 08."""
from copy import deepcopy
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from bake import PACK, ROOT, landscape_light
from roads import sections

sys.path.insert(0,str(ROOT/'src'))
from vtx.vaderland import LanternSound


def curve(a,b,c,d):
    t=np.linspace(0,1,33)[:,None]
    return ((1-t)**3*np.array(a)+3*(1-t)**2*t*np.array(b)+3*(1-t)*t**2*np.array(c)+t**3*np.array(d)).round(3).tolist()


def build():
    w=LanternSound()
    original={o['id']:o for o in w.obstacles}
    roads={r['name']:r for r in w.vaderland['routes']}
    added=[];removed=set()
    def solid(oid,kind,x,y,bottom,top,a,b,finish,role='architecture',parent=None,landable=True,**other):
        o=dict(id=oid,kind=kind,center=[float(x),float(y),round((bottom+top)/2,4)],
               half=[float(a),float(b),round((top-bottom)/2,4)],color='#596066',role=role,
               finish=finish,landable=landable,**other)
        if parent:o.update(support='stack',parent=parent)
        if oid in original:removed.add(oid)
        added.append(o)
    # Preserve the original hangar roof elevation and outer footprint. The two
    # long walls carry the full roof; the east and west mouths are actually open.
    solid('hangar','box',85,45,15.8,18,23,17,'hangar-roof',role='deck',
          support='span',span='Airside hangar',bearings=['hangar-wall-north','hangar-wall-south'])
    for name,side in [('north',1),('south',-1)]:
        solid('hangar-wall-'+name,'box',85,45+side*16.4,-.5,15.85,23,.6,'hangar-wall',role='wall',landable=False)
    # Retain the circular footprint and roof landing surfaces. Tag the existing
    # walls for the airfield glazing and metal skin.
    for o in w.obstacles:
        name=o['id']
        if name in {'tower','dispatch','terminal','arcade','freight','workshop','ridge-block'}:
            removed.add(name)
            added.append(dict(deepcopy(o),finish='service'))
        if name.startswith(('airport-rotunda','concourse-','arrivals-','terminal-gallery-')):
            removed.add(name)
            tag='rotunda' if 'rotunda' in name else 'gate'
            added.append(dict(deepcopy(o),finish=tag))
        if name.startswith('terminal-gallery-'):
            x,y,z=o['center'];a,b,h=o['half'];top=z+h
            # Short metal roof sections bear directly on the gate hall. Their
            # stepped silhouette is identical in the browser and contact model.
            count=11
            for j in range(count):
                u=2*(j+.5)/count-1
                height=.65+5.2*np.sqrt(max(0,1-u*u))
                solid(f'vault-{name}-{j}','box',x+u*a,y,top-.055,top+height,
                      a/count,b,'vault',parent=name)
    # The control tower is a supported sequence of simple civil shapes.
    tower=[('tower-plinth',12.,-.8,4.5,'stone'),('signal-tower',4.15,4.46,86.,'shaft'),
           ('tower-bearing',6.,85.97,88.4,'bronze'),('tower-balcony',10.8,88.36,90.3,'bronze'),
           ('signal-tower-cab',10.1,90.26,96.3,'cab'),('tower-cab-roof',11.3,96.26,97.5,'bronze')]
    parent=None
    for name,r,low,top,finish in tower:
        solid(name,'cylinder',116,-235,low,top,r,r,finish,parent=parent)
        parent=name
    hardstands=[dict(id='West stands',xy=[-476,-132],half=[165,64]),
                dict(id='East stands',xy=[476,-132],half=[165,64]),
                dict(id='North service apron',xy=[-46,55],half=[344,31])]
    pads=[]
    for code,x,y in [('W1',-546,-154),('W2',-397,-150),('E1',396,-150),('E2',546,-154)]:
        solid('stand-'+code,'cylinder',x,y,-.15,.024,18,18,'pad',role='deck')
        pads.append(dict(code=code,x=x,y=y,radius_m=18,level_m=.024))
    ring=roads['Terminal boulevard']['points']
    west=52; south=78
    landing=curve([-600,-83],[-498,-126],[-335,-186],ring[west])+ring[west+1:south+1]
    landing+=curve(landing[-1],[90,-492],[158,-484],[183.29,-500.22])[1:]
    landing+=curve(landing[-1],[197,-516],[202,-537],[205,-550])[1:]
    changes={'Airport landing road':dict(roads['Airport landing road'],points=landing)}
    north=[[-435.,45.],[137.,45.]]+curve([137,45],[154,45],[151,79],[184,79])[1:]+[[321.,79.]]
    routes=[dict(name='North hangar passage',kind='taxi',width_m=14,points=north),
            dict(name='South parallel taxiway',kind='taxi',width_m=12,points=[[-1160.,-45.],[1160.,-45.]])]
    for side,code in [(-1,'West'),(1,'East')]:
        curve_in=curve([side*452,-45],[side*416,-45],[side*387,-72],[side*387,-100])
        curve_in+=curve(curve_in[-1],[side*387,-127],[side*423,-128],[side*465,-128])[1:]
        curve_in+=[[side*579,-128]]
        routes.append(dict(name=code+' stand lead-in',kind='taxi',width_m=12,points=curve_in))
    entries=[dict(name='W2',xy=[-600,-83]),dict(name='E apron',xy=[510,-80])]
    airfield=dict(aprons=hardstands,pads=pads,hangar_id='hangar',public_road='Airport landing road',
                  terminal_center=[0,-300],entries=entries)
    # Remove old tree solids from the extended paved footprint, actual gate
    # volumes, and the swept width of both the new and retained access roads.
    run=[changes.get(r['name'],r) for r in w.vaderland['routes']]+routes
    samples=[(sections(r),r['width_m']/2) for r in run]
    xy=np.vstack([p for p,rad in samples]);width=np.concatenate([np.full(len(p),rad) for p,rad in samples])
    tree=cKDTree(xy)
    walls=[o for o in w.obstacles+added if o.get('role')=='architecture' or o['kind']=='box']
    walls=[o for o in walls if abs(o['center'][0])<750 and -560<o['center'][1]<220]
    retired={}
    for o in w.obstacles:
        x,y,z=o['center'];r=o['half'][0]
        if o['kind']!='cylinder' or o.get('role') or abs(x)>1200 or not -552<y<200:continue
        d,k=tree.query([x,y],k=8)
        if any(abs(x-h['xy'][0])<=h['half'][0]+r+1 and abs(y-h['xy'][1])<=h['half'][1]+r+1 for h in hardstands):
            retired[o['id']]='apron'
        elif np.any(d<width[k]+r+1):retired[o['id']]='swept route'
        elif any(abs(x-b['center'][0])<b['half'][0]+r and abs(y-b['center'][1])<b['half'][1]+r for b in walls):
            retired[o['id']]='structure'
    removed.update(retired)
    # Place clusters around the concourses, keeping the full crown out of
    # traffic, buildings, pavement and the surveyed shoreline.
    rng=np.random.default_rng(919)
    stems=[o['center'][:2] for o in w.obstacles if not o.get('role') and o['kind']=='cylinder' and o['id'] not in removed]
    existing=cKDTree(stems);planted=[]
    gardens=[(-300,-379),(285,-376),(-171,-453),(234,-461),(-385,-324),(376,-328),(-72,-401),(65,-411)]
    for k in range(900):
        x,y=np.round(rng.normal(gardens[k%len(gardens)],[29,18]),2)
        h=round(rng.uniform(7.5,17.5),2); crown=h*rng.uniform(.15,.21)
        d,ix=tree.query([x,y],k=8)
        if np.any(d<width[ix]+crown+2) or existing.query([x,y])[0]<5.2:continue
        if any(np.hypot(x-a,y-b)<6.5 for a,b in planted):continue
        if any(abs(x-b['center'][0])<b['half'][0]+crown+2 and abs(y-b['center'][1])<b['half'][1]+crown+2 for b in walls):continue
        if y<-510 or any(abs(x-a['xy'][0])<a['half'][0]+crown and abs(y-a['xy'][1])<a['half'][1]+crown for a in hardstands):continue
        radius=round(h*.018,3);base=w.terrain_z(x,y)-.35
        solid('airfield-fir-'+str(k),'cylinder',x,y,base,base+h,radius,radius,'fir',
              role='conifer',landable=False,crown_radius_m=round(crown,2))
        planted.append((x,y))
    lamps=[]
    for j in range(2,103,4):
        x,y=ring[j];direction=np.array([x/335**2,(y+335)/158**2]);direction/=np.linalg.norm(direction)
        x,y=np.round(np.array([x,y])+direction*11,3)
        d,ix=tree.query([x,y],k=12)
        if np.any(d<width[ix]+1.1):continue
        if any(abs(x-b['center'][0])<b['half'][0]+1 and abs(y-b['center'][1])<b['half'][1]+1 for b in walls):continue
        if any(np.hypot(x-o['center'][0],y-o['center'][1])<o.get('crown_radius_m',o['half'][0])+.65
               for o in w.obstacles+added if o['kind']=='cylinder' and (not o.get('role') or o['role']=='conifer')
               and o['id'] not in retired):continue
        base=w.terrain_z(x,y);oid=f'terminal-lamp-{j}'
        solid(oid,'cylinder',x,y,base-.2,base+7,.19,.19,'lamp',role='pier',landable=False)
        lamps.append([float(x),float(y),base+7])
    airfield['lamps']=lamps
    out=dict(removed=sorted(removed),added=added,revised_routes=changes,routes=routes,airfield=airfield,retired=retired)
    (PACK/'airport-09.json').write_text(json.dumps(out,separators=(',',':'))+'\n',encoding='utf-8')
    landscape_light(np.rint(w.heights*10),[o for o in w.obstacles if o['id'] not in removed]+added,'relief-airport.png')
    print(len(added),'solids authored or refitted;',len(retired),'conflicting trees removed')


if __name__=='__main__':build()
