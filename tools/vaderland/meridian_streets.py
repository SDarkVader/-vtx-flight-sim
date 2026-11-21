"""Bake Meridian's street layout in the clear space between the V33 buildings and race courses."""

import argparse
from collections import defaultdict
from heapq import heappop, heappush
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.world import make_world


MIN_X, MIN_Y, MAX_X, MAX_Y, CELL = -3450, 530, 3200, 5590, 5
RACE_KINDS = {'track', 'experimental', 'speedway', 'vertical-loop'}
WIDTHS = {'boulevard': 37, 'arterial': 23, 'street': 14, 'local': 10, 'lane': 6, 'cycleway': 4}
MAX_STREET_GRADE = .20

# Each named node is shared across its adjoining streets. The protected spines remain at their survey points.
NODES = {
    'airport-west': (-1200, 640), 'airport-centre': (0, 640), 'airport-east': (1260, 640),
    'south-gardens': (-1810, 900), 'south-court': (-645, 905), 'airfield-square': (540, 865),
    'east-works': (1730, 970), 'east-fields': (2530, 970), 'west-market': (-2310, 1550),
    'west-corner': (-2740, 1850), 'exchange-west': ('Exchange Boulevard', -2570, 2320),
    'exchange-west-inner': ('Exchange Boulevard', -1390, 2340),
    'exchange-east-inner': ('Exchange Boulevard', 1550, 2360),
    'exchange-east': ('Exchange Boulevard', 2780, 2300), 'west-crescent': (-2320, 2870),
    'west-court': (-1680, 2810), 'east-bend': (2720, 1900), 'east-green': (2670, 3030),
    'north-arc': (-2000, 4150), 'north-dell': (-1160, 4380),
    'north-park': ('Meridian Avenue', 53, 4355), 'north-terrace': (635, 4340),
    'east-terrace': (1550, 4440), 'east-rim': (2510, 4410),
    'north-east-court': (1370, 4250), 'west-overlook': (-2780, 4360),
    'west-north-court': (-2350, 4450), 'high-court': (-480, 4490),
    'north-end': ('Meridian Avenue', 88, 4500), 'east-race-approach': (1700, 1820),
    'east-inner-court': (1780, 2880), 'north-inner-court': (1680, 3620),
    'lower-market-edge': (-1300, 1590), 'south-east-court': (835, 1060),
    'west-rampart': (-2900, 3390), 'west-park': (-1280, 3450),
    'east-hollow': (2850, 3830), 'glass-court': (1300, 2840),
    'arch-lane': (-940, 1230), 'outer-lane': (-1270, 1310),
    'archive-entry': ('Archive street', -350, 2402),
    'exchange-court': ('Exchange Boulevard', -540, 2330),
    'press-court': (-518, 2535), 'market-shelf': (-980, 1640), 'mews-junction': (-736, 1830),
    'delivery-court': (-442, 2050), 'civic-crossing': ('Exchange Boulevard', -940, 2350),
    'upper-market': (-1000, 2570), 'neighbourhood-green': (-945, 3010),
    'inner-rim': (-510, 3340), 'terrace-steps': (-565, 3700),
    'exchange-east-court': ('Exchange Boulevard', 525, 2370),
    'glass-steps': (615, 2685), 'courtyard-fork': (706, 2965), 'bell-yard': (950, 3100),
    'lower-east-mews': (635, 2030), 'merchant-court': (1020, 1780),
}

# A few continuous distributor roads, deliberately staggered junctions, local loops, and short passages.
STREETS = [
    ('Garden Crescent', 'boulevard', 'airport-west', 'south-gardens', [(-1450, 735)]),
    ('West Gardens Road', 'arterial', 'south-gardens', 'west-market', [(-2060, 975), (-2190, 1190)]),
    ('Orchard Approach', 'street', 'west-market', 'west-corner', [(-2520, 1600)]),
    ('Western Exchange Approach', 'arterial', 'west-corner', 'exchange-west', [(-2760, 2090)]),
    ('Lower Garden Way', 'street', 'airport-west', 'south-court', [(-940, 705), (-750, 800)]),
    ('South Court Lane', 'local', 'south-court', 'airport-centre', [(-410, 940), (-225, 785)]),
    ('Station Forecourt', 'arterial', 'airport-centre', 'airfield-square', [(230, 695), (420, 745)]),
    ('Foundry Sweep', 'street', 'airfield-square', 'airport-east', [(675, 820), (960, 714)]),
    ('Foundry Court', 'local', 'airfield-square', 'south-east-court', [(638, 955)]),
    ('Foundry Alley', 'lane', 'south-east-court', 'east-works', [(1175, 1150), (1425, 1080)]),
    ('Runway Fringe Road', 'arterial', 'airport-east', 'east-works', [(1430, 690), (1650, 815)]),
    ('Kiln Fields Road', 'arterial', 'east-works', 'east-fields', [(1990, 1110), (2255, 1000)]),
    ('Lantern Bend', 'boulevard', 'east-fields', 'east-bend', [(2700, 1300), (2750, 1620)]),
    ('East Exchange Approach', 'arterial', 'east-bend', 'exchange-east', [(2800, 2050)]),
    ('East Reservoir Road', 'arterial', 'exchange-east', 'east-green', [(2970, 2530), (2820, 2840)]),
    ('Hollow Rise', 'street', 'east-green', 'east-hollow', [(2560, 3300), (2770, 3540)]),
    ('Terrace Rim', 'arterial', 'east-hollow', 'east-rim', [(2930, 4060), (2710, 4280)]),
    ('Long Northern Terrace', 'boulevard', 'east-rim', 'east-terrace', [(2210, 4370), (1820, 4475)]),
    ('Crown Parkway', 'arterial', 'east-terrace', 'north-terrace', [(1240, 4460), (890, 4410)]),
    ('Park Gate', 'street', 'north-terrace', 'north-park', [(350, 4300)]),
    ('Crown Terrace Side Road', 'local', 'north-terrace', 'north-east-court', [(840, 4290), (1150, 4250)]),
    ('West Exchange Crescent', 'boulevard', 'exchange-west', 'west-crescent', [(-2740, 2520), (-2540, 2750)]),
    ('Orchard Rise', 'arterial', 'west-crescent', 'west-rampart', [(-2470, 3020), (-2730, 3230)]),
    ('Quarry Paddock Road', 'street', 'west-rampart', 'north-arc', [(-2680, 3720), (-2350, 3930)]),
    ('High Orchard Spur', 'street', 'west-rampart', 'west-overlook', [(-3080, 3800), (-2980, 4190)]),
    ('Ridge Lane', 'lane', 'west-overlook', 'west-north-court', [(-2620, 4435)]),
    ('Upper Orchard Road', 'street', 'west-north-court', 'north-arc', [(-2210, 4430), (-2100, 4340)]),
    ('Crown Woodland Road', 'boulevard', 'north-arc', 'north-dell', [(-1660, 4230), (-1400, 4370)]),
    ('Woodland Crescent', 'arterial', 'north-dell', 'high-court', [(-1000, 4450), (-755, 4450)]),
    ('Northern Gate', 'street', 'high-court', 'north-end', [(-180, 4515)]),
    ('Crown Bike Cut', 'cycleway', 'high-court', 'north-park', [(-360, 4400), (-115, 4320)]),
    ('Garden Cross Lane', 'local', 'west-crescent', 'west-court', [(-2020, 3040), (-1830, 3000)]),
    ('Inner Exchange Rise', 'street', 'exchange-west-inner', 'west-court', [(-1480, 2520)]),
    ('Ridge Park Loop', 'street', 'west-court', 'west-park', [(-1510, 3140)]),
    ('Park Passage', 'cycleway', 'west-park', 'north-dell', [(-1510, 3770), (-1350, 4140)]),
    ('Lower Market Street', 'street', 'west-market', 'lower-market-edge', [(-1980, 1745), (-1700, 1750)]),
    ('Exchange Market Approach', 'street', 'lower-market-edge', 'exchange-west-inner', [(-1420, 1940)]),
    ('Market Back Lane', 'local', 'south-gardens', 'lower-market-edge', [(-1610, 1120), (-1600, 1350)]),
    ('Archive Passage', 'lane', 'south-court', 'arch-lane', [(-815, 1050)]),
    ('Camera Yard Cut', 'cycleway', 'arch-lane', 'outer-lane', [(-1090, 1160)]),
    ('Old Arch Lane', 'lane', 'outer-lane', 'lower-market-edge', [(-1340, 1450)]),
    ('Archive Carriage Alley', 'lane', 'archive-entry', 'exchange-court', [(-435, 2380)]),
    ('Press Walk', 'cycleway', 'archive-entry', 'press-court', [(-397, 2455), (-465, 2495)]),
    ('Shelf Street', 'street', 'lower-market-edge', 'market-shelf', [(-1130, 1515)]),
    ('Mews Crescent', 'local', 'market-shelf', 'mews-junction', [(-890, 1745)]),
    ('Delivery Passage', 'lane', 'mews-junction', 'delivery-court', [(-620, 1920), (-500, 1950)]),
    ('Archive Approach', 'local', 'delivery-court', 'exchange-court', []),
    ('Market Street', 'street', 'mews-junction', 'civic-crossing', [(-930, 1980)]),
    ('Coppersmith Alley', 'lane', 'civic-crossing', 'upper-market', [(-1000, 2480)]),
    ('Upper Market Fold', 'local', 'upper-market', 'neighbourhood-green', [(-1060, 2700), (-955, 2860)]),
    ('North Mews Cut', 'cycleway', 'neighbourhood-green', 'inner-rim', [(-820, 3180), (-650, 3220)]),
    ('Ward Terrace Road', 'street', 'inner-rim', 'terrace-steps', [(-453, 3540)]),
    ('Park Terrace Link', 'arterial', 'terrace-steps', 'west-park', [(-820, 3615), (-1050, 3560)]),
    ('Glass Steps Lane', 'lane', 'exchange-east-court', 'glass-steps', [(645, 2500)]),
    ('Glass Court Rise', 'local', 'glass-steps', 'courtyard-fork', [(550, 2860)]),
    ('Bell Yard Bike Cut', 'cycleway', 'courtyard-fork', 'bell-yard', [(838, 3120)]),
    ('Bell Yard Street', 'street', 'bell-yard', 'glass-court', [(1080, 3065), (1140, 2940)]),
    ('Merchant Mews', 'lane', 'exchange-east-court', 'lower-east-mews', [(700, 2230)]),
    ('Merchant Court Street', 'street', 'lower-east-mews', 'merchant-court', [(825, 1865)]),
    ('Circuit Quarter Link', 'street', 'merchant-court', 'east-race-approach', [(1270, 1615), (1560, 1690)]),
    ('Inside Circuit Approach', 'street', 'exchange-east-inner', 'east-race-approach', [(1550, 2095)]),
    ('Glazing Court Street', 'local', 'exchange-east-inner', 'glass-court', [(1430, 2670)]),
    ('East Yard Passage', 'lane', 'glass-court', 'east-inner-court', [(1490, 3000)]),
    ('Upper Yard Crescent', 'street', 'east-inner-court', 'north-inner-court', [(1850, 3180), (1770, 3410)]),
]


class StreetSurvey:
    def __init__(self, world):
        cols, rows = round((MAX_X - MIN_X) / CELL) + 1, round((MAX_Y - MIN_Y) / CELL) + 1
        self.blocked = np.zeros((rows, cols), dtype=bool)
        self.race = self.blocked.copy()
        for obj in world.obstacles:
            x, y = obj['center'][:2]
            a, b = obj['half'][:2]
            self.mark(self.blocked, x, y, a, b)
        for road in world.vaderland['routes']:
            if road['kind'] not in RACE_KINDS and 'Circuit' not in road['name']:
                continue
            reach = road['width_m'] / 2 + 8
            for start, end in zip(road['points'], road['points'][1:]):
                for x, y in samples(start, end):
                    self.mark(self.race, x, y, reach, reach)
        self.clearance = distance_transform_edt(~(self.blocked | self.race)) * CELL

    @staticmethod
    def index(x, y):
        return round((x - MIN_X) / CELL), round((y - MIN_Y) / CELL)

    @staticmethod
    def point(i, j):
        return MIN_X + i * CELL, MIN_Y + j * CELL

    def mark(self, mask, x, y, a, b):
        i, j = self.index(x - a - CELL / 2, y - b - CELL / 2)
        k, l = self.index(x + a + CELL / 2, y + b + CELL / 2)
        nx, ny = mask.shape[1], mask.shape[0]
        if k >= 0 and l >= 0 and i < nx and j < ny:
            mask[max(0, j):min(ny, l+1), max(0, i):min(nx, k+1)] = True

    def clear(self, point, reach):
        i, j = self.index(*point)
        return 0 <= j < self.clearance.shape[0] and 0 <= i < self.clearance.shape[1] and self.clearance[j, i] >= reach

    def aligned(self, point, reach):
        if self.clear(point, reach):
            return point
        i, j = self.index(*point)
        nearby = (self.point(u, v) for u in range(i-14, i+15) for v in range(j-14, j+15))
        return min((p for p in nearby if self.clear(p, reach)), key=lambda p: math.dist(p, point))

    def clear_line(self, a, b, reach):
        return all(self.clear(p, reach) for p in samples(a, b))

    def segment(self, a, b, reach):
        if self.clear_line(a, b, reach):
            return [a, b]
        start, end = self.index(*a), self.index(*b)
        queue, cost, parent = [(math.dist(start, end), 0, start)], {start: 0}, {}
        while queue:
            _, previous, p = heappop(queue)
            if cost[p] != previous:
                continue
            if p == end:
                return self.simplify(a, b, p, parent, reach)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                q = p[0]+dx, p[1]+dy
                if not self.clear(self.point(*q), reach):
                    continue
                if dx and dy and not all(self.clear(self.point(*r), reach) for r in ((q[0], p[1]), (p[0], q[1]))):
                    continue
                score = previous + math.hypot(dx, dy)
                if score < cost.get(q, math.inf):
                    cost[q], parent[q] = score, p
                    heappush(queue, (score + math.dist(q, end), score, q))
        raise ValueError(f'No surveyed street between {a} and {b}')

    def simplify(self, a, b, p, parent, reach):
        path = [b]
        while p in parent:
            path.append(self.point(*p))
            p = parent[p]
        path.append(a)
        path.reverse()
        output, i = [a], 0
        while i < len(path)-1:
            j = next(j for j in range(len(path)-1, i, -1) if self.clear_line(path[i], path[j], reach))
            if output[-1] != path[j]:
                output.append(path[j])
            i = j
        return output


def samples(a, b, spacing=CELL / 2):
    n = max(1, math.ceil(math.dist(a, b) / spacing))
    return ((a[0] + (b[0]-a[0])*i/n, a[1] + (b[1]-a[1])*i/n) for i in range(n+1))


def maximum_grade(world, a, b):
    ground = [(p, world.terrain_z(*p)) for p in samples(a, b, CELL / 4)]
    return max((abs(z1 - z0) / math.dist(p0, p1)
                for (p0, z0), (p1, z1) in zip(ground, ground[1:]) if p0 != p1), default=0)


def route_point(road, target):
    points = []
    for a, b in zip(road['points'], road['points'][1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        f = min(1, max(0, ((target[0]-a[0])*dx+(target[1]-a[1])*dy) / max(dx*dx+dy*dy, 1e-6)))
        points.append((a[0]+f*dx, a[1]+f*dy))
    return min(points, key=lambda p: math.dist(p, target))


def soften(points, survey, reach):
    curve = [points[0]]
    for a, corner, b in zip(points, points[1:], points[2:]):
        left, right = math.dist(a, corner), math.dist(corner, b)
        trim = min(58, left*.34, right*.34)
        if trim < CELL:
            curve.append(corner)
            continue
        start = tuple(c + (v-c)*trim/left for c, v in zip(corner, a))
        end = tuple(c + (v-c)*trim/right for c, v in zip(corner, b))
        arc = [tuple(round((1-t)**2*u + 2*t*(1-t)*v + t*t*w, 4) for u, v, w in zip(start, corner, end))
               for t in np.linspace(0, 1, max(4, math.ceil(trim / 7)))]
        check = [curve[-1], *arc, b]
        if all(survey.clear_line(p, q, reach) for p, q in zip(check, check[1:])):
            curve.extend(arc)
        else:
            curve.append(corner)
    curve.append(points[-1])
    return curve


def build(world):
    survey = StreetSurvey(world)
    width_at = defaultdict(float)
    for _, kind, start, end, _ in STREETS:
        for node in (start, end):
            width_at[node] = max(width_at[node], WIDTHS[kind] / 2 + 5)
    roads = {r['name']: r for r in world.vaderland['routes']}
    nodes = {}
    for node, location in NODES.items():
        if isinstance(location[0], str):
            name, *target = location
            spot = route_point(roads[name], target)
            if not survey.clear(spot, width_at[node]):
                raise ValueError(f'Trunk junction {node} has inadequate clearance at {spot}')
            nodes[node] = spot
        else:
            nodes[node] = survey.aligned(location, width_at[node])
    result = []
    for name, kind, start, end, via in STREETS:
        width, reach = WIDTHS[kind], WIDTHS[kind] / 2 + 5
        points = [nodes[start], *(survey.aligned(p, reach) for p in via), nodes[end]]
        route = [points[0]]
        for a, b in zip(points, points[1:]):
            try:
                route.extend(survey.segment(a, b, reach)[1:])
            except ValueError as error:
                raise ValueError(f'{name}: {error}') from error
        curve = [(round(x, 4), round(y, 4)) for x, y in soften(route, survey, reach)]
        for a, b in zip(curve, curve[1:]):
            if not survey.clear_line(a, b, reach - .01):
                raise ValueError(f'{name} leaves its surveyed corridor')
            if maximum_grade(world, a, b) > MAX_STREET_GRADE:
                raise ValueError(f'{name} exceeds the street grade limit between {a} and {b}')
        result.append(dict(name=name, kind=kind, width_m=width, points=curve, mitre=True))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'public/vtx-env/vaderland/meridian-street-plan.js')
    args = parser.parse_args()
    routes = build(make_world('vaderland-33'))
    payload = ',\n'.join('  ' + json.dumps(road, separators=(',', ':')) for road in routes)
    args.output.write_text('// Generated by tools/vaderland/meridian_streets.py.\nexport const MERIDIAN_STREET_PLAN = [\n'
                           + payload + '\n];\n', encoding='utf-8')
    print(f'Wrote {len(routes)} surveyed Meridian streets to {args.output}')
