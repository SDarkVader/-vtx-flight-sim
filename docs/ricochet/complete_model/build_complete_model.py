"""Headless Blender 5.2+ builder for the complete Ricochet RC-01 `.blend` and Blendstra articulated `.glb`.

Builds from authoritative VTX / MuJoCo sources (never touches legacy `public/assets/ricochet-concept-a.glb`):
  1. Complete interactive `.blend` file:
     - Canonical RC-01 Concept A meshes with cleared rudder hinge cove (0 interference at +/-30 deg);
     - Exact MuJoCo body hierarchy & hinge empties (AXIS_ANGLE about MuJoCo axes, matching `rig_spec.json`);
     - `RC01_Controls` empty with real actuator bounds and live drivers mapped from `rig_spec.json['command_map']`;
     - Watertight carbon ski blades + tracking fins on ski hinges (`ski_port`, `ski_stbd`, optional `ski_aft`)
       and Ti-6Al-4V ski struts on sponsons/airframe, matching `plant.visual_geometry()`;
     - Optional alternate hydro-architecture collection (e.g. Option 2 hydrofoil-skis alongside Option 1 planing)
       so both architectures can be compared directly inside Blender;
     - Real actuator mount markers (Volz DA 30-HT-D, Volz DA 58-D, Exlar GSX30) at exact VTX coordinates;
     - Optional cockpit-study enclosure collections (from `cockpit_study.json`, hidden by default so owner picks);
     - Baked MuJoCo bench-sweep animation (`sweep.json`, 24 fps) + automated per-frame Blender-vs-MuJoCo
       pose-parity verification (`pose_parity_report.json`);
     - Embedded `README` text block and optional studio preview renders.
  2. Blendstra-ready articulated `.glb` (`export_yup=True, export_extras=True, export_animations=True`):
     - Clean production hierarchy matching `tools/rig_blendstra_r6.py` & VTX glTF conventions:
       container empties named after every MuJoCo physical body with `physical_body`, `blendstra_id`,
       `ricochet_joint`, `hinge_axis_vtx`, `range_deg`, and `actuator_component` extras;
     - Crisp PBR materials (`carbon_satin`, `vtx_gold_paint`, `titanium_strut`, `canopy_glass` BLEND,
       `cockpit_detail`, `avionics_glow`, `fan_rotor`) and baked articulation animation tracks.

Usage (headless only, never touch an open Blender GUI window):
  blender -b --factory-startup --python docs/ricochet/complete_model/build_complete_model.py -- \\
      --worktree . --out scratch/complete_model --profile rc01-planing-3pt-v1 \\
      [--alt-profile rc01-hydrofoil-ski-v1] [--rig-spec scratch/complete_model/rig_spec.json] \\
      [--sweep scratch/complete_model/sweep.json] [--cockpit-study scratch/cockpit_study/cockpit_study.json] \\
      [--render]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import pathlib
import sys
import types
from typing import Any

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def _load_vtx_geometry_modules(wt: pathlib.Path):
    """Load pure-NumPy VTX geometry & profile modules inside Blender's bundled Python (no mujoco/scipy needed)."""
    src = wt / 'src'
    for pkg_name, pkg_dir in (
        ('vtx', src / 'vtx'),
        ('vtx.water', src / 'vtx' / 'water'),
        ('vtx.ricochet', src / 'vtx' / 'ricochet'),
    ):
        if pkg_name not in sys.modules:
            mod = types.ModuleType(pkg_name)
            mod.__path__ = [str(pkg_dir)]
            sys.modules[pkg_name] = mod

    def _load(mod_name: str, file_path: pathlib.Path):
        if mod_name in sys.modules:
            return sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod

    _load('vtx.water.datum', src / 'vtx' / 'water' / 'datum.py')
    _load('vtx.water.hydrodynamics', src / 'vtx' / 'water' / 'hydrodynamics.py')
    _load('vtx.ricochet.spec_math', src / 'vtx' / 'ricochet' / 'spec_math.py')
    cab = _load('vtx.ricochet.concept_a_builder', src / 'vtx' / 'ricochet' / 'concept_a_builder.py')
    rc = _load('vtx.ricochet.real_components', src / 'vtx' / 'ricochet' / 'real_components.py')
    return cab, rc


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(description='Build Ricochet RC-01 complete .blend and Blendstra articulated .glb')
    p.add_argument('--worktree', required=True, help='Repository worktree root')
    p.add_argument('--out', required=True, help='Isolated output directory')
    p.add_argument('--profile', default='rc01-planing-3pt-v1', help='Primary Ricochet profile ID')
    p.add_argument('--alt-profile', default='rc01-hydrofoil-ski-v1', help='Optional alternate hydro profile for comparison collection')
    p.add_argument('--rig-spec', default=None, help='Path to rig_spec.json (optional; derived from profile if omitted)')
    p.add_argument('--sweep', default=None, help='Path to sweep.json (optional; synthetic full-range sweep if omitted)')
    p.add_argument('--cockpit-study', default=None, help='Path to cockpit_study.json (optional)')
    p.add_argument('--blend-name', default='ricochet_rc01_complete.blend')
    p.add_argument('--glb-name', default='ricochet_rc01_blendstra_articulated.glb')
    p.add_argument('--render', action='store_true', help='Render studio still previews')
    return p.parse_args(argv)


def _clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _ensure_collection(name: str, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def _move_to_collection(obj, coll) -> None:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


def _build_pbr_materials() -> dict[int, Any]:
    """Create canonical VTX PBR materials keyed by concept_a_builder material index.

    Uses ShaderNodeVertexColor('Color') -> Base Color so every mesh (imported Concept A
    and procedural rudder/skis/struts) exports COLOR_0 and shares the exact 7 canonical
    glTF material names with zero '.001' duplicates, while keeping Alpha unlinked so
    canopy_glass exports alphaMode='BLEND' with explicit baseColorFactor alpha=0.36.
    """
    specs = {
        0: ('carbon_satin', (0.045, 0.052, 0.068, 1.0), 0.18, 0.42, False, None),
        1: ('vtx_gold_paint', (0.910, 0.460, 0.012, 1.0), 0.65, 0.20, False, None),
        2: ('titanium_strut', (0.360, 0.400, 0.455, 1.0), 0.85, 0.25, False, None),
        3: ('canopy_glass', (0.140, 0.300, 0.420, 0.36), 0.08, 0.06, True, None),
        4: ('fan_rotor', (0.145, 0.165, 0.200, 1.0), 0.55, 0.30, False, None),
        5: ('cockpit_detail', (0.035, 0.040, 0.050, 1.0), 0.08, 0.72, False, None),
        6: ('avionics_glow', (0.050, 0.720, 0.880, 1.0), 0.05, 0.20, False, (0.060, 0.750, 0.920, 1.0)),
    }
    mats: dict[int, Any] = {}
    for mid, (name, rgba, metal, rough, is_glass, emissive) in specs.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        if mat.node_tree is None:
            mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get('Principled BSDF')
        for link in list(nt.links):
            if link.to_node == bsdf and link.to_socket.name in ('Base Color', 'Alpha'):
                nt.links.remove(link)
        vcol = nt.nodes.get('VTX_COLOR_0') or nt.nodes.new('ShaderNodeVertexColor')
        vcol.name = 'VTX_COLOR_0'
        vcol.layer_name = 'Color'
        nt.links.new(vcol.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Base Color'].default_value = rgba
        bsdf.inputs['Metallic'].default_value = metal
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Alpha'].default_value = rgba[3] if is_glass else 1.0
        if is_glass:
            try:
                mat.surface_render_method = 'BLENDED'
            except Exception:
                mat.blend_method = 'BLEND'
            mat.use_backface_culling = False
        if emissive is not None and 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emissive
            bsdf.inputs['Emission Strength'].default_value = 1.0
        mats[mid] = mat
    return mats


def _marker_material(name: str, rgba: tuple[float, float, float, float]):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        if m.node_tree is None:
            m.use_nodes = True
        bsdf = m.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = rgba
        bsdf.inputs['Metallic'].default_value = 0.35
        bsdf.inputs['Roughness'].default_value = 0.35
    return m


def _create_mesh_from_part(
    name: str,
    part: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    mats: dict[int, Any],
    coll,
    *,
    physical_body: str,
    blendstra_id: str,
    split_fn=None,
) -> Any:
    """Create a Blender mesh object from a concept_a_builder (verts, faces, face_colors, face_mats) tuple.

    Splits sharp 34-deg creases and color seams identically to `_export_concept_a_glb` and populates
    `UVMap` (TEXCOORD_0) and `Color` (COLOR_0) so every primitive in the exported GLB has identical
    vertex attributes and crisp normals.
    """
    verts, faces, fc, face_mats = part
    me = bpy.data.meshes.new(name + '_Mesh')

    if split_fn is not None:
        prims = split_fn(verts, faces, fc, face_mats, crease_deg=34.0)
        all_pos, all_norm, all_col, all_uv, all_tris, tri_mats = [], [], [], [], [], []
        v_off = 0
        for pr in prims:
            p_pos = np.asarray(pr['pos'], dtype=np.float64)
            p_norm = np.asarray(pr['norm'], dtype=np.float64)
            p_col = np.asarray(pr['col'], dtype=np.float64)
            p_uv = np.asarray(pr['uv'], dtype=np.float64)
            p_idx = np.asarray(pr['idx'], dtype=np.int32).reshape(-1, 3) + v_off
            mid = int(pr['material'])
            all_pos.append(p_pos)
            all_norm.append(p_norm)
            all_col.append(p_col)
            all_uv.append(p_uv)
            all_tris.append(p_idx)
            tri_mats.extend([mid] * len(p_idx))
            v_off += len(p_pos)
        v_arr = np.concatenate(all_pos, axis=0)
        n_arr = np.concatenate(all_norm, axis=0)
        c_arr = np.concatenate(all_col, axis=0)
        u_arr = np.concatenate(all_uv, axis=0)
        f_arr = np.concatenate(all_tris, axis=0)
    else:
        v_arr = np.asarray(verts, dtype=np.float64)
        f_arr = np.asarray(faces, dtype=np.int32)
        n_arr = None
        c_arr = None
        u_arr = np.zeros((len(v_arr), 2), dtype=np.float64)
        tri_mats = [int(m) for m in face_mats]

    me.from_pydata(v_arr.tolist(), [], f_arr.tolist())
    used_mats = sorted(set(tri_mats))
    mat_slot_by_id = {}
    for slot_idx, mid in enumerate(used_mats):
        me.materials.append(mats.get(mid, mats[0]))
        mat_slot_by_id[mid] = slot_idx
    for poly, mid in zip(me.polygons, tri_mats):
        poly.material_index = mat_slot_by_id[int(mid)]
        poly.use_smooth = True
    me.update(calc_edges=True)

    if n_arr is not None:
        try:
            me.normals_split_custom_set_from_vertices([tuple(x) for x in n_arr.tolist()])
        except Exception:
            pass

    uv_layer = me.uv_layers.new(name='UVMap')
    me.uv_layers.active = uv_layer
    loop_verts = [lp.vertex_index for lp in me.loops]
    if u_arr is not None:
        uv_flat = u_arr[loop_verts].ravel().tolist()
        uv_layer.data.foreach_set('uv', uv_flat)

    col_attr = me.color_attributes.new(name='Color', type='BYTE_COLOR', domain='CORNER')
    me.color_attributes.active_color = col_attr
    me.color_attributes.render_color_index = 0
    if c_arr is not None:
        col_flat = c_arr[loop_verts].ravel().tolist()
    else:
        col_flat = []
        for poly_idx, poly in enumerate(me.polygons):
            rgba = [float(x) for x in fc[poly_idx]]
            for _ in poly.loop_indices:
                col_flat.extend(rgba)
    col_attr.data.foreach_set('color', col_flat)

    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    obj['physical_body'] = physical_body
    obj['blendstra_id'] = blendstra_id
    return obj


def _derive_rig_spec_from_profile(wt: pathlib.Path, profile_id: str) -> dict[str, Any]:
    """Fallback rig specification built directly from concept_a_builder & real_components if rig_spec.json omitted."""
    cab, rc = _load_vtx_geometry_modules(wt)

    prof = rc.load_profile(profile_id)
    S = cab.SPONSON_MOUNT_CONCEPT_A_VTX
    F = cab.FAN_CENTER_PORT_VTX
    bodies: dict[str, Any] = {
        'airframe': dict(chain=['airframe'], origin_af=[0.0, 0.0, 0.0], joints=[]),
        'fan_rotor_port': dict(chain=['fan_rotor_port'], origin_af=list(F),
                               joints=[dict(name='fan_rotor_port_hinge', type='hinge', pos_af=list(F), axis_af=[1.0, 0.0, 0.0], limited=False, range=[0.0, 0.0])]),
        'fan_rotor_stbd': dict(chain=['fan_rotor_stbd'], origin_af=[F[0], -F[1], F[2]],
                               joints=[dict(name='fan_rotor_stbd_hinge', type='hinge', pos_af=[F[0], -F[1], F[2]], axis_af=[-1.0, 0.0, 0.0], limited=False, range=[0.0, 0.0])]),
        'aileron_port': dict(chain=['aileron_port'], origin_af=list(cab.AILERON_HINGE_PORT_VTX),
                             joints=[dict(name='aileron_port_hinge', type='hinge', pos_af=list(cab.AILERON_HINGE_PORT_VTX), axis_af=list(cab.AILERON_AXIS_PORT), limited=True, range=[-25.0, 25.0])]),
        'aileron_stbd': dict(chain=['aileron_stbd'], origin_af=list(cab.AILERON_HINGE_STBD_VTX),
                             joints=[dict(name='aileron_stbd_hinge', type='hinge', pos_af=list(cab.AILERON_HINGE_STBD_VTX), axis_af=list(cab.AILERON_AXIS_STBD), limited=True, range=[-25.0, 25.0])]),
        'elevator': dict(chain=['elevator'], origin_af=list(cab.ELEVATOR_HINGE_VTX),
                         joints=[dict(name='elevator_hinge', type='hinge', pos_af=list(cab.ELEVATOR_HINGE_VTX), axis_af=list(cab.ELEVATOR_AXIS), limited=True, range=[-20.0, 20.0])]),
        'rudder': dict(chain=['rudder'], origin_af=list(cab.RUDDER_HINGE_VTX),
                       joints=[dict(name='rudder_hinge', type='hinge', pos_af=list(cab.RUDDER_HINGE_VTX), axis_af=list(cab.RUDDER_AXIS), limited=True, range=[-30.0, 30.0])]),
        'reverse_bucket_port': dict(chain=['reverse_bucket_port'], origin_af=list(cab.REVERSE_BUCKET_HINGE_PORT_VTX),
                                    joints=[dict(name='reverse_bucket_port_hinge', type='hinge', pos_af=list(cab.REVERSE_BUCKET_HINGE_PORT_VTX), axis_af=list(cab.REVERSE_BUCKET_AXIS), limited=True, range=[0.0, 85.0])]),
        'reverse_bucket_stbd': dict(chain=['reverse_bucket_stbd'], origin_af=list(cab.REVERSE_BUCKET_HINGE_STBD_VTX),
                                    joints=[dict(name='reverse_bucket_stbd_hinge', type='hinge', pos_af=list(cab.REVERSE_BUCKET_HINGE_STBD_VTX), axis_af=list(cab.REVERSE_BUCKET_AXIS), limited=True, range=[0.0, 85.0])]),
        'sponson_port': dict(chain=['sponson_port'], origin_af=list(S),
                             joints=[dict(name='sponson_port_flex_z', type='slide', pos_af=list(S), axis_af=[0.0, 0.0, 1.0], limited=True, range=[-0.06, 0.06])]),
        'sponson_stbd': dict(chain=['sponson_stbd'], origin_af=[S[0], -S[1], S[2]],
                             joints=[dict(name='sponson_stbd_flex_z', type='slide', pos_af=[S[0], -S[1], S[2]], axis_af=[0.0, 0.0, 1.0], limited=True, range=[-0.06, 0.06])]),
    }
    ski = prof['skis']
    pv = ski['pivot_in_sponson_m']
    j0s, j1s = (float(v) for v in ski['joint_range_deg'])
    env_s = rc.linear_on_lever_envelope(prof['_components'][ski['actuator']['component']], float(ski['actuator']['lever_m']), ski['actuator'].get('stroke_mm'))
    ski_hi = min(j1s, j0s + float(env_s['travel_deg']))
    for side, sy in (('port', 1.0), ('stbd', -1.0)):
        orig = [S[0] + pv[0], sy * (S[1] + pv[1]), S[2] + pv[2]]
        bodies[f'ski_{side}'] = dict(
            chain=[f'sponson_{side}', f'ski_{side}'],
            origin_af=orig,
            joints=[dict(name=f'ski_{side}_incidence', type='hinge', pos_af=orig, axis_af=[0.0, -1.0, 0.0], limited=True, range=[j0s, j1s])],
        )
    cmd_map: dict[str, Any] = {
        'aileron_port_hinge': dict(terms=[['aileron_deg', -1.0]]),
        'aileron_stbd_hinge': dict(terms=[['aileron_deg', 1.0]]),
        'elevator_hinge': dict(terms=[['elevator_deg', 1.0]]),
        'rudder_hinge': dict(terms=[['rudder_deg', 1.0]]),
        'reverse_bucket_port_hinge': dict(terms=[['reverse_bucket', 85.0]]),
        'reverse_bucket_stbd_hinge': dict(terms=[['reverse_bucket', 85.0]]),
        'ski_port_incidence': dict(terms=[['ski_incidence_deg', 1.0], ['ski_differential_deg', 1.0]], clip_deg=[j0s, ski_hi]),
        'ski_stbd_incidence': dict(terms=[['ski_incidence_deg', 1.0], ['ski_differential_deg', -1.0]], clip_deg=[j0s, ski_hi]),
    }
    ch_limits: dict[str, Any] = {
        'aileron_deg': dict(min=-25.0, max=25.0),
        'elevator_deg': dict(min=-20.0, max=20.0),
        'rudder_deg': dict(min=-30.0, max=30.0),
        'reverse_bucket': dict(min=0.0, max=1.0),
        'ski_incidence_deg': dict(min=float(ski['incidence_command_deg'][0]), max=float(ski['incidence_command_deg'][1])),
        'ski_differential_deg': dict(min=float(ski['differential_command_deg'][0]), max=float(ski['differential_command_deg'][1])),
    }
    aski = prof.get('aft_ski')
    if aski:
        pva = [float(v) for v in aski['pivot_in_airframe_m']]
        j0a, j1a = (float(v) for v in aski['joint_range_deg'])
        bodies['ski_aft'] = dict(
            chain=['ski_aft'],
            origin_af=pva,
            joints=[dict(name='ski_aft_incidence', type='hinge', pos_af=pva, axis_af=[0.0, -1.0, 0.0], limited=True, range=[j0a, j1a])],
        )
        cmd_map['ski_aft_incidence'] = dict(terms=[['aft_ski_incidence_deg', 1.0]], clip_deg=[j0a, j1a])
        ch_limits['aft_ski_incidence_deg'] = dict(min=float(aski['incidence_command_deg'][0]), max=float(aski['incidence_command_deg'][1]))

    return dict(
        profile=profile_id,
        bodies=bodies,
        command_map=cmd_map,
        channel_limits=ch_limits,
        actuator_mounts_vtx_m=prof.get('actuator_mounts_vtx_m', {}),
        surface_actuators=prof.get('surface_actuators', {}),
        ski=ski,
        aft_ski=aski,
        rudder_cove_clear=bool(prof.get('rudder_cove_clear', True)),
    )


def _add_axis_angle_driver(hinge_obj, ctrl_obj, jname: str, spec: dict[str, Any]) -> None:
    """Drive hinge_obj.rotation_axis_angle[0] (radians) from RC01_Controls custom properties."""
    fcurve = hinge_obj.driver_add('rotation_axis_angle', 0)
    drv = fcurve.driver
    drv.type = 'SCRIPTED'
    expr_parts = []
    for idx, (chan, gain) in enumerate(spec['terms']):
        var = drv.variables.new()
        var.name = f'v{idx}'
        var.type = 'SINGLE_PROP'
        var.targets[0].id = ctrl_obj
        var.targets[0].data_path = f'["{chan}"]'
        expr_parts.append(f'({gain:.6f} * v{idx})')
    deg_expr = ' + '.join(expr_parts) if expr_parts else '0.0'
    if 'clip_deg' in spec:
        lo, hi = spec['clip_deg']
        deg_expr = f'min({hi:.6f}, max({lo:.6f}, {deg_expr}))'
    drv.expression = f'radians({deg_expr})'


def _add_slide_z_driver(slide_obj, ctrl_obj, prop_name: str, base_z: float) -> None:
    """Drive slide_obj.location[2] (metres, VTX +Z) from RC01_Controls[prop_name]."""
    fcurve = slide_obj.driver_add('location', 2)
    drv = fcurve.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'dz'
    var.type = 'SINGLE_PROP'
    var.targets[0].id = ctrl_obj
    var.targets[0].data_path = f'["{prop_name}"]'
    drv.expression = f'{base_z:.6f} + dz'


def _configure_controls_object(ctrl_obj, rig_spec: dict[str, Any]) -> None:
    """Attach bounded custom properties to RC01_Controls matching exact actuator limits."""
    ch_limits = rig_spec.get('channel_limits', {})
    defaults = [
        ('aileron_deg', 0.0, -25.0, 25.0, 'Aileron deflection (deg): + right roll'),
        ('elevator_deg', 0.0, -20.0, 20.0, 'Elevator deflection (deg): + TE up / nose up'),
        ('rudder_deg', 0.0, -30.0, 30.0, 'Rudder deflection (deg): + TE port / left yaw'),
        ('reverse_bucket', 0.0, 0.0, 1.0, 'Reverse thrust bucket deployment fraction [0..1] -> [0..85 deg]'),
        ('ski_incidence_deg', 0.0, -6.0, 12.0, 'Outboard ski collective incidence (deg)'),
        ('ski_differential_deg', 0.0, -4.0, 4.0, 'Outboard ski differential roll incidence (deg)'),
        ('sponson_port_flex_m', 0.0, -0.06, 0.06, 'Port sponson vertical heave flex displacement (m)'),
        ('sponson_stbd_flex_m', 0.0, -0.06, 0.06, 'Starboard sponson vertical heave flex displacement (m)'),
        ('fan_port_deg', 0.0, -360000.0, 360000.0, 'Port ducted fan rotor angle (deg)'),
        ('fan_stbd_deg', 0.0, -360000.0, 360000.0, 'Starboard ducted fan rotor angle (deg)'),
    ]
    if rig_spec.get('aft_ski'):
        defaults.append(('aft_ski_incidence_deg', 0.0, -8.0, 10.0, 'Aft trim ski incidence (deg)'))
    for key, val, lo_d, hi_d, desc in defaults:
        lim = ch_limits.get(key, {})
        lo = float(lim.get('min', lo_d))
        hi = float(lim.get('max', hi_d))
        ctrl_obj[key] = float(val)
        ui = ctrl_obj.id_properties_ui(key)
        ui.update(min=lo, max=hi, soft_min=lo, soft_max=hi, default=float(val), description=desc)


def _quat_err_deg(q_a: Quaternion, q_b: Quaternion) -> float:
    dot = abs(float(q_a.dot(q_b)))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def _build_airframe_and_rig(
    wt: pathlib.Path,
    rig_spec: dict[str, Any],
    mats: dict[int, Any],
    coll_main,
    coll_actuators,
    alt_profile_id: str | None,
) -> tuple[dict[str, Any], Any]:
    """Construct canonical meshes, MuJoCo-exact container empties, skis/struts, drivers & markers."""
    cab, rc = _load_vtx_geometry_modules(wt)
    mats_by_name = {m.name: m for m in mats.values()}

    # 1. Build exact MuJoCo body container empties (Blendstra physical_body convention!)
    containers: dict[str, Any] = {}
    root_af = bpy.data.objects.new('airframe', None)
    root_af.empty_display_type = 'PLAIN_AXES'
    root_af.empty_display_size = 0.35
    root_af.location = Vector((0.0, 0.0, 0.0))
    root_af['physical_body'] = 'airframe'
    root_af['blendstra_id'] = 'rc01_body_airframe'
    root_af['profile_id'] = rig_spec['profile']
    root_af['model_revision'] = rig_spec.get(
        'model_revision',
        getattr(rc, 'PROFILE_MODEL_REVISIONS', {}).get(rig_spec['profile'], 'RC01-CA-0'),
    )
    root_af['model_name'] = rig_spec.get(
        'model_name',
        getattr(rc, 'PROFILE_MODEL_NAMES', {}).get(rig_spec['profile'], 'Ricochet RC-01'),
    )
    coll_main.objects.link(root_af)
    containers['airframe'] = root_af

    # Map actuator component per body for glTF extras
    act_by_joint = {v['joint']: v['component'] for v in rig_spec.get('surface_actuators', {}).values()}
    ski_comp = rig_spec.get('ski', {}).get('actuator', {}).get('component', 'exlar_gsx30_2stack_0p2in')
    aski_comp = (rig_spec.get('aft_ski') or {}).get('actuator', {}).get('component', 'volz_da58d')

    # Create bodies in parent-first order (sponsons before skis)
    body_order = [
        'sponson_port', 'sponson_stbd',
        'aileron_port', 'aileron_stbd', 'elevator', 'rudder',
        'reverse_bucket_port', 'reverse_bucket_stbd',
        'fan_rotor_port', 'fan_rotor_stbd',
        'ski_port', 'ski_stbd',
    ]
    if 'ski_aft' in rig_spec['bodies']:
        body_order.append('ski_aft')

    for bname in body_order:
        if bname not in rig_spec['bodies']:
            continue
        binfo = rig_spec['bodies'][bname]
        chain = binfo.get('chain', [bname])
        parent_name = chain[-2] if len(chain) >= 2 else 'airframe'
        parent_obj = containers[parent_name]
        p_af = Vector(binfo['origin_af'])
        p_parent = Vector(rig_spec['bodies'][parent_name]['origin_af']) if parent_name != 'airframe' else Vector((0.0, 0.0, 0.0))

        emp = bpy.data.objects.new(bname, None)
        emp.empty_display_type = 'ARROWS'
        emp.empty_display_size = 0.22
        emp.parent = parent_obj
        emp.location = p_af - p_parent
        emp['physical_body'] = bname
        emp['blendstra_id'] = f'rc01_body_{bname}'

        jlist = binfo.get('joints', [])
        if jlist:
            jt = jlist[0]
            jname = jt['name']
            ax = Vector(jt['axis_af']).normalized()
            emp['ricochet_joint'] = jname
            emp['joint_type'] = jt['type']
            emp['q_rest'] = 0.0
            if jt['type'] == 'slide':
                emp['slide_axis_vtx'] = [round(float(ax.x), 6), round(float(ax.y), 6), round(float(ax.z), 6)]
                if jt.get('limited'):
                    emp['range_m'] = [float(jt['range'][0]), float(jt['range'][1])]
                    emp['range_unit'] = 'm'
            else:
                emp['hinge_axis_vtx'] = [round(float(ax.x), 6), round(float(ax.y), 6), round(float(ax.z), 6)]
                if jt.get('limited'):
                    emp['range_deg'] = [float(jt['range'][0]), float(jt['range'][1])]
                    emp['range_unit'] = 'deg'
            if jname in act_by_joint:
                emp['actuator_component'] = act_by_joint[jname]
            elif bname in ('ski_port', 'ski_stbd'):
                emp['actuator_component'] = ski_comp
            elif bname == 'ski_aft':
                emp['actuator_component'] = aski_comp
            if jt['type'] == 'hinge':
                emp.rotation_mode = 'AXIS_ANGLE'
                emp.rotation_axis_angle = (0.0, float(ax.x), float(ax.y), float(ax.z))
        coll_main.objects.link(emp)
        containers[bname] = emp
    bpy.context.view_layer.update()

    # 2. Import canonical Concept A meshes from the untouched legacy GLB, then replace ONLY the rudder
    #    with the cleared-cove mesh (keeping public/assets/ricochet-concept-a.glb 100% untouched!).
    legacy_glb = wt / 'public' / 'assets' / 'ricochet-concept-a.glb'
    node_to_body = {
        'Ricochet_ConceptA_Hull_Cabin': 'airframe',
        'Ricochet_Sponson_Port': 'sponson_port',
        'Ricochet_Sponson_Stbd': 'sponson_stbd',
        'Ricochet_Wing_Port': 'airframe',
        'Ricochet_Wing_Stbd': 'airframe',
        'Ricochet_Aileron_Port': 'aileron_port',
        'Ricochet_Aileron_Stbd': 'aileron_stbd',
        'Ricochet_Winglet_Port': 'airframe',
        'Ricochet_Winglet_Stbd': 'airframe',
        'Ricochet_Strut_Port': 'airframe',
        'Ricochet_Strut_Stbd': 'airframe',
        'Ricochet_Tail_Pylon_T_Tail': 'airframe',
        'Ricochet_Elevator': 'elevator',
        'Ricochet_Rudder': 'rudder',
        'Ricochet_Duct_Port': 'airframe',
        'Ricochet_Duct_Stbd': 'airframe',
        'Ricochet_Reverse_Bucket_Port': 'reverse_bucket_port',
        'Ricochet_Reverse_Bucket_Stbd': 'reverse_bucket_stbd',
        'Ricochet_Fan_Rotor_Port': 'fan_rotor_port',
        'Ricochet_Fan_Rotor_Stbd': 'fan_rotor_stbd',
        'Ricochet_Fan_Spinner_Port': 'fan_rotor_port',
        'Ricochet_Fan_Spinner_Stbd': 'fan_rotor_stbd',
        'Ricochet_Canopy_Glass': 'airframe',
        'Ricochet_Cockpit_Interior': 'airframe',
        'Ricochet_Avionics_Display': 'airframe',
    }
    before = set(bpy.data.objects)
    before_mats = set(bpy.data.materials)
    bpy.ops.import_scene.gltf(filepath=str(legacy_glb))
    bpy.context.view_layer.update()
    imported = [o for o in bpy.data.objects if o not in before]
    for obj in list(imported):
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        base_name = obj.name.split('.')[0]
        if base_name == 'Ricochet_Rudder' and rig_spec.get('rudder_cove_clear', True):
            old_me = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if old_me is not None and old_me.users == 0:
                bpy.data.meshes.remove(old_me)
            continue
        bname = node_to_body.get(base_name, 'airframe')
        parent_emp = containers[bname]
        mw = obj.matrix_world.copy()
        obj.parent = parent_emp
        obj.matrix_world = mw
        _move_to_collection(obj, coll_main)
        obj['physical_body'] = bname
        obj['blendstra_id'] = f'rc01_{base_name.lower()}'
        # Remap imported .001 materials to canonical VTX PBR materials so zero duplicate materials exist
        for slot in obj.material_slots:
            if slot.material is not None:
                canon_name = slot.material.name.split('.')[0]
                if canon_name in mats_by_name:
                    slot.material = mats_by_name[canon_name]
    for m_imp in [m for m in list(bpy.data.materials) if m not in before_mats]:
        if m_imp.users == 0:
            bpy.data.materials.remove(m_imp)

    # Add cleared-cove rudder directly on the exact rudder hinge empty (0 vertices inside fin at +/-30 deg)
    if rig_spec.get('rudder_cove_clear', True):
        rud_part = cab.build_pass3_rudder(rudder_cove_clear=True)
        rud_obj = _create_mesh_from_part(
            'Ricochet_Rudder', rud_part, mats, coll_main,
            physical_body='rudder', blendstra_id='rc01_ricochet_rudder_cove_clear',
            split_fn=cab._split_sharp_and_color_seams,
        )
        rud_obj.parent = containers['rudder']
        rud_obj.location = Vector((0.0, 0.0, 0.0))

    # 3. Build primary profile skis, fins, struts & optional aft trim ski from single-source concept_a_builder
    def _attach_profile_skis(prof_ski: dict[str, Any], prof_aft: dict[str, Any] | None, target_coll, prefix: str = '', use_containers: bool = True):
        pv = [float(x) for x in prof_ski['pivot_in_sponson_m']]
        strut_cfg = prof_ski.get('strut') or {}
        anchor_x = float(np.clip(pv[0], -0.45, 0.52))
        anchor = (anchor_x, 0.0, -0.10)
        aft_brace = (anchor_x - 0.50, 0.0, -0.10) if abs(pv[0] - anchor_x) > 0.12 or pv[2] < -0.25 else None
        ski_part = cab.build_profile_ski_mesh(prof_ski)
        strut_part = cab.build_profile_ski_strut_mesh(
            pv, anchor,
            chord_m=float(strut_cfg.get('chord_m', 0.18)),
            thickness_m=float(strut_cfg.get('thickness_m', 0.036)),
            aft_brace_anchor=aft_brace,
        )
        S = cab.SPONSON_MOUNT_CONCEPT_A_VTX
        for side, sy in (('port', 1.0), ('stbd', -1.0)):
            so = _create_mesh_from_part(
                f'{prefix}Ricochet_Ski_{side.capitalize()}', ski_part, mats, target_coll,
                physical_body=f'ski_{side}', blendstra_id=f'rc01_{prefix}ski_{side}',
                split_fn=cab._split_sharp_and_color_seams,
            )
            sto = _create_mesh_from_part(
                f'{prefix}Ricochet_Ski_Strut_{side.capitalize()}', strut_part, mats, target_coll,
                physical_body=f'sponson_{side}', blendstra_id=f'rc01_{prefix}ski_strut_{side}',
                split_fn=cab._split_sharp_and_color_seams,
            )
            if use_containers:
                so.parent = containers[f'ski_{side}']
                so.location = Vector((0.0, 0.0, 0.0))
                sto.parent = containers[f'sponson_{side}']
                sto.location = Vector((0.0, 0.0, 0.0))
            else:
                so.location = Vector((S[0] + pv[0], sy * (S[1] + pv[1]), S[2] + pv[2]))
                sto.location = Vector((S[0], sy * S[1], S[2]))

        if prof_aft:
            pva = [float(x) for x in prof_aft['pivot_in_airframe_m']]
            strut_a = prof_aft.get('strut') or {}
            anchor_a = (pva[0], pva[1], float(strut_a.get('anchor_z_airframe_m', 0.36)))
            aft_part = cab.build_profile_ski_mesh(prof_aft)
            aft_st_part = cab.build_profile_ski_strut_mesh(
                pva, anchor_a,
                chord_m=float(strut_a.get('chord_m', 0.16)),
                thickness_m=float(strut_a.get('thickness_m', 0.030)),
                aft_brace_anchor=(pva[0] + 0.30, pva[1], anchor_a[2] - 0.04),
            )
            ao = _create_mesh_from_part(
                f'{prefix}Ricochet_Ski_Aft', aft_part, mats, target_coll,
                physical_body='ski_aft', blendstra_id=f'rc01_{prefix}ski_aft',
                split_fn=cab._split_sharp_and_color_seams,
            )
            asto = _create_mesh_from_part(
                f'{prefix}Ricochet_Ski_Strut_Aft', aft_st_part, mats, target_coll,
                physical_body='airframe', blendstra_id=f'rc01_{prefix}ski_strut_aft',
                split_fn=cab._split_sharp_and_color_seams,
            )
            if use_containers and 'ski_aft' in containers:
                ao.parent = containers['ski_aft']
                ao.location = Vector((0.0, 0.0, 0.0))
                asto.parent = containers['airframe']
                asto.location = Vector((0.0, 0.0, 0.0))
            else:
                ao.location = Vector(pva)
                asto.location = Vector((0.0, 0.0, 0.0))

    _attach_profile_skis(rig_spec['ski'], rig_spec.get('aft_ski'), coll_main, prefix='', use_containers=True)

    # 4. Optional alternate hydro architecture collection (hidden by default in viewport & render)
    if alt_profile_id and alt_profile_id != rig_spec['profile']:
        try:
            alt_prof = rc.load_profile(alt_profile_id)
            coll_alt = _ensure_collection(f'Alt_{alt_profile_id}')
            _attach_profile_skis(alt_prof['skis'], alt_prof.get('aft_ski'), coll_alt, prefix='Alt_', use_containers=False)
            coll_alt.hide_viewport = True
            coll_alt.hide_render = True
        except Exception as exc:
            print(f'Warning: skipped alt profile {alt_profile_id}: {exc}', flush=True)

    # 5. RC01_Controls object + live drivers implementing rig_spec['command_map']
    ctrl_obj = bpy.data.objects.new('RC01_Controls', None)
    ctrl_obj.empty_display_type = 'CUBE'
    ctrl_obj.empty_display_size = 0.25
    ctrl_obj.location = Vector((0.0, 0.0, 2.90))
    coll_actuators.objects.link(ctrl_obj)
    _configure_controls_object(ctrl_obj, rig_spec)

    joint_to_body = {}
    for bname, binfo in rig_spec['bodies'].items():
        for jt in binfo.get('joints', []):
            joint_to_body[jt['name']] = bname

    for jname, cmap in rig_spec.get('command_map', {}).items():
        bname = joint_to_body.get(jname)
        if bname and bname in containers:
            _add_axis_angle_driver(containers[bname], ctrl_obj, jname, cmap)
    for fn, prop in (('fan_rotor_port', 'fan_port_deg'), ('fan_rotor_stbd', 'fan_stbd_deg')):
        if fn in containers:
            _add_axis_angle_driver(containers[fn], ctrl_obj, f'{fn}_hinge', dict(terms=[[prop, 1.0]]))
    for sp_side, sp_prop in (('sponson_port', 'sponson_port_flex_m'), ('sponson_stbd', 'sponson_stbd_flex_m')):
        if sp_side in containers and sp_prop in ctrl_obj:
            base_z = float(rig_spec['bodies'][sp_side]['origin_af'][2])
            _add_slide_z_driver(containers[sp_side], ctrl_obj, sp_prop, base_z)

    # 6. Actuator mount markers (Volz DA 30-HT-D, Volz DA 58-D, Exlar GSX30)
    m_da30 = _marker_material('Actuator_Volz_DA30HTD', (0.15, 0.72, 0.28, 1.0))
    m_da58 = _marker_material('Actuator_Volz_DA58D', (0.95, 0.42, 0.08, 1.0))
    m_exlar = _marker_material('Actuator_Exlar_GSX30', (0.12, 0.45, 0.92, 1.0))
    surf_acts = rig_spec.get('surface_actuators', {})
    for aname, pos in rig_spec.get('actuator_mounts_vtx_m', {}).items():
        comp = surf_acts.get(aname, {}).get('component', 'volz_da30htd')
        is_58 = 'da58' in comp
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=Vector(pos))
        mk = bpy.context.active_object
        mk.name = f'Marker_{aname}'
        mk.scale = (0.12, 0.07, 0.07) if is_58 else (0.08, 0.05, 0.05)
        mk.data.materials.append(m_da58 if is_58 else m_da30)
        mk['actuator_component'] = comp
        _move_to_collection(mk, coll_actuators)
    # Exlar GSX30 linear actuators inside outboard sponsons above ski pivots
    for side in ('port', 'stbd'):
        if f'ski_{side}' in containers:
            sp_orig = Vector(rig_spec['bodies'][f'sponson_{side}']['origin_af'])
            bpy.ops.mesh.primitive_cylinder_add(radius=0.038, depth=0.34, location=sp_orig + Vector((0.25, 0.0, 0.06)))
            mk = bpy.context.active_object
            mk.name = f'Marker_ski_{side}_exlar_gsx30'
            mk.rotation_euler = (0.0, math.radians(90.0), 0.0)
            mk.data.materials.append(m_exlar)
            mk['actuator_component'] = ski_comp
            _move_to_collection(mk, coll_actuators)
    if 'ski_aft' in containers:
        ap = Vector(rig_spec['bodies']['ski_aft']['origin_af'])
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=ap + Vector((0.0, 0.0, 0.24)))
        mk = bpy.context.active_object
        mk.name = 'Marker_ski_aft_actuator'
        mk.scale = (0.11, 0.06, 0.06)
        mk.data.materials.append(m_da58)
        mk['actuator_component'] = aski_comp
        _move_to_collection(mk, coll_actuators)

    return containers, ctrl_obj


def _bake_sweep_and_check_parity(
    containers: dict[str, Any],
    ctrl_obj,
    rig_spec: dict[str, Any],
    sweep_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Bake articulation keyframes onto hinges & RC01_Controls and verify Blender-vs-MuJoCo pose parity."""
    scene = bpy.context.scene
    fps = int(sweep_data['fps']) if sweep_data else 24
    scene.render.fps = fps

    parity = dict(
        source='mujoco_sweep' if sweep_data else 'synthetic_rig_spec_sweep',
        frames_checked=0,
        max_pos_err_m=0.0,
        max_rot_err_deg=0.0,
        worst_body=None,
        worst_frame=None,
    )

    if sweep_data and sweep_data.get('frames'):
        frames = sweep_data['frames']
        scene.frame_start = 0
        scene.frame_end = len(frames) - 1
        # Keyframe exact MuJoCo achieved joint equivalents onto RC01_Controls so Blender drivers
        # track real slew-limited actuator trajectories (zero step-command mismatch during ramps).
        for fr in frames:
            idx = int(fr['frame'])
            jd = fr.get('joints_deg', {})
            poses_af = fr.get('poses_af', {})
            achieved_ctrl = {}
            if 'aileron_port_hinge' in jd and 'aileron_stbd_hinge' in jd:
                achieved_ctrl['aileron_deg'] = 0.5 * (float(jd['aileron_stbd_hinge']) - float(jd['aileron_port_hinge']))
            if 'elevator_hinge' in jd:
                achieved_ctrl['elevator_deg'] = float(jd['elevator_hinge'])
            if 'rudder_hinge' in jd:
                achieved_ctrl['rudder_deg'] = float(jd['rudder_hinge'])
            if 'reverse_bucket_port_hinge' in jd and 'reverse_bucket_stbd_hinge' in jd:
                achieved_ctrl['reverse_bucket'] = 0.5 * (float(jd['reverse_bucket_port_hinge']) + float(jd['reverse_bucket_stbd_hinge'])) / 85.0
            if 'ski_port_incidence' in jd and 'ski_stbd_incidence' in jd:
                qp_s, qs_s = float(jd['ski_port_incidence']), float(jd['ski_stbd_incidence'])
                achieved_ctrl['ski_incidence_deg'] = 0.5 * (qp_s + qs_s)
                achieved_ctrl['ski_differential_deg'] = 0.5 * (qp_s - qs_s)
            if 'ski_aft_incidence' in jd:
                achieved_ctrl['aft_ski_incidence_deg'] = float(jd['ski_aft_incidence'])
            for sp_side, sp_prop in (('sponson_port', 'sponson_port_flex_m'), ('sponson_stbd', 'sponson_stbd_flex_m')):
                if sp_side in poses_af and sp_side in rig_spec['bodies']:
                    base_z = float(rig_spec['bodies'][sp_side]['origin_af'][2])
                    achieved_ctrl[sp_prop] = float(poses_af[sp_side]['p'][2]) - base_z
            for key, val in achieved_ctrl.items():
                if key in ctrl_obj:
                    ctrl_obj[key] = float(val)
                    ctrl_obj.keyframe_insert(data_path=f'["{key}"]', frame=idx)
            fans = fr.get('fans_deg', {})
            for fprop, jkey in (('fan_port_deg', 'fan_rotor_port_hinge'), ('fan_stbd_deg', 'fan_rotor_stbd_hinge')):
                if fprop in ctrl_obj and jkey in fans:
                    ctrl_obj[fprop] = float(fans[jkey])
                    ctrl_obj.keyframe_insert(data_path=f'["{fprop}"]', frame=idx)

        # Verify Blender driver-evaluated world poses against MuJoCo poses_af per frame across ALL bodies
        for fr in frames[::2]:
            idx = int(fr['frame'])
            scene.frame_set(idx)
            bpy.context.view_layer.update()
            af_inv = containers['airframe'].matrix_world.inverted()
            poses_af = fr.get('poses_af', {})
            for bname, mj_pose in poses_af.items():
                if bname not in containers:
                    continue
                rel_mat = af_inv @ containers[bname].matrix_world
                p_bl = rel_mat.to_translation()
                q_bl = rel_mat.to_quaternion()
                p_mj = Vector(mj_pose['p'])
                q_mj = Quaternion(mj_pose['q'])  # w, x, y, z matches mathutils.Quaternion
                pe = float((p_bl - p_mj).length)
                re = _quat_err_deg(q_bl, q_mj)
                if pe > parity['max_pos_err_m']:
                    parity['max_pos_err_m'] = pe
                if re > parity['max_rot_err_deg']:
                    parity['max_rot_err_deg'] = re
                    parity['worst_body'] = bname
                    parity['worst_frame'] = idx
            parity['frames_checked'] += 1
        parity['max_pos_err_m'] = round(parity['max_pos_err_m'], 6)
        parity['max_rot_err_deg'] = round(parity['max_rot_err_deg'], 4)
        scene.frame_set(0)
        return parity

    # Synthetic full-range demo sweep directly from rig_spec limits when sweep.json is omitted
    keyframes = [
        (0, {}),
        (24, {'aileron_deg': 25.0}), (48, {'aileron_deg': -25.0}), (64, {}),
        (88, {'elevator_deg': 20.0}), (112, {'elevator_deg': -20.0}), (128, {}),
        (152, {'rudder_deg': 30.0}), (176, {'rudder_deg': -30.0}), (192, {}),
        (220, {'reverse_bucket': 1.0}), (244, {}),
        (268, {'ski_incidence_deg': 10.0}),
        (292, {'ski_incidence_deg': 8.0, 'ski_differential_deg': 4.0}),
        (316, {'ski_incidence_deg': 8.0, 'ski_differential_deg': -4.0}),
        (340, {}),
    ]
    if 'aft_ski_incidence_deg' in ctrl_obj:
        keyframes.extend([(364, {'aft_ski_incidence_deg': 6.0}), (388, {'aft_ski_incidence_deg': -3.0}), (408, {})])
    keyframes.append((keyframes[-1][0] + 48, {'fan_port_deg': 720.0, 'fan_stbd_deg': 720.0}))
    scene.frame_start = 0
    scene.frame_end = keyframes[-1][0]
    all_keys = [k for k in ctrl_obj.keys() if not k.startswith('_')]
    for fnum, vals in keyframes:
        for k in all_keys:
            ctrl_obj[k] = float(vals.get(k, 0.0))
            ctrl_obj.keyframe_insert(data_path=f'["{k}"]', frame=fnum)
    scene.frame_set(0)
    return parity


def _export_blendstra_articulated_glb(
    out_glb: pathlib.Path,
    containers: dict[str, Any],
    rig_spec: dict[str, Any],
    sweep_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Export a clean Blendstra-ready articulated GLB (physical bodies + meshes + baked quaternion animations)."""
    scene = bpy.context.scene
    # Temporarily bake exact quaternion keyframes onto articulated body empties so glTF 2.0 exports
    # standard TRS rotation animation channels without requiring Blender drivers!
    baked_empties = []
    frame_end = scene.frame_end
    step = 2 if frame_end > 250 else 1
    sampled_frames = list(range(scene.frame_start, frame_end + 1, step))
    if sampled_frames[-1] != frame_end:
        sampled_frames.append(frame_end)

    # Record driver-evaluated local quaternions across frames first
    recorded: dict[str, list[tuple[int, Quaternion]]] = {b: [] for b in containers if b != 'airframe'}
    for fnum in sampled_frames:
        scene.frame_set(fnum)
        bpy.context.view_layer.update()
        for bname in recorded:
            obj = containers[bname]
            if obj.rotation_mode == 'AXIS_ANGLE':
                ang, ax, ay, az = obj.rotation_axis_angle
                q = Quaternion(Vector((ax, ay, az)), float(ang))
            else:
                q = obj.rotation_quaternion.copy()
            recorded[bname].append((fnum, q))

    export_coll = bpy.data.collections.new('_Temp_GLB_Export')
    scene.collection.children.link(export_coll)
    dup_containers: dict[str, Any] = {}
    dup_objs = []

    def _clone_obj(src, parent_dup):
        dst = src.copy()
        if src.data is not None:
            dst.data = src.data
        export_coll.objects.link(dst)
        dst.animation_data_clear()
        dst.parent = parent_dup
        dst.matrix_parent_inverse = src.matrix_parent_inverse.copy()
        dst.location = src.location.copy()
        dst.scale = src.scale.copy()
        if src.rotation_mode == 'AXIS_ANGLE':
            dst.rotation_mode = 'QUATERNION'
            dst.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        else:
            dst.rotation_mode = src.rotation_mode
            dst.rotation_quaternion = src.rotation_quaternion.copy()
            dst.rotation_euler = src.rotation_euler.copy()
        # Preserve exact custom extras for Blendstra
        for k, v in src.items():
            if not k.startswith('_'):
                dst[k] = v
        dup_objs.append(dst)
        return dst

    # Clone hierarchy top-down at exact rest origins: airframe -> child bodies -> child meshes
    scene.frame_set(0)
    bpy.context.view_layer.update()
    dup_af = _clone_obj(containers['airframe'], None)
    dup_af.name = 'airframe'
    dup_containers['airframe'] = dup_af

    for bname, emp in containers.items():
        if bname == 'airframe':
            continue
        p_name = emp.parent.name if emp.parent else 'airframe'
        if p_name not in dup_containers:
            continue
        de = _clone_obj(emp, dup_containers[p_name])
        if bname in rig_spec['bodies']:
            p_af = Vector(rig_spec['bodies'][bname]['origin_af'])
            p_parent = Vector(rig_spec['bodies'][p_name]['origin_af']) if p_name != 'airframe' else Vector((0.0, 0.0, 0.0))
            de.location = p_af - p_parent
        dup_containers[bname] = de
    # Second pass for grand-children (skis under sponsons)
    for bname, emp in containers.items():
        if bname in dup_containers:
            continue
        p_name = emp.parent.name if emp.parent else 'airframe'
        de = _clone_obj(emp, dup_containers[p_name])
        if bname in rig_spec['bodies']:
            p_af = Vector(rig_spec['bodies'][bname]['origin_af'])
            p_parent = Vector(rig_spec['bodies'][p_name]['origin_af']) if p_name != 'airframe' else Vector((0.0, 0.0, 0.0))
            de.location = p_af - p_parent
        dup_containers[bname] = de

    # Clone all meshes parented to containers
    mesh_count = 0
    for bname, emp in containers.items():
        for ch in emp.children:
            if ch.type == 'MESH':
                _clone_obj(ch, dup_containers[bname])
                mesh_count += 1

    # Give exact canonical node names inside export hierarchy (avoid .001 suffixes in GLB!)
    saved_names = []
    for o in list(bpy.data.objects):
        if o not in dup_objs:
            saved_names.append((o, o.name))
            o.name = f'__orig__{o.name}'
    for bname, de in dup_containers.items():
        de.name = bname
    for o in dup_objs:
        if o.type == 'MESH':
            o.name = o.name.split('.')[0]

    # Keyframe recorded quaternion sweep onto duplicate body containers for glTF animation tracks
    q_ident = Quaternion((1.0, 0.0, 0.0, 0.0))
    for bname, pairs in recorded.items():
        de = dup_containers.get(bname)
        if de is None or not pairs:
            continue
        q0 = pairs[0][1]
        if max(_quat_err_deg(q0, q) for _, q in pairs) < 1e-3:
            de.rotation_quaternion = q_ident.copy()
            continue
        prev_q = None
        for fnum, q in pairs:
            q_use = q_ident.copy() if fnum == 0 else q.copy()
            if prev_q is not None and float(prev_q.dot(q_use)) < 0.0:
                q_use = -q_use
            prev_q = q_use
            de.rotation_quaternion = q_use
            de.keyframe_insert(data_path='rotation_quaternion', frame=fnum)
        baked_empties.append(bname)

    scene.frame_set(0)
    for de in dup_containers.values():
        if de.rotation_mode == 'QUATERNION':
            de.rotation_quaternion = q_ident.copy()
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        o.select_set(o in dup_objs)

    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format='GLB',
        use_selection=True,
        export_yup=True,
        export_extras=True,
        export_animations=True,
        export_cameras=False,
        export_lights=False,
    )

    # Clean up temporary export clones and restore exact names on the live .blend scene
    for o in list(dup_objs):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(export_coll)
    for o, orig_name in saved_names:
        o.name = orig_name
    scene.frame_set(0)
    bpy.context.view_layer.update()

    # Read back GLB manifest directly to verify Blendstra extras, materials & animations
    import struct
    raw = out_glb.read_bytes()
    assert raw[:4] == b'glTF', f'Invalid GLB header in {out_glb}'
    jlen = struct.unpack_from('<I', raw, 12)[0]
    manifest = json.loads(raw[20:20 + jlen].decode('utf-8'))
    phys_nodes = [n['name'] for n in manifest.get('nodes', []) if n.get('extras', {}).get('physical_body') == n.get('name')]
    mat_names = [m.get('name', '') for m in manifest.get('materials', [])]
    dup_mats = [mn for mn in mat_names if '.' in mn]
    assert not dup_mats, f'Duplicate .001 materials found in exported GLB: {dup_mats}'
    glass_mats = [m for m in manifest.get('materials', []) if m.get('name') == 'canopy_glass']
    assert len(glass_mats) == 1 and glass_mats[0].get('alphaMode') == 'BLEND', f'Invalid canopy_glass material: {glass_mats}'
    return dict(
        glb_path=str(out_glb),
        size_bytes=len(raw),
        bodies=len(dup_containers),
        meshes=mesh_count,
        animated_bodies=baked_empties,
        gltf_nodes=len(manifest.get('nodes', [])),
        gltf_meshes=len(manifest.get('meshes', [])),
        gltf_materials=mat_names,
        gltf_animations=len(manifest.get('animations', [])),
        verified_physical_body_containers=sorted(phys_nodes),
    )


def _import_cockpit_study(wt: pathlib.Path, study_json: pathlib.Path, mats: dict[int, Any]) -> int:
    """Import available cockpit-study GLBs into excluded/hidden collections so owner can browse."""
    if not study_json.is_file():
        return 0
    mats_by_name = {m.name: m for m in mats.values()}
    data = json.loads(study_json.read_text(encoding='utf-8'))
    root_coll = _ensure_collection('Cockpit_Study_Options')
    loaded = 0
    for rec in data.get('results', []):
        glb_path = wt / rec['glb']
        if not glb_path.is_file():
            alt_path = study_json.parent / pathlib.Path(rec['glb']).name
            if alt_path.is_file():
                glb_path = alt_path
            else:
                continue
        c_coll = _ensure_collection(f"Study_{rec['case']}", parent=root_coll)
        before = set(bpy.data.objects)
        before_mats = set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=str(glb_path))
        for obj in [o for o in bpy.data.objects if o not in before]:
            base = obj.name.split('.')[0]
            if obj.type != 'MESH' or base not in (
                'Ricochet_Canopy_Glass', 'Ricochet_Cockpit_Interior', 'Ricochet_Avionics_Display', 'Study_Pilot_Manikin'
            ):
                bpy.data.objects.remove(obj, do_unlink=True)
                continue
            for slot in obj.material_slots:
                if slot.material is not None:
                    cname = slot.material.name.split('.')[0]
                    if cname in mats_by_name:
                        slot.material = mats_by_name[cname]
            _move_to_collection(obj, c_coll)
        for m_imp in [m for m in list(bpy.data.materials) if m not in before_mats]:
            if m_imp.users == 0:
                bpy.data.materials.remove(m_imp)
        c_coll.hide_viewport = True
        c_coll.hide_render = True
        loaded += 1
    root_coll.hide_viewport = True
    root_coll.hide_render = True
    return loaded


def _setup_lighting_and_render(out_dir: pathlib.Path, do_render: bool) -> None:
    scene = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('RC01_Studio_World')
    if world.node_tree is None:
        world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.86, 0.89, 0.92, 1.0)
    world.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    scene.world = world

    coll_studio = _ensure_collection('Studio_Lights_Cameras')
    for direction, energy, lname in (
        (Vector((0.45, -0.55, 0.90)), 3.2, 'Sun_Key'),
        (Vector((-0.65, 0.70, 0.45)), 1.3, 'Sun_Fill'),
    ):
        ld = bpy.data.lights.new(lname, 'SUN')
        ld.energy = energy
        lo = bpy.data.objects.new(lname, ld)
        lo.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        coll_studio.objects.link(lo)

    views = [
        ('three_quarter_front', Vector((8.2, -7.2, 3.6)), Vector((0.0, 0.0, 0.85)), 42.0),
        ('side_elevation', Vector((0.0, -11.5, 0.95)), Vector((0.0, 0.0, 0.95)), 50.0),
        ('rear_quarter_skis', Vector((-7.5, -6.5, 2.4)), Vector((-0.5, 0.0, 0.70)), 42.0),
    ]
    first_cam = None
    for vname, loc, target, lens in views:
        cd = bpy.data.cameras.new(f'Cam_{vname}')
        cd.lens = lens
        cd.clip_end = 200.0
        co = bpy.data.objects.new(f'Cam_{vname}', cd)
        co.location = loc
        co.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
        coll_studio.objects.link(co)
        if first_cam is None:
            first_cam = co
        if do_render:
            scene.camera = co
            scene.render.resolution_x = 1600
            scene.render.resolution_y = 1000
            scene.render.resolution_percentage = 100
            scene.render.filepath = str(out_dir / f'preview_{vname}.png')
            bpy.ops.render.render(write_still=True)
    if first_cam is not None:
        scene.camera = first_cam


def _write_readme_text(rig_spec: dict[str, Any], parity: dict[str, Any], glb_info: dict[str, Any]) -> None:
    txt = bpy.data.texts.new('README_RC01_COMPLETE_MODEL')
    lines = [
        'VTX RICOCHET RC-01 — COMPLETE ARTICULATED MODEL & BLENDSTRA RIG',
        f"Profile: {rig_spec['profile']}",
        f"Rudder hinge cove cleared: {rig_spec.get('rudder_cove_clear', True)}",
        '',
        'COORDINATE FRAME:',
        '  Blender world = VTX airframe frame (+X forward, +Y port, +Z up), metres.',
        '  Exported GLB uses standard glTF Y-up (+X fwd, +Y up, -Z port) with exact physical_body extras.',
        '',
        'INTERACTIVE CONTROLS (select object RC01_Controls -> Object Properties -> Custom Properties):',
    ]
    for ch, lim in rig_spec.get('channel_limits', {}).items():
        lines.append(f"  - {ch}: [{lim.get('min')}, {lim.get('max')}]")
    lines.extend([
        '',
        'BLENDER-VS-MUJOCO POSE PARITY:',
        json.dumps(parity, indent=2),
        '',
        'BLENDSTRA GLB EXPORT:',
        json.dumps(glb_info, indent=2),
    ])
    txt.write('\n'.join(lines))


def main() -> None:
    args = _parse_args()
    wt = pathlib.Path(args.worktree).resolve()
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.rig_spec and pathlib.Path(args.rig_spec).is_file():
        rig_spec = json.loads(pathlib.Path(args.rig_spec).read_text(encoding='utf-8'))
    else:
        rig_spec = _derive_rig_spec_from_profile(wt, args.profile)

    sweep_data = None
    if args.sweep and pathlib.Path(args.sweep).is_file():
        sweep_data = json.loads(pathlib.Path(args.sweep).read_text(encoding='utf-8'))

    _clear_scene()
    mats = _build_pbr_materials()
    coll_main = _ensure_collection('RC01_Airframe_Articulated')
    coll_act = _ensure_collection('RC01_Controls_And_Actuators')

    containers, ctrl_obj = _build_airframe_and_rig(
        wt, rig_spec, mats, coll_main, coll_act, args.alt_profile,
    )
    parity = _bake_sweep_and_check_parity(containers, ctrl_obj, rig_spec, sweep_data)
    glb_info = _export_blendstra_articulated_glb(out / args.glb_name, containers, rig_spec, sweep_data)

    study_loaded = 0
    if args.cockpit_study:
        study_loaded = _import_cockpit_study(wt, pathlib.Path(args.cockpit_study), mats)

    _setup_lighting_and_render(out, args.render)
    _write_readme_text(rig_spec, parity, glb_info)

    blend_path = out / args.blend_name
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    report = dict(
        profile=rig_spec['profile'],
        blend_path=str(blend_path),
        glb=glb_info,
        pose_parity=parity,
        cockpit_study_cases_loaded=study_loaded,
        rendered_previews=bool(args.render),
    )
    (out / 'build_complete_model_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
