"""Vertical ray-cast packaging map of a Phantom .blend (Blender -b --disable-autoexec).

Usage:
  blender -b --disable-autoexec <file.blend> --python tools/phantom/packaging_map.py -- \
      <out.json> [--frame F] [--hull NAME] [--x A B] [--y A B] [--dx M]

For each (x, y) grid column, casts vertical rays through the evaluated scene and records:
  * hull_top_z / hull_bottom_z: the outer-hull upper and lower surface (first hit from above /
    below on the hull object only);
  * occupied: z-intervals occupied by every other closed object (entry/exit pairs along the ray).
Gives the free vertical envelope inside the body for packaging studies. Geometry only.
"""
import bpy
import bmesh
import json
import sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0])
opts = dict(frame=1, hull='PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL', x=(-2.5, 2.5), y=(-1.3, 1.3), dx=0.05)
i = 1
while i < len(argv):
    k = argv[i][2:]
    if k in ('x', 'y'):
        opts[k] = (float(argv[i + 1]), float(argv[i + 2])); i += 3
    elif k in ('frame',):
        opts[k] = int(argv[i + 1]); i += 2
    elif k == 'dx':
        opts[k] = float(argv[i + 1]); i += 2
    else:
        opts[k] = argv[i + 1]; i += 2

scene = bpy.context.scene
scene.frame_set(opts['frame'])
dg = bpy.context.evaluated_depsgraph_get()


def bvh_of(o):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    if me is None or not len(me.polygons):
        ev.to_mesh_clear()
        return None
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(o.matrix_world)
    bm.verts.ensure_lookup_table()
    verts = [v.co.copy() for v in bm.verts]
    polys = [[v.index for v in f.verts] for f in bm.faces]
    lo = [min(v[k] for v in verts) for k in range(3)]
    hi = [max(v[k] for v in verts) for k in range(3)]
    bm.free()
    return BVHTree.FromPolygons(verts, polys), lo, hi


def hits(bvh, origin, d, limit=6.0):
    zs, o = [], origin.copy()
    for _ in range(64):
        loc, _n, _i, dist = bvh.ray_cast(o, d, limit)
        if loc is None:
            break
        zs.append(loc.z)
        o = loc + d * 1e-5
    return zs


objs = {}
for o in scene.objects:
    if o.type in {'MESH', 'CURVE'} and not o.hide_render:
        b = bvh_of(o)
        if b:
            objs[o.name] = b
hull = objs.pop(opts['hull'])

cols = []
nx = int(round((opts['x'][1] - opts['x'][0]) / opts['dx'])) + 1
ny = int(round((opts['y'][1] - opts['y'][0]) / opts['dx'])) + 1
down = Vector((0, 0, -1))
for ix in range(nx):
    x = opts['x'][0] + ix * opts['dx']
    for iy in range(ny):
        y = opts['y'][0] + iy * opts['dx']
        top = hits(hull[0], Vector((x, y, 5.0)), down, 10.0)
        if not top:
            continue
        occ = []
        for name, (bvh, lo, hi) in objs.items():
            if not (lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1]):
                continue
            zs = hits(bvh, Vector((x, y, 5.0)), down, 10.0)
            if len(zs) >= 2:
                occ.append(dict(name=name, z=[min(zs), max(zs)]))
        cols.append(dict(x=round(x, 4), y=round(y, 4), hull_top_z=max(top), hull_bottom_z=min(top),
                         hull_hits=len(top), occupied=occ))

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(file=bpy.data.filepath, frame=opts['frame'], hull=opts['hull'],
                               grid_m=opts['dx'], columns=cols), indent=0))
print('PACKAGING_MAP', len(cols), 'columns')
