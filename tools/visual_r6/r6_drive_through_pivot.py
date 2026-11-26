"""Candidate: carry each fan drive through the duct tilt pivot (owner review before any adoption).

usage: python r6_drive_through_pivot.py <in.glb> <out.glb> <log.json>

The drive used to stop at the top of the rising fan spindle (z 1.49 m), 0.5 m below the nacelle
gearbox (z 2.07 m). The nacelle tilts about its physics pivot (nacelle container origin, z 1.98 m),
so the only joint that stays joined at every tilt is one centred on that pivot. Per fan this:
  1. lengthens the rising fan spindle (airframe) from its top up to 10 mm past the pivot;
  2. adds a CV joint at the pivot: new airframe nodes reusing the existing CV boot (solid ball) and
     CV primary race meshes (the original parts at the hub are left in place);
  3. adds a nacelle input stub shaft (new nacelle node reusing the spindle mesh) from 10 mm below
     the pivot up 6 mm into the bottom of the nacelle reduction gearbox.
Body containers, existing vertex data and every other part are unchanged. JSON-only edit.
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import r6_glb as K  # noqa: E402

src, dst, log_path = sys.argv[1:4]
blob = open(src, 'rb').read()
jlen = struct.unpack_from('<I', blob, 12)[0]
G = json.loads(blob[20:20 + jlen])
BIN = blob[20 + jlen + 8:]
M = K.GLBModel(G, BIN[:struct.unpack_from('<I', blob, 20 + jlen)[0]])
PART = {p['name']: p for p in M.parts}
NODE = {n.get('name'): i for i, n in enumerate(G['nodes'])}
PARENT = {c: i for i, n in enumerate(G['nodes']) for c in n.get('children', [])}
LOG = []
END = 0.010      # how far each shaft end passes the pivot into the CV joint (m)
INTO = 0.006     # how far the stub enters the gearbox (m)


def world_of(i):
    m = K.local(G['nodes'][i])
    while i in PARENT:
        i = PARENT[i]
        m = K.local(G['nodes'][i]) @ m
    return m


def z_axis_node(mesh, container, z0, z1, x, y, name):
    """New node showing `mesh` (a rod along its local long axis) from world z0 to z1 at (x, y)."""
    V = M.accessor(G['meshes'][mesh]['primitives'][0]['attributes']['POSITION'])
    for prim in G['meshes'][mesh]['primitives'][1:]:
        V = np.vstack([V, M.accessor(prim['attributes']['POSITION'])])
    k = int(np.argmax(V.max(0) - V.min(0)))
    lo, hi = float(V[:, k].min()), float(V[:, k].max())
    s = (z1 - z0) / (hi - lo)
    # rotation taking local axis k to world +z (container frames here are unrotated)
    rot = {0: [0, -0.7071067811865476, 0, 0.7071067811865476], 1: [0.7071067811865476, 0, 0, 0.7071067811865476], 2: [0, 0, 0, 1]}[k]
    R = K.quat_mat(rot)
    S = np.ones(3)
    S[k] = s
    c_local = (V.max(0) + V.min(0)) / 2
    centre = np.array([x, y, (z0 + z1) / 2])
    Wc = world_of(NODE[container])
    t_world = centre - R @ (S * c_local)
    t = (np.linalg.inv(Wc) @ np.append(t_world, 1))[:3]
    node = dict(name=name, mesh=mesh, translation=[float(v) for v in t], rotation=rot, scale=[float(v) for v in S],
                extras=dict(physical_body=container, vtx_added='r6_drive_through_pivot.py'))
    G['nodes'].append(node)
    G['nodes'][NODE[container]].setdefault('children', []).append(len(G['nodes']) - 1)
    return node


for j in range(1, 5):
    pivot = world_of(NODE[f'nacelle{j}'])[:3, 3]
    spindle = f'P03 | F{j} rising fan spindle'
    sp = PART[spindle]
    n = G['nodes'][sp['node']]
    V = sp['V']
    k = int(np.argmax(V.max(0) - V.min(0)))
    W = M.world(sp)
    top_now = float(W[:, 2].max())
    target = float(pivot[2]) + END
    # which local end is the top: the one whose world z is larger
    Wn = world_of(sp['node'])
    end_hi_world = (Wn @ np.append(np.where(np.arange(3) == k, V[:, k].max(), (V.max(0) + V.min(0)) / 2), 1))[2]
    fixed = V[:, k].min() if end_hi_world >= top_now - 1e-6 else V[:, k].max()
    L = V[:, k].max() - V[:, k].min()
    per = float(np.linalg.norm(Wn[:3, k]))
    f = (L + (target - top_now) / per) / L
    T0, R0 = np.array(n.get('translation', [0, 0, 0]), float), K.quat_mat(n.get('rotation', [0, 0, 0, 1]))
    S0 = np.array(n.get('scale', [1, 1, 1]), float)
    S = S0.copy()
    S[k] *= f
    e = np.zeros(3)
    e[k] = fixed * (1 - f)
    n['translation'] = [float(v) for v in T0 + R0 @ (S0 * e)]
    n['scale'] = [float(v) for v in S]
    LOG.append(dict(part=spindle, op='lengthen to the tilt pivot', top_from_m=round(top_now, 4), top_to_m=round(target, 4)))

    # CV joint on the pivot: a copy of the solid CV boot ball, ringed by a copy of the CV primary race.
    for src_name, new_name in ((f'V3 P03 | F{j} CV boot envelope', f'R3 P03 | F{j} tilt-pivot CV joint'),
                               (f'V3 P03 | F{j} torque transfer spherical CV primary', f'R3 P03 | F{j} tilt-pivot CV race')):
        cv_src = G['nodes'][NODE[src_name]]
        cv = dict(name=new_name, mesh=cv_src['mesh'], rotation=cv_src.get('rotation', [0, 0, 0, 1]),
                  extras=dict(physical_body='airframe', vtx_added='r6_drive_through_pivot.py'))
        Vc = M.accessor(G['meshes'][cv_src['mesh']]['primitives'][0]['attributes']['POSITION'])
        c_local = (Vc.max(0) + Vc.min(0)) / 2
        Rcv = K.quat_mat(cv['rotation']) * np.array(cv_src.get('scale', [1, 1, 1]))
        cv['translation'] = [float(v) for v in (np.linalg.inv(world_of(NODE['airframe'])) @ np.append(pivot - Rcv @ c_local, 1))[:3]]
        if 'scale' in cv_src:
            cv['scale'] = cv_src['scale']
        G['nodes'].append(cv)
        G['nodes'][NODE['airframe']].setdefault('children', []).append(len(G['nodes']) - 1)
        LOG.append(dict(part=new_name, op=f'new copy of {src_name} centred on the physics tilt pivot', centre_m=[round(float(v), 4) for v in pivot]))
    gb = PART[f'V4 P03 | F{j} nacelle-local 7.5:1 reduction gearbox V4 candidate']
    gb_bottom = float(M.world(gb)[:, 2].min())
    z_axis_node(G['nodes'][sp['node']]['mesh'], f'nacelle{j}', float(pivot[2]) - END, gb_bottom + INTO, float(pivot[0]), float(pivot[1]),
                f'R3 P03 | F{j} nacelle input stub shaft')
    LOG.append(dict(part=f'R3 P03 | F{j} nacelle input stub shaft', op='new shaft from the pivot into the gearbox',
                    z_from_m=round(float(pivot[2]) - END, 4), z_to_m=round(gb_bottom + INTO, 4)))

G.setdefault('asset', {}).setdefault('extras', {})['vtx_candidate'] = 'r6_drive_through_pivot.py: drive carried through the tilt pivot (owner review)'
js = json.dumps(G, separators=(',', ':')).encode()
js += b' ' * (-len(js) % 4)
binb = BIN[:struct.unpack_from('<I', blob, 20 + jlen)[0]]
binb += b'\0' * (-len(binb) % 4)
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binb)) + struct.pack('<II', len(js), 0x4E4F534A)
                      + js + struct.pack('<II', len(binb), 0x004E4942) + binb)
json.dump(LOG, open(log_path, 'w'), indent=1)
print(json.dumps(LOG, indent=1))
