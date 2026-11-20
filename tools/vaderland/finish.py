"""Join road grades across the watershed and finish the Meridian airport precinct."""
import json
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from bake import AXIS, HALF, PACK, STEP, X, Y, geography, grid_water, landscape_light, smooth
from city import TestWorld
from refine import ground_material
from roads import sections


def survey(z):
    w=object.__new__(TestWorld)
    w.n=len(z);w.half=HALF;w.heights=z
    return w


def ribbon(z,xy,heights,inner,outer,lower_only=False):
    lo=np.maximum(0,np.searchsorted(AXIS,xy.min(axis=0)-outer-30))
    hi=np.minimum(len(z),np.searchsorted(AXIS,xy.max(axis=0)+outer+30))
    bounds=np.s_[lo[1]:hi[1],lo[0]:hi[0]]
    block=z[bounds]
    q=np.column_stack((X[bounds].ravel(),Y[bounds].ravel()))
    distance,index=cKDTree(xy).query(q)
    target=heights[index].reshape(block.shape)
    if lower_only:target=np.minimum(target,block)
    block+=(target-block)*(1-smooth(inner,outer,distance.reshape(block.shape)))


def build():
    old=np.load(PACK/'vaderland-04.npz')['height_dm']*.1
    data=json.loads((PACK/'vaderland-04.json').read_text())
    chart=json.loads((PACK/'coast-01.json').read_text())
    z=geography(chart,local_canyon=True).astype(float)/10
    terrace=9+.012*np.maximum(Y-500,0)+.06*np.maximum(Y-4050,0)+2*np.sin(X/470+Y/680)
    edge=np.maximum.reduce([-3160-X,X-2960,590-Y,Y-5690])
    z+=(np.minimum(z,terrace)-z)*(1-smooth(10,1080,edge))
    # Keep natural foothills and a continuous carved canyon beyond the wards.
    for stream in data['streams']:
        xy=np.array(stream['points'])
        river=np.array([survey(old).terrain_z(*p) for p in xy])*.57
        ribbon(z,xy,river,38,540)
    # Broad glacial saddle beneath the east viaduct avoids an artificial wall
    # around the high-speed route. Leave the hills on either side intact.
    crown=next(r for r in data['routes'] if r['name']=='Crown viaduct')
    cp=np.array(crown['points'])
    ribbon(z,cp,np.full(len(cp),180.),160,1080,True)
    # Extend the alluvial bench into the southeast gallery and proving circuit.
    south=np.maximum.reduce([2550-X,X-7010,Y+2120,-5280-Y])
    bench=113+.024*np.maximum(-Y-3000,0)+.004*(X-3300)
    z+=(bench-z)*(1-smooth(0,750,south))
    # A real loop serves the gate frontage and north apron, sharing the existing
    # western access. More demanding machines must respect the bends.
    ring=[[round(335*np.cos(t),2),round(-335+158*np.sin(t),2)] for t in np.linspace(0,2*np.pi,105)]
    data['routes']+= [
        dict(name='Terminal boulevard',width_m=12,kind='boulevard',points=ring),
        dict(name='Apron link',width_m=12,kind='boulevard',points=[[-600,-83],[-469,-98],[-315,-154],[-207,-211]])]
    roads=data['routes']
    sections_xy=[sections(r) for r in roads]
    coords=np.vstack(sections_xy)
    sizes=np.array([len(q) for q in sections_xy]);offset=np.r_[0,np.cumsum(sizes)]
    label=np.repeat(np.arange(len(roads)),sizes)
    grade=np.repeat([.157 if r['kind']=='track' else .082 for r in roads],sizes)
    targets=[];portals=np.ones(len(coords),bool);constant=[]
    heights={'Sound crossing':22.,'Crown viaduct':217.,'Falls bridge':247.,'Cut-and-cover gallery':146.,'Proving apron':179.}
    w=survey(z)
    for i,(road,xy) in enumerate(zip(roads,sections_xy)):
        levels=gaussian_filter1d([w.terrain_z(*p) for p in xy],9,mode='nearest')
        if road['name'] in heights:
            levels[:]=heights[road['name']]
            constant.append(i)
            if road['kind'] in ('viaduct','tunnel'):
                portals[offset[i]+10:offset[i+1]-10]=False
        levels[np.abs(xy[:,1])<530]=0
        targets.extend(levels)
    pairs=cKDTree(coords).query_pairs(16.,output_type='ndarray')
    a,b=pairs.T
    keep=(label[a]==label[b])|(portals[a]&portals[b])
    a,b=a[keep],b[keep]
    cost=np.maximum(1e-9,np.linalg.norm(coords[a]-coords[b],axis=1)*np.minimum(grade[a],grade[b]))
    source=len(coords)+len(constant)
    starts=[a,b,np.full(len(coords),source)]
    ends=[b,a,np.arange(len(coords))]
    costs=[cost,cost,np.maximum(1e-9,targets)]
    for j,i in enumerate(constant):
        ix=np.arange(offset[i],offset[i+1])
        hub=np.full(len(ix),len(coords)+j)
        starts.extend([hub,ix]);ends.extend([ix,hub]);costs.extend([np.full(len(ix),1e-9)]*2)
    # Multi-source shortest paths give a rise-limited surface over the entire
    # connected network. Equal-elevation hubs keep bridge decks and gallery level.
    matrix=csr_matrix((np.concatenate(costs),(np.concatenate(starts),np.concatenate(ends))),shape=(source+1,source+1))
    levels=dijkstra(matrix,directed=True,indices=source)[:len(coords)]
    for i,r in enumerate(roads):
        if r['name'] in heights:heights[r['name']]=round(float(levels[offset[i]]),1)
    # A broad first grading pass blends into the hillside. Finish all roadway
    # cells together so a later cut cannot introduce a step across a junction.
    ground_ix=np.repeat([r['kind']!='viaduct' for r in roads],sizes)
    bank=coords[ground_ix];rz=levels[ground_ix]
    widths=np.repeat([r['width_m']/2 for r in roads],sizes)[ground_ix]
    for i,r in enumerate(roads):
        if r['kind']=='viaduct':continue
        xy=sections_xy[i]
        ribbon(z,xy,levels[offset[i]:offset[i+1]],r['width_m']/2+34,r['width_m']/2+195)
    tree=cKDTree(bank)
    grid=np.column_stack((X.ravel(),Y.ravel()))
    d,ix=tree.query(grid)
    strength=1-smooth(widths[ix]+28,widths[ix]+105,d)
    z+=(rz[ix].reshape(z.shape)-z)*strength.reshape(z.shape)
    for i,r in enumerate(roads):
        if r['kind']!='viaduct':continue
        xy=sections_xy[i];length=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        top=heights[r['name']];r['deck_z_m']=top
        clearance=np.minimum(np.minimum(length,length[-1]-length)*.24,124)
        ribbon(z,xy,top-clearance,r['width_m']/2+12,265,True)
        # Bearings meet the land at each end at the exact carriageway height.
        for j in (0,-1):
            q=xy[[j]]
            ribbon(z,q,np.array([top]),r['width_m']/2+16,r['width_m']/2+64)
    apron=next(r for r in roads if r['kind']=='apron')
    reach=np.maximum(np.abs(X-4900)-425,np.abs(Y+4890)-apron['width_m']/2)
    z+=(heights['Proving apron']-z)*(1-smooth(26,130,reach))
    # Maintain sight and wheel contact beyond the portal. The candidate's
    # east-side rise began inside its safe braking and sight distance.
    gallery=np.column_stack((np.linspace(2740,3670,160),np.full(160,-4350.)))
    ribbon(z,gallery,np.full(len(gallery),heights['Cut-and-cover gallery']),37,126)
    for s in data['spans']:
        road=next(r for r in roads if r['name']==s['name'])
        path=np.asarray(road['points'])
        for end,neighbor in [(0,1),(-1,-2)]:
            out=path[end]-path[neighbor];out/=np.linalg.norm(out)
            approach=path[end]+np.linspace(7,88,18)[:,None]*out
            ribbon(z,approach,np.full(len(approach),heights[s['name']]),road['width_m']/2+14,75)
    # Keep the surveyed water level and original inner berths. No road follows
    # the wet bed. The single water crossing has its own supported deck.
    wet=grid_water(chart)
    z[wet]=np.minimum(z[wet],old[wet])
    z[abs(Y)<=500]=0
    terrain=np.rint(np.maximum(0,z)*10).astype('<u2')
    w=survey(terrain*.1); previous=survey(old)
    def bounds(world,o):
        x,y,_=o['center'];a,b,_=o['half']
        xx=np.unique(np.r_[x-a,AXIS[(AXIS>x-a)&(AXIS<x+a)],x,x+a])
        yy=np.unique(np.r_[y-b,AXIS[(AXIS>y-b)&(AXIS<y+b)],y,y+b])
        zz=[world.terrain_z(i,j) for i in xx for j in yy]
        return min(zz),max(zz)
    def set_z(o,lo,hi):
        o['center'][2]=round((hi+lo)/2,4);o['half'][2]=round((hi-lo)/2,4)
    tops={}
    new=[]
    for o in data['obstacles']:
        support=o.get('support')
        if o.get('span') in heights or any(o['id'].startswith(s['name']+'-pier-') for s in data['spans']):continue
        lo=o['center'][2]-o['half'][2];hi=lo+2*o['half'][2]
        if o['id'].startswith('gallery-'):
            delta=heights['Cut-and-cover gallery']-146
            set_z(o,lo+delta,hi+delta)
        elif support=='stack':
            delta=tops[o['parent']]
            set_z(o,lo+delta,hi+delta)
        elif support!='span' and o['role']!='pier':
            _,oldhi=bounds(previous,o);newlo,newhi=bounds(w,o)
            set_z(o,newlo-1.4,newhi+max(2,hi-oldhi))
        elif o['role']=='pier':
            set_z(o,bounds(w,o)[0]-2,hi)
        tops[o['id']]=o['center'][2]+o['half'][2]-hi
        new.append(o)
    old_objects={o['id']:o for o in data['obstacles']}
    for s in data['spans']:
        name=s['name'];road=next(r for r in roads if r['name']==name)
        top=road['deck_z_m'];s['top_m']=top;s['piers']=[]
        segments=[o for o in old_objects.values() if o.get('span')==name]
        for o in segments:
            set_z(o,top-2.8,top)
        new.extend(segments)
        xy=np.array(road['points']);dist=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        stations=np.linspace(0,dist[-1],int(np.ceil(dist[-1]/59))+1)
        s['max_station_spacing_m']=round(float(np.max(np.diff(stations))),2)
        for j,chain in enumerate(stations):
            x,y=[round(float(np.interp(chain,dist,xy[:,k])),2) for k in (0,1)]
            bottom=min(w.terrain_z(x+u,y+v) for u,v in [(0,0),(4,0),(-4,0),(0,4),(0,-4)])-2
            if bottom>=top-2.8:continue
            oid=f'{name}-pier-{j}';s['piers'].append(oid)
            o=dict(id=oid,kind='cylinder',center=[x,y,0],half=[3.4,3.4,1],role='pier',landable=False,color='#73717a')
            set_z(o,bottom,top-2.55);new.append(o)
    # Survey new small conifer stands along the harbour and airport. Each trunk
    # and crown has a corresponding grounded solid in the physics world.
    groves=[];rng=np.random.default_rng(7621)
    blocks=[o for o in new if o['role']=='architecture' and o.get('support')!='stack']
    for k in range(2100):
        x,y=rng.normal([0,-340],[430,140]) if k<800 else rng.normal([(-1750,-1300),(-400,-880),(1480,-1260),(-5200,3860),(-5280,3230),(-2680,-6010)][k%6],[260,155])
        if y>-125 and abs(x)<3900 or abs(y)<=525 and abs(x)>3880:continue
        if abs(x)>7950 or abs(y)>7950 or wet[round((y+HALF)/STEP),round((x+HALF)/STEP)]:continue
        d,kx=tree.query([x,y],k=5)
        if np.any(d<widths[kx]+5) or any(abs(x-o['center'][0])<o['half'][0]+5 and abs(y-o['center'][1])<o['half'][1]+5 for o in blocks):continue
        if -630<y<-525 and -85<x<380:continue
        h=round(rng.uniform(7,20),2)
        groves.append(dict(id=f'precinct-pine-{k}',kind='cylinder',center=[round(x,2),round(y,2),h/2],half=[h*.17,h*.17,h/2],
            color=rng.choice(['#314932','#526341','#364d39','#344b33']),landable=False))
    kept=[]
    for o in data['groves']+groves:
        x,y,_=o['center'];r,_,hh=o['half'];d,k=tree.query([x,y],k=4)
        if np.any(d<widths[k]+r+2):continue
        foot=min(w.terrain_z(x+a,y+b) for a,b in [(0,0),(r,0),(-r,0),(0,r),(0,-r)])
        set_z(o,foot-.55,foot-.55+2*hh);kept.append(o)
    data.update(obstacles=new,groves=kept)
    np.savez_compressed(PACK/'meridian-05.npz',height_dm=terrain)
    (PACK/'meridian-05.json').write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8')
    landscape_light(terrain,new+kept,'relief-meridian.png')
    ground_material(w,new,roads,'civic-meridian.png')
    print('Connected grades',heights,'structures',len(new),'trees',len(kept))


if __name__=='__main__':
    build()
