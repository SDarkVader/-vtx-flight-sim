"""Munk step 3: body-only CAD envelope from phantom-a10.glb (same exclusions as the parameter file's projected areas)."""
import sys, json, numpy as np, trimesh
sc = trimesh.load(sys.argv[1] + '/ck/public/assets/phantom-a10.glb')
EXC = ('WHEEL_', 'LEG_', 'A10_WING', 'A10_CANARD', 'CFD_', 'A10_HATCH', 'PHANTOM_FL_', 'PHANTOM_FR_', 'PHANTOM_RL_', 'PHANTOM_RR_', 'JOINT_', 'SEAT_')
V = []; used = []
for n in sc.graph.nodes_geometry:
    if n.startswith(EXC): continue
    T, g = sc.graph[n]; mesh = sc.geometry[g]
    V.append(trimesh.transform_points(mesh.vertices, T)); used.append(n)
V = np.vstack(V); print('body nodes', len(used), 'vertices', len(V), 'x', V[:, 0].min().round(2), V[:, 0].max().round(2), 'y', V[:, 1].min().round(2), V[:, 1].max().round(2), 'z', V[:, 2].min().round(2), V[:, 2].max().round(2))
# rasterised projections (2 cm grid) to check against the parameter file (plan 10.14, side 3.96, frontal 2.12 m2)
def proj(a, b, g=0.02):
    I = np.floor(V[:, [a, b]] / g).astype(int); return len(set(map(tuple, I))) * g * g
# vertex density can leave holes; use per-slab extents instead for the envelope
xs = np.arange(V[:, 0].min(), V[:, 0].max(), 0.02); w = []; h = []; zlo = []
for x in xs:
    s = V[np.abs(V[:, 0] - x) < 0.02]
    if len(s) < 4: w.append(0); h.append(0); zlo.append(np.nan); continue
    w.append(s[:, 1].max() - s[:, 1].min()); h.append(s[:, 2].max() - s[:, 2].min()); zlo.append(s[:, 2].min())
w = np.array(w); h = np.array(h)
print('plan area from slab widths %.2f m2 (param 10.14) | raster plan %.2f side %.2f frontal %.2f' % (np.trapezoid(w, xs), proj(0, 1), proj(0, 2), proj(1, 2)))
json.dump(dict(x=xs.tolist(), w=w.tolist(), h=h.tolist(), zlo=[float(z) for z in zlo]), open(sys.argv[1] + '/m3_cad.json', 'w'))
for i in range(0, len(xs), 15): print('  x %+.2f  w %.2f  h %.2f' % (xs[i], w[i], h[i]))
