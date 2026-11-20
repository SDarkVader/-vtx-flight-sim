"""Run in Blender to build the continuous terminal asset and its editable local source."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

root=Path(__file__).resolve().parents[2]
out=root/'public/vtx-env/vaderland/meridian-terminal.glb'
source=Path(sys.argv[sys.argv.index('--')+1])
plan=json.loads((root/'inputs/vaderland/arrivals-11.json').read_text(encoding='utf8'))
operations='--operations' in sys.argv
if operations:
    overlay=json.loads((root/'inputs/vaderland/operations-12.json').read_text())
    replaced=set(overlay['removed']);plan['solids']=[o for o in plan['solids'] if o['id'] not in replaced]
    out=out.with_name(overlay['operations']['terminal_asset'])
bpy.ops.wm.read_factory_settings(use_empty=True)
palette={'Glass':(.075,.15,.20),'Nickel':(.10,.13,.16),'Skylight':(.052,.12,.17),
         'Bronze':(.52,.29,.105),'Light':(1.,.65,.28),'Stone':(.23,.23,.20),
         'Planting':(.15,.22,.10),'Soffit':(.23,.16,.11),'Shaft':(.41,.41,.36),'Mark':(.86,.65,.30)}
materials={}
for name,color in palette.items():
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    principal=m.node_tree.nodes.get('Principled BSDF');principal.inputs['Base Color'].default_value=(*color,1)
    principal.inputs['Metallic'].default_value=.72 if name in ('Nickel','Bronze','Shaft') else .18
    principal.inputs['Roughness'].default_value=.19 if name in ('Glass','Skylight','Bronze') else .40
    if name=='Light':
        principal.inputs['Emission Color'].default_value=(*color,1);principal.inputs['Emission Strength'].default_value=2.8
    materials[name]=m
curves={}
def bead(points,material,radius):
    key=(material,radius)
    if key not in curves:
        g=bpy.data.curves.new(material+' detailing','CURVE');g.dimensions='3D';g.resolution_u=1
        g.bevel_resolution=2;g.bevel_depth=radius
        obj=bpy.data.objects.new(material+' detailing',g);bpy.context.collection.objects.link(obj)
        obj.data.materials.append(materials[material]);curves[key]=g
    spline=curves[key].splines.new('POLY');spline.points.add(len(points)-1)
    for v,p in zip(spline.points,points):v.co=(*p,1)
def ring(x,y,r,z,mat,radius):
    bead([(x+r*math.cos(a*math.tau/144),y+r*math.sin(a*math.tau/144),z) for a in range(145)],mat,radius)
for o in plan['solids']:
    if o['kind']!='mesh':continue
    name=o['id'];skin=o['skin'];c=Vector(o['center'])
    vertices=[Vector(v)+c for v in o['vertices']]
    hidden=set(o.get('internal_faces',[]))
    faces=[f for i,f in enumerate(o['faces']) if i not in hidden]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj['sceneryId']=name
    for m in materials.values():mesh.materials.append(m)
    for f in mesh.polygons:
        n=f.normal;z=f.center.z
        if skin=='wing':
            mat='Glass' if abs(n.z)<.24 else 'Skylight' if n.z>.94 else 'Nickel'
            if n.z<-.50:mat='Soffit'
        elif skin=='glass':mat='Glass' if abs(n.z)<.90 else 'Nickel'
        elif skin=='crown':mat='Nickel' if n.z>.25 else 'Bronze'
        else:mat={'lip':'Bronze','tower':'Shaft','canopy':'Soffit' if n.z<-.15 else 'Nickel',
                  'kerb':'Stone','garden':'Planting','bronze':'Bronze'}[skin]
        f.material_index=list(materials).index(mat)
        f.use_smooth=(n.z>.36 and n.z<.9995 and skin in ('wing','crown','canopy')) or (abs(n.z)<.94 and skin in ('glass','tower','lip'))
    if skin=='wing':
        half=len(vertices)//2
        idx=int(name.split('-')[-1])
        if idx%2==0:
            bead([tuple(p) for p in vertices[:half][2:]],'Bronze',.095)
        for k in (2,half-1):
            bead([vertices[k],vertices[half+k]],'Light',.092)
        if idx%2==0:
            for q in (0,1):
                a=vertices[0 if q else 1];b=vertices[half-1 if q else 2]
                bead([a.lerp(b,.025),b],'Bronze',.12)
    if skin=='canopy':
        n=len(vertices)//2
        for k in (1,5):bead([vertices[k],vertices[k+n]],'Light',.070)
# Tapered mullions stand proud of the recessed glazing and follow its rake.
for r0,r1,z0,z1,num in [(80.1,81,2.6,14.48,120),(83.48,72.72,16.6,29.33,120)]:
    for i in range(num):
        a=i*math.tau/num
        if operations and z0<4 and abs(math.cos(a))<math.sin(math.pi/16):continue
        bead([(r0*math.cos(a),-300+r0*math.sin(a),z0),(r1*math.cos(a),-300+r1*math.sin(a),z1)],
             'Bronze' if i%5==0 else 'Nickel',.16 if i%5==0 else .10)
for r,z in [(85.94,15.48),(78.27,30.77),(68.3,38.56),(40.01,46.05)]:
    ring(0,-300,r,z,'Light' if z<32 else 'Bronze',.085 if z<32 else .062)
for r,z in [(13.95,.42),(8.19,.9),(2.7,1.47)]:ring(0,-437,r,z,'Light',.073)
for i in range(16):
    a=math.tau*i/16;r=11.5 if i%4 else 13.20
    bead([(9.85*math.cos(a),-437+9.85*math.sin(a),.413),(r*math.cos(a),-437+r*math.sin(a),.413)],'Bronze',.085)
for r,z in [(10.85,90.43),(10.94,95.43),(11.67,96.81)]:ring(116,-235,r,z,'Light',.082)
for i in range(16):
    a=math.tau*i/16
    bead([(116+9.66*math.cos(a),-235+9.66*math.sin(a),90.50),(116+11.04*math.cos(a),-235+11.04*math.sin(a),95.3)],'Nickel',.13)
# All exportable surfaces are real meshes. Save editable curve splines in the .blend.
bpy.context.scene.unit_settings.system='METRIC'
bpy.ops.wm.save_as_mainfile(filepath=str(source))
for obj in list(bpy.context.scene.objects):
    if obj.type=='CURVE':
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True);bpy.ops.object.convert(target='MESH');obj.select_set(False)
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_yup=True,export_extras=True,
                          export_texcoords=False,export_animations=False,export_cameras=False,export_lights=False)
