"""Survey the road and build the landward entrance to Lantern Marina."""
from copy import copy
import gzip
import json
import math

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.spatial import cKDTree

from drafting import Masonry
from streets import StreetIndex
from vtx.vaderland import PACK
from vtx.world import make_world


LINK = 'Lantern Shore Link'
COURT = 'Lantern Marina turnaround'
GOLD = '#e4b67c'
CYAN = '#8dd5df'
DECK = 22.2
JOIN = np.array([1037., -1092.])
LOWER = np.array([930., -1155.])


def chain(points):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]


def smooth(points, entry, exit, spacing=3.0):
    points = np.asarray(points, float)
    distance = chain(points)
    curve = CubicSpline(distance, points, bc_type=((1, entry), (1, exit)))
    x = np.linspace(0, distance[-1], math.ceil(distance[-1]/spacing)+1)
    return curve(x)


def smoothstep(start, finish, value):
    u = np.clip((value-start)/(finish-start), 0, 1)
    return u*u*(3-2*u)


def alignment(world):
    existing = next(r for r in world.vaderland['routes'] if r['name']=='Airport landing road')
    source = np.asarray(existing['points'])
    point = np.array([142.911,-490.811])
    k = int(np.argmin(np.linalg.norm(source-point, axis=1)))
    if np.linalg.norm(source[k]-point) > .01:
        raise ValueError('Airport Landing junction moved')
    heading = source[k+1]-source[k-1]
    heading /= np.linalg.norm(heading)
    anchors = [source[k], (300,-484), (465,-467), (610,-481),
               (739,-519), (841,-590), (915,-690), (963,-803), (990,-913),
               (1012,-1002), (1034,-1060), JOIN]
    link = smooth(anchors, heading, [0,-1])
    height = PchipInterpolator(chain(np.asarray(anchors)),
        [0.,0.,0.,0.,.9,4.7,12.9,20.9,26.35,27.6,24.65,DECK])

    inbound = smooth([JOIN, (1034,-1114), (1023,-1127), (1007,-1138),
                      (995,-1154), (992,-1178)], [0,-1], [0,-1], 1.8)
    angle = np.linspace(math.pi, math.tau, 43)
    bottom = np.column_stack((1018+26*np.cos(angle), -1178+26*np.sin(angle)))
    exit = smooth([(1044,-1178), (1044,-1151), (1042,-1122), JOIN],
                  [0,1], [0,1], 1.8)
    loop = np.vstack((inbound, bottom[1:], exit[1:]))

    def road(name, width, points, tint):
        xy = np.round(points,5)
        return dict(name=name, width_m=width, kind='marina-link', edge_color=tint, points=xy.tolist())
    grade = height(np.linspace(0,height.x[-1], len(link)))
    return [road(LINK,14.,link,GOLD), road(COURT,9.6,loop,CYAN)], grade


def regrade(base, roads, grade):
    world = copy(base)
    world.heights = base.heights.copy()
    _, path = (np.asarray(r['points']) for r in roads)
    centers = np.vstack((roads[0]['points'],path[1:]))
    levels = np.r_[grade, np.full(len(path)-1,DECK)]
    proximity = cKDTree(centers)
    axes = np.linspace(-world.half,world.half,world.n)
    cols = np.flatnonzero((axes>260)&(axes<1140))
    rows = np.flatnonzero((axes>-1270)&(axes<-420))
    i,j = np.meshgrid(cols,rows)
    x,y = axes[i],axes[j]
    xy = np.column_stack((x.ravel(),y.ravel()))
    distance,k = proximity.query(xy)
    weight = 1-smoothstep(23,61,distance)
    weight *= smoothstep(260,355,xy[:,0])
    weight *= 1-(1-smoothstep(960,980,xy[:,0]))*(1-smoothstep(9,38,abs(xy[:,1]-LOWER[1])))
    # Preserve an entire heightfield cell around water and the current runway basin.
    # Protected vertices cannot contribute to any wet triangle.
    reach = 2*world.half/(world.n-1)*math.sqrt(2)
    for cell in np.flatnonzero(weight):
        if base.harbour_overlaps(*xy[cell],reach):
            weight[cell] = 0.
    old = world.heights[j,i].ravel()
    new = np.round(old+weight*(levels[k]-old),5)
    changed = np.flatnonzero(np.abs(new-old)>1e-5)
    terrain = [[int(j.flat[m]),int(i.flat[m]),float(new[m])] for m in changed]
    for row,col,z in terrain:
        world.heights[row,col] = z
    return world, terrain


def grounded(world, masonry, name, x, y, a, b, top, skin):
    bed = min(world.terrain_z(x+i*a,y+j*b) for i in (-1,1) for j in (-1,1))-.48
    return masonry.box(name,x,y,bed,top,a,b,skin)


def along(masonry, name, a, b, width, thickness, skin, **kwargs):
    a,b = np.array(a),np.array(b)
    heading = b[:2]-a[:2]
    across = np.array([-heading[1],heading[0]])/np.linalg.norm(heading)
    return masonry.hull(name,[(p[0]+side*across[0]*width/2,p[1]+side*across[1]*width/2,p[2]-drop)
        for p in (a,b) for side in (-1,1) for drop in (0.,thickness)],skin,**kwargs)


def stairs(world, masonry):
    sx,sy = LOWER
    low, high = 8.2, DECK
    width, run = 6.6, .54
    sections, per_flight = 4, 18
    rise = (high-low)/(sections*per_flight)
    low_landing = masonry.box('marina-stairs-landing-lower',sx+.65,sy,low-.43,low+.007,.71,.5*width,'marinaDeck')
    names = []
    x = sx+1.3
    for flight in range(sections):
        for i in range(per_flight):
            top = low+(flight*per_flight+i+1)*rise
            ground = [world.terrain_z(x+d,sy+v) for d in (0.,run) for v in (-width/2,width/2)]
            bed = min(ground)-.38
            if max(ground)>top+.015:
                raise ValueError('Stair tread intersects the shore slope')
            p = masonry.box(f'marina-stairs-{flight}-{i:02d}',x+run/2,sy,bed,top,run/2+.002,width/2,
                'marinaDeck',parent=names[-1] if i else low_landing)
            names.append(p)
            x+=run
        length = 2.6 if flight<sections-1 else 6.0
        platform = grounded(world,masonry,f'marina-stairs-landing-{flight}',x+length/2,sy,
                           length/2,width/2,top+.03,'marinaDeck')
        names.append(platform)
        x+=length
    high_east = x
    for side in (-1,1):
        for flight in range(sections):
            span = per_flight*run+2.6
            x = sx+1.3+span*flight
            y = sy+side*(width*.5-.095)
            z1,z2 = low+flight*per_flight*rise,low+(flight+1)*per_flight*rise
            for j in (0,1,2):
                u = j*.5
                xx = x+per_flight*run*u
                zz = z1+(z2-z1)*u
                masonry.box(f'marina-stair-post-{side}-{flight}-{j}',xx,y,zz-.09,zz+.99,.064,.071,'marinaMetal')
            a,b,c = (x,y,z1+1.02),(x+per_flight*run,y,z2+1.02),(x+span,y,z2+1.02)
            along(masonry,f'marina-rail-flight-{side}-{flight}',a,b,.09,.075,'marinaMetal')
            along(masonry,f'marina-rail-landing-{side}-{flight}',b,c,.09,.075,'marinaMetal')
            if flight in (0,2,3):
                along(masonry,f'marina-stair-tube-{side}-{flight}',(a[0],y,.96+z1),
                      (b[0],y,.96+z2),.045,.047,'marinaTeal')
    return [high_east, sy]


def dock_support(world, masonry):
    # Author the air/road physics counterpart of the already charted walkway.
    # The boat solver and the visible dock keep their existing structure data.
    origin, level = world.harbour['origin'], world.harbour['waterLevelM']+1.2
    for path in world.harbour['docks']['access']:
        if not path['id'].startswith('lantern-'):
            continue
        points = [[origin[0]+x,origin[1]-y,level] for x,y in path['points']]
        for i,(a,b) in enumerate(zip(points,points[1:])):
            name = f"{path['id']}-{i}"
            along(masonry,'marina-chart-'+name,a,b,path['width'],1.2,'marinaHidden',harbour_structure=name)


def pavilion(world, masonry):
    cx,cy,z = 1017.,-1171.5,DECK
    slab = grounded(world,masonry,'marina-pavilion-slab',cx,cy,15.,18.8,z+.08,'marinaDeck')
    width_stations = [(-15,5.14),(-11,6.26),(-4.7,8.0),(2.5,8.66),(8.5,7.74),(13.8,6.28)]
    roof_x,roof_z = np.array(width_stations).T
    lamp_specs = []
    for y in (cy-14.,cy-5.,cy+5.,cy+14.):
        for x in (cx-10.4,cx+10.4):
            top = z+np.interp(x-cx,roof_x,roof_z)-.05
            p = masonry.box(f'marina-pavilion-post-{x}-{y}',x,y,z+.045,top,.245,.255,'marinaMetal',parent=slab)
            if x<cx:
                masonry.box(f'marina-pavilion-sconce-{y}',x-.28,y,z+1.35,z+3.44,.065,.084,'marinaWarm',parent=p)
                lamp_specs.append(dict(position=[x-.47,y,z+3.3],reach=12.,color=GOLD))
    glazing = ((cx+10.4,cy-9.5,.12,4.2),(cx+10.4,cy+9.5,.12,4.2),
              (cx-10.4,cy-9.5,.12,4.2),(cx-10.4,cy+9.5,.12,4.2),
              (cx,cy-14.,10.2,.10),(cx,cy+14.,10.2,.10))
    for i,(x,y,a,b) in enumerate(glazing):
        masonry.box(f'marina-sill-{i}',x,y,z+.05,z+.72,a+.084,b+.103,'marinaMetal',parent=slab)
        masonry.box(f'marina-glass-{i}',x,y,z+.69,z+5.25,a,b,'marinaGlass',parent=slab)
    for s in (-1,1):
        masonry.box(f'marina-counter-{s}',cx+5.,cy+s*4.65,z+.06,z+1.06,1.02,3.2,'marinaTimber',parent=slab)
        masonry.box(f'marina-counter-front-{s}',cx+3.97,cy+s*4.65,z+.24,z+.93,.024,3.12,'marinaTeal',parent=slab)
        masonry.box(f'marina-side-bench-{s}',cx-5.2,cy+s*12.0,z+.05,z+.49,2.7,.61,'marinaTimber',parent=slab)
    for i,((a,h1),(b,h2)) in enumerate(zip(width_stations,width_stations[1:])):
        span = lambda u: 19.3-.18*abs(u)
        masonry.hull(f'marina-roof-{i}',[(cx+u,cy+side*span(u),z+h+dz)
          for u,h in ((a,h1),(b,h2)) for side in (-1,1) for dz in (0.,.43)],
          'marinaMetal',parent=p)
        for side in (-1,1):
            along(masonry,f'marina-roof-edge-{i}-{side}',
              [cx+a,cy+side*span(a),z+h1+.20],[cx+b,cy+side*span(b),z+h2+.20],
              .16,.16,'marinaWarm')
        for j,y in enumerate((cy-14.,cy-5.,cy+5.,cy+14.)):
            along(masonry,f'marina-roof-rib-{i}-{j}',[cx+a,y,z+h1+.08],[cx+b,y,z+h2+.08],
                  .31,.38,'marinaMetal')
    for side in (-1,1):
        x = cx+side*10.4
        along(masonry,f'marina-glass-header-{side}',[x,cy-14.,z+5.62],[x,cy+14.,z+5.62],.29,.38,'marinaMetal')
    for i,t in enumerate((-11.,0.,11.)):
        u = z+5.3
        along(masonry,f'marina-interior-light-{i}',[cx-9.6,cy+t,u],[cx+9.6,cy+t,u],.15,.13,'marinaWarm')
        along(masonry,f'marina-roof-beam-{i}',[cx-10.4,cy+t,u+.22],[cx+10.4,cy+t,u+.22],.39,.42,'marinaMetal')
        lamp_specs.append(dict(position=[cx-3.6,cy+t,u],reach=16.,color=GOLD))
    masonry.box('marina-terminal-fascia',cx-14.99,cy,z+4.38,z+5.56,.24,7.15,'marinaMetal',parent='marina-roof-0')
    masonry.box('marina-berth-fascia',cx,cy+14.13,z+4.04,z+5.43,9.8,.24,'marinaMetal',parent=slab)

    for side in (-1,1):
        for i in range(12):
            x = cx+(i-5.5)*2.24
            y = cy+side*17.83
            masonry.box(f'marina-terrace-baluster-{side}-{i}',x,y,z+.05,z+1.16,.047,.053,'marinaMetal',parent=slab)
        along(masonry,f'marina-terrace-handrail-{side}',
              [cx-13.0,cy+side*17.83,z+1.16],[cx+13.0,cy+side*17.83,z+1.16],.074,.074,'marinaMetal')
    return lamp_specs


def roadside(world, masonry, road):
    signs = []
    lamps = []
    samples = np.asarray(road['points'])
    distance = chain(samples)
    for i,s in enumerate([101.,350.,600.,765.,925.,1030.,1130.,1215.,1270.,1330.]):
        j = int(np.searchsorted(distance,min(s,distance[-1]-6.)))
        x,y = samples[j]
        tangent = samples[j+1]-samples[j-1]
        tangent /= np.linalg.norm(tangent)
        right = np.array([tangent[1],-tangent[0]])
        x,y = np.array([x,y])+right*9.6
        z = world.terrain_z(x,y)
        base = grounded(world,masonry,f'marina-lamp-plinth-{i}',x,y,.45,.45,z+.33,'marinaDeck')
        masonry.box(f'marina-lamp-stem-{i}',x,y,z+.31,z+4.94,.11,.11,'marinaMetal',parent=base)
        a = np.array([x,y,z+4.98])
        b = a-np.r_[right*1.44,0.]
        along(masonry,f'marina-lamp-arm-{i}',a,b,.218,.25,'marinaMetal')
        masonry.box(f'marina-lamp-lens-{i}',*b[:2],b[2]-.29,b[2]-.21,.23,.19,'marinaWarm')
        lamps.append(dict(position=[*b[:2],b[2]-.31],reach=12.5,color=GOLD))
        if i in (4,9):
            # A separate shoulder panel is held beside the lamp, facing drivers.
            center = a-np.array([0,0,2.02])+np.r_[right*.96,0]
            point = center+np.r_[-tangent*.071,0]
            along(masonry,f'marina-sign-panel-{i}', center+np.r_[right*1.16,.38],
              center-np.r_[right*1.16,-.38],.14,.76,'marinaMetal')
            text = {4:'MARINA  /  ISLET TRIAL',9:'BOAT BERTHS'}[i]
            signs.append(dict(label=text,point=point.tolist(),normal=(-tangent).tolist(),width=2.21,height=.66))
    x,y = 128.,-478.8
    z = world.terrain_z(x,y)
    foot = grounded(world,masonry,'marina-junction-base',x,y,.62,.75,z+.34,'marinaDeck')
    masonry.box('marina-junction-stem',x,y,z+.25,z+4.05,.17,.145,'marinaMetal',parent=foot)
    for j,(label,d) in enumerate((('STRAIGHT   /   LANTERN MARINA',3.78),('RIGHT   /   AIRPORT LANDING',3.02))):
        masonry.box(f'marina-junction-board-{j}',x,y,z+d-.356,z+d+.356,.17,2.695,'marinaMetal',
                    parent='marina-junction-stem')
        signs.append(dict(label=label,point=[x-.178,y,z+d],normal=[-1,0],width=5.17,height=.646))
    return signs, lamps


def shore_furniture(world, masonry, roads):
    # Tides reach the charts. The new dry bank, seats and beacons stay outside it.
    index = StreetIndex(world,roads)
    rng = np.random.default_rng(3812)
    for i,(x,y,rx,ry,h) in enumerate([
        (947,-1167,5.6,3.1,1.4), (957,-1171,6.4,4.8,1.9),
        (961,-1139,8.8,4.3,2.2), (952,-1145,5.9,3.1,1.6),
        (974,-1182,5.2,6.4,1.6), (969,-1103,9.1,6.2,2.2),
        (983,-1072,9.9,5.6,2.4), (1002,-1037,6.5,7.4,2.6),
        (1068,-1045,12.1,6.5,3.5), (1071,-1087,8.4,6.4,2.3),
        (1074,-1199,9.3,8.7,2.7), (1047,-1227,13.2,8.4,3.2),
        (996,-1222,7.1,6.5,2.3), (973,-1206,5.6,4.1,1.6),
    ]):
        z = world.terrain_z(x,y)
        ring=[]
        for theta in np.linspace(0,math.tau,7,endpoint=False):
            dx=rx*math.cos(theta)*rng.uniform(.71,1.)
            dy=ry*math.sin(theta)*rng.uniform(.71,1.)
            ring.append([x+dx,y+dy,world.terrain_z(x+dx,y+dy)-.39])
            a,b=x+dx*.58,y+dy*.51
            ring.append([a,b,max(z,world.terrain_z(a,b))+h*rng.uniform(.46,1.)])
        masonry.hull(f'marina-bank-stone-{i}',ring,'marinaBasalt')
    lamps = []
    for i,(x,y,height) in enumerate(((975.,-1129.,8.9),(1061.,-1136.,10.6))):
        z = world.terrain_z(x,y)
        base = grounded(world,masonry,f'marina-beacon-foot-{i}',x,y,1.42,1.28,z+.43,'marinaBasalt')
        mast = masonry.hull(f'marina-beacon-mast-{i}',[
            (x+a*w+.21*k,y+b*w,z+height*k+(1-k)*.37)
            for a in (-1,1) for b in (-1,1) for k,w in ((0,.65),(1,.35))],
            'marinaMetal',parent=base)
        for j,(low,high,finish) in enumerate(((.31,.43,'marinaTeal'),(.84,.99,'marinaWarm'))):
            face = x-(.536 if j==0 else .247)
            masonry.box(f'marina-beacon-lens-{i}-{j}',face,y,z+height*low,z+height*high,.20,.26,finish,parent=mast)
        masonry.box(f'marina-beacon-cap-{i}',x+.21,y,z+height-.14,z+height+.24,.55,.544,'marinaMetal',parent=mast)
        lamps.append(dict(position=[x-.76,y,z+height*.42],reach=11.,color=CYAN))
    for i,(x,y) in enumerate(((976.,-1144.),(980.,-1166.))):
        base=grounded(world,masonry,f'marina-seat-base-{i}',x,y,.85,2.05,world.terrain_z(x,y)+.27,'marinaBasalt')
        z=world.terrain_z(x,y)+.27
        for s in (-1,1):
            masonry.box(f'marina-seat-leg-{i}-{s}',x,y+s*1.33,z-.055,z+.43,.18,.19,'marinaMetal',parent=base)
        masonry.box(f'marina-seat-plank-{i}',x,y,z+.38,z+.55,.47,1.82,'marinaTimber',parent=base)
    groves = []
    for center,(rx,ry) in [
        ((1003,-1076),(27,45)), ((1080,-1158),(30,45)), ((979,-1239),(49,23)),
        ((955,-1105),(11,23)), ((976,-1045),(25,32)), ((1054,-1235),(35,15)),
    ]:
        for _ in range(7):
            x,y = np.asarray(center)+rng.uniform(-1,1,size=2)*[rx,ry]
            if (x<990 and abs(y-LOWER[1])<13) or world.harbour_overlaps(x,y,7.):
                continue
            if any(math.hypot(p['center'][0]-x,p['center'][1]-y)<7.4 for p in groves):
                continue
            ground = world.terrain_z(x,y)
            h = rng.uniform(5.4,11.)
            radius = 0.17*h
            tree = dict(id=f'marina-windbreak-{len(groves):02d}',kind='cylinder',role='conifer',
                center=[float(x),float(y),float(ground+h/2-.19)],half=[h*.029,h*.029,h/2],
                crown_radius_m=radius, color=['#486956','#4e5844','#56705b'][len(groves)%3],landable=False)
            if not index.overlaps(tree,margin=3.5):
                groves.append(tree)
    return groves, lamps


def audit_roads(world, roads):
    for road in roads:
        xy = np.asarray(road['points'])
        offsets = []
        distance = np.diff(chain(xy))
        tangents = np.diff(xy,axis=0)/distance[:,None]
        bend = np.abs(np.arctan2(tangents[:-1,0]*tangents[1:,1]-tangents[:-1,1]*tangents[1:,0],
                               np.sum(tangents[:-1]*tangents[1:],axis=1)))
        radius = (distance[:-1]+distance[1:])/(2*np.maximum(bend,1e-12))
        mid = xy[1:-1]
        across = tangents[:-1,::-1]*np.array([-1,1])
        up = np.array([world.terrain_z(*p) for p in xy])
        for side in (-.43,0,.43):
            points = mid+side*road['width_m']*across
            if np.any(world.harbour_water_mask(*points.T)):
                raise ValueError(f"Road reaches the charted sea: {road['name']}")
            offsets.append(np.array([world.terrain_z(*p) for p in points]))
        grade = 100*np.max(abs(np.diff(up)/distance))
        crossfall = 100*np.max(abs(offsets[0]-offsets[2])/(.86*road['width_m']))
        if grade>10.9 or crossfall>4.5 or float(radius.min())<16.:
            raise ValueError(f"{road['name']} grade {grade:.2f}%, crossfall {crossfall:.2f}%, radius {radius.min():.1f} m")
        print(road['name'], round(distance.sum(),2), 'm', round(grade,2), 'grade %',
              round(crossfall,2),'crossfall %', round(float(radius.min()),2),'minimum radius m')


def bake(base):
    roads, grade = alignment(base)
    world, terrain = regrade(base, roads, grade)
    audit_roads(world, roads)
    masonry = Masonry()
    dock_support(world,masonry)
    upper = stairs(world,masonry)
    lamps = pavilion(world,masonry)
    signs, road_lamps = roadside(world,masonry,roads[0])
    groves, bank_lamps = shore_furniture(world,masonry,roads)
    signs.extend([
        dict(label='LANTERN MARINA', point=[1001.751,-1171.5,DECK+4.97],width=13.2,height=1.1,normal=[-1,0]),
        dict(label='ISLET TRIAL  /  BERTHS', point=[1017.,-1157.129,DECK+4.76],width=18.4,height=1.15,normal=[0,1]),
    ])
    legacy = next(r for r in world.vaderland['routes'] if r['name']=='Airport landing road')
    index = StreetIndex(world,[*roads,legacy])
    conflicts = {}
    for o in masonry.solids:
        if o['skin']=='marinaHidden':
            continue
        hits=index.overlaps(o, margin=.04)
        if hits:conflicts[o['id']]=hits
    if conflicts:
        raise ValueError(f'Shore link furniture overlaps driving clearance: {conflicts}')
    removed=[]
    permanent = [o for o in masonry.solids if o['skin']!='marinaHidden']
    for o in base.obstacles:
        x,y,z = o['center']
        if not 95<x<1180 or not -1270<y<-445:
            continue
        tree = o['kind']=='cylinder' and o.get('role') in (None,'conifer')
        tree_blocking = tree and any(name!=legacy['name'] for name in index.overlaps(o,margin=2.))
        if tree and not tree_blocking:
            reach = o.get('crown_radius_m',o['half'][0])
            tree_blocking = any(abs(p['center'][0]-x)<p['half'][0]+reach+.22
                                and abs(p['center'][1]-y)<p['half'][1]+reach+.22 for p in permanent)
        if o['id'] in ('quay-pavilion-0','quay-pavilion-1','quay-pavilion-2') or tree_blocking:
            removed.append(o['id'])
        elif abs(base.terrain_z(x,y)-world.terrain_z(x,y))>.08:
            if not tree:
                raise ValueError(f'Grading alters existing structure support: {o["id"]}')
            moved = dict(o,center=[x,y,round(z+world.terrain_z(x,y)-base.terrain_z(x,y),5)])
            removed.append(o['id'])
            masonry.solids.append(moved)
    dock_finishes = [[o['harbour_structure'],o['id']] for o in masonry.solids if o.get('harbour_structure')]
    dock_finishes.extend([p['id'],'deck-'+p['id']] for p in world.harbour['docks']['piers']
                         if p['id'].startswith('lantern-'))
    changed = dict(center=[1017.,-1171.5], spawn=[1018.,-1204.], approach=roads[0]['points'][27], landing=upper,
                   stairs=[*LOWER,8.2], signs=signs, lamps=lamps+road_lamps+bank_lamps,
                   laybys=[[988.45,-1163.9],[987.52,-1172.1]],
                   dock_finishes=dock_finishes,
                   junction_roads=['Airport landing road',LINK,COURT])
    return dict(terrain=terrain, roads=roads, solids=masonry.solids+groves, removed=removed, marina=changed)


if __name__ == '__main__':
    plan = bake(make_world('vaderland-31'))
    out=PACK/'lantern-marina-32.json.gz'
    out.write_bytes(gzip.compress(json.dumps(plan,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    print(len(plan['terrain']), 'dry terrain cells;',len(plan['solids']), 'solids;',len(plan['removed']), 'retired or resited')
