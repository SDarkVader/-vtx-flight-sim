"""Versioned Vaderland scenery. Aircraft use their usual vehicle definitions."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

import numpy as np

from .harbour_water import contains
from .world import TestWorld

PACK = Path(__file__).resolve().parents[2] / 'inputs' / 'vaderland'


@lru_cache(maxsize=1)
def geography():
    with np.load(PACK / 'geography-01.npz', allow_pickle=False) as data:
        heights = data['height_dm'].astype(np.float64) / 10
    chart = json.loads((PACK / 'coast-01.json').read_text(encoding='utf-8'))
    trees = json.loads((PACK / 'groves-01.json').read_text(encoding='utf-8'))
    return heights, chart, trees


class Vaderland(TestWorld):
    id = environment_key = 'vaderland-01'
    label = 'Vaderland · Alpine coast'
    version = '1'
    half, n, height_scale_m = 8000., 801, 2400
    default_departure = [-3885., 0.]
    default_destination = [300., 0.]

    def __init__(self, seed=41031):
        airport = TestWorld(seed)
        self.seed = seed
        self.runway = airport.runway
        self.approach_corridor = airport.approach_corridor
        # The old test pond straddles the runway. The compatibility rectangle
        # for this survey is entirely inside the charted western sound.
        self.water = dict(x=-4900.,y=-5100.,half_x=10.,half_y=10.)
        self.obstacles = airport.obstacles
        terrain, chart, trees = geography()
        self.obstacles.extend(deepcopy(trees))
        self.heights = terrain.copy()
        self.harbour = deepcopy(chart)
        self.vaderland = dict(height_scale_m=self.height_scale_m, routes=[], places=[])
        rings = [chart['layout']['outer'], *(i['ring'] for i in chart['layout']['islands'])]
        edges = [np.asarray(ring, dtype=float) for ring in rings]
        self._island_bounds = tuple((ring, ring.min(axis=0), ring.max(axis=0)) for ring in edges[1:])
        self._shore = np.concatenate(edges)
        self._ends = np.concatenate([np.roll(p, -1, axis=0) for p in edges])
        self._delta = self._ends-self._shore
        self._length2 = np.maximum(np.sum(self._delta**2,axis=1),1e-16)

    def harbour_water_mask(self, x, y):
        x, y = np.broadcast_arrays(x, y)
        ox, oy = self.harbour['origin']
        p = np.column_stack((x.ravel()-ox, oy-y.ravel()))
        layout = self.harbour['layout']
        wet = contains(p, layout['outer'])
        for ring, lower, upper in self._island_bounds:
            nearby = wet & np.all((p >= lower) & (p <= upper), axis=1)
            if np.any(nearby):
                wet[nearby] &= ~contains(p[nearby], ring)
        return wet.reshape(x.shape)

    def harbour_overlaps(self, x, y, radius):
        streams=self.vaderland.get('streams',())
        for stream in streams:
            p=np.asarray(stream['points'],dtype=float)
            if x<p[:,0].min()-radius-30 or x>p[:,0].max()+radius+30 or y<p[:,1].min()-radius-30 or y>p[:,1].max()+radius+30:
                continue
            ab=np.diff(p,axis=0);ap=np.array([x,y])-p[:-1]
            t=np.clip(np.sum(ap*ab,axis=1)/np.maximum(np.sum(ab*ab,axis=1),1e-12),0,1)
            if np.min(np.linalg.norm(ap-t[:,None]*ab,axis=1))<=radius+stream['width_m']/2:
                return True
        if y > self.harbour['origin'][1] + radius:
            return False
        if self.harbour_water_mask(x,y):
            return True
        ox,oy = self.harbour['origin']
        offset = np.array([x-ox,oy-y])-self._shore
        t = np.clip(np.sum(offset*self._delta,axis=1)/self._length2,0,1)
        return bool(np.min(np.sum((offset-t[:,None]*self._delta)**2,axis=1)) <= radius**2)

    def public(self):
        return dict(super().public(), vaderland=deepcopy(self.vaderland))

    def surface_z(self,x,y):
        height=super().surface_z(x,y)
        for o in self.obstacles:
            if o.get('role') in ('architecture','deck','pier') and o['kind']=='cylinder':
                cx,cy,cz=o['center']
                if (x-cx)**2+(y-cy)**2<=o['half'][0]**2:
                    height=max(height,cz+o['half'][2])
        return height


class VaderlandCity(Vaderland):
    id = environment_key = 'vaderland-02'
    version = '2'
    label = 'Vaderland · Meridian City'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with np.load(PACK/'city-02.npz',allow_pickle=False) as data:
            self.heights=data['height_dm'].astype(np.float64)/10
        city=json.loads((PACK/'city-02.json').read_text(encoding='utf-8'))
        self.obstacles.extend(city['obstacles'])
        self.vaderland.update(routes=city['routes'],places=city['places'])


class VaderlandNetwork(VaderlandCity):
    id = environment_key = 'vaderland-03'
    version = '3'
    label = 'Vaderland · Sound and summit'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with np.load(PACK/'routes-03.npz',allow_pickle=False) as data:
            self.heights=data['height_dm'].astype(np.float64)/10
        layout=json.loads((PACK/'routes-03.json').read_text(encoding='utf-8'))
        self.obstacles=[o for o in self.obstacles if not o['id'].startswith('pine-')]
        self.obstacles.extend(layout['groves'])
        self.obstacles.extend(layout['obstacles'])
        self.vaderland['routes'].extend(layout['routes'])
        self.vaderland['places'].extend(layout['places'])
        self.vaderland.update(streams=layout['streams'],spans=layout['spans'])


class VaderlandReview(Vaderland):
    id = environment_key = 'vaderland-04'
    version = '4'
    label = 'Vaderland · Twin Falls and the Sound'
    survey_file = 'vaderland-04'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with np.load(PACK/(self.survey_file+'.npz'),allow_pickle=False) as data:
            self.heights=data['height_dm'].astype(np.float64)/10
        layout=json.loads((PACK/(self.survey_file+'.json')).read_text(encoding='utf-8'))
        self.obstacles=[o for o in self.obstacles if not o['id'].startswith('pine-')]
        self.obstacles.extend(layout.pop('groves'))
        self.obstacles.extend(layout.pop('obstacles'))
        self.vaderland.update(layout)


class Meridian(VaderlandReview):
    id = environment_key = 'vaderland-05'
    version = '5'
    height_scale_m = 2600
    label = 'Vaderland · Meridian and Twin Falls'
    survey_file = 'meridian-05'


class TwinFalls(Meridian):
    id = environment_key = 'vaderland-06'
    version = '6'
    label = 'Vaderland · Falls Bridge'

    def __init__(self, seed=41031):
        super().__init__(seed)
        with np.load(PACK/'falls-06.npz',allow_pickle=False) as delta:
            row,col=delta['row'],delta['col']
            self.heights[row,col]=np.round(self.heights[row,col]+delta['change_dm']*.1,1)
        layout=json.loads((PACK/'falls-06.json').read_text(encoding='utf-8'))
        removed=set(layout['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in removed]+layout['added']
        self._falls_deck=next(o for o in layout['added'] if o['id']=='Falls bridge-deck-main')

    def harbour_overlaps(self,x,y,radius):
        # Aircraft site selection queries the upper support. A complete dry
        # footprint on the deck sits tens of metres above the channel.
        cx,cy,_=self._falls_deck['center']
        hx,hy,_=self._falls_deck['half']
        if abs(x-cx)+radius<=hx and abs(y-cy)+radius<=hy:
            return False
        return super().harbour_overlaps(x,y,radius)


class LanternGallery(TwinFalls):
    id = environment_key = 'vaderland-07'
    version = '7'
    label = 'Vaderland · Lantern Gallery'

    def __init__(self, seed=41031):
        super().__init__(seed)
        lane, median, shoulder = 4.5, 1., 1.25
        clear = lane*4 + median + shoulder*2
        road_names = {'Cut-and-cover gallery','Gallery west approach','Gallery east approach'}
        for road in self.vaderland['routes']:
            if road['name'] in road_names:
                road.update(width_m=clear, lanes_each_way=2, lane_width_m=lane,
                            median_m=median, shoulder_m=shoulder)
        retained={o['id']:o for o in self.obstacles}
        roof=retained['gallery-roof']
        x,y,z=roof['center']
        length=roof['half'][0]
        underside=z-roof['half'][2]
        for side in (-1,1):
            wall=retained['gallery-wall-'+str(side)]
            wall['center'][1]=y+side*(clear/2+wall['half'][1])
        roof['half'][1]=clear/2+2.4
        roof_top=underside+2.15
        roof['center'][2]=(roof_top+underside)/2
        roof['half'][2]=(roof_top-underside)/2
        # The cover is a second solid surface over an open traffic bore. The
        # adjacent earth banks use the base heightfield and meet the cover.
        soil=1.45
        self.obstacles.append(dict(id='gallery-earth-cover',kind='box',
            center=[x,y,roof_top+soil/2],half=[length-12,roof['half'][1],soil/2],
            color='#555f42',role='cover',landable=True,support='stack',parent='gallery-roof'))
        axis=np.linspace(-self.half,self.half,self.n)
        ix=np.flatnonzero(abs(axis-x)<=length+35)
        iy=np.flatnonzero(abs(axis-y)<=148)
        sx,sy=np.meshgrid(axis[ix]-x,axis[iy]-y)
        def ease(value):
            v=np.clip(value,0,1)
            return v*v*(3-2*v)
        width=105+16*np.cos(sx/73)+11*np.sin(sx/95+sy*.015)
        # The carriageway lies between y = -4360 and -4340 grid lines. Only
        # the outer earth cells rise, leaving all four swept lanes untouched.
        weight=ease((length-7-abs(sx))/54)*ease((abs(sy)-10)/19)*ease((width-abs(sy))/67)
        ground=self.heights[np.ix_(iy,ix)]
        self.heights[np.ix_(iy,ix)]=np.round(ground+weight*np.maximum(0,roof_top+soil-ground),1)
        # Compact earth fills meet the slab edges. Both their bases and the
        # terrain beyond them support the cross-section from either portal.
        for side in (-1,1):
            inner,outer=roof['half'][1],30.
            for bay,(a,b,fill) in enumerate([(-288,-270,.48),(-270,-250,.80),(-250,250,1.),(250,270,.80),(270,288,.48)]):
                bottom=underside-9.
                top=self.terrain_z(x,y)+(roof_top+soil-self.terrain_z(x,y))*fill
                self.obstacles.append(dict(id=f'gallery-bank-{side}-{bay}',kind='box',
                    center=[x+(a+b)/2,y+side*(inner+outer)/2,(top+bottom)/2],
                    half=[(b-a)/2,(outer-inner)/2,(top-bottom)/2],color='#636247',
                    role='cover',landable=True))
        floor=self.terrain_z(x,y)
        self.vaderland['gallery']=dict(center=[x,y],portal_x_m=[x-length,x+length],
            floor_z_m=floor,ceiling_z_m=underside,clear_width_m=clear,
            lane_width_m=lane,median_m=median,shoulder_m=shoulder,
            lane_centres_m=[-median/2-1.5*lane,-median/2-.5*lane,median/2+.5*lane,median/2+1.5*lane])
        alignments=[np.array(r['points']) for r in self.vaderland['routes'] if r['name'] in road_names]
        starts=np.concatenate([line[:-1] for line in alignments])
        segments=np.concatenate([np.diff(line,axis=0) for line in alignments])
        squared=np.maximum(1e-12,(segments*segments).sum(axis=1))
        kept=[]
        for o in self.obstacles:
            px,py,pz=o['center']
            if o['kind']=='cylinder' and not o.get('role') and 2500<px<4900 and -4550<py<-3550:
                offset=np.asarray([px,py])-starts
                t=np.clip((offset*segments).sum(axis=1)/squared,0,1)
                d=np.min(np.linalg.norm(offset-t[:,None]*segments,axis=1))
                if d<=clear/2+o['half'][0]+.75:
                    continue
                if abs(px-x)<length+35 and abs(py-y)<148:
                    if self.terrain_z(px,py)>pz-o['half'][2]+1.5:
                        continue
            kept.append(o)
        self.obstacles=kept


class LanternSound(LanternGallery):
    id = environment_key = 'vaderland-08'
    version = '8'
    label = 'Vaderland · Lantern Sound'

    def __init__(self, seed=41031):
        super().__init__(seed)
        self.vaderland['harbour_surface']=dict(samples=49,spacing_m=2.,snap_m=12.)


class MeridianAirfield(LanternSound):
    id = environment_key = 'vaderland-09'
    version = '9'
    label = 'Vaderland · Meridian Airfield'

    def __init__(self, seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'airport-09.json').read_text(encoding='utf-8'))
        remove=set(plan['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in remove]+plan['added']
        self.vaderland['routes']=[plan['revised_routes'].get(r['name'],r) for r in self.vaderland['routes']]+plan['routes']
        self.vaderland['airfield']=plan['airfield']
        self.harbour['accessPath']=deepcopy(plan['revised_routes']['Airport landing road']['points'])


class AirportLanding(MeridianAirfield):
    id = environment_key = 'vaderland-10'
    version = '10'
    label = 'Vaderland · Airport Landing'

    def __init__(self, seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'landing-10.json').read_text(encoding='utf-8'))
        for row,col,height in plan['bank']:
            self.heights[row,col]=height
        remove=set(plan['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in remove]+plan['added']
        self.vaderland['routes'].extend(plan['routes'])
        self.vaderland['landing']=plan['landing']
        road=next(r for r in self.vaderland['routes'] if r['name']==self.vaderland['airfield']['public_road'])
        road['points']=plan['approach']
        self.harbour['accessPath']=deepcopy(road['points'])


class MeridianArrivals(AirportLanding):
    id = environment_key = 'vaderland-11'
    version = '11'
    label = 'Vaderland · Meridian Arrivals'

    def __init__(self,seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'arrivals-11.json').read_text(encoding='utf-8'))
        remove=set(plan['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in remove]+plan['solids']
        self.vaderland['routes'].extend(plan['routes'])
        self.vaderland['arrivals']=plan['arrivals']
        self.vaderland['airfield']['lamps']=[[o['center'][0],o['center'][1],o['center'][2]+o['half'][2]]
                                             for o in self.obstacles if o.get('finish')=='lamp']
        self._shells=[(o,np.asarray(o['planes'])) for o in plan['solids'] if o['kind']=='mesh']

    def surface_z(self,x,y):
        z=super().surface_z(x,y)
        for obstacle,planes in self._shells:
            cx,cy,cz=obstacle['center']
            if abs(x-cx)>obstacle['half'][0] or abs(y-cy)>obstacle['half'][1]:continue
            d=planes[:,0]*(x-cx)+planes[:,1]*(y-cy)+planes[:,3]
            if np.any(d[np.abs(planes[:,2])<1e-8]>1e-5):continue
            top=planes[:,2]>1e-8;bottom=planes[:,2]<-1e-8
            hi=np.min(-d[top]/planes[top,2]);lo=np.max(-d[bottom]/planes[bottom,2])
            if hi>=lo-1e-5:z=max(z,cz+float(hi))
        return z


class MeridianOperations(MeridianArrivals):
    id = environment_key = 'vaderland-12'
    version = '12'
    label = 'Vaderland · Meridian Operations'
    moving_scenery = True

    def __init__(self,seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'operations-12.json').read_text(encoding='utf-8'))
        remove=set(plan['removed'])
        self.obstacles=[plan['replaced'].get(o['id'],o) for o in self.obstacles if o['id'] not in remove]+plan['solids']
        for o in self.obstacles:
            if o['id'] in plan['parents']:o.update(support='joint',parent=plan['parents'][o['id']])
        self.vaderland['routes']=[plan['revised_routes'].get(r['name'],r) for r in self.vaderland['routes']]+plan['routes']
        self.vaderland['operations']=plan['operations']
        from .course_timing import CourseTiming
        self.timing=CourseTiming([plan['operations']['course']])
        self.vaderland['arrivals']['asset']=plan['operations']['terminal_asset']
        self.vaderland['places'].extend([dict(name="Arthur Finch · Compliance and Records",point=[1000,-344]),
            dict(name="Raymond Winston · Tower",point=[116,-235]),dict(name="Engineering and model design",point=[34,-302])])
        self._shells=[(o,np.asarray(o['planes'])) for o in self.obstacles if o['kind']=='mesh' and 'motion' not in o]


class AviatorPlaza(MeridianOperations):
    id = environment_key = 'vaderland-13'
    version = '13'
    label = 'Vaderland · Aviator Plaza'

    def __init__(self,seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'civic-13.json').read_text(encoding='utf-8'))
        for row,col,height in plan['bank']:self.heights[row,col]=height
        remove=set(plan['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in remove]+plan['solids']
        self.vaderland['routes'].extend(plan['routes']);self.vaderland['civic_district']=plan['civic']
        from .course_timing import CourseTiming
        self.timing=CourseTiming([*self.timing.courses,plan['civic']['course']])
        self.vaderland['places'].append(dict(name='VaderLand Aviator Plaza',point=plan['civic']['plaza'][:2]))
        self._shells.extend((o,np.asarray(o['planes'])) for o in plan['solids'] if o['kind']=='mesh' and 'motion' not in o)


class CrestPlaza(AviatorPlaza):
    id = environment_key = 'vaderland-14'
    version = '14'
    label = 'Vaderland · V Crest Plaza'

    def __init__(self,seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'crest-14.json').read_text(encoding='utf-8'))
        frontage=plan['frontage'];removed=set(frontage['removed'])
        self.obstacles=[o for o in self.obstacles if o.get('motion',{}).get('name')!='aviator' and o['id'] not in removed]+plan['solids']
        self.vaderland['frontage']=frontage
        self.vaderland['operations']['annex']['doors']=frontage['doors']
        self._shells=[(o,np.asarray(o['planes'])) for o in self.obstacles if o['kind']=='mesh' and 'motion' not in o]
        district=self.vaderland['civic_district']
        del district['statue']
        district['monument']=plan['monument']
        district['course']['name']='V Crest Plaza'
        for r in self.vaderland['routes']:
            if r['name']=='Aviator Plaza Circuit':r['name']='V Crest Plaza Circuit'
        for p in self.vaderland['places']:
            if p['name']=='VaderLand Aviator Plaza':p['name']='Vaderland V Crest Plaza'
        from .course_timing import CourseTiming
        self.timing=CourseTiming([self.vaderland['operations']['course'],district['course']])


class NightVelocity(CrestPlaza):
    id = environment_key = 'vaderland-15'
    version = '15'
    label = 'Vaderland · Night Velocity'

    def __init__(self,seed=41031):
        super().__init__(seed)
        plan=json.loads((PACK/'night-15.json').read_text(encoding='utf-8'));removed=set(plan['removed'])
        self.obstacles=[o for o in self.obstacles if o['id'] not in removed]+plan['solids']
        self.vaderland['routes'].append(plan['route']);self.vaderland['speedway']=plan['speedway']
        self.vaderland['places'].append(dict(name='Night Velocity start',point=plan['speedway']['timing']['gates'][0]['center'][:2]))
        from .course_timing import CourseTiming
        self.timing=CourseTiming([*self.timing.courses,plan['speedway']['timing']])
        self._shells=[(o,np.asarray(o['planes'])) for o in self.obstacles if o['kind']=='mesh' and 'motion' not in o]


class MarketQuarter(NightVelocity):
    reuse_water_neighbourhoods = True
    id = environment_key = 'vaderland-16'
    version = '16'
    label = 'Vaderland · Meridian Market Quarter'

    def __init__(self, seed=41031):
        super().__init__(seed)
        import gzip
        with gzip.open(PACK/'market-16.json.gz','rt',encoding='utf-8') as survey:
            plan=json.load(survey)
        self.obstacles.extend(plan['solids'])
        self.vaderland['quarter']=plan['quarter']
        self._shells.extend((o,np.asarray(o['planes'])) for o in plan['solids'] if 'motion' not in o)
        self._water_cells=None

    def harbour_water_mask(self,x,y):
        # Only cells touched by a coastline edge can change membership within that cell.
        # Ambiguous cells use the original polygon test, including every island and boundary.
        if getattr(self,'_water_cells',None) is None:
            ox,oy=self.harbour['origin']
            edges=np.array([self._shore[:,0]+ox,oy-self._shore[:,1]]).T
            ends=np.array([self._ends[:,0]+ox,oy-self._ends[:,1]]).T
            stride=32.
            lo=np.floor(edges.min(axis=0)/stride)*stride-stride
            nx,ny=np.ceil((edges.max(axis=0)-lo)/stride).astype(int)+2
            ax=lo[0]+stride*(np.arange(nx)+.5)
            ay=lo[1]+stride*(np.arange(ny)+.5)
            grid=super().harbour_water_mask(*np.meshgrid(ax,ay)).astype(np.int8)
            mins=np.floor((np.minimum(edges,ends)-lo)/stride-1e-10).astype(int)
            maxs=np.floor((np.maximum(edges,ends)-lo)/stride+1e-10).astype(int)
            for start, end, (i, j), (k, last_row) in zip(edges, ends, mins, maxs):
                dy = end[1] - start[1]
                if dy == 0:
                    grid[j:last_row+1, i:k+1] = -1
                    continue
                # A diagonal shore touches only part of each row in its bounding box.
                # Include neighbouring cells on grid lines before using the exact polygon.
                for row in range(j, last_row + 1):
                    bottom = lo[1] + row * stride
                    fraction = np.clip((np.array([bottom, bottom + stride]) - start[1]) / dy, 0, 1)
                    cross_x = start[0] + fraction * (end[0] - start[0])
                    first = int(np.floor((cross_x.min() - lo[0]) / stride - 1e-10))
                    last = int(np.floor((cross_x.max() - lo[0]) / stride + 1e-10))
                    grid[row, first:last+1] = -1
            self._water_cells=(lo,stride,grid)
        lo,stride,grid=self._water_cells
        x,y=np.broadcast_arrays(x,y);xx=x.ravel();yy=y.ravel()
        i=np.floor((xx-lo[0])/stride).astype(int);j=np.floor((yy-lo[1])/stride).astype(int)
        valid=(i>=0)&(i<grid.shape[1])&(j>=0)&(j<grid.shape[0])
        flags=np.zeros(i.size,dtype=np.int8)
        flags[valid]=grid[j[valid],i[valid]]
        edge=flags<0
        if edge.any():
            flags[edge]=super().harbour_water_mask(xx[edge],yy[edge])
        return (flags>0).reshape(x.shape)


class MeridianCityLights(MarketQuarter):
    id = environment_key = 'vaderland-17'
    version = '17'
    label = 'Vaderland · Meridian City Lights'

    def __init__(self, seed=41031):
        super().__init__(seed)
        import gzip
        with gzip.open(PACK/'city-lights-17.json.gz', 'rt', encoding='utf-8') as f:
            design = json.load(f)
        self.obstacles.extend(design['solids'])
        self._shells.extend((o, np.asarray(o['planes'])) for o in design['solids'] if 'motion' not in o)
        self.vaderland['city_lights'] = {'buildings': design['places']}
        self.vaderland['places'].extend({'name': p['name'], 'point': p['point']} for p in design['places'])
