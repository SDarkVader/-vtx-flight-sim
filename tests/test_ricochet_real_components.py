"""Verification tests for Ricochet RC-01 real-component profiles, SWE reflective walls,
HarbourFleet 100 Hz integration, rudder hinge cove clearance, and Option 1 vs Option 2
hydrodynamic architecture comparison under MuJoCo."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import mujoco as mj
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from test_harbour_fleet import harbour_world
from vtx.harbour_fleet import DT as FLEET_DT, HarbourFleet
from vtx.harbour_session import _restart_boat
from vtx.ricochet.concept_a_builder import (
    RUDDER_AXIS,
    RUDDER_HINGE_VTX,
    build_pass3_rudder,
    build_pass3_tail_pylon_t_tail,
)
from vtx.ricochet.live import RicochetAction, normalize_ricochet_action
from vtx.ricochet.plant import RICOCHET_SURFACE_LIMITS, RicochetCraft
from vtx.water.datum import WaterEnvironmentConfig
from vtx.water.shallow_water import ShallowWaterSolver

ROOT = Path(__file__).resolve().parents[1]
LEGACY_GLB_SHA256 = '00f7d9cff2092fe433c9b66a0846774724de26486e92ba592736cd2ae1647124'


def _open_lake_world(half_x: float = 1200.0, half_y: float = 400.0, bed_z: float = 2.0, wl: float = 7.0):
    """Wide uniform-depth basin for unobstructed straight-line acceleration tests."""
    return SimpleNamespace(
        id='isolated-open-lake',
        version='1',
        environment_key='ricochet_lake',
        seed=41032,
        nx=81,
        ny=41,
        half_x=half_x,
        half_y=half_y,
        z_min=0.0,
        z_max=20.0,
        heights=np.full((41, 81), bed_z, dtype=np.float64),
        water_level=wl,
        structures=[],
        buoys=[],
        terrain_z=lambda x, y: bed_z,
        terrain_z_array=lambda xg, yg: np.full_like(np.asarray(xg, dtype=np.float64), bed_z),
    )


def _inside_mesh_ray_parity(points: np.ndarray, V: np.ndarray, F: np.ndarray) -> np.ndarray:
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


def test_swe_reflective_walls_lake_at_rest_and_pulse_conservation():
    world = HarbourFleet(harbour_world()).world
    cfg = WaterEnvironmentConfig(water_level_m=7.0, wave_mode='still', wind_speed_mps=0.0, current_speed_mps=0.0)
    swe = ShallowWaterSolver(world, cfg, nx=61, ny=41)
    assert float(np.min(swe.h)) == pytest.approx(5.0)

    # Lake-at-rest C-property on a wet-wall basin (no dry halo) over 10 s
    for _ in range(100):
        swe.step(0.1)
    assert float(np.max(np.abs(swe.h - 5.0))) < 1e-12
    assert float(np.max(np.abs(swe.hu))) < 1e-12
    assert float(np.max(np.abs(swe.hv))) < 1e-12

    # Off-center solitary pulse reflecting off walls must conserve mass to machine precision
    swe.inject_solitary_pulse(-160.0, 0.0, amp_m=0.35, sigma_m=22.0)
    for _ in range(150):
        swe.step(0.1)
    metrics = swe.conservation_metrics()
    assert metrics['relative_mass_error'] < 1e-13
    assert np.all(np.isfinite(swe.h))
    assert float(np.max(swe.h)) < 6.0


def test_legacy_concept_a_unchanged_without_profile():
    glb = ROOT / 'public' / 'assets' / 'ricochet-concept-a.glb'
    assert hashlib.sha256(glb.read_bytes()).hexdigest() == LEGACY_GLB_SHA256

    world = HarbourFleet(harbour_world()).world
    cfg = WaterEnvironmentConfig(water_level_m=7.0, wave_mode='still', wake_enabled=False, whirlpools_enabled=False)
    legacy = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-01', water_config=cfg)
    assert legacy.profile is None
    assert legacy.surface_limits is RICOCHET_SURFACE_LIMITS
    assert set(legacy.command) == set(RICOCHET_SURFACE_LIMITS)
    assert 'ski_port' not in legacy.bids
    vg = legacy.visual_geometry()
    names = {m['name'] for m in vg['meshes']}
    assert 'ski_port' not in names and 'ski_stbd' not in names and 'ski_strut_port' not in names
    legacy.spawn(-180.0, 0.0, 7.0)
    for _ in range(40):
        legacy.step()
    snap = legacy.physical_snapshot()
    assert 'profile_id' not in snap
    assert 'skis' not in snap['control_surfaces']


def test_rudder_cove_zero_interference_at_full_travel():
    v_fin, f_fin, _, _ = build_pass3_tail_pylon_t_tail()
    v_rud, _, _, _ = build_pass3_rudder(rudder_cove_clear=True)
    piv = np.asarray(RUDDER_HINGE_VTX, dtype=np.float64)
    axis = np.asarray(RUDDER_AXIS, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    for q_deg in (-30.0, 0.0, 30.0):
        rot = Rotation.from_rotvec(math.radians(q_deg) * axis).as_matrix()
        v_af = (rot @ v_rud.T).T + piv
        inside = _inside_mesh_ray_parity(v_af, v_fin, f_fin)
        assert int(inside.sum()) == 0, f'Rudder interferes with fin at {q_deg} deg: {int(inside.sum())} verts'


def test_rest_bench_sweep_passive_and_tracks_skis():
    world = HarbourFleet(harbour_world()).world
    cfg = WaterEnvironmentConfig(water_level_m=7.0, wave_mode='still', wind_speed_mps=0.0, current_speed_mps=0.0,
                                 wake_enabled=False, whirlpools_enabled=False)
    craft = RicochetCraft(world, variant='ricochet-concept-a', hull_variant='concept_a', load_case='LC-01',
                          water_config=cfg, profile='rc01-real-components-v1')
    craft.spawn(-180.0, 0.0, 7.0)
    # Full sequence reproducing PR #66 Blocker #1 (surface sweeps then ski collective & differential holds)
    plan = [
        (0.6, {}),
        (1.0, dict(aileron_deg=25.0)), (1.2, dict(aileron_deg=-25.0)), (0.8, {}),
        (1.0, dict(elevator_deg=20.0)), (1.2, dict(elevator_deg=-20.0)), (0.8, {}),
        (1.2, dict(rudder_deg=30.0)), (1.5, dict(rudder_deg=-30.0)), (1.0, {}),
        (1.8, dict(reverse_bucket=1.0)), (1.8, {}),
        (1.4, dict(ski_incidence_deg=10.0)),
        (1.2, dict(ski_incidence_deg=10.0, ski_differential_deg=4.0)),
        (1.4, dict(ski_incidence_deg=10.0, ski_differential_deg=-4.0)),
    ]
    base = dict(throttle=0.0, differential_thrust=0.0, rudder_deg=0.0, elevator_deg=0.0,
                aileron_deg=0.0, reverse_bucket=0.0, ski_incidence_deg=0.0, ski_differential_deg=0.0)
    max_z = -1e9
    min_z = 1e9
    max_pitch_deg = 0.0
    max_ski_hm = 0.0
    end_skis = []
    af = craft.bids['airframe']
    for dur, extra in plan:
        craft.set_command(dict(base, **extra))
        for _ in range(int(round(dur / craft.DT))):
            craft.step()
            z = float(craft.data.xpos[af, 2])
            max_z = max(max_z, z)
            min_z = min(min_z, z)
            eul = Rotation.from_matrix(craft.data.xmat[af].reshape(3, 3)).as_euler('xyz', degrees=True)
            max_pitch_deg = max(max_pitch_deg, abs(float(eul[1])))
            for side in ('port', 'stbd'):
                max_ski_hm = max(max_ski_hm, abs(float(craft._act_load_nm.get(f'ski_{side}_actuator', 0.0))))
        if 'ski_differential_deg' in extra:
            qp, _ = craft.joint('ski_port_incidence')
            qs, _ = craft.joint('ski_stbd_incidence')
            end_skis.append((extra['ski_differential_deg'], math.degrees(qp), math.degrees(qs)))

    assert 6.30 <= min_z and max_z <= 6.55, f'Airframe heave drifted at rest: [{min_z:.3f}, {max_z:.3f}]'
    assert max_pitch_deg < 2.5, f'Excessive pitch at rest: {max_pitch_deg:.2f} deg'
    assert max_ski_hm < 100.0, f'Excessive rest ski hinge moment: {max_ski_hm:.1f} Nm'
    # +4 diff -> port clipped at 12 deg, stbd at 6 deg; -4 diff -> port 6 deg, stbd 12 deg
    assert end_skis[0][1] == pytest.approx(12.0, abs=0.15)
    assert end_skis[0][2] == pytest.approx(6.0, abs=0.15)
    assert end_skis[1][1] == pytest.approx(6.0, abs=0.15)
    assert end_skis[1][2] == pytest.approx(12.0, abs=0.15)
    assert not craft.capsized


def test_harbour_fleet_profile_100hz_stop_restart_and_bit_exact_restore():
    world = harbour_world()
    vessels = [
        dict(id='rc01-legacy', name='Legacy Concept A', variant='ricochet-concept-a', berth_id='airport-landing-ricochet'),
        dict(id='rc01-opt1', name='RC-01 3-Pt Planing', variant='ricochet-concept-a', berth_id='lantern-marina-ricochet',
             profile='rc01-planing-3pt-v1'),
    ]
    fleet = HarbourFleet(world, vessels=vessels)
    vg_legacy = fleet.visual_geometry('rc01-legacy')
    vg_opt1 = fleet.visual_geometry('rc01-opt1')
    assert 'ski_port' not in {m['name'] for m in vg_legacy['meshes']}
    opt1_names = {m['name'] for m in vg_opt1['meshes']}
    assert {'ski_port', 'ski_stbd', 'ski_strut_port', 'ski_strut_stbd', 'ski_aft', 'ski_strut_aft'}.issubset(opt1_names)

    # Channel validation strictly follows per-boat surface_limits
    with pytest.raises(ValueError, match='Unknown harbour control channel'):
        fleet.action('rc01-legacy', {'ski_incidence_deg': 4.0})
    assert fleet.release('rc01-opt1')['ok']
    assert fleet.action('rc01-opt1', {'throttle': 0.25, 'ski_incidence_deg': 5.0, 'ski_differential_deg': 1.5, 'ecu_assist': 0.0})['ok']
    for _ in range(15):
        fleet.step()

    # Serialize / restore must be bit-exact for profiled + legacy mixed fleet at 100 Hz
    state = json.loads(json.dumps(fleet.serialize(), allow_nan=False))
    restored = HarbourFleet.restore(world, state)
    assert restored.crafts['rc01-opt1'].profile_id == 'rc01-planing-3pt-v1'
    assert restored.crafts['rc01-legacy'].profile_id is None
    for _ in range(20):
        fleet.step()
        restored.step()
        np.testing.assert_allclose(fleet.data.qpos, restored.data.qpos, atol=1e-12, rtol=0)
        np.testing.assert_allclose(fleet.data.qvel, restored.data.qvel, atol=1e-11, rtol=0)

    # harbour_session._restart_boat preserves profile_id (test on valid-clock restored fleet before raw mj_step)
    restored.select('rc01-opt1')
    restarted = _restart_boat(world, restored, {'boatId': 'rc01-opt1'})
    assert restarted.crafts['rc01-opt1'].profile_id == 'rc01-planing-3pt-v1'

    # 100 Hz ski hard-stop slam test (-2,500 N m external slam against -3 deg stop)
    craft_opt1 = fleet.crafts['rc01-opt1']
    jid_p = craft_opt1.jids['ski_port_incidence']
    ov = int(craft_opt1.model.jnt_dofadr[jid_p])
    sv = next(sv_i for _, _, _, ov_i, sv_i, _ in fleet.mappings['rc01-opt1']['joints'] if ov_i == ov)
    oq = int(craft_opt1.model.jnt_qposadr[jid_p])
    sq = next(sq_i for oq_i, sq_i, _, _, _, _ in fleet.mappings['rc01-opt1']['joints'] if oq_i == oq)
    min_q_deg = 1e9
    for _ in range(30):
        fleet.data.qfrc_applied[sv] = -2500.0
        mj.mj_step(fleet.model, fleet.data)
        min_q_deg = min(min_q_deg, math.degrees(float(fleet.data.qpos[sq])))
    settled_q_deg = math.degrees(float(fleet.data.qpos[sq]))
    assert min_q_deg >= -3.85, f'100 Hz ski hard stop transient overshoot too far: {min_q_deg:.2f} deg'
    assert settled_q_deg >= -3.35, f'100 Hz ski hard stop settled penetration too far: {settled_q_deg:.2f} deg'

    # Extended RicochetAction schema accepts ski & ECU channels cleanly
    norm = normalize_ricochet_action({'ski_incidence': 6.0, 'ski_diff': -2.0, 'aft_ski': 1.5, 'ecu': 0.8})
    act = RicochetAction.model_validate(norm)
    assert act.ski_incidence_deg == pytest.approx(6.0)
    assert act.ski_differential_deg == pytest.approx(-2.0)
    assert act.aft_ski_incidence_deg == pytest.approx(1.5)
    assert act.ecu_assist == pytest.approx(0.8)


def _run_accel_profile(profile_id: str, duration_s: float = 24.0) -> dict:
    world = _open_lake_world(half_x=1400.0, half_y=400.0)
    cfg = WaterEnvironmentConfig(
        water_level_m=7.0, wave_mode='still', wind_speed_mps=0.0,
        current_speed_mps=0.0, wake_enabled=True, whirlpools_enabled=False,
    )
    craft = RicochetCraft(
        world, variant='ricochet-concept-a', hull_variant='concept_a',
        load_case='LC-01', water_config=cfg, profile=profile_id, hydro_stride=2,
    )
    craft.spawn(-1100.0, 0.0, 7.0)
    # Settle 1.5 s at rest to verify static trim & waterline
    for _ in range(int(round(1.5 / craft.DT))):
        craft.step()
    af = craft.bids['airframe']
    eul0 = Rotation.from_matrix(craft.data.xmat[af].reshape(3, 3)).as_euler('xyz', degrees=True)
    rest_z = float(craft.data.xpos[af, 2])
    rest_pitch_deg = float(eul0[1])
    rest_vol_hull = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
    rest_vol_sp = float(
        craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
        + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
    )

    # Full throttle straight run with on-board speed-scheduled ECU driving real actuators
    craft.set_command({'throttle': 1.0, 'ecu_assist': 1.0})
    steps = int(round(duration_s / craft.DT))
    max_u = 0.0
    min_vol_hull = 1e9
    min_vol_sp = 1e9
    max_roll = 0.0
    max_yaw = 0.0
    min_pitch = 1e9
    max_pitch = -1e9
    max_ski_hm = 0.0
    max_aft_hm = 0.0
    hump_clear_t = None
    hull_clear_t = None
    max_eta_err = 0.0
    samples = []
    t_run = 0.0
    for i in range(steps):
        craft.step()
        t_run += craft.DT
        rot = craft.data.xmat[af].reshape(3, 3)
        vel6 = np.zeros(6, dtype=np.float64)
        mj.mj_objectVelocity(craft.model, craft.data, mj.mjtObj.mjOBJ_BODY, af, vel6, 0)
        u = float((rot.T @ vel6[3:])[0])
        eul = Rotation.from_matrix(rot).as_euler('xyz', degrees=True)
        vh = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
        vsp = float(
            craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
            + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
        )
        max_u = max(max_u, u)
        min_vol_hull = min(min_vol_hull, vh)
        min_vol_sp = min(min_vol_sp, vsp)
        max_roll = max(max_roll, abs(float(eul[0])))
        max_yaw = max(max_yaw, abs(float(eul[2])))
        min_pitch = min(min_pitch, float(eul[1]))
        max_pitch = max(max_pitch, float(eul[1]))
        if hump_clear_t is None and u >= 12.0:
            hump_clear_t = round(t_run, 2)
        if hull_clear_t is None and vh < 0.02:
            hull_clear_t = round(t_run, 2)
        for side in ('port', 'stbd'):
            max_ski_hm = max(max_ski_hm, abs(float(craft._act_load_nm.get(f'ski_{side}_actuator', 0.0))))
        max_aft_hm = max(max_aft_hm, abs(float(craft._act_load_nm.get('ski_aft_actuator', 0.0))))
        max_eta_err = max(max_eta_err, abs(float(craft.last_hydro.waterline_z_world_mean) - 7.0))
        if i % 800 == 0 or i == steps - 1:
            samples.append(dict(
                t_s=round(t_run, 2),
                u_mps=round(u, 2),
                z_m=round(float(craft.data.xpos[af, 2]), 3),
                nose_up_deg=round(-float(eul[1]), 2),
                roll_deg=round(float(eul[0]), 2),
                yaw_deg=round(float(eul[2]), 2),
                vol_hull_m3=round(vh, 4),
                vol_sp_m3=round(vsp, 4),
                ski_port_deg=round(float(craft.last_ski_telemetry.get('port', {}).get('incidence_deg', 0.0)), 2),
                ski_regime=craft.last_ski_telemetry.get('port', {}).get('regime'),
                ski_hm_nm=round(float(craft._act_load_nm.get('ski_port_actuator', 0.0)), 1),
                aft_deg=round(float(craft.last_ski_telemetry.get('aft', {}).get('incidence_deg', 0.0)), 2),
                elev_deg=round(math.degrees(craft.joint('elevator_hinge')[0]), 2),
                thrust_tot_n=round(sum(craft.last_thrust_per_fan_n), 1),
            ))

    return dict(
        profile_id=profile_id,
        mass_kg=round(float(np.sum(craft.model.body_mass)), 2),
        rest_z_m=round(rest_z, 4),
        rest_nose_up_deg=round(-rest_pitch_deg, 2),
        rest_vol_hull_m3=round(rest_vol_hull, 4),
        rest_vol_sp_m3=round(rest_vol_sp, 4),
        max_speed_mps=round(max_u, 2),
        final_speed_mps=samples[-1]['u_mps'],
        hump_clear_12mps_s=hump_clear_t,
        hull_clear_t_s=hull_clear_t,
        min_vol_hull_m3=round(min_vol_hull, 5),
        min_vol_sp_m3=round(min_vol_sp, 5),
        nose_up_range_deg=[round(-max_pitch, 2), round(-min_pitch, 2)],
        max_abs_roll_deg=round(max_roll, 2),
        max_abs_yaw_deg=round(max_yaw, 2),
        max_ski_hinge_nm=round(max_ski_hm, 1),
        ski_rated_nm=round(float(craft.profile['_ski_env']['rated_nm']), 1),
        max_aft_hinge_nm=round(max_aft_hm, 1),
        aft_peak_nm=round(float(craft.profile['_aft_ski_env']['peak_nm']), 1),
        above_rated_s={k: round(v, 3) for k, v in craft._act_above_rated_s.items()},
        max_eta_err_m=round(max_eta_err, 4),
        capsized=bool(craft.capsized),
        flags=sorted(craft.flags),
        samples=samples,
    )


def test_option1_vs_option2_hump_clearance_and_stability():
    opt1 = _run_accel_profile('rc01-planing-3pt-v1', duration_s=22.0)
    opt2 = _run_accel_profile('rc01-hydrofoil-ski-v1', duration_s=22.0)
    out_path = ROOT / 'scratch' / 'complete_model' / 'option1_vs_option2_comparison.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({'option1': opt1, 'option2': opt2}, indent=2), encoding='utf-8')
    print('\n=== OPTION 1 (3-PT PLANING) ===')
    print(json.dumps({k: v for k, v in opt1.items() if k != 'samples'}, indent=2))
    print('=== OPTION 2 (HYDROFOIL-SKI) ===')
    print(json.dumps({k: v for k, v in opt2.items() if k != 'samples'}, indent=2))

    # Both architectures must preserve buoyant sponsons at rest, stay upright, and clear displacement hump!
    for res in (opt1, opt2):
        assert res['rest_vol_sp_m3'] > 0.12, f"{res['profile_id']} lost static sponson buoyancy at rest"
        assert not res['capsized'], f"{res['profile_id']} capsized during acceleration"
        assert res['max_abs_roll_deg'] < 10.0, f"{res['profile_id']} rolled excessively: {res['max_abs_roll_deg']}"
        assert res['max_abs_yaw_deg'] < 10.0, f"{res['profile_id']} broached/yawed: {res['max_abs_yaw_deg']}"
        assert res['max_speed_mps'] > 15.0, f"{res['profile_id']} failed to clear hump: {res['max_speed_mps']} m/s"
        assert res['min_vol_sp_m3'] < 0.005, f"{res['profile_id']} sponsons did not lift clear on plane"
