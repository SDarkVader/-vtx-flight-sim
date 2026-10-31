"""Concept illustration: four independent planetary power-split branches.

Not a production gear model or a verified installation. Dimensions in metres;
the fan-pivot positions reproduce the flight-model layout. The gear teeth,
bearing sizes, wiring, mount loads, clearances and housing dimensions are not
engineering specifications. Existing VTX geometry is not modified.
"""
import bpy, math
from mathutils import Vector

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def material(name, color, metallic=0.0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.metallic=metallic;m.roughness=.34
    return m

case=material('Illustrative casing',(.045,.22,.25),.65)
shaft=material('Input and output shafts',(.43,.48,.49),.8)
ring=material('Variator ring',(.11,.68,.61),.55)
sun=material('Sun input',(.96,.62,.12),.65)
planet=material('Planet gears',(.6,.66,.68),.75)
drive=material('Motor generator',(.19,.28,.36),.65)
bus=material('Shared power and control',(.93,.35,.11),.35)

def cyl(name,loc,r,depth,mat,axis='Z'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc)
    o=bpy.context.object;o.name=name
    if axis=='X':o.rotation_euler[1]=math.pi/2
    o.data.materials.append(mat);return o

def bar(name,a,b,r,mat):
    a,b=Vector(a),Vector(b);d=b-a
    o=cyl(name,(a+b)/2,r,d.length,mat)
    o.rotation_euler=d.to_track_quat('Z','Y').to_euler();return o

def torus(name,loc,major,minor,mat):
    bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=12,location=loc,major_radius=major,minor_radius=minor)
    o=bpy.context.object;o.name=name;o.data.materials.append(mat);return o

# Packaging markers are at the model's fan pivots, but Z dimensions are a
# provisional exploded concept; do not infer a validated installed fit.
pivots=[(2.6,0), (0,2.6),(-2.6,0),(0,-2.6)]
for i,(x,y) in enumerate(pivots,1):
    z=.8
    cyl(f'F{i} fixed reducer concept',(x,y,z-.34),.15,.24,case)
    bar(f'F{i} high speed branch',(.35*x/2.6,.35*y/2.6,z-.34),(x,y,z-.34),.027,shaft)
    cyl(f'F{i} reducer to sun connection',(x,y,z-.12),.035,.23,shaft)
    torus(f'F{i} electronically driven ring conceptual envelope',(x,y,z+.04),.20,.027,ring)
    cyl(f'F{i} central sun schematic',(x,y,z+.04),.045,.12,sun)
    for j in range(3):
        a=j*2*math.pi/3
        cyl(f'F{i} planet schematic {j+1}',(x+.11*math.cos(a),y+.11*math.sin(a),z+.04),.046,.10,planet)
    cyl(f'F{i} carrier and rotor output',(x,y,z+.18),.075,.16,shaft)
    bar(f'F{i} fan shaft interface',(x,y,z+.25),(x,y,1.72),.034,shaft)
    u=Vector((x,y,0)).normalized();m=(x+u.x*.32,y+u.y*.32,z+.04)
    bar(f'F{i} motor generator concept',(m[0]-u.x*.115,m[1]-u.y*.115,m[2]),(m[0]+u.x*.115,m[1]+u.y*.115,m[2]),.09,drive)
    torus(f'F{i} motor coupler indicator',(x+u.x*.23,y+u.y*.23,z+.04),.055,.01,bus)
    bar(f'F{i} power control line',(.28*u.x,.28*u.y,.46),(x+u.x*.32,y+u.y*.32,.46),.012,bus)

cyl('Common engine input reference',(0,0,.46),.18,.32,case)
torus('Shared electrical bus reference',(0,0,.46),.28,.018,bus)
