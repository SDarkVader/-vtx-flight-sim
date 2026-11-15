"""Build an explicitly schematic A10-C front suspension overlay.

Run with Blender from any directory:
  blender --background --python tools/phantom/build_suspension_schematic.py

The cyan datum/guide and orange carrier depict the model's measured suspension
slide. Their dimensions are chosen for legibility; they are not actuator CAD,
hardpoints, collision shapes, spring-seat travel or a proposed structural design.
No original B visual or earlier provisional C parts are opened or overwritten.
"""
from pathlib import Path
import hashlib
import json
import math

import bpy
from mathutils import Vector


REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / 'assets/derived/phantom-a10c-suspension-schematic.blend'
GLB = REPO / 'public/assets/phantom-a10c-suspension-schematic.glb'
PREVIEW = REPO / 'assets/derived/phantom-a10c-suspension-schematic.png'
ROOT_NAME = 'VTX_A10C_SUSPENSION_SCHEMATIC'
SOURCE_MODEL = '1e04c9e9f82fe55fe6aae60ce3aaf15520c0ea593ea4658389259ac86a0e8d39'


def material(name, rgb):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*rgb, 1)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*rgb, 1)
    shader.inputs['Roughness'].default_value = .4
    shader.inputs['Emission Color'].default_value = (*rgb, 1)
    shader.inputs['Emission Strength'].default_value = .3
    return result


def empty(name, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .05
    obj.parent = parent
    obj.location = location
    return obj


def box(name, parent, location, dimensions, surface):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = location
    obj.dimensions = dimensions
    obj.data.materials.append(surface)
    return obj


def ring(name, parent, location, radius, surface):
    bpy.ops.mesh.primitive_torus_add(major_segments=32, minor_segments=8,
                                   major_radius=radius, minor_radius=.005)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = location
    obj.rotation_euler.x = math.pi / 2
    obj.data.materials.append(surface)
    return obj


bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
cyan = material('SCHEMATIC_Cyan_Datum', (.025, .72, .92))
orange = material('SCHEMATIC_Orange_Measured_Carrier', (1.0, .24, .025))
root = empty(ROOT_NAME)
root['schematic'] = True
root['representation'] = 'model suspension slide'
root['units'] = 'm'
root['visual_only'] = True
root['collision_geometry'] = False
root['source_model_xml_sha256'] = SOURCE_MODEL
root['coordinate_system'] = '+X forward, physical FL +Y, +Z up'
root['dimension_basis'] = 'Datum origins from recorded model; all guide/carrier sizes are cosmetic'
root['not_represented'] = 'structural actuator, hardpoints, spring-seat motion, force or clearance envelope'

for side, sign in [('FL', 1), ('FR', -1)]:
    prefix = f'VTX_SCHEMATIC_{side}'
    pod = empty(prefix + '_POD', root, (1.54, sign * 1.25, .61))
    pod['schematic'] = True
    pod['representation'] = 'model suspension slide'
    pod['source_body'] = 'pod_' + side
    pod['source_joint'] = f'pod_{side}_susp'
    pod['units'] = 'm'
    pod['q_rest'] = 0.0
    pod['axis_parent'] = [0.0, 0.0, 1.0]
    pod['runtime_parent'] = 'measured physical pod transform'
    pod['nominal_airframe_origin_m'] = [1.54, sign * 1.25, .61]
    pod['cosmetic_display_offset_m'] = [0.0, sign * .115, 0.0]
    display_y = sign * .115
    box(prefix + '_GUIDE', pod, (.12, display_y, -.11), (.012, .012, .50), cyan)
    ring(prefix + '_DATUM', pod, (0, display_y, 0), .075, cyan)
    box(prefix + '_DATUM_CROSS', pod, (.06, display_y, 0), (.12, .012, .012), cyan)
    for index, z in enumerate([-.3, -.2, -.1, 0, .1]):
        box(prefix + f'_TICK_{index}', pod, (.13, display_y, z), (.045, .010, .006), cyan)
    carrier = empty(prefix + '_CARRIER', pod)
    carrier['schematic'] = True
    carrier['representation'] = 'model suspension slide'
    carrier['source_joint'] = f'pod_{side}_susp'
    carrier['units'] = 'm'
    carrier['q_rest'] = 0.0
    carrier['axis_parent'] = [0.0, 0.0, 1.0]
    carrier['binding'] = 'local z = measured suspension; never nose_lift_m'
    ring(prefix + '_CARRIER_MARK', carrier, (0, display_y + sign * .012, 0), .055, orange)
    box(prefix + '_CARRIER_CROSS', carrier, (.06, display_y + sign * .012, 0),
        (.12, .014, .014), orange)
    box(prefix + '_CARRIER_SLIDER', carrier, (.12, display_y + sign * .012, 0),
        (.035, .025, .035), orange)
    connector = empty(prefix + '_CONNECTOR', pod, (.12, display_y + sign * .012, 0))
    connector['schematic'] = True
    connector['representation'] = 'displacement indicator, not structural linkage'
    connector['units'] = 'm'
    connector['binding'] = 'z=min(0,measured slide); scale.z=abs(measured slide); hidden at zero'
    # Unit-length indicator makes the runtime endpoint contract explicit.
    box(prefix + '_CONNECTOR_LINE', connector, (0, 0, .5), (.006, .006, 1.0), orange)
    connector.scale.z = 0.0
    connector.hide_render = True

# GLB contains only the diagram; the editable master additionally retains a
# reproducible inspection camera and lights. No physics or original mesh data.
bpy.ops.object.select_all(action='DESELECT')
for obj in root.children_recursive:
    obj.select_set(True)
root.select_set(True)
GLB.parent.mkdir(parents=True, exist_ok=True)
MASTER.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(GLB), export_format='GLB', export_yup=False,
                          export_extras=True, use_selection=True, export_cameras=False,
                          export_lights=False)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1200
scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.world.color = (.025, .035, .05)
scene.view_settings.view_transform = 'AgX'
for name, location, energy in [('SCHEMATIC_Key', (3, 2, 4), 500),
                               ('SCHEMATIC_Fill', (1, -3, 2), 300)]:
    light_data = bpy.data.lights.new(name, 'AREA')
    light_data.energy = energy
    light_data.shape = 'DISK'
    light_data.size = 3
    light = bpy.data.objects.new(name, light_data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (Vector((1.54, 0, .5)) - light.location).to_track_quat('-Z', 'Y').to_euler()
camera_data = bpy.data.cameras.new('SCHEMATIC_Inspection_Camera')
camera = bpy.data.objects.new('SCHEMATIC_Inspection_Camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (4.5, -4.8, 2.5)
camera.rotation_euler = (Vector((1.54, 0, .5)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 3.6
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
# The standalone preview illustrates a selected -0.20 m slide. It is not a
# recorded flight state, and it is not saved as the source asset's rest pose.
for side in ('FL', 'FR'):
    bpy.data.objects[f'VTX_SCHEMATIC_{side}_CARRIER'].location.z = -.20
    indicator = bpy.data.objects[f'VTX_SCHEMATIC_{side}_CONNECTOR']
    indicator.location.z = -.20
    indicator.scale.z = .20
    indicator.hide_render = False
scene.render.filepath = str(PREVIEW)
bpy.ops.render.render(write_still=True)
print(json.dumps({'glb': str(GLB), 'sha256': hashlib.sha256(GLB.read_bytes()).hexdigest(),
                  'master': str(MASTER), 'preview': str(PREVIEW),
                  'note': 'Schematic only; runtime measured-state binding and cockpit verification required'}))
