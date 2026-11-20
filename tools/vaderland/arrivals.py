"""Author the terminal as continuous lofts. Export one set of convex hulls for all models."""
import json
import math

import numpy as np
from scipy.spatial import ConvexHull

from airfield import curve
from bake import PACK, landscape_light
from vtx.vaderland import AirportLanding


def build():
    world=AirportLanding()
    solids=[];routes=[]
    remove={o['id'] for o in world.obstacles if o['id'].startswith(
        ('airport-rotunda','concourse-','arrivals-','terminal-gallery-','vault-terminal-','tower-','signal-tower'))}
    def hull(name,points,skin,*,parent=None,bearings=None,landable=False,hidden=(),**extra):
        p=np.asarray(points,dtype=float).round(5)
        center=np.round((p.max(axis=0)+p.min(axis=0))/2,5)
        local=(p-center).round(5);ch=ConvexHull(local)
        faces=[];hidden_faces=[]
        for face,plane in zip(ch.simplices,ch.equations):
            a,b,c=map(int,face)
            if np.dot(np.cross(local[b]-local[a],local[c]-local[a]),plane[:3])<0:b,c=c,b
            if any({a,b,c}<=subset for subset in hidden):hidden_faces.append(len(faces))
            faces.append([a,b,c])
        item=dict(id=name,kind='mesh',center=center.tolist(),half=((p.max(axis=0)-p.min(axis=0))/2).round(6).tolist(),
                  role='architecture',landable=landable,color='#314050',finish='shell',skin=skin,
                  vertices=local.tolist(),faces=faces,planes=np.unique(ch.equations.round(9),axis=0).tolist(),**extra)
        if hidden_faces:item['internal_faces']=hidden_faces
        if parent:item.update(support='stack',parent=parent)
        if bearings:item.update(support='span',span=name,bearings=bearings,role='deck')
        solids.append(item)
        return name
    def turned(name,cx,cy,profile,skin,segments=72,**kw):
        segments+=1
        return hull(name,[[cx+r*math.cos(a),cy+r*math.sin(a),z] for r,z in profile
                    for a in (np.arange(segments)+.31)*2*math.pi/segments],skin,**kw)
    def column(name,x,y,top,r=.37):
        o=dict(id=name,kind='cylinder',center=[x,y,(top-.35)/2],half=[r,r,(top+.35)/2],
               color='#71533e',role='pier',finish='quay-column',landable=False)
        solids.append(o);return name
    turned('airport-rotunda',0,-300,[(77,-.7),(81,2.5),(81,14.6)],'glass',96,landable=True)
    turned('rotunda-low-eave',0,-300,[(85.7,14.55),(86.5,15.1),(85.8,15.7)],'lip',96,parent='airport-rotunda',landable=True)
    turned('airport-rotunda-drum',0,-300,[(83.8,15.65),(83.7,16.55),(72.6,29.5)],'glass',96,parent='rotunda-low-eave',landable=True)
    turned('airport-rotunda-crown',0,-300,[(77.8,29.45),(78.5,30.2),(77.9,31.4),(74.4,35.0),
           (68.1,38.65),(59.7,41.75),(50.,44.23),(40.,46.)],'crown',96,parent='airport-rotunda-drum',landable=True)
    # The cabin and shaft have a continuous, flared profile in flight and on foot.
    stages=[('tower-plinth',[(10,-.5),(11,1.1),(8.2,3.6),(6.8,4.8)],'lip'),
            ('signal-tower',[(5.3,4.74),(4.2,9.),(3.1,65.),(3.5,81.),(4.4,85.2)],'tower'),
            ('tower-bearing',[(4.35,85.16),(10.7,89.8),(11.2,90.5)],'lip'),
            ('signal-tower-cab',[(9.55,90.45),(11.0,95.3),(10.8,96.1)],'glass'),
            ('tower-cab-roof',[(11.95,96.05),(12.3,96.5),(10.7,97.45),(6.0,98.3)],'lip')]
    parent=None
    for oid,profile,finish in stages:
        turned(oid,116,-235,profile,finish,48,parent=parent)
        parent=oid
    # Loft four swept fingers from a shared root. Cross-sections carry the
    # facades, eaves and vaults in the same convex geometry as the contact mesh.
    for side in (-1,1):
        for branch in (0,1):
            control=([(52,-315),(103,-303),(194,-316),(258,-344)] if branch==0 else
                     [(46,-335),(104,-354),(176,-400),(237,-427)])
            guide=np.array(curve(*control))[::2]
            tangent=np.gradient(guide,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
            rows=[]
            for j,((x,y),(dx,dy)) in enumerate(zip(guide,tangent)):
                t=j/(len(guide)-1)
                width=14.+6.4*math.sin(math.pi*t)**.8
                if t>.82:width*=max(.08,math.cos((t-.82)/.18*1.51))
                wall=8.7+2.7*math.sin(math.pi*t)+1.1*branch
                rise=(6.2+3.4*math.sin(math.pi*t))*(.60+.40*width/20)
                section=[(-width*.87,-.48),(width*.87,-.48),(width,wall)]
                section.extend((width*math.cos(a),wall+rise*math.sin(a)) for a in np.linspace(0,math.pi,21)[1:])
                rows.append([[side*(x-dy*u),y+dx*u,z] for u,z in section])
            for j,(a,b) in enumerate(zip(rows,rows[1:])):
                n=len(a);hidden=[]
                if j:hidden.append(set(range(n)))
                if j<len(rows)-2:hidden.append(set(range(n,2*n)))
                hull(f'terminal-wing-{side}-{branch}-{j}',a+b,'wing',hidden=hidden,
                     spine=[[side*guide[i,0],guide[i,1]] for i in (j,j+1)],branch=branch)
    # A thin pickup canopy bows upwards along its span. Drivers pass between
    # the bearing rows. Its southern edge remains north of the roundabout.
    for j,(a,b) in enumerate(zip([-36,-24,-12,0,12,24],[-24,-12,0,12,24,36])):
        rows=[];bearings=[]
        for endpoint,x in [(a,max(-36,a-.035)),(b,min(36,b+.035))]:
            top=9.0+2.1*(1-(x/38)**2)
            cross=[(-6.,top-.58),(-6.3,top-.24),(-5.6,top+.15),(0,top+.70),(5.6,top+.15),(6.3,top-.24),(6.,top-.58)]
            rows.append([[x,-395+u,z] for u,z in cross])
            for s in (-1,1):
                name=f'pickup-column-{endpoint}-{s}';bearings.append(name)
                if not any(o['id']==name for o in solids):column(name,endpoint,-395+s*5.7,top-.53)
        n=len(rows[0]);hidden=([set(range(n))] if j else [])+([set(range(n,n*2))] if j<5 else [])
        hull('pickup-canopy-'+str(j),rows[0]+rows[1],'canopy',bearings=bearings,hidden=hidden)
    # Low civic island is built up from the actual ground.
    turned('arrivals-island',0,-437,[(13.9,-.25),(14.25,.12),(13.95,.40)],'kerb',80)
    turned('arrivals-terrace',0,-437,[(9.35,.36),(9.15,.68),(8.15,.9)],'garden',64,parent='arrivals-island')
    turned('arrivals-compass',0,-437,[(4.25,.86),(3.85,1.22),(2.65,1.48)],'bronze',64,parent='arrivals-terrace')
    boulevard=next(r for r in world.vaderland['routes'] if r['name']=='Terminal boulevard')
    def gate(x):
        return min((p for p in boulevard['points'] if p[1]<-465),key=lambda p:abs(p[0]-x))
    west=curve(gate(-101),[-68,-487],[-67,-461],[-65,-433])
    west+=curve(west[-1],[-64,-409],[-54,-395],[-31,-395])[1:]
    pickup=west+[[31,-395]]+[[-x,y] for x,y in west[-2::-1]]
    def route(name,points,width):
        routes.append(dict(name=name,kind='arrivals',points=points,width_m=width))
    route('Terminal pickup',pickup,10.)
    circle=[[round(23.6*math.cos(a),4),round(-437+23.6*math.sin(a),4)] for a in np.linspace(math.pi, -math.pi,113)]
    route('Arrivals circle',circle,9.)
    feeder=curve(gate(-42),[-15,-485],[-23.6,-457],[-23.6,-437])
    route('West arrivals slip',feeder,8.4)
    route('East arrivals slip',[[-x,y] for x,y in feeder],8.4)
    route('Pickup link',curve(circle[28],[28,-413],[37,-395],[31,-395]),7.)
    # Clearance around the re-formed terminal and canopy includes the tree's
    # physical stem plus the visible crown. Keep the accessible curb line open.
    outline=[]
    for o in solids:
        if o.get('skin')!='wing':continue
        v=np.array(o['vertices'])[:,:2]+o['center'][:2]
        outline.append((np.asarray(o['center'][:2]),np.asarray(o['half'][:2]),ConvexHull(v).equations))
    lines=[(np.array(r['points']),r['width_m']/2) for r in routes]
    cleared={}
    def blocked(x,y,r):
        if np.hypot(x,y+437)<15+r or (abs(x)<38+r and abs(y+395)<7+r):return 'island or canopy'
        for c,a,edges in outline:
            if np.all(abs(np.array([x,y])-c)<a+r) and np.max(edges[:,:2]@[x,y]+edges[:,2])<r:return 'terminal shell'
        for points,width in lines:
            delta=np.diff(points,axis=0);offset=np.array([x,y])-points[:-1]
            t=np.clip((delta*offset).sum(axis=1)/np.maximum((delta*delta).sum(axis=1),1e-12),0,1)
            if np.min(np.linalg.norm(offset-delta*t[:,None],axis=1))<width+r+.8:return 'public carriageway'
        return None
    for o in world.obstacles:
        x,y,z=o['center']
        if abs(x)>283 or not -500<y<-267 or o['kind']!='cylinder' or o.get('role') not in (None,'conifer','pier'):continue
        why=blocked(x,y,o.get('crown_radius_m',o['half'][0]))
        if why:cleared[o['id']]=why;remove.add(o['id'])
    rng=np.random.default_rng(11341)
    trees=[(o['center'][0],o['center'][1],o.get('crown_radius_m',o['half'][0])) for o in world.obstacles
           if o['kind']=='cylinder' and o['id'] not in remove and abs(o['center'][0])<360 and -520<o['center'][1]<-250]
    for j in range(280):
        cx,cy=[(-90,-455),(86,-456),(-151,-435),(152,-436),(-39,-449),(40,-453),(-213,-388),(214,-384)][j%8]
        x,y=rng.normal([cx,cy],[17,9]).round(2);crown=round(rng.uniform(3.4,5.8),2);height=round(rng.uniform(9.3,15.5),2)
        if blocked(x,y,crown) or np.hypot(x,y+300)<88+crown:continue
        if min((np.hypot(x-a,y-b)-r for a,b,r in trees),default=50)<crown-.35:continue
        if abs((x/335)**2+((y+335)/158)**2-1)<.12:continue
        trees.append((x,y,crown))
        solids.append(dict(id='arrivals-tree-'+str(j),kind='cylinder',center=[x,y,height/2-.18],
            half=[.23,.23,height/2],role='conifer',crown_radius_m=crown,color='#455c41',
            species=j%3,finish='fir',landable=False))
    # The original lamp uniforms derive from the surviving physical poles.
    plac=dict(center=[0,-300],island=[0,-437],pickup=[0,-395],asset='meridian-terminal.glb')
    data=dict(removed=sorted(remove),solids=solids,routes=routes,arrivals=plac,clearance=cleared)
    (PACK/'arrivals-11.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    others=[o for o in world.obstacles if o['id'] not in remove]
    landscape_light(np.rint(world.heights*10),others+solids,'relief-arrivals.png')
    print(len(solids),'solids;',len(cleared),'conflicts removed;',sum(o['kind']=='mesh' for o in solids),'convex hulls')


if __name__=='__main__':build()
