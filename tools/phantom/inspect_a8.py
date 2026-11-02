"""Read-only inventory of the pinned Phantom A8 source (run with Blender -b --disable-autoexec).

Usage:
  blender -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend \
      --python tools/phantom/inspect_a8.py -- evidence/phantom/a8_inventory.json

Records every object's hierarchy, world bounds (evaluated mesh), materials, custom
properties, constraints and animation, plus the scene frame range and text blocks.
The source file is never saved.
"""
import bpy
import json
import sys
from pathlib import Path

out = Path(sys.argv[sys.argv.index('--') + 1])
out.parent.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene


def safe(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if hasattr(v, 'to_list'):
        return v.to_list()
    try:
        return [safe(x) for x in v]
    except TypeError:
        return str(v)


def world_bounds(o, depsgraph):
    if o.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
        return None
    ev = o.evaluated_get(depsgraph)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None
    if me is None or not len(me.vertices):
        ev.to_mesh_clear()
        return None
    mw = ev.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    nverts, nfaces = len(me.vertices), len(me.polygons)
    ev.to_mesh_clear()
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return dict(min=lo, max=hi, vertices=nverts, faces=nfaces)


def anim(o):
    ad = o.animation_data
    if not ad or not ad.action:
        return None
    act = ad.action
    curves = []
    # Blender 5 layered actions expose channelbags; fall back to legacy fcurves.
    fcs = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    fcs.extend(bag.fcurves)
    except AttributeError:
        fcs = list(getattr(act, 'fcurves', []))
    for fc in fcs:
        keys = [(k.co[0], k.co[1]) for k in fc.keyframe_points]
        curves.append(dict(path=fc.data_path, index=fc.array_index,
                           frames=[keys[0][0], keys[-1][0]] if keys else None,
                           values=[min(k[1] for k in keys), max(k[1] for k in keys)] if keys else None,
                           nkeys=len(keys)))
    return dict(action=act.name, curves=curves)


scene.frame_set(scene.frame_start)
dg = bpy.context.evaluated_depsgraph_get()
objects = []
for o in bpy.data.objects:
    objects.append(dict(
        name=o.name, type=o.type,
        parent=o.parent.name if o.parent else None,
        parent_type=o.parent_type if o.parent else None,
        collections=[c.name for c in o.users_collection],
        hide_render=o.hide_render, hide_viewport=o.hide_viewport,
        location=list(o.matrix_world.translation),
        matrix_world=[list(r) for r in o.matrix_world],
        rotation_mode=o.rotation_mode,
        local_location=list(o.location), local_rotation_euler=list(o.rotation_euler),
        bounds=world_bounds(o, dg),
        materials=[s.material.name for s in o.material_slots if s.material],
        props={k: safe(v) for k, v in o.items()},
        constraints=[dict(type=c.type, name=c.name, target=getattr(getattr(c, 'target', None), 'name', None))
                     for c in o.constraints],
        modifiers=[dict(type=m.type, name=m.name) for m in o.modifiers],
        animation=anim(o),
    ))

result = dict(
    blender=bpy.app.version_string,
    file=bpy.data.filepath,
    unit_system=scene.unit_settings.system, unit_scale=scene.unit_settings.scale_length,
    frame_range=[scene.frame_start, scene.frame_end], fps=scene.render.fps,
    markers=[(m.name, m.frame) for m in scene.timeline_markers],
    collections=[dict(name=c.name, objects=len(c.objects), children=[x.name for x in c.children])
                 for c in bpy.data.collections],
    texts={t.name: t.as_string() for t in bpy.data.texts},
    scene_props={k: safe(v) for k, v in scene.items()},
    objects=objects,
)
out.write_text(json.dumps(result, indent=1))
print('A8_INVENTORY', len(objects), 'objects; frames', result['frame_range'], 'texts', list(result['texts']))
