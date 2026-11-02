"""Export A9 articulation, mass properties and joint data for MuJoCo integration.

Usage:
  blender -b --disable-autoexec assets/derived/phantom-a9-cassette.blend \
      --python tools/phantom/export_handover.py -- evidence/phantom/a9_handover.json evidence/phantom/a9_mujoco_fragment.xml

* Rigid bodies = parts grouped under their nearest joint empty (A9_JOINT_*, JOINT_WHEEL_POD_*, JOINT_LEG_SLIDE_*).
* Mass: the part's `mass_kg` property if present (DERIVED/SYNTHETIC, see wing_loads.py), otherwise mesh
  volume x material density. COM and inertia by exact signed-tetrahedron integration of each closed
  mesh at uniform density, combined with the parallel-axis theorem.
* Reference pose: frame 240 (wings deployed and pinned, surfaces neutral, canards deployed).
  Stowed pose (frame 1) COMs are also reported.
"""
import bpy
import bmesh
import json
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
OUT_JSON, OUT_XML = Path(argv[0]).resolve(), Path(argv[1]).resolve()
SC = bpy.context.scene
REF, STOW = 240, 1
DENSITY = {'CFRP': 1580.0, 'Ti': 4430.0, 'steel': 7800.0, 'actuator': 2700.0, 'duct': 1580.0}


def density_of(ob):
    m = ob.active_material.name if ob.active_material else ''
    if 'CFRP' in m or 'graphite' in m.lower():
        return DENSITY['CFRP'], 'CFRP'
    if 'Ti' in m or 'titanium' in m.lower():
        return DENSITY['Ti'], 'Ti'
    if 'steel' in m.lower():
        return DENSITY['steel'], 'steel'
    if 'actuator' in m.lower():
        return DENSITY['actuator'], 'actuator'
    return DENSITY['CFRP'], 'CFRP'


def mass_props(ob):
    """Volume, centroid and inertia (about centroid, world axes) of a closed mesh at unit density."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    import numpy as np
    tri = np.array([[list(v.co) for v in f.verts] for f in bm.faces], dtype=np.float64)
    bm.free()
    bpy.data.meshes.remove(me)
    if not len(tri):
        return 0.0, Vector(), Matrix.Identity(3)
    o = tri.reshape(-1, 3).mean(axis=0)            # integrate about a local origin (float64) to avoid cancellation
    a, b, c = tri[:, 0] - o, tri[:, 1] - o, tri[:, 2] - o
    d = np.einsum('ij,ij->i', a, np.cross(b, c)) / 6.0
    V = d.sum()
    if abs(V) < 1e-12:
        return 0.0, Vector(), Matrix.Identity(3)
    C = (d[:, None] * (a + b + c) / 4.0).sum(axis=0) / V
    S = np.zeros((3, 3))
    for x, y in ((a, a), (b, b), (c, c)):
        S += 2 * np.einsum('k,ki,kj->ij', d, x, y)
    for x, y in ((a, b), (a, c), (b, c)):
        S += np.einsum('k,ki,kj->ij', d, x, y) + np.einsum('k,kj,ki->ij', d, x, y)
    S /= 20.0
    if V < 0:
        V, S = -V, -S
    S_c = S - V * np.outer(C, C)
    I = np.trace(S_c) * np.eye(3) - S_c
    return float(V), Vector(C + o), Matrix(I.tolist())


def body_of(ob):
    p = ob.parent
    while p is not None:
        if p.type == 'EMPTY' and ('JOINT' in p.name):
            return p.name
        p = p.parent
    return None


JOINTS = [o for o in SC.objects if o.type == 'EMPTY' and ('JOINT' in o.name)]
JNAMES = {j.name for j in JOINTS}


def joint_parent(j):
    p = j.parent
    while p is not None:
        if p.name in JNAMES:
            return p.name
        p = p.parent
    return 'chassis'


def collect(frame):
    SC.frame_set(frame)
    bodies = {}
    for ob in SC.objects:
        if ob.type != 'MESH':
            continue
        b = body_of(ob)
        if b is None and not ob.name.startswith('A9_'):
            continue
        b = b or 'chassis_A9_fixed_parts'
        V, Cm, I = mass_props(ob)
        if V <= 0:
            continue
        rho, mat = density_of(ob)
        if 'mass_kg' in ob.keys():
            m, basis = float(ob['mass_kg']), 'property (DERIVED/SYNTHETIC)'
        elif ob.name.startswith('A9_'):
            m, basis = V * rho, f'DERIVED volume x {mat} density'
        else:
            m, basis = V * rho, f'A8 PLACEHOLDER: solid CAD volume x {mat} density, not a mass estimate'
        scale = m / V
        bodies.setdefault(b, []).append(dict(part=ob.name, mass=m, com=Cm, I=I * scale, basis=basis, volume=V))
    out = {}
    for b, parts in bodies.items():
        M = sum(p['mass'] for p in parts)
        com = sum((p['com'] * p['mass'] for p in parts), Vector()) / M
        I = Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        for p in parts:
            d = p['com'] - com
            pa = Matrix([[(d.length_squared if i == j else 0) - d[i] * d[j] for j in range(3)] for i in range(3)]) * p['mass']
            I = I + p['I'] + pa
        ev = sorted(eigs(I))
        out[b] = dict(mass_kg=M, com_world_m=list(com), inertia_about_com_world_axes_kg_m2=[list(r) for r in I],
                      principal_moments_kg_m2=ev, positive_definite=ev[0] > 0,
                      parts=[dict(name=p['part'], mass_kg=p['mass'], basis=p['basis']) for p in parts])
    return out


def eigs(I):
    import numpy as np
    return [float(x) for x in np.linalg.eigvalsh(np.array([list(r) for r in I]))]


def joint_record(j):
    SC.frame_set(REF)
    mw = j.matrix_world
    axis = (mw.to_3x3() @ Vector((1, 0, 0))).normalized()
    if j.get('joint_type') == 'hinge' and 'axis_world' in j.keys():
        axis = Vector(j['axis_world']).normalized() if 'CANARD' in j.name or 'HATCH' in j.name else axis
    rec = dict(name=j.name, parent_body=joint_parent(j), anchor_world_m=list(mw.translation), axis_world=list(axis))
    for k in j.keys():
        v = j[k]
        if k.startswith('_') or k in ('blendstra_id',):
            continue
        try:
            json.dumps(v)
            rec[k] = v
        except TypeError:
            rec[k] = list(v)
    if 'HATCH' in j.name:
        rec['value_at_reference_frame'] = -180.0
        rec['mjcf_note'] = 'MJCF body is written at the reference frame (door open); its range is shifted so 0 = open, 180 = closed'
    if j.name.startswith('JOINT_WHEEL_POD_'):
        rec.update(joint_type='hinge', axis_world=[1, 0, 0], range_deg=[-90, 0] if j.location.y < 0 else [0, 90],
                   note='A8 wheel-thruster pod rotation about X (road <-> VTOL), animation-derived range')
    if j.name.startswith('JOINT_LEG_SLIDE_'):
        rec.update(joint_type='slide', axis_world=[0, 0, 1], range_m=[-0.52, 0.0], note='A8 landing leg extension, animation-derived')
    return rec


ref = collect(REF)
stow = collect(STOW)
joints = [joint_record(j) for j in sorted(JOINTS, key=lambda o: o.name)]

sites = {}
SC.frame_set(REF)
for side, s in (('R', 1), ('L', -1)):
    for st, tag in ((1.17, 'OUT'), (0.24, 'IN')):
        j = bpy.data.objects.get(f'A9_JOINT_WING_{side}_LOCK_REAR_{tag}')
        if j:
            sites[f'lock_station_{side}_{tag}'] = list(j.matrix_world.translation)
aero = dict(
    wing=dict(S_ref_m2=4.055, S_exposed_each_m2=0.756, span_m=5.19, mac_m=0.872, x_ac_mac_m=-0.806, y_mac_m=1.042,
              ac_height_R_m=1.0015, ac_height_L_m=0.879, section='NACA 2411 -> 2410 (stand-in)', incidence_deg=0.0,
              CLalpha_per_rad_M0=4.0, CLmax_clean=1.2, CLmax_flap=1.6, cm0=-0.04, basis='DERIVED/SYNTHETIC, wing_loads.py A9_cassette_build'),
    aileron=dict(eta=[0.55, 0.95], area_each_m2=0.067, cf_c=0.28, tau=0.64, Ch_delta=-0.70, Ch_alpha=-0.35),
    flap=dict(eta=[0.05, 0.50], area_each_m2=0.114, cf_c=0.28, tau=0.64),
    canard=dict(area_each_m2=0.278, x_pivot_m=1.80, y_root_m=1.26, y_tip_m=1.84, z_m=0.95, section='NACA 0009', CLalpha_per_rad=3.0,
                pivot_frac_mac=0.25),
)
handover = dict(
    schema='phantom-a9-handover-0.1', source_file=bpy.data.filepath, reference_frame=REF, stowed_frame=STOW,
    frame_convention='Blender model: X forward, Y to A8-RIGHT side (+Y), Z up, right-handed, metres. Use the same '
                     'axes for the MuJoCo body frame (x forward, z up); A8 "RIGHT" objects sit at +Y.',
    status='Kinematic CAD + DERIVED/SYNTHETIC mass. Chassis (A8 hull, tub, pods, occupants, powertrain) mass is NOT included.',
    bodies_reference_pose=ref, body_coms_stowed_pose={k: v['com_world_m'] for k, v in stow.items()},
    joints=joints, sites=sites, aero_surfaces=aero,
    control_limits=dict(
        wing_slide=dict(stroke_m=1.37, max_speed_m_s=0.30, stall_force_N=2500, transit_q_limit_Pa=600, sequence='hatch open -> slide -> 4 pins -> locked'),
        locks=dict(pins_per_wing=4, engage_stroke_m=0.07, engage_time_s=0.5, ultimate_pin_force_N=54000, sensor='2 proximity sensors per pin'),
        aileron=dict(travel_deg=[-20, 20], rate_deg_s=80, stall_torque_Nm=72, power_peak_W=78, min_stiffness_Nm_rad=6929),
        flap=dict(travel_deg=[-5, 35], rate_deg_s=15, stall_torque_Nm=60, min_stiffness_Nm_rad=27276, max_speed_m_s=75),
        canard_pitch=dict(travel_deg=[-20, 25], rate_deg_s=40, stall_torque_Nm=420),
        canard_fold=dict(travel_deg=90, rate_deg_s=60, lock='shoot bolt'),
        hatch=dict(travel_deg=180, rate_deg_s=180, latch_load_at_VD_N=2105)),
)
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(handover, indent=1, default=float))

# ------------------------------------------------------------------ MJCF fragment (A9 articulation only)
SC.frame_set(REF)
by_parent = {}
for j in joints:
    by_parent.setdefault(j['parent_body'], []).append(j)


def fmt(v):
    return ' '.join(f'{x:.5g}' for x in v)


def body_xml(j, parent_anchor, depth):
    ind = '  ' * depth
    b = ref.get(j['name'])
    pos = [j['anchor_world_m'][k] - parent_anchor[k] for k in range(3)]
    lines = [f'{ind}<body name="{j["name"]}" pos="{fmt(pos)}">']
    if b:
        com = [b['com_world_m'][k] - j['anchor_world_m'][k] for k in range(3)]
        I = b['inertia_about_com_world_axes_kg_m2']
        lines.append(f'{ind}  <inertial pos="{fmt(com)}" mass="{b["mass_kg"]:.5g}" fullinertia="{I[0][0]:.5g} {I[1][1]:.5g} {I[2][2]:.5g} '
                     f'{I[0][1]:.5g} {I[0][2]:.5g} {I[1][2]:.5g}"/>')
    else:
        lines.append(f'{ind}  <inertial pos="0 0 0" mass="0.05" diaginertia="1e-5 1e-5 1e-5"/>')
    jt = j.get('joint_type', 'hinge')
    off = j.get('value_at_reference_frame', 0.0)       # ranges are stored relative to the as-built pose
    if jt == 'slide':
        lo, hi = j.get('range_m', [0, 0])
        lo, hi = lo - off, hi - off
        lines.append(f'{ind}  <joint name="{j["name"]}" type="slide" axis="{fmt(j["axis_world"])}" range="{lo:.5g} {hi:.5g}" limited="true" armature="0.01" damping="20"/>')
    else:
        lo, hi = j.get('range_deg', [-180, 180])
        lo, hi = lo - off, hi - off
        lines.append(f'{ind}  <joint name="{j["name"]}" type="hinge" axis="{fmt(j["axis_world"])}" range="{lo:.5g} {hi:.5g}" limited="true" armature="0.001" damping="0.5"/>')
    for c in by_parent.get(j['name'], []):
        lines += body_xml(c, j['anchor_world_m'], depth + 1)
    lines.append(f'{ind}</body>')
    return lines


xml = ['<!-- VTX Phantom A9 articulation fragment (generated by tools/phantom/export_handover.py).',
       '     Insert inside the chassis body; positions are relative to the chassis origin (model origin).',
       '     Angles in degrees (compiler angle="degree"). Mass/inertia DERIVED/SYNTHETIC; chassis not included. -->']
for j in by_parent.get('chassis', []):
    if j['name'].startswith('A9_'):
        xml += body_xml(j, [0, 0, 0], 0)
OUT_XML.write_text('\n'.join(xml) + '\n')
print('HANDOVER', len(ref), 'bodies', len(joints), 'joints ->', OUT_JSON.name, OUT_XML.name)
for k, v in sorted(ref.items()):
    print(f'  {k:45s} m={v["mass_kg"]:7.2f} kg  com={[round(x, 3) for x in v["com_world_m"]]}  PD={v["positive_definite"]}')
