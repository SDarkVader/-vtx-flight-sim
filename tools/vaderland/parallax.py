"""Author the Parallax Exchange crown on its surveyed Meridian Avenue roof."""
import gzip
import json
import math

import numpy as np

from drafting import Masonry
from vtx.vaderland import MeridianCityLights, PACK


def author(world):
    roof = next(o for o in world.obstacles if o['id'] == 'market-block-17-roof')
    origin = np.array([*roof['center'][:2], roof['center'][2] + roof['half'][2]])
    masonry = Masonry()

    def solid(name, cloud, finish, parent):
        # The opening faces Meridian Avenue and the city to its east.
        xyz = np.asarray(cloud)[:, [1, 0, 2]] + origin
        return masonry.hull('parallax-' + name, xyz, finish, parent=parent)

    def ring(u, v, z, span, depth, turn=0):
        ang = np.arange(24) * math.tau / 24
        x, y = span * np.cos(ang), depth * np.sin(ang)
        return np.column_stack((u + x * math.cos(turn) - y * math.sin(turn),
                                v + x * math.sin(turn) + y * math.cos(turn),
                                np.full_like(x, z)))

    def wings(side, s):
        bow = math.sin(math.pi * s)
        return (side * (6.6 + 26.4 * bow + 2.8 * s),
                3.0 * s + side * 2.8 * bow,
                3.80 + 145.0 * s,
                7.0 - 3.6 * s, 12.6 - 6.4 * s, side * (.72 * s - .20))

    def band(side, s, dz, pad):
        u, v, z, span, depth, turn = wings(side, s)
        return ring(u, v, z + dz, span + pad, depth + pad, turn)

    def ribbon(side, s, edge):
        u, v, z, span, depth, turn = wings(side, s)
        # Both ribs are fixed to the outer shoulders of the curved glazing.
        uv = np.array([[side * span * a, edge * depth * b]
                       for a in (.63, .87) for b in (.54, .78)])
        rot = np.array([[math.cos(turn), math.sin(turn)], [-math.sin(turn), math.cos(turn)]])
        return np.column_stack((uv @ rot + [u, v], np.full(4, z)))

    plinth = solid('plinth', np.vstack((ring(0, 0, -.12, 19.0, 14.6),
                                       ring(0, 0, 3.95, 19.7, 14.9))),
                   'parallaxAlloy', roof['id'])
    tops = {}
    sections = 16
    for side in (-1, 1):
        parent = plinth
        for i in range(sections):
            a, b = i / sections, (i + 1) / sections
            shell = solid(f'wing-{side}-{i}', np.vstack((band(side, a, 0, 0), band(side, b, 0, 0))),
                          'parallaxGlass', parent)
            if i < sections - 1:
                seam = b - .004
                solid(f'eave-{side}-{i}', np.vstack((band(side, seam, -.70, .35),
                                                     band(side, seam, .05, .24))),
                      'parallaxAlloy', shell)
            for edge in (-1, 1):
                solid(f'rib-{side}-{edge}-{i}', np.vstack((ribbon(side, a, edge), ribbon(side, b, edge))),
                      'parallaxBronze', shell)
            parent = shell
        tops[side] = parent

    # The crown stays above the passage. Each continuous half bears on a wing.
    def saddle(s):
        u = s * 9.4
        z = 147.5 + 5.4 * (1 - abs(s) ** 1.6)
        return [[u, v, z + dz] for v in (.15, 6.25) for dz in (0, 1.65)]

    for side in (-1, 1):
        parent = tops[side]
        for i in range(4):
            a, b = side * (1 - i / 4), side * (1 - (i + 1) / 4)
            parent = solid(f'saddle-{side}-{i}', saddle(a) + saddle(b), 'parallaxAlloy', parent)
        u, v, z, _, _, turn = wings(side, 1)
        tip_height = 25.0 if side > 0 else 15.5
        tip_offset = 13.8 if side > 0 else 8.8
        foot = ring(u, v, z - .40, 2.8, 5.75, turn)
        tip = ring(u + side * tip_offset, v + 5.5, z + tip_height, .28, .85, turn)
        solid(f'fin-{side}', np.vstack((foot, tip)), 'parallaxBronze', tops[side])

    return dict(solids=masonry.solids, landmark=dict(name='Parallax Exchange',
                point=origin.tolist(), foundation=roof['id'], passage_height_m=150.0))


if __name__ == '__main__':
    design = author(MeridianCityLights())
    raw = json.dumps(design, separators=(',', ':'), allow_nan=False).encode()
    (PACK / 'parallax-19.json.gz').write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    print(len(design['solids']), 'shared Parallax Exchange hulls')
