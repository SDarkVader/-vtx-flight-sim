"""Freeze the fourth survey with local glacial relief and the airport/city nightscape."""
import json
import struct
import zlib
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter
from scipy.spatial import cKDTree

from bake import AXIS, HALF, PACK, ROOT, STEP, coast_chart, geography, landscape_light
from city import build as city_survey, TestWorld
from network import build as route_survey


def ground_material(world,buildings,roads,filename='civic-ground.png'):
    # Paint site aprons, footways and vegetation colour into the terrain itself.
    # This texture cannot lift a road, shift a foundation or change a collision.
    n=1601;axis=np.linspace(-HALF,HALF,n);step=axis[1]-axis[0]
    sites=np.zeros((n,n),bool);streets=np.zeros_like(sites)
    for o in buildings:
        if o.get('role')!='architecture' or o.get('support')=='stack':continue
        x,y,_=o['center'];a,b,_=o['half']
        i0,i1=np.searchsorted(axis,[x-a-13,x+a+13]);j0,j1=np.searchsorted(axis,[y-b-13,y+b+13])
        sites[j0:j1,i0:i1]=True
    for road in roads:
        if 'deck_z_m' in road or road['kind']=='track':continue
        pts=np.array(road['points'])
        for a,b in zip(pts,pts[1:]):
            p=np.linspace(a,b,max(2,int(np.linalg.norm(b-a)/7)+1))
            ij=np.rint((p+HALF)/step).astype(int)
            streets[ij[:,1],ij[:,0]]=True
    blocks=gaussian_filter(sites.astype(float),4.2)
    dist=distance_transform_edt(~streets)*step
    pavement=np.maximum(sites*.86,np.clip(1-(dist-9)/24,0,1)*.75)
    path=np.clip((blocks-.13)*1.7,0,1)
    rgb=np.uint8(np.stack([pavement,path,np.minimum(1,dist/200)],axis=-1)[::-1]*255)
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    raw=b''.join(b'\0'+row.tobytes() for row in rgb)
    data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',n,n,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')
    (ROOT/'public/vtx-env/vaderland'/filename).write_bytes(data)


def final_survey():
    chart=coast_chart()
    terrain=geography(chart,local_canyon=True)
    terrace,city=city_survey(terrain)
    terrain,network=route_survey(np.rint(terrace*10).astype('<u2'),city,refine=True)
    w=object.__new__(TestWorld);w.heights=terrain*.1;w.n=len(terrain);w.half=HALF
    obstacles=city['obstacles']+network['obstacles']
    # Modest ward infill at street scale. Long wings, courtyards, service lanes
    # and terrace gardens articulate the plots around the taller placeholders.
    routes=city['routes']+network['routes']
    road_points=[];widths=[]
    for r in routes:
        for a,b in zip(np.array(r['points']),np.array(r['points'])[1:]):
            samples=np.linspace(a,b,max(2,int(np.linalg.norm(b-a)/12)+1))
            road_points.extend(samples);widths.extend([r['width_m']/2]*len(samples))
    tree=cKDTree(road_points);widths=np.array(widths)
    bases=[o for o in city['obstacles'] if o.get('support')!='stack']
    def clear(x,y,a,b):
        d,k=tree.query([x,y],k=8)
        if np.min(d-widths[k])<max(a,b)+4:return False
        return not any(abs(x-o['center'][0])<a+o['half'][0]+6 and
                       abs(y-o['center'][1])<b+o['half'][1]+6 for o in bases)
    rng=np.random.default_rng(4481)
    for k in range(1630):
        x,y=np.round(rng.uniform([-2740,770],[2580,4610]),1)
        core=np.exp(-((x+230)/1800)**2-((y-2250)/1560)**2)
        if rng.random()>.3+.67*core:continue
        a,b=round(rng.uniform(9,24),1),round(rng.uniform(12,36),1)
        if not clear(x,y,a,b):continue
        levels=[w.terrain_z(x+dx,y+dy) for dx in [-a,0,a] for dy in [-b,0,b]]
        base=min(levels)-1.5;top=max(levels)+round(rng.uniform(6,20)+core*rng.uniform(1,17),1)
        o=dict(id=f'courtyard-{k}',kind='box',center=[x,y,(top+base)/2],half=[a,b,(top-base)/2],
               color=rng.choice(['#37484d','#42535c','#5d554a','#39484c']),role='architecture',landable=True)
        obstacles.append(o);bases.append(o)
    # Small colonnaded wings around the surviving airport apron. All independent
    # pieces originate below the surveyed grade. They can be struck in the plant.
    for side in (-1,1):
        for i in range(5):
            x=side*(104+30*i);y=-373-i*9
            a=13.5;b=26-i*2.;top=11+i*1.7
            obstacles.append(dict(id=f'terminal-gallery-{side}-{i}',kind='box',center=[x,y,(top-1)/2],
                             half=[a,b,(top+1)/2],role='architecture',color='#465057',landable=True))
    network.update(obstacles=obstacles,routes=routes,places=city['places']+network['places'])
    np.savez_compressed(PACK/'vaderland-04.npz',height_dm=terrain)
    (PACK/'vaderland-04.json').write_text(json.dumps(network,separators=(',',':'))+'\n',encoding='utf-8')
    landscape_light(terrain,obstacles+network['groves'],'relief-final.png')
    ground_material(w,obstacles,routes)
    print('Review survey',len(obstacles),'structural elements',len(network['groves']),'pines')


if __name__=='__main__':
    final_survey()
