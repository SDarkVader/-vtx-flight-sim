"""Export the RC-01 articulation rig and a MuJoCo bench sweep for the complete Blender model (offline, isolated).

Everything the Blender rig uses comes from the compiled MuJoCo model of Concept A with the
rc01-real-components-v1 profile, not from hand-copied numbers:
  * hinge points, hinge axes and joint ranges (model.body_pos / body_quat / jnt_axis / jnt_range, chained to the
    airframe body frame, which is the GLB / VTX frame: +X forward, +Y port, +Z up);
  * channel limits and slew rates (craft.surface_limits, i.e. the actuators' published no-load speeds);
  * which visual GLB node rides on which physical body (hull_geometry.CONCEPT_A_AIRFRAME_NODE_SPECS), and the
    GLB node translations are compared with the MuJoCo body origins;
  * the command -> joint mapping the plant applies (plant._apply_actuator_controls / _profile_actuator_targets),
    stated below and then CHECKED against what MuJoCo actually does in the sweep.
Kinematic checks per surface mesh (as exported by craft.visual_geometry()): the hinge axis distance from the
surface's leading edge, the trailing-edge direction for +q, and how many surface vertices end up inside the
fixed neighbouring mesh at full travel (interference, ray-parity point-in-mesh).
Bench sweep: the craft floats at rest in the isolated harbour basin (still water, nothing live) and each command
is stepped through its full range at the actuators' real rates; joint angles and every articulated body's pose
relative to the airframe are sampled at 24 fps for the Blender animation and for the Blender-vs-MuJoCo check.
Usage: python export_rig.py <worktree> <out_dir>
"""
import json
import math
import pathlib
import struct
import sys
import time

import numpy as np

WT = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WT / 'src'))
sys.path.insert(0, str(WT / 'tests'))
import mujoco as mj  # noqa: E402
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.hull_geometry import CONCEPT_A_AIRFRAME_NODE_SPECS, CONCEPT_A_GLB  # noqa: E402
from vtx.ricochet.plant import ARTICULATED_CHILD_SPECS, RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402

PROFILE = 'rc01-real-components-v1'
FPS = 24
t_wall = time.time()

world = HarbourFleet(harbour_world()).world
WCFG = WaterEnvironmentConfig.from_dict(dict(water_level_m=world.harbour['waterLevelM'], wave_mode='still',
                                             wind_speed_mps=0.0, current_speed_mps=0.0, wake_enabled=False,
                                             whirlpools_enabled=False))
c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-01', water_config=WCFG,
                  profile=PROFILE)
m, d = c.model, c.data
c.spawn(-180.0, 0.0, 7.0)


def bid(name):
    return mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, name)


AF = bid('airframe')


def qmat(q):
    r = np.zeros(9)
    mj.mju_quat2Mat(r, np.asarray(q, dtype=np.float64))
    return r.reshape(3, 3)


def mat_quat(R):
    q = np.zeros(4)
    mj.mju_mat2Quat(q, np.asarray(R, dtype=np.float64).ravel())
    return q


def static_pose_in_airframe(b):
    """Body frame in the airframe frame with every joint between them at zero (model defaults)."""
    chain = []
    while b != AF:
        chain.append(b)
        b = int(m.body_parentid[b])
        if b == 0:
            raise RuntimeError('body is not under the airframe')
    p, R = np.zeros(3), np.eye(3)
    for bb in reversed(chain):
        p = p + R @ m.body_pos[bb]
        R = R @ qmat(m.body_quat[bb])
    return p, R, [mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, x) for x in reversed(chain)]


def glb_nodes(path):
    raw = pathlib.Path(path).read_bytes()
    n = struct.unpack_from('<I', raw, 12)[0]
    js = json.loads(raw[20:20 + n])
    return {nd.get('name'): nd for nd in js['nodes']}


# --- command -> joint mapping exactly as plant._apply_actuator_controls / _profile_actuator_targets apply it -------
ski = c.profile['skis']
j0s, j1s = (float(v) for v in ski['joint_range_deg'])
ski_hi = min(j1s, j0s + float(c.profile['_ski_env']['travel_deg']))
COMMAND_MAP = {
    'aileron_port_hinge': dict(terms=[['aileron_deg', -1.0]], note='+aileron_deg = right roll => port TE down (-q)'),
    'aileron_stbd_hinge': dict(terms=[['aileron_deg', 1.0]], note='+aileron_deg = right roll => stbd TE up (+q)'),
    'elevator_hinge': dict(terms=[['elevator_deg', 1.0]]),
    'rudder_hinge': dict(terms=[['rudder_deg', 1.0]]),
    'reverse_bucket_port_hinge': dict(terms=[['reverse_bucket', 85.0]], note='fraction x 85 deg'),
    'reverse_bucket_stbd_hinge': dict(terms=[['reverse_bucket', 85.0]], note='fraction x 85 deg'),
    'ski_port_incidence': dict(terms=[['ski_incidence_deg', 1.0], ['ski_differential_deg', 1.0]], clip_deg=[j0s, ski_hi],
                               note='collective + differential, clipped to the joint range and the rod stroke'),
    'ski_stbd_incidence': dict(terms=[['ski_incidence_deg', 1.0], ['ski_differential_deg', -1.0]], clip_deg=[j0s, ski_hi],
                               note='collective - differential, clipped to the joint range and the rod stroke'),
}


def mapped_deg(joint, cmd):
    spec = COMMAND_MAP[joint]
    v = sum(float(cmd.get(ch, 0.0)) * g for ch, g in spec['terms'])
    if 'clip_deg' in spec:
        v = min(max(v, spec['clip_deg'][0]), spec['clip_deg'][1])
    return v


# --- static rig -------------------------------------------------------------------------------------------------
nodes = glb_nodes(CONCEPT_A_GLB)
visual_by_body = {}
for part_key, node_name, role, _pin, _off, body in CONCEPT_A_AIRFRAME_NODE_SPECS:
    visual_by_body.setdefault(body, []).append(dict(part=part_key, node=node_name, material_role=role))

RIG_BODIES = [s['body'] for s in ARTICULATED_CHILD_SPECS] + ['sponson_port', 'sponson_stbd', 'ski_port', 'ski_stbd']
rig = {}
node_err = 0.0
for name in RIG_BODIES:
    b = bid(name)
    p, R, chain = static_pose_in_airframe(b)
    joints = [j for j in range(m.njnt) if int(m.jnt_bodyid[j]) == b]
    jinfo = []
    for j in joints:
        jt = int(m.jnt_type[j])
        jinfo.append(dict(
            name=mj.mj_id2name(m, mj.mjtObj.mjOBJ_JOINT, j),
            type={2: 'slide', 3: 'hinge'}.get(jt, str(jt)),
            pos_af=(p + R @ m.jnt_pos[j]).tolist(),
            axis_af=(R @ m.jnt_axis[j]).tolist(),
            limited=bool(m.jnt_limited[j]),
            range=[float(math.degrees(x)) if jt == 3 else float(x) for x in m.jnt_range[j]],
            range_unit='deg' if jt == 3 else 'm',
        ))
    vis = []
    for v in visual_by_body.get(name, []):
        nd = nodes.get(v['node'], {})
        tg = nd.get('translation', [0.0, 0.0, 0.0])
        t_vtx = [tg[0], -tg[2], tg[1]]
        err = float(np.linalg.norm(np.asarray(t_vtx) - p))
        node_err = max(node_err, err)
        vis.append(dict(v, glb_translation_vtx=t_vtx, origin_mismatch_m=round(err, 6)))
    rig[name] = dict(chain=chain, origin_af=p.tolist(), R_af=R.tolist(), joints=jinfo, visual_nodes=vis)

# --- kinematic checks on the exported visual meshes ---------------------------------------------------------------
vg = c.visual_geometry()
mesh_by_part = {s['name']: s for s in vg['meshes']}


def verts(spec):
    return np.asarray(spec['vertices'], dtype=np.float64).reshape(-1, 3) + np.asarray(spec.get('offset', [0, 0, 0]))


def faces(spec):
    return np.asarray(spec['faces'], dtype=np.int64).reshape(-1, 3)


def rot(axis, ang):
    a = np.asarray(axis, dtype=np.float64)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def inside_mesh(points, V, F):
    """Ray-parity point-in-closed-mesh test (one skewed ray direction)."""
    dvec = np.array([0.5772, 0.5781, 0.5766])
    dvec /= np.linalg.norm(dvec)
    v0 = V[F[:, 0]]
    e1 = V[F[:, 1]] - v0
    e2 = V[F[:, 2]] - v0
    h = np.cross(dvec, e2)
    a = (e1 * h).sum(1)
    ok = np.abs(a) > 1e-14
    inv = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    out = np.zeros(len(points), dtype=bool)
    for i0 in range(0, len(points), 48):
        P = points[i0:i0 + 48]
        s = P[:, None, :] - v0[None]
        u = (s * h[None]).sum(2) * inv
        q = np.cross(s, e1[None])
        vv = (q * dvec).sum(2) * inv
        t = (q * e2[None]).sum(2) * inv
        hit = ok[None] & (u >= 0) & (u <= 1) & (vv >= 0) & (u + vv <= 1) & (t > 1e-9)
        out[i0:i0 + 48] = hit.sum(1) % 2 == 1
    return out


NEIGHBOUR = {
    'aileron_port': ['wing_port'], 'aileron_stbd': ['wing_stbd'],
    'elevator': ['tail_pylon_t_tail'], 'rudder': ['tail_pylon_t_tail'],
    'reverse_bucket_port': ['duct_port'], 'reverse_bucket_stbd': ['duct_stbd'],
}
kin = {}
for body, neighbours in NEIGHBOUR.items():
    r = rig[body]
    jt = r['joints'][0]
    p0 = np.asarray(r['origin_af'])
    Rb = np.asarray(r['R_af'])
    axis_af = np.asarray(jt['axis_af'])
    axis_af /= np.linalg.norm(axis_af)
    piv_af = np.asarray(jt['pos_af'])
    spec = mesh_by_part[body]
    V_af = (Rb @ verts(spec).T).T + p0
    rel = V_af - piv_af
    radial = rel - np.outer(rel @ axis_af, axis_af)
    dist = np.linalg.norm(radial, axis=1)
    te = dist >= np.percentile(dist, 97)
    q_test = math.radians(5.0)
    te_c = V_af[te].mean(0)
    te_move = (rot(axis_af, q_test) @ (te_c - piv_af) + piv_af) - te_c
    fixed = [(verts(mesh_by_part[n]), faces(mesh_by_part[n])) for n in neighbours]
    lo, hi = jt['range']
    interference = {}
    for qd in sorted({lo, 0.0, hi}):
        Vq = (rot(axis_af, math.radians(qd)) @ rel.T).T + piv_af
        n_in = 0
        r_in = []
        for Vf, Ff in fixed:
            mask = inside_mesh(Vq, Vf, Ff)
            n_in += int(mask.sum())
            r_in += dist[mask].tolist()
        interference[f'{qd:+.0f}deg'] = dict(vertices_inside_neighbour=n_in, of=int(len(Vq)),
                                             max_radius_from_hinge_m=round(max(r_in), 4) if r_in else 0.0)
    kin[body] = dict(
        hinge_axis_to_nearest_vertex_m=round(float(dist.min()), 4),
        surface_chord_from_hinge_m=round(float(dist.max()), 4),
        te_motion_for_plus5deg_af_m=[round(float(x), 4) for x in te_move],
        interference_at_travel=interference,
    )

# --- bench sweep in MuJoCo ----------------------------------------------------------------------------------------
BASE = dict(throttle=0.0, differential_thrust=0.0, rudder_deg=0.0, elevator_deg=0.0, aileron_deg=0.0,
            reverse_bucket=0.0, ski_incidence_deg=0.0, ski_differential_deg=0.0)
SEQ = [
    ('neutral', 0.6, {}),
    ('aileron +25 (right roll)', 1.0, dict(aileron_deg=25.0)),
    ('aileron -25 (left roll)', 1.2, dict(aileron_deg=-25.0)),
    ('aileron 0', 0.8, {}),
    ('elevator +20', 1.0, dict(elevator_deg=20.0)),
    ('elevator -20', 1.2, dict(elevator_deg=-20.0)),
    ('elevator 0', 0.8, {}),
    ('rudder +30', 1.2, dict(rudder_deg=30.0)),
    ('rudder -30', 1.5, dict(rudder_deg=-30.0)),
    ('rudder 0', 1.0, {}),
    ('reverse buckets deployed', 1.8, dict(reverse_bucket=1.0)),
    ('reverse buckets stowed', 1.8, {}),
    ('ski collective 10', 1.4, dict(ski_incidence_deg=10.0)),
    ('ski differential +4', 1.2, dict(ski_incidence_deg=10.0, ski_differential_deg=4.0)),
    ('ski differential -4', 1.4, dict(ski_incidence_deg=10.0, ski_differential_deg=-4.0)),
    ('ski differential 0', 1.2, dict(ski_incidence_deg=10.0)),
    ('ski collective 0', 1.4, {}),
    ('combined', 1.5, dict(aileron_deg=25.0, elevator_deg=-20.0, rudder_deg=30.0, reverse_bucket=0.5, ski_incidence_deg=6.0)),
    ('neutral', 1.5, {}),
    ('fans 35% throttle', 4.0, dict(throttle=0.35)),
    ('fans throttle 0', 3.0, {}),
]
JOINTS = list(COMMAND_MAP)
FANS = ['fan_rotor_port_hinge', 'fan_rotor_stbd_hinge']
POSE_BODIES = [b for b in RIG_BODIES]


def jq(name):
    j = c.jids[name]
    return float(d.qpos[m.jnt_qposadr[j]])


frames = []
segments = []
t = 0.0
n_frame = 0
dt = float(c.DT)
for label, dur, extra in SEQ:
    cmd = dict(BASE, **extra)
    c.set_command(cmd)
    seg = dict(label=label, t0=round(t, 4), dur=dur, command=cmd, settle_s={}, peak_rate_deg_s={})
    prev = {jn: jq(jn) for jn in JOINTS}
    steps = int(round(dur / dt))
    for i in range(steps):
        c.step()
        t += dt
        for jn in JOINTS:
            q = jq(jn)
            rate = abs(math.degrees(q - prev[jn])) / dt
            seg['peak_rate_deg_s'][jn] = max(seg['peak_rate_deg_s'].get(jn, 0.0), rate)
            prev[jn] = q
            if jn not in seg['settle_s'] and abs(math.degrees(q) - mapped_deg(jn, cmd)) < 0.5:
                seg['settle_s'][jn] = round(t - seg['t0'], 4)
        if t + 1e-9 >= n_frame / FPS:
            Raf = d.xmat[AF].reshape(3, 3)
            paf = d.xpos[AF]
            poses = {}
            for bn in POSE_BODIES:
                b = bid(bn)
                Rr = Raf.T @ d.xmat[b].reshape(3, 3)
                poses[bn] = dict(p=[round(float(x), 6) for x in Raf.T @ (d.xpos[b] - paf)],
                                 q=[round(float(x), 7) for x in mat_quat(Rr)])
            frames.append(dict(
                frame=n_frame, t=round(t, 4), segment=label, command=cmd,
                joints_deg={jn: round(math.degrees(jq(jn)), 4) for jn in JOINTS},
                fans_deg={fn: round(math.degrees(jq(fn)), 3) for fn in FANS},
                fan_rpm=[round(float(x), 1) for x in c.last_fan_rpm],
                poses_af=poses,
            ))
            n_frame += 1
    seg['end_deg'] = {jn: round(math.degrees(jq(jn)), 3) for jn in JOINTS}
    seg['expected_deg'] = {jn: round(mapped_deg(jn, cmd), 3) for jn in JOINTS}
    seg['end_error_deg'] = {jn: round(seg['end_deg'][jn] - seg['expected_deg'][jn], 3) for jn in JOINTS}
    seg['peak_rate_deg_s'] = {k: round(v, 1) for k, v in seg['peak_rate_deg_s'].items()}
    segments.append(seg)
    print(f"{label:28s} worst end error {max(abs(v) for v in seg['end_error_deg'].values()):.3f} deg", flush=True)

worst_end = max(abs(v) for s in segments for v in s['end_error_deg'].values())
spec = dict(
    method=__doc__,
    profile=PROFILE,
    frame='VTX airframe body frame = GLB frame (+X forward, +Y port, +Z up), metres',
    glb=str(CONCEPT_A_GLB.relative_to(WT)) if str(CONCEPT_A_GLB).startswith(str(WT)) else str(CONCEPT_A_GLB),
    bodies=rig,
    glb_node_vs_mujoco_origin_max_m=round(node_err, 6),
    command_map=COMMAND_MAP,
    channel_limits=c.surface_limits,
    actuator_envelopes={k: v for k, v in c.profile['_env'].items()},
    ski_actuator_envelope=c.profile['_ski_env'],
    actuator_mounts_vtx_m=c.profile['actuator_mounts_vtx_m'],
    surface_actuators=c.profile['surface_actuators'],
    components={k: c.profile['_components'][k] for k in sorted({a['component'] for a in c.profile['surface_actuators'].values()}
                                                                 | {ski['actuator']['component']})},
    ski=ski,
    kinematics=kin,
)
json.dump(spec, open(OUT / 'rig_spec.json', 'w'), indent=1, default=str)
json.dump(dict(fps=FPS, dt=dt, segments=segments, worst_end_error_deg=worst_end,
               actuator_time_above_rated_s=c._act_above_rated_s, frames=frames),
          open(OUT / 'sweep.json', 'w'), indent=None, default=str)
print(json.dumps(dict(glb_node_vs_mujoco_origin_max_m=round(node_err, 6), worst_end_error_deg=worst_end,
                      frames=len(frames), kinematics=kin, above_rated_s=c._act_above_rated_s,
                      wall_s=round(time.time() - t_wall, 1)), indent=1))
