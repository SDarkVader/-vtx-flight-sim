"""Bake wheel-bearing vertical loop geometry and its Cathedral road connections."""
import gzip
import json
import math

import numpy as np
from scipy.integrate import cumulative_trapezoid, solve_ivp

from drafting import Masonry
from streets import StreetIndex
from vtx.meridian_yard import MeridianHandlingYard
from vtx.vaderland import PACK
from vtx.world import MapPoint


GRAVITY = 9.80665
REFERENCE = 40.
PEAK_LOAD = 2.23
CROWN_LOAD = .85
UP = np.array([0., 0., 1.])
ACROSS = np.array([0., 1., 0.])
TRACKS = {
    'full': dict(name='Cathedral Grand Loop', base=(4032., -4204., 152.),
                 scale=1., width=11.5, offset=47., approach=312., runout=250.,
                 pitch=.83, join_x=4547., color='#ffb46b'),
    'compact': dict(name='Cathedral Switchback', base=(4060., -4025., 148.5),
                    scale=.45, width=6.7, offset=26., approach=215., runout=220.,
                    pitch=.69, join_x=4630., color='#d38bff'),
}


def loop_profile(spec):
    def angle(u):
        return 2 * np.pi * u**2 * (3 - 2 * u)

    def derivative(u, state):
        turn = angle(u)
        load = PEAK_LOAD - (PEAK_LOAD - CROWN_LOAD) * (.5 - .5*np.cos(turn))**8
        speed2 = REFERENCE**2 - 2 * GRAVITY * state[1]
        radius = max(2., speed2 / (GRAVITY * (load - np.cos(turn))))
        # The entry and exit ease to zero curvature where they meet flat track.
        ease = 310. * np.exp(-55. * min(u, 1-u))
        arc = radius * 12 * np.pi * u * (1-u) + ease
        return arc * np.cos(turn), arc * np.sin(turn), arc

    solution = solve_ivp(derivative, (0, 1), [0., 0., 0.], rtol=1e-9,
                         atol=1e-9, dense_output=True, max_step=.004)
    u = np.linspace(0, 1, 3000)
    x, z, length = solution.sol(u) * spec['scale']
    s = np.linspace(0, length[-1], math.ceil(length[-1]/spec['pitch'])+1)
    turn = angle(np.interp(s, length, u))
    x = np.interp(s, length, x)
    z = np.interp(s, length, z)
    # Dimension the sideways stagger independently from vehicle power or grip.
    # Open the limbs out modestly around the slower crown, then carry the
    # same heading into the approach and braking deck.
    roll_speed = np.sqrt(REFERENCE**2 * spec['scale'] - 2 * GRAVITY * z / 1.4)
    roll_time = cumulative_trapezoid(1./roll_speed, s, initial=0.)
    side_speed = spec['offset']/roll_time[-1]
    y = side_speed * roll_time
    centers = np.column_stack((x, y, z)) + spec['base']
    normals = np.column_stack((-np.sin(turn), np.zeros(len(s)), np.cos(turn)))
    axis = np.array([1., side_speed / roll_speed[0], 0.])
    directions = np.gradient(s)/np.maximum(1e-8, np.gradient(turn))
    crown_radius = directions[len(s)//2]
    # Check the projected separation of the two crossing limbs.
    cross = int(np.argmin(abs(x[:len(x)//2] - x[-1]/2)))
    clearance = y[-1-cross]-y[cross]-spec['width']
    if clearance < 3.:
        raise ValueError(f"Loop crossover only {clearance:.2f} m clear")
    return centers, normals, axis, dict(height_m=float(z.max()),
        crown_radius_m=float(crown_radius),
        projected_crossover_edge_gap_m=float(clearance),
        nominal_entry_kph=float(3.6*REFERENCE*math.sqrt(spec['scale'])),
        loop_length_m=float(np.linalg.norm(np.diff(centers, axis=0), axis=1).sum()))


def ease(p):
    return p**3 * (10 - 15*p + 6*p*p)


def approach_deck(world, base, axis, length, width, sense):
    # Sink the final outer joint into the existing terrain, where the roadway
    # meets its painted at-grade connector. The central loop stays above grade.
    n = math.ceil(length / 4.)
    distance = np.linspace(0., length, n+1)
    points = base + distance[:, None] * sense * axis
    blend = ease(np.clip((distance - (length-115.))/115., 0., 1.))
    for i, xy in enumerate(points[:, :2]):
        ground = min(world.terrain_z(*(xy + [0., y])) for y in (-width/2, 0., width/2))
        points[i, 2] = (1-blend[i])*base[2] + blend[i]*(ground-.18)
    pitch = np.gradient(points[:, 2])/np.gradient(points[:, 0])
    normals = np.column_stack((-pitch, np.zeros(len(pitch)), np.ones(len(pitch))))
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    bank = 1. - ease(np.clip((distance-(length-125.))/90., 0., 1.))
    return points, normals, bank


def deck_vertices(center, normal, bank, half_width):
    # A broad flat center and two sloped shoulders. The crossfall follows the
    # local road normal when the rider goes upside down.
    return np.array([
        center - half_width*ACROSS + .39*half_width*bank*normal,
        center - .34*half_width*ACROSS,
        center + .34*half_width*ACROSS,
        center + half_width*ACROSS + .39*half_width*bank*normal,
    ])


def panels(masonry, key, points, normals, banks, width):
    cross = np.array([deck_vertices(p, v, b, width/2)
                      for p, v, b in zip(points, normals, banks)])
    for i, delta in enumerate(np.diff(points, axis=0)):
        tangent = delta/np.linalg.norm(delta)
        for strip in range(3):
            hull = []
            for j, end in ((i, -.02), (i+1, .02)):
                for vertex in cross[j, strip:strip+2]:
                    top = vertex + end*tangent
                    hull.extend((top, top-.75*normals[j]))
            masonry.hull(f'vertical-loop-{key}-deck-{i:04d}-{strip}', hull,
                         'loopBed' if strip == 1 else 'loopBank')
            masonry.solids[-1]['role'] = 'deck'
    return cross


def mount(masonry, world, key, xy, cap, width):
    x, y = xy
    ground = min(world.terrain_z(x+i*1.8,y+j*2.2) for i in (-1,1) for j in (-1,1))
    if cap < ground+.55:
        return
    stem = masonry.box(f'vertical-loop-{key}-foot',x,y,ground-.7,cap-.33,
                       1.25,1.58,'loopStone')
    masonry.box(f'vertical-loop-{key}-cap',x,y,cap-.4,cap,1.25,width/2,
                'loopMetal',parent=stem)


def beam(masonry, name, a, b, thickness, skin, **attrs):
    axis = b-a
    axis /= np.linalg.norm(axis)
    u = np.cross(axis, [0.,1.,0.] if abs(axis[1])<.9 else [1.,0.,0.])
    u *= thickness/np.linalg.norm(u)
    v = np.cross(axis, u)
    return masonry.hull('vertical-loop-'+name,
        [p+i*u+j*v for p in (a,b) for i in (-1,1) for j in (-1,1)], skin, **attrs)


def fittings(masonry, world, key, points, loop, normal, width, launch):
    for n, i in enumerate([*range(5, 44, 8), *range(len(points)-44, len(points)-4, 8)]):
        p = points[i]
        mount(masonry,world,f'{key}-pier-{n}',p[:2],p[2]-.68,width)
    crown = int(np.argmax(loop[:,2]))
    # Steel bents outside the wheel envelope carry the inverted crown. The
    # crossmember sits behind the road and never crosses the driven face.
    p = loop[crown] - normal[crown]*1.45
    reach = 18. if key == 'full' else 10.5
    low_y = float(loop[0,1] - reach)
    high_y = float(loop[-1,1] + reach)
    a, b = np.array([p[0],low_y,p[2]]), np.array([p[0],high_y,p[2]])
    top = beam(masonry,key+'-header',a,b,1.25,'loopMetal')
    for side in (a,b):
        name = 'south' if side is a else 'north'
        x,y,z = side
        gz = world.terrain_z(x,y)
        foot = masonry.box(f'vertical-loop-{key}-{name}-foot',x,y,gz-1.,gz+.45,
                           2.4,2.3,'loopStone')
        beam(masonry,f'{key}-{name}-stack',np.array([x,y,gz+.35]),side,
             1.32,'loopMetal',parent=foot)
        for k,direction in enumerate((-1.,1.)):
            bottom = np.array([x+direction*11., y, world.terrain_z(x+direction*11.,y)])
            sock = masonry.box(f'vertical-loop-{key}-{name}-shoe-{k}',*bottom[:2],
                               bottom[2]-.9,bottom[2]+.4,1.45,1.6,'loopStone')
            beam(masonry,f'{key}-{name}-brace-{k}',bottom+[0.,0.,.35],side-[0.,0.,11.],
                 .58,'loopMetal',parent=sock)
    glow = 'loopGold' if key=='full' else 'loopViolet'
    beam(masonry,key+'-header-trim',a+[-1.25,0.,.45],b+[-1.25,0.,.45],
         .16,glow,parent=top)
    for j, outer in enumerate((a,b)):
        x,y,z = outer
        low = world.terrain_z(x,y)+.5
        mast_foot = np.array([x,y,low])
        for face in (-1.,1.):
            off = np.array([face*1.04,-1.30,0.])
            beam(masonry,f'{key}-track-mast-{j}-{face}',mast_foot+off,
                 outer+off,.15,glow,parent=top)
        # Cross braces keep the illuminated outer edges readable against sky.
        for k,h in enumerate(np.linspace(low+2.,z-6.,max(2,int((z-low)/9.)))):
            brace_a = np.array([x-1.29,y-1.32,h])
            brace_b = np.array([x+1.29,y-1.32,h+3.4])
            beam(masonry,f'{key}-mast-tie-{j}-{k}',brace_a,brace_b,.20,'loopMetal',
                 parent=top)

    p = launch
    sign_reach = width/2 + 1.45
    floor = p[2]
    header = floor+7.6
    for side in (-1,1):
        xy = p[:2] + [0.,side*sign_reach]
        base = world.terrain_z(*xy)
        foot = masonry.box(f'vertical-loop-{key}-entry-base-{side}',*xy,base-.7,base+.32,
                           1.55,.82,'loopStone')
        pier = masonry.box(f'vertical-loop-{key}-entry-post-{side}',*xy,base+.23,header,
                            .63,.44,'loopMetal',parent=foot)
        masonry.box(f'vertical-loop-{key}-entry-light-{side}',xy[0]-.52,xy[1],floor+.45,
                    header-.97,.13,.29,'loopGold' if key=='full' else 'loopViolet',parent=pier)
    masonry.box(f'vertical-loop-{key}-entry-bar',*p[:2],header-.85,header+.72,.62,
                sign_reach+.48,'loopMetal')
    return [float(p[0]-.626),float(p[1]),float(header-.06)]


def cubic(name, width, start, end, direction0, direction1, color):
    start, end = np.asarray(start), np.asarray(end)
    reach = np.linalg.norm(end-start) * .40
    start_handle = start + reach*direction0/np.linalg.norm(direction0)
    end_handle = end - reach*direction1/np.linalg.norm(direction1)
    t = np.linspace(0, 1, 80)[:, None]
    p = (1-t)**3*start+3*(1-t)**2*t*start_handle+3*(1-t)*t**2*end_handle+t**3*end
    return dict(name=name,kind='experimental',width_m=width,
                points=p.round(5).tolist(),edge_color=color)


def join(road, x):
    xy = np.asarray(road['points'])
    i = int(np.searchsorted(xy[:,0],x))
    before, after = xy[i-1:i+1]
    return np.array([x,np.interp(x,xy[:,0],xy[:,1])]),after-before


def make_loops(world):
    masonry = Masonry()
    tracks, roads, runs = [], [], {}
    east = next(r for r in world.vaderland['routes'] if r['name']=='Gallery east approach')
    for key,spec in TRACKS.items():
        loop, normal, axis, metrics = loop_profile(spec)
        width, color = spec['width'],spec['color']
        launch, ln, lb = approach_deck(world,loop[0],axis,spec['approach'],width,-1)
        brake, bn, bb = approach_deck(world,loop[-1],axis,spec['runout'],width,1)
        points = np.vstack((launch[:0:-1],loop,brake[1:]))
        normals = np.vstack((ln[:0:-1],normal,bn[1:]))
        banks = np.r_[lb[:0:-1],np.ones(len(loop)),bb[1:]]
        cross = panels(masonry,key,points,normals,banks,width)
        gate = int(np.argmin(abs(points[:,0]-(launch[-1,0]+82.))))
        sign = fittings(masonry,world,key,points,loop,normal,width,points[gate])
        if key == 'full':
            start,direction = join(east,3532.)
        else:
            start,direction = join(roads[0],3644.)
        access=cubic(spec['name']+' access',width,start,launch[-1,:2],
                     direction,axis[:2],color)
        spawn = next((xy for xy in access['points']
                      if (key=='full' or np.linalg.norm(xy-start)>43.) and
                      world.validate(MapPoint(x_m=xy[0],y_m=xy[1]),'departure').valid), None)
        if spawn is None:
            raise ValueError(f'No supported departure on {spec["name"]} access')
        # Extend the ground paint under the deck's buried joints so there is
        # a continuous visible traffic ribbon as the structure clears grade.
        access['points'].append((launch[-1,:2]+axis[:2]*31.).round(5).tolist())
        end,direction = join(east,spec['join_x'])
        back=cubic(spec['name']+' return',width,brake[-1,:2],end,
                   axis[:2],direction,color)
        back['points'].insert(0,(brake[-1,:2]-axis[:2]*26.).round(5).tolist())
        roads.extend((access,back))

        # The map uses the real plan projection, including the offset between
        # limbs. The terrain renderer leaves the elevated ribbons to WebGL.
        roads.append(dict(name=spec['name'],kind='vertical-loop',width_m=width,
            edge_color=color,points=points[:-1:3,:2].round(5).tolist()+[points[-1,:2].round(5).tolist()]))
        tracks.append(dict(id=key,name=spec['name'],color=color,width_m=width,
            entry=start.round(5).tolist(),spawn=spawn,launch=launch[-1,:2].round(5).tolist(),
            exit=brake[-1,:2].round(5).tolist(),sign=sign,
            approach_m=round(float(np.linalg.norm(np.diff(launch,axis=0),axis=1).sum()),2),
            runout_m=round(float(np.linalg.norm(np.diff(brake,axis=0),axis=1).sum()),2),
            **metrics,cross_sections=cross.round(5).tolist(),
            normals=normals.round(7).tolist(),stations=points.round(6).tolist(),
            loop_in=len(launch)-1,loop_out=len(launch)+len(loop)-2))
        runs[key]=(points,cross,normals)
    legacy = StreetIndex(world)
    overlaps = {o['id']:hit for o in masonry.solids if (hit:=legacy.overlaps(o,headroom=6.6))}
    if overlaps:
        raise ValueError(f'Existing road obstruction: {overlaps}')
    old = [o for o in world.obstacles if 3510<o['center'][0]<4680 and -4350<o['center'][1]<-3760]
    new = StreetIndex(world,[r for r in roads if r['kind']=='experimental'])
    if hits := {o['id']:hit for o in old if (hit:=new.overlaps(o,headroom=5.))}:
        raise ValueError(f'Access obstruction: {hits}')
    check_clearance(masonry.solids,runs)
    return dict(solids=masonry.solids,roads=roads,tracks=tracks)


def check_clearance(solids,runs):
    # Test the wheel ribbon against neighboring limbs and all structures. Checks
    # are in the local road frame so they apply equally to the inverted crown.
    centers = np.asarray([o['center'] for o in solids])
    halves = np.asarray([o['half'] for o in solids])
    planes = [np.asarray(o['planes']) for o in solids]
    for key,(stations,cross,normals) in runs.items():
        for i,(p,borders,n) in enumerate(zip(stations,cross,normals)):
            if i in (0,len(stations)-1):
                continue
            probe = np.vstack([borders[1]*a+borders[2]*(1-a)+z*n
                               for a in (.02,.5,.98) for z in (.08,.35,1.5,3.5,5.)])
            nearby = np.flatnonzero(np.all(abs(centers-p)<halves+[6.5,8.,6.5],axis=1))
            for j in nearby:
                name=solids[j]['id']
                if '-deck-' in name and name.startswith(f'vertical-loop-{key}-'):
                    segment=int(name.split('-')[-2])
                    if abs(segment-i)<=2:
                        continue
                hull=planes[j]
                if np.any(np.all((probe-centers[j]) @ hull[:,:3].T+hull[:,3] < -.02,axis=1)):
                    raise ValueError(f'{key} station {i}, {name} in the driven envelope')


if __name__=='__main__':
    design = make_loops(MeridianHandlingYard())
    target = PACK / 'vertical-loops-26.json.gz'
    payload=json.dumps(design,separators=(',',':'),allow_nan=False).encode()
    target.write_bytes(gzip.compress(payload,compresslevel=9,mtime=0))
    for track in design['tracks']:
        print(track['name'], {k:round(v,2) for k,v in track.items() if isinstance(v,float)})
    print(len(design['solids']),'convex scenery hulls')