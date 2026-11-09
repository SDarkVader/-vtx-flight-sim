"""Build the A10-B visual model (public/assets/phantom-a10b-visual.glb) from the refined A10 visual.

A10-B geometry changes applied to the file:
  * wing incidence +7 deg (leading edge up) on both wing slide joints' rest pose (P8, parameter
    proposals.p8_wing_incidence_deg); the runtime rig keeps the rest rotation and adds the joint motion;
  * asset extras naming the variant, its config SHA and the change list.
Front-wheel steering is animated by the runtime rig (public/vtx-env/phantom-look.js) on the pod joints from the plant's
pod_F*_steer joints, so it needs no new nodes. Rudder surfaces are not modelled in the mesh yet (hinge data in the spec).

  python tools/phantom/build_a10b_visual.py
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
from pygltflib import GLTF2

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'public/assets/phantom-a10-visual.glb'
OUT = ROOT / 'public/assets/phantom-a10b-visual.glb'
WING_SLIDES = ('A10_JOINT_WING_L_SLIDE', 'A10_JOINT_WING_R_SLIDE')


def qmul(a, b):   # xyzw
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def main():
    sys.path.insert(0, str(ROOT / 'src'))
    from vtx.phantom.params import Params
    P = Params('phantom-a10b'); inc = P['proposals.p8_wing_incidence_deg']
    g = GLTF2().load(str(SRC))
    q_inc = [0.0, math.sin(-math.radians(inc) / 2), 0.0, math.cos(-math.radians(inc) / 2)]   # about parent +y: LE (+x) up
    done = []
    for n in g.nodes:
        if n.name in WING_SLIDES:
            n.rotation = qmul(q_inc, list(n.rotation or [0, 0, 0, 1]))
            ex = dict(n.extras or {}); ex['a10b_wing_incidence_deg'] = inc; n.extras = ex; done.append(n.name)
    assert len(done) == 2, done
    g.asset.extras = dict(vtx_variant='phantom-a10b', config_sha256=P.config_sha256, source=str(SRC.relative_to(ROOT)),
                          a10b_changes=['wing incidence +7 deg (rest pose of both wing slide joints)',
                                        'front steer-by-wire animated by the runtime rig from pod_F*_steer',
                                        'rudders, booster TVC and suspension travel are plant states; mesh rudders pending'])
    g.save_binary(str(OUT))
    print('wrote', OUT.relative_to(ROOT), OUT.stat().st_size // 1024, 'KiB; incidence applied to', done)


if __name__ == '__main__':
    main()
