"""Blender (headless): render close-ups of connectivity-audit findings on the R6 GLB.

blender -b --factory-startup --python blender_findings_r6.py -- <r6.glb> <poses.json> <findings.json> <out_dir>
findings.json: [{"id", "title", "pose", "red": [part names], "amber": [part names],
                 "centre": [x,y,z] (optional), "view": [dx,dy,dz], "scale": m, "crop": m}]
Red = the defective part, amber = the part it should meet, grey = everything else within `crop` of the focus.
Body containers are posed from physics exactly as the cockpit does; parts are never edited.
"""
import bpy, json, math, os, sys, mathutils

glb, poses_path, findings_path, out_dir = sys.argv[sys.argv.index('--') + 1:][:4]
P = json.load(open(poses_path))
FINDINGS = json.load(open(findings_path))
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
meshes = [o for o in sc.objects if o.type == 'MESH']
by_name = {}
for o in meshes:
    by_name.setdefault(o.get('vtx_name', o.name), o)
    by_name.setdefault(o.name, o)


def sim(p):
    w, x, y, z = p['quat_wxyz']
    return mathutils.Matrix.Translation(p['pos']) @ mathutils.Quaternion((w, x, y, z)).to_matrix().to_4x4()


def _centre(o):
    pts = [c.matrix_world @ mathutils.Vector(v) for c in o.children_recursive if c.type == 'MESH' for v in c.bound_box]
    return sum(pts, mathutils.Vector()) / len(pts)


# Containers with a vtx_spin_centre (shafts) turn about their drawn centreline, as the cockpit does (app.js).
spin_centre_rest = {n: _centre(o) for n, o in bodies.items() if 'vtx_spin_centre' in o.keys()}


def apply(label):
    for n, o in bodies.items():
        if n in P[label]:
            o.matrix_world = sim(P[label][n]) @ sim(P['rest'][n]).inverted() @ rest_world[n]
    bpy.context.view_layer.update()
    af = bodies['airframe'].matrix_world @ rest_world['airframe'].inverted()
    for n, c_rest in spin_centre_rest.items():
        o = bodies[n]
        q = rest_world[n].inverted() @ c_rest
        o.matrix_world = mathutils.Matrix.Translation(af @ c_rest - o.matrix_world @ q) @ o.matrix_world
    bpy.context.view_layer.update()


# With the SIM_FRAME parent, Blender world coordinates are simulator coordinates (z up).
S2B = mathutils.Matrix.Identity(3)


def bbox_sim(o):
    inv = S2B.inverted()
    pts = [inv @ (o.matrix_world @ mathutils.Vector(c)) for c in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light, sh.color_type, sh.show_cavity, sh.show_object_outline = 'STUDIO', 'OBJECT', True, True
sh.show_shadows = False
sc.render.resolution_x, sc.render.resolution_y = 1000, 800
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = 'ORTHO'
cam.data.clip_start, cam.data.clip_end = 0.001, 100
os.makedirs(out_dir, exist_ok=True)
missing = []
for f in FINDINGS:
    apply(f['pose'])
    red = [by_name[n] for n in f.get('red', []) if n in by_name]
    amber = [by_name[n] for n in f.get('amber', []) if n in by_name]
    missing += [n for n in f.get('red', []) + f.get('amber', []) if n not in by_name]
    focus = red or amber
    lo = [min(bbox_sim(o)[0][i] for o in focus) for i in range(3)]
    hi = [max(bbox_sim(o)[1][i] for o in focus) for i in range(3)]
    centre = mathutils.Vector(f.get('centre') or [(a + b) / 2 for a, b in zip(lo, hi)])
    crop = f.get('crop', 0.6)
    for o in meshes:
        a, b = bbox_sim(o)
        near = all(a[i] <= centre[i] + crop and b[i] >= centre[i] - crop for i in range(3))
        o.hide_render = not (near or o in red or o in amber)
        o.color = (0.85, 0.08, 0.08, 1) if o in red else (1.0, 0.62, 0.05, 1) if o in amber else (0.62, 0.64, 0.66, 1)
    view = mathutils.Vector(f.get('view', [0, -1, 0.35])).normalized()
    c_b = S2B @ centre
    cam.location = c_b + (S2B @ view) * 20
    cam.rotation_euler = (c_b - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = f.get('scale', 1.0)
    # optional cutaway: clip everything nearer the camera than `clip` metres in front of the focus point
    cam.data.clip_start = 20 - f['clip'] if 'clip' in f else 0.001
    sc.render.filepath = os.path.join(out_dir, f"{f['id']}.png")
    bpy.ops.render.render(write_still=True)
print('MISSING_NAMES', sorted(set(missing)))
