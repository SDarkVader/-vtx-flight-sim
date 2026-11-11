import bpy
import math
import numpy as np
from mathutils import Vector, Matrix

# Open source master CAD
scene = bpy.context.scene

# 1. Clean exclusions:
# - 32 legacy flat box spar skins
# - 8 orphaned V2 lateral diagonals
# - Wake markers at origin
# - Unplaced redundant digital bus cables at origin
# - Any unplaced pieces with no vertices or zero origin
to_remove = []
for o in list(scene.objects):
    name = o.name
    # Box spars
    if name.startswith('P06 | F') and 'spar' in name and 'skin' in name:
        to_remove.append(o)
    # Orphaned V2 diagonals
    elif name.startswith('V2 P06 | Rotor F') and 'lateral diagonal' in name:
        to_remove.append(o)
    # Wake markers
    elif 'wake marker' in name.lower() or 'wake' in name.lower():
        to_remove.append(o)
    # Unrouted digital bus lines
    elif 'redundant digital bus' in name:
        to_remove.append(o)
    # Check if object is an unplaced origin piece (center at 0,0,0 and not airframe)
    elif o.matrix_world.translation.length < 0.001 and o.type == 'MESH':
        if any(k in name for k in ['actuator', 'torque shaft', 'output shaft stub']):
            to_remove.append(o)

print(f'Removing {len(to_remove)} unattached / legacy / origin clutter objects...')
for o in to_remove:
    bpy.data.objects.remove(o, do_unlink=True)

# 2. Materials Setup:
# A. Canopy Glass
glass = bpy.data.materials.get('Laminated glazing nominal')
if glass:
    nodes = glass.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.60, 0.82, 0.92, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.02
        bsdf.inputs['IOR'].default_value = 1.52
        if 'Transmission Weight' in bsdf.inputs:
            bsdf.inputs['Transmission Weight'].default_value = 0.96
        elif 'Transmission' in bsdf.inputs:
            bsdf.inputs['Transmission'].default_value = 0.96

# B. Duct Accent Rim Ring & Emissive Glow
duct_mat = bpy.data.materials.get('Duct inlet highlight')
if duct_mat:
    nodes = duct_mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.02, 0.15, 0.18, 1.0)
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (0.18, 0.89, 1.0, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 4.5
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = (0.18, 0.89, 1.0, 1.0)

# C. Nacelles - smooth aerodynamic composite
nacelle_mat = bpy.data.materials.get('CFRP woven reinforced')
if nacelle_mat:
    bsdf = next((n for n in nacelle_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.10, 0.13, 0.16, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.22
        bsdf.inputs['Metallic'].default_value = 0.15

# D. Spaceframe Trusses - dark titanium/composite
truss_mat = bpy.data.materials.get('CFRP structural composite')
if truss_mat:
    bsdf = next((n for n in truss_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.08, 0.10, 0.12, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.28
        bsdf.inputs['Metallic'].default_value = 0.20

# E. Aluminum / Alloy surfaces
alloy_mat = bpy.data.materials.get('Aerospace aluminum surfaces')
if alloy_mat:
    bsdf = next((n for n in alloy_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.75, 0.80, 0.85, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.25
        bsdf.inputs['Metallic'].default_value = 0.85

# 3. Add glowing ducted lip rings and taxi checkerboard livery band (Phase 2 feature)
livery_mat = bpy.data.materials.new(name='TaxiCheckerLivery')
livery_mat.use_nodes = True
l_bsdf = livery_mat.node_tree.nodes.get('Principled BSDF')
if l_bsdf:
    l_bsdf.inputs['Base Color'].default_value = (0.95, 0.72, 0.05, 1.0)
    l_bsdf.inputs['Roughness'].default_value = 0.4

lip_glow_mat = bpy.data.materials.new(name='DuctGlowRim')
lip_glow_mat.use_nodes = True
g_bsdf = lip_glow_mat.node_tree.nodes.get('Principled BSDF')
if g_bsdf:
    g_bsdf.inputs['Base Color'].default_value = (0.02, 0.18, 0.22, 1.0)
    if 'Emission Color' in g_bsdf.inputs:
        g_bsdf.inputs['Emission Color'].default_value = (0.18, 0.89, 1.0, 1.0)
        g_bsdf.inputs['Emission Strength'].default_value = 5.0

# Nacelle center locations
fan_centers = [
    Vector((2.600, 0.000, 2.315)),
    Vector((0.000, 2.600, 2.315)),
    Vector((-2.600, 0.000, 2.315)),
    Vector((0.000, -2.600, 2.315)),
]

for i, fc in enumerate(fan_centers, 1):
    # Glowing Lip Torus
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.215, minor_radius=0.016, major_segments=64, minor_segments=12,
        location=(fc.x, fc.y, fc.z + 0.27)
    )
    lip_obj = bpy.context.active_object
    lip_obj.name = f'Phase2_Duct_Lip_Glow_F{i}'
    lip_obj.data.materials.append(lip_glow_mat)

    # Livery Band Torus
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.205, minor_radius=0.028, major_segments=64, minor_segments=10,
        location=(fc.x, fc.y, fc.z + 0.15)
    )
    band_obj = bpy.context.active_object
    band_obj.name = f'Phase2_Duct_Livery_Band_F{i}'
    band_obj.data.materials.append(livery_mat)

# 4. Save canonical recovered .blend
out_blend = 'assets/derived/p0-v4-canonical.blend'
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f'SAVED CLEAN CANONICAL BLEND: {out_blend}')

# 5. Studio Lighting Setup
sun_data = bpy.data.lights.new('StudioKey', type='SUN')
sun_data.energy = 5.5
sun_data.color = (1.0, 0.98, 0.95)
sun_obj = bpy.data.objects.new('StudioKey', sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(52), math.radians(22), math.radians(-38))

fill_data = bpy.data.lights.new('StudioFill', type='SUN')
fill_data.energy = 2.2
fill_data.color = (0.75, 0.85, 1.0)
fill_obj = bpy.data.objects.new('StudioFill', fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(-30), math.radians(-15), math.radians(140))

rim_data = bpy.data.lights.new('StudioRim', type='SUN')
rim_data.energy = 3.5
rim_data.color = (0.8, 0.95, 1.0)
rim_obj = bpy.data.objects.new('StudioRim', rim_data)
scene.collection.objects.link(rim_obj)
rim_obj.rotation_euler = (math.radians(20), math.radians(60), math.radians(-120))

scene.render.image_settings.file_format = 'PNG'
scene.render.engine = 'BLENDER_EEVEE'

# Camera Helper
cam_data = bpy.data.cameras.new('StudioCam')
cam_data.lens = 45
cam_obj = bpy.data.objects.new('StudioCam', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Shot 1: 3/4 Perspective Hero View
cam_obj.location = Vector((4.6, -4.8, 2.9))
cam_obj.rotation_euler = (Vector((0, 0, 1.25)) - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.filepath = 'C:/Users/steve/.gemini/antigravity/brain/b329c633-e4ba-40e1-bf29-811ed0dfd8d8/render_1_perspective_hero.png'
bpy.ops.render.render(write_still=True)
print('RENDER 1 FINISHED')

# Shot 2: Cockpit Close-Up View
cam_obj.location = Vector((1.8, -2.4, 2.1))
cam_obj.rotation_euler = (Vector((0, 0, 1.55)) - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = 55
scene.render.filepath = 'C:/Users/steve/.gemini/antigravity/brain/b329c633-e4ba-40e1-bf29-811ed0dfd8d8/render_2_cockpit_detail.png'
bpy.ops.render.render(write_still=True)
print('RENDER 2 FINISHED')

# Shot 3: Front Elevation Ground View
cam_obj.location = Vector((0.0, -5.8, 1.6))
cam_obj.rotation_euler = (Vector((0, 0, 1.40)) - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = 42
scene.render.filepath = 'C:/Users/steve/.gemini/antigravity/brain/b329c633-e4ba-40e1-bf29-811ed0dfd8d8/render_3_front_elevation.png'
bpy.ops.render.render(write_still=True)
print('RENDER 3 FINISHED')

# 6. Export Canonical GLB
out_glb = 'public/assets/airframe-r6.glb'
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    export_animations=False,
    export_yup=False,
    export_extras=True,
    export_cameras=False,
    export_lights=False
)
print(f'EXPORTED CLEAN CANONICAL GLB: {out_glb}')
