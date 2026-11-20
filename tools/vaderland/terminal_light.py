"""Bake soft sun and contact shadows from the surveyed terminal and trees."""
import argparse
import gzip
import json
from math import cos, sin, pi
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def boundary(points):
    pts=sorted(set(map(tuple,points)))
    def side(values):
        result=[]
        for p in values:
            while len(result)>1:
                a,b=result[-2:]
                if (b[0]-a[0])*(p[1]-a[1])>(b[1]-a[1])*(p[0]-a[0]):break
                result.pop()
            result.append(p)
        return result[:-1]
    return side(pts)+side(pts[::-1])


def bake(world,output):
    size=(1600,1280);sun=np.array([.89,-.45])/.26
    def pixel(x,y):return ((x+480)*size[0]/960,(140-y)*size[1]/800)
    shadow=Image.new('L',size,255);roots=Image.new('L',size,255)
    sh=ImageDraw.Draw(shadow);ao=ImageDraw.Draw(roots)
    for o in world['obstacles']:
        x,y,z=o['center'];a,b,c=o['half']
        if x<-520 or x>1010 or y<-930 or y>210:continue
        if o['kind']=='cylinder' and (not o.get('role') or o.get('role')=='conifer'):
            r=o.get('crown_radius_m',a)
            if r<.5:continue
            q=np.array([x,y]);top=max(0.,z+c);base=max(0.,z-c)
            sh.line([pixel(x,y),pixel(*(q-sun*top*.86))],fill=88,width=max(1,round(r*.23)))
            pts=[]
            for h,spread in [(.19,.65),(.40,1.),(.68,.79),(.91,.33),(1.,.06)]:
                p=q-sun*(base+(top-base)*h)
                pts.extend([pixel(p[0]+r*spread*cos(i*pi/6),p[1]+r*spread*sin(i*pi/6)) for i in range(12)])
            sh.polygon(boundary(pts),fill=78)
            ao.ellipse([pixel(x-r*.77,y+r*.77),pixel(x+r*.77,y-r*.77)],fill=50)
            continue
        if o['kind']=='mesh':
            v=np.array(o['vertices'])+o['center']
        elif o['kind']=='box':
            v=np.array([[x+u*a,y+t*b,z+h*c] for u in (-1,1) for t in (-1,1) for h in (-1,1)])
        else:
            v=np.array([[x+a*cos(i*pi/16),y+b*sin(i*pi/16),z+h*c] for i in range(32) for h in (-1,1)])
        if z+c<.32:continue
        projected=v[:,:2]-sun*np.maximum(0,v[:,2:3])
        poly=boundary([pixel(*p) for p in projected])
        if len(poly)>=3:sh.polygon(poly,fill=17)
        if z-c<1.5:
            foot=boundary([pixel(*p[:2]) for p in v])
            if len(foot)>=3:ao.polygon(foot,fill=32)
    direct=Image.blend(shadow.filter(ImageFilter.GaussianBlur(1.45)),shadow.filter(ImageFilter.GaussianBlur(8)),.33)
    occlusion=Image.blend(roots.filter(ImageFilter.GaussianBlur(2.6)),roots.filter(ImageFilter.GaussianBlur(12)),.46)
    Image.merge('RGB',(direct,occlusion,occlusion)).save(output,optimize=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('survey',type=Path)
    args=parser.parse_args()
    w=json.loads(gzip.decompress((args.survey/'world.json.gz').read_bytes()))
    bake(w,Path(__file__).resolve().parents[2]/'public/vtx-env/vaderland/terminal-light.png')
