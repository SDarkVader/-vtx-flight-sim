"""Compare the rendered world (sample.mjs dump) with the physics world (src/vtx/world.py).

Usage (from the worktree root):
  PYTHONPATH=src python evidence/visual/harness/coincidence_check.py <sample.json> <report.json>
Read-only with respect to physics: it only instantiates TestWorld and calls its query methods.
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
import numpy as np
from vtx.world import TestWorld
from vtx.mission_selection import MapPoint

src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
w = TestWorld()
rep: dict = {'source': src, 'quality': d.get('quality')}

# 1. terrain mesh vertices and triangle diagonals
P = np.array(d['terrain']['positions']).reshape(-1, 3)
M = np.array(d['terrain']['matrix'])
ident = bool(np.allclose(M, np.eye(4).flatten()))
vz = np.array([w.terrain_z(x, y) for x, y, _ in P])
step = 2 * w.half / (w.n - 1)
gi = np.rint((P[:, 0] + w.half) / step).astype(int); gj = np.rint((P[:, 1] + w.half) / step).astype(int)
on_grid = np.allclose(P[:, 0], -w.half + gi * step, atol=1e-4) and np.allclose(P[:, 1], -w.half + gj * step, atol=1e-4)
hz = w.heights[gj, gi]
I = np.array(d['terrain']['index']).reshape(-1, 3)
bad_diag = 0
for tri in I:
    ii, jj = gi[tri], gj[tri]; i0, j0 = ii.min(), jj.min()
    keys = set(zip(ii.tolist(), jj.tolist()))
    if not ((i0, j0) in keys and (i0 + 1, j0 + 1) in keys): bad_diag += 1
# random interior samples using the mesh's own triangles (barycentric) vs world.terrain_z
cells = defaultdict(list)
for tri in I:
    cells[(gi[tri].min(), gj[tri].min())].append(tri)
rng = np.random.default_rng(7)
samples = np.concatenate([rng.uniform(-499.9, 499.9, (12000, 2)),
                          np.stack(np.meshgrid(np.linspace(-495, 495, 100), np.linspace(-495, 495, 100)), -1).reshape(-1, 2)])
maxdiff = 0.0
for x, y in samples:
    i, j = int((x + w.half) // step), int((y + w.half) // step)
    zbest = None
    for tri in cells[(i, j)]:
        a, b, c = P[tri]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9: zbest = l1 * a[2] + l2 * b[2] + l3 * c[2]; break
    maxdiff = max(maxdiff, abs(zbest - w.terrain_z(x, y)))
rep['terrain'] = dict(vertices=len(P), matrix_identity=ident, vertices_on_grid=bool(on_grid),
                      max_vertex_vs_heights_m=float(np.abs(P[:, 2] - hz).max()),
                      max_vertex_vs_terrain_z_m=float(np.abs(P[:, 2] - vz).max()),
                      triangles=len(I), triangles_with_wrong_diagonal=bad_diag,
                      interior_samples=len(samples), max_interior_diff_m=maxdiff)

# 2. downward raycasts at mission points
rays = []
for r in d['rays']:
    out = []
    for h in r['hits']:
        x, y = r['x'] + h['dx'], r['y'] + h['dy']
        s = w.surface_z(x, y) if max(abs(x), abs(y)) <= w.half else None
        out.append(dict(dx=h['dx'], dy=h['dy'], visual=h['z'], surface=s, diff=None if (h['z'] is None or s is None) else h['z'] - s, obj=h['obj']))
    c = [o for o in out if o['dx'] == 0 and o['dy'] == 0][0]
    diffs = [o['diff'] for o in out if o['diff'] is not None]
    v = w.validate(MapPoint(r['x'], r['y']), 'mission') if max(abs(r['x']), abs(r['y'])) <= w.half else None
    rays.append(dict(name=r['name'], x=r['x'], y=r['y'], centre_diff=c['diff'], centre_obj=c['obj'],
                     footprint_min_diff=min(diffs) if diffs else None, footprint_max_diff=max(diffs) if diffs else None,
                     worst_obj=max(out, key=lambda o: abs(o['diff'] or 0))['obj'],
                     validate=None if v is None else dict(ok=v.valid, reason=v.reason)))
rep['rays'] = rays

# 3. buildings
boxes = []
for b in d['boxes']:
    vis = [n for n in b['near'] if n['visible']]
    over = sorted([n for n in vis if n['prot'] > 0.8 + 1e-3], key=lambda n: -n['prot'])
    boxes.append(dict(id=b['id'], meshes=len(vis), max_protrusion_m=max([n['prot'] for n in vis], default=None),
                      over_trim_limit=[dict(obj=n['obj'], prot=n['prot']) for n in over[:12]]))
rep['boxes'] = boxes

# 4. trees
trees = d['trees']
rep['trees'] = dict(instances=len(trees),
                    max_radius_ratio=max((t['maxR'] / t['radius'] for t in trees), default=None),
                    max_top_excess_m=max((t['maxZ'] - t['top'] for t in trees), default=None),
                    min_base_z=min((t['minZ'] for t in trees), default=None),
                    max_centre_offset_m=max((t['offset'] for t in trees), default=None),
                    outside_collider=sum(1 for t in trees if t['maxR'] > t['radius'] + 1e-3 or t['maxZ'] > t['top'] + 1e-3))

# 5. paint / drape
by = defaultdict(lambda: dict(n=0, buried=0, floating=0, max_above=-1e9, min_above=1e9, outside_physics=0, depthTest_off=0))
for g, name, x, y, z, dt in d['paint']:
    k = by[g]; k['n'] += 1; k['depthTest_off'] += (dt == 0)
    if max(abs(x), abs(y)) > w.half: k['outside_physics'] += 1; continue
    a = z - w.terrain_z(x, y)
    k['max_above'] = max(k['max_above'], a); k['min_above'] = min(k['min_above'], a)
    if a < -0.02: k['buried'] += 1
    if a > 0.15: k['floating'] += 1
rep['paint'] = by

# 6. collider-less inventory, grouped
inv = defaultdict(list)
for it in d['inventory']:
    inv[it['obj'].split('|')[0]].append(it)
rep['inventory'] = {k: dict(count=len(v), example=v[0]) for k, v in sorted(inv.items())}
rep['lights'] = d['lights']

# 7. vehicles vs colliders / water
def hits_box(bmin, bmax):
    for o in w.obstacles:
        cx, cy, cz = o['center']; hx, hy, hz = o['half']
        if bmax[0] > cx - hx and bmin[0] < cx + hx and bmax[1] > cy - hy and bmin[1] < cy + hy and bmin[2] < cz + hz:
            return o['id']
    wa = w.water
    if bmax[0] > wa['x'] - wa['half_x'] and bmin[0] < wa['x'] + wa['half_x'] and bmax[1] > wa['y'] - wa['half_y'] and bmin[1] < wa['y'] + wa['half_y']:
        return 'water'
    return None
veh = defaultdict(lambda: dict(samples=0, conflicts=defaultdict(int), max_ground_gap=0.0))
for nm, t, x0, y0, z0, x1, y1, z1, vis in d['vehicles']:
    if not vis: continue
    v = veh[nm]; v['samples'] += 1
    h = hits_box((x0, y0, z0), (x1, y1, z1))
    if h: v['conflicts'][h] += 1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if max(abs(cx), abs(cy)) <= w.half: v['max_ground_gap'] = max(v['max_ground_gap'], abs(z0 - w.terrain_z(cx, cy)))
rep['vehicles'] = veh
json.dump(rep, open(dst, 'w'), indent=1, default=lambda o: dict(o) if isinstance(o, defaultdict) else str(o))
print(json.dumps(dict(terrain=rep['terrain'], trees=rep['trees'], paint=rep['paint'],
                      rays=[(r['name'], None if r['centre_diff'] is None else round(r['centre_diff'], 4), None if r['footprint_max_diff'] is None else round(r['footprint_max_diff'], 3), r['worst_obj'], r['validate']['ok'] if r['validate'] else None) for r in rays],
                      boxes=[(b['id'], b['max_protrusion_m'], len(b['over_trim_limit'])) for b in boxes],
                      vehicles={k: dict(samples=v['samples'], conflicts=dict(v['conflicts'])) for k, v in veh.items()},
                      inventory={k: v['count'] for k, v in rep['inventory'].items()}), indent=1, default=str))
