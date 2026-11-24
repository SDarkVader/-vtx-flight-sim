"""Blender (headless): tile PNGs into one contact sheet, in name order.

blender -b --factory-startup --python blender_contact_sheet.py -- <out.png> <cols> <tile_w> <tile_h> <png> [<png> ...]
"""
import bpy, sys

out, cols, tw, th, *files = sys.argv[sys.argv.index('--') + 1:]
cols, tw, th = int(cols), int(tw), int(th)
rows = (len(files) + cols - 1) // cols
W, H = cols * tw, rows * th
sheet = [1.0] * (W * H * 4)
for k, f in enumerate(files):
    img = bpy.data.images.load(f)
    img.scale(tw, th)
    px = list(img.pixels)
    c, r = k % cols, rows - 1 - k // cols  # Blender pixels start bottom-left
    for y in range(th):
        src = y * tw * 4
        dst = ((r * th + y) * W + c * tw) * 4
        sheet[dst:dst + tw * 4] = px[src:src + tw * 4]
    # 3 px dark border between tiles
    for y in range(th):
        for x in list(range(3)) + list(range(tw - 3, tw)):
            i = ((r * th + y) * W + c * tw + x) * 4
            sheet[i:i + 3] = [0.15, 0.15, 0.15]
    for x in range(tw):
        for y in list(range(3)) + list(range(th - 3, th)):
            i = ((r * th + y) * W + c * tw + x) * 4
            sheet[i:i + 3] = [0.15, 0.15, 0.15]
im = bpy.data.images.new('sheet', W, H, alpha=True)
im.pixels = sheet
im.filepath_raw = out
im.file_format = 'PNG'
im.save()
print('SHEET', out, W, H)
