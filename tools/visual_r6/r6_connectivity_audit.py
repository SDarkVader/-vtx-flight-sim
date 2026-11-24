"""Geometric connectivity audit of an R6 display GLB, at rest and in physics poses.

usage: python r6_connectivity_audit.py <r6.glb> <poses.json> <out.json> [contact_tol_mm]

Checks, using exact mesh geometry (no rendering):
  1. contact graph: two parts touch if a vertex of one lies within tol of the other's surface,
     or an edge of one passes through a triangle of the other (interpenetrating joints);
  2. floating groups: any connected group of parts not joined to the main assembly;
  3. free rod ends: elongated parts with an end that touches nothing;
  4. artifacts: empty/non-finite/degenerate meshes, tiny stray parts, coincident duplicates;
  5. articulation: every contact between parts on different physics bodies at rest must still
     hold in every physics pose (otherwise the part is owned by the wrong body).
Read-only; writes only <out.json>.
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))

import r6_glb as K  # noqa: E402
from r6_glb import Geo, pair_distance, end_contact, inside, NEAR  # noqa: E402,F401

glb_path, poses_path, out_path = sys.argv[1:4]
TOL = (float(sys.argv[4]) if len(sys.argv) > 4 else 1.0) / 1000.0
M = K.load(glb_path)
G, parts, roots = M.G, M.parts, M.roots
P = json.load(open(poses_path))


def world(part, pose):
    return M.world(part, P[pose])


# ---------------------------------------------------------------- 4. artifacts
artifacts = []
for p in parts:
    V, F = p['V'], p['F']
    if not np.all(np.isfinite(V)):
        artifacts.append(dict(part=p['name'], issue='non-finite vertices'))
    t = V[F]
    area = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) / 2
    if (area < 1e-12).sum():
        artifacts.append(dict(part=p['name'], issue=f'{int((area < 1e-12).sum())} zero-area triangles of {len(F)}'))
    if p['extras_body'] and p['extras_body'] != p['body']:
        artifacts.append(dict(part=p['name'], issue=f"tagged physical_body {p['extras_body']} but parented to {p['body']}"))
rest = [Geo(p, world(p, 'rest')) for p in parts]
for g in rest:
    diag = float(np.linalg.norm(g.hi - g.lo))
    if diag < 0.005:
        artifacts.append(dict(part=g.part['name'], issue=f'tiny part, {diag * 1000:.1f} mm across'))
sig = defaultdict(list)
for g in rest:
    sig[(len(g.W), tuple(np.round(g.lo, 4)), tuple(np.round(g.hi, 4)))].append(g.part['name'])
for names in sig.values():
    if len(names) > 1:
        artifacts.append(dict(part=names, issue='coincident duplicate parts (same vertex count and bounds)'))

# ---------------------------------------------------------------- 1-2. contact graph at rest
n = len(rest)
LO = np.array([g.lo for g in rest]) - NEAR
HI = np.array([g.hi for g in rest]) + NEAR
pairs = {}
for i in range(n):
    ov = np.all((LO[i + 1:] <= HI[i]) & (HI[i + 1:] >= LO[i]), 1)
    for j in np.nonzero(ov)[0] + i + 1:
        d = pair_distance(rest[i], rest[j])
        if d <= NEAR:
            pairs[(i, j)] = d
parent = list(range(n))


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


for (i, j), d in pairs.items():
    if d <= TOL:
        parent[find(i)] = find(j)
groups = defaultdict(list)
for i in range(n):
    groups[find(i)].append(i)
main = max(groups.values(), key=len)
floating = []
for members in groups.values():
    if members is main:
        continue
    near = sorted(((d, rest[j if i in members else i].part['name']) for (i, j), d in pairs.items()
                   if (i in members) != (j in members) and d <= NEAR))
    lo = np.min([rest[k].lo for k in members], 0)
    hi = np.max([rest[k].hi for k in members], 0)
    floating.append(dict(parts=[rest[k].part['name'] for k in members], bodies=sorted({rest[k].part['body'] for k in members}),
                         centre_m=np.round((lo + hi) / 2, 3).tolist(),
                         nearest_gap_mm=round(near[0][0] * 1000, 2) if near else None,
                         nearest_part=near[0][1] if near else None))

# ---------------------------------------------------------------- 3. free rod ends
free_ends = []
neighbours = defaultdict(list)
for (i, j), d in pairs.items():
    neighbours[i].append(j)
    neighbours[j].append(i)
for i, g in enumerate(rest):
    X = g.W - g.W.mean(0)
    if len(X) < 4:
        continue
    _, s, vt = np.linalg.svd(X, full_matrices=False)
    proj = X @ vt[0]
    length = float(proj.max() - proj.min())
    thick = float(np.ptp(X @ vt[1])) if len(vt) > 1 else 0.0
    if length < 0.08 or thick <= 0 or length / max(thick, 1e-6) < 5:
        continue
    band = max(2 * thick, 0.03 * length)
    ends = [np.nonzero(proj <= proj.min() + band)[0], np.nonzero(proj >= proj.max() - band)[0]]
    gaps = end_contact(g, ends, [rest[k] for k in neighbours[i]], inward=[vt[0] * band, -vt[0] * band])
    for k, gap in enumerate(gaps):
        if gap > TOL:
            tip = g.W[ends[k]].mean(0)
            free_ends.append(dict(part=g.part['name'], body=g.part['body'], end=k, tip_m=np.round(tip, 3).tolist(),
                                  length_m=round(length, 3), gap_mm=None if not np.isfinite(gap) else round(gap * 1000, 2)))

# ---------------------------------------------------------------- 5. articulation
articulation = []
cross = [(i, j) for (i, j), d in pairs.items() if d <= TOL and rest[i].part['body'] != rest[j].part['body']]
for pose in [k for k in P if k not in ('rest', 'meta')]:
    geos = {}
    for i, j in cross:
        for k in (i, j):
            if k not in geos:
                geos[k] = Geo(parts[k], world(parts[k], pose))
        d = pair_distance(geos[i], geos[j], pad=0.05)
        if d > TOL:
            articulation.append(dict(pose=pose, parts=[parts[i]['name'], parts[j]['name']],
                                     bodies=[parts[i]['body'], parts[j]['body']],
                                     gap_mm=None if not np.isfinite(d) else round(d * 1000, 2)))

near_misses = sorted(([rest[i].part['name'], rest[j].part['name'], round(d * 1000, 2)]
                      for (i, j), d in pairs.items() if TOL < d <= NEAR and find(i) != find(j)), key=lambda r: r[2])
report = dict(glb=glb_path, contact_tol_mm=TOL * 1000, parts=n, bodies=sorted(roots), contacts=sum(d <= TOL for d in pairs.values()),
              main_assembly_parts=len(main), floating_groups=floating, free_rod_ends=free_ends, artifacts=artifacts,
              articulation_breaks=articulation, near_misses_between_groups=near_misses[:50],
              poses_checked=[k for k in P if k != 'meta'],
              clean=not floating and not free_ends and not artifacts and not articulation)
json.dump(report, open(out_path, 'w'), indent=1)
print(json.dumps(dict(parts=n, contacts=report['contacts'], main_assembly=len(main), floating_groups=len(floating),
                      floating_parts=sum(len(f['parts']) for f in floating), free_rod_ends=len(free_ends),
                      artifacts=len(artifacts), articulation_breaks=len(articulation), clean=report['clean']), indent=1))
