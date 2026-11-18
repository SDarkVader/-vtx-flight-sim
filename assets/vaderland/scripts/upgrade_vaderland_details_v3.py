"""
UPGRADE VADERLAND DETAILS v3
Adds high-poly intricate props, autonomous flying drones in the central airspace,
multi-screen command matrices, library banker's lamps, and hospital recovery equipment.
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, Matrix

BLEND_PATH = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1\Vaderland_RotatingOffice_Full3D_v1.blend"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
scene = bpy.context.scene

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

col_depts = bpy.data.collections.get("02_3D_DEPARTMENTS")
col_lights = bpy.data.collections.get("04_LIGHTING")
col_env = bpy.data.collections.get("01_CYLINDRICAL_STRUCTURE")

# Get materials
mat_brass = bpy.data.materials.get("Mat_GoldBrass")
mat_emerald = bpy.data.materials.get("Mat_EmeraldBaize")
mat_mahogany = bpy.data.materials.get("Mat_DarkMahogany")
mat_screen = bpy.data.materials.get("Mat_ScreenBlueUI")
mat_cyan = bpy.data.materials.get("Mat_CyanEmissive")
mat_amber = bpy.data.materials.get("Mat_AmberEmissive")
mat_titanium = bpy.data.materials.get("Mat_TitaniumFighter")
mat_yellow = bpy.data.materials.get("Mat_IndustrialYellow")
mat_white = bpy.data.materials.get("Mat_CleanroomWhite")
mat_leather = bpy.data.materials.get("Mat_CrimsonLeather")
mat_velvet = bpy.data.materials.get("Mat_CrimsonVelvet")
mat_red = bpy.data.materials.get("Mat_JapaneseLacqueredRed")
mat_glass = bpy.data.materials.get("Mat_Glass")
mat_chrome = bpy.data.materials.get("Mat_PolishedChrome")
mat_water = bpy.data.materials.get("Mat_KoiTurquoiseWater")

def add_sub_object(name, mesh_func, mat, col, matrix_world):
    m = bpy.data.meshes.new(f"Mesh_{name}")
    o = bpy.data.objects.new(name, m)
    col.objects.link(o)
    if mat:
        o.data.materials.append(mat)
    bm = bmesh.new()
    mesh_func(bm)
    bm.to_mesh(m)
    bm.free()
    o.matrix_world = matrix_world
    return o

# -----------------------------------------------------------------------------
# 1. AUTONOMOUS FLYING DRONES IN THE CENTRAL AIRSPACE
# Demonstrates robots flying around and doing work in the rotating office!
# -----------------------------------------------------------------------------
print(">>> ADDING AUTONOMOUS FLYING ROBOTS IN CENTRAL AIRSPACE...")
col_drones = bpy.data.collections.new("03_FLYING_DRONES")
scene.collection.children.link(col_drones)

def build_flying_drone(name, world_matrix):
    # Drone chassis: spherical body with quad rotor arms and glowing sensor eye
    def make_body(bm):
        # Center pod
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.35)
        # 4 carbon fiber rotor arms
        for ang in [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]:
            xa = 0.65 * math.cos(ang)
            ya = 0.65 * math.sin(ang)
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.03, radius2=0.03, depth=0.6,
                                  matrix=Matrix.Translation(Vector((xa/2, ya/2, 0))) @ Matrix.Rotation(ang + math.pi/2, 4, 'Z') @ Matrix.Rotation(math.pi/2, 4, 'X'))
            # Rotor duct ring
            bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.22, radius2=0.22, depth=0.06,
                                  matrix=Matrix.Translation(Vector((xa, ya, 0))))
    add_sub_object(f"{name}_Chassis", make_body, mat_titanium, col_drones, world_matrix)

    # Sensor eye & thruster glow
    def make_sensors(bm):
        # Front camera lens
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.12, radius2=0.12, depth=0.08,
                              matrix=Matrix.Translation(Vector((0, 0.35, 0))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
        # 4 Rotor glow disks
        for ang in [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]:
            xa = 0.65 * math.cos(ang)
            ya = 0.65 * math.sin(ang)
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.18, radius2=0.18, depth=0.02,
                                  matrix=Matrix.Translation(Vector((xa, ya, 0.02))))
    add_sub_object(f"{name}_Lights", make_sensors, mat_cyan, col_drones, world_matrix)

# Drone 1: Patrolling near central hub (X = -5.0, Y = 0.0, Z = 5.0)
m1 = Matrix.Translation(Vector((-5.0, -1.5, 4.5))) @ Matrix.Rotation(0.3, 4, 'Z')
build_flying_drone("Drone_Alpha", m1)

# Drone 2: Surveying over the Turntable Bay (X = -15.0, Y = 2.0, Z = 6.0)
m2 = Matrix.Translation(Vector((-16.0, 3.0, 5.5))) @ Matrix.Rotation(-0.5, 4, 'Z')
build_flying_drone("Drone_Beta", m2)

# Drone 3: Inspecting Operations / Library (X = 12.0, Y = -2.0, Z = 4.0)
m3 = Matrix.Translation(Vector((12.0, -2.5, 4.8))) @ Matrix.Rotation(1.2, 4, 'Z')
build_flying_drone("Drone_Gamma", m3)

# -----------------------------------------------------------------------------
# 2. UPGRADE VICTORIAN LIBRARY (BANKER'S LAMP, WINGBACK CHAIRS, COLORFUL BOOKS)
# -----------------------------------------------------------------------------
print(">>> UPGRADING VICTORIAN LIBRARY PROPS...")
mat_deck_lib = get_deck_matrix(17.0, 280.0)

# Green Banker's Lamp on Study Table
def make_lib_bankers_lamp(bm):
    # Brass base and stem
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.09, radius2=0.09, depth=0.03, matrix=Matrix.Translation(Vector((-0.5, 0.0, 0.81))))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.015, radius2=0.015, depth=0.45, matrix=Matrix.Translation(Vector((-0.5, 0.0, 1.05))))
    # Emerald green shade
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.5, 0.0, 1.28))) @ Matrix.Diagonal(Vector((0.28, 0.14, 0.11, 1))))
add_sub_object("Library_BankersLamp", make_lib_bankers_lamp, mat_emerald, col_depts, mat_deck_lib)

# Two Wingback Leather Armchairs
def make_wingback_chairs(bm):
    for yw in [-0.85, 0.85]:
        # Seat
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.5, yw, 0.38))) @ Matrix.Diagonal(Vector((0.7, 0.65, 0.15, 1))))
        # High curved backrest
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.8, yw, 0.85))) @ Matrix.Diagonal(Vector((0.15, 0.65, 0.85, 1))))
        # Wings
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.65, yw - 0.28, 0.85))) @ Matrix.Diagonal(Vector((0.3, 0.1, 0.7, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.65, yw + 0.28, 0.85))) @ Matrix.Diagonal(Vector((0.3, 0.1, 0.7, 1))))
add_sub_object("Library_WingbackChairs", make_wingback_chairs, mat_leather, col_depts, mat_deck_lib)

# -----------------------------------------------------------------------------
# 3. UPGRADE OPERATIONS COMMAND WALL (MODULAR MONITOR PANELS & WORKSTATIONS)
# -----------------------------------------------------------------------------
print(">>> UPGRADING OPERATIONS COMMAND WALL...")
mat_deck_ops = get_deck_matrix(-17.0, 324.0)

def make_monitor_wall_grid(bm):
    # 3x2 Matrix of angled tactical monitor displays with black bezels
    for col_idx in [-1.8, 0.0, 1.8]:
        for row_idx in [1.2, 2.2]:
            # Black bezel frame
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((col_idx, 3.15, row_idx))) @ Matrix.Diagonal(Vector((1.65, 0.06, 0.9, 1))))
add_sub_object("Operations_MonitorBezels", make_monitor_wall_grid, mat_titanium, col_depts, mat_deck_ops)

# -----------------------------------------------------------------------------
# 4. UPGRADE MEDICAL CLINIC (BIOMETRIC MONITORS & IV STAND)
# -----------------------------------------------------------------------------
print(">>> UPGRADING MEDICAL CLINIC...")
mat_deck_med = get_deck_matrix(17.0, 45.0)

def make_med_equipment(bm):
    # Bed mattress & pillow
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.72))) @ Matrix.Diagonal(Vector((1.1, 2.3, 0.15, 1))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.85, 0.82))) @ Matrix.Diagonal(Vector((0.8, 0.45, 0.12, 1))))
    # IV Stand on Left
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.02, radius2=0.02, depth=1.9, matrix=Matrix.Translation(Vector((-0.8, 0.8, 0.95))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.8, 0.8, 1.8))) @ Matrix.Diagonal(Vector((0.15, 0.15, 0.25, 1))))
    # Biometric monitor cart on Right
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.85, 0.4, 0.6))) @ Matrix.Diagonal(Vector((0.55, 0.55, 1.2, 1))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.85, 0.4, 1.25))) @ Matrix.Diagonal(Vector((0.5, 0.1, 0.35, 1))))
add_sub_object("Medical_EquipmentDetails", make_med_equipment, mat_white, col_depts, mat_deck_med)

# -----------------------------------------------------------------------------
# 5. UPGRADE AIRCRAFT WORKSHOP & ENGINE TEST RIG
# -----------------------------------------------------------------------------
print(">>> UPGRADING WORKSHOP & ENGINE TEST RIG...")
mat_deck_eng = get_deck_matrix(-17.0, 200.0)

def make_engine_details(bm):
    # Multi-stage compressor discs inside nacelle
    for xd in [-0.8, -0.4, 0.0, 0.4, 0.8]:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.58, radius2=0.58, depth=0.05,
                              matrix=Matrix.Translation(Vector((xd, 0, 0.95))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
    # Fuel manifold ring
    bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.68, radius2=0.68, depth=0.1,
                          matrix=Matrix.Translation(Vector((1.1, 0, 0.95))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
    # Mechanic red tool cabinet
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-2.4, 1.6, 0.55))) @ Matrix.Diagonal(Vector((1.2, 0.7, 1.1, 1))))
    # Diagnostic computer terminal
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((2.4, 1.6, 0.55))) @ Matrix.Diagonal(Vector((0.9, 0.6, 1.1, 1))))
add_sub_object("Workshop_EngineDetails", make_engine_details, mat_yellow, col_depts, mat_deck_eng)

# -----------------------------------------------------------------------------
# 6. UPGRADE JAPANESE GARDEN (BRIDGE ARCH, STEPPING STONES, LANTERN)
# -----------------------------------------------------------------------------
print(">>> UPGRADING JAPANESE GARDEN PROPS...")
mat_deck_gar = get_deck_matrix(0.0, 150.0)

def make_garden_props(bm):
    # Japanese Stone Lantern (Toro) beside pond
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.25, radius2=0.2, depth=0.3, matrix=Matrix.Translation(Vector((-1.8, -1.8, 0.15))))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.12, radius2=0.12, depth=0.6, matrix=Matrix.Translation(Vector((-1.8, -1.8, 0.55))))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.35, radius2=0.05, depth=0.25, matrix=Matrix.Translation(Vector((-1.8, -1.8, 1.0))))
    # Stepping stones across water
    for xs, ys in [(0.8, -1.2), (1.4, -0.6), (1.8, 0.2), (1.5, 0.9)]:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.3, radius2=0.28, depth=0.08, matrix=Matrix.Translation(Vector((xs, ys, 0.05))))
add_sub_object("Garden_StoneLanternAndSteps", make_garden_props, mat_brass, col_depts, mat_deck_gar)

# Save updated scene
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(">>> UPGRADES APPLIED AND SAVED TO MASTER BLEND FILE!")
