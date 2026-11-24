"""Blender (headless): pose the R6 GLB with physics body poses and render/save each pose.

blender -b --factory-startup --python blender_pose_r6.py -- <r6.glb> <poses.json> <out_dir> [save_blend_pose]
Parts, meshes and origins are never edited; only the 20 body containers are moved, exactly as the cockpit does.
"""
import bpy, json, math, os, sys, mathutils

glb, poses_path, out_dir, *rest = sys.argv[sys.argv.index('--') + 1:]
save_pose = rest[0] if rest else None
P = json.load(open(poses_path))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
roots = [o for o in sc.objects if o.parent is None]
frame = bpy.data.objects.new('SIM_FRAME_MuJoCo_ZUp', None)
sc.collection.objects.link(frame)
frame.rotation_euler = (-math.pi / 2, 0, 0)
for o in roots:
    o.parent = frame
bpy.context.view_layer.update()
bodies = {o.name: o for o in roots}
rest_world = {n: o.matrix_world.copy() for n, o in bodies.items()}


def sim(p):
    w, x, y, z = p['quat_wxyz']
    return mathutils.Matrix.Translation(p['pos']) @ mathutils.Quaternion((w, x, y, z)).to_matrix().to_4x4()


# Rest check: imported containers must already sit at the physics rest frames.
worst = max((rest_world[n].translation - sim(P['rest'][n]).translation).length for n in bodies if n in P['rest'])


def apply(label):
    for n, o in bodies.items():
        if n in P[label]:
            o.matrix_world = sim(P[label][n]) @ sim(P['rest'][n]).inverted() @ rest_world[n]
    bpy.context.view_layer.update()


sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light, sh.color_type, sh.show_cavity, sh.show_object_outline = 'STUDIO', 'MATERIAL', True, True
sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = 'ORTHO'


def shot(name, pos, target, scale):
    cam.location = mathutils.Vector(pos)
    cam.rotation_euler = (mathutils.Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = scale
    sc.render.filepath = os.path.join(out_dir, name + '.png')
    bpy.ops.render.render(write_still=True)


os.makedirs(out_dir, exist_ok=True)
for label in ('rest', 'tilt_x', 'tilt_y', 'tilt_diag'):
    apply(label)
    shot(f'{label}_side', (0, -14, 1.2), (0, 0, 1.2), 8.5)
    shot(f'{label}_duct1_close', (2.6, -6, 1.6), (2.6, 0, 1.4), 3.2)
    shot(f'{label}_iso', (9, -9, 6.5), (0, 0, 1.2), 8.5)
if save_pose:
    apply(save_pose)
    sc['vtx_pose'] = save_pose
    sc['vtx_note'] = 'Body containers posed from the physics model (r6_pose_export.py). Parts untouched.'
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f'airframe-r6-a2b-{save_pose}.blend'), compress=False)
print('REST_WORST_M', worst)
