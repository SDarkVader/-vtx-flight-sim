import bpy
import math
from mathutils import Vector, Euler, Matrix

blend_path = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Vaderland_RotatingOffice_Full3D_v1.blend"
out_blend = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Raymond_Winston_Canonical_v1.blend"
out_glb = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Raymond_Winston_Canonical_v1.glb"
out_proof = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\proof_raymond_standalone_fullbody.png"

bpy.ops.wm.open_mainfile(filepath=blend_path)
scene = bpy.context.scene

print("=== ISOLATING RAYMOND WINSTON (CANONICAL INDIVIDUAL ASSET) ===")

ray_comp = bpy.data.objects.get('Component_raymond')
ray_rig = bpy.data.objects.get('RAYMOND_Winston_BipedRig')

if not ray_rig or not ray_comp:
    raise Exception("Raymond rig or component not found!")

# 1. Unparent Component_raymond and center cleanly at origin
ray_comp.parent = None
ray_comp.location = Vector((0.0, 0.0, 0.0))
ray_comp.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
bpy.context.view_layer.update()

# 2. Collect all objects belonging to Raymond
def get_descendants(o):
    desc = [o]
    for c in o.children:
        desc.extend(get_descendants(c))
    return desc

all_ray_objs = set(get_descendants(ray_comp))

# Remove scratch/hidden construction objects
scratch_names = {'Tie_Loose_Knot', 'Taxi_Emblem_Bonnet', 'Taxi_Emblem_Cabin', 'Taxi_Hat_Wheel_-0.02', 'Taxi_Hat_Wheel_0.02', 'Tie_Tartan_Cross_00'}
ray_keep = {o for o in all_ray_objs if o.name not in scratch_names}

print(f"Retaining {len(ray_keep)} objects for Raymond Winston.")

# 3. Delete all other objects in scene
for o in list(bpy.data.objects):
    if o not in ray_keep:
        bpy.data.objects.remove(o, do_unlink=True)

# Delete unneeded collections
for col in list(bpy.data.collections):
    if col.name != "Collection":
        bpy.data.collections.remove(col)

# Ensure ray_comp is linked to main collection
if ray_comp.name not in scene.collection.objects:
    scene.collection.objects.link(ray_comp)

# 4. Target Empty at Raymond's chest
target_empty = bpy.data.objects.new("Target_Raymond_Chest", None)
target_empty.location = Vector((0.0, 0.0, 0.65))
scene.collection.objects.link(target_empty)

# 5. Studio Lighting for Clean Showcase
def add_tracked_light(name, ltype, pos, energy, color, size=1.0):
    ldata = bpy.data.lights.new(name, ltype)
    ldata.energy = energy
    ldata.color = color
    if hasattr(ldata, 'size'):
        ldata.size = size
    lobj = bpy.data.objects.new(name, ldata)
    lobj.location = pos
    scene.collection.objects.link(lobj)
    con = lobj.constraints.new(type='TRACK_TO')
    con.target = target_empty
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    return lobj

add_tracked_light("Studio_Key", 'AREA', Vector((1.4, -2.4, 1.6)), 280.0, (1.0, 0.98, 0.94), size=1.2)
add_tracked_light("Studio_Fill", 'AREA', Vector((-1.6, -1.8, 1.2)), 160.0, (0.88, 0.94, 1.0), size=1.5)
add_tracked_light("Studio_Rim", 'AREA', Vector((0.0, 2.0, 1.6)), 220.0, (1.0, 0.88, 0.65), size=1.0)
add_tracked_light("Studio_Top", 'POINT', Vector((0.0, -0.2, 2.2)), 100.0, (1.0, 0.96, 0.90))

# 6. Framing Camera (Centered Full Body)
cdata = bpy.data.cameras.new("Cam_Raymond_Showcase")
cdata.lens = 50.0
cam = bpy.data.objects.new("Cam_Raymond_Showcase", cdata)
cam.location = Vector((0.0, -2.8, 0.65))
scene.collection.objects.link(cam)
scene.camera = cam

con_cam = cam.constraints.new(type='TRACK_TO')
con_cam.target = target_empty
con_cam.track_axis = 'TRACK_NEGATIVE_Z'
con_cam.up_axis = 'UP_Y'

# 7. Render Showcase Image
scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderSettings') and 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.resolution_x = 1080
scene.render.resolution_y = 1440
scene.render.resolution_percentage = 100
scene.render.filepath = out_proof
bpy.ops.render.render(write_still=True)
print(f"Rendered: {out_proof}")

# 8. Save Standalone Blend File
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"Saved: {out_blend}")

# 9. Export Standalone GLB File
for o in bpy.data.objects:
    o.select_set(o in ray_keep)

bpy.context.view_layer.objects.active = ray_rig
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_materials='EXPORT',
    export_skins=True,
    export_morph=True,
    export_yup=True,
    export_cameras=False,
    export_lights=False
)
print(f"Exported: {out_glb}")
print("=== RAYMOND WINSTON STANDALONE ASSETS GENERATED ===")
