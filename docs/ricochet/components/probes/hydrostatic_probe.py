"""RC-01 Concept A hydrostatics from the plant's own meshes and MuJoCo mass model (offline, isolated).

For each load case: whole-vehicle CG from the built MuJoCo model (all bodies incl. sponsons and surfaces),
register CG for comparison, then a free-trim static solve on the exact hull + sponson meshes the plant
floats on: equilibrium draft and trim, CB, displacement split, waterplane areas, GM_T / GM_L and a GZ
curve to 60 deg heel. Also the CG shift from adding the selected actuators at their hinge bodies.
Usage: python hydrostatic_probe.py <worktree> <out.json>
"""
import json
import math
import sys

import mujoco as mj
import numpy as np

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.ricochet.spec_math import _waterplane_moments  # noqa: E402
from vtx.water.hydrodynamics import _clip_submerged_triangles, _submerged_volume_and_centroid  # noqa: E402

world = HarbourFleet(harbour_world()).world
ACTUATORS = {  # selected parts (docs/ricochet/components/components.json), mounted at the surface body
    'aileron_port': 1.85, 'aileron_stbd': 1.85, 'elevator': 1.85,
    'rudder': 5.6, 'reverse_bucket_port': 5.6, 'reverse_bucket_stbd': 5.6,
}


def rot(phi, theta):
    cx, sx, cy, sy = math.cos(phi), math.sin(phi), math.cos(theta), math.sin(theta)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return ry @ rx


def body_frame_meshes(c):
    m = c.model
    out = {'main_hull': (c.hull_bundle.main_hull._verts_body.copy(), c.hull_bundle.main_hull.mesh.faces)}
    af = c.bids['airframe']
    for key, comp in (('sponson_port', c.hull_bundle.port_sponson), ('sponson_stbd', c.hull_bundle.stbd_sponson)):
        bid = c.bids[key]
        assert int(m.body_parentid[bid]) == af, f'{key} not a direct child of airframe'
        q = m.body_quat[bid]
        assert np.allclose(q, [1, 0, 0, 0]), f'{key} body rotated {q}'
        out[key] = (comp._verts_body + m.body_pos[bid][None, :], comp.mesh.faces)
    return out


def solve(meshes, cg, mass, rho, phi, theta):
    """Waterline for weight == buoyancy at given heel/trim about CG. Returns CB (CG-relative, earth axes)."""
    placed = {k: ((v - cg) @ rot(phi, theta).T, f) for k, (v, f) in meshes.items()}
    target = mass / rho

    def vol(zwl, full=False):
        tot, mom, parts = 0.0, np.zeros(3), {}
        for k, (v, f) in placed.items():
            wet, _, _, cap = _clip_submerged_triangles(v, f, zwl - v[:, 2])
            if len(wet):
                vk, cbk = _submerged_volume_and_centroid(wet, cap, np.array([0.0, 0.0, zwl]))
            else:
                vk, cbk = 0.0, np.zeros(3)
            tot += vk
            mom += vk * np.asarray(cbk)
            parts[k] = (float(vk), np.asarray(cbk, dtype=float))
        return (tot, mom / max(tot, 1e-12), parts) if full else tot

    lo, hi = -3.0, 3.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if vol(mid) < target:
            lo = mid
        else:
            hi = mid
    zwl = 0.5 * (lo + hi)
    tot, cb, parts = vol(zwl, full=True)
    return zwl, tot, cb, parts, placed


def equilibrium_trim(meshes, cg, mass, rho):
    lo, hi = math.radians(-12), math.radians(12)
    for _ in range(40):  # CB_x(theta) increases as nose goes down (theta > 0)
        mid = 0.5 * (lo + hi)
        if solve(meshes, cg, mass, rho, 0.0, mid)[2][0] < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def analyse(load_case):
    c = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case=load_case)
    c.spawn(100.0, 100.0, 7.0)
    m, d = c.model, c.data
    af = c.bids['airframe']
    # MuJoCo whole-vehicle CG in airframe body frame (spawned level, heading 0)
    R_af = d.xmat[af].reshape(3, 3)
    cg_mj = R_af.T @ (d.subtree_com[af] - d.xpos[af])
    mass_mj = float(m.body_subtreemass[af])
    agg = c.mass_register.aggregate(include_sponsons=True)
    rho = float(c.water_config.rho_water_kg_m3)
    meshes = body_frame_meshes(c)
    keel_z = min(float(v[:, 2].min()) for v, _ in [meshes['main_hull']])

    th0 = equilibrium_trim(meshes, cg_mj, mass_mj, rho)
    zwl, tot, cb, parts, placed = solve(meshes, cg_mj, mass_mj, rho, 0.0, th0)
    # draft at the keel (earth z of lowest hull vertex below waterline)
    draft = zwl - float(placed['main_hull'][0][:, 2].min())
    awl = {k: round(_waterplane_moments(v, f, zwl)[0], 4) for k, (v, f) in placed.items()}

    def gz_roll(phi_deg):
        _, _, cbp, parts_p, _ = solve(meshes, cg_mj, mass_mj, rho, math.radians(phi_deg), th0)
        return float(-cbp[1]), {k: round(v[0], 4) for k, v in parts_p.items()}

    gz1, _ = gz_roll(1.0)
    gm_t = gz1 / math.sin(math.radians(1.0))
    _, _, cbt, _, _ = solve(meshes, cg_mj, mass_mj, rho, 0.0, th0 + math.radians(0.5))
    gm_l = float(cbt[0]) / math.sin(math.radians(0.5))
    curve = []
    for ph in (0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60):
        g, pv = gz_roll(float(ph))
        curve.append({'heel_deg': ph, 'gz_m': round(g, 4), 'righting_nm': round(g * mass_mj * 9.81, 0), 'vol_m3': pv})

    # actuator CG shift (masses placed at the surface child-body origin, airframe frame)
    m_add, mom_add, act_pos = 0.0, np.zeros(3), {}
    for bname, ma in ACTUATORS.items():
        bid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, bname)
        p = R_af.T @ (d.xpos[bid] - d.xpos[af]) if bid >= 0 else None
        act_pos[bname] = None if p is None else [round(float(x), 3) for x in p]
        if p is not None:
            m_add += ma
            mom_add += ma * p
    cg_act = (mass_mj * cg_mj + mom_add) / (mass_mj + m_add)

    return {
        'load_case': load_case,
        'register_description': agg.get('description'),
        'mass_register_kg': round(agg['total_mass_kg'], 2),
        'mass_mujoco_kg': round(mass_mj, 2),
        'cg_register_vtx_m': [round(float(x), 4) for x in agg['cg_vtx_m']],
        'cg_mujoco_body_m': [round(float(x), 4) for x in cg_mj],
        'airframe_body_origin_note': 'MuJoCo CG is in the airframe body frame; compare with register CG for frame offset',
        'inertia_diag_register': [round(float(x), 1) for x in agg['inertia_diag_vtx_kg_m2']],
        'equilibrium_trim_deg_nose_down_positive': round(math.degrees(th0), 3),
        'keel_draft_m': round(draft, 4),
        'waterline_above_cg_m': round(zwl, 4),
        'displacement_m3': round(tot, 4),
        'displacement_split_m3': {k: round(v[0], 4) for k, v in parts.items()},
        'cb_rel_cg_earth_m': [round(float(x), 4) for x in cb],
        'cb_body_m': [round(float(x), 4) for x in (cg_mj + rot(0.0, th0).T @ cb)],
        'waterplane_area_m2': awl,
        'gm_t_m': round(gm_t, 4),
        'gm_l_m': round(gm_l, 3),
        'gz_curve': curve,
        'actuators_added_kg': m_add,
        'actuator_positions_body_m': act_pos,
        'cg_with_actuators_body_m': [round(float(x), 4) for x in cg_act],
        'cg_shift_from_actuators_m': [round(float(x), 4) for x in (cg_act - cg_mj)],
        'keel_z_body_m': round(keel_z, 4),
    }


res = {'method': __doc__, 'cases': []}
for lc in ('LC-03', 'LC-01', 'LC-05'):
    r = analyse(lc)
    res['cases'].append(r)
    print(json.dumps({k: r[k] for k in r if k != 'gz_curve'}, indent=1), flush=True)
    print('GZ:', [(g['heel_deg'], g['gz_m']) for g in r['gz_curve']], flush=True)
json.dump(res, open(sys.argv[2], 'w'), indent=1)
