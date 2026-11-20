"""Blender script: lay out the cockpit-study GLBs in labelled grids, render them and save a .blend to browse.

Rows = enclosure variant (current bubble reference first), columns = pilot posture. Each grid is drawn with an
orthographic camera so every case is at the same scale. Colours come from the GLB's per-face COLOR_0 attribute;
glazing is rendered see-through so the pilot manikin is visible.
Usage: blender -b --factory-startup --python render_study.py -- <study.json> <out_dir> [--no-render]
"""
import json
import math
import pathlib
import sys

import bpy
from mathutils import Euler, Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STUDY = pathlib.Path(argv[0]).resolve()
OUT = pathlib.Path(argv[1]).resolve()
DO_RENDER = '--no-render' not in argv
PROFILE_ARG = None
if '--profile' in argv:
    p_idx = argv.index('--profile')
    if p_idx + 1 < len(argv):
        PROFILE_ARG = pathlib.Path(argv[p_idx + 1]).resolve()
WT = STUDY.resolve().parents[2] if STUDY.parent.name == 'cockpit_study' and STUDY.parent.parent.name == 'scratch' else None
data = json.loads(STUDY.read_text(encoding='utf-8'))
results = data['results']
ROWS = ['REF_current_bubble', 'A_continuous', 'B_faceted', 'C_hardtop']
COLS = ['upright_18', 'semi_35', 'reclined_50']
ROW_TITLE = {'REF_current_bubble': 'CURRENT BUBBLE (reference)', 'A_continuous': 'A  CONTINUOUS', 'B_faceted': 'B  FACETED',
             'C_hardtop': 'C  HARDTOP'}
COL_TITLE = {'upright_18': 'upright 18°', 'semi_35': 'semi-reclined 35°', 'reclined_50': 'reclined 50°'}
COCKPIT_NODES = ('Ricochet_ConceptA_Hull_Cabin', 'Ricochet_Canopy_Glass', 'Ricochet_Cockpit_Interior',
                 'Ricochet_Avionics_Display', 'Study_Pilot_Manikin')

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene = bpy.context.scene
for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        continue
try:
    scene.eevee.taa_render_samples = 48
except Exception:
    pass
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('study_world')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.86, 0.88, 0.90, 1.0)
world.node_tree.nodes['Background'].inputs[1].default_value = 1.0
scene.world = world

_mats = {}


def study_material(gltf_name: str, attr_name: str):
    key = (gltf_name, attr_name)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(f'study_{gltf_name}')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    a = nt.nodes.new('ShaderNodeAttribute')
    a.attribute_type = 'GEOMETRY'
    a.attribute_name = attr_name
    nt.links.new(a.outputs['Color'], p.inputs['Base Color'])
    props = {'carbon_satin': (0.25, 0.45), 'vtx_gold_paint': (0.6, 0.25), 'titanium_strut': (0.8, 0.3), 'fan_rotor': (0.5, 0.35),
             'cockpit_detail': (0.05, 0.7), 'avionics_glow': (0.0, 0.3), 'canopy_glass': (0.0, 0.05)}
    met, rough = props.get(gltf_name.split('.')[0], (0.1, 0.5))
    p.inputs['Metallic'].default_value = met
    p.inputs['Roughness'].default_value = rough
    if gltf_name.startswith('canopy_glass'):
        p.inputs['Alpha'].default_value = 0.30
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
        m.use_backface_culling = False
    if gltf_name.startswith('avionics_glow') and 'Emission Color' in p.inputs:
        nt.links.new(a.outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 2.0
    _mats[key] = m
    return m


def import_case(glb: pathlib.Path, offset: Vector, keep=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        base = o.name.split('.')[0]
        if keep is not None and o.type == 'MESH' and base not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
            new.remove(o)
    for o in new:
        if o.type != 'MESH':
            continue
        attr = o.data.color_attributes[0].name if len(o.data.color_attributes) else 'Color'
        for slot in o.material_slots:
            if slot.material is not None:
                slot.material = study_material(slot.material.name, attr)
        o.location = o.location + offset
    return new


if PROFILE_ARG is not None and PROFILE_ARG.exists():
    PROFILE = json.loads(PROFILE_ARG.read_text(encoding='utf-8'))
elif WT is not None:
    PROFILE = json.loads((WT / 'inputs' / 'ricochet_profiles' / 'rc01_real_components_v1.json').read_text(encoding='utf-8'))
else:
    PROFILE = None
SPONSON_MOUNT = (-0.34, 3.80, 0.48)  # hull_geometry / concept_a_builder SPONSON_MOUNT_CONCEPT_A_VTX


def _ski_material(name='ski_as_simulated', color=(0.05, 0.22, 0.62, 1.0), metallic=0.2, roughness=0.45):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = color
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    return m


def add_skis(offset: Vector, coll):
    """Skis, struts, fins and optional aft trim ski matching the active Ricochet physics profile."""
    if PROFILE is None or 'skis' not in PROFILE:
        return []
    ski = PROFILE['skis']
    L, b, t = float(ski['length_m']), float(ski['beam_m']), float(ski['thickness_m'])
    a_te, zb = float(ski['hinge_from_trailing_edge_m']), float(ski['bottom_below_pivot_m'])
    pv = ski['pivot_in_sponson_m']
    fin = ski.get('fin')
    strut = ski.get('strut')
    mat = _ski_material()
    mat_strut = _ski_material('ski_strut_ti', (0.55, 0.59, 0.65, 1.0), metallic=0.8, roughness=0.3)
    out = []

    def _add_box(centre, size, material):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=Vector(centre) + offset)
        o = bpy.context.active_object
        o.scale = size
        o.data.materials.append(material)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        out.append(o)

    for sy in (1.0, -1.0):
        piv = Vector((SPONSON_MOUNT[0] + pv[0], sy * (SPONSON_MOUNT[1] + pv[1]), SPONSON_MOUNT[2] + pv[2]))
        te_x = piv.x - a_te
        _add_box((te_x + 0.5 * L, piv.y, piv.z - zb + 0.5 * t), (L, b, t), mat)
        if fin:
            _add_box((piv.x + fin['x_from_pivot_m'], piv.y, piv.z - zb - 0.5 * fin['span_m']),
                     (fin['chord_m'], 0.016, fin['span_m']), mat)
        st_h = max(0.08, (SPONSON_MOUNT[2] - 0.10) - (piv.z - zb + t))
        st_c = float(strut['chord_m']) if strut else 0.16
        st_t = float(strut['thickness_m']) if strut else 0.032
        _add_box((piv.x, piv.y, (piv.z - zb + t) + 0.5 * st_h), (st_c, st_t, st_h), mat_strut)

    aski = PROFILE.get('aft_ski')
    if aski:
        pva = Vector(aski['pivot_in_airframe_m'])
        La, ba, ta = float(aski['length_m']), float(aski['beam_m']), float(aski['thickness_m'])
        aa_te, zba = float(aski['hinge_from_trailing_edge_m']), float(aski['bottom_below_pivot_m'])
        _add_box((pva.x - aa_te + 0.5 * La, pva.y, pva.z - zba + 0.5 * ta), (La, ba, ta), mat)
        st_ha = max(0.08, 0.36 - (pva.z - zba + ta))
        _add_box((pva.x, pva.y, (pva.z - zba + ta) + 0.5 * st_ha), (0.14, 0.028, st_ha), mat_strut)
        afin = aski.get('fin')
        if afin:
            _add_box((pva.x + afin['x_from_pivot_m'], pva.y, pva.z - zba - 0.5 * afin['span_m']),
                     (afin['chord_m'], 0.014, afin['span_m']), mat)
    return out


def add_text(body, loc, rot, size, coll, color=(0.05, 0.05, 0.06, 1.0), align='CENTER'):
    cu = bpy.data.curves.new('lbl', 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = 'TOP'
    ob = bpy.data.objects.new('label', cu)
    ob.location = loc
    ob.rotation_euler = rot
    for attr in ('visible_glossy', 'visible_shadow', 'visible_transmission'):
        try:
            setattr(ob, attr, False)
        except Exception:
            pass
    m = bpy.data.materials.new('label_mat')
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = color
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
    cu.materials.append(m)
    coll.objects.link(ob)
    return ob


def case_lines(r):
    if r['variant'] == 'REF_current_bubble':
        cl = r['clearance_m']
        return (f"average pilot does NOT fit: head {cl.get('head', 0):+.2f} m, shoulders {cl.get('shoulder', 0):+.2f} m\n"
                f"canopy CdA {r['canopy_CdA_m2']:.3f} m²   craft {r['craft_CdA_parasite_m2']:.3f} m²\n"
                f"glazing {r['glazing_m2']:.2f} m²")
    v = r['vision']
    return (f"{r['max_height_above_sill']:.2f} m above sill   top z {r['enclosure_peak_z']:.2f} m\n"
            f"canopy CdA {r['canopy_CdA_m2']:.3f} m²   craft {r['craft_CdA_parasite_m2']:.3f} m²\n"
            f"view over nose {v['over_nose_down_view_deg']:.0f}°   sightline/glass {v['sightline_to_glass_angle_deg']}°\n"
            f"glazing {r['glazing_m2']:.2f} m² + fairing {r['opaque_fairing_m2']:.2f} m²   seat +{r['seat_moved_fwd_m']:.2f} m")


def screen_axes(view_dir: Vector):
    d = view_dir.normalized()          # from target toward camera
    right = (-d).cross(Vector((0, 0, 1))).normalized()
    up = right.cross(-d).normalized()
    return right, up


def build_grid(name, view_dir, dc, dr, keep=None, text_size=0.32, label_drop=1.0):
    """Cells are dc wide and dr tall (metres, screen axes); each label hangs label_drop metres below its model."""
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    right, up = screen_axes(view_dir)
    rot = view_dir.to_track_quat('Z', 'Y').to_euler()
    centre_c = (len(COLS) - 1) / 2.0
    centre_r = (len(ROWS) - 1) / 2.0
    by = {(r['variant'], r['posture']): r for r in results}
    placed = []
    for i, rv in enumerate(ROWS):
        for j, pc in enumerate(COLS):
            r = by.get((rv, pc))
            if r is None:
                continue
            off = (j - centre_c) * dc * right - (i - centre_r) * dr * up
            glb = (WT / r['glb']) if WT else pathlib.Path(r['glb'])
            if not glb.is_file():
                alt_glb = STUDY.parent / pathlib.Path(r['glb']).name
                if alt_glb.is_file():
                    glb = alt_glb
            objs = import_case(glb, off, keep)
            for o in objs:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                coll.objects.link(o)
            if keep is None:
                add_skis(off, coll)
            add_text(f"{ROW_TITLE[rv]}  ·  {COL_TITLE[pc]}\n" + case_lines(r), off - label_drop * up, rot, text_size, coll)
            placed.append(off)
    return coll, right, up, rot


def camera_for(name, view_dir, ortho_scale, res):
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    cam_data.clip_end = 500.0
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = view_dir.normalized() * 120.0 + Vector((0.4, 0.0, 0.9))
    cam.rotation_euler = view_dir.to_track_quat('Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    return cam, res


def sun(direction, energy=3.5):
    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy = energy
    ob = bpy.data.objects.new('sun', ld)
    ob.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    scene.collection.objects.link(ob)


# name, view direction, cell width, cell height, kept nodes, text size, label drop below model origin, ortho scale, px
GRIDS = [
    ('side_elevations', Vector((0.0, -1.0, 0.0)), 8.6, 5.2, None, 0.25, 0.35, 27.0, (3600, 3500)),
    ('three_quarter_front', Vector((0.80, -0.62, 0.42)), 11.5, 9.2, None, 0.36, 2.6, 40.0, (3600, 3800)),
    ('cockpit_closeup', Vector((0.55, -0.80, 0.48)), 4.6, 4.2, COCKPIT_NODES, 0.13, 1.25, 20.0, (3600, 3800)),
]
sun(Vector((0.4, -0.5, 1.0)), 3.2)
sun(Vector((-0.6, 0.7, 0.5)), 1.2)
cams = []
for name, vd, dc, dr, keep, ts, ld, oscale, res in GRIDS:
    coll, *_ = build_grid(name, vd, dc, dr, keep, ts, ld)
    cam, res = camera_for('cam_' + name, vd, oscale, res)
    cams.append((name, coll, cam, res))

OUT.mkdir(parents=True, exist_ok=True)
for name, coll, cam, res in cams:
    for _n, c2, _c, _r in cams:
        c2.hide_render = c2 is not coll
        c2.hide_viewport = c2 is not coll
    if not DO_RENDER:
        continue
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(OUT / f'{name}.png')
    bpy.ops.render.render(write_still=True)
for _n, c2, _c, _r in cams:
    c2.hide_render = False
    c2.hide_viewport = _n != 'three_quarter_front'
scene.camera = cams[1][2]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'cockpit_study.blend'))
(OUT / 'render_done.txt').write_text(f'{scene.render.engine}\n')
