"""Quantitative MuJoCo side-by-side comparison: Legacy vs Baseline vs Option 1 (3-Pt Planing) vs Option 2 (Hydrofoil Skis).

All runs use real physical limits (2x EMRAX 228, Volz DA 30-HT-D / DA 58-D, Exlar GSX30),
full 2-D SWE + Kelvin wake, real Raymer aero drag, and real strut + spray + cavitation/ventilation drag.
Usage: python docs/ricochet/complete_model/compare_hydro_options.py <worktree> <out_dir>
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time
from types import SimpleNamespace

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

WT = pathlib.Path(sys.argv[1]).resolve()
OUT = pathlib.Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WT / 'src'))
sys.path.insert(0, str(WT / 'tests'))

from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402
from vtx.harbour_session import _restart_boat  # noqa: E402
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402
from vtx.water.shallow_water import ShallowWaterSolver  # noqa: E402


def open_lake_world(half_x: float = 1500.0, half_y: float = 400.0, bed_z: float = 2.0, wl: float = 7.0):
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


def check_swe_and_fleet() -> dict:
    world = HarbourFleet(harbour_world()).world
    cfg = WaterEnvironmentConfig(water_level_m=7.0, wave_mode='still', wind_speed_mps=0.0, current_speed_mps=0.0)
    swe = ShallowWaterSolver(world, cfg, nx=61, ny=41)
    for _ in range(100):
        swe.step(0.1)
    lake_at_rest_err = float(np.max(np.abs(swe.h - 5.0)))
    swe.inject_solitary_pulse(-160.0, 0.0, amp_m=0.35, sigma_m=22.0)
    for _ in range(150):
        swe.step(0.1)
    pulse_mass_err = float(swe.conservation_metrics()['relative_mass_error'])

    # 100 Hz HarbourFleet mixed legacy + profiled save/restore + slam stop + restart
    hw = harbour_world()
    vessels = [
        dict(id='rc01-legacy', name='Legacy Concept A', variant='ricochet-concept-a', berth_id='airport-landing-ricochet'),
        dict(id='rc01-opt1', name='RC-01 3-Pt Planing', variant='ricochet-concept-a', berth_id='lantern-marina-ricochet',
             profile='rc01-planing-3pt-v1'),
    ]
    fleet = HarbourFleet(hw, vessels=vessels)
    assert fleet.release('rc01-opt1')['ok']
    assert fleet.action('rc01-opt1', {'throttle': 0.25, 'ski_incidence_deg': 5.0, 'ski_differential_deg': 1.5, 'ecu_assist': 0.0})['ok']
    for _ in range(15):
        fleet.step()
    state = json.loads(json.dumps(fleet.serialize(), allow_nan=False))
    restored = HarbourFleet.restore(hw, state)
    max_qpos_diff = 0.0
    for _ in range(20):
        fleet.step()
        restored.step()
        max_qpos_diff = max(max_qpos_diff, float(np.max(np.abs(fleet.data.qpos - restored.data.qpos))))

    restored.select('rc01-opt1')
    restarted = _restart_boat(hw, restored, {'boatId': 'rc01-opt1'})
    restart_preserved = restarted.crafts['rc01-opt1'].profile_id == 'rc01-planing-3pt-v1'

    # 100 Hz -2500 Nm external slam against -3 deg stop (isolated on fleet copy)
    craft = fleet.crafts['rc01-opt1']
    jid_p = craft.jids['ski_port_incidence']
    ov = int(craft.model.jnt_dofadr[jid_p])
    sv = next(sv_i for _, _, _, ov_i, sv_i, _ in fleet.mappings['rc01-opt1']['joints'] if ov_i == ov)
    oq = int(craft.model.jnt_qposadr[jid_p])
    sq = next(sq_i for oq_i, sq_i, _, _, _, _ in fleet.mappings['rc01-opt1']['joints'] if oq_i == oq)
    min_q_deg = 1e9
    for _ in range(30):
        fleet.data.qfrc_applied[sv] = -2500.0
        mj.mj_step(fleet.model, fleet.data)
        min_q_deg = min(min_q_deg, math.degrees(float(fleet.data.qpos[sq])))
    return dict(
        swe_lake_at_rest_err_m=lake_at_rest_err,
        swe_pulse_rel_mass_err=pulse_mass_err,
        fleet_100hz_restore_max_qpos_diff=max_qpos_diff,
        fleet_100hz_slam_min_q_deg=round(min_q_deg, 3),
        restart_preserved_profile=restart_preserved,
    )


def run_profile_trial(profile_id: str | None, duration_s: float = 26.0) -> dict:
    world = open_lake_world()
    cfg = WaterEnvironmentConfig(
        water_level_m=7.0, wave_mode='still', wind_speed_mps=0.0,
        current_speed_mps=0.0, wake_enabled=True, whirlpools_enabled=False,
    )
    craft = RicochetCraft(
        world, variant='ricochet-concept-a', hull_variant='concept_a',
        load_case='LC-01', water_config=cfg, profile=profile_id, hydro_stride=2,
    )
    craft.spawn(-1200.0, 0.0, 7.0)
    for _ in range(int(round(1.5 / craft.DT))):
        craft.step()
    af = craft.bids['airframe']
    eul0 = Rotation.from_matrix(craft.data.xmat[af].reshape(3, 3)).as_euler('xyz', degrees=True)
    rest_z = float(craft.data.xpos[af, 2])
    rest_nose_up = -float(eul0[1])
    rest_vol_h = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
    rest_vol_sp = float(
        craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
        + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
    )

    cmd = {'throttle': 1.0}
    if 'ecu_assist' in craft.command:
        cmd['ecu_assist'] = 1.0
    elif profile_id == 'rc01-real-components-v1':
        cmd['ski_incidence_deg'] = 5.0
    craft.set_command(cmd)

    steps = int(round(duration_s / craft.DT))
    max_u = 0.0
    min_vh = 1e9
    min_vsp = 1e9
    max_roll = 0.0
    max_yaw = 0.0
    min_nu = 1e9
    max_nu = -1e9
    max_ski_hm = 0.0
    max_aft_hm = 0.0
    max_eta_err = 0.0
    t_12 = None
    t_20 = None
    t_hull_clear = None
    samples = []
    t = 0.0
    for i in range(steps):
        craft.step()
        t += craft.DT
        rot = craft.data.xmat[af].reshape(3, 3)
        vel6 = np.zeros(6, dtype=np.float64)
        mj.mj_objectVelocity(craft.model, craft.data, mj.mjtObj.mjOBJ_BODY, af, vel6, 0)
        u = float((rot.T @ vel6[3:])[0])
        eul = Rotation.from_matrix(rot).as_euler('xyz', degrees=True)
        nu_deg = -float(eul[1])
        vh = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
        vsp = float(
            craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
            + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
        )
        max_u = max(max_u, u)
        min_vh = min(min_vh, vh)
        min_vsp = min(min_vsp, vsp)
        max_roll = max(max_roll, abs(float(eul[0])))
        max_yaw = max(max_yaw, abs(float(eul[2])))
        min_nu = min(min_nu, nu_deg)
        max_nu = max(max_nu, nu_deg)
        max_eta_err = max(max_eta_err, abs(float(craft.last_hydro.waterline_z_world_mean) - 7.0))
        if t_12 is None and u >= 12.0:
            t_12 = round(t, 2)
        if t_20 is None and u >= 20.0:
            t_20 = round(t, 2)
        if t_hull_clear is None and vh < 0.02:
            t_hull_clear = round(t, 2)
        for side in ('port', 'stbd'):
            max_ski_hm = max(max_ski_hm, abs(float(craft._act_load_nm.get(f'ski_{side}_actuator', 0.0))))
        max_aft_hm = max(max_aft_hm, abs(float(craft._act_load_nm.get('ski_aft_actuator', 0.0))))
        if i % 800 == 0 or i == steps - 1:
            samples.append(dict(
                t_s=round(t, 2), u_mps=round(u, 2), z_m=round(float(craft.data.xpos[af, 2]), 3),
                nose_up_deg=round(nu_deg, 2), roll_deg=round(float(eul[0]), 2), yaw_deg=round(float(eul[2]), 2),
                vol_h=round(vh, 4), vol_sp=round(vsp, 4),
                ski_deg=round(float(craft.last_ski_telemetry.get('port', {}).get('incidence_deg', 0.0)), 2),
                regime=craft.last_ski_telemetry.get('port', {}).get('regime'),
                ski_hm=round(float(craft._act_load_nm.get('ski_port_actuator', 0.0)), 1),
                aft_deg=round(float(craft.last_ski_telemetry.get('aft', {}).get('incidence_deg', 0.0)), 2),
                elev_deg=round(math.degrees(craft.joint('elevator_hinge')[0]), 2),
                thrust_n=round(sum(craft.last_thrust_per_fan_n), 1),
                foil_cl=craft.last_ski_telemetry.get('port', {}).get('foil_cl'),
                foil_ld=craft.last_ski_telemetry.get('port', {}).get('foil_ld'),
            ))

    return dict(
        profile=profile_id or 'legacy-concept-a',
        mass_kg=round(float(np.sum(craft.model.body_mass)), 2),
        rest_z_m=round(rest_z, 4),
        rest_nose_up_deg=round(rest_nose_up, 2),
        rest_vol_hull_m3=round(rest_vol_h, 4),
        rest_vol_sp_m3=round(rest_vol_sp, 4),
        max_speed_mps=round(max_u, 2),
        final_speed_mps=samples[-1]['u_mps'],
        t_to_12mps_s=t_12,
        t_to_20mps_s=t_20,
        t_hull_clear_s=t_hull_clear,
        min_vol_hull_m3=round(min_vh, 5),
        min_vol_sp_m3=round(min_vsp, 5),
        nose_up_range_deg=[round(min_nu, 2), round(max_nu, 2)],
        max_abs_roll_deg=round(max_roll, 2),
        max_abs_yaw_deg=round(max_yaw, 2),
        max_ski_hinge_nm=round(max_ski_hm, 1),
        max_aft_hinge_nm=round(max_aft_hm, 1),
        above_rated_s={k: round(v, 3) for k, v in craft._act_above_rated_s.items()},
        max_eta_err_m=round(max_eta_err, 4),
        capsized=bool(craft.capsized),
        flags=sorted(craft.flags),
        samples=samples,
    )


def main() -> None:
    t0 = time.time()
    infra = check_swe_and_fleet()
    results = {}
    for pid in (None, 'rc01-real-components-v1', 'rc01-planing-3pt-v1', 'rc01-hydrofoil-ski-v1'):
        key = pid or 'legacy-concept-a'
        res = run_profile_trial(pid, duration_s=26.0)
        results[key] = res
        print(f"\n--- {key} ---", flush=True)
        print(json.dumps({k: v for k, v in res.items() if k != 'samples'}, indent=2), flush=True)
    report = dict(infra=infra, results=results, wall_s=round(time.time() - t0, 1))
    (OUT / 'option1_vs_option2_comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('\nINFRA:', json.dumps(infra, indent=2), flush=True)


if __name__ == '__main__':
    main()
