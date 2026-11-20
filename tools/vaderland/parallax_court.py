"""Bake the Parallax Court canopy, garden walls, and survey paving."""
import gzip
import json
import math

import numpy as np

from drafting import Masonry
from streets import StreetIndex
from vtx.meridian_parallax import MeridianParallax
from vtx.vaderland import PACK


def author(world):
    lot = next(x for x in world.vaderland['quarter']['lots'] if x['id'] == 'market-block-17-shops')
    door = np.asarray(lot['door'])
    matrix = np.array([lot['axis'], lot['front']])
    base = lot['datum']
    m = Masonry()

    def at(u, d):
        return door + np.array([u, d]) @ matrix

    def prism(name, points, material, parent=None):
        vertices = [[*at(u, d), base + z] for u, d, z in points]
        return m.hull('court-' + name, vertices, material, parent=parent)

    def profile(t, f):
        # The fascia flares over the forecourt and pulls back at both ends of the frontage.
        envelope = math.cos(t * math.pi * .5) ** 1.32
        u = t * (20.0 + .68 * f) - 1.55 * f
        d = -.56 + f * (8.4 + 5.6 * envelope)
        ridge = 4.76 + 4.28 * envelope + .92 * t
        z = ridge + (1.80 * envelope - .24) * math.sin(f * math.pi * .68) - .93 * f * f
        return u, d, z

    def section(a, b, f0, f1, low, high):
        return[(u, d, z + dz) for t in (a, b) for f in (f0, f1)
               for u, d, z in [profile(t, f)] for dz in (low, high)]

    lights = []
    for i in range(24):
        a, b = -1 + i / 12, -1 + (i + 1) / 12
        # The rear strip of each section bears directly on the existing facade.
        parent = 'market-block-17-upper' if 10 <= i <= 15 else lot['id']
        for j in range(5):
            parent = prism(f'canopy-{i}-{j}', section(a, b, j / 5, (j + 1) / 5, -.56, .34),
                           'courtShell', parent)
        trim = prism(f'lip-{i}', section(a, b, .968, 1.014, -.51, .26),
                     'courtBronze', parent)
        prism(f'light-{i}', section(a, b, .998, 1.009, -.58, -.42), 'courtAmber', trim)
        for j, f in enumerate((.31, .63)):
            panel = f'court-canopy-{i}-{int(f*5)}'
            rib = prism(f'soffit-rib-{i}-{j}', section(a, b, f-.030, f+.030, -.683, -.49),
                        'courtBronze', panel)
            if 2 <= i <= 21:
                prism(f'soffit-lamp-{i}-{j}', section(a+.009, b-.009, f-.009, f+.009, -.699, -.653),
                      'courtAmber', rib)
        if i % 2:
            u, d, z = profile((a+b)*.5, .63)
            lights.append([*at(u,d), base + z - .59])

    for i, t in enumerate((-.84, -.52, .45, .79)):
        u0, d0, z0 = profile(t, .93)
        u, d = u0 + (.64 if t < 0 else -.64), d0 - 2.20
        ground = min(world.terrain_z(*at(u+a, d+b)) for a in (-.8,.8) for b in (-.7,.7))
        leg = [(u, d, ground-base-.26, .54, .41),
               (u-.22, d+.25, z0*.58, .31, .31),
               (u0, d0, z0-.40, .49, .29)]
        points = [(x+a*s, y+b*r, z) for x,y,z,s,r in leg for a in (-1,1) for b in (-1,1)]
        prism(f'column-{i}', points, 'courtBronze')

    beds = []
    for i,(u,d,r,s,height) in enumerate([(-19,19,3.0,1.58,.62),(-14.5,18.8,1.93,1.43,.53),
                                        (-11.0,20.0,1.48,1.28,.51),(13.1,18.3,2.1,1.49,.60),
                                        (18.0,19.4,2.9,1.76,.64),(23.1,16.6,2.08,1.55,.54),
                                        (-27.5,11.2,2.68,1.43,.54),(-29.8,16.6,2.05,1.61,.61)]):
        angles = np.arange(16) * math.tau / 16
        ring = [(u+r*math.cos(a),d+s*math.sin(a)) for a in angles]
        lo = min(world.terrain_z(*at(x,y)) for x,y in ring)
        top = max(world.terrain_z(*at(x,y)) for x,y in ring) + height
        prism(f'bed-{i}', [(x,y,z-base) for x,y in ring for z in (lo-.20, top)], 'courtStone')
        tree = i in (0,4,6)
        if tree:
            trunk = [(u+radius*math.cos(a), d+radius*math.sin(a), z-base)
                     for radius,z in ((.16,top-.025),(.095,top+2.9))
                     for a in angles[::2]]
            prism(f'tree-{i}', trunk, 'courtBark', f'court-bed-{i}')
        if i == 3:
            # Fixed bronze armillary. Both upright rings bear on the bed through the common pedestal.
            foot = f'court-bed-{i}'
            pedestal = [(u+r*math.cos(a), d+r*math.sin(a), z-base)
                        for r,z in ((.63, top-.035),(.44, top+.54)) for a in angles]
            seat = prism('armillary-foot', pedestal, 'courtBronze', foot)
            ring_z = top-base+1.89
            for side, turn in enumerate((-.26,1.03)):
                parent = seat
                for j in range(24):
                    a = -math.pi*.5 + j*math.tau/24
                    b = -math.pi*.5 + (j+1)*math.tau/24
                    def section(radii, depth):
                        return [(u+math.cos(t)*r*math.cos(turn)-k*math.sin(turn),
                                 d+math.cos(t)*r*math.sin(turn)+k*math.cos(turn),
                                 ring_z+math.sin(t)*r)
                                for t in (a,b) for r in radii for k in depth]
                    parent = prism(f'armillary-ring-{side}-{j}',section((1.25,1.43),(-.095,.095)),
                                   'courtBronze',parent)
                    if side == 1 and j % 4 == 2:
                        prism(f'armillary-lens-{j}',section((1.35,1.40),(.085,.112)),
                              'courtTeal',parent)
        beds.append(dict(point=[*at(u,d), top], radii=[r,s], tree=tree, seed=i))

    # These are surface finishes draped onto the original terrain, with no raised road surface.
    boundary = [[13.,2349.8],[22.,2350.6],[46.,2350.7],[53.,2352.9],[61.,2353.5],
                [73.,2356.7],[73.,2399.2],[54.,2401.6],[46.,2391.6],
                [46.,2364.0],[22.,2362.1],[11.7,2361.1]]
    faces = [[0,1,11],[1,10,11],[1,2,10],[2,9,10],[2,3,9],[3,8,9],
             [3,7,8],[3,4,7],[4,5,7],[5,6,7]]
    paving = [[boundary[i] for i in face] for face in faces]
    streets = StreetIndex(world)
    overlaps = {s['id']: issues for s in m.solids if (issues := streets.overlaps(s))}
    if overlaps:
        raise ValueError(overlaps)
    storefronts = [[*parcel['door'], parcel['datum'] + 3.7] for parcel in world.vaderland['quarter']['lots']
                   if parcel['id'] in {f'market-block-{i}-shops' for i in range(13, 21)}]
    return dict(solids=m.solids, court=dict(paving=paving, lamps=lights, beds=beds, storefronts=storefronts,
                front=lot['front'], axis=lot['axis'], door=lot['door'], datum=base))


if __name__ == '__main__':
    package = author(MeridianParallax())
    raw = json.dumps(package, separators=(',', ':'), allow_nan=False).encode()
    (PACK / 'parallax-court-20.json.gz').write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    print(len(package['solids']), 'court solids checked against the road envelope')
