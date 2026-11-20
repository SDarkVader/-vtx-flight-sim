"""Forge a freestanding, rotating version of the winged V carried by the Meridian terminal."""
import json
from pathlib import Path

from drafting import Masonry


def build():
    pack=Path(__file__).resolve().parents[2]/'inputs/vaderland'
    plaza=json.loads((pack/'civic-13.json').read_text())['civic']
    x,y,z=plaza['statue']['center']
    m=Masonry()
    motion=dict(name='vaderland-crest',origin=[x,y,z],period_s=120.)
    def solid(name,vertices,skin,parent):
        return m.hull('crest-'+name,[[x+u,y+v,z+h] for u,v,h in vertices],skin,parent=parent,motion=motion)
    foot=m.rings('crest-thrust-bearing',[(x,y,5.40,4.55,z-.12),(x,y,5.40,4.55,z+.47),
            (x,y,4.55,3.87,z+.92)],'darkbronze',65,parent='civic-turntable',motion=motion)
    keel=solid('keel',[(u,v,h) for h,a,b in [(.85,4.1,3.2),(3.65,3.95,3.1),(9.0,2.2,2.4)]
                       for u,v in ((-a,0),(0,-b),(a,0),(0,b))],'blacksteel',foot)
    # Each section is folded around a ridge on both faces. The plan sweeps aft as it rises.
    # The open, secondary cuts join their main wing at the outer end.
    blade=[(0.,2.1,11.1,3.20,0.),(3.,1.72,14.02,3.95,-.10),
           (7.70,6.47,20.52,4.73,-.38),(13.05,13.06,27.63,4.94,-.10),
           (19.65,20.99,33.12,4.23,.99),(26.51,28.25,36.45,3.10,2.82),
           (33.28,35.11,39.15,1.50,4.69),(38.20,41.55,41.73,.17,6.45)]
    plume=[(3.48,19.04,19.57,.30,-.48),(6.80,20.65,23.56,1.22,-.56),
           (12.75,25.76,30.48,2.12,.42),(18.55,30.77,34.57,2.12,1.22),
           (23.70,33.37,36.10,1.14,2.13),(27.08,35.70,36.79,.38,2.97)]
    def section(side,row):
        u,lo,hi,d,offset=row
        return [[side*u,offset+b,h] for b,h in [(-.29*d,lo),(-d,lo+.43*(hi-lo)),(-.19*d,hi),
                                                (.23*d,hi),(.88*d,lo+.56*(hi-lo)),(.23*d,lo)]]
    def lip(side,row,face):
        u,lo,hi,d,offset=row
        h=hi-lo
        return [[side*u,offset+face*k*d,height] for k,height in
                [(.18,hi+.022),(.28,hi-.043*h),(.36,hi-.098*h)]]
    for side in (-1,1):
        parent=keel;main=[]
        for i,(a,b) in enumerate(zip(blade,blade[1:])):
            name=f'wing-{side}-{i}'
            parent=solid(name,section(side,a)+section(side,b),'blacksteel',parent);main.append(parent)
            for face in (-1,1):
                solid(f'gold-edge-{side}-{i}-{face}',lip(side,a,face)+lip(side,b,face),'crestgold',parent)
        parent=main[-2]
        for i in reversed(range(len(plume)-1)):
            a,b=plume[i:i+2]
            parent=solid(f'inner-quill-{side}-{i}',section(side,a)+section(side,b),'crestsilver',parent)
    crest=dict(center=[x,y,z],width_m=76.4,height_m=41.752,period_s=120.,bearing='civic-turntable')
    from frontage import build as frontage
    site=frontage(m)
    (pack/'crest-14.json').write_text(json.dumps(dict(solids=m.solids,monument=crest,frontage=site),separators=(',',':'))+'\n')


if __name__=='__main__':build()
