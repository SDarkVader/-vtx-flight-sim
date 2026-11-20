"""Bake the Vaderland land survey. Coordinates are east, north, up, in metres."""
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates, gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'inputs' / 'vaderland'
HALF, STEP = 8000, 20
AXIS = np.arange(-HALF, HALF + STEP, STEP, dtype=float)
X, Y = np.meshgrid(AXIS, AXIS)


def smooth(lo, hi, value):
    t = np.clip((value - lo) / (hi - lo), 0, 1)
    return t*t*(3-2*t)


def noise(x, y, scale, seed):
    grid = np.random.default_rng(seed).uniform(-1, 1, (96, 96))
    return map_coordinates(grid, [y/scale + 47, x/scale + 47], order=3, mode='grid-wrap')


def relief(x, y):
    # Long glacial divides, with branching arêtes breaking the skyline. The
    # warped ridges supply real relief at five scales down to the contact grid.
    wx = x + 270*noise(x, y, 1050, 32)
    wy = y + 340*noise(x, y, 1350, 11)
    ridge = np.zeros_like(x)
    peaks = [
        (-7680,5100,1900,2130,2500),(-6750,6500,2300,1750,1950),
        (-5120,7160,2070,1720,1650),(-3260,6730,1620,1530,1620),
        (-1380,7650,1950,1980,1730),(1180,7190,1480,2320,1650),
        (3400,7820,1580,1980,1820),(5700,6350,1300,1910,2200),
        (7520,5110,1560,1840,2060),(-7300,2020,930,1900,1130),
        (-5880,3170,1090,1850,1790),(6040,2440,720,2240,1320),
        (7650,-2990,670,1320,1450),(6320,-6020,720,2650,1860),
        (3890,-7840,740,2600,1930),(-2640,-6210,410,1530,1700),
    ]
    for cx, cy, height, rx, ry in peaks:
        radius = np.hypot((wx-cx)/rx, (wy-cy)/ry)
        ridge = np.maximum(ridge, height * np.exp(-1.45*radius**1.23))
    folds = np.zeros_like(x)
    for scale, weight, seed in [(980,.46,71),(475,.28,81),(210,.17,91),(86,.07,101),(40,.025,111)]:
        folds += weight*(1 - np.abs(noise(wx,wy,scale,seed)))
    ridge *= .42 + .77*folds
    low = 18 + 35*(noise(x,y,1400,19)+1) + 12*(noise(x,y,420,93)+1)
    return low + ridge + smooth(200,700,ridge)*54*noise(x,y,150,5)


def coast_chart():
    chart = json.loads((ROOT/'inputs/main_airport_harbour.json').read_text())
    ox, oy = chart['origin']
    def local(x, y):
        return [round(x-ox,2), round(oy-y,2)]
    outer = chart['layout']['outer']
    # Open the southwest side of the original sheltered harbour to a long
    # continental inlet. Its two working quays and inner navigation marks stay.
    headlands = [(-1900,-3200),(-1470,-3420),(-1250,-3810),(-880,-4080),
        (-940,-4500),(-540,-4710),(40,-4540),(380,-4800),(550,-5280),
        (970,-5550),(1300,-5470),(1530,-5860),(1150,-6300),(1390,-6710),
        (2030,-6920),(2380,-7400),(2570,-8000),(-8000,-8000),(-8000,-1230),
        (-7600,-1460),(-7350,-1510),(-7060,-1950),(-6530,-2030),
        (-6170,-1760),(-5800,-1950),(-5560,-2260),(-5120,-2140),
        (-4750,-1820),(-4420,-1880),(-4090,-2150),(-3650,-2260),(-3200,-1910)]
    ring = outer[:657] + [local(*p) for p in headlands] + outer[725:]
    chart['layout']['outer'] = ring
    for i,(cx,cy,rx,ry) in enumerate([(-4830,-3710,610,330),(-5920,-4630,270,600),
          (-3780,-4880,310,190),(-2680,-6100,650,620),(-1000,-6820,220,460),
          (-7230,-3010,290,200),(-4050,-3380,160,80)]):
        island = []
        for a in np.linspace(0,2*np.pi,81)[:-1]:
            rad = 1+.14*np.sin(3*a+i)+.08*np.cos(5*a-i)+.04*np.sin(9*a+2*i)
            island.append(local(cx+rx*rad*np.cos(a),cy+ry*rad*np.sin(a)))
        chart['layout']['islands'].append(dict(name=f'Outer skerry {i+1}',ring=island))
    def area(poly):
        p = np.array(poly)
        return float(abs(np.dot(p[:,0],np.roll(p[:,1],1))-np.dot(p[:,1],np.roll(p[:,0],1)))/2)
    chart['layout']['waterAreaM2'] = round(area(ring)-sum(area(q['ring']) for q in chart['layout']['islands']))
    return chart


def grid_water(chart):
    wet = np.zeros(X.shape, dtype=bool)
    for ring in [chart['layout']['outer'], *(i['ring'] for i in chart['layout']['islands'])]:
        p = np.array(ring, dtype=float)
        p[:,0] += chart['origin'][0]
        p[:,1] = chart['origin'][1]-p[:,1]
        for (ax,ay),(bx,by) in zip(p,np.roll(p,-1,axis=0)):
            if ay == by:
                continue
            rows = slice(*np.searchsorted(AXIS,[min(ay,by),max(ay,by)]))
            edge = ax+(AXIS[rows,None]-ay)*(bx-ax)/(by-ay)
            wet[rows] ^= AXIS < edge
    # The navigable sea exits at the west and south map edges.
    wet[:,0] = wet[:,1]
    wet[0] = wet[1]
    return wet


def geography(chart,local_canyon=False):
    z = relief(X,Y)
    # The north river descends through two resistant shelves into the airfield
    # valley. Terrace lips, cirques and the canyon walls are heightfield contact.
    river_x = -4870 + 380*np.sin(Y/820+.65) + 220*np.sin(Y/420)
    distance = abs(X-river_x)
    shelf = 22 + .029*np.maximum(Y-650,0) + 128*smooth(2880,2960,Y) + 197*smooth(4300,4380,Y)
    wall = 240*smooth(70,420,distance) + 100*smooth(410,1350,distance)
    river_zone = smooth(450,1250,Y)*(1-smooth(6200,7300,Y))
    if local_canyon:
        # The first survey inadvertently capped the far eastern and western
        # ranges at the river shelves' altitude. Confine their influence to
        # the actual glacial catchment so distant ridges keep their own relief.
        river_zone*=1-smooth(540,1770,distance)
    valley = np.minimum(z,shelf + wall)
    z += (valley-z)*river_zone
    if local_canyon:
        west=(1-smooth(-8000,-6520,X))*(1-smooth(3000,5700,Y))*smooth(650,1260,Y)
        z+=(26+22*noise(X,Y,640,48)-z)*west
    # A developable alluvial terrace north of the airport, rising gently into
    # the foothills. Keep its irregular perimeter rather than a flat rectangle.
    city_blend = (1-smooth(2700,3950,abs(X+180)))*(1-smooth(4350,5720,Y))*smooth(270,850,Y)
    terrace = 10 + .009*np.maximum(Y,0) + 3*np.sin(X/730)*np.sin(Y/620)
    z += (terrace-z)*city_blend
    # Wide sightlines east and west of both thresholds. Other land is available
    # for real topography in the northern catchment and on the southern coast.
    z *= smooth(500,1120,abs(Y))
    wet = grid_water(chart)
    dry_dist = distance_transform_edt(~wet)*STEP
    wet_dist = distance_transform_edt(wet)*STEP
    level = chart['waterLevelM']
    bank = level + 0.16*dry_dist + np.maximum(0,noise(X,Y,170,4))*dry_dist*.12
    blend = smooth(0,490,dry_dist)
    z = np.where(wet,level-np.minimum(6.1,wet_dist*.085),bank*(1-blend)+z*blend)
    # Preserve the existing berths' surveyed bed and access to the inner basin.
    from vtx.world import TestWorld
    old=TestWorld()
    ix=np.arange(200,601)
    x,y=X[np.ix_(ix,ix)],Y[np.ix_(ix,ix)]
    berths=smooth(-1500,-750,y)*(1-smooth(-600,-480,y))*smooth(-600,-80,x)*(1-smooth(920,1350,x))
    z[np.ix_(ix,ix)] += (old.heights-z[np.ix_(ix,ix)])*berths
    z[abs(Y)<=500]=0
    return np.rint(z*10).astype('<u2')


def forest(terrain, chart):
    from vtx.world import TestWorld
    survey = object.__new__(TestWorld)
    survey.half, survey.n, survey.heights = HALF, len(terrain), terrain/10
    wet = grid_water(chart)
    rng = np.random.default_rng(8410)
    trees = []
    groves = [(-4600,2400),(-5870,3800),(-3350,4830),(-6720,5330),
              (3650,4540),(5110,2710),(6300,3480),(6380,-3750),(3550,-5960),
              (-4840,-3700),(-2670,-6050),(-5950,-4660),(-3860,-4860),
              (-3740,-1680),(-5090,-1840),(-2080,-3180),(1980,-3430)]
    for cx,cy in groves:
        for _ in range(80):
            x,y=np.round(rng.normal((cx,cy),(280,160)),1)
            i,j=np.rint((np.array([x,y])+HALF)/STEP).astype(int)
            if wet[j,i] or terrain[j,i]>14000:
                continue
            h=round(rng.uniform(9,24),1)
            r=round(h*rng.uniform(.10,.16),2)
            z=min(survey.terrain_z(x+dx,y+dy) for dx,dy in [(0,0),(r,0),(-r,0),(0,r),(0,-r)])
            trees.append(dict(id=f'pine-{len(trees)}',kind='cylinder',center=[x,y,round(z+h/2-.35,3)],
                    half=[r,r,h/2],color=rng.choice(['#283e36','#304c40','#3c5542','#35493e']),landable=False))
    return trees


def landscape_light(terrain,obstacles=(),filename='relief-light.png',sun=(.89,-.45,.26)):
    h=terrain.astype(float)/10
    surface=h.copy()
    for o in obstacles:
        x,y,z=o['center'];a,b,c=o['half']
        i0,i1=np.searchsorted(AXIS,[x-a-4,x+a+4]);j0,j1=np.searchsorted(AXIS,[y-b-4,y+b+4])
        if i1<=i0 or j1<=j0:continue
        block=surface[j0:j1,i0:i1]
        solid=True if o['kind']=='box' else ((X[j0:j1,i0:i1]-x)**2+(Y[j0:j1,i0:i1]-y)**2<(a+5)**2)
        block[:]=np.where(solid,np.maximum(block,z+c),block)
    horizon=np.full(h.shape,-2.)
    for distance in np.geomspace(30,6800,78):
        ix=np.clip(np.arange(len(h))+round(sun[0]*distance/STEP),0,len(h)-1)
        iy=np.clip(np.arange(len(h))+round(sun[1]*distance/STEP),0,len(h)-1)
        horizon=np.maximum(horizon,(surface[np.ix_(iy,ix)]-h)/distance)
    light=smooth(-.06,.06,sun[2]-horizon)
    shelter=np.clip((gaussian_filter(h,12)-h)/130,0,1)
    # A linear-data texture: the first channel is terrain self-shadow, the
    # second local valley occlusion. Row zero in the PNG is world north.
    depth=np.clip((7-h)/6.1,0,1)
    pixels=np.uint8(np.stack([light,1-shelter*.55,depth],axis=-1)[::-1]*255)
    raw=b''.join(b'\0'+row.tobytes() for row in pixels)
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    content=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',len(h),len(h),8,2,0,0,0))
    content+=chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')
    (ROOT/'public/vtx-env/vaderland'/filename).write_bytes(content)


def main():
    import sys
    sys.path.insert(0,str(ROOT/'src'))
    PACK.mkdir(parents=True,exist_ok=True)
    chart = coast_chart()
    terrain = geography(chart)
    np.savez_compressed(PACK/'geography-01.npz', height_dm=terrain)
    (PACK/'coast-01.json').write_text(json.dumps(chart,separators=(',',':'))+'\n',encoding='utf-8')
    (PACK/'groves-01.json').write_text(json.dumps(forest(terrain,chart),separators=(',',':'))+'\n',encoding='utf-8')
    landscape_light(terrain)
    print('Contact grid',terrain.shape,terrain.min()/10,terrain.max()/10)


if __name__ == '__main__':
    main()
