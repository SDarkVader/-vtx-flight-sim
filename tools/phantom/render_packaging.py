"""Orthographic packaging renders of the A8 with an optional, unsaved candidate-cassette overlay.

Usage:
  blender -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend \
      --python tools/phantom/render_packaging.py -- <out_dir> <frame> [--overlay T]

Renders top, left-side and rear orthographic views (Workbench, flat colours by role).
Overlay "T" adds translucent boxes for the telescopic sleeve bay and the candidate deployed
wing planform, using the geometry declared in engineering/phantom/wing_loads.py. The .blend is
never saved. Pictures are packaging aids only.
"""
import bpy
import sys
import math
from pathlib import Path

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0]).resolve(); out.mkdir(parents=True, exist_ok=True)
frame = int(argv[1])
overlay = argv[3] if len(argv) > 3 and argv[2] == '--overlay' else None
sc = bpy.context.scene
sc.frame_set(frame)

ROLE = [  # substring -> RGBA
    ('WING_AERODYNAMIC', (1.0, 0.55, 0.0, 1)), ('CANARD_STOWED', (1.0, 0.55, 0.0, 1)),
    ('TYRE', (0.15, 0.15, 0.15, 1)), ('SEAT', (0.2, 0.5, 0.9, 1)), ('TUB_', (0.3, 0.7, 0.3, 1)),
    ('MOUNT_001', (0.9, 0.1, 0.1, 1)), ('SIDEGLASS', (0.4, 0.8, 0.9, 1)), ('DUCT_ENGINE', (0.7, 0.2, 0.8, 1)),
    ('V_TAIL', (0.5, 0.5, 0.5, 1)), ('DORSAL', (0.55, 0.55, 0.55, 1)), ('HULL', (0.82, 0.82, 0.82, 1)),
]
for o in sc.objects:
    col = next((c for k, c in ROLE if k in o.name), (0.65, 0.65, 0.65, 1))
    o.color = col

if overlay == 'T':
    def box(name, lo, hi, rgba):
        bpy.ops.mesh.primitive_cube_add(size=1, location=[(a + b) / 2 for a, b in zip(lo, hi)])
        ob = bpy.context.object
        ob.name = name
        ob.scale = [b - a for a, b in zip(lo, hi)]
        ob.color = rgba
        return ob

    def plate(name, pts, z0, z1, rgba):
        me = bpy.data.meshes.new(name)
        n = len(pts)
        verts = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
        faces = [list(range(n))[::-1], [i + n for i in range(n)]] + [[i, (i + 1) % n, (i + 1) % n + n, i + n] for i in range(n)]
        me.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)
        ob.color = rgba
        return ob

    # sleeve bay (two stacked cells) across the body, x -0.63..-1.48, z 0.82..1.06, |y|<=1.12
    box('OVL_SLEEVE_LOWER', (-1.48, -1.12, 0.82), (-0.63, 1.12, 0.94), (0.9, 0.1, 0.6, 1))
    box('OVL_SLEEVE_UPPER', (-1.48, -1.12, 0.94), (-0.63, 1.12, 1.06), (0.6, 0.1, 0.9, 1))
    # deployed T wings (right upper, left lower), planform from wing_loads.py
    for s, z0 in ((1, 0.958), (-1, 0.838)):
        pts = [(-0.66, s * 1.12), (-1.14, s * 2.47), (-1.46, s * 2.47), (-1.46, s * 1.12)]
        if s < 0:
            pts = pts[::-1]
        plate('OVL_WING_T_%s' % ('R' if s > 0 else 'L'), pts, z0, z0 + 0.088, (0.1, 0.8, 0.2, 1))

sh = sc.display.shading
sc.render.engine = 'BLENDER_WORKBENCH'
sh.light = 'FLAT'
sh.color_type = 'OBJECT'
sh.show_xray = True
sh.xray_alpha = 0.55
sc.display.shading.show_object_outline = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.render.film_transparent = False
if sc.world is None:
    sc.world = bpy.data.worlds.new('PKG_WORLD')
sc.world.color = (1, 1, 1)

cam_data = bpy.data.cameras.new('PKG_CAM')
cam_data.type = 'ORTHO'
cam = bpy.data.objects.new('PKG_CAM', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
views = {
    'top': ((-0.3, 0.0, 10.0), (0, 0, -math.pi / 2), 7.2),
    'left': ((-0.3, -10.0, 0.7), (math.pi / 2, 0, 0), 6.2),
    'rear': ((-10.0, 0.0, 0.7), (math.pi / 2, 0, -math.pi / 2), 7.2),
}
for name, (loc, rot, scale) in views.items():
    cam.location = loc
    cam.rotation_euler = rot
    cam_data.ortho_scale = scale
    sc.render.filepath = str(out / f'f{frame:03d}_{overlay or "A8"}_{name}.png')
    bpy.ops.render.render(write_still=True)
print('RENDERED', out)
