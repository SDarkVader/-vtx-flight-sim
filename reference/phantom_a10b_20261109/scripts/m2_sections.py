"""Munk step 2: exact convex-piece sections (plane x = const) of the airframe collision hull; union across pieces."""
import sys, json, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
from scipy.spatial import ConvexHull
a = C.plant('phantom-fx', {'proposals': {'p6_drs_stabilator': {'v': 1.}}}, start_configuration='road'); m, d = a.model, a.data
Rb = a.R(); org = d.xpos[a.bids['airframe']]; pieces = []
for gi in range(m.ngeom):
    if m.body(m.geom_bodyid[gi]).name != 'airframe' or m.geom_type[gi] != 7: continue
    mid = m.geom_dataid[gi]; v0 = m.mesh_vertadr[mid]; nv = m.mesh_vertnum[mid]
    R = d.geom_xmat[gi].reshape(3, 3); pb = ((d.geom_xpos[gi] + m.mesh_vert[v0:v0+nv] @ R.T) - org) @ Rb
    H = ConvexHull(pb); E = set()
    for s in H.simplices:
        for i in range(3): E.add(tuple(sorted((s[i], s[(i+1) % 3]))))
    pieces.append((m.geom(gi).name, pb, np.array(sorted(E)), H.volume))
vol = sum(p[3] for p in pieces); xmin = min(p[1][:, 0].min() for p in pieces); xmax = max(p[1][:, 0].max() for p in pieces)
def section(x):
    ys, zs, area = [], [], 0.0
    for n, p, E, _ in pieces:
        a_, b_ = p[E[:, 0]], p[E[:, 1]]; da, db = a_[:, 0] - x, b_[:, 0] - x
        cr = (da * db) <= 0
        if not cr.any(): continue
        t = np.where(np.abs(db - da)[cr] > 1e-12, da[cr] / (da[cr] - db[cr]), 0.0)
        q = a_[cr] + t[:, None] * (b_[cr] - a_[cr])
        if len(q) >= 3:
            ys += [q[:, 1].min(), q[:, 1].max()]; zs += [q[:, 2].min(), q[:, 2].max()]
            try: area += ConvexHull(q[:, 1:]).volume
            except Exception: pass
    return (max(ys) - min(ys), max(zs) - min(zs), area, min(zs) if zs else 0) if ys else (0, 0, 0, 0)
xs = np.linspace(xmin, xmax, 200); S = np.array([section(x) for x in xs])
print('length %.2f m (x %.2f..%.2f), sum of piece volumes %.2f m3, integral of section area %.2f m3' % (xmax - xmin, xmin, xmax, vol, np.trapezoid(S[:, 2], xs)))
print('plan area from widths %.2f m2 (params body plan 10.14)' % np.trapezoid(S[:, 0], xs), ' max width %.2f, max height %.2f' % (S[:, 0].max(), S[:, 1].max()))
json.dump(dict(x=xs.tolist(), w=S[:, 0].tolist(), h=S[:, 1].tolist(), A=S[:, 2].tolist(), zlow=S[:, 3].tolist()), open(sys.argv[1] + '/m2_sections.json', 'w'))
for i in range(0, 200, 12): print('  x %+.2f  w %.2f  h %.2f  A %.2f' % (xs[i], *S[i, :3]))
