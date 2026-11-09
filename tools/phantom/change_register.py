"""A10 change register vs A9 (object-level, by role name with the revision prefix stripped).

Usage: blender -b --disable-autoexec assets/derived/phantom-a10-cassette.blend --python tools/phantom/change_register.py -- \
           assets/derived/phantom-a9-cassette.blend evidence/phantom/a10_change_register.json
Opens the A9 file read-only via bpy.data.libraries.load (names only); nothing is saved.
"""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
a9_path, out = argv[0], Path(argv[1])
with bpy.data.libraries.load(a9_path, link=False) as (src, _):
    a9_names = list(src.objects)
a10 = {o.name: o for o in bpy.context.scene.objects}


def role(n):
    for p in ('A10_', 'A9_'):
        if n.startswith(p):
            return n[len(p):]
    return None


r9 = {role(n): n for n in a9_names if role(n)}
r10 = {role(n): n for n in a10 if role(n)}
WHY = {
    'SLEEVE_CARRY_THROUGH_BOX': 'twin-cell sleeve -> split-level sleeve (panel level over two fore/aft tongue channels + divider spar); same outer box',
    'WING_R_TONGUE_CARRY_THROUGH_BOX': 'full-chord 0.090 m tongue in upper cell -> half-chord 0.095 m tongue in front channel',
    'WING_L_TONGUE_CARRY_THROUGH_BOX': 'full-chord tongue in lower cell -> half-chord tongue in rear channel',
    'WING_L_PANEL_CFRP_TORSION_BOX': 'moved up 0.118 m to the common panel level; span 1.364 -> 1.198 m, tip chord 0.32 -> 0.42 m',
    'WING_R_PANEL_CFRP_TORSION_BOX': 'same height as A9; span 1.364 -> 1.198 m, tip chord 0.32 -> 0.42 m',
    'HATCH_L_FLUSH_DOOR': 'left slot moved to the panel level; door now mirrors the right door (hinge at z 0.9405, flips down)',
    'JOINT_WING_R_SLIDE': 'stroke 1.37 -> 1.205 m', 'JOINT_WING_L_SLIDE': 'stroke 1.37 -> 1.205 m; anchor z 0.8815 -> 0.9995',
}
changed = []
for k in sorted(set(r9) & set(r10)):
    if k in WHY or k.startswith('WING_L') or k.startswith('JOINT_WING_L') or k.startswith('JOINT_AILERON_L') or k.startswith('JOINT_FLAP_L') \
            or k.startswith('HATCH_L') or k.startswith('JOINT_HATCH_L') or 'LOCK' in k or 'SLEEVE' in k:
        changed.append(dict(a9=r9[k], a10=r10[k], change=WHY.get(k, 'relocated/re-sized for the split-level cassette (see A10_WING_SYMMETRY_REVISION.md)')))
reg = dict(
    base='A9 (assets/derived/phantom-a9-cassette.blend, built from A8 version_a5589426...); A10 rebuilt from the same A8 source',
    builder='tools/phantom/build_a10_cassette.py (imports build_a9_cassette.py, A9_IMPORT_ONLY=1)',
    removed_vs_A9=[r9[k] for k in sorted(set(r9) - set(r10))],
    added_vs_A9=[r10[k] for k in sorted(set(r10) - set(r9))],
    carried_over_renamed=len(set(r9) & set(r10)),
    changed_vs_A9=changed,
    unchanged_from_A9='canards (blades, spindles, yokes, root structures), induction ducts, haunch/hull shoulders, A8 trims, timeline (frames 1-530)',
    a8_removed=bpy.context.scene.get('a10_removed_objects', '').split(', '),
    a8_trimmed=bpy.context.scene.get('a10_trimmed_objects', '').split(', '))
out.write_text(json.dumps(reg, indent=1))
print('REGISTER removed', len(reg['removed_vs_A9']), 'added', len(reg['added_vs_A9']), 'changed', len(changed))
