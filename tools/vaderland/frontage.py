"""Curved diaphragm leaves, structural entrance ribbons and lighting on their surveyed foundations."""
import math
import numpy as np


def build(m):
    removed=[];doors=[];lights=[];beds=[];trims=[];trees=[]
    for side,direction in [('west',-1),('east',1)]:
        key='iris-'+side;mouth=1000+direction*30.;x=mouth+direction*1.55
        doors.append(dict(id=side,center=[x,-325.,18.],radius_m=12.1,travel_deg=50.3,stroke_s=4.))
        def radial(name,xlo,xhi,r1,r2,a,b,skin,parent):
            return m.hull(name,[[xx,-325+r*math.cos(t),18+r*math.sin(t)]
                          for xx in (xlo,xhi) for r in (r1,r2) for t in (a,b)],skin,parent=parent)
        # The plates enclose a real axial slot for the moving leaves. The spindle is fixed at both ends.
        fascia=mouth+direction*2.19
        for k in range(56):
            a,b=k*math.tau/56,(k+1)*math.tau/56
            back=radial(f'{key}-case-{k}',mouth,mouth+direction*2.19,18.67,18.96,a,b,'blacksteel',None
                        if k in (41,42) else f'{key}-case-{k+1 if k<41 else k-1}')
            radial(f'{key}-face-{k}',fascia,fascia+direction*.32,12.08,18.88,a,b,'blacksteel',back)
            radial(f'{key}-brass-{k}',fascia+direction*.30,fascia+direction*.39,12.22,12.52,a,b,'crestgold',f'{key}-face-{k}')
        for j in range(8):
            removed.append(f'{key}-leaf-{j}')
            base=math.radians(35)+j*math.tau/8;pivot_t=base+math.radians(8)
            py=-325+13.3*math.cos(pivot_t);pz=18+13.3*math.sin(pivot_t);px=x+(j%2)*.17
            moving=dict(name=key+'-'+str(j),origin=[px,py,pz],door=side,travel_rad=-math.radians(50.3),period_s=4.)
            shaft=m.hull(f'{key}-spindle-{j}',[[xx,py+.27*math.cos(a),pz+.27*math.sin(a)]
                       for xx in (mouth,fascia) for a in np.arange(16)*math.tau/16],'crestgold',
                       parent=f'{key}-frame-{int(pivot_t/math.tau*40)%40:02}')
            def polar(r,t):
                if r==0.:
                    return -325-.22*math.cos(base+.66),18-.22*math.sin(base+.66)
                theta=base+t*math.pi/4+math.radians(46)*(1-r**1.4)
                return -325+12.35*r*math.cos(theta),18+12.35*r*math.sin(theta)
            link=m.hull(f'{key}-crank-{j}',[[xx,yy,zz] for xx in (px-.06,px+.06)
                         for yy,zz in [polar(.94,.10),polar(1,.47),(py+.18,pz),(py-.18,pz),(py,pz+.21)]],
                         'blade',motion=moving,hinge=shaft)
            for band in reversed(range(6)):
                for k in range(3):
                    u,v=band/6,(band+1)/6;a,b=k/3,(k+1)/3
                    ring=[polar(u,a),polar(v,a),polar(v,b),polar(u,b)]
                    parent=link if band==5 and k==0 else (f'{key}-leaf-{j}-{band}-{k-1}' if k else f'{key}-leaf-{j}-{band+1}-0')
                    m.hull(f'{key}-leaf-{j}-{band}-{k}',[[xx,yy,zz] for xx in (px-.057,px+.057) for yy,zz in ring],
                           'blade',motion=moving,parent=parent)
            trims.append(dict(motion=moving,edge=[[[px+direction*.075,*polar(r,t)] for t in (0,.016)]
                          for r in np.linspace(.014,.997,35)]))
        # Two architecturally continuous ribs spring from the podium to the roof at each end.
        for off in (-1,1):
            prev=None
            for k in range(15):
                corners=[];roof=[];wall=[]
                for t in [k/15,(k+1)/15]:
                    a=t*math.pi/2;dy=(26.65 if off<0 else 34.8)*math.cos(a)
                    h=35.9*math.sin(a)-.14
                    xx=mouth+direction*(4.2+2.1*math.sin(a)+1.35*math.sin(2*a))
                    for edge in (-1,1):
                        for th in (0.,.61):
                            corners.append([xx+edge*1.76,-325.+off*(dy-th*math.cos(a)),h-th*math.sin(a)])
                    for rear in (mouth-direction*2.3,xx):
                        for dep in (0,.38):
                            roof.append([rear,-325.+off*(dy-dep*math.cos(a)),h-dep*math.sin(a)])
                    # The spandrel follows the real portal radius. An opening in the
                    # west records stair and a clear flight bore pass through its facade.
                    for r in (18.90,):
                        innery=off*r*math.cos(a);innerz=18+r*math.sin(a)
                        for thick in (0,.27):
                            wall.extend([[mouth+direction*(2.62+thick),-325+off*dy,h],
                                         [mouth+direction*(2.62+thick),-325+innery,innerz]])
                prev=m.hull(f'entrance-ribbon-{side}-{off}-{k}',corners,'crestsilver',parent=prev)
                m.hull(f'entrance-soffit-{side}-{off}-{k}',roof,'vault',parent=prev)
                # The stair lies below this spandrel; keep its 3.2 m passage open on the west.
                if not(side=='west' and off<0 and k<4):
                    m.hull(f'entrance-spandrel-{side}-{off}-{k}',wall,'blacksteel',parent=f'entrance-soffit-{side}-{off}-{k}')
        for j in range(48):
            a=math.tau*j/48.;rim=13.12
            yy=-325+rim*math.cos(a);zz=18+rim*math.sin(a)
            xface=fascia+direction*.33
            m.hull(f'{key}-bolt-{j}',[[xx,yy+.15*math.cos(t),zz+.15*math.sin(t)]
                for xx in [xface-direction*.08,xface+direction*.14] for t in np.arange(6)*math.tau/6],
                'crestsilver',parent=f'{key}-face-{int(j/48*56)%56}')
    # The office's door is on a pedestrian walk. Furniture and lamps stay outside the vehicle wash.
    for j,x in enumerate((927.,943.,958.,976.,995.,1013.,1031.,1047.,1065.,1081.)):
        road_y=float(np.interp(x,[890,958,1060,1110],[-366,-359,-359,-353]))
        for side in (-1,1):
            y=road_y+side*6.85;p=m.box(f'frontage-lamp-foot-{j}-{side}',x,y,-.12,.13,.30,.27,'blacksteel')
            post=m.hull(f'frontage-lamp-{j}-{side}',[[x+u,y+v,h] for h,a,b in [(.10,.21,.18),(.97,.18,.15),(1.16,.16,.145)]
                    for u,v in [(-a,-b),(a,-b),(a,b),(-a,b)]],'blacksteel',parent=p)
            lens=m.box(f'frontage-lens-{j}-{side}',x,y,.83,.985,.187,.159,'lamplens',parent=post)
            lights.append(dict(xyz=[x,y,.977],site='frontage',size=.20,anchor=lens))
    for j,(x,y,a,b) in enumerate([(1037.,-351.2,3.6,1.04),(1065.,-366.5,4.9,1.36),
            (1082.,-365.7,3.8,1.15),(982.,-351.4,3.2,1.),(949.,-349.5,3.8,1.1)]):
        bed=m.rings('operations-planter-'+str(j),[(x,y,a,b,-.15),(x,y,a,b,.35),(x,y,a-.04,b-.04,.49)],'planterstone',32)
        beds.append(dict(center=[x,y,.48],half=[a,b],anchor=bed))
    for j,(dx,dy) in enumerate([(-22,-18),(22,-18),(-22,18),(22,18)]):
        x,y=-183+dx,2325+dy;z=31.2
        base=m.rings('crest-uplight-'+str(j),[(x,y,.59,.59,z-.04),(x,y,.53,.53,z+.46)],'blacksteel',22)
        cap=m.rings('crest-lens-'+str(j),[(x,y,.43,.43,z+.44),(x,y,.41,.41,z+.49)],'lamplens',22,parent=base)
        lights.append(dict(xyz=[x,y,z+.50],site='plaza',size=.36,anchor=cap))
    for j,(x,y,h) in enumerate([(1074,-368.4,8.1),(1047,-373.5,6.8),(1015,-376,8.2),(974,-375,6.4),(948,-378.5,7.2)]):
        trunk=m.rings(f'operations-shade-tree-{j}',[(x,y,.30,.29,-.12),(x,y,.24,.22,h*.33),(x+.22,y,.14,.13,h*.65)],'bark',19)
        trees.append(dict(center=[x,y,-.06],height=h,anchor=trunk))
    path=np.array([[903.6,-364.6],[958.,-359.],[1060.,-359.],[1097.5,-354.5]])
    gradients=np.gradient(path,axis=0);normals=gradients[:,[1,0]]*[-1,1]/np.linalg.norm(gradients,axis=1)[:,None]
    for s in (-1,1):
        for j in range(len(path)-1):
            for name,near,far,level,skin in [('walk',5.05,9.45,.115,'planterstone'),('kerb',4.99,5.23,.153,'sandstone')]:
                m.hull(f'operations-{name}-{s}-{j}',[[*(path[k]+s*normals[k]*v),h]
                     for k in (j,j+1) for v in (near,far) for h in [-.12,level]],skin)
    return dict(removed=removed,doors=doors,lights=lights,beds=beds,trims=trims,trees=trees)
