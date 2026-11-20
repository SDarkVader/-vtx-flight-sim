"""Author Meridian's occupied street blocks. Shapely 2.1 is needed only to bake the survey."""
import json
import math
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from bake import PACK, landscape_light
from drafting import Masonry
from streets import footprint
from vtx.vaderland import NightVelocity


def build():
    w = NightVelocity()
    rng = np.random.default_rng(61472)
    district = box(-1010, 1480, 1010, 3480)
    plaza = box(-322, 2229, -49, 2412)
    roads = []
    street_lines = []
    for r in w.vaderland['routes']:
        line = LineString(r['points'])
        if not line.intersects(district.buffer(140)):
            continue
        width = r['width_m']
        roads.append(line.buffer(width/2,quad_segs=5))
        if r['name'].startswith(('North street','Terrace','Exchange Boulevard','Meridian Avenue')):
            street_lines.append((r['name'],line,width))
    carriageway = unary_union(roads)
    pavement = carriageway.buffer(8.5,quad_segs=4).difference(carriageway.buffer(.12,quad_segs=4)).intersection(district)
    footways = []
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(pavement)):
        footways.append([[round(x,3),round(y,3)] for x,y in list(tri.exterior.coords)[:3]])
    protected = []
    retained = []
    for o in w.obstacles:
        x,y = o['center'][:2]
        if not (-1250<x<1250 and 1250<y<3700):
            continue
        protected.append(Polygon(footprint(o)).buffer(.45))
        if o['id'].startswith(('ward-','courtyard-')) and o['kind'] in ('box','cylinder'):
            retained.append(o['id'])
    theory = STRtree(protected)
    reserved = unary_union([carriageway.buffer(3.2,quad_segs=4),plaza])
    occupied = defaultdict(list)
    def tiles(shape):
        x0,y0,x1,y1=shape.bounds
        return [(i,j) for i in range(math.floor(x0/80),math.floor(x1/80)+1)
                      for j in range(math.floor(y0/80),math.floor(y1/80)+1)]
    def vacant(shape):
        if not district.covers(shape) or reserved.intersects(shape) or len(theory.query(shape,predicate='intersects')):
            return False
        return all(not other.intersects(shape) for cell in tiles(shape) for other in occupied[cell])
    def take(shape):
        for key in tiles(shape):occupied[key].append(shape)

    m=Masonry();places=[];walks=[];lots=[];buildings=0;towers=0
    def rounded(a,b,r):
        r=min(a*.91,b*.91,r)
        ring=[]
        for u,v,start in [(a-r,b-r,0),(-a+r,b-r,90),(-a+r,-b+r,180),(a-r,-b+r,270)]:
            for angle in np.deg2rad(np.linspace(start,start+90,5)):
                ring.append([u+r*math.cos(angle),v+r*math.sin(angle)])
        return np.array(ring)
    def build_lot(center,axis,front,width,depth,high,street):
        nonlocal buildings,towers
        shape=rounded(width/2,depth/2,float(rng.uniform(2.2,8.4)))
        matrix=np.vstack([axis,front])
        xy=center+shape@matrix
        poly=Polygon(xy).buffer(1.0)
        if not vacant(poly):return False
        take(poly)
        k=buildings;buildings+=1
        key=f'market-block-{k}'
        inner=np.asarray([w.terrain_z(*p) for p in xy])
        # Bury the full bounding rectangle down to its lowest terrain corner.
        x0,y0,x1,y1=poly.bounds
        base=min(w.terrain_z(x,y) for x in (x0,(x0+x1)/2,x1) for y in (y0,(y0+y1)/2,y1))-.55
        level=round(float(inner.mean()),3);shop=level+7.85
        kind=int(rng.integers(4));tall=high and width>25 and depth>21
        def band(tag,levels,skin,parent=None,arc=False):
            cloud=[]
            profile=shape if not arc else np.array([[width*.5*math.cos(t),depth*.5*math.sin(t)]
                                                  for t in np.arange(24)*math.tau/24])
            for sx,sy,du,dv,z,*special in levels:
                rot,slope=special if special else (0,0)
                angle=np.array([[math.cos(rot),math.sin(rot)],[-math.sin(rot),math.cos(rot)]])
                local=(profile*[sx,sy])@angle
                q=center+(local+[du,dv])@matrix
                cloud.extend([*p,z+slope*v/width] for p,v in zip(q,local[:,0]))
            return m.hull(key+'-'+tag,cloud,skin,parent=parent,city=True,datum_m=level,
                          tenancy=kind,front=front.round(6).tolist(),landable=True)
        ground=band('shops',[(1,1,0,0,base),(1,1,0,0,shop)],'shopfront')
        floors=int(rng.choice([3,4,5,6,7,8,11,14],p=[.12,.17,.19,.18,.13,.09,.07,.05]))
        h=round(shop+floors*3.48,3);skin=['apartments','workrooms','masonry','galleryhouse'][kind]
        if tall:
            towers+=1
            full=float(rng.uniform(78,214))
            podium=band('podium',[(.99,.99,0,0,shop-.04),(.98,.99,0,0,shop+8.2)],skin,ground)
            shift=float(rng.uniform(-.11,.11))*width
            mid=shop+full*.63
            if k%5==0:
                for side in (-1,1):
                    du=width*side*.224;top=shop+full*(.73 if side<0 else 1.0)
                    band('twin'+str(side),[(.39,.75,du,0,shop+8.16),(.25,.53,du+side*.031*width,0,top,.09*side,23*side)],
                         'officeglass16',podium)
            else:
                arc=k%5 in (1,2);turn=.23 if k%5==2 else -.12 if k%5==3 else 0
                slope=(21 if k%5==1 else -30 if k%5==3 else 0)
                trunk=band('shaft',[(.85,.83,0,0,shop+8.17),(.75,.79,shift,.04*depth,mid,turn*.48,0)],'officeglass16',podium,arc)
                crown=band('lantern',[(.75,.79,shift,.04*depth,mid-.04,turn*.48,0),(.51,.68,shift*1.22,.07*depth,shop+full,turn,slope)],'officeglass16',trunk,arc)
                band('cap',[(.51,.68,shift*1.22,.07*depth,shop+full-.04,turn,slope),(.48,.64,shift*1.22,.07*depth,shop+full+1.45,turn,slope)],'roof16',crown,arc)
        else:
            side=float(rng.uniform(-.038,.038))*width
            shell=band('upper',[(.986,.986,0,0,shop-.04),(.92,.95,side,0,h)],skin,ground)
            band('roof',[(.925,.96,side,0,h-.06),(.922,.955,side,0,h+.48)],'roof16',shell)
        # The awning is mechanically fixed to the lintel. Its edge is inside the site clearance.
        if depth>14 and k%3!=2:
            cloud=[]
            for u in [-width*.34,width*.34]:
                for v,z in [(depth*.46,level+4.75),(depth*.5+.92,level+4.30)]:
                    p=center+u*axis+v*front
                    for dz in [0,.19]:cloud.append([*p,z+dz])
            m.hull(key+'-awning',cloud,'awning16',parent=ground,city=True,datum_m=level,tenancy=kind)
        door=center+front*(depth/2+.035)
        lots.append(dict(id=ground,xy=center.round(3).tolist(),door=door.round(3).tolist(),axis=axis.round(5).tolist(),
                         front=front.round(5).tolist(),width=round(width,2),depth=round(depth,2),datum=level,kind=kind,street=street))
        if k%8==0 and width>25:
            places.append(dict(xy=door.round(3).tolist(),height_m=level+5.8,front=front.round(5).tolist(),
                               name=['EXCHANGE HALL','NORTH MARKET','FOUNDRY COFFEE','MERIDIAN WORKS','ARCADE','THE READING ROOM'][k//8%6],width_m=min(9,width*.39)))
        return True
    street_lines.sort(key=lambda r:(r[0]!='Meridian Avenue',r[0]!='Exchange Boulevard',r[0]))
    for name,line,wide in street_lines:
        for side in [-1,1]:
            s=float(rng.uniform(4,35))
            while s<line.length-24:
                width=float(rng.uniform(20,49))
                a=line.interpolate(s);s+=width+float(rng.uniform(1.7,7.4))
                center=np.array([a.x,a.y])
                if not district.contains(a):continue
                before=line.project(a);p=line.interpolate(before-3);q=line.interpolate(before+3)
                axis=np.array([q.x-p.x,q.y-p.y]);axis/=np.linalg.norm(axis)
                normal=side*np.array([-axis[1],axis[0]])
                for setback,depth in [(float(rng.uniform(7.8,11.9)),float(rng.uniform(15,34))),
                                       (8.5,14.),(14.,16.)]:
                    centerline=center+normal*(wide/2+setback+depth*.5)
                    if build_lot(centerline,axis,-normal,width,depth,rng.random()<.17,name):break
                # Interior buildings form an irregular second street wall and landscaped passages.
                if rng.random()<.74:
                    depth=float(rng.uniform(22,43));cw=float(rng.uniform(24,53))
                    pos=center+normal*(wide/2+float(rng.uniform(65,105)))
                    build_lot(pos,axis,-normal,cw,depth,rng.random()<.25,name)
    # Walkable promenades are distinct from the traffic envelope. Each closed path is checked
    # against real occupied footprints and kerbs, including over the ends of its orbit.
    for j,lot in enumerate(lots):
        if j%2 and lot['street']!='Meridian Avenue':continue
        door=np.array(lot['door']);axis=np.array(lot['axis']);front=np.array(lot['front'])
        if lot['street']!='Meridian Avenue' and len(walks)>=120:continue
        span=min(13.5,lot['width']*.33)
        for s in range(2 if lot['street']=='Meridian Avenue' else 1):
            center=door+front*(3.1+s*1.5)
            lateral=.51+float(rng.random())*.32
            phase=float(rng.uniform(0,math.tau));a=axis*span;b=front*lateral
            bounds=LineString([center-a,center+a]).buffer(lateral+.55)
            if carriageway.buffer(.8).intersects(bounds) or len(theory.query(bounds,predicate='intersects')):continue
            if any(shape.intersects(bounds) for cell in tiles(bounds) for shape in occupied[cell]):continue
            period=round(math.tau*span/float(rng.uniform(1.00,1.67)),3)
            z=[round(w.terrain_z(*(center+a*math.cos(t)+b*math.sin(t))),4) for t in np.arange(48)*math.tau/48]
            xy=center+a*math.cos(phase)+b*math.sin(phase);height=float(rng.uniform(1.55,1.90));p0=[*xy,w.terrain_z(*xy)]
            k=len(walks);spec=dict(name=f'meridian-pedestrian-{k}',walk=True,origin=p0,
                center=center.round(5).tolist(),a=a.round(5).tolist(),b=b.round(5).tolist(),phase=round(phase,7),
                period_s=period,heights=z,height_m=round(height,4),look=int(rng.integers(12)))
            m.rings(spec['name'],[(*xy,.18,.15,p0[2]-.018),(*xy,.31,.25,p0[2]+height*.74),
                    (*xy,.13,.12,p0[2]+height)],'pedestrian16',10,motion=spec,source_visual='meridian-pedestrian')
            walks.append(spec)
    # A pocket market occupies the eastern edge of the civic plaza. The centres of its
    # small businesses follow the pavement and leave an unscripted walking lane between them.
    pockets=[];stalls=[];furniture=[];crowds=[]
    for j,(xx,yy,angle) in enumerate([(-101,2276,-.39),(-108,2291,.13),(-91,2310,-.19),
            (-101,2330,.46),(-105,2350,.27),(-116,2365,-.25),(-243,2281,.52),(-259,2336,-.28),
            (-272,2309,.13),(-262,2361,-.32)]):
        c=np.array([xx,yy]);ax=np.array([math.cos(angle),math.sin(angle)]);fr=np.array([-ax[1],ax[0]])
        xy=lambda u,v:c+ax*u+fr*v
        site=Polygon([xy(u,v) for u,v in [(-4,-3),(4,-3),(4,3),(-4,3)]]).buffer(.55)
        if carriageway.buffer(1.75).intersects(site) or len(theory.query(site,predicate='intersects')):continue
        key=f'market-kiosk-{j}';z=min(w.terrain_z(*p) for p in list(site.exterior.coords)[::4])-.14
        def unit(name,points,skin,parent=None):
            return m.hull(key+'-'+name,[[*xy(u,v),z+h] for u,v,h in points],skin,parent=parent,
                          city=True,datum_m=z,tenancy=j%4,front=fr.round(6).tolist())
        floor=unit('counter',[(u,v,h) for u in (-2.64,2.64) for v in (-1.62,1.55) for h in (0,1.16)],'shopfront')
        # The counter is open above waist height. Separate masts carry the pitched canopy.
        for i,(u,v,height) in enumerate([(-2.4,-1.4,3.67),(2.4,-1.4,3.08),(-2.4,1.39,3.34),(2.4,1.39,3.52)]):
            unit('post'+str(i),[(u+s,v+t,h) for s in (-.075,.075) for t in (-.075,.075) for h in (1.12,height)],'fixture16',floor)
        corners=[(-3.23,-2.06,3.78),(3.20,-2.06,3.14),(3.31,2.15,3.63),(-3.42,2.18,3.46)]
        for i,tri in enumerate([[0,1,2],[0,2,3]]):
            unit('sail'+str(i),[(u,v,h+d) for u,v,h in [corners[k] for k in tri] for d in (-.17,.02)],'canopy16',key+'-post'+str(0 if i==0 else 2))
        stalls.append(dict(xy=c.round(3).tolist(),axis=ax.round(6).tolist(),front=fr.round(6).tolist(),z=z,kind=j%4))
        places.append(dict(xy=xy(0,1.59).round(3).tolist(),height_m=z+.76,front=fr.round(6).tolist(),
                           width_m=4.55,name=['COFFEE','FLOWERS','THE BAKERY','RECORDS','NOODLES'][j%5]))
        take(site);pockets.append(site)
        # Small, irregular orbits represent companions and people queueing outside each stand.
        for group in range(3):
            centre=xy(-3.6+group*3.6,5.5+(j+group)%3*1.8)
            for ii in range(3):
                p=centre+ax*ii*.91+fr*((ii+j)%2)*.63
                a=ax*(.42 if group==1 else 1.1);b=fr*.29
                mark=LineString([p-a,p+a]).buffer(.7)
                if carriageway.buffer(.75).intersects(mark) or len(theory.query(mark,predicate='intersects')) or any(o.intersects(mark) for o in pockets):continue
                crowds.append((p,a,b,j,group,ii))
        # Tables and seats are solid, grounded furnishings in the market rather than racing obstacles.
        for ii in (0,1):
            p=xy(-3.9+ii*6.4,-4.8-j%2*1.1);disc=shapely.Point(p).buffer(1.68)
            if carriageway.buffer(.95).intersects(disc) or len(theory.query(disc,predicate='intersects')) or any(o.intersects(disc) for o in pockets):continue
            z0=w.terrain_z(*p);base=m.rings(key+'-table-foot'+str(ii),[(*p,.32,.32,z0-.09),(*p,.12,.12,z0+.81)],'fixture16',12,city=True)
            m.rings(key+'-table'+str(ii),[(*p,.89,.89,z0+.77),(*p,.93,.93,z0+.85)],'awning16',20,city=True,parent=base)
            for jj in range(3):
                t=angle+jj*math.tau/3;chair=p+1.20*np.array([math.cos(t),math.sin(t)]);zc=w.terrain_z(*chair)
                seat=m.rings(key+f'-seat{ii}-{jj}',[(*chair,.28,.25,zc-.11),(*chair,.30,.29,zc+.45)],'canopy16',12,city=True)
                back=chair+np.array([math.cos(t),math.sin(t)])*.21
                m.rings(key+f'-back{ii}-{jj}',[(*back,.18,.10,zc+.40),(*back,.19,.10,zc+.75)],'awning16',10,city=True,parent=seat)
            pockets.append(disc);furniture.append(p.round(3).tolist())
    for p,a,b,j,g,i in crowds:
        phase=j*.57+g*1.61+i*.84;xy=p+a*math.cos(phase)+b*math.sin(phase);h=1.61+((j+g+i)%6)*.047
        z=[round(w.terrain_z(*(p+a*math.cos(t)+b*math.sin(t))),4) for t in np.arange(48)*math.tau/48]
        k=len(walks);p0=[*xy,w.terrain_z(*xy)];s=dict(name=f'meridian-pedestrian-{k}',walk=True,origin=p0,center=p.tolist(),
            a=a.tolist(),b=b.tolist(),phase=phase,period_s=26.1+3.7*((g*2+j+i)%7),heights=z,height_m=h,look=(k+j)%12)
        m.rings(s['name'],[(*xy,.18,.15,p0[2]-.018),(*xy,.31,.25,p0[2]+h*.74),(*xy,.13,.12,p0[2]+h)],'pedestrian16',10,motion=s,source_visual='meridian-pedestrian')
        walks.append(s)
    trees=[]
    walking=[LineString([np.array(p['center'])-p['a'],np.array(p['center'])+p['a']]).buffer(1.25) for p in walks]
    paths=STRtree(walking)
    for k,lot in enumerate(lots):
        if k%5 or lot['width']<23:continue
        axis=np.array(lot['axis']);front=np.array(lot['front']);door=np.array(lot['door'])
        xy=door+axis*lot['width']*.39+front*4.1
        site=shapely.Point(xy).buffer(1.05)
        if carriageway.buffer(3.1).intersects(site) or len(paths.query(site,predicate='intersects')) or not vacant(site):continue
        z=w.terrain_z(*xy);h=round(float(rng.uniform(4.2,8.4)),3)
        anchor=m.rings(f'market-tree-{k}',[(*xy,.24,.23,z-.25),(*xy,.20,.19,z+h*.54)],'citybark16',10,city=True)
        trees.append(dict(xy=xy.round(3).tolist(),z=round(z,3),h=h,anchor=anchor))
    out=dict(solids=m.solids,quarter=dict(name='Meridian Market Quarter',bounds_m=list(district.bounds),buildings=buildings,
             towers=towers,trees=trees,retained=retained,paving=footways,lots=lots,signs=places,people=walks,
             stalls=stalls,cafe_tables=furniture))
    import gzip
    (PACK/'market-16.json.gz').write_bytes(gzip.compress(json.dumps(out,separators=(',',':')).encode(),compresslevel=6,mtime=0))
    landscape_light(np.rint(w.heights*10),[o for o in w.obstacles+m.solids if not o.get('motion')],
                    'relief-market.png',sun=(-.89,.46,.19))
    print(buildings,'occupied buildings,',towers,'new high-rises,',len(walks),'walkers,',len(footways),'paving triangles,',len(m.solids),'solid features')


if __name__=='__main__':
    build()
