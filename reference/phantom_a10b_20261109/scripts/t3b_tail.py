import sys, math, numpy as np, mujoco as mj
sys.path.insert(0, sys.argv[1]); import camp as C
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
a = C.plant('phantom-fx', P6, start_configuration='road'); m, d = a.model, a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
Rb = a.R(); org = d.xpos[a.bids['airframe']]
rear = [np.array(d.contact[i].pos) for i in range(d.ncon) if any(m.geom(g).name.startswith('tyre_R') for g in (d.contact[i].geom1, d.contact[i].geom2))]
Pr = np.mean(rear, axis=0); zg = Pr[2]; fwd = Rb @ [1, 0, 0]
TYPES = {0: 'plane', 2: 'sphere', 3: 'capsule', 5: 'cylinder', 6: 'box', 7: 'mesh'}
res = []
for gi in range(m.ngeom):
    n = m.geom(gi).name
    if m.geom_bodyid[gi] == 0 or n.startswith(('tyre_', 'foot_')) or (m.geom_contype[gi] == 0 and m.geom_conaffinity[gi] == 0): continue
    R = d.geom_xmat[gi].reshape(3, 3); t = m.geom_type[gi]
    if t == 7:
        mid = m.geom_dataid[gi]; v0 = m.mesh_vertadr[mid]; nv = m.mesh_vertnum[mid]; V = m.mesh_vert[v0:v0+nv]
        pts = d.geom_xpos[gi] + V @ R.T
    elif t == 6:
        hs = m.geom_size[gi]; pts = np.array([d.geom_xpos[gi] + R @ (hs * [sx, sy, sz]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    else:
        pts = np.array([d.geom_xpos[gi] - [0, 0, m.geom_rbound[gi]]])
    dx = (Pr - pts) @ fwd; dz = pts[:, 2] - zg
    sel = dx > 0.02
    if sel.any():
        ang = np.degrees(np.arctan2(dz[sel], dx[sel])); k = int(np.argmin(ang))
        res.append((float(ang[k]), n, TYPES.get(t, t), round(float(dx[sel][k]), 2), round(float(dz[sel][k]), 3), m.body(m.geom_bodyid[gi]).name))
res.sort()
print('ground clearance of the airframe origin', round(org[2] - zg, 3), 'm; tyre radius', a.P['pods.tyre_radius_m'])
for r in res[:8]: print('  tail-strike angle %5.1f deg  %-22s %-8s %.2f m aft of rear contact, %.3f m above ground  (body %s)' % r)
