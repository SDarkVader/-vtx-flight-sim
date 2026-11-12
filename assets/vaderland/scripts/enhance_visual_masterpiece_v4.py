"""
ENHANCE VISUAL MASTERPIECE v4
Refines shaders, procedural monitor displays, procedural book spines,
tactical HUDs, turbine blades, and camera compositions for maximum visual impact.
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
# 1. PROCEDURAL SHADERS FOR OPERATIONS SCREENS, BOOKS, AND MEDICAL ECG
# -----------------------------------------------------------------------------
print(">>> CREATING PROCEDURAL SCI-FI DISPLAY SHADERS...")

# 1A. Procedural Tactical Screen Shader (World Radar & Flight Telemetry)
mat_tactical_screen = bpy.data.materials.new("Mat_Procedural_TacticalScreen")
mat_tactical_screen.use_nodes = True
snodes = mat_tactical_screen.node_tree.nodes
slinks = mat_tactical_screen.node_tree.links
snodes.clear()

s_out = snodes.new('ShaderNodeOutputMaterial')
s_bsdf = snodes.new('ShaderNodeBsdfPrincipled')
s_bsdf.inputs['Base Color'].default_value = (0.02, 0.06, 0.14, 1.0)
s_bsdf.inputs['Roughness'].default_value = 0.15

# Procedural Grid Waves for Flight Radar
s_tex_coord = snodes.new('ShaderNodeTexCoord')
s_wave1 = snodes.new('ShaderNodeTexWave')
s_wave1.wave_type = 'RINGS'
s_wave1.inputs['Scale'].default_value = 8.0
s_wave1.inputs['Distortion'].default_value = 1.2
s_wave1.inputs['Detail'].default_value = 2.0

s_wave2 = snodes.new('ShaderNodeTexWave')
s_wave2.wave_type = 'BANDS'
s_wave2.inputs['Scale'].default_value = 24.0

s_mix = snodes.new('ShaderNodeMix')
s_mix.data_type = 'RGBA'
s_mix.inputs['Factor'].default_value = 0.5

s_ramp = snodes.new('ShaderNodeValToRGB')
s_ramp.color_ramp.elements[0].position = 0.3
s_ramp.color_ramp.elements[0].color = (0.02, 0.08, 0.22, 1.0)
s_ramp.color_ramp.elements[1].position = 0.8
s_ramp.color_ramp.elements[1].color = (0.0, 0.85, 1.0, 1.0)

slinks.new(s_tex_coord.outputs['Generated'], s_wave1.inputs['Vector'])
slinks.new(s_tex_coord.outputs['Generated'], s_wave2.inputs['Vector'])
slinks.new(s_wave1.outputs['Color'], s_mix.inputs['A'])
slinks.new(s_wave2.outputs['Color'], s_mix.inputs['B'])
slinks.new(s_mix.outputs['Result'], s_ramp.inputs['Fac'])
slinks.new(s_ramp.outputs['Color'], s_bsdf.inputs['Emission Color'])
s_bsdf.inputs['Emission Strength'].default_value = 2.8
slinks.new(s_bsdf.outputs['BSDF'], s_out.inputs['Surface'])

# Assign to Operations Main Wall and Screens
for obj_name in ["Operations_MainWallRadar", "Operations_TacticalScreens", "Operations_MonitorBezels"]:
    obj = bpy.data.objects.get(obj_name)
    if obj and len(obj.data.materials) > 0:
        obj.data.materials[0] = mat_tactical_screen

# 1B. Procedural Rich Leather Book Spines Shader
mat_rich_books = bpy.data.materials.new("Mat_Procedural_RichBooks")
mat_rich_books.use_nodes = True
bnodes = mat_rich_books.node_tree.nodes
blinks = mat_rich_books.node_tree.links
bnodes.clear()

b_out = bnodes.new('ShaderNodeOutputMaterial')
b_bsdf = bnodes.new('ShaderNodeBsdfPrincipled')
b_tex_coord = bnodes.new('ShaderNodeTexCoord')
b_voronoi = bnodes.new('ShaderNodeTexVoronoi')
b_voronoi.feature = 'F1'
b_voronoi.inputs['Scale'].default_value = 16.0

b_ramp = bnodes.new('ShaderNodeValToRGB')
b_ramp.color_ramp.interpolation = 'CONSTANT'
# Palette: Burgundy Red, Forest Green, Navy Blue, Antique Gold, Deep Brown
b_ramp.color_ramp.elements[0].position = 0.0
b_ramp.color_ramp.elements[0].color = (0.35, 0.05, 0.06, 1.0) # Burgundy
e1 = b_ramp.color_ramp.elements.new(0.25)
e1.color = (0.04, 0.22, 0.08, 1.0) # Forest Green
e2 = b_ramp.color_ramp.elements.new(0.50)
e2.color = (0.05, 0.12, 0.32, 1.0) # Navy Blue
e3 = b_ramp.color_ramp.elements.new(0.75)
e3.color = (0.65, 0.48, 0.15, 1.0) # Antique Gold

blinks.new(b_tex_coord.outputs['Object'], b_voronoi.inputs['Vector'])
blinks.new(b_voronoi.outputs['Distance'], b_ramp.inputs['Fac'])
blinks.new(b_ramp.outputs['Color'], b_bsdf.inputs['Base Color'])
b_bsdf.inputs['Roughness'].default_value = 0.45
blinks.new(b_bsdf.outputs['BSDF'], b_out.inputs['Surface'])

obj_books = bpy.data.objects.get("Library_Books")
if obj_books and len(obj_books.data.materials) > 0:
    obj_books.data.materials[0] = mat_rich_books

# 1C. Procedural Medical ECG Vital Signs Monitor Shader
mat_ecg = bpy.data.materials.new("Mat_Procedural_MedicalECG")
mat_ecg.use_nodes = True
mnodes = mat_ecg.node_tree.nodes
mlinks = mat_ecg.node_tree.links
mnodes.clear()

m_out = mnodes.new('ShaderNodeOutputMaterial')
m_bsdf = mnodes.new('ShaderNodeBsdfPrincipled')
m_bsdf.inputs['Base Color'].default_value = (0.01, 0.04, 0.05, 1.0)
m_bsdf.inputs['Roughness'].default_value = 0.1

m_tex_coord = mnodes.new('ShaderNodeTexCoord')
m_wave = mnodes.new('ShaderNodeTexWave')
m_wave.wave_type = 'BANDS'
m_wave.inputs['Scale'].default_value = 45.0
m_wave.inputs['Distortion'].default_value = 4.0

m_ramp = mnodes.new('ShaderNodeValToRGB')
m_ramp.color_ramp.elements[0].position = 0.6
m_ramp.color_ramp.elements[0].color = (0.01, 0.04, 0.05, 1.0)
m_ramp.color_ramp.elements[1].position = 0.85
m_ramp.color_ramp.elements[1].color = (0.0, 1.0, 0.65, 1.0) # Glowing Cyan/Green ECG trace

mlinks.new(m_tex_coord.outputs['Generated'], m_wave.inputs['Vector'])
mlinks.new(m_wave.outputs['Color'], m_ramp.inputs['Fac'])
mlinks.new(m_ramp.outputs['Color'], m_bsdf.inputs['Emission Color'])
m_bsdf.inputs['Emission Strength'].default_value = 3.5
mlinks.new(m_bsdf.outputs['BSDF'], m_out.inputs['Surface'])

obj_med = bpy.data.objects.get("Medical_EquipmentDetails")
if obj_med:
    # Append ECG material
    obj_med.data.materials.append(mat_ecg)

# -----------------------------------------------------------------------------
# 2. CAMERA COMPOSITION ENHANCEMENTS
# -----------------------------------------------------------------------------
print(">>> OPTIMIZING CAMERA RIG COMPOSITIONS...")
R_CYLINDER = 15.0

def get_deck_matrix(x_pos, theta_deg):
    rad = math.radians(theta_deg)
    px = x_pos
    py = -R_CYLINDER * math.sin(rad)
    pz = -R_CYLINDER * math.cos(rad)
    c = math.cos(rad)
    s = math.sin(rad)
    return Matrix((
        (1.0, 0.0, 0.0, px),
        (0.0, -c,   s,   py),
        (0.0,  s,   c,   pz),
        (0.0, 0.0, 0.0, 1.0)
    ))

def update_camera_transform(name, x_pos, theta_deg, local_pos, local_target, focal_length=35.0):
    cobj = bpy.data.objects.get(name)
    if not cobj:
        return
    cobj.data.lens = focal_length
    mat_deck = get_deck_matrix(x_pos, theta_deg)
    dir_vec = (local_target - local_pos).normalized()
    z_c = -dir_vec
    up_v = Vector((0.0, 0.0, 1.0))
    x_c = dir_vec.cross(up_v).normalized()
    y_c = z_c.cross(x_c).normalized()
    l_mat = Matrix((
        (x_c.x, y_c.x, z_c.x, local_pos.x),
        (x_c.y, y_c.y, z_c.y, local_pos.y),
        (x_c.z, y_c.z, z_c.z, local_pos.z),
        (0.0,   0.0,   0.0,   1.0)
    ))
    cobj.matrix_world = mat_deck @ l_mat

# 1. Jet Turbine Bay: Front three-quarter dynamic shot
update_camera_transform("CAM_Master_Jet_Turbine_Bay", -17.0, 200.0,
                        local_pos=Vector((2.6, -2.4, 1.6)),
                        local_target=Vector((0.2, 0.0, 0.95)),
                        focal_length=32.0)

# 2. Medical Clinic: Bed & biometric monitor view
update_camera_transform("CAM_Master_Medical_Clinic", 17.0, 45.0,
                        local_pos=Vector((-2.2, -1.8, 1.6)),
                        local_target=Vector((0.0, 0.2, 0.75)),
                        focal_length=32.0)

# 3. History & Trophies: Balanced view of armor statue, vitrine, red runner, Scottish flag
update_camera_transform("CAM_Master_History_Trophies", 17.0, 180.0,
                        local_pos=Vector((0.4, -3.2, 1.6)),
                        local_target=Vector((0.4, 0.0, 1.1)),
                        focal_length=32.0)

# 4. RD & Bar: Wide angle framing both the holographic globe and the neon red bar
update_camera_transform("CAM_Master_RD_Stasis_Lab", -17.0, 105.0,
                        local_pos=Vector((0.0, -3.8, 1.6)),
                        local_target=Vector((0.0, 0.0, 1.1)),
                        focal_length=28.0)

# 5. Add Hero Camera: Drone Flight Path inside the open central cylinder corridor
col_cams = bpy.data.collections.get("05_CAMERAS")
cam_flight_data = bpy.data.cameras.new("CAM_Master_Drone_Flight")
cam_flight_data.lens = 22.0
cam_flight_obj = bpy.data.objects.new("CAM_Master_Drone_Flight", cam_flight_data)
col_cams.objects.link(cam_flight_obj)

# Camera flying alongside Drone Alpha at X = -7.0, Y = -1.2, Z = 5.2 looking forward down the tube
f_pos = Vector((-7.5, -1.2, 5.2))
f_target = Vector((15.0, -0.5, 4.0))
f_dir = (f_target - f_pos).normalized()
f_zc = -f_dir
f_up = Vector((0.0, 0.0, 1.0))
f_xc = f_dir.cross(f_up).normalized()
f_yc = f_zc.cross(f_xc).normalized()
cam_flight_obj.matrix_world = Matrix((
    (f_xc.x, f_yc.x, f_zc.x, f_pos.x),
    (f_xc.y, f_yc.y, f_zc.y, f_pos.y),
    (f_xc.z, f_yc.z, f_zc.z, f_pos.z),
    (0.0,    0.0,    0.0,    1.0)
))

# Save scene
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(">>> VISUAL MASTERPIECE v4 SUCCESSFULLY APPLIED AND SAVED!")
