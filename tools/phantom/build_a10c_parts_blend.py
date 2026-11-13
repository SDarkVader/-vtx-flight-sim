"""Build A10-C visual additions as an independent Blender master and GLB.

Target branch: work/a10c-cockpit-controls-20261112
Run from repository root: blender -b --python tools/phantom/build_a10c_parts_blend.py
Generates assets/derived/phantom-a10c-parts.blend and .glb. Does not edit A10-B.
Engine envelope PBS TJ150: 636 mm long, 272 mm outside diameter.
Actuator x=1.54m, y=+/-0.78m is a provisional inboard visual placement to
avoid the tyre: physics mass ledger assumes +/-1.00m.
Visual only; no pod downlock or tyre physics changes made.
"""

import bpy, math
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, rgb, metal=0.0, rough=.5):
    m=bpy.data.materials.new(name); m.diffuse_color=(*rgb,1)
    m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value=(*rgb,1)
        p.inputs["Metallic"].default_value=metal
        p.inputs["Roughness"].default_value=rough
    return m
steel=material('A10C_BrushedTitanium',(.48,.56,.61),.6,.32)
carbon=material('A10C_CarbonComposite',(.025,.036,.049),.08,.6)
ceramic=material('A10C_CeramicExhaust',(.23,.23,.26),.12,.55)
amber=material('A10C_AmberAccent',(.9,.36,.065),.25,.35)
black=material('A10C_IntakeShadow',(.01,.014,.022),.13,.8)

def empty(n, loc, parent=None):
    o=bpy.data.objects.new(n,None); bpy.context.collection.objects.link(o)
    o.empty_display_type='PLAIN_AXES';o.empty_display_size=.08
    if parent: o.parent=parent
    o.location=loc; o['blendstra_id']=n
    return o
root=empty('A10C_PARTS_ROOT',(0,0,0))
root['variant']='phantom-a10c'
root['visual_only']=True
root['coordinates']='x forward, y lateral, z up; metre'
def cylinder(n,r,depth,loc,mat,parent=None,axis='Z',vertices=28):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=(0,0,0))
    o=bpy.context.object;o.name=n
    if parent:o.parent=parent
    o.location=loc
    if axis=='X':o.rotation_euler[1]=math.pi/2
    o.data.materials.append(mat);o['blendstra_id']=n
    for poly in o.data.polygons: poly.use_smooth=True
    return o
def taper(n,ra,rb,depth,loc,mat,parent=None):
    bpy.ops.mesh.primitive_cone_add(vertices=28,radius1=ra,radius2=rb,depth=depth,location=(0,0,0))
    o=bpy.context.object; o.name=n
    if parent:o.parent=parent
    o.location=loc;o.rotation_euler[1]=math.pi/2
    o.data.materials.append(mat);o['blendstra_id']=n
    for poly in o.data.polygons: poly.use_smooth=True
    return o

for side,y in [('L',-.4),('R',.4)]:
    for level,z in [('LOWER',.355),('UPPER',.665)]:
        sn=f'{side}_{level}';p=empty('A10C_TJ150_'+sn+'_MOUNT',(-1.972,y,z),root)
        p['component']='PBS TJ150 envelope only, not vendor CAD'
        p['envelope_length_m']=.636;p['envelope_diameter_m']=.272
        p['rated_thrust_n']=1500
        cylinder('A10C_TJ150_'+sn+'_CASE',.129,.428,(.015,0,0),steel,p,'X')
        taper('A10C_TJ150_'+sn+'_FRONT_CONE',.116,.136,.126,(.25,0,0),steel,p)
        cylinder('A10C_TJ150_'+sn+'_INLET',.087,.018,(.305,0,0),black,p,'X')
        cylinder('A10C_TJ150_'+sn+'_CASE_RING',.135,.028,(-.045,0,0),carbon,p,'X')
        taper('A10C_TJ150_'+sn+'_TAIL',.080,.117,.167,(-.233,0,0),ceramic,p)
        cylinder('A10C_TJ150_'+sn+'_EXHAUST',.070,.010,(-.311,0,0),black,p,'X')
        cylinder('A10C_TJ150_'+sn+'_HEAT_RING',.112,.016,(-.290,0,0),amber,p,'X')
        for ii,dy in enumerate([-.074,.074]):
            cylinder('A10C_TJ150_'+sn+'_LUG_'+str(ii),.018,.09,(.08,dy,.064),steel,p)
for sn,y in [('FL',-.78),('FR',.78)]:
    p=empty('A10C_NOSE_LIFT_'+sn+'_MOUNT',(1.54,y,.75),root)
    p['nominal_actuator_package_m']=[.12,.12,.50]
    p['nominal_dynamic_force_n']=10000
    p['visual_lateral_location_provisional']=True
    cylinder('A10C_NOSE_LIFT_'+sn+'_BARREL',.055,.33,(0,0,.025),steel,p)
    cylinder('A10C_NOSE_LIFT_'+sn+'_HEAD',.063,.045,(0,0,.213),carbon,p)
    cylinder('A10C_NOSE_LIFT_'+sn+'_PORT',.061,.028,(0,0,-.15),amber,p)
    cylinder('A10C_NOSE_LIFT_'+sn+'_TOP_PIN',.022,.12,(0,0,.258),steel,p,'X')
    j=empty('A10C_JOINT_NOSE_LIFT_'+sn,(0,0,0),p)
    j['joint_type']='slide';j['axis_parent']=[0.0,0.0,-1.0]
    j['stroke_m']=.20
    j['phantom_joint']='nose_lift_'+sn
    cylinder('A10C_NOSE_LIFT_'+sn+'_MOVING_ROD',.027,.23,(0,0,-.275),steel,j)
    cylinder('A10C_NOSE_LIFT_'+sn+'_LOWER_EYE',.051,.035,(0,0,-.40),carbon,j)
    cylinder('A10C_NOSE_LIFT_'+sn+'_LOWER_PIN',.018,.095,(0,0,-.425),steel,j,'X')

# Store outside the canonical source model/physics directories.
from pathlib import Path
_repo=Path(__file__).resolve().parents[2]
_derived=_repo/"assets"/"derived"
_derived.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(_derived/"phantom-a10c-parts.blend"))
bpy.ops.export_scene.gltf(filepath=str(_derived/"phantom-a10c-parts.glb"),
                          export_format='GLB', export_yup=False,
                          export_extras=True, use_selection=False)
print("Saved:", _derived/"phantom-a10c-parts.blend")
print("Saved:", _derived/"phantom-a10c-parts.glb")
