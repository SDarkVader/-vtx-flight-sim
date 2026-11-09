"""Munk step 4: exact plane sections (x = const) of the body-only CAD meshes; envelope width/height per station."""
import sys, json, numpy as np, trimesh
sc = trimesh.load(sys.argv[1] + '/ck/public/assets/phantom-a10.glb')
EXC = ('WHEEL_', 'LEG_', 'A10_WING', 'A10_CANARD', 'CFD_', 'A10_HATCH', 'PHANTOM_FL_', 'PHANTOM_FR_', 'PHANTOM_RL_', 'PHANTOM_RR_', 'JOINT_', 'SEAT_')
M = []
for n in sc.graph.nodes_geometry:
    if n.startswith(EXC): continue
    T, g = sc.graph[n]; m = sc.geometry[g].copy(); m.apply_transform(T); M.append(m)
xs = np.linspace(-2.44, 2.45, 99); W = []; H = []; ZL = []
for x in xs:
    ys = []; zs = []
    for m in M:
        if m.bounds[0][0] > x or m.bounds[1][0] < x: continue
        try:
            sec = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
        except Exception: sec = None
        if sec is None: continue
        v = sec.vertices; ys += [v[:, 1].min(), v[:, 1].max()]; zs += [v[:, 2].min(), v[:, 2].max()]
    W.append(max(ys) - min(ys) if ys else 0.0); H.append(max(zs) - min(zs) if zs else 0.0); ZL.append(min(zs) if zs else float('nan'))
W = np.array(W); H = np.array(H)
side = np.trapezoid(H, xs); plan = np.trapezoid(W, xs)
print('envelope plan area %.2f m2 (param 10.14), side envelope %.2f m2 (param 3.96), max width %.2f, max height %.2f' % (plan, side, W.max(), H.max()))
json.dump(dict(x=xs.tolist(), w=W.tolist(), h=H.tolist(), zlo=ZL), open(sys.argv[1] + '/m4_cad.json', 'w'))
for i in range(0, len(xs), 7): print('  x %+.2f  w %.2f  h %.2f  z_low %.2f' % (xs[i], W[i], H[i], ZL[i]))
