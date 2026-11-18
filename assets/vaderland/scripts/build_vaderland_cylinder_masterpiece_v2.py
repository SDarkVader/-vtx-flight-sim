"""
VADERLAND ROTATING OFFICE - MASTERPIECE CYLINDRICAL WORLD BUILDER v2
Builds the complete, uncompromised, photorealistic 3D cylindrical rotating office
matching all canonical reference images, character sheets, and unwrapped environment map.
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, Matrix

# -----------------------------------------------------------------------------
# 0. CONFIGURATION & PATHS
# -----------------------------------------------------------------------------
WORKSPACE = r"c:\Users\steve\Projects\Vaderland\RotatingOffice_v1"
ARTIFACT_DIR = r"C:\Users\steve\.gemini\antigravity\brain\ed31e7eb-4c27-4e85-8fdd-7e684baae6e9"

CANONICAL_MAP_PATH = os.path.join(WORKSPACE, "vaderland_canonical_unwrapped_map.jpg")
RAYMOND_BLEND_PATH = os.path.join(WORKSPACE, "Raymond_Winston_Canonical_v1.blend")
ARTHUR_BLEND_PATH = os.path.join(WORKSPACE, "Arthur_Finch_Canonical_v1.blend")
OUTPUT_BLEND_PATH = os.path.join(WORKSPACE, "Vaderland_RotatingOffice_Full3D_v1.blend")

# Cylinder Dimensions:
# Aspect ratio of 1024 / 682 = 1.5015
# Radius R = 15.0 m -> Circumference = 2 * pi * 15 = 94.248 m
# Length L = Circumference / 1.5015 = 62.77 m -> use 60.0 m
R_CYLINDER = 15.0
CYLINDER_LENGTH = 60.0

# -----------------------------------------------------------------------------
# 1. INITIALIZE BLENDER SCENE
# -----------------------------------------------------------------------------
print(">>> INITIALIZING SCENE...")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "Scene_Vaderland_RotatingOffice"
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.film_transparent = False

# World Environment
world = bpy.data.worlds.new("World_Vaderland")
scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()
w_out = wnodes.new(type='ShaderNodeOutputWorld')
w_bg = wnodes.new(type='ShaderNodeBackground')
w_bg.inputs['Color'].default_value = (0.02, 0.025, 0.04, 1.0) # Deep aerospace ambient
w_bg.inputs['Strength'].default_value = 0.6
wlinks.new(w_bg.outputs['Background'], w_out.inputs['Surface'])

# Master Collections
col_env = bpy.data.collections.new("01_CYLINDRICAL_STRUCTURE")
col_depts = bpy.data.collections.new("02_3D_DEPARTMENTS")
col_chars = bpy.data.collections.new("03_CHARACTERS")
col_lights = bpy.data.collections.new("04_LIGHTING")
col_cams = bpy.data.collections.new("05_CAMERAS")

scene.collection.children.link(col_env)
scene.collection.children.link(col_depts)
scene.collection.children.link(col_chars)
scene.collection.children.link(col_lights)
scene.collection.children.link(col_cams)

# -----------------------------------------------------------------------------
# 2. PBR MATERIAL BUILDERS
# -----------------------------------------------------------------------------
print(">>> BUILDING PBR MATERIALS...")
def make_pbr_material(name, base_color=(0.8, 0.8, 0.8, 1.0), roughness=0.4, metallic=0.0,
                      emission_color=(0.0, 0.0, 0.0, 1.0), emission_strength=0.0,
                      alpha=1.0, clearcoat=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.inputs['Base Color'].default_value = base_color
    node_bsdf.inputs['Roughness'].default_value = roughness
    node_bsdf.inputs['Metallic'].default_value = metallic
    node_bsdf.inputs['Alpha'].default_value = alpha
    node_bsdf.inputs['Emission Color'].default_value = emission_color
    node_bsdf.inputs['Emission Strength'].default_value = emission_strength
    if 'Clearcoat Weight' in node_bsdf.inputs:
        node_bsdf.inputs['Clearcoat Weight'].default_value = clearcoat
    elif 'Coat Weight' in node_bsdf.inputs:
        node_bsdf.inputs['Coat Weight'].default_value = clearcoat

    links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])
    if alpha < 0.99:
        mat.blend_method = 'BLEND'
    return mat

materials = {
    'Hull': make_pbr_material("Mat_OuterHull", (0.15, 0.17, 0.20, 1.0), roughness=0.5, metallic=0.8),
    'Bulkhead': make_pbr_material("Mat_Bulkhead", (0.22, 0.25, 0.28, 1.0), roughness=0.4, metallic=0.6),
    'TrussArch': make_pbr_material("Mat_TrussArch", (0.35, 0.38, 0.42, 1.0), roughness=0.3, metallic=0.7),
    'Mahogany': make_pbr_material("Mat_DarkMahogany", (0.12, 0.04, 0.02, 1.0), roughness=0.35, clearcoat=0.3),
    'GoldBrass': make_pbr_material("Mat_GoldBrass", (0.95, 0.78, 0.35, 1.0), roughness=0.2, metallic=0.95),
    'EmeraldBaize': make_pbr_material("Mat_EmeraldBaize", (0.02, 0.40, 0.12, 1.0), roughness=0.85),
    'CrimsonLeather': make_pbr_material("Mat_CrimsonLeather", (0.40, 0.04, 0.06, 1.0), roughness=0.45),
    'CrimsonVelvet': make_pbr_material("Mat_CrimsonVelvet", (0.45, 0.03, 0.05, 1.0), roughness=0.9),
    'TitaniumFighter': make_pbr_material("Mat_TitaniumFighter", (0.75, 0.78, 0.82, 1.0), roughness=0.25, metallic=0.85),
    'JetBlackCarbon': make_pbr_material("Mat_JetBlackCarbon", (0.03, 0.03, 0.04, 1.0), roughness=0.3, metallic=0.4),
    'CockpitCanopy': make_pbr_material("Mat_CockpitCanopy", (0.05, 0.15, 0.25, 0.6), roughness=0.05, alpha=0.6),
    'AfterburnerOrange': make_pbr_material("Mat_AfterburnerOrange", (1.0, 0.4, 0.05, 1.0), emission_color=(1.0, 0.45, 0.05, 1.0), emission_strength=12.0),
    'CyanEmissive': make_pbr_material("Mat_CyanEmissive", (0.0, 0.85, 1.0, 1.0), emission_color=(0.0, 0.85, 1.0, 1.0), emission_strength=8.0),
    'AmberEmissive': make_pbr_material("Mat_AmberEmissive", (1.0, 0.65, 0.05, 1.0), emission_color=(1.0, 0.65, 0.05, 1.0), emission_strength=8.0),
    'NeonRed': make_pbr_material("Mat_NeonRed", (1.0, 0.05, 0.05, 1.0), emission_color=(1.0, 0.05, 0.05, 1.0), emission_strength=15.0),
    'IndustrialYellow': make_pbr_material("Mat_IndustrialYellow", (0.95, 0.75, 0.05, 1.0), roughness=0.4, metallic=0.3),
    'HazardBlack': make_pbr_material("Mat_HazardBlack", (0.05, 0.05, 0.05, 1.0), roughness=0.5),
    'CleanroomWhite': make_pbr_material("Mat_CleanroomWhite", (0.92, 0.94, 0.96, 1.0), roughness=0.25),
    'KoiTurquoiseWater': make_pbr_material("Mat_KoiTurquoiseWater", (0.02, 0.35, 0.45, 0.7), roughness=0.1, alpha=0.7),
    'CherryBlossomPink': make_pbr_material("Mat_CherryBlossomPink", (0.98, 0.65, 0.75, 1.0), roughness=0.6),
    'JapaneseLacqueredRed': make_pbr_material("Mat_JapaneseLacqueredRed", (0.70, 0.05, 0.05, 1.0), roughness=0.2),
    'DarkMossyStone': make_pbr_material("Mat_DarkMossyStone", (0.15, 0.16, 0.14, 1.0), roughness=0.8),
    'ServerBlackMetal': make_pbr_material("Mat_ServerBlackMetal", (0.08, 0.09, 0.10, 1.0), roughness=0.3, metallic=0.8),
    'ScreenBlueUI': make_pbr_material("Mat_ScreenBlueUI", (0.05, 0.25, 0.65, 1.0), emission_color=(0.08, 0.35, 0.85, 1.0), emission_strength=1.5),
    'BookSpines': make_pbr_material("Mat_BookSpines", (0.2, 0.1, 0.05, 1.0), roughness=0.6),
    'WhitePaper': make_pbr_material("Mat_WhitePaper", (0.92, 0.90, 0.84, 1.0), roughness=0.8),
    'RedStamp': make_pbr_material("Mat_RedStamp", (0.75, 0.08, 0.08, 1.0), roughness=0.9),
    'CorkBoard': make_pbr_material("Mat_CorkBoard", (0.55, 0.38, 0.22, 1.0), roughness=0.95),
    'Glass': make_pbr_material("Mat_Glass", (0.9, 0.95, 1.0, 0.25), roughness=0.05, alpha=0.25),
    'PolishedChrome': make_pbr_material("Mat_PolishedChrome", (0.95, 0.95, 0.97, 1.0), roughness=0.05, metallic=0.98),
}

# -----------------------------------------------------------------------------
# 3. CANONICAL CYLINDRICAL DECK MATERIAL & MESH
# -----------------------------------------------------------------------------
print(">>> BUILDING SEAMLESS CYLINDRICAL DECK...")
mat_deck = bpy.data.materials.new("Mat_Cylinder_Canonical_Deck")
mat_deck.use_nodes = True
dnodes = mat_deck.node_tree.nodes
dlinks = mat_deck.node_tree.links
dnodes.clear()

d_out = dnodes.new(type='ShaderNodeOutputMaterial')
d_bsdf = dnodes.new(type='ShaderNodeBsdfPrincipled')
d_bsdf.inputs['Roughness'].default_value = 0.35
d_bsdf.inputs['Specular IOR Level'].default_value = 0.5
d_bsdf.inputs['Emission Strength'].default_value = 0.35 # Subtle self-illumination for rich graphics

d_tex = dnodes.new(type='ShaderNodeTexImage')
if os.path.exists(CANONICAL_MAP_PATH):
    img = bpy.data.images.load(CANONICAL_MAP_PATH)
    d_tex.image = img

dlinks.new(d_tex.outputs['Color'], d_bsdf.inputs['Base Color'])
dlinks.new(d_tex.outputs['Color'], d_bsdf.inputs['Emission Color'])
dlinks.new(d_bsdf.outputs['BSDF'], d_out.inputs['Surface'])

# Mesh generation with mathematically verified continuous non-mirrored UVs
m_deck = bpy.data.meshes.new("Mesh_Cylinder_Deck")
o_deck = bpy.data.objects.new("Cylinder_Deck", m_deck)
col_env.objects.link(o_deck)
o_deck.data.materials.append(mat_deck)

bm_deck = bmesh.new()
num_x = 96
num_theta = 128

verts_grid = []
for i in range(num_x + 1):
    x = -CYLINDER_LENGTH / 2.0 + (i / num_x) * CYLINDER_LENGTH
    row = []
    for j in range(num_theta):
        theta = (j / num_theta) * 2.0 * math.pi
        y = -R_CYLINDER * math.sin(theta)
        z = -R_CYLINDER * math.cos(theta)
        v = bm_deck.verts.new((x, y, z))
        row.append(v)
    verts_grid.append(row)

bm_deck.verts.ensure_lookup_table()
uv_layer = bm_deck.loops.layers.uv.new("UVMap")

U_MIN, U_MAX = 0.015, 0.985
V_MIN, V_MAX = 0.016, 0.942

for i in range(num_x):
    # Continuous decreasing U un-mirrors the horizontal text and layout perfectly
    u0 = U_MAX - (i / num_x) * (U_MAX - U_MIN)
    u1 = U_MAX - ((i + 1) / num_x) * (U_MAX - U_MIN)
    for j in range(num_theta):
        j_next = (j + 1) % num_theta
        v0 = V_MIN + (j / num_theta) * (V_MAX - V_MIN)
        v1 = V_MIN + ((j + 1) / num_theta) * (V_MAX - V_MIN)

        v_a = verts_grid[i][j]
        v_b = verts_grid[i + 1][j]
        v_c = verts_grid[i + 1][j_next]
        v_d = verts_grid[i][j_next]

        # Inward facing normal winding
        face = bm_deck.faces.new((v_a, v_d, v_c, v_b))
        for loop in face.loops:
            if loop.vert == v_a:
                loop[uv_layer].uv = (u0, v0)
            elif loop.vert == v_d:
                loop[uv_layer].uv = (u0, v1)
            elif loop.vert == v_c:
                loop[uv_layer].uv = (u1, v1)
            elif loop.vert == v_b:
                loop[uv_layer].uv = (u1, v0)

bm_deck.to_mesh(m_deck)
bm_deck.free()

# Outer Hull Shell
m_hull = bpy.data.meshes.new("Mesh_Outer_Hull")
o_hull = bpy.data.objects.new("Outer_Hull", m_hull)
col_env.objects.link(o_hull)
o_hull.data.materials.append(materials['Hull'])
bm_hull = bmesh.new()
bmesh.ops.create_cone(
    bm_hull, cap_ends=False, segments=64,
    radius1=R_CYLINDER + 0.35, radius2=R_CYLINDER + 0.35, depth=CYLINDER_LENGTH,
    matrix=Matrix.Rotation(math.pi / 2.0, 4, 'Y')
)
bm_hull.to_mesh(m_hull)
bm_hull.free()

# End Bulkheads (West and East) with observation cupolas and heavy airlocks
for x_end, name in [(-CYLINDER_LENGTH / 2.0, "End_Bulkhead_West"), (CYLINDER_LENGTH / 2.0, "End_Bulkhead_East")]:
    mb = bpy.data.meshes.new(f"Mesh_{name}")
    ob = bpy.data.objects.new(name, mb)
    col_env.objects.link(ob)
    ob.data.materials.append(materials['Bulkhead'])
    bm_b = bmesh.new()
    bmesh.ops.create_cone(
        bm_b, cap_ends=True, segments=48,
        radius1=R_CYLINDER + 0.4, radius2=R_CYLINDER + 0.4, depth=0.8,
        matrix=Matrix.Translation(Vector((x_end, 0, 0))) @ Matrix.Rotation(math.pi / 2.0, 4, 'Y')
    )
    # Circular iris airlock portal
    bmesh.ops.create_cone(
        bm_b, cap_ends=True, segments=32,
        radius1=4.5, radius2=4.5, depth=1.2,
        matrix=Matrix.Translation(Vector((x_end, 0, 0))) @ Matrix.Rotation(math.pi / 2.0, 4, 'Y')
    )
    bm_b.to_mesh(mb)
    bm_b.free()

# 5 Structural Rib Arch Rings along cylinder (X = -24, -12, 0, 12, 24)
for x_ring in [-24.0, -12.0, 0.0, 12.0, 24.0]:
    mr = bpy.data.meshes.new(f"Mesh_Truss_Ring_{int(x_ring)}")
    obr = bpy.data.objects.new(f"Truss_Ring_{int(x_ring)}", mr)
    col_env.objects.link(obr)
    obr.data.materials.append(materials['TrussArch'])
    bm_r = bmesh.new()
    # Arch ring band
    bmesh.ops.create_cone(
        bm_r, cap_ends=False, segments=64,
        radius1=R_CYLINDER - 0.1, radius2=R_CYLINDER - 0.1, depth=0.6,
        matrix=Matrix.Translation(Vector((x_ring, 0, 0))) @ Matrix.Rotation(math.pi / 2.0, 4, 'Y')
    )
    bmesh.ops.create_cone(
        bm_r, cap_ends=False, segments=64,
        radius1=R_CYLINDER - 0.35, radius2=R_CYLINDER - 0.35, depth=0.4,
        matrix=Matrix.Translation(Vector((x_ring, 0, 0))) @ Matrix.Rotation(math.pi / 2.0, 4, 'Y')
    )
    bm_r.to_mesh(mr)
    bm_r.free()

# -----------------------------------------------------------------------------
# 4. TRANSFORMATION HELPER: MATHEMATICAL DECK COORDINATE MATRIX
# -----------------------------------------------------------------------------
def get_deck_matrix(x_pos, theta_deg):
    rad = math.radians(theta_deg)
    px = x_pos
    py = -R_CYLINDER * math.sin(rad)
    pz = -R_CYLINDER * math.cos(rad)
    c = math.cos(rad)
    s = math.sin(rad)
    # Orthonormal basis:
    # X_local (lateral): (1, 0, 0)
    # Y_local (forward North along theta): (0, -c, s)
    # Z_local (upward toward central axis): (0, s, c)
    return Matrix((
        (1.0, 0.0, 0.0, px),
        (0.0, -c,   s,   py),
        (0.0,  s,   c,   pz),
        (0.0, 0.0, 0.0, 1.0)
    ))

# -----------------------------------------------------------------------------
# 5. HIGH-POLY 3D PROCEDURAL ASSET BUILDERS
# -----------------------------------------------------------------------------
def create_sub_object(name, mesh_func, mat, col, matrix_world):
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

# --- ASSET 1: SLEEK SCI-FI FIGHTER JET (FOR TURNTABLE & WORKSHOP) ---
def build_fighter_jet(parent_matrix, col, prefix="Jet"):
    # Fuselage
    def make_fuselage(bm):
        # Center body
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.25, radius2=0.85, depth=4.2,
                              matrix=Matrix.Translation(Vector((0, 0.8, 0.5))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
        # Nose cone
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.02, radius2=0.25, depth=1.8,
                              matrix=Matrix.Translation(Vector((0, 3.8, 0.42))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
        # Rear body
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -1.8, 0.45))) @ Matrix.Diagonal(Vector((1.6, 2.2, 0.55, 1))))
    create_sub_object(f"{prefix}_Fuselage", make_fuselage, materials['TitaniumFighter'], col, parent_matrix)

    # Canopy
    def make_canopy(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.15, radius2=0.45, depth=1.9,
                              matrix=Matrix.Translation(Vector((0, 1.4, 0.95))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
    create_sub_object(f"{prefix}_Canopy", make_canopy, materials['CockpitCanopy'], col, parent_matrix)

    # Delta Wings
    def make_wings(bm):
        # Swept forward-canted delta wings
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -0.6, 0.45))) @ Matrix.Diagonal(Vector((6.2, 2.6, 0.08, 1))))
        # Wingtip missile rails
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((3.1, -0.6, 0.45))) @ Matrix.Diagonal(Vector((0.08, 1.8, 0.12, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-3.1, -0.6, 0.45))) @ Matrix.Diagonal(Vector((0.08, 1.8, 0.12, 1))))
        # Canards
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 2.1, 0.52))) @ Matrix.Diagonal(Vector((2.2, 0.8, 0.06, 1))))
    create_sub_object(f"{prefix}_Wings", make_wings, materials['TitaniumFighter'], col, parent_matrix)

    # Twin Tailfins (Canted)
    def make_tailfins(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.7, -2.4, 1.1))) @ Matrix.Rotation(0.25, 4, 'Y') @ Matrix.Diagonal(Vector((0.08, 1.2, 1.1, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.7, -2.4, 1.1))) @ Matrix.Rotation(-0.25, 4, 'Y') @ Matrix.Diagonal(Vector((0.08, 1.2, 1.1, 1))))
    create_sub_object(f"{prefix}_Tailfins", make_tailfins, materials['IndustrialYellow'], col, parent_matrix)

    # Twin Jet Exhausts & Afterburner Glow
    def make_exhausts(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.38, radius2=0.32, depth=0.9,
                              matrix=Matrix.Translation(Vector((0.55, -3.1, 0.45))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.38, radius2=0.32, depth=0.9,
                              matrix=Matrix.Translation(Vector((-0.55, -3.1, 0.45))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
    create_sub_object(f"{prefix}_Exhausts", make_exhausts, materials['JetBlackCarbon'], col, parent_matrix)

    def make_afterburners(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.28, radius2=0.28, depth=0.6,
                              matrix=Matrix.Translation(Vector((0.55, -3.4, 0.45))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.28, radius2=0.28, depth=0.6,
                              matrix=Matrix.Translation(Vector((-0.55, -3.4, 0.45))) @ Matrix.Rotation(math.pi/2, 4, 'X'))
    create_sub_object(f"{prefix}_Afterburners", make_afterburners, materials['AfterburnerOrange'], col, parent_matrix)

    # Tricycle Landing Gear
    def make_gear(bm):
        # Nose gear
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.06, radius2=0.06, depth=0.55,
                              matrix=Matrix.Translation(Vector((0, 2.2, 0.25))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.18, radius2=0.18, depth=0.15,
                              matrix=Matrix.Translation(Vector((0, 2.2, 0.1))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
        # Main gear L & R
        for xg in [-1.1, 1.1]:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.08, radius2=0.08, depth=0.55,
                                  matrix=Matrix.Translation(Vector((xg, -0.8, 0.25))))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.22, radius2=0.22, depth=0.2,
                                  matrix=Matrix.Translation(Vector((xg, -0.8, 0.1))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
    create_sub_object(f"{prefix}_LandingGear", make_gear, materials['HazardBlack'], col, parent_matrix)

# --- ASSET 2: REGULATION BILLIARDS / POOL TABLE ---
def build_pool_table(parent_matrix, col):
    # Mahogany Frame & Legs
    def make_frame(bm):
        # Bed apron
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.68))) @ Matrix.Diagonal(Vector((2.4, 1.4, 0.16, 1))))
        # 4 Turned fluted corner legs
        for xl, yl in [(-1.05, -0.55), (1.05, -0.55), (-1.05, 0.55), (1.05, 0.55)]:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.11, radius2=0.08, depth=0.6,
                                  matrix=Matrix.Translation(Vector((xl, yl, 0.3))))
    create_sub_object("PoolTable_MahoganyFrame", make_frame, materials['Mahogany'], col, parent_matrix)

    # Emerald Green Baize (Felt Bed)
    def make_felt(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.77))) @ Matrix.Diagonal(Vector((2.16, 1.16, 0.04, 1))))
    create_sub_object("PoolTable_FeltBed", make_felt, materials['EmeraldBaize'], col, parent_matrix)

    # Brass Corner and Side Pockets
    def make_brass_pockets(bm):
        for xp, yp in [(-1.12, -0.62), (1.12, -0.62), (-1.12, 0.62), (1.12, 0.62), (0, -0.63), (0, 0.63)]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xp, yp, 0.79))) @ Matrix.Diagonal(Vector((0.14, 0.14, 0.05, 1))))
    create_sub_object("PoolTable_BrassPockets", make_brass_pockets, materials['GoldBrass'], col, parent_matrix)

    # Racked Pool Balls & Triangle
    def make_balls(bm):
        # Triangle racked balls
        for row in range(5):
            for col_b in range(row + 1):
                xb = -0.45 + row * 0.065
                yb = -row * 0.035 + col_b * 0.07
                bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.032, matrix=Matrix.Translation(Vector((xb, yb, 0.82))))
        # Cue ball
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.032, matrix=Matrix.Translation(Vector((0.55, 0.0, 0.82))))
    create_sub_object("PoolTable_Balls", make_balls, materials['AmberEmissive'], col, parent_matrix)

    # Suspended 3-Shade Brass Billiard Lamp
    def make_billiard_lamp(bm):
        # Brass horizontal rail
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.025, radius2=0.025, depth=1.8,
                              matrix=Matrix.Translation(Vector((0, 0, 2.1))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
        # 3 Conical lampshades
        for xl in [-0.65, 0.0, 0.65]:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.22, radius2=0.06, depth=0.25,
                                  matrix=Matrix.Translation(Vector((xl, 0, 1.95))))
    create_sub_object("PoolTable_BrassLamp", make_billiard_lamp, materials['GoldBrass'], col, parent_matrix)

    # Velvet Banquette Sofas flanking pool table
    def make_sofas(bm):
        # Sofa South
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -1.6, 0.42))) @ Matrix.Diagonal(Vector((2.6, 0.75, 0.45, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -1.9, 0.72))) @ Matrix.Diagonal(Vector((2.6, 0.3, 0.65, 1))))
        # Sofa North
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.6, 0.42))) @ Matrix.Diagonal(Vector((2.6, 0.75, 0.45, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.9, 0.72))) @ Matrix.Diagonal(Vector((2.6, 0.3, 0.65, 1))))
    create_sub_object("Recreation_VelvetSofas", make_sofas, materials['CrimsonLeather'], col, parent_matrix)

# -----------------------------------------------------------------------------
# 6. DEPARTMENT BUILDERS
# -----------------------------------------------------------------------------
print(">>> CONSTRUCTING 12 HIGH-FIDELITY DEPARTMENTS...")

# --- DEPT 1: RAYMOND'S EXECUTIVE OFFICE (X = 0, theta = 324 deg) ---
def build_dept_raymond(col):
    mat_deck = get_deck_matrix(0.0, 324.0)

    # Dais Platform & Ornate Carpet
    def make_dais(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.4, 0.08))) @ Matrix.Diagonal(Vector((6.5, 4.8, 0.16, 1))))
    create_sub_object("Raymond_Dais", make_dais, materials['Mahogany'], col, mat_deck)

    def make_carpet(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.3, 0.17))) @ Matrix.Diagonal(Vector((5.2, 3.8, 0.02, 1))))
    create_sub_object("Raymond_PersianRug", make_carpet, materials['CrimsonVelvet'], col, mat_deck)

    # Panoramic Window Arc at Rear
    def make_rear_window(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 2.5, 1.8))) @ Matrix.Diagonal(Vector((7.2, 0.15, 2.4, 1))))
    create_sub_object("Raymond_PanoramicWindow", make_rear_window, materials['ScreenBlueUI'], col, mat_deck)

    # Executive Mahogany Desk (Proper ergonomic scale: height 0.65m, width 2.4m, depth 1.1m)
    def make_desk(bm):
        # Top slab
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.0, 0.62))) @ Matrix.Diagonal(Vector((2.4, 1.1, 0.08, 1))))
        # Dual pedestal cabinets
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.85, 0.0, 0.30))) @ Matrix.Diagonal(Vector((0.6, 0.95, 0.58, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.85, 0.0, 0.30))) @ Matrix.Diagonal(Vector((0.6, 0.95, 0.58, 1))))
        # Modesty panel
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -0.4, 0.35))) @ Matrix.Diagonal(Vector((1.2, 0.04, 0.48, 1))))
        # Green leather blotter
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.0, 0.67))) @ Matrix.Diagonal(Vector((1.1, 0.7, 0.02, 1))))
    create_sub_object("Raymond_ExecutiveDesk", make_desk, materials['Mahogany'], col, mat_deck)

    # Executive Throne (BEHIND Raymond at y = 1.35m, so Raymond stands proud in front)
    def make_throne(bm):
        # Seat cushion
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.35, 0.42))) @ Matrix.Diagonal(Vector((0.85, 0.8, 0.16, 1))))
        # High tufted backrest
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.70, 0.95))) @ Matrix.Diagonal(Vector((0.85, 0.18, 1.1, 1))))
        # Armrests
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.42, 1.35, 0.62))) @ Matrix.Diagonal(Vector((0.14, 0.75, 0.28, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.42, 1.35, 0.62))) @ Matrix.Diagonal(Vector((0.14, 0.75, 0.28, 1))))
    create_sub_object("Raymond_ExecutiveThrone", make_throne, materials['CrimsonLeather'], col, mat_deck)

    # Desk Props: Green Banker's Lamp & Armillary Globe
    def make_props(bm):
        # Banker's lamp
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.08, radius2=0.08, depth=0.04, matrix=Matrix.Translation(Vector((-0.75, 0.25, 0.68))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.015, radius2=0.015, depth=0.35, matrix=Matrix.Translation(Vector((-0.75, 0.25, 0.84))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.75, 0.25, 1.02))) @ Matrix.Diagonal(Vector((0.26, 0.12, 0.1, 1))))
        # Armillary globe on pedestal
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.35, radius2=0.25, depth=0.9, matrix=Matrix.Translation(Vector((2.2, 0.8, 0.55))))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.38, matrix=Matrix.Translation(Vector((2.2, 0.8, 1.35))))
    create_sub_object("Raymond_DeskProps", make_props, materials['GoldBrass'], col, mat_deck)

    # Heraldic Banners & Planters
    def make_banners(bm):
        for xb in [-2.4, 2.4]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xb, 2.2, 1.6))) @ Matrix.Diagonal(Vector((0.9, 0.05, 1.8, 1))))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.3, radius2=0.2, depth=0.6, matrix=Matrix.Translation(Vector((xb, 0.5, 0.4))))
    create_sub_object("Raymond_BannersPlanters", make_banners, materials['CrimsonVelvet'], col, mat_deck)

    # APPEND CANONICAL RAYMOND WINSTON
    if os.path.exists(RAYMOND_BLEND_PATH):
        with bpy.data.libraries.load(RAYMOND_BLEND_PATH, link=False) as (data_from, data_to):
            data_to.objects = [n for n in data_from.objects if not (n.startswith("Studio_") or n.startswith("Cam_") or n.startswith("Target_"))]
        col_ray = bpy.data.collections.new("Col_Raymond_Winston")
        col_chars.children.link(col_ray)
        for obj in data_to.objects:
            if obj:
                col_ray.objects.link(obj)
        ray_root = bpy.data.objects.get("Component_raymond")
        if ray_root:
            # Raymond stands at y = 0.85m, z = 0.16m facing -Y across desk toward visitor camera
            local_trans = Matrix.Translation(Vector((0.0, 0.85, 0.16)))
            ray_root.matrix_world = mat_deck @ local_trans
            print(">>> Raymond Winston placed successfully in Executive Office!")

build_dept_raymond(col_depts)

# --- DEPT 2: ARTHUR'S COMPLIANCE & RECORDS (X = +17.0, theta = 105 deg) ---
def build_dept_arthur(col):
    mat_deck = get_deck_matrix(17.0, 105.0)

    # Arthur's Compliance Investigation Desk
    def make_desk(bm):
        # Desk top
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0.0, 0.58))) @ Matrix.Diagonal(Vector((2.2, 1.1, 0.06, 1))))
        # Desk legs
        for xd, yd in [(-1.0, -0.45), (1.0, -0.45), (-1.0, 0.45), (1.0, 0.45)]:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.04, radius2=0.04, depth=0.55, matrix=Matrix.Translation(Vector((xd, yd, 0.28))))
        # Piles of incident report folders ("INCIDENTS", "EVIDENCE", "DRAFT FINDINGS")
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.65, -0.15, 0.72))) @ Matrix.Diagonal(Vector((0.45, 0.35, 0.22, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.65, 0.22, 0.70))) @ Matrix.Diagonal(Vector((0.42, 0.32, 0.18, 1))))
        # Open incident folder stamped "UNDER REVIEW" (Incident #4713 North Dock)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.15, -0.05, 0.63))) @ Matrix.Diagonal(Vector((0.65, 0.45, 0.04, 1))))
        # VADER'S TAXIS coffee mug
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.065, radius2=0.065, depth=0.14, matrix=Matrix.Translation(Vector((-0.25, -0.28, 0.68))))
    create_sub_object("Arthur_InvestigationDesk", make_desk, materials['WhitePaper'], col, mat_deck)

    # Cork Investigation Pinboard & Filing Cabinets behind Arthur
    def make_corkboard(bm):
        # Corkboard frame & surface
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.7, 1.6))) @ Matrix.Diagonal(Vector((3.2, 0.08, 1.6, 1))))
    create_sub_object("Arthur_Corkboard", make_corkboard, materials['CorkBoard'], col, mat_deck)

    def make_filing_cabinets(bm):
        # Metal filing cabinets on West and East
        for xf in [-1.8, 1.8]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xf, 0.8, 0.95))) @ Matrix.Diagonal(Vector((0.9, 0.75, 1.9, 1))))
    create_sub_object("Arthur_FilingCabinets", make_filing_cabinets, materials['ServerBlackMetal'], col, mat_deck)

    # Task Desk Lamp
    def make_task_lamp(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.07, radius2=0.07, depth=0.03, matrix=Matrix.Translation(Vector((0.75, 0.25, 0.62))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.015, radius2=0.015, depth=0.45, matrix=Matrix.Translation(Vector((0.75, 0.25, 0.85))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.12, radius2=0.04, depth=0.16,
                              matrix=Matrix.Translation(Vector((0.65, 0.15, 1.05))) @ Matrix.Rotation(-0.5, 4, 'X'))
    create_sub_object("Arthur_TaskLamp", make_task_lamp, materials['GoldBrass'], col, mat_deck)

    # APPEND CANONICAL ARTHUR FINCH
    if os.path.exists(ARTHUR_BLEND_PATH):
        with bpy.data.libraries.load(ARTHUR_BLEND_PATH, link=False) as (data_from, data_to):
            data_to.objects = [n for n in data_from.objects if not (n.startswith("Studio_") or n.startswith("Cam_") or n.startswith("Target_"))]
        col_art = bpy.data.collections.new("Col_Arthur_Finch")
        col_chars.children.link(col_art)
        for obj in data_to.objects:
            if obj:
                col_art.objects.link(obj)
        art_root = bpy.data.objects.get("ARTHUR_FINCH_INERTIAL_MOTION_ROOT")
        if art_root:
            # Arthur seated at y = 0.70m, z = 0.12m facing -Y toward compliance desk & camera
            local_trans = Matrix.Translation(Vector((0.0, 0.70, 0.12)))
            art_root.matrix_world = mat_deck @ local_trans
            print(">>> Arthur Finch placed successfully in Compliance Office!")

build_dept_arthur(col_depts)

# --- DEPT 3: TEST BAY & PROTOTYPES / FIGHTER TURNTABLE (X = -17.0, theta = 54 deg) ---
def build_dept_test_bay(col):
    mat_deck = get_deck_matrix(-17.0, 54.0)

    # Circular Turntable Platform with Concentric Rings
    def make_turntable(bm):
        # Outer steel rim
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=5.2, radius2=5.2, depth=0.12, matrix=Matrix.Translation(Vector((0, 0, 0.06))))
        # Inner brass ring
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=3.8, radius2=3.8, depth=0.14, matrix=Matrix.Translation(Vector((0, 0, 0.07))))
        # Center rotating hub
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=2.2, radius2=2.2, depth=0.16, matrix=Matrix.Translation(Vector((0, 0, 0.08))))
    create_sub_object("Turntable_Platform", make_turntable, materials['HazardBlack'], col, mat_deck)

    # Turntable Perimeter Guidance Lights
    def make_lights_ring(bm):
        for k in range(16):
            ang = (k / 16.0) * 2.0 * math.pi
            xl = 4.8 * math.cos(ang)
            yl = 4.8 * math.sin(ang)
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.08, radius2=0.08, depth=0.06, matrix=Matrix.Translation(Vector((xl, yl, 0.15))))
    create_sub_object("Turntable_RunwayLights", make_lights_ring, materials['AmberEmissive'], col, mat_deck)

    # Heavy Tool Chests & Diagnostic Carts
    def make_equipment(bm):
        for xe, ye in [(-4.5, -2.5), (4.5, -2.5), (-4.2, 3.2), (4.2, 3.2)]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xe, ye, 0.6))) @ Matrix.Diagonal(Vector((1.4, 0.85, 1.2, 1))))
    create_sub_object("TestBay_ToolChests", make_equipment, materials['IndustrialYellow'], col, mat_deck)

    # Sleek Sci-Fi Fighter Jet parked on the Turntable!
    # Facing along +Y with canopy, swept delta wings, canted twin fins, glowing afterburners
    jet_trans = Matrix.Translation(Vector((0.0, 0.2, 0.08)))
    build_fighter_jet(mat_deck @ jet_trans, col, prefix="Turntable_Jet")

build_dept_test_bay(col_depts)

# --- DEPT 4: RECREATION & LOUNGE / BILLIARDS (X = 0, theta = 54 deg) ---
def build_dept_recreation(col):
    mat_deck = get_deck_matrix(0.0, 54.0)

    # Regulation Pool Table, Felt, Brass Pockets, Balls, Brass Lamp, Velvet Sofas
    build_pool_table(mat_deck, col)

    # Holographic Gaming / Roulette Table on East
    def make_roulette(bm):
        # Round mahogany base
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=1.1, radius2=0.85, depth=0.75, matrix=Matrix.Translation(Vector((2.8, 0, 0.38))))
        # Glowing holographic disk
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.95, radius2=0.95, depth=0.04, matrix=Matrix.Translation(Vector((2.8, 0, 0.77))))
    create_sub_object("Recreation_RouletteTable", make_roulette, materials['CyanEmissive'], col, mat_deck)

build_dept_recreation(col_depts)

# --- DEPT 5: GARDEN & SERVER CORE (X = 0, theta = 120 - 180 deg) ---
def build_dept_garden(col):
    mat_deck = get_deck_matrix(0.0, 150.0)

    # Stepped Mossy Stone Terraces & Koi Pond
    def make_pond(bm):
        # Water surface
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=3.4, radius2=3.4, depth=0.08, matrix=Matrix.Translation(Vector((0, 0, 0.04))))
    create_sub_object("Garden_KoiPondWater", make_pond, materials['KoiTurquoiseWater'], col, mat_deck)

    # Japanese Arched Wooden Bridge spanning pond
    def make_bridge(bm):
        # Curved timber arch
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.42))) @ Matrix.Diagonal(Vector((1.3, 4.2, 0.12, 1))))
        # Red lacquered railings L & R
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.65, 0, 0.85))) @ Matrix.Diagonal(Vector((0.08, 4.2, 0.8, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.65, 0, 0.85))) @ Matrix.Diagonal(Vector((0.08, 4.2, 0.8, 1))))
    create_sub_object("Garden_JapaneseBridge", make_bridge, materials['JapaneseLacqueredRed'], col, mat_deck)

    # Sakura Cherry Blossom Trees
    def make_cherry_trees(bm):
        for xt, yt in [(-3.2, 2.1), (3.2, 2.1), (-2.8, -2.4), (2.8, -2.4)]:
            # Trunk
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.22, radius2=0.12, depth=1.8, matrix=Matrix.Translation(Vector((xt, yt, 0.9))))
            # Blossom foliage cluster
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.1, matrix=Matrix.Translation(Vector((xt, yt, 2.2))))
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.8, matrix=Matrix.Translation(Vector((xt + 0.3, yt - 0.3, 2.6))))
    create_sub_object("Garden_CherryBlossoms", make_cherry_trees, materials['CherryBlossomPink'], col, mat_deck)

    # Vertical High-Tech Server Rack Towers
    def make_server_racks(bm):
        for xs, ys in [(-3.8, 0.2), (-3.8, -0.9), (3.8, 0.2), (3.8, -0.9)]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xs, ys, 1.2))) @ Matrix.Diagonal(Vector((0.85, 0.9, 2.4, 1))))
    create_sub_object("Garden_ServerRacks", make_server_racks, materials['ServerBlackMetal'], col, mat_deck)

    # Server Status LED Strips
    def make_server_leds(bm):
        for xs, ys in [(-3.8, 0.2), (-3.8, -0.9), (3.8, 0.2), (3.8, -0.9)]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xs, ys - 0.46, 1.2))) @ Matrix.Diagonal(Vector((0.7, 0.04, 2.1, 1))))
    create_sub_object("Garden_ServerLEDs", make_server_leds, materials['CyanEmissive'], col, mat_deck)

build_dept_garden(col_depts)

# --- DEPT 6: VICTORIAN LIBRARY & ARCHIVE (X = +17.0, theta = 280 deg) ---
def build_dept_library(col):
    mat_deck = get_deck_matrix(17.0, 280.0)

    # Curved Two-Tier Tall Mahogany Bookcases
    def make_bookcases(bm):
        for ang_deg in range(-45, 50, 18):
            rad = math.radians(ang_deg)
            xb = 4.2 * math.sin(rad)
            yb = 4.2 * math.cos(rad)
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xb, yb, 1.6))) @ Matrix.Rotation(-rad, 4, 'Z') @ Matrix.Diagonal(Vector((1.4, 0.65, 3.2, 1))))
    create_sub_object("Library_CurvedBookcases", make_bookcases, materials['Mahogany'], col, mat_deck)

    # Bookshelf Spines
    def make_book_spines(bm):
        for ang_deg in range(-40, 45, 18):
            rad = math.radians(ang_deg)
            xb = 4.0 * math.sin(rad)
            yb = 4.0 * math.cos(rad)
            for tier in [0.7, 1.4, 2.1, 2.7]:
                bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xb, yb, tier))) @ Matrix.Rotation(-rad, 4, 'Z') @ Matrix.Diagonal(Vector((1.1, 0.25, 0.35, 1))))
    create_sub_object("Library_Books", make_book_spines, materials['BookSpines'], col, mat_deck)

    # Brass Spiral Staircase
    def make_staircase(bm):
        # Central brass pole
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.08, radius2=0.08, depth=3.2, matrix=Matrix.Translation(Vector((1.8, 1.2, 1.6))))
        # Spiral steps
        for step in range(12):
            ang = step * (math.pi / 6.0)
            zs = 0.2 + step * 0.22
            xs = 1.8 + 0.45 * math.cos(ang)
            ys = 1.2 + 0.45 * math.sin(ang)
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xs, ys, zs))) @ Matrix.Rotation(ang, 4, 'Z') @ Matrix.Diagonal(Vector((0.7, 0.3, 0.06, 1))))
    create_sub_object("Library_SpiralStaircase", make_staircase, materials['GoldBrass'], col, mat_deck)

    # Large Brass Armillary Sphere & Heavy Study Table
    def make_study_table(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.5, 0.0, 0.4))) @ Matrix.Diagonal(Vector((2.2, 1.2, 0.8, 1))))
        # Armillary sphere
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.4, radius2=0.3, depth=0.8, matrix=Matrix.Translation(Vector((-2.2, 0.2, 0.4))))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.55, matrix=Matrix.Translation(Vector((-2.2, 0.2, 1.25))))
    create_sub_object("Library_StudyTable", make_study_table, materials['Mahogany'], col, mat_deck)

build_dept_library(col_depts)

# --- DEPT 7: OPERATIONS & DISPATCH (X = -17.0, theta = 324 deg) ---
def build_dept_operations(col):
    mat_deck = get_deck_matrix(-17.0, 324.0)

    # Semicircular Tiered Command Consoles
    def make_consoles(bm):
        for ang_deg in [-30, 0, 30]:
            rad = math.radians(ang_deg)
            xc = 2.4 * math.sin(rad)
            yc = 2.4 * math.cos(rad) - 0.5
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xc, yc, 0.42))) @ Matrix.Rotation(-rad, 4, 'Z') @ Matrix.Diagonal(Vector((1.6, 0.85, 0.84, 1))))
    create_sub_object("Operations_Consoles", make_consoles, materials['ServerBlackMetal'], col, mat_deck)

    # Blue Tactical Monitor Screens
    def make_screens(bm):
        for ang_deg in [-30, 0, 30]:
            rad = math.radians(ang_deg)
            xc = 2.4 * math.sin(rad)
            yc = 2.4 * math.cos(rad) - 0.5
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((xc, yc + 0.2, 1.05))) @ Matrix.Rotation(-rad, 4, 'Z') @ Matrix.Diagonal(Vector((1.4, 0.1, 0.45, 1))))
    create_sub_object("Operations_TacticalScreens", make_screens, materials['ScreenBlueUI'], col, mat_deck)

    # Giant Main Video Wall at Rear
    def make_video_wall(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 3.2, 1.8))) @ Matrix.Diagonal(Vector((5.8, 0.15, 2.4, 1))))
    create_sub_object("Operations_MainWallRadar", make_video_wall, materials['ScreenBlueUI'], col, mat_deck)

build_dept_operations(col_depts)

# --- DEPT 8: AIRCRAFT WORKSHOP & ENGINEERING (X = -17.0, theta = 200 deg) ---
def build_dept_workshop(col):
    mat_deck = get_deck_matrix(-17.0, 200.0)

    # Jet Turbine Engine Assembly on Yellow Stand
    def make_turbine(bm):
        # Compressor stages & casing
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.65, radius2=0.55, depth=2.8,
                              matrix=Matrix.Translation(Vector((0, 0, 0.95))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
        # Exhaust nozzle
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.55, radius2=0.42, depth=1.1,
                              matrix=Matrix.Translation(Vector((1.9, 0, 0.95))) @ Matrix.Rotation(math.pi/2, 4, 'Y'))
        # Yellow maintenance test stand
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.35))) @ Matrix.Diagonal(Vector((3.4, 1.2, 0.7, 1))))
    create_sub_object("Workshop_JetTurbineEngine", make_turbine, materials['TitaniumFighter'], col, mat_deck)

    # Overhead Traveling Gantry Crane
    def make_crane(bm):
        # Runway I-beams
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, -2.2, 2.8))) @ Matrix.Diagonal(Vector((5.5, 0.35, 0.45, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 2.2, 2.8))) @ Matrix.Diagonal(Vector((5.5, 0.35, 0.45, 1))))
        # Traveling bridge beam
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0.5, 0, 2.8))) @ Matrix.Diagonal(Vector((0.45, 4.4, 0.4, 1))))
    create_sub_object("Workshop_GantryCrane", make_crane, materials['IndustrialYellow'], col, mat_deck)

build_dept_workshop(col_depts)

# --- DEPT 9: RESEARCH & DEVELOPMENT & VADER'S TAXIS BAR (X = -17.0, theta = 105 deg) ---
def build_dept_rd_bar(col):
    mat_deck = get_deck_matrix(-17.0, 105.0)

    # Holographic Globe Projector
    def make_holo_globe(bm):
        # Base plinth
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=1.2, radius2=0.9, depth=0.75, matrix=Matrix.Translation(Vector((-1.8, 0, 0.38))))
        # Holographic wireframe sphere
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.95, matrix=Matrix.Translation(Vector((-1.8, 0, 1.6))))
    create_sub_object("RD_HolographicGlobe", make_holo_globe, materials['CyanEmissive'], col, mat_deck)

    # Vader's Taxis Bar Counter & Stools
    def make_bar(bm):
        # Curved counter
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((1.8, 0, 0.55))) @ Matrix.Diagonal(Vector((1.2, 3.2, 1.1, 1))))
        # Barstools
        for yb in [-1.1, 0.0, 1.1]:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.22, radius2=0.22, depth=0.65, matrix=Matrix.Translation(Vector((1.0, yb, 0.32))))
    create_sub_object("RD_VadersTaxisBar", make_bar, materials['Mahogany'], col, mat_deck)

    # Glowing Neon Red "VADER'S TAXIS" Sign
    def make_neon_sign(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((2.2, 0, 2.2))) @ Matrix.Diagonal(Vector((0.1, 2.8, 0.65, 1))))
    create_sub_object("RD_NeonSign", make_neon_sign, materials['NeonRed'], col, mat_deck)

build_dept_rd_bar(col_depts)

# --- DEPT 10: MEDICAL & RECOVERY (X = +17.0, theta = 45 deg) ---
def build_dept_medical(col):
    mat_deck = get_deck_matrix(17.0, 45.0)

    # High-Tech Patient Recovery Bed
    def make_medbay(bm):
        # Bed frame & mattress
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.45))) @ Matrix.Diagonal(Vector((1.2, 2.4, 0.7, 1))))
        # Articulated overhead scanner arm
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.04, radius2=0.04, depth=1.6, matrix=Matrix.Translation(Vector((-0.8, 0.5, 1.2))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-0.2, 0.5, 1.95))) @ Matrix.Diagonal(Vector((1.1, 0.4, 0.2, 1))))
    create_sub_object("Medical_RecoveryBed", make_medbay, materials['CleanroomWhite'], col, mat_deck)

    # Glowing Cyan Medical Cross Sign
    def make_cross(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.8, 1.5))) @ Matrix.Diagonal(Vector((0.8, 0.05, 0.25, 1))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 1.8, 1.5))) @ Matrix.Diagonal(Vector((0.25, 0.05, 0.8, 1))))
    create_sub_object("Medical_CyanCross", make_cross, materials['CyanEmissive'], col, mat_deck)

build_dept_medical(col_depts)

# --- DEPT 11: HISTORY, TROPHIES & DISPLAYS (X = +17.0, theta = 180 deg) ---
def build_dept_history(col):
    mat_deck = get_deck_matrix(17.0, 180.0)

    # Red Carpet Runner
    def make_carpet(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 0, 0.02))) @ Matrix.Diagonal(Vector((2.4, 6.2, 0.04, 1))))
    create_sub_object("History_RedRunner", make_carpet, materials['CrimsonVelvet'], col, mat_deck)

    # Glass Display Vitrines with Aircraft Models
    def make_vitrines(bm):
        for yv in [-2.2, 2.2]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((-1.4, yv, 0.8))) @ Matrix.Diagonal(Vector((0.8, 1.6, 1.6, 1))))
    create_sub_object("History_DisplayVitrines", make_vitrines, materials['Glass'], col, mat_deck)

    # Ceremonial Polished Chrome Armor Statues
    def make_armor(bm):
        for ya in [-1.2, 1.2]:
            # Plinth
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((1.4, ya, 0.3))) @ Matrix.Diagonal(Vector((0.7, 0.7, 0.6, 1))))
            # Statue body
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.25, radius2=0.18, depth=1.4, matrix=Matrix.Translation(Vector((1.4, ya, 1.3))))
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.22, matrix=Matrix.Translation(Vector((1.4, ya, 2.15))))
    create_sub_object("History_RoboticArmorStatues", make_armor, materials['PolishedChrome'], col, mat_deck)

build_dept_history(col_depts)

# --- DEPT 12: OBSERVATION & LOUNGE (X = +17.0, theta = 345 deg) ---
def build_dept_observation(col):
    mat_deck = get_deck_matrix(17.0, 345.0)

    # Panoramic Observation Window Frame
    def make_obs_window(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector((0, 2.6, 1.8))) @ Matrix.Diagonal(Vector((5.8, 0.15, 2.4, 1))))
    create_sub_object("Observation_Window", make_obs_window, materials['ScreenBlueUI'], col, mat_deck)

    # Brass Telescope on Tripod
    def make_telescope(bm):
        # 3 Tripod legs
        for ang in [0, 2.094, 4.188]:
            xl = 0.45 * math.cos(ang)
            yl = 0.45 * math.sin(ang)
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.02, radius2=0.02, depth=1.2, matrix=Matrix.Translation(Vector((xl, yl + 1.2, 0.6))))
        # Main brass optical tube
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.09, radius2=0.06, depth=1.1,
                              matrix=Matrix.Translation(Vector((0, 1.2, 1.35))) @ Matrix.Rotation(0.4, 4, 'X'))
    create_sub_object("Observation_Telescope", make_telescope, materials['GoldBrass'], col, mat_deck)

build_dept_observation(col_depts)

# -----------------------------------------------------------------------------
# 7. MULTI-LAYER LIGHTING ARCHITECTURE
# -----------------------------------------------------------------------------
print(">>> CALIBRATING MULTI-LAYER CINEMATIC LIGHTING...")
def add_spot_light(name, col, parent_matrix, local_pos, local_target, energy=600.0, spot_size=1.0, color=(1.0, 0.95, 0.88)):
    ldata = bpy.data.lights.new(name=name, type='SPOT')
    ldata.energy = energy
    ldata.spot_size = spot_size
    ldata.color = color
    lobj = bpy.data.objects.new(name, ldata)
    col.objects.link(lobj)

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
    lobj.matrix_world = parent_matrix @ l_mat
    return lobj

def add_point_light(name, col, parent_matrix, local_pos, energy=400.0, color=(1.0, 0.95, 0.88)):
    ldata = bpy.data.lights.new(name=name, type='POINT')
    ldata.energy = energy
    ldata.color = color
    lobj = bpy.data.objects.new(name, ldata)
    col.objects.link(lobj)
    lobj.matrix_world = parent_matrix @ Matrix.Translation(local_pos)
    return lobj

# Department Accent Lights
add_spot_light("Light_Spot_Raymond", col_lights, get_deck_matrix(0, 324), Vector((0, 0, 3.8)), Vector((0, 0.5, 0.6)), energy=900.0, spot_size=0.9, color=(1.0, 0.92, 0.82))
add_point_light("Light_Fill_Raymond", col_lights, get_deck_matrix(0, 324), Vector((0.8, -0.5, 1.4)), energy=350.0, color=(1.0, 0.95, 0.90))

add_spot_light("Light_Spot_Arthur", col_lights, get_deck_matrix(17, 105), Vector((0, 0, 3.5)), Vector((0, 0.2, 0.8)), energy=850.0, spot_size=0.85, color=(1.0, 0.90, 0.78))
add_point_light("Light_Fill_Arthur", col_lights, get_deck_matrix(17, 105), Vector((-0.6, -0.4, 1.3)), energy=300.0, color=(1.0, 0.92, 0.85))

add_spot_light("Light_Spot_Turntable", col_lights, get_deck_matrix(-17, 54), Vector((0, 0, 5.5)), Vector((0, 0, 0.2)), energy=1800.0, spot_size=1.2, color=(0.95, 0.98, 1.0))
add_spot_light("Light_Spot_Billiards", col_lights, get_deck_matrix(0, 54), Vector((0, 0, 2.5)), Vector((0, 0, 0.7)), energy=800.0, spot_size=0.8, color=(1.0, 0.95, 0.85))
add_point_light("Light_Fill_Garden", col_lights, get_deck_matrix(0, 150), Vector((0, 0, 2.8)), energy=600.0, color=(0.7, 0.9, 1.0))
add_point_light("Light_Fill_Library", col_lights, get_deck_matrix(17, 280), Vector((0, 0, 3.2)), energy=750.0, color=(1.0, 0.88, 0.75))
add_point_light("Light_Fill_Operations", col_lights, get_deck_matrix(-17, 324), Vector((0, 0, 3.5)), energy=900.0, color=(0.6, 0.85, 1.0))

add_spot_light("Light_Spot_Turbine", col_lights, get_deck_matrix(-17, 200), Vector((0, -1.0, 3.2)), Vector((0.5, 0, 0.95)), energy=900.0, spot_size=1.0)
add_spot_light("Light_Spot_Medical", col_lights, get_deck_matrix(17, 45), Vector((0, 0, 3.0)), Vector((0, 0, 0.65)), energy=800.0, spot_size=0.9, color=(0.85, 0.95, 1.0))
add_spot_light("Light_Spot_History", col_lights, get_deck_matrix(17, 180), Vector((0, 0, 3.2)), Vector((0, 0, 1.0)), energy=850.0, spot_size=1.0, color=(1.0, 0.92, 0.85))
add_spot_light("Light_Spot_RD_Bar", col_lights, get_deck_matrix(-17, 105), Vector((0, 0, 3.2)), Vector((0, 0, 1.0)), energy=850.0, spot_size=1.0, color=(1.0, 0.95, 0.9))

# Soft Axis Fill Lights (Lighting the massive cylinder habitat)
for x_ax, name in [(-18.0, "Axis_West"), (0.0, "Axis_Center"), (18.0, "Axis_East")]:
    l_ax_data = bpy.data.lights.new(name=f"Light_{name}", type='POINT')
    l_ax_data.energy = 2200.0
    l_ax_data.color = (0.95, 0.96, 1.0)
    l_ax_obj = bpy.data.objects.new(f"Light_{name}", l_ax_data)
    col_lights.objects.link(l_ax_obj)
    l_ax_obj.location = Vector((x_ax, 0.0, 0.0))

# -----------------------------------------------------------------------------
# 8. MASTER CAMERA RIG (12 TARGET INSPECTION VIEWS)
# -----------------------------------------------------------------------------
print(">>> CONFIGURING MASTER CAMERA RIG...")
def create_deck_camera(name, col, x_pos, theta_deg, local_cam_pos, local_target, focal_length=35.0):
    cdata = bpy.data.cameras.new(name)
    cdata.lens = focal_length
    cdata.clip_start = 0.1
    cdata.clip_end = 200.0
    cobj = bpy.data.objects.new(name, cdata)
    col.objects.link(cobj)

    mat_deck = get_deck_matrix(x_pos, theta_deg)
    dir_vec = (local_target - local_cam_pos).normalized()
    z_c = -dir_vec
    up_v = Vector((0.0, 0.0, 1.0))
    x_c = dir_vec.cross(up_v).normalized()
    y_c = z_c.cross(x_c).normalized()

    l_mat = Matrix((
        (x_c.x, y_c.x, z_c.x, local_cam_pos.x),
        (x_c.y, y_c.y, z_c.y, local_cam_pos.y),
        (x_c.z, y_c.z, z_c.z, local_cam_pos.z),
        (0.0,   0.0,   0.0,   1.0)
    ))
    cobj.matrix_world = mat_deck @ l_mat
    return cobj

cameras = {}

# 1. Master Cutaway Diorama Perspective (Inside the cylinder looking down the axis)
cam_diorama_data = bpy.data.cameras.new("CAM_Master_Cutaway_Diorama")
cam_diorama_data.lens = 18.0
cam_diorama_obj = bpy.data.objects.new("CAM_Master_Cutaway_Diorama", cam_diorama_data)
col_cams.objects.link(cam_diorama_obj)
d_pos = Vector((-26.0, 0.0, 3.0))
d_target = Vector((5.0, 0.0, -1.0))
d_dir = (d_target - d_pos).normalized()
d_zc = -d_dir
d_up = Vector((0.0, 0.0, 1.0))
d_xc = d_dir.cross(d_up).normalized()
d_yc = d_zc.cross(d_xc).normalized()
cam_diorama_obj.matrix_world = Matrix((
    (d_xc.x, d_yc.x, d_zc.x, d_pos.x),
    (d_xc.y, d_yc.y, d_zc.y, d_pos.y),
    (d_xc.z, d_yc.z, d_zc.z, d_pos.z),
    (0.0,    0.0,    0.0,    1.0)
))
cameras["CAM_Master_Cutaway_Diorama"] = cam_diorama_obj

# 2. Raymond Winston Portrait Camera (Eye-level across executive desk)
cameras["Cam_Full3D_Raymond"] = create_deck_camera(
    "Cam_Full3D_Raymond", col_cams,
    x_pos=0.0, theta_deg=324.0,
    local_cam_pos=Vector((0.0, -1.35, 1.05)),
    local_target=Vector((0.0, 0.85, 0.95)),
    focal_length=35.0
)

# 3. Arthur Finch Portrait Camera (Eye-level across compliance desk)
cameras["Cam_Full3D_Arthur"] = create_deck_camera(
    "Cam_Full3D_Arthur", col_cams,
    x_pos=17.0, theta_deg=105.0,
    local_cam_pos=Vector((0.0, -1.25, 1.05)),
    local_target=Vector((0.0, 0.70, 0.95)),
    focal_length=35.0
)

# 4. Fighter Turntable Platform & Interceptor (Front three-quarter view)
cameras["CAM_Master_Turntable_Jet"] = create_deck_camera(
    "CAM_Master_Turntable_Jet", col_cams,
    x_pos=-17.0, theta_deg=54.0,
    local_cam_pos=Vector((3.6, 3.8, 1.8)),
    local_target=Vector((0.0, 0.4, 0.6)),
    focal_length=28.0
)

# 5. Billiards & Recreation Lounge
cameras["CAM_Master_Billiards_Lounge"] = create_deck_camera(
    "CAM_Master_Billiards_Lounge", col_cams,
    x_pos=0.0, theta_deg=54.0,
    local_cam_pos=Vector((-2.4, -2.6, 1.8)),
    local_target=Vector((0.0, 0.0, 0.75)),
    focal_length=32.0
)

# 6. Garden Koi Pond, Bridge & Server Core
cameras["CAM_Master_Garden_ServerCore"] = create_deck_camera(
    "CAM_Master_Garden_ServerCore", col_cams,
    x_pos=0.0, theta_deg=150.0,
    local_cam_pos=Vector((0.0, -4.8, 1.8)),
    local_target=Vector((0.0, 0.0, 0.7)),
    focal_length=28.0
)

# 7. Victorian Library & Spiral Staircase
cameras["CAM_Master_Victorian_Library"] = create_deck_camera(
    "CAM_Master_Victorian_Library", col_cams,
    x_pos=17.0, theta_deg=280.0,
    local_cam_pos=Vector((-2.6, -2.6, 1.8)),
    local_target=Vector((0.5, 0.8, 1.4)),
    focal_length=30.0
)

# 8. Operations & Dispatch Video Wall
cameras["CAM_Master_Operations_Dispatch"] = create_deck_camera(
    "CAM_Master_Operations_Dispatch", col_cams,
    x_pos=-17.0, theta_deg=324.0,
    local_cam_pos=Vector((0.0, -3.2, 1.7)),
    local_target=Vector((0.0, 0.5, 1.3)),
    focal_length=30.0
)

# 9. Jet Turbine Bay Workshop
cameras["CAM_Master_Jet_Turbine_Bay"] = create_deck_camera(
    "CAM_Master_Jet_Turbine_Bay", col_cams,
    x_pos=-17.0, theta_deg=200.0,
    local_cam_pos=Vector((-2.6, -2.8, 1.8)),
    local_target=Vector((0.5, 0.0, 0.95)),
    focal_length=32.0
)

# 10. Medical & Recovery Clinic
cameras["CAM_Master_Medical_Clinic"] = create_deck_camera(
    "CAM_Master_Medical_Clinic", col_cams,
    x_pos=17.0, theta_deg=45.0,
    local_cam_pos=Vector((-1.8, -2.2, 1.6)),
    local_target=Vector((0.0, 0.0, 0.65)),
    focal_length=32.0
)

# 11. History, Trophies & Displays
cameras["CAM_Master_History_Trophies"] = create_deck_camera(
    "CAM_Master_History_Trophies", col_cams,
    x_pos=17.0, theta_deg=180.0,
    local_cam_pos=Vector((0.0, -3.6, 1.8)),
    local_target=Vector((0.0, 0.0, 1.1)),
    focal_length=32.0
)

# 12. R&D Holographic Globe & Vader's Taxis Bar
cameras["CAM_Master_RD_Stasis_Lab"] = create_deck_camera(
    "CAM_Master_RD_Stasis_Lab", col_cams,
    x_pos=-17.0, theta_deg=105.0,
    local_cam_pos=Vector((0.0, -3.5, 1.7)),
    local_target=Vector((0.0, 0.0, 1.1)),
    focal_length=32.0
)

# Set default scene camera
scene.camera = cameras["CAM_Master_Cutaway_Diorama"]

# -----------------------------------------------------------------------------
# 9. SAVE MASTER PRODUCTION BLEND FILE
# -----------------------------------------------------------------------------
print(f">>> SAVING MASTER BLEND FILE: {OUTPUT_BLEND_PATH}...")
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND_PATH)
print(">>> VADERLAND FULL 3D CYLINDRICAL WORLD SUCCESSFULLY BUILT AND SAVED!")
