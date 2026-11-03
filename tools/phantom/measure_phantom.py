"""Read-only Blender measurement of the Phantom A9 for the simulator (never saves the .blend).

Usage:
  blender -b --disable-autoexec assets/derived/phantom-a9-cassette.blend \
      --python tools/phantom/measure_phantom.py -- evidence/phantom/phantom_geometry.json

Writes MEASURED-K geometry: per-collection surface areas and area centroids at frame 1 (road
stance, wings stowed) and per-object bounds, body projected areas (frontal / side / plan) by a
ray grid, and the hull vertex set split into x-slabs x left/right for convex collision pieces.
"""
import bpy, bmesh, json, sys, hashlib, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

out = Path(sys.argv[sys.argv.index('--') + 1])
SC = bpy.context.scene
SC.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
src = Path(bpy.data.filepath)
sha = hashlib.sha256(src.read_bytes()).hexdigest()
EXCL = ('WHEEL_', 'LEG_', 'A9_WING_', 'A9_CANARD_', 'CFD_', 'A9_HATCH', 'PHANTOM_FL_', 'PHANTOM_FR_', 'PHANTOM_RL_', 'PHANTOM_RR_', 'JOINT_')

def world_mesh(o):
    ev = o.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None
    if me is None or not len(me.polygons):
        ev.to_mesh_clear(); return None
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(ev.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    ev.to_mesh_clear()
    return bm

objects = {}
groups = {}
body_tris = []
for o in SC.objects:
    if o.type not in {'MESH'} or not o.visible_get():
        continue
    bm = world_mesh(o)
    if bm is None:
        continue
    area = 0.0; c = Vector((0, 0, 0))
    for f in bm.faces:
        a = f.calc_area(); area += a; c += f.calc_center_median() * a
    vs = [v.co.copy() for v in bm.verts]
    lo = [min(v[i] for v in vs) for i in range(3)]; hi = [max(v[i] for v in vs) for i in range(3)]
    col = o.users_collection[0].name if o.users_collection else ''
    objects[o.name] = dict(collection=col, area_m2=area, area_centroid_m=list(c / area) if area else lo,
                           bounds_min_m=lo, bounds_max_m=hi, closed=all(e.is_manifold for e in bm.edges))
    g = groups.setdefault(col, dict(area_m2=0.0, moment=[0.0, 0.0, 0.0], objects=0))
    g['area_m2'] += area; g['objects'] += 1
    for i in range(3):
        g['moment'][i] += c[i]
    if not o.name.startswith(EXCL):
        for f in bm.faces:
            body_tris.append([v.co.copy() for v in f.verts])
    bm.free()
for g in groups.values():
    g['area_centroid_m'] = [m / g['area_m2'] for m in g.pop('moment')] if g['area_m2'] else None

verts = [v for t in body_tris for v in t]
polys = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(body_tris))]
tree = BVHTree.FromPolygons(verts, polys)
lo = [min(v[i] for v in verts) for i in range(3)]; hi = [max(v[i] for v in verts) for i in range(3)]
def projected(axis, step=0.02):
    a, b = [i for i in range(3) if i != axis]
    hits = 0; n = 0
    u = lo[a]
    while u <= hi[a]:
        w = lo[b]
        while w <= hi[b]:
            p = Vector((0, 0, 0)); p[a] = u; p[b] = w; p[axis] = lo[axis] - 1.0
            d = Vector((0, 0, 0)); d[axis] = 1.0
            if tree.ray_cast(p, d, hi[axis] - lo[axis] + 2.0)[0] is not None:
                hits += 1
            n += 1; w += step
        u += step
    return hits * step * step
proj = dict(frontal_m2=projected(0), side_m2=projected(1), plan_m2=projected(2), grid_m=0.02,
            excludes=list(EXCL), note='body only (no pods, legs, wings, canards, hatches) at frame 1')

hull = SC.objects['PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL']
bm = world_mesh(hull)
hv = [v.co.copy() for v in bm.verts]; bm.free()
xs = [v.x for v in hv]; x0, x1 = min(xs), max(xs)
NS = 10
pieces = []
for k in range(NS):
    xa = x0 + (x1 - x0) * k / NS; xb = x0 + (x1 - x0) * (k + 1) / NS
    for side, sel in (('L', lambda v: v.y >= -0.02), ('R', lambda v: v.y <= 0.02)):
        pts = [v for v in hv if xa - 0.05 <= v.x <= xb + 0.05 and sel(v)]
        if len(pts) >= 8:
            pieces.append(dict(slab=k, side_cad=side, x=[xa, xb], vertices=[[round(c, 4) for c in v] for v in pts]))

res = dict(schema='phantom-geometry-1', source_file=str(src.name), source_sha256=sha, frame=1,
           label='MEASURED-K', frame_convention='CAD X forward, Y to CAD-RIGHT (+Y, physical left), Z up, metres',
           projected_areas=proj, collections=groups, objects=objects,
           hull=dict(object=hull.name, bounds_min_m=[min(v[i] for v in hv) for i in range(3)],
                     bounds_max_m=[max(v[i] for v in hv) for i in range(3)], convex_pieces=pieces))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(res, indent=1))
print('WROTE', out, len(objects), 'objects', proj)
