"""
APPLY ROTATION AND VIEWPORT MASTER
1. Binds all habitat structures, departments, characters, and department lights to a master rotating root.
2. Animates smooth, seamless 360-degree rotation across 360 frames (linear cyclic loop).
3. Animates circular turntable launch pad and autonomous flying drones.
4. Configures all Blender viewport screens (Layout, Animation, Shading, etc.) to RENDERED mode with scene lights and scene world enabled.
5. Sets Solid mode color_type to TEXTURE as a fallback.
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, Matrix

BLEND_PATH = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Vaderland_RotatingOffice_Full3D_v1.blend"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
scene = bpy.context.scene

# -----------------------------------------------------------------------------
# 1. SETUP TIMELINE FOR ROTATION
# -----------------------------------------------------------------------------
scene.frame_start = 1
scene.frame_end = 360
scene.frame_current = 1
scene.render.fps = 30

# -----------------------------------------------------------------------------
# 2. CREATE MASTER ROTATING HABITAT ROOT
# -----------------------------------------------------------------------------
print(">>> CREATING MASTER ROTATING HABITAT ROOT...")
root_name = "Vaderland_Rotating_Habitat_Root"
old_root = bpy.data.objects.get(root_name)
if old_root:
    bpy.data.objects.remove(old_root, do_unlink=True)

root = bpy.data.objects.new(root_name, None)
root.empty_display_type = 'CIRCLE'
root.empty_display_size = 15.2
scene.collection.objects.link(root)

# Objects that MUST REMAIN INERTIAL (Stationary in space or navigating the central core):
inertial_objects = {
    "CAM_Master_Cutaway_Diorama",
    "CAM_Master_Drone_Flight",
    "Light_Axis_West",
    "Light_Axis_Center",
    "Light_Axis_East",
    "Drone_Alpha_Chassis",
    "Drone_Alpha_Lights",
    "Drone_Beta_Chassis",
    "Drone_Beta_Lights",
    "Drone_Gamma_Chassis",
    "Drone_Gamma_Lights"
}

# Parent all other habitat objects, departments, characters, and lights to root
print(">>> PARENTING DEPARTMENTS, CHARACTERS, AND STRUCTURES TO ROTATING ROOT...")
collections_to_parent = [
    "01_CYLINDRICAL_STRUCTURE",
    "02_3D_DEPARTMENTS",
    "04_LIGHTING",
    "05_CAMERAS"
]

for col_name in collections_to_parent:
    col = bpy.data.collections.get(col_name)
    if not col:
        continue
    for obj in col.objects:
        if obj.name in inertial_objects:
            continue
        # Preserve world transform
        mw = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_parent_inverse = root.matrix_world.inverted()
        obj.matrix_world = mw

# Parent character root empties (Raymond & Arthur)
char_roots = ["Component_raymond", "ARTHUR_FINCH_INERTIAL_MOTION_ROOT"]
for cr_name in char_roots:
    cr_obj = bpy.data.objects.get(cr_name)
    if cr_obj:
        mw = cr_obj.matrix_world.copy()
        cr_obj.parent = root
        cr_obj.matrix_parent_inverse = root.matrix_world.inverted()
        cr_obj.matrix_world = mw
        print(f"Parented character root {cr_name} to rotating habitat root.")

# -----------------------------------------------------------------------------
# 3. ANIMATE ROTATION AROUND X AXIS
# -----------------------------------------------------------------------------
print(">>> ANIMATING ROTATION AROUND CYLINDER X AXIS...")
root.rotation_mode = 'XYZ'
root.rotation_euler = (0.0, 0.0, 0.0)
root.keyframe_insert(data_path='rotation_euler', frame=1)

root.rotation_euler = (2.0 * math.pi, 0.0, 0.0)
root.keyframe_insert(data_path='rotation_euler', frame=361)

# Set Linear Interpolation on F-Curves
action = root.animation_data.action if root.animation_data else None
if action:
    # Blender 5.2 layered action structure
    if hasattr(action, 'layers') and len(action.layers) > 0:
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'LINEAR'
    # Legacy fallback
    elif hasattr(action, 'fcurves'):
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
print(">>> Rotation animation keyed successfully (360 frames, 30 fps, seamless linear loop)!")

# -----------------------------------------------------------------------------
# 4. ANIMATE TURNTABLE ROTATION & DRONE HOVERING
# -----------------------------------------------------------------------------
# Animate Turntable Hub
turntable = bpy.data.objects.get("Turntable_Platform")
if turntable:
    turntable.rotation_mode = 'XYZ'
    turntable.rotation_euler = (0, 0, 0)
    turntable.keyframe_insert(data_path='rotation_euler', frame=1)
    turntable.rotation_euler = (0, 0, math.pi)
    turntable.keyframe_insert(data_path='rotation_euler', frame=361)

# Animate Drone Alpha hovering bob
drone_a = bpy.data.objects.get("Drone_Alpha_Chassis")
if drone_a:
    pos_orig = drone_a.location.copy()
    for fr, z_off in [(1, 0.0), (90, 0.25), (180, 0.0), (270, -0.25), (360, 0.0)]:
        drone_a.location = pos_orig + Vector((0.0, 0.0, z_off))
        drone_a.keyframe_insert(data_path='location', frame=fr)

# -----------------------------------------------------------------------------
# 5. CONFIGURE BLENDER VIEWPORT SHADING IN ALL SCREENS
# -----------------------------------------------------------------------------
print(">>> CONFIGURING VIEWPORT SHADING (RENDERED MODE + LIGHTS + TEXTURES)...")
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Default viewport to RENDERED mode with scene lights & scene world!
                    space.shading.type = 'RENDERED'
                    space.shading.use_scene_lights = True
                    space.shading.use_scene_world = True
                    # Set solid mode fallback to show textures
                    space.shading.color_type = 'TEXTURE'
                    # Set camera perspective
                    space.region_3d.view_perspective = 'CAMERA'
                    print(f"Screen '{screen.name}' 3D View set to RENDERED mode with Scene Lights!")

# Set default scene camera
cam_diorama = bpy.data.objects.get("CAM_Master_Cutaway_Diorama")
if cam_diorama:
    scene.camera = cam_diorama

# Save file
print(f">>> SAVING MASTER BLEND FILE: {BLEND_PATH}...")
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(">>> ROTATION AND VIEWPORT CONFIGURATION SUCCESSFULLY SAVED!")
