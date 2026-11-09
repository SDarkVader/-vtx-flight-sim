"""Munk step 1: hull section geometry (body frame) from the plant's airframe collision meshes."""
import sys, math, json, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
from scipy.spatial import ConvexHull
a = C.plant('phantom-fx', {'proposals': {'p6_drs_stabilator': {'v': 1.}}}, start_configuration='road'); m, d = a.model, a.data
Rb = a.R(); org = d.xpos[a.bids['airframe']]
pieces = []
for gi in range(m.ngeom):
    n = m.geom(gi).name
    if m.body(m.geom_bodyid[gi]).name != 'airframe' or m.geom_type[gi] != 7: continue
    mid = m.geom_dataid[gi]; v0 = m.mesh_vertadr[mid]; nv = m.mesh_vertnum[mid]
    R = d.geom_xmat[gi].reshape(3, 3); pts = d.geom_xpos[gi] + m.mesh_vert[v0:v0+nv] @ R.T
    pb = (pts - org) @ Rb                      # body frame
    pieces.append((n, pb))
    print(n, nv, 'x', np.round([pb[:, 0].min(), pb[:, 0].max()], 2), 'y', np.round([pb[:, 1].min(), pb[:, 1].max()], 2), 'z', np.round([pb[:, 2].min(), pb[:, 2].max()], 2))
allp = np.vstack([p for _, p in pieces]); H = ConvexHull(allp)
print('airframe collision union (convex hull of all pieces): volume', round(H.volume, 2), 'm3')
xs = np.linspace(allp[:, 0].min(), allp[:, 0].max(), 60); rows = []
for x in xs:
    w = h = 0.0
    for _, p in pieces:      # section of each convex piece: extent of vertices within a slab (convex => interval)
        s = p[np.abs(p[:, 0] - x) < 0.06]
        if len(s) >= 3: w = max(w, s[:, 1].max() - s[:, 1].min()); h = max(h, s[:, 2].max() - s[:, 2].min())
    rows.append((round(float(x), 3), round(w, 3), round(h, 3)))
json.dump(dict(sections=rows, volume_hull=H.volume, geom=a.P.geometry.get('projected_areas')), open(sys.argv[1] + '/m1_sections.json', 'w'))
print('projected areas (params)', a.P.geometry.get('projected_areas'))
for r in rows[::5]: print('  x %+.2f  width %.2f  height %.2f' % r)
