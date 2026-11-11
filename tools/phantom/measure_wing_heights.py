"""Measure the deployed chord-plane height of the left and right wing panels (MEASURED-K).

Usage:
  blender -b --disable-autoexec <file.blend> --python tools/phantom/measure_wing_heights.py -- <out.json> [--frame F] [--rev A9|A10]

At each spanwise station |y| the panel mesh is sliced (bmesh bisect) in world space; the chord line
runs from the leading-edge point (max x) to the trailing-edge point (min x). Chord-plane height =
mean z of those two points. Residual = z_R - z_L at mirrored stations. Geometry only.
"""
import bpy
import bmesh
import json
import sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0])
frame = int(argv[argv.index('--frame') + 1]) if '--frame' in argv else 240
rev = argv[argv.index('--rev') + 1] if '--rev' in argv else bpy.context.scene.get('vtx_revision_tag', 'A9')
sc = bpy.context.scene
sc.frame_set(frame + 1)
sc.frame_set(frame)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()


def section(ob, y):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(ob.matrix_world)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector((0, y, 0)), plane_no=Vector((0, 1, 0)), dist=1e-7)
    pts = [e.co.copy() for e in res['geom_cut'] if isinstance(e, bmesh.types.BMVert)]
    bm.free()
    if len(pts) < 3:
        return None
    le = max(pts, key=lambda p: p.x)
    te = min(pts, key=lambda p: p.x)
    import math
    return dict(y=y, le=list(le), te=list(te), chord=le.x - te.x, z_chord_plane=0.5 * (le.z + te.z),
                incidence_deg=math.degrees(math.atan2(le.z - te.z, le.x - te.x)),
                z_max=max(p.z for p in pts), z_min=min(p.z for p in pts))


panels = {s: bpy.data.objects[f'{rev}_WING_{s}_PANEL_CFRP_TORSION_BOX'] for s in ('R', 'L')}
lo, hi = [], []
for s, ob in panels.items():
    ys = [abs((ob.matrix_world @ v.co).y) for v in ob.data.vertices]
    lo.append(min(ys)); hi.append(max(ys))
y0, y1 = max(lo) + 0.02, min(hi) - 0.02
stations = [y0 + (y1 - y0) * k / 8 for k in range(9)]
rows = []
for y in stations:
    r, l = section(panels['R'], y), section(panels['L'], -y)
    rows.append(dict(abs_y=y, R=r, L=l, residual_m=(r['z_chord_plane'] - l['z_chord_plane']) if r and l else None))
res = [abs(r['residual_m']) for r in rows if r['residual_m'] is not None]
for r in rows:
    r['incidence_diff_deg'] = r['R']['incidence_deg'] - r['L']['incidence_deg']
inc = [abs(r['incidence_diff_deg']) for r in rows]
twist = {k: rows[-1][k]['incidence_deg'] - rows[0][k]['incidence_deg'] for k in ('R', 'L')}
outd = dict(file=bpy.data.filepath, revision=rev, frame=frame, method='bmesh bisect at |y| stations, LE/TE mid-height; MEASURED-K',
            stations=rows, max_abs_incidence_diff_deg=max(inc), twist_deg=twist, twist_diff_deg=twist['R'] - twist['L'], max_abs_residual_m=max(res), mean_residual_m=sum(r['residual_m'] for r in rows) / len(rows),
            root_chord_plane_R_m=rows[0]['R']['z_chord_plane'], root_chord_plane_L_m=rows[0]['L']['z_chord_plane'])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(outd, indent=1))
print('HEIGHTS', rev, 'frame', frame, 'R', round(outd['root_chord_plane_R_m'], 5), 'L', round(outd['root_chord_plane_L_m'], 5),
      'max |residual| mm', round(1000 * outd['max_abs_residual_m'], 3), 'max |d_incidence| deg', round(max(inc), 4), 'twist', twist)
