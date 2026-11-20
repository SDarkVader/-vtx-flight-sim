"""Recover the owner's office furniture on a level floor and the canonical walking inspector."""
import json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector

root=Path(__file__).resolve().parents[2]
folder=Path(sys.argv[sys.argv.index('--')+1])
refs=folder/'office-source'
public=root/'public/vtx-env/vaderland'
art=[];clouds={};origins={}
def mesh_copy(o,transform,group,contact):
    deps=bpy.context.evaluated_depsgraph_get();ev=o.evaluated_get(deps)
    mesh=bpy.data.meshes.new_from_object(ev);mesh.transform(transform@ev.matrix_world)
    name=o.name;new=bpy.data.objects.new('Installed '+name,mesh);bpy.context.scene.collection.objects.link(new)
    new['movingPart']=group;art.append(new)
    pts=[v.co[:] for v in mesh.vertices]
    if pts and contact:clouds.setdefault(contact,[]).extend(pts)
def simple(name,size,mat,transform,group):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o=bpy.context.object;o.name=name;o.matrix_world=transform@Matrix.Diagonal(Vector([*size,1]))
    o.data.materials.append(mat);mesh_copy(o,Matrix.Identity(4),group,'hand-board')
    bpy.data.objects.remove(o,do_unlink=True)
def mat(name,col,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*col,1);b.inputs['Metallic'].default_value=metal
    return m
def finish(file):
    bpy.ops.object.select_all(action='DESELECT')
    for o in art:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(public/file),export_format='GLB',use_selection=True,
        export_extras=True,export_animations=False,export_yup=True,export_lights=False,export_cameras=False)
def small_cloud(p):
    arr=np.asarray(p);directions=[]
    for t in np.linspace(-math.pi/2,math.pi/2,11):
        for a in np.arange(23)*math.tau/23:
            directions.append([math.cos(t)*math.cos(a),math.cos(t)*math.sin(a),math.sin(t)])
    idx=np.argmax(arr@np.asarray(directions).T,axis=0)
    return np.unique(arr[idx].round(5),axis=0).tolist()
# Use the actual source armature. Pose its hand to carry the clipboard.
bpy.ops.wm.open_mainfile(filepath=str(refs/'Arthur_Finch_Canonical_v1.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
arm=rig.pose.bones['upper_arm.L'];fore=rig.pose.bones['forearm.L']
for bone,angle in [(arm,-.68),(fore,-.33)]:
    p=bone.matrix.translation.copy()
    bone.matrix=Matrix.Translation(p)@Matrix.Rotation(angle,4,'X')@Matrix.Translation(-p)@bone.matrix
    bpy.context.view_layer.update()
roll=Matrix.Rotation(math.pi,4,'Z')
for b in ('thigh.L','thigh.R','upper_arm.R'):
    origins[b]=list(roll@(rig.matrix_world@rig.pose.bones[b].head))
for o in list(bpy.context.scene.objects):
    if o.type!='MESH':continue
    b=o.parent_bone
    group='thigh.'+b[-1] if b.startswith(('thigh','shin','foot')) else 'upper_arm.R' if b.endswith('.R') and ('arm' in b or 'hand' in b) else 'body'
    contact=group if group!='body' else 'head' if b in ('head','neck') else 'arm-l' if b.endswith('.L') else 'torso'
    mesh_copy(o,roll,group,contact)
hand=roll@(rig.matrix_world@rig.pose.bones['hand.L'].tail)
loc=Matrix.Translation(hand+Vector((.072,.013,.115)))@Matrix.Rotation(-.43,4,'X')
simple('Finch inspection clipboard',(.224,.018,.31),mat('Oiled board',(.14,.061,.024)),loc,'body')
simple('Inspection sheet',(.202,.004,.281),mat('Cream paper',(.81,.75,.56)),loc@Matrix.Translation((0,.012,.003)),'body')
simple('Spring clip',(.079,.016,.028),mat('Polished brass',(.66,.43,.18),.78),loc@Matrix.Translation((0,.019,.139)),'body')
for j in range(7):simple('Form rule '+str(j),(.118 if j%2 else .154,.0025,.0028),mat('Ink '+str(j),(.10,.15,.138)),
                          loc@Matrix.Translation((-.004,.015,.093-j*.023)),'body')
# Rest boot sole sits on the survey ground.
sole=min(v.co.z for o in art for v in o.data.vertices)
for o in art:o.data.transform(Matrix.Translation((0,0,-sole)))
for p in origins.values():p[2]-=sole
staff={k:small_cloud([[x,y,z-sole] for x,y,z in pts]) for k,pts in clouds.items()}
finish('finch-on-inspection.glb')
art.clear();clouds.clear()
bpy.ops.wm.open_mainfile(filepath=str(refs/'Vaderland_RotatingOffice_Full3D_v1.blend'))
def deck(x,deg):
    t=math.radians(deg);s=math.sin(t);c=math.cos(t)
    return Matrix(((1,0,0,x),(0,-c,s,-15*s),(0,s,c,-15*c),(0,0,0,1)))
names=['Raymond_ExecutiveDesk','Raymond_ExecutiveThrone','Raymond_DeskProps','Arthur_InvestigationDesk',
       'Arthur_Corkboard','Arthur_FilingCabinets','Arthur_TaskLamp']
# Use the source room's own local tangent coordinates; discard the cylinder and global animation.
for name in names:
    o=bpy.data.objects[name]
    ray=name.startswith('Raymond');offset=(423,-338.7,.023) if ray else (431,-338.6,.023)
    matrix=Matrix.Translation(offset)@deck(0,324).inverted() if ray else Matrix.Translation(offset)@deck(17,105).inverted()
    mesh_copy(o,matrix,'',name)
furniture={k:small_cloud(v) for k,v in clouds.items()}
finish('finch-office-furniture.glb')
(folder/'department-surfaces.json').write_text(json.dumps(dict(origins=origins,staff=staff,furniture=furniture)))
print('Floor',sole,'character groups',list(staff),'office inventory',list(furniture))
