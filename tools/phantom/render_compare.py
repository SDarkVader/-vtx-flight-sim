"""Comparison stills (Workbench, material colours) for A9 vs A10: deployed (240) and stowed (1), front and rear.

Usage:
  blender -b --disable-autoexec <file.blend> --python tools/phantom/render_compare.py -- <out_dir> <prefix>
Writes <prefix>_{rear34,front34,ortho_front,ortho_rear}_{deployed_f240,stowed_f001}.png. The .blend is never saved.
Visualisation only.
"""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0]).resolve()
out.mkdir(parents=True, exist_ok=True)
prefix = argv[1]
SC = bpy.context.scene
SC.render.engine = 'BLENDER_WORKBENCH'
sh = SC.display.shading
sh.light, sh.color_type = 'STUDIO', 'MATERIAL'
sh.show_shadows = sh.show_cavity = sh.show_object_outline = True
sh.cavity_type = 'BOTH'
if SC.world is None:
    SC.world = bpy.data.worlds.new('CMP_WORLD')
SC.world.color = (0.82, 0.83, 0.85)
for ob in SC.objects:
    if ob.type == 'EMPTY':
        ob.hide_render = True
cd = bpy.data.cameras.new('CMP_CAM')
cam = bpy.data.objects.new('CMP_CAM', cd)
SC.collection.objects.link(cam)
SC.camera = cam
SC.render.resolution_x, SC.render.resolution_y = 1600, 900

VIEWS = {
    'rear34': dict(loc=(-6.2, 4.6, 3.4), tgt=(-0.6, 0.2, 0.7), lens=35),
    'front34': dict(loc=(5.6, 4.4, 2.6), tgt=(0.2, 0.3, 0.7), lens=35),
    'ortho_front': dict(loc=(10.0, 0.0, 0.95), tgt=(0.0, 0.0, 0.95), ortho=5.6),
    'ortho_rear': dict(loc=(-10.0, 0.0, 0.95), tgt=(0.0, 0.0, 0.95), ortho=5.6),
}
for frame, tag in ((240, 'deployed_f240'), (1, 'stowed_f001')):
    SC.frame_set(frame + 1)
    SC.frame_set(frame)
    for name, v in VIEWS.items():
        cam.location = Vector(v['loc'])
        cam.rotation_euler = (Vector(v['tgt']) - Vector(v['loc'])).to_track_quat('-Z', 'Y').to_euler()
        if 'ortho' in v:
            cd.type, cd.ortho_scale = 'ORTHO', v['ortho']
        else:
            cd.type, cd.lens = 'PERSP', v['lens']
        SC.render.filepath = str(out / f'{prefix}_{name}_{tag}.png')
        bpy.ops.render.render(write_still=True)
print('RENDERED_COMPARE', prefix, out)
