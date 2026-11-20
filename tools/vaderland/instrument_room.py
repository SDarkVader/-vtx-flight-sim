"""Open one real workshop in the original Parallax podium and bake its physical fixtures."""
import gzip
import json
import math

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull

from drafting import Masonry
from parallax_review import planes
from streets import StreetIndex
from vtx.meridian_parallax import ParallaxCourt
from vtx.vaderland import PACK


def clip(polygon, axis, limit, sign):
    result = []
    previous = polygon[-1]
    for point in polygon:
        a = sign * (previous[axis] - limit)
        b = sign * (point[axis] - limit)
        if (a < 0) != (b < 0):
            result.append(previous + (point - previous) * (a / (a - b)))
        if b >= 0:
            result.append(point)
        previous = point
    return np.array(result)


def touching(a, b):
    hull = np.vstack((planes(a), planes(b)))
    result = linprog(np.zeros(3), A_ub=hull[:, :3], b_ub=-hull[:, 3],
                     bounds=[(None, None)] * 3, method='highs')
    return result.success


def author(world):
    court = world.vaderland['parallax_court']
    origin = np.array([*court['door'], court['datum']])
    basis = np.array([(*court['axis'], 0), (*court['front'], 0), (0, 0, 1)])
    base = origin[2]
    original = next(o for o in world.obstacles if o['id'] == 'market-block-17-shops')
    m = Masonry()
    index = {}

    def build(name, cloud, material, parent=None, **attributes):
        key = m.hull(name, np.asarray(cloud) @ basis + origin, material, parent=parent, **attributes)
        index[key] = m.solids[-1]
        return key

    def box(name, u, d, z, material, parent=None, **attributes):
        return build('instrument-' + name, [(x,y,h) for x in u for y in d for h in z],
                     material, parent, **attributes)

    def band(name, xy, bottom, top):
        return build(name, [[*p,z] for p in xy for z in (bottom,top)], original['skin'],
                     city=True, datum_m=original['datum_m'], tenancy=original['tenancy'],
                     front=original['front'], landable=original['landable'])

    footprint = (np.asarray(original['vertices']) + original['center'] - origin) @ np.linalg.inv(basis)
    points = np.unique(np.round(footprint[:, :2], 5), axis=0)
    plan = points[ConvexHull(points).vertices]
    low, high = footprint[:, 2].min(), footprint[:, 2].max()
    centre = clip(clip(plan, 0, -8.85, 1), 0, 8.85, -1)
    floor_z, ceiling_z, rear = .32, 5.62, -11.2
    floor = band('market-block-17-instrument-base', centre, low, floor_z)
    header = band(original['id'], centre, ceiling_z, high)
    left = band('market-block-17-instrument-south', clip(plan, 0, -8.85, -1), low, high)
    right = band('market-block-17-instrument-north', clip(plan, 0, 8.85, 1), low, high)
    back = band('market-block-17-instrument-back', clip(centre, 1, rear, -1), floor_z, ceiling_z)
    # The surviving facade and header carry the court's original cantilever attachments.
    supports = {}
    for o in world.obstacles:
        if o.get('parent') != original['id']:
            continue
        for alternative in (header, left, right, back, floor):
            if touching(o, index[alternative]):
                supports[o['id']] = alternative
                break
        else:
            raise ValueError(f'No bearing for {o["id"]}')

    skirting = box('stone-floor',(-8.84,8.84),(rear,-.018),(floor_z-.008,floor_z+.047),'roomFloor',floor)
    floor_top = floor_z + .047
    ramp_base = min(world.terrain_z(*(np.array([u,d,0]) @ basis + origin)[:2])-base
                    for u in (-1.42,1.42) for d in (-.035,1.92))
    ramp = [(u,d,z) for u in (-1.42,1.42)
            for d,h in [(-.035,floor_top),(1.92,ramp_base+.035)]
            for z in (ramp_base-.17,h)]
    build('instrument-door-ramp',ramp,'roomFloor',skirting)
    box('rear-lining',(-8.84,8.84),(rear-.006,rear+.16),(floor_top-.01,ceiling_z),
        'roomStone',skirting)
    for side, parent in ((-1,left),(1,right)):
        box(f'lining-{side}',sorted([side*8.63,side*8.88]),(rear,-.018),
            (floor_top-.02,ceiling_z+.015),'roomStone',parent)
    soffit = box('ceiling',(-8.85,8.85),(rear,0.),(5.47,ceiling_z+.022),'roomStone',header)
    for i,u in enumerate(np.arange(-8.75,8.76,1.75)):
        box(f'roof-rib-{i}',(u-.038,u+.038),(rear+.01,-.17),(5.374,5.51),'roomMetal',soffit)

    # Visible glazing has real thickness. The central aperture has its own threshold and lintel.
    frame = box('window-header',(-8.86,8.86),(-.17,.082),(4.80,5.65),'roomMetal',header)
    for i,u in enumerate((-8.80,-6.91,-5.04,-3.17,-1.28,1.28,3.17,5.04,6.91,8.80)):
        box(f'glass-mullion-{i}',(u-.057,u+.057),(-.183,.064),(floor_top-.022,4.88),'roomMetal',frame)
    for side in (-1,1):
        offsets = (1.28,3.17,5.04,6.91,8.80)
        z0 = floor_top+.39
        sill = box(f'sill-{side}',sorted([side*offsets[0],side*offsets[-1]]),(-.17,.105),
                   (floor_top-.009,z0),'roomMetal',skirting)
        for i,(a,b) in enumerate(zip(offsets,offsets[1:])):
            box(f'pane-{side}-{i}',sorted([side*(a+.046),side*(b-.046)]),(-.079,-.052),
                (z0-.006,4.83),'roomGlass',sill)
    box('entry-transom',(-1.326,1.326),(-.19,.087),(3.15,4.84),'roomMetal',frame)
    box('entry-light',(-1.16,1.16),(.074,.102),(3.30,3.34),'roomCyan','instrument-entry-transom')
    for side in (-1,1):
        # Rebate the external reveal and return the bronze frame into the glazing.
        for i,(a,b) in enumerate(zip((.40,1.21,2.13,3.06,3.96),(1.21,2.13,3.06,3.96,4.86))):
            def rim(z):
                t=z/4.86
                u=side*(1.41+.18*math.sin(t*math.pi))
                d=.099+.12*math.sin(t*math.pi*.88)
                return [(u+x,d+y,z, ) for x in (-.10,.10) for y in (-.118,.062)]
            parent = ('instrument-glass-mullion-4' if side < 0 else 'instrument-glass-mullion-5') if i==0 else f'instrument-reveal-{side}-{i-1}'
            # A straight inner flange keys the bowed reveal to the jamb all the way up.
            cloud = rim(a)+rim(b)+[(side*1.28,-.018,z) for z in (a,b)]
            detail=build(f'instrument-reveal-{side}-{i}',cloud,'roomBronze',parent)
            if i%2==0:
                span=sorted((side*1.41,side*1.46))
                d=.11+.12*math.sin((a+.18)/4.86*math.pi*.88)
                box(f'reveal-diodes-{side}-{i}',span,(d-.033,d+.009),(a+.08,a+.26),'roomWarm',detail)

    def circular(u,d,levels,sections=24):
        return [(u+r*math.cos(a),d+r*math.sin(a),z)
                for z,r in levels for a in np.arange(sections)*math.tau/sections]

    exhibit_u, exhibit_d, pivot_z = -4.18,-5.57,2.85
    pedestal = build('instrument-orrery-foot',circular(exhibit_u,exhibit_d,
                     [(floor_top-.014,1.78),(.57,1.74),(.79,1.53),(.94,1.41)]),
                     'roomWood',skirting)
    trim = build('instrument-orrery-base',circular(exhibit_u,exhibit_d,
                 [(.89,1.40),(1.01,1.45),(1.11,1.26)]),'roomBronze',pedestal)
    bearing = build('instrument-orrery-bearing',circular(exhibit_u,exhibit_d,
                    [(1.06,.49),(1.25,.39),(2.91,.12)],16),'roomMetal',trim)
    lamp = build('instrument-orrery-core',circular(exhibit_u,exhibit_d,
                 [(2.69,.16),(2.79,.25),(3.00,.25),(3.12,.13)],16),'roomCyan',bearing)
    pivot = (np.array([exhibit_u,exhibit_d,pivot_z]) @ basis + origin).tolist()

    def arc(name,radius,tilt,rot,motion,parent,metal,accent):
        for j in range(40):
            a = -math.pi*.5 + j*math.tau/40
            b = -math.pi*.5 + (j+1)*math.tau/40
            def section(t, width, depth, shift=0.):
                x = (radius+width)*math.cos(t)
                z = (radius+width)*math.sin(t)
                y = depth+z*math.sin(tilt)
                return exhibit_u+math.cos(rot)*x-math.sin(rot)*y,exhibit_d+math.sin(rot)*x+math.cos(rot)*y,pivot_z+z*math.cos(tilt)+shift
            cloud = [section(t,w,d) for t in (a,b) for w in (-.080,.080) for d in (-.071,.071)]
            key = 'instrument-orbit-'+name+'-'+str(j)
            attrs = {'motion':motion} if motion else {}
            parent = build(key,cloud,metal,parent,**attrs)
            if j % 4 == 1:
                color = [section(t,w,d) for t in (a+.014,b-.017) for w in (-.041,.041) for d in (.066,.081)]
                build(key+'-lamp',color,accent,parent,**attrs)
    arc('meridian',1.74,0.,.24,None,trim,'roomBronze','roomWarm')
    for k, radius in enumerate((1.34,.98)):
        turn = (.14,.92)[k]
        spec = {'name':f'instrument-ring-{k}','origin':pivot,'period_s':(39.,67.)[k]}
        # The rotating hoop bears on a vertical pin through its bottom vertex.
        lower = pivot_z-radius*math.cos(turn)
        collar = build(f'instrument-collar-{k}',circular(exhibit_u,exhibit_d,
                       [(lower-.09,.35),(lower+.042,.35)],20),'roomBronze',bearing,motion=spec)
        link=box(f'pin-link-{k}',(exhibit_u-.071,exhibit_u+.071),
                 (exhibit_d-radius*math.sin(turn)-.08,exhibit_d+.22),
                 (lower-.09,lower+.025),'roomBronze',collar,motion=spec)
        pin = build(f'instrument-pin-{k}',circular(exhibit_u,exhibit_d-radius*math.sin(turn),
                    [(lower-.14,.165),(lower+.12,.16)],12),'roomBronze',link,motion=spec)
        arc(str(k),radius,turn,0.,spec,pin,'roomBronze',('roomCyan','roomWarm')[k])

    # Repeated lamps trace a real ceiling circle with a dark gap around the central exhibit.
    lights = []
    for j in range(36):
        a,b = j*math.tau/36,(j+1)*math.tau/36
        def ceiling_strip(r0,r1,z0,z1, gap=0.):
            return [(-2.2+r*math.cos(t),-5.8+r*math.sin(t),z)
                    for t in (a+gap,b-gap) for r in (r0,r1) for z in (z0,z1)]
        brass=build(f'instrument-ceiling-track-{j}',ceiling_strip(2.83,3.02,5.35,5.50),'roomBronze',soffit)
        build(f'instrument-ceiling-light-{j}',ceiling_strip(2.88,2.96,5.335,5.376,.020),'roomWarm',brass)
        if j % 4 == 0:
            lights.append([-2.2+2.92*math.cos(a),-5.8+2.92*math.sin(a),5.30,1.])

    # Instrument-maker's bench with real circular housings, controls, and salvaged optical parts.
    bench_profile = [(2.84,-9.83),(7.88,-9.83),(8.04,-9.56),(8.04,-8.96),(7.65,-8.59),
                     (3.18,-8.59),(2.76,-8.89),(2.72,-9.48)]
    bench = build('instrument-bench-chassis',[[u,d,z] for u,d in bench_profile
                 for z in (floor_top-.013,1.19)],'roomWood',skirting)
    desk = build('instrument-bench-top',[[u,d,z] for u,d in bench_profile
                  for z in (1.173,1.34)],'roomBronze',bench)
    box('bench-inlay',(3.14,7.73),(-8.609,-8.566),(.58,.613),'roomWarm',bench)
    for j,u in enumerate(np.arange(3.19,7.79,.21)):
        h=.017+.018*(j%4)
        box(f'bench-reed-{j}',(u-h,u+h),(-8.599,-8.562),(.435,1.176),'roomWood',bench)

    def face_cylinder(name,u,d,z,r,thick,skin,parent,sections=24):
        points=[(u+r*math.cos(a),d+b,z+r*math.sin(a))
                for a in np.arange(sections)*math.tau/sections
                for b in (-thick/2,thick/2)]
        return build('instrument-'+name,points,skin,parent)

    for j,(u,r) in enumerate(((3.26,.21),(4.23,.27),(5.39,.32),(6.55,.245),(7.48,.19))):
        body = box(f'bench-cradle-{j}',(u-r*.60,u+r*.60),(-9.42,-9.10),(1.32,1.60),'roomMetal',desk)
        collar = face_cylinder(f'bench-gauge-{j}',u,-9.19,1.64+r*.20,r,.18,'roomBronze',body)
        face_cylinder(f'gauge-light-{j}',u,-9.093,1.64+r*.20,r*.82,.022,
                      f'roomDial{j%2}',collar)
        knob = face_cylinder(f'bench-knob-{j}',u+r+.07,-9.09,1.388,.058,.075,'roomMetal',desk,14)
        face_cylinder(f'knob-index-{j}',u+r+.07,-9.047,1.388,.021,.017,'roomCyan',knob,12)
        lights.append([u,-8.97,1.64,0.])

    for j,z in enumerate((1.94,2.69,3.51,4.33)):
        shelf = box(f'shelf-{j}',(2.44,8.60),(rear+.091,-10.56),(z,z+.098),
                    'roomBronze','instrument-rear-lining')
        box(f'shelf-reveal-{j}',(2.53,8.50),(-10.59,-10.554),(z+.029,z+.055),'roomWarm',shelf)
        for k in range(8):
            u=2.77+.68*k
            h=.13+.27*(.5+.5*math.sin(k*3.19+j))
            if (j+k)%3 == 0:
                build(f'instrument-canister-{j}-{k}',circular(u,-10.86,
                      [(z+.086,.16),(z+.12,.192),(z+h,.192),(z+h+.08,.131)],14),
                      ('roomMetal','roomBronze')[j%2],shelf)
            else:
                box(f'parts-case-{j}-{k}',(u,u+.23+.04*(k%2)),(-11.03,-10.71),
                    (z+.087,z+h+.078),'roomWood',shelf)

    # A wall-mounted instrument rack, optically dark brass with engraved faces.
    rack = box('rear-rack',(-8.59,-1.30),(rear+.129,rear+.321),(1.96,4.58),
               'roomWood','instrument-rear-lining')
    for u,z,r in [(-7.31,3.23,.75),(-5.39,3.28,.65),(-3.60,3.43,.54),(-2.28,2.94,.40)]:
        i=round(abs(u)*10)
        backplate = face_cylinder(f'wall-meter-{i}',u,rear+.315,z,r,.21,'roomBronze',rack,36)
        face_cylinder(f'wall-dial-{i}',u,rear+.43,z,r*.87,.026,
                      f'roomDial{i%2}',backplate,32)
    for i in range(19):
        u=-8.39+i*.372
        box(f'rear-rack-rib-{i}',(u-.029,u+.029),(rear+.314,rear+.414),(2.03,2.40),
             'roomBronze',rack)
    lights.append([-5.9,rear+1.09,4.13,1.])
    rack_key = box('rear-rack-light',(-8.28,-1.57),(rear+.285,rear+.429),(4.44,4.56),
                    'roomBronze',rack)
    box('rear-rack-glow',(-8.12,-1.73),(rear+.412,rear+.438),(4.447,4.472),'roomWarm',rack_key)

    # Inboard end of the atelier holds two working stools behind the public walking line.
    for j,u in enumerate((3.84,6.72)):
        foot = build(f'instrument-stool-foot-{j}',circular(u,-7.68,
                     [(floor_top-.014,.37),(.47,.37)]),'roomMetal',skirting)
        leg = build(f'instrument-stool-leg-{j}',circular(u,-7.68,
                    [(.45,.113),(.93,.113)],16),'roomBronze',foot)
        build(f'instrument-stool-seat-{j}',circular(u,-7.68,
              [(.909,.27),(.996,.31),(1.039,.285)]),'roomWood',leg)
    # Curved services screen around the exhibit, with open vertical shadow gaps.
    for i in range(16):
        u=-8.49+.43*i
        d=rear+.48+.88*((u+4.6)/4.)**2
        ped = box(f'exhibit-channel-{i}',(u-.072,u+.072),(d-.09,d+.08),
                  (floor_top-.021,1.91),'roomWood',skirting)
        box(f'exhibit-brass-line-{i}',(u-.019,u+.019),(d+.068,d+.092),
            (.56,1.86),'roomBronze',ped)
        box(f'exhibit-valance-{i}',(u-.072,u+.072),(d-.09,d+.08),
            (4.67,5.50),'roomWood',soffit)
    shelf_axis = (3.0,7.75)
    lens_foot = box('optic-foot',shelf_axis,(-5.83,-4.02),(floor_top-.012,.58),'roomMetal',skirting)
    for i,u in enumerate((3.20,7.55)):
        box(f'optic-leg-{i}',(u-.12,u+.12),(-5.55,-4.28),(.57,1.21),'roomBronze',lens_foot)
    optic_top = box('optic-bench',(3.10,7.64),(-5.73,-4.11),(1.158,1.285),'roomWood','instrument-optic-leg-0')
    box('optic-trim',(3.10,7.64),(-4.135,-4.084),(1.173,1.252),'roomBronze',optic_top)
    rail = box('optic-rail',(3.4,7.28),(-5.22,-4.60),(1.27,1.443),'roomBronze',optic_top)
    for i,(u,r) in enumerate(((4.17,.38),(5.36,.46),(6.54,.34))):
        post = box(f'optic-mount-{i}',(u-.13,u+.13),(-5.05,-4.71),(1.43,2.0-r*.86),'roomMetal',rail)
        for j in range(24):
            a,b=-math.pi*.5+j*math.tau/24,-math.pi*.5+(j+1)*math.tau/24
            cloud=[(u+z,-4.89+q*math.cos(t),2.0+q*math.sin(t))
                   for t in (a,b) for q in (r-.087,r) for z in (-.08,.08)]
            parent = post if j==0 else f'instrument-optic-ring-{i}-{j-1}'
            build(f'instrument-optic-ring-{i}-{j}',cloud,'roomBronze',parent)
        optic = [(u+t,-4.89+(r-.066)*math.cos(a),2.0+(r-.066)*math.sin(a))
                 for a in np.arange(24)*math.tau/24 for t in (-.019,.019)]
        build(f'instrument-optic-lens-{i}',optic,'roomOptic',f'instrument-optic-ring-{i}-0')
    box('optic-index',(3.42,7.24),(-4.612,-4.593),(1.354,1.375),'roomCyan',rail)

    # A bronze fascia frames the shop and hides the header's service cavity.
    bronze_fascia=box('entry-fascia',(-8.79,8.79),(.078,.142),(4.91,5.36),'roomBronze',frame)
    for j,z in enumerate((4.955,5.278)):
        box(f'fascia-lamp-{j}',(-8.51,8.51),(.138,.153),(z,z+.018),
            ('roomWarm','roomBronze')[j],bronze_fascia)

    streets=StreetIndex(world)
    issues={o['id']:hit for o in m.solids if (hit:=streets.overlaps(o))}
    if issues:
        raise ValueError(issues)
    return {'solids':m.solids,'support_remap':supports,'replace':original['id'],
            'room':{'origin':origin.tolist(),'basis':basis.tolist(),'lights':lights,'floor_m':floor_top,
                    'length_m':11.2,'width_m':17.7,'door_width_m':2.446}}


if __name__ == '__main__':
    raw=json.dumps(author(ParallaxCourt()),separators=(',',':'),allow_nan=False).encode()
    (PACK/'instrument-room-21.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
