"""Animated schematic, ideal kinematics, NOT manufacturing or physical simulation."""
import bpy, math
from mathutils import Vector

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.frame_start=1
scene.frame_end=121
scene.render.fps=24

def mat(name, color, metal=0.2):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.metallic=metal; m.roughness=.35
    return m
sun_mat=mat('Gold - sun input',(.96,.58,.08),.65)
planet_mat=mat('Silver - four planet gears',(.62,.72,.78),.65)
ring_mat=mat('Teal - control ring',(.03,.48,.51),.55)
carrier_mat=mat('Blue - carrier fan output',(.08,.26,.8),.4)
red_mat=mat('Coral - rotation marker',(.95,.18,.08),.1)

def gear(name, teeth, pitch, thickness, material, internal=False):
    n=teeth*4; verts=[]; faces=[]
    # Stylized teeth with correct count, not an involute tooth design.
    for z in (-thickness/2, thickness/2):
        for j in range(n):
            a=2*math.pi*j/n
            if internal:
                ri=pitch + (-.012 if j%4 in (1,2) else .012); ro=pitch+.08
            else:
                ri=.055; ro=pitch + (.012 if j%4 in (1,2) else -.012)
            verts.extend([(ri*math.cos(a),ri*math.sin(a),z),(ro*math.cos(a),ro*math.sin(a),z)])
    for j in range(n):
        k=(j+1)%n; a=2*j; b=2*k; u=2*n+a; v=2*n+b
        faces.extend([(a,b,b+1,a+1),(u,u+1,v+1,v),(a,u,v,b),(a+1,b+1,v+1,u+1)])
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); scene.collection.objects.link(obj); obj.data.materials.append(material)
    return obj

sun=gear('Sun input - 20 stylized teeth',20,.2,.06,sun_mat)
ring=gear('Ring control - 60 stylized internal teeth',60,.6,.06,ring_mat,True)
carrier=bpy.data.objects.new('Carrier output - fan shaft',None); scene.collection.objects.link(carrier)

def bar(name, start, end, radius, material, parent=None):
    delta=Vector(end)-Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=delta.length,location=(Vector(start)+Vector(end))/2)
    o=bpy.context.object; o.name=name; o.rotation_euler=delta.to_track_quat('Z','Y').to_euler(); o.data.materials.append(material)
    if parent: o.parent=parent
    return o

for j in range(4):
    a=2*math.pi*j/4
    bar('Carrier arm %d'%(j+1),(0,0,.12),(.4*math.cos(a),.4*math.sin(a),.12),.023,carrier_mat,carrier)
bar('Fan shaft output',(0,0,.11),(0,0,.35),.045,carrier_mat,carrier)
bar('Sun direction marker',(0,0,.045),(.15,0,.045),.012,red_mat,sun)
bar('Ring direction marker',(.61,0,.06),(.66,0,.06),.012,red_mat,ring)

planets=[]
for j in range(4):
    p=gear('Planet %d - 20 stylized teeth'%(j+1),20,.2,.06,planet_mat)
    bar('Planet %d marker'%(j+1),(0,0,.04),(.14,0,.04),.009,red_mat,p)
    planets.append(p)

# At the nominal case, ring=0, carrier=1 turn, sun=4 turns,
# planet absolute spin=2*carrier - sun = -2 turns (equal sun/planet teeth).
# Baked samples make the schematic playable without browser scripts.
for frame in range(1,122,3):
    phase=2*math.pi*(frame-1)/120
    sun.rotation_euler.z=4*phase; sun.keyframe_insert(data_path='rotation_euler',frame=frame)
    carrier.rotation_euler.z=phase; carrier.keyframe_insert(data_path='rotation_euler',frame=frame)
    for j,p in enumerate(planets):
        a=phase+j*math.pi/2
        p.location=(.4*math.cos(a),.4*math.sin(a),0); p.rotation_euler.z=-2*phase
        p.keyframe_insert(data_path='location',frame=frame); p.keyframe_insert(data_path='rotation_euler',frame=frame)
for obj in [sun,carrier,*planets]:
    if obj.animation_data and obj.animation_data.action:
        for curve in obj.animation_data.action.fcurves:
            for key in curve.keyframe_points: key.interpolation='LINEAR'
scene.frame_set(1)
