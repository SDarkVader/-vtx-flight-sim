"""Motion demonstration and stills of the A9 revision (Workbench, material colours).

Usage:
  blender -b --disable-autoexec assets/derived/phantom-a9-cassette.blend \
      --python tools/phantom/render_motion.py -- <out_dir> [--video] [--step N]

Stills: 3/4 rear views at road (frame 1), hatch open (108), half-deployed (168), locked (240),
control demo (262, 286), plus a slot close-up and a canard close-up. Video: frames 1..END at the
given step, H.264 MP4. Visualisation only: no physics or aerodynamics.
"""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0]).resolve()
out.mkdir(parents=True, exist_ok=True)
video = '--video' in argv
step = int(argv[argv.index('--step') + 1]) if '--step' in argv else 1
SC = bpy.context.scene

SC.render.engine = 'BLENDER_WORKBENCH'
sh = SC.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_xray = False
sh.show_shadows = True
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_object_outline = True
sh.object_outline_color = (0.05, 0.05, 0.05)
if SC.world is None:
    SC.world = bpy.data.worlds.new('A9_WORLD')
SC.world.color = (0.82, 0.83, 0.85)
SC.render.film_transparent = False
for ob in SC.objects:
    if ob.type == 'EMPTY':
        ob.hide_render = True

cam_data = bpy.data.cameras.new('A9_CAM')
cam = bpy.data.objects.new('A9_CAM', cam_data)
SC.collection.objects.link(cam)
SC.camera = cam


def aim(loc, target, lens=35):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = lens


def still(name, frame, loc, target, lens=35, res=(1600, 900)):
    SC.frame_set(frame + 1)   # same-frame set after load can leave nested-child matrices stale
    SC.frame_set(frame)
    aim(loc, target, lens)
    SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.image_settings.file_format = 'PNG'
    SC.render.filepath = str(out / f'{name}.png')
    bpy.ops.render.render(write_still=True)


rear34 = ((-6.2, 4.6, 3.4), (-0.6, 0.2, 0.7))
still('a9_road_f001', 1, *rear34)
still('a9_hatch_open_f108', 108, *rear34)
still('a9_sliding_f168', 168, *rear34)
still('a9_locked_f240', 240, *rear34)
still('a9_flaps_ailerons_f262', 262, *rear34)
still('a9_ailerons_reverse_f286', 286, *rear34)
still('a9_front34_locked_f240', 240, (5.6, 4.4, 2.6), (0.2, 0.3, 0.7))
still('a9_slot_closeup_f108', 108, (-1.05, 3.4, 1.35), (-1.05, 1.2, 0.95), lens=50)
still('a9_slot_closeup_f240', 240, (-1.05, 3.4, 1.35), (-1.05, 1.2, 0.95), lens=50)
still('a9_canard_closeup_f001', 1, (2.9, 2.6, 1.6), (1.7, 1.1, 0.9), lens=45)
still('a9_canard_closeup_f264', 264, (2.9, 2.6, 1.6), (1.7, 1.1, 0.9), lens=45)

if video:
    SC.render.resolution_x, SC.render.resolution_y = 1280, 720
    aim(*rear34)
    SC.frame_step = step
    try:
        SC.render.image_settings.media_type = 'VIDEO'
    except (AttributeError, TypeError):
        pass
    SC.render.image_settings.file_format = 'FFMPEG'
    SC.render.ffmpeg.format = 'MPEG4'
    SC.render.ffmpeg.codec = 'H264'
    SC.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    SC.render.fps = max(1, 24 // step)
    SC.render.filepath = str(out / 'a9_wing_cassette_motion_')
    bpy.ops.render.render(animation=True)
print('RENDERED_MOTION', out)
