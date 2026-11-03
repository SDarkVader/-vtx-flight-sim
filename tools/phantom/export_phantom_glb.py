"""Export a Phantom wing-cassette revision (A9 or A10) as the browser GLB (render only; never saves the .blend).

Run with the project Python; it writes the joint map from the simulator ledger and then calls
Blender in background mode on assets/derived/phantom-<rev>-cassette.blend (read-only):

  PYTHONPATH=src .venv/Scripts/python.exe tools/phantom/export_phantom_glb.py [--revision A9|A10] [--blender <exe>]

Default output public/assets/phantom-<rev>.glb (the plant's provenance.render_asset for that revision).

Output: frame 1 (road stance, wings stowed), Z-up (export_yup=False, same frame as MuJoCo), no
animations, renderable meshes only. A root empty 'airframe' (extras physical_body='airframe')
receives the chassis pose; every mapped CAD joint empty carries extras
  phantom_joint (MuJoCo joint name), joint_type (hinge|slide), axis_parent (unit axis in the
  empty's parent frame), q_rest (MuJoCo joint value at the exported frame).
phantom-look.js drives those empties from rendering_truth.phantom.joints.
"""
from __future__ import annotations
import json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLEND = {'A9': ROOT / 'assets/derived/phantom-a9-cassette.blend', 'A10': ROOT / 'assets/derived/phantom-a10-cassette.blend'}
VARIANT = {'A9': 'phantom', 'A10': 'phantom-a10'}
BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'


def write_map(path, revision='A9'):
    sys.path.insert(0, str(ROOT / 'src'))
    from vtx.phantom.params import Params
    from vtx.phantom.ledger import PhantomLedger
    from vtx.phantom.geometry import SIDE
    L = PhantomLedger(Params(VARIANT[revision]))
    out = {}
    for b in L.bodies.values():
        if not (b.cad and b.joint):
            continue
        q = SIDE[b.name[4:]] * math.pi / 2 if b.name.startswith('pod_') else (-0.52 if b.name.startswith('leg_') else 0.0)
        out[b.name] = dict(cad=b.cad, type=b.joint, axis_world=[float(x) for x in b.axis], q_frame240=q, range=[float(x) for x in b.range] if b.range else None)
    Path(path).write_text(json.dumps(out, indent=1))


def blender_main(argv):
    import bpy
    from mathutils import Vector, Quaternion
    a = dict(zip(argv[::2], argv[1::2]))
    jm = json.loads(Path(a['--map']).read_text())
    sc = bpy.context.scene
    def world_of(o, f):
        # pose relative to the parent, so child joints (canard pitch under fold) do not see the parent's motion
        sc.frame_set(f); bpy.context.view_layer.update()
        return (o.parent.matrix_world.inverted() @ o.matrix_world) if o.parent else o.matrix_world.copy()
    report = {}
    for jn, j in jm.items():
        o = bpy.data.objects.get(j['cad'])
        if o is None:
            report[jn] = 'missing'; continue
        m1 = world_of(o, 1); m240 = world_of(o, 240)
        sc.frame_set(1); bpy.context.view_layer.update()
        ax = (o.parent.matrix_world.to_3x3().inverted() @ Vector(j['axis_world'])).normalized() if o.parent else Vector(j['axis_world']).normalized()
        if j['type'] == 'slide':
            q1 = j['q_frame240'] + (m1.translation - m240.translation).dot(ax)
        else:
            dq = (m1.to_quaternion() @ m240.to_quaternion().inverted())
            ang = dq.angle if dq.angle <= math.pi else dq.angle - 2 * math.pi
            sgn = 1.0 if Vector(dq.axis).dot(ax) >= 0 else -1.0
            q1 = j['q_frame240'] + sgn * ang
            r = j.get('range')
            for k in (-1, 1):
                if r and not (r[0] - 1e-4 <= q1 <= r[1] + 1e-4) and r[0] - 1e-4 <= q1 + k * 2 * math.pi <= r[1] + 1e-4:
                    q1 += k * 2 * math.pi
        j['q_rest'] = q1; report[jn] = dict(cad=j['cad'], q_rest=round(q1, 5), children=len(o.children_recursive))
    sc.frame_set(1); bpy.context.view_layer.update()
    # strip animation so the exported rest pose is frame 1 and nothing plays in the browser
    for o in bpy.data.objects:
        o.animation_data_clear()
    for jn, j in jm.items():
        o = bpy.data.objects.get(j['cad'])
        if o is None or 'q_rest' not in j:
            continue
        pr = o.parent.matrix_world.to_3x3() if o.parent else None
        axp = (pr.inverted() @ Vector(j['axis_world'])) if pr else Vector(j['axis_world'])
        o['phantom_joint'] = jn; o['joint_type'] = j['type']; o['axis_parent'] = list(axp.normalized()); o['q_rest'] = j['q_rest']
    tops = [o for o in sc.objects if o.parent is None]
    root = bpy.data.objects.new('airframe', None); sc.collection.objects.link(root)
    root['physical_body'] = 'airframe'
    for o in tops:
        mw = o.matrix_world.copy(); o.parent = root; o.matrix_world = mw
    for o in sc.objects:   # render-only: hide helper/collision meshes from export
        if o.type == 'MESH' and (o.hide_render or o.name.upper().startswith(('COLL', 'UCX', 'HELPER'))):
            o.hide_set(True)
    bpy.ops.export_scene.gltf(filepath=a['--out'], export_format='GLB', export_yup=False, export_animations=False, export_extras=True,
                              use_visible=True, use_renderable=True, export_apply=True)
    Path(a['--report']).write_text(json.dumps(report, indent=1))
    print('exported', a['--out'])


if __name__ == '__main__':
    if '--' in sys.argv and 'bpy' in sys.modules or any(m == 'bpy' for m in sys.modules):
        blender_main(sys.argv[sys.argv.index('--') + 1:])
    else:
        import argparse
        ap = argparse.ArgumentParser(); ap.add_argument('--revision', choices=sorted(BLEND), default='A9'); ap.add_argument('--blender', default=BLENDER)
        ap.add_argument('--out'); ap.add_argument('--report'); x = ap.parse_args()
        sfx = '' if x.revision == 'A9' else '_' + x.revision.lower()   # A9 keeps its original evidence file names
        x.out = x.out or str(ROOT / f'public/assets/phantom-{x.revision.lower()}.glb')
        x.report = x.report or str(ROOT / f'evidence/phantom/phantom_glb_export{sfx}.json')
        mp = ROOT / f'evidence/phantom/phantom_glb_joint_map{sfx}.json'; write_map(mp, x.revision)
        subprocess.run([x.blender, '-b', '--disable-autoexec', str(BLEND[x.revision]), '--python', __file__, '--', '--map', str(mp), '--out', x.out, '--report', x.report], check=True)
