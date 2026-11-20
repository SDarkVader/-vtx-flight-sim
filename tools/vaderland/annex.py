"""Install the source cylinder on bearings beside the airport, with two independent irises."""
import math
import numpy as np


def build(m):
    cx,cy,axis=1000.,-325.,18.
    radius=12.35;outer=15.4;length=60.;doors=[]
    def radial(name,x0,x1,inside,outside,a,b,skin,**extras):
        return m.hull(name,[[x,cy+r*math.cos(t),axis+r*math.sin(t)]
                  for x in (x0,x1) for r in (inside,outside) for t in (a,b)],skin,**extras)
    # A continuous inhabited foundation fills the space beneath the drum. The
    # barrel is recessed into stepped stone and glazed galleries on both sides.
    plinth=m.box('office-podium',cx,cy,-.62,2.64,31.5,17.7,'basalt')
    for side in (-1,1):
        shoulder=(10.38,10.38) if side<0 else (11.65,12.62)
        pts=[[cx+dx,cy+side*y,z] for dx in (-31.45,31.45) for y,z in
             [(0,2.57),(17.6,2.57),(17.6,shoulder[0]),(15.15,shoulder[1]),(13.70,10.69),(10.9,7.05),(7.7,4.66),(3.2,2.92)]]
        m.hull('office-foundation-'+str(side),pts,'sandstone',parent=plinth)
    for idx,x in enumerate((cx-23,cx+23)):
        m.box('office-saddle-base-'+str(idx),x,cy,-.42,2.32,3.6,15.1,'basalt')
        for s in (-1,1):
            m.hull(f'office-saddle-{idx}-{s}',[[u,cy+s*v,z] for u in [x-3.2,x+3.2]
                    for v,z in [(0,2.20),(14.5,2.20),(14.5,10.6),(12.85,10.16),(9.6,6.05),(5.3,3.72),(0,2.74)]],
                   'sandstone',parent='office-saddle-base-'+str(idx))
    for j in range(40):
        a=j*math.tau/40;b=a+math.tau/40
        mid=(a+b)/2
        parent='office-saddle-0-'+('1' if math.cos(mid)>0 else '-1') if j in (29,30) else 'barrel-'+str((j+1)%40 if j<29 else j-1)
        skin='barrelglass' if .0<math.sin(mid)<.94 or -.78<math.sin(mid)<-.18 else 'vault'
        radial('barrel-'+str(j),cx-30,cx+30,14.92,outer,a,b,skin,parent=parent,landable=math.sin(mid)>.75)
    for s,side in [(-1,'west'),(1,'east')]:
        x=cx+s*length/2;group='iris-'+side
        doors.append(dict(id=side,center=[x,cy,axis],radius_m=radius,travel_deg=76.,stroke_s=4.))
        for j in range(40):
            a=j*math.tau/40;b=a+math.tau/40
            radial(f'{group}-frame-{j:02}',x-.62,x+.62,radius,15.88,a,b,'sandstone',parent='barrel-'+str(j),frame=side)
        for j in range(8):
            a=(j-.5)*math.tau/8;b=a+math.tau/8
            pivot=[x+(j%2)*.12,cy+radius*math.cos(a),axis+radius*math.sin(a)]
            poly=[(0.,0.)]+[(radius*math.cos(t),radius*math.sin(t)) for t in np.linspace(a,b,7)]
            pts=[[pivot[0]+d,cy+u,axis+v] for u,v in poly for d in [-.056,.056]]
            motion=dict(name=group+'-'+str(j),origin=pivot,door=side,travel_rad=-math.radians(76),period_s=4)
            m.hull(group+'-leaf-'+str(j),pts,'blade',motion=motion,hinge=group+'-frame-'+format((j*5-2)%40,'02'))
    # A level inhabited gallery is built beside the central flight bore.
    # Its glazing, rail, inspection walk and furnishings all lie beyond the protected radius.
    floor=10.8;side_y=-344.0
    for s in (-1,1):
        m.box('office-ground-gallery-'+str(s),cx,side_y+s*5.13,-.44,10.49,26.1,.28,'hallglass')
    m.box('office-ground-gallery-east',cx+25.85,side_y,-.44,10.49,.30,5.18,'walnut')
    slab=m.box('office-gallery-floor',cx,side_y,10.42,floor,26,5.3,'walnut',parent='office-ground-gallery-1')
    # The north side houses the ground-level departmental wing, on its own bearings.
    m.hull('office-north-wing',[[cx+dx,cy+y,z] for dx in (-29.5,29.5) for y,z in
            [(12.,-.50),(24.,-.50),(24.,6.0),(22.3,8.5),(15.05,13.0),(12.0,10.9)]],'wingglass')
    for y in [side_y-5.20,side_y+5.16]:
        m.box('records-glass-'+str(y),cx,y,floor-.04,15.1,25.9,.11,'officeglass',parent=slab)
    m.box('records-end-wall',cx+25.8,side_y,floor-.04,15.1,.2,5.25,'walnut',parent=slab)
    m.box('records-office-roof',cx,side_y,15.07,15.46,26.3,5.48,'vault',parent='records-end-wall')
    # A level stair landing connects the office to its own pedestrian entrance on the west.
    for j in range(59):
        top=(j+1)*floor/59.
        m.box('records-stair-'+str(j),955.12+j*.32,side_y,-.15,top,.161,1.6,'sandstone')
    # The cylinder forms the spine of a single occupied building. Folded wing roofs
    # join the outer barrel high above the flight envelope and spring from full-height facades.
    for side,width in [(-1,25.1),(1,37.0)]:
        edge=cy+side*width
        for j,(start,end) in enumerate([(-34.,-13.),(-10.,9.),(13.,34.)]):
            m.box(f'annex-frontage-{side}-{j}',cx+(start+end)/2,edge,-.46,10.65,(end-start)/2,.23,'officeglass')
        for j,(u,v) in enumerate(zip([0,.19,.39,.62,.84],[.19,.39,.62,.84,1.])):
            def roof(q):
                dy=8.0+(width-8)*q
                return dy,10.6+22.0*(1-q)**1.27,34.4+1.4*math.sin(math.pi*q)
            pts=[[cx+s*ext,cy+side*dy,h-d] for q in [u,v] for dy,h,ext in [roof(q)] for s in [-1,1] for d in [0,.38]]
            name=f'annex-fold-{side}-{j}'
            parent=f'annex-frontage-{side}-0' if j==4 else f'annex-fold-{side}-{j+1}'
            m.hull(name,pts,'vault',parent=parent,landable=True)
        for face in (-1,1):
            x=cx+face*34.15
            entry=side==-1 and face==-1
            bays=[(12.5,16),(16,17.0),(21.,width)] if entry else [(12.5,16),(16,width)]
            for j,(a,b) in enumerate(bays):
                def cap(u):return 10.56+22.*(1-(u-8.)/(width-8.))**1.27
                m.hull(f'annex-end-{side}-{face}-{j}',[[x+q,cy+side*u,z] for q in [-.28,.28]
                         for u in [a,b] for z in [-.45,cap(u)]],'wingglass')
            if entry:
                m.hull('records-stair-lintel',[[x+q,cy-u,z] for q in [-.28,.28]
                    for u in (17.,21.) for z in (10.25,cap(u))],'wingglass',parent='annex-end--1--1-2')
    # The public road stays clear of all the saddles and supports.
    access=[[331.,-359.],[393.,-371.],[551.,-388.],[740.,-383.],[890.,-366.],[958.,-359.],
            [1060.,-359.],[1110.,-353.],[1138.,-338.],[1150.,-316.],[1144.,-296.],
            [1124.,-280.],[1090.,-272.],[987.,-276.],[830.,-267.],[670.,-250.],[498.,-255.],
            [401.,-272.],[328.,-297.]]
    return dict(center=[cx,cy,axis],inside_m=[length,29.84],clear_bore_radius_m=11.,outside_diameter_m=30.8,
        approaches_m=[650.,650.],doors=doors,design_plot=dict(center=[1000.,-455.],clear_m=[68.,102.,34.]),
        office=dict(center=[1000,side_y,floor],clear_m=[51.4,10.2],owner='Arthur Finch'),
        access=dict(name='Meridian Operations Circuit',kind='local',width_m=9.4,points=access))
