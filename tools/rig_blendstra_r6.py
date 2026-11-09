"""Create the live R6 visual rig from the explicitly supplied Blendstra GLB.

Run with Blender: blender -b --python tools/rig_blendstra_r6.py
The existing simulator GLB supplies physical body assignments and pivots by
stable part ID. The supplied GLB supplies every displayed mesh and material.
No physics ledger or original asset is modified.
"""
import bpy
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'public/assets/airframe-r6.glb'
SOURCE = ROOT / 'assets/reference/r6-blendstra-reference.glb'
OUTPUT = ROOT / 'public/assets/airframe-r6-blendstra-rig.glb'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(OLD))
bpy.context.view_layer.update()
groups = {o.name:o.matrix_world.copy() for o in bpy.data.objects
          if o.type == 'EMPTY' and o.get('physical_body') == o.name}
parts = {}
for obj in bpy.data.objects:
    if obj.type != 'MESH' or not obj.get('blendstra_id'):
        continue
    axis = obj.get('pitch_axis')
    parts[obj['blendstra_id']] = (obj.get('physical_body'), list(axis) if axis else None)
expected_groups = {'airframe','cabin'} | {f'{name}{i}' for name,count in [('rotor',4),('nacelle',4),('shaft',4),('gear',6)] for i in range(1,count+1)}
assert set(groups) == expected_groups, sorted(set(groups) ^ expected_groups)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
bpy.context.view_layer.update()
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(meshes) == 691, len(meshes)
source_empties = [o for o in bpy.context.scene.objects if o.type != 'MESH']
containers = {}
for name, matrix in groups.items():
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = matrix
    obj['physical_body'] = name
    containers[name] = obj
bpy.context.view_layer.update()
matched = 0
extras = []
for obj in meshes:
    part_id = obj.get('blendstra_id')
    if part_id in parts:
        body, axis = parts[part_id]
        matched += 1
    else:
        accessory = re.fullmatch(r'Phase2_Duct_(?:Lip_Glow|Livery_Band)_F([1-4])', obj.name)
        if accessory:
            body = 'nacelle' + accessory.group(1)
        elif re.fullmatch(r'P06 \| F[1-4] (?:longitudinal web(?:\.001)?|ring join|rotor attach)', obj.name):
            body = 'airframe'
        else:
            raise RuntimeError('Unmapped source mesh: ' + obj.name)
        axis = None
        extras.append(obj.name)
    if body not in containers:
        raise RuntimeError('Unknown simulator body for ' + obj.name + ': ' + str(body))
    world_matrix = obj.matrix_world.copy()
    obj.parent = containers[body]
    obj.matrix_world = world_matrix
    obj['physical_body'] = body
    if axis is not None:
        obj['pitch_axis'] = axis
for obj in source_empties:
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.context.view_layer.update()
assert matched == 667 and len(extras) == 24, (matched, extras)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB',
                          export_animations=False, export_yup=True, export_extras=True,
                          export_cameras=False, export_lights=False, use_active_scene=True)
print('R6_RIG_RESULT',len(meshes),'meshes',matched,'mapped parts',len(extras),'source-only parts')
