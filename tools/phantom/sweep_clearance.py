"""Frame-by-frame collision and clearance sweep for a Phantom .blend (Blender -b --disable-autoexec).

Usage:
  blender -b --disable-autoexec <file.blend> --python tools/phantom/sweep_clearance.py -- \
      <out.json> [--step N] [--frames A B] [--ignore-pair REGEX_A REGEX_B ...] [--watch REGEX]

Method (KINEMATIC GEOMETRY ONLY — no structural or aerodynamic meaning):
  * Every mesh/curve object is evaluated (modifiers + animation) and triangulated in world space.
  * "Moving" objects are those whose evaluated world matrix changes between any two swept frames.
  * For each swept frame, each moving object is tested against every other object:
      - surface intersection: BVH triangle-pair overlap (mathutils.bvhtree.overlap);
      - containment: a moving object's sample point lies inside a closed (manifold) partner,
        tested by +X/-Y/+Z ray-parity voting;
      - clearance: minimum distance from dense surface samples of the moving object to the
        partner BVH (find_nearest). Reported only when partner AABB is within 0.25 m.
  * At the first frame, every static object pair is also checked for surface intersection.
Sampling resolution is reported; clearances are accurate to about that resolution.
"""
import bpy
import bmesh
import json
import re
import sys
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0])
step, frames, ignore, watch = 1, None, [], None
SAMPLE = 0.01   # m, target surface sample spacing on moving objects
MAX_SAMPLES = 20000
i = 1
while i < len(argv):
    if argv[i] == '--step':
        step = int(argv[i + 1]); i += 2
    elif argv[i] == '--sample':
        SAMPLE = float(argv[i + 1]); i += 2
    elif argv[i] == '--frames':
        frames = (int(argv[i + 1]), int(argv[i + 2])); i += 3
    elif argv[i] == '--ignore-pair':
        ignore.append((re.compile(argv[i + 1]), re.compile(argv[i + 2]))); i += 3
    elif argv[i] == '--watch':
        watch = re.compile(argv[i + 1]); i += 2
    else:
        raise SystemExit('unknown arg ' + argv[i])

scene = bpy.context.scene
f0, f1 = frames or (scene.frame_start, scene.frame_end)
frame_list = list(range(f0, f1 + 1, step))
if frame_list[-1] != f1:
    frame_list.append(f1)
NEAR = 0.25    # m, AABB proximity for clearance evaluation

geom_objs = [o for o in scene.objects if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'} and not o.hide_render]


def ignored(a, b):
    for ra, rb in ignore:
        if (ra.search(a) and rb.search(b)) or (ra.search(b) and rb.search(a)):
            return True
    return False


def world_tris(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    if me is None or not len(me.polygons):
        ev.to_mesh_clear()
        return None
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(o.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    verts = [v.co.copy() for v in bm.verts]
    tris = [[v.index for v in f.verts] for f in bm.faces]
    manifold = all(e.is_manifold for e in bm.edges) and len(bm.edges) > 0
    bm.free()
    if not tris:
        return None
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    return dict(verts=verts, tris=tris, bvh=BVHTree.FromPolygons(verts, tris, epsilon=0.0),
                lo=lo, hi=hi, manifold=manifold)


def samples(g):
    pts = list(g['verts'])
    for t in g['tris']:
        a, b, c = (g['verts'][k] for k in t)
        n = max(1, int(math.ceil(max((b - a).length, (c - a).length, (c - b).length) / SAMPLE)))
        if n == 1:
            pts.append((a + b + c) / 3)
            continue
        for u in range(n + 1):
            for v in range(n + 1 - u):
                w = n - u - v
                pts.append((a * u + b * v + c * w) / n)
    if len(pts) > MAX_SAMPLES:  # keep all vertices, thin the interior samples evenly
        nv = len(g['verts'])
        stride = math.ceil((len(pts) - nv) / (MAX_SAMPLES - nv))
        pts = pts[:nv] + pts[nv::stride]
    return pts


def aabb_gap(a, b):
    d = [max(0.0, a['lo'][k] - b['hi'][k], b['lo'][k] - a['hi'][k]) for k in range(3)]
    return math.sqrt(sum(x * x for x in d))


def inside(g, p):
    votes = 0
    for d in (Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))):
        hits, origin = 0, p.copy()
        for _ in range(64):
            loc, _n, _i, _d = g['bvh'].ray_cast(origin, d)
            if loc is None:
                break
            hits += 1
            origin = loc + d * 1e-5
        votes += hits % 2
    return votes >= 2


def snapshot(frame):
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    return {o.name: world_tris(o, dg) for o in geom_objs}, {o.name: [list(r) for r in o.matrix_world] for o in geom_objs}


# Identify moving objects from world matrices over the sweep.
mats = {}
for fr in frame_list:
    scene.frame_set(fr)
    for o in geom_objs:
        mats.setdefault(o.name, []).append(o.matrix_world.copy())
moving = sorted(n for n, ms in mats.items()
                if any(max(abs(ms[0][r][c] - m[r][c]) for r in range(4) for c in range(4)) > 1e-6 for m in ms[1:]))
if watch:
    moving = [n for n in moving if watch.search(n)]

# Static pairwise interferences at the first frame.
geo0, _ = snapshot(frame_list[0])
static_hits = []
names = [n for n in geo0 if geo0[n]]
for ia, na in enumerate(names):
    for nb in names[ia + 1:]:
        if ignored(na, nb) or aabb_gap(geo0[na], geo0[nb]) > 0:
            continue
        ov = geo0[na]['bvh'].overlap(geo0[nb]['bvh'])
        if ov:
            static_hits.append(dict(a=na, b=nb, triangle_pairs=len(ov)))

per_object = {n: dict(collisions={}, contained_in={}, min_clearance=None) for n in moving}
timeline = []
for fr in frame_list:
    geo, _ = snapshot(fr) if fr != frame_list[0] else (geo0, None)
    row = dict(frame=fr, objects={})
    for nm in moving:
        g = geo.get(nm)
        if not g:
            continue
        pts = None
        rec = dict(hits=[], inside=[], clearance=None)
        for other, h in geo.items():
            if other == nm or not h or ignored(nm, other):
                continue
            gap = aabb_gap(g, h)
            if gap > NEAR:
                continue
            if gap == 0 and g['bvh'].overlap(h['bvh']):
                rec['hits'].append(other)
                continue
            if h['manifold'] and gap == 0 and inside(h, g['verts'][0]):
                rec['inside'].append(other)
                continue
            if pts is None:
                pts = samples(g)
            dmin = min(h['bvh'].find_nearest(p)[3] for p in pts)
            if rec['clearance'] is None or dmin < rec['clearance'][1]:
                rec['clearance'] = (other, dmin)
        row['objects'][nm] = rec
        po = per_object[nm]
        for other in rec['hits']:
            po['collisions'].setdefault(other, []).append(fr)
        for other in rec['inside']:
            po['contained_in'].setdefault(other, []).append(fr)
        if rec['clearance'] and (po['min_clearance'] is None or rec['clearance'][1] < po['min_clearance']['m']):
            po['min_clearance'] = dict(partner=rec['clearance'][0], m=rec['clearance'][1], frame=fr)
    timeline.append(row)


def ranges(fs):
    out, start, prev = [], fs[0], fs[0]
    for f in fs[1:]:
        if f - prev > step:
            out.append([start, prev]); start = f
        prev = f
    out.append([start, prev])
    return out


for po in per_object.values():
    po['collisions'] = {k: ranges(v) for k, v in po['collisions'].items()}
    po['contained_in'] = {k: ranges(v) for k, v in po['contained_in'].items()}

result = dict(
    file=bpy.data.filepath, blender=bpy.app.version_string, frames=frame_list,
    method='BVH triangle overlap + ray-parity containment + sampled nearest distance; kinematic only',
    sample_spacing_m=SAMPLE, clearance_search_m=NEAR,
    moving_objects=moving, static_intersections_first_frame=static_hits,
    per_object=per_object, timeline=timeline)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=1, default=lambda v: list(v)))
ncol = sum(1 for p in per_object.values() if p['collisions'])
print('SWEEP', len(frame_list), 'frames', len(moving), 'moving;', ncol, 'moving objects collide;',
      len(static_hits), 'static intersecting pairs')
