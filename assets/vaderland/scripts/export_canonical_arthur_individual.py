import bpy
import math
from mathutils import Vector, Euler, Matrix

blend_path = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Vaderland_RotatingOffice_Full3D_v1.blend"
out_blend = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Arthur_Finch_Canonical_v1.blend"
out_glb = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Arthur_Finch_Canonical_v1.glb"
out_proof = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\proof_arthur_standalone_fullbody.png"

bpy.ops.wm.open_mainfile(filepath=blend_path)
scene = bpy.context.scene

print("=== ISOLATING ARTHUR FINCH (CANONICAL INDIVIDUAL ASSET) ===")

art_root = bpy.data.objects.get('ARTHUR_FINCH_INERTIAL_MOTION_ROOT')
art_rig = bpy.data.objects.get('ARTHUR_FINCH_Compliance_Biped_Rig')

if not art_rig or not art_root:
    raise Exception("Arthur rig or root not found!")

# 1. Unparent and clear cylinder inertial root animation, center cleanly at origin
art_root.parent = None
if art_root.animation_data:
    art_root.animation_data_clear()
art_root.location = Vector((0.0, 0.0, 0.0))
art_root.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
bpy.context.view_layer.update()

# 2. Collect all objects belonging to Arthur
def get_descendants(o):
    desc = [o]
    for c in o.children:
        desc.extend(get_descendants(c))
    return desc

all_art_objs = set(get_descendants(art_root))

# Filter out old unused eye/stylus construction pieces
scratch_names = {
    'Arthur_HeadMounted_ComplianceStylus', 'Arthur_HeadMounted_StylusNib',
    'Arthur_L_AmberIris_Emissive', 'Arthur_L_LowerLid', 'Arthur_L_Pupil_Graphite',
    'Arthur_L_SkepticalAmberBrow', 'Arthur_L_TopLid',
    'Arthur_R_AmberIris_Emissive', 'Arthur_R_LowerLid', 'Arthur_R_Pupil_Graphite',
    'Arthur_R_SkepticalAmberBrow', 'Arthur_R_TopLid'
}
art_keep = {o for o in all_art_objs if o.name not in scratch_names}

print(f"Retaining {len(art_keep)} objects for Arthur Finch.")

# 3. Delete all other objects in scene
for o in list(bpy.data.objects):
    if o not in art_keep:
        bpy.data.objects.remove(o, do_unlink=True)

# Delete unneeded collections
for col in list(bpy.data.collections):
    if col.name != "Collection":
        bpy.data.collections.remove(col)

# Ensure art_root is linked to main collection
if art_root.name not in scene.collection.objects:
    scene.collection.objects.link(art_root)

# 4. Target Empty at Arthur's chest
target_empty = bpy.data.objects.new("Target_Arthur_Chest", None)
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
cdata = bpy.data.cameras.new("Cam_Arthur_Showcase")
cdata.lens = 50.0
cam = bpy.data.objects.new("Cam_Arthur_Showcase", cdata)
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
    o.select_set(o in art_keep)

bpy.context.view_layer.objects.active = art_rig
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
print("=== ARTHUR FINCH STANDALONE ASSETS GENERATED ===")
