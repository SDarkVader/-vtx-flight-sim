"""Standalone closed-loop telemetry-only AI pilot simulation qualification suite for Ricochet RC-01.

Drives BOTH Option 1 (`rc01-planing-3pt-v1`: 3-Point Planing Skis) and Option 2
(`rc01-hydrofoil-ski-v1`: Cambered Hydrofoil-Section Skis) strictly through the live
telemetry-only observation and action contract:
    `ricochet.live.sensor_observation` -> `normalize_ricochet_action` -> `RicochetAction` -> `craft.set_command`

Operational qualification maneuvers:
  * Maneuver A (19-DOF & 9-Surface Authority Check at Rest):
    Exercises every control surface channel (`aileron_deg`, `elevator_deg`, `rudder_deg`,
    `reverse_bucket`, `ski_incidence_deg`, `ski_differential_deg`, `aft_ski_incidence_deg`,
    `throttle` + `differential_thrust`) via `RicochetAction` (including alias/text normalization
    checks) and records achieved DOF deflections, slew rates, sponson flex stroke, and hinge moments.
  * Maneuver B (Closed-Loop Takeoff -> Hump Clearance -> High-Speed Cruise):
    Telemetry-driven takeoff from rest to `u > 18 m/s`, recording time to hull liftoff
    (`vol_hull < 0.02 m^3`), time to `12 m/s`, peak speed, pitch/roll/yaw envelope,
    sponson flex loads, and actuator load percentages.
  * Maneuver C (High-Speed Coordinated S-Turn at `12-18 m/s`):
    Once on plane / on foils, commands a closed-loop turn to `+12 deg` heading (port turn)
    for `4 s`, then `-12 deg` heading (starboard turn) for `4 s`, then straightens out —
    verifying responsive heading change, bounded roll bank (`max_abs_roll_deg < 18 deg`),
    zero spin-out, and `capsized == False`.
  * Maneuver D (High-Speed Reverse-Bucket Water Braking & Stop):
    From high speed, cuts throttle to `0.30` with `reverse_bucket = 1.0` (braking flare),
    verifying rapid deceleration without bow-stuffing (`nose_up_deg > -6.0 deg`,
    `capsized == False`, no `IMPACT`), then stows reverse buckets at stop.

Usage:
    python docs/ricochet/complete_model/closed_loop_maneuver_suite.py <worktree> <out_json>
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Any

import mujoco as mj
import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

from vtx.ricochet.live import (  # noqa: E402
    RicochetAction,
    normalize_ricochet_action,
    sensor_observation,
)
from vtx.ricochet.plant import RicochetCraft  # noqa: E402
from vtx.water.datum import WaterEnvironmentConfig  # noqa: E402


EXPECTED_19_DOF_JOINTS: tuple[tuple[str, int, str], ...] = (
    ('root', 6, 'freejoint'),
    ('fan_rotor_port_hinge', 1, 'fan_spin'),
    ('fan_rotor_stbd_hinge', 1, 'fan_spin'),
    ('aileron_port_hinge', 1, 'control_surface'),
    ('aileron_stbd_hinge', 1, 'control_surface'),
    ('elevator_hinge', 1, 'control_surface'),
    ('rudder_hinge', 1, 'control_surface'),
    ('reverse_bucket_port_hinge', 1, 'control_surface'),
    ('reverse_bucket_stbd_hinge', 1, 'control_surface'),
    ('sponson_port_flex_z', 1, 'sponson_slide'),
    ('sponson_stbd_flex_z', 1, 'sponson_slide'),
    ('ski_port_incidence', 1, 'control_surface'),
    ('ski_stbd_incidence', 1, 'control_surface'),
    ('ski_aft_incidence', 1, 'control_surface'),
)

CONTROL_SURFACE_JOINTS: tuple[str, ...] = (
    'aileron_port_hinge',
    'aileron_stbd_hinge',
    'elevator_hinge',
    'rudder_hinge',
    'reverse_bucket_port_hinge',
    'reverse_bucket_stbd_hinge',
    'ski_port_incidence',
    'ski_stbd_incidence',
    'ski_aft_incidence',
)


def make_open_lake_world(
    half_x: float = 1500.0,
    half_y: float = 450.0,
    bed_z: float = 2.0,
    wl: float = 7.0,
) -> SimpleNamespace:
    """Wide uniform-depth basin for unobstructed closed-loop maneuver qualification."""
    return SimpleNamespace(
        id='isolated-open-lake',
        version='1',
        environment_key='ricochet_lake',
        seed=41032,
        nx=41,
        ny=21,
        half_x=half_x,
        half_y=half_y,
        z_min=0.0,
        z_max=20.0,
        heights=np.full((21, 41), bed_z, dtype=np.float64),
        water_level=wl,
        structures=[],
        buoys=[],
        terrain_z=lambda x, y: bed_z,
        terrain_z_array=lambda xg, yg: np.full_like(np.asarray(xg, dtype=np.float64), bed_z),
    )


class TelemetryOnlyPilotHarness:
    """Strict `/api/observe` -> `/api/action` adapter around RicochetCraft."""

    def __init__(self, craft: RicochetCraft, seed: int = 20261120) -> None:
        self.aircraft = craft
        self.sensor_rng = np.random.default_rng(seed)
        self.obs_id = 0
        self.clock_lag_s = 0.0
        self.mission = 'ricochet_closed_loop_qualification'
        self.authority = 'colin'
        self.active = True
        self.paused = False
        self.time_scale = 1.0
        self.action_log: list[dict[str, Any]] = []

    def observe(self) -> dict[str, Any]:
        self.obs_id += 1
        return sensor_observation(self)

    def act(self, raw_payload: dict[str, Any]) -> RicochetAction:
        payload = dict(raw_payload)
        payload.setdefault('authority', 'colin')
        payload.setdefault('observation_id', self.obs_id)
        norm = normalize_ricochet_action(payload)
        action = RicochetAction.model_validate(norm)
        dumped = action.model_dump(exclude_none=True)
        cmd = {k: float(dumped[k]) for k in self.aircraft.command if k in dumped}
        self.aircraft.set_command(cmd)
        self.action_log.append({
            'obs_id': self.obs_id,
            't_s': round(float(self.aircraft.data.time), 4),
            'command': cmd,
            'reason': action.reason,
        })
        return action


def inspect_dof_topology(craft: RicochetCraft) -> dict[str, Any]:
    """Verify and summarize the 19-DOF / 9-control-surface MuJoCo topology."""
    m = craft.model
    joints_summary = []
    category_dofs: dict[str, int] = {}
    for jid in range(m.njnt):
        jname = mj.mj_id2name(m, mj.mjtObj.mjOBJ_JOINT, jid)
        jtype = int(m.jnt_type[jid])
        nv_j = 6 if jtype == int(mj.mjtJoint.mjJNT_FREE) else 1
        cat = next((c for n, _, c in EXPECTED_19_DOF_JOINTS if n == jname), 'other')
        category_dofs[cat] = category_dofs.get(cat, 0) + nv_j
        joints_summary.append({
            'name': jname,
            'dof_adr': int(m.jnt_dofadr[jid]),
            'qpos_adr': int(m.jnt_qposadr[jid]),
            'nv': nv_j,
            'category': cat,
        })
    actuators = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_ACTUATOR, i) for i in range(m.nu)]
    return {
        'nv': int(m.nv),
        'nq': int(m.nq),
        'njnt': int(m.njnt),
        'nu': int(m.nu),
        'category_dofs': category_dofs,
        'control_surface_count': len(CONTROL_SURFACE_JOINTS),
        'joints': joints_summary,
        'actuators': actuators,
    }


def run_maneuver_a_authority_at_rest(profile_id: str) -> dict[str, Any]:
    """Maneuver A: 19-DOF & 9-Surface Authority Check at Rest via RicochetAction."""
    world = make_open_lake_world(half_x=600.0, half_y=300.0)
    cfg = WaterEnvironmentConfig(
        water_level_m=7.0,
        wave_mode='still',
        wind_speed_mps=0.0,
        current_speed_mps=0.0,
        wake_enabled=False,
        whirlpools_enabled=False,
    )
    craft = RicochetCraft(
        world,
        variant='ricochet-concept-a',
        hull_variant='concept_a',
        load_case='LC-01',
        water_config=cfg,
        profile=profile_id,
        hydro_stride=4,
    )
    craft.spawn(-180.0, 0.0, 7.0)
    lab = TelemetryOnlyPilotHarness(craft)
    topo = inspect_dof_topology(craft)

    neutral_cmd = {
        'throttle': 0.0,
        'differential_thrust': 0.0,
        'rudder_deg': 0.0,
        'elevator_deg': 0.0,
        'aileron_deg': 0.0,
        'reverse_bucket': 0.0,
        'ski_incidence_deg': 0.0,
        'ski_differential_deg': 0.0,
        'aft_ski_incidence_deg': 0.0,
        'ecu_assist': 0.0,
    }

    # Sequence exercising all 9 control surfaces + twin fans via aliases, text, and canonical keys
    steps_plan: list[tuple[str, float, dict[str, Any], dict[str, float]]] = [
        ('neutral_settle', 0.6, dict(neutral_cmd, reason='rest neutral settle'), {}),
        (
            'aileron_pos_25',
            0.9,
            dict(neutral_cmd, aileron='hard right', reason='aileron +25 deg via qualitative alias'),
            {'aileron_port_hinge': -25.0, 'aileron_stbd_hinge': 25.0},
        ),
        (
            'aileron_neg_25',
            0.9,
            dict(neutral_cmd, roll_deg=-25.0, reason='aileron -25 deg via roll_deg alias'),
            {'aileron_port_hinge': 25.0, 'aileron_stbd_hinge': -25.0},
        ),
        ('aileron_zero', 0.5, dict(neutral_cmd), {'aileron_port_hinge': 0.0, 'aileron_stbd_hinge': 0.0}),
        (
            'elevator_pos_20',
            0.8,
            dict(neutral_cmd, elevator='full nose up', reason='elevator +20 deg via qualitative phrase'),
            {'elevator_hinge': 20.0},
        ),
        (
            'elevator_neg_20',
            0.8,
            dict(neutral_cmd, stabilator=-20.0, reason='elevator -20 deg via stabilator alias'),
            {'elevator_hinge': -20.0},
        ),
        ('elevator_zero', 0.5, dict(neutral_cmd), {'elevator_hinge': 0.0}),
        (
            'rudder_pos_30',
            1.0,
            dict(neutral_cmd, text='hard port rudder', reason='rudder +30 deg via text clause'),
            {'rudder_hinge': 30.0},
        ),
        (
            'rudder_neg_30',
            1.2,
            dict(neutral_cmd, helm_deg=-30.0, reason='rudder -30 deg via helm_deg alias'),
            {'rudder_hinge': -30.0},
        ),
        ('rudder_zero', 0.6, dict(neutral_cmd), {'rudder_hinge': 0.0}),
        (
            'reverse_bucket_deploy',
            1.3,
            dict(neutral_cmd, text='deploy reverse bucket', reason='deploy reverse buckets 85 deg'),
            {'reverse_bucket_port_hinge': 85.0, 'reverse_bucket_stbd_hinge': 85.0},
        ),
        (
            'reverse_bucket_stow',
            1.3,
            dict(neutral_cmd, reverser='stow', reason='stow reverse buckets 0 deg'),
            {'reverse_bucket_port_hinge': 0.0, 'reverse_bucket_stbd_hinge': 0.0},
        ),
        (
            'ski_collective_8_diff_pos_3',
            1.0,
            dict(neutral_cmd, ski_collective=8.0, ski_diff=3.0, reason='ski collective 8 + diff +3'),
            {'ski_port_incidence': 11.0, 'ski_stbd_incidence': 5.0},
        ),
        (
            'ski_collective_6_diff_neg_3',
            1.0,
            dict(neutral_cmd, ski_incidence_deg=6.0, ski_differential_deg=-3.0, reason='ski collective 6 + diff -3'),
            {'ski_port_incidence': 3.0, 'ski_stbd_incidence': 9.0},
        ),
        ('skis_zero', 0.7, dict(neutral_cmd), {'ski_port_incidence': 0.0, 'ski_stbd_incidence': 0.0}),
        (
            'aft_ski_pos_6',
            0.8,
            dict(neutral_cmd, aft_ski=6.0, reason='aft trim ski +6 deg'),
            {'ski_aft_incidence': 6.0},
        ),
        (
            'aft_ski_neg_3',
            0.8,
            dict(neutral_cmd, stern_ski=-3.0, reason='aft trim ski -3 deg'),
            {'ski_aft_incidence': -3.0},
        ),
        ('aft_ski_zero', 0.6, dict(neutral_cmd), {'ski_aft_incidence': 0.0}),
        (
            'propulsion_diff_thrust',
            1.2,
            dict(neutral_cmd, power=0.35, diff_thrust=0.50, reason='throttle 0.35 + differential thrust +0.50'),
            {},
        ),
    ]

    dt = float(craft.DT)
    peak_slew_deg_s: dict[str, float] = {jn: 0.0 for jn in CONTROL_SURFACE_JOINTS}
    max_hinge_nm: dict[str, float] = {}
    sponson_stroke_mm = {'port_min': 1e9, 'port_max': -1e9, 'stbd_min': 1e9, 'stbd_max': -1e9}
    rest_z_min = 1e9
    rest_z_max = -1e9
    segment_results: list[dict[str, Any]] = []
    worst_tracking_err_deg = 0.0
    diff_thrust_fan_rpm: list[float] = [0.0, 0.0]

    for seg_name, dur_s, raw_cmd, expected_joints in steps_plan:
        # Remove keys from neutral_cmd that would shadow alias keys in raw_cmd
        clean_raw = dict(raw_cmd)
        for alias_key, canon_key in (
            ('aileron', 'aileron_deg'),
            ('roll_deg', 'aileron_deg'),
            ('elevator', 'elevator_deg'),
            ('stabilator', 'elevator_deg'),
            ('helm_deg', 'rudder_deg'),
            ('reverser', 'reverse_bucket'),
            ('ski_collective', 'ski_incidence_deg'),
            ('ski_diff', 'ski_differential_deg'),
            ('aft_ski', 'aft_ski_incidence_deg'),
            ('stern_ski', 'aft_ski_incidence_deg'),
            ('power', 'throttle'),
            ('diff_thrust', 'differential_thrust'),
        ):
            if alias_key in clean_raw and canon_key in clean_raw:
                clean_raw.pop(canon_key, None)
        if 'text' in clean_raw:
            for k in ('rudder_deg', 'reverse_bucket'):
                clean_raw.pop(k, None)

        obs_pre = lab.observe()
        assert obs_pre['profile_id'] == profile_id
        lab.act(clean_raw)

        prev_q = {jn: math.degrees(craft.joint(jn)[0]) for jn in CONTROL_SURFACE_JOINTS}
        n_steps = int(round(dur_s / dt))
        for _ in range(n_steps):
            craft.step()
            for jn in CONTROL_SURFACE_JOINTS:
                q_deg = math.degrees(craft.joint(jn)[0])
                rate = abs(q_deg - prev_q[jn]) / dt
                peak_slew_deg_s[jn] = max(peak_slew_deg_s[jn], rate)
                prev_q[jn] = q_deg
            for aname, load_nm in craft._act_load_nm.items():
                max_hinge_nm[aname] = max(max_hinge_nm.get(aname, 0.0), abs(float(load_nm)))
            sp_p_mm = 1000.0 * craft.joint('sponson_port_flex_z')[0]
            sp_s_mm = 1000.0 * craft.joint('sponson_stbd_flex_z')[0]
            sponson_stroke_mm['port_min'] = min(sponson_stroke_mm['port_min'], sp_p_mm)
            sponson_stroke_mm['port_max'] = max(sponson_stroke_mm['port_max'], sp_p_mm)
            sponson_stroke_mm['stbd_min'] = min(sponson_stroke_mm['stbd_min'], sp_s_mm)
            sponson_stroke_mm['stbd_max'] = max(sponson_stroke_mm['stbd_max'], sp_s_mm)
            if seg_name != 'propulsion_diff_thrust':
                z_af = float(craft.data.xpos[craft.bids['airframe'], 2])
                rest_z_min = min(rest_z_min, z_af)
                rest_z_max = max(rest_z_max, z_af)

        obs_post = lab.observe()
        achieved_joints = {jn: round(math.degrees(craft.joint(jn)[0]), 3) for jn in expected_joints}
        errors = {jn: round(achieved_joints[jn] - exp_v, 3) for jn, exp_v in expected_joints.items()}
        for err in errors.values():
            worst_tracking_err_deg = max(worst_tracking_err_deg, abs(err))
        if seg_name == 'propulsion_diff_thrust':
            diff_thrust_fan_rpm = list(obs_post['fan_rpm'])

        segment_results.append({
            'segment': seg_name,
            'duration_s': dur_s,
            'expected_deg': expected_joints,
            'achieved_deg': achieved_joints,
            'error_deg': errors,
            'control_surfaces_obs': obs_post['control_surfaces'],
        })

    passed = (
        topo['nv'] == 19
        and topo['control_surface_count'] == 9
        and worst_tracking_err_deg < 0.35
        and diff_thrust_fan_rpm[1] > diff_thrust_fan_rpm[0] > 1000.0
        and 6.30 <= rest_z_min
        and rest_z_max <= 6.55
        and not craft.capsized
    )
    return {
        'maneuver': 'A_19dof_9surface_authority_at_rest',
        'profile_id': profile_id,
        'passed': bool(passed),
        'topology': topo,
        'worst_tracking_error_deg': round(worst_tracking_err_deg, 4),
        'peak_slew_rate_deg_s': {k: round(v, 1) for k, v in peak_slew_deg_s.items()},
        'max_hinge_moments_nm': {k: round(v, 2) for k, v in max_hinge_nm.items()},
        'sponson_flex_stroke_mm': {k: round(v, 3) for k, v in sponson_stroke_mm.items()},
        'rest_heave_z_range_m': [round(rest_z_min, 4), round(rest_z_max, 4)],
        'diff_thrust_fan_rpm': diff_thrust_fan_rpm,
        'capsized': bool(craft.capsized),
        'segments': segment_results,
    }


def _euler_xyz_deg_from_rot(rot: np.ndarray) -> tuple[float, float, float]:
    """Exact extrinsic xyz Euler angles (deg) matching scipy Rotation.as_euler('xyz', degrees=True)."""
    r20 = max(-1.0, min(1.0, float(rot[2, 0])))
    pitch = math.degrees(math.asin(-r20))
    roll = math.degrees(math.atan2(float(rot[2, 1]), float(rot[2, 2])))
    yaw = math.degrees(math.atan2(float(rot[1, 0]), float(rot[0, 0])))
    return roll, pitch, yaw


def run_maneuver_b_takeoff_and_cruise(
    profile_id: str,
    duration_s: float = 22.5,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], RicochetCraft]:
    """Maneuver B: Closed-Loop Takeoff -> Hump Clearance -> High-Speed Cruise (`u > 18 m/s`).

    Returns `(report_b, ckpt_on_plane, ckpt_high_speed, craft)`.
    """
    world = make_open_lake_world(half_x=1500.0, half_y=450.0)
    cfg = WaterEnvironmentConfig(
        water_level_m=7.0,
        wave_mode='still',
        wind_speed_mps=0.0,
        current_speed_mps=0.0,
        wake_enabled=False,
        whirlpools_enabled=False,
    )
    craft = RicochetCraft(
        world,
        variant='ricochet-concept-a',
        hull_variant='concept_a',
        load_case='LC-01',
        water_config=cfg,
        profile=profile_id,
        hydro_stride=4,
    )
    craft.spawn(-1150.0, 0.0, 7.0)
    lab = TelemetryOnlyPilotHarness(craft)

    # 1.0 s calm water settle before takeoff command
    lab.observe()
    lab.act({'throttle': 0.0, 'ecu_assist': 1.0, 'reason': 'pre-takeoff calm settle'})
    for _ in range(int(round(1.0 / craft.DT))):
        craft.step()

    obs0 = lab.observe()
    rest_vol_hull = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
    rest_vol_sp = float(
        craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
        + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
    )

    dt = float(craft.DT)
    steps = int(round(duration_s / dt))
    pilot_stride = max(1, int(round(0.05 / dt)))  # 20 Hz closed-loop telemetry pilot

    hull_liftoff_t_s: float | None = None
    t_to_12mps_s: float | None = None
    t_to_18mps_s: float | None = None
    peak_speed_mps = 0.0
    min_vol_hull = 1e9
    min_vol_sp = 1e9
    min_nose_up_deg = 1e9
    max_nose_up_deg = -1e9
    max_abs_roll_deg = 0.0
    max_abs_yaw_deg = 0.0
    max_sponson_stroke_mm = 0.0
    max_sponson_force_z_n = 0.0
    max_actuator_load_pct: dict[str, float] = {}
    max_actuator_load_nm: dict[str, float] = {}
    samples: list[dict[str, Any]] = []

    ckpt_on_plane: dict[str, Any] | None = None
    t_run = 0.0

    for i in range(steps):
        if i % pilot_stride == 0:
            obs = lab.observe()
            u_obs = float(obs['body_velocity_mps'][0])
            roll_obs, pitch_obs, yaw_obs = (float(x) for x in obs['attitude_xyz_deg'])
            yaw_rate_obs = float(obs['gyro_world_deg_s'][2])
            # Closed-loop centerline heading hold via rudder while ECU schedules hydro-skis & pitch trim
            rud_trim = float(np.clip(-1.2 * yaw_obs - 0.35 * yaw_rate_obs, -8.0, 8.0))
            lab.act({
                'throttle': 1.0,
                'differential_thrust': 0.0,
                'rudder_deg': rud_trim,
                'reverse_bucket': 0.0,
                'ecu_assist': 1.0,
                'reason': f'closed-loop takeoff u={u_obs:.1f} m/s',
            })

        craft.step()
        t_run += dt

        # Record physical + telemetry metrics
        obs_curr = lab.observe() if (i % 800 == 0 or i == steps - 1) else None
        af = craft.bids['airframe']
        rot = craft.data.xmat[af].reshape(3, 3)
        vel6 = np.zeros(6, dtype=np.float64)
        mj.mj_objectVelocity(craft.model, craft.data, mj.mjtObj.mjOBJ_BODY, af, vel6, 0)
        u_true = float(rot[0, 0] * vel6[3] + rot[1, 0] * vel6[4] + rot[2, 0] * vel6[5])
        vh = float(craft.last_hydro.component_loads['main_hull']['submerged_volume_m3'])
        vsp = float(
            craft.last_hydro.component_loads['sponson_port']['submerged_volume_m3']
            + craft.last_hydro.component_loads['sponson_stbd']['submerged_volume_m3']
        )
        roll_d, pitch_d, yaw_d = _euler_xyz_deg_from_rot(rot)
        nose_up_d = -pitch_d

        peak_speed_mps = max(peak_speed_mps, u_true)
        min_vol_hull = min(min_vol_hull, vh)
        min_vol_sp = min(min_vol_sp, vsp)
        min_nose_up_deg = min(min_nose_up_deg, nose_up_d)
        max_nose_up_deg = max(max_nose_up_deg, nose_up_d)
        max_abs_roll_deg = max(max_abs_roll_deg, abs(roll_d))
        max_abs_yaw_deg = max(max_abs_yaw_deg, abs(yaw_d))

        if hull_liftoff_t_s is None and vh < 0.02:
            hull_liftoff_t_s = round(t_run, 3)
        if t_to_12mps_s is None and u_true >= 12.0:
            t_to_12mps_s = round(t_run, 3)
        if t_to_18mps_s is None and u_true >= 18.0:
            t_to_18mps_s = round(t_run, 3)

        # Capture on-plane / on-foils checkpoint in the 12-18 m/s window (t >= 12.0 s and u >= 13.5 m/s)
        if ckpt_on_plane is None and t_run >= 12.0 and u_true >= 13.5 and vh < 0.01:
            ckpt_on_plane = craft.checkpoint_state()

        if i % 4 == 0 or i == steps - 1:
            sp_p_mm = abs(1000.0 * craft.joint('sponson_port_flex_z')[0])
            sp_s_mm = abs(1000.0 * craft.joint('sponson_stbd_flex_z')[0])
            max_sponson_stroke_mm = max(max_sponson_stroke_mm, sp_p_mm, sp_s_mm)
            att = craft.attachment_loads()
            max_sponson_force_z_n = max(
                max_sponson_force_z_n,
                abs(float(att['sponson_port']['force_n'][2])),
                abs(float(att['sponson_stbd']['force_n'][2])),
            )

            cs = craft.control_surface_telemetry()
            for surf_key in ('rudder', 'elevator', 'aileron', 'reverse_bucket'):
                if surf_key in cs and 'load_pct' in cs[surf_key]:
                    max_actuator_load_pct[surf_key] = max(max_actuator_load_pct.get(surf_key, 0.0), float(cs[surf_key]['load_pct']))
                    max_actuator_load_nm[surf_key] = max(max_actuator_load_nm.get(surf_key, 0.0), float(cs[surf_key]['load_nm']))
            if 'skis' in cs:
                sk_pct = max(float(cs['skis']['port_load_pct']), float(cs['skis']['stbd_load_pct']))
                sk_nm = max(abs(float(cs['skis']['port_load_nm'])), abs(float(cs['skis']['stbd_load_nm'])))
                max_actuator_load_pct['skis'] = max(max_actuator_load_pct.get('skis', 0.0), sk_pct)
                max_actuator_load_nm['skis'] = max(max_actuator_load_nm.get('skis', 0.0), sk_nm)
            if 'aft_ski' in cs:
                max_actuator_load_pct['aft_ski'] = max(max_actuator_load_pct.get('aft_ski', 0.0), float(cs['aft_ski']['load_pct']))
                max_actuator_load_nm['aft_ski'] = max(max_actuator_load_nm.get('aft_ski', 0.0), abs(float(cs['aft_ski']['load_nm'])))

        if obs_curr is not None:
            samples.append({
                't_s': round(t_run, 2),
                'u_mps': round(u_true, 2),
                'z_m': round(float(craft.data.xpos[af, 2]), 3),
                'nose_up_deg': round(nose_up_d, 2),
                'roll_deg': round(roll_d, 2),
                'yaw_deg': round(yaw_d, 2),
                'vol_hull_m3': round(vh, 4),
                'vol_sp_m3': round(vsp, 4),
                'ski_feedback_deg': obs_curr.get('ski_feedback_deg'),
                'warning_lamps': obs_curr.get('warning_lamps'),
            })

    ckpt_high_speed = craft.checkpoint_state()
    if ckpt_on_plane is None:
        ckpt_on_plane = ckpt_high_speed

    final_obs = lab.observe()
    passed = (
        hull_liftoff_t_s is not None
        and t_to_12mps_s is not None
        and peak_speed_mps > 18.0
        and min_vol_hull < 0.02
        and max_abs_roll_deg < 5.0
        and max_abs_yaw_deg < 5.0
        and not craft.capsized
        and 'IMPACT' not in final_obs['warning_lamps']
    )
    report = {
        'maneuver': 'B_closed_loop_takeoff_hump_clearance_cruise',
        'profile_id': profile_id,
        'passed': bool(passed),
        'rest_vol_hull_m3': round(rest_vol_hull, 4),
        'rest_vol_sp_m3': round(rest_vol_sp, 4),
        'hull_liftoff_t_s': hull_liftoff_t_s,
        't_to_12mps_s': t_to_12mps_s,
        't_to_18mps_s': t_to_18mps_s,
        'peak_speed_mps': round(peak_speed_mps, 2),
        'final_speed_mps': round(float(final_obs['body_velocity_mps'][0]), 2),
        'min_vol_hull_m3': round(min_vol_hull, 5),
        'min_vol_sp_m3': round(min_vol_sp, 5),
        'nose_up_range_deg': [round(min_nose_up_deg, 2), round(max_nose_up_deg, 2)],
        'max_abs_roll_deg': round(max_abs_roll_deg, 2),
        'max_abs_yaw_deg': round(max_abs_yaw_deg, 2),
        'max_sponson_flex_stroke_mm': round(max_sponson_stroke_mm, 3),
        'max_sponson_vertical_force_n': round(max_sponson_force_z_n, 1),
        'max_actuator_load_pct': {k: round(v, 1) for k, v in max_actuator_load_pct.items()},
        'max_actuator_load_nm': {k: round(v, 1) for k, v in max_actuator_load_nm.items()},
        'capsized': bool(craft.capsized),
        'warning_lamps': final_obs['warning_lamps'],
        'samples': samples,
    }
    return report, ckpt_on_plane, ckpt_high_speed, craft


def run_maneuver_c_coordinated_s_turn(
    craft: RicochetCraft,
    ckpt_on_plane: dict[str, Any],
) -> dict[str, Any]:
    """Maneuver C: High-Speed Coordinated S-Turn (+12 deg port for 4 s, -12 deg stbd for 4 s, straighten out)."""
    craft.restore_state(ckpt_on_plane)
    lab = TelemetryOnlyPilotHarness(craft)
    obs_entry = lab.observe()
    entry_speed_mps = float(obs_entry['body_velocity_mps'][0])

    dt = float(craft.DT)
    pilot_stride = max(1, int(round(0.05 / dt)))  # 20 Hz telemetry pilot
    phases: list[tuple[str, float, float]] = [
        ('port_turn_plus12', 4.0, 12.0),
        ('stbd_turn_minus12', 4.0, -12.0),
        ('straighten_zero', 3.0, 0.0),
    ]

    max_port_yaw_deg = -1e9
    min_stbd_yaw_deg = 1e9
    max_abs_roll_deg = 0.0
    max_abs_yaw_rate_deg_s = 0.0
    min_speed_mps = entry_speed_mps
    max_speed_mps = entry_speed_mps
    samples: list[dict[str, Any]] = []
    t_turn = 0.0

    for phase_name, dur_s, target_yaw_deg in phases:
        n_steps = int(round(dur_s / dt))
        for i in range(n_steps):
            if i % pilot_stride == 0:
                obs = lab.observe()
                u_obs = float(obs['body_velocity_mps'][0])
                roll_obs, _pitch_obs, yaw_obs = (float(x) for x in obs['attitude_xyz_deg'])
                roll_rate_obs, _pitch_rate_obs, yaw_rate_obs = (float(x) for x in obs['gyro_world_deg_s'])

                yaw_err = target_yaw_deg - yaw_obs
                des_yaw_rate = float(np.clip(1.15 * yaw_err, -8.5, 8.5))
                rate_err = des_yaw_rate - yaw_rate_obs

                rud_cmd = float(np.clip(1.85 * yaw_err + 0.95 * rate_err, -24.0, 24.0))
                diff_cmd = float(np.clip(0.055 * yaw_err + 0.030 * rate_err, -0.50, 0.50))

                # Coordinated inward roll bank target (-roll = left bank for +yaw port turn)
                target_bank_deg = float(np.clip(-0.20 * des_yaw_rate, -2.5, 2.5))
                bank_err = target_bank_deg - roll_obs
                ski_diff_cmd = float(np.clip(0.25 * bank_err - 0.05 * roll_rate_obs, -2.0, 2.0))
                ail_cmd = float(np.clip(0.60 * bank_err - 0.10 * roll_rate_obs, -12.0, 12.0))

                lab.act({
                    'throttle': 0.95,
                    'differential_thrust': diff_cmd,
                    'rudder_deg': rud_cmd,
                    'aileron_deg': ail_cmd,
                    'ski_differential_deg': ski_diff_cmd,
                    'reverse_bucket': 0.0,
                    'ecu_assist': 1.0,
                    'reason': f'{phase_name} tgt={target_yaw_deg:+.0f} yaw={yaw_obs:+.1f} u={u_obs:.1f}',
                })

            craft.step()
            t_turn += dt

            obs_step = lab.observe() if (i % 100 == 0 or i == n_steps - 1) else None
            if obs_step is not None:
                u_s = float(obs_step['body_velocity_mps'][0])
                r_s, p_s, y_s = (float(x) for x in obs_step['attitude_xyz_deg'])
                yr_s = float(obs_step['gyro_world_deg_s'][2])
                min_speed_mps = min(min_speed_mps, u_s)
                max_speed_mps = max(max_speed_mps, u_s)
                max_abs_roll_deg = max(max_abs_roll_deg, abs(r_s))
                max_abs_yaw_rate_deg_s = max(max_abs_yaw_rate_deg_s, abs(yr_s))
                if phase_name == 'port_turn_plus12':
                    max_port_yaw_deg = max(max_port_yaw_deg, y_s)
                elif phase_name == 'stbd_turn_minus12':
                    min_stbd_yaw_deg = min(min_stbd_yaw_deg, y_s)
                if i % 200 == 0 or i == n_steps - 1:
                    samples.append({
                        't_turn_s': round(t_turn, 2),
                        'phase': phase_name,
                        'target_yaw_deg': target_yaw_deg,
                        'u_mps': round(u_s, 2),
                        'yaw_deg': round(y_s, 2),
                        'roll_deg': round(r_s, 2),
                        'nose_up_deg': round(-p_s, 2),
                        'yaw_rate_deg_s': round(yr_s, 2),
                        'rudder_deg': obs_step['rudder_feedback_deg'],
                    })

    final_obs = lab.observe()
    final_yaw_deg = float(final_obs['attitude_xyz_deg'][2])
    heading_swing_deg = max_port_yaw_deg - min_stbd_yaw_deg
    passed = (
        max_port_yaw_deg >= 5.0
        and min_stbd_yaw_deg <= -4.0
        and heading_swing_deg >= 10.0
        and max_abs_roll_deg < 18.0
        and max_abs_yaw_rate_deg_s < 45.0
        and not craft.capsized
        and 'CAPSIZED' not in final_obs['warning_lamps']
        and 'IMPACT' not in final_obs['warning_lamps']
    )
    return {
        'maneuver': 'C_high_speed_coordinated_s_turn',
        'profile_id': craft.profile_id,
        'passed': bool(passed),
        'entry_speed_mps': round(entry_speed_mps, 2),
        'min_speed_mps': round(min_speed_mps, 2),
        'max_speed_mps': round(max_speed_mps, 2),
        'exit_speed_mps': round(float(final_obs['body_velocity_mps'][0]), 2),
        'max_port_yaw_deg': round(max_port_yaw_deg, 2),
        'min_stbd_yaw_deg': round(min_stbd_yaw_deg, 2),
        'heading_swing_deg': round(heading_swing_deg, 2),
        'final_yaw_deg': round(final_yaw_deg, 2),
        'max_abs_roll_deg': round(max_abs_roll_deg, 2),
        'max_abs_yaw_rate_deg_s': round(max_abs_yaw_rate_deg_s, 2),
        'capsized': bool(craft.capsized),
        'warning_lamps': final_obs['warning_lamps'],
        'samples': samples,
    }


def run_maneuver_d_reverse_bucket_braking(
    craft: RicochetCraft,
    ckpt_high_speed: dict[str, Any],
    max_brake_duration_s: float = 13.0,
) -> dict[str, Any]:
    """Maneuver D: High-Speed Reverse-Bucket Water Braking & Stop (`throttle=0.30, reverse_bucket=1.0`, then stow)."""
    craft.restore_state(ckpt_high_speed)
    lab = TelemetryOnlyPilotHarness(craft)
    obs_entry = lab.observe()
    entry_speed_mps = float(obs_entry['body_velocity_mps'][0])

    dt = float(craft.DT)
    pilot_stride = max(1, int(round(0.05 / dt)))  # 20 Hz telemetry pilot
    max_steps = int(round(max_brake_duration_s / dt))

    min_nose_up_deg = 1e9
    max_nose_up_deg = -1e9
    max_abs_roll_deg = 0.0
    max_reverse_bucket_frac = 0.0
    max_bucket_hinge_nm = 0.0
    peak_decel_mps2 = 0.0
    stop_t_s: float | None = None
    stow_rem_steps: int | None = None
    prev_u = entry_speed_mps
    t_brake = 0.0
    samples: list[dict[str, Any]] = []

    for i in range(max_steps):
        if i % pilot_stride == 0:
            obs = lab.observe()
            u_obs = float(obs['body_velocity_mps'][0])
            roll_obs, pitch_obs, yaw_obs = (float(x) for x in obs['attitude_xyz_deg'])
            yaw_rate_obs = float(obs['gyro_world_deg_s'][2])
            decel = max(0.0, (prev_u - u_obs) / (pilot_stride * dt)) if i > 0 else 0.0
            peak_decel_mps2 = max(peak_decel_mps2, decel)
            prev_u = u_obs

            if stop_t_s is None and (u_obs <= 1.1 or t_brake >= max_brake_duration_s - 1.6):
                stop_t_s = round(t_brake, 3)
                stow_rem_steps = int(round(1.5 / dt))

            if stop_t_s is None:
                # Active reverse-bucket water braking flare: throttle=0.30, reverse_bucket=1.0, nose-up flare protection
                rud_hold = float(np.clip(-1.2 * yaw_obs - 0.35 * yaw_rate_obs, -10.0, 10.0))
                lab.act({
                    'throttle': 0.30,
                    'differential_thrust': 0.0,
                    'reverse_bucket': 1.0,
                    'elevator_deg': 6.0,
                    'ski_incidence_deg': 2.0,
                    'rudder_deg': rud_hold,
                    'ecu_assist': 1.0,
                    'reason': f'reverse-bucket braking flare u={u_obs:.2f} m/s',
                })
            else:
                # Stop reached: stow reverse buckets and cut throttle to idle/zero
                lab.act({
                    'throttle': 0.0,
                    'differential_thrust': 0.0,
                    'reverse_bucket': 0.0,
                    'elevator_deg': 0.0,
                    'ski_incidence_deg': 0.0,
                    'rudder_deg': 0.0,
                    'ecu_assist': 1.0,
                    'reason': f'stop achieved u={u_obs:.2f} m/s: stow reverse buckets',
                })

        craft.step()
        t_brake += dt

        for side in ('port', 'stbd'):
            hm = abs(float(craft._act_load_nm.get(f'reverse_bucket_{side}_servo', 0.0)))
            max_bucket_hinge_nm = max(max_bucket_hinge_nm, hm)

        if i % 80 == 0 or i == max_steps - 1 or stow_rem_steps == 1:
            obs_s = lab.observe()
            u_s = float(obs_s['body_velocity_mps'][0])
            r_s, p_s, y_s = (float(x) for x in obs_s['attitude_xyz_deg'])
            nu_s = -p_s
            rev_frac = float(obs_s['reverse_bucket_fraction'])
            min_nose_up_deg = min(min_nose_up_deg, nu_s)
            max_nose_up_deg = max(max_nose_up_deg, nu_s)
            max_abs_roll_deg = max(max_abs_roll_deg, abs(r_s))
            max_reverse_bucket_frac = max(max_reverse_bucket_frac, rev_frac)
            if i % 240 == 0 or stow_rem_steps == 1 or i == max_steps - 1:
                samples.append({
                    't_brake_s': round(t_brake, 2),
                    'u_mps': round(u_s, 2),
                    'nose_up_deg': round(nu_s, 2),
                    'roll_deg': round(r_s, 2),
                    'yaw_deg': round(y_s, 2),
                    'reverse_bucket_fraction': round(rev_frac, 3),
                    'phase': 'stowed_stop' if stop_t_s is not None else 'reverse_braking',
                })

        if stow_rem_steps is not None:
            stow_rem_steps -= 1
            if stow_rem_steps <= 0:
                break

    final_obs = lab.observe()
    final_speed_mps = float(final_obs['body_velocity_mps'][0])
    final_rev_frac = float(final_obs['reverse_bucket_fraction'])
    passed = (
        entry_speed_mps > 15.0
        and final_speed_mps < 2.0
        and max_reverse_bucket_frac > 0.95
        and final_rev_frac < 0.05
        and min_nose_up_deg > -6.0
        and not craft.capsized
        and 'CAPSIZED' not in final_obs['warning_lamps']
        and 'IMPACT' not in final_obs['warning_lamps']
    )
    return {
        'maneuver': 'D_high_speed_reverse_bucket_braking_and_stop',
        'profile_id': craft.profile_id,
        'passed': bool(passed),
        'entry_speed_mps': round(entry_speed_mps, 2),
        'final_speed_mps': round(final_speed_mps, 2),
        'stop_t_s': stop_t_s,
        'peak_decel_mps2': round(peak_decel_mps2, 2),
        'min_nose_up_deg': round(min_nose_up_deg, 2),
        'max_nose_up_deg': round(max_nose_up_deg, 2),
        'max_abs_roll_deg': round(max_abs_roll_deg, 2),
        'max_reverse_bucket_fraction': round(max_reverse_bucket_frac, 3),
        'final_reverse_bucket_fraction': round(final_rev_frac, 3),
        'max_bucket_hinge_nm': round(max_bucket_hinge_nm, 2),
        'capsized': bool(craft.capsized),
        'warning_lamps': final_obs['warning_lamps'],
        'samples': samples,
    }


def run_profile_qualification(profile_id: str, *, include_maneuver_a: bool = True) -> dict[str, Any]:
    """Run closed-loop telemetry-only qualification maneuvers on a profile."""
    t0 = time.time()
    man_a = run_maneuver_a_authority_at_rest(profile_id) if include_maneuver_a else None
    man_b, ckpt_on_plane, ckpt_high_speed, craft = run_maneuver_b_takeoff_and_cruise(profile_id)
    man_c = run_maneuver_c_coordinated_s_turn(craft, ckpt_on_plane)
    man_d = run_maneuver_d_reverse_bucket_braking(craft, ckpt_high_speed)
    checked = [m for m in (man_a, man_b, man_c, man_d) if m is not None]
    all_passed = all(m['passed'] for m in checked)
    maneuvers: dict[str, Any] = {
        'B_takeoff_and_cruise': man_b,
        'C_coordinated_s_turn': man_c,
        'D_reverse_bucket_braking': man_d,
    }
    if man_a is not None:
        maneuvers = {'A_authority_at_rest': man_a, **maneuvers}
    return {
        'profile_id': craft.profile_id,
        'model_revision': craft.model_revision,
        'model_name': craft.model_name,
        'all_passed': bool(all_passed),
        'wall_s': round(time.time() - t0, 2),
        'maneuvers': maneuvers,
    }


def run_profiles_parallel(
    profiles: tuple[str, ...],
    *,
    mode: str = 'qual',
    include_maneuver_a: bool = True,
) -> dict[str, Any]:
    """Run independent profile simulations concurrently in isolated Python subprocesses."""
    script = pathlib.Path(__file__).resolve()
    env = dict(os.environ)
    src_path = str(REPO_ROOT / 'src')
    env['PYTHONPATH'] = src_path + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    with tempfile.TemporaryDirectory(prefix='vtx-rc01-qual-') as td:
        td_path = pathlib.Path(td)
        jobs: list[tuple[str, pathlib.Path, subprocess.Popen[str]]] = []
        for pid in profiles:
            out_file = td_path / f'{pid}.json'
            cmd = [sys.executable, str(script), '--worker', mode, pid, str(out_file)]
            if not include_maneuver_a:
                cmd.append('--no-maneuver-a')
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(REPO_ROOT))
            jobs.append((pid, out_file, proc))
        results: dict[str, Any] = {}
        for pid, out_file, proc in jobs:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f'Worker {mode} failed for {pid} (rc={proc.returncode}):\n{stdout}\n{stderr}')
            results[pid] = json.loads(out_file.read_text(encoding='utf-8'))
        return results


def run_qualification_suite(
    out_json_path: pathlib.Path | str | None = None,
    *,
    include_maneuver_a: bool = True,
    parallel: bool = True,
) -> dict[str, Any]:
    """Run the complete closed-loop qualification suite across Option 1 and Option 2."""
    t0 = time.time()
    profiles = ('rc01-planing-3pt-v1', 'rc01-hydrofoil-ski-v1')
    if parallel and len(profiles) > 1:
        results = run_profiles_parallel(profiles, mode='qual', include_maneuver_a=include_maneuver_a)
    else:
        results = {
            pid: run_profile_qualification(pid, include_maneuver_a=include_maneuver_a)
            for pid in profiles
        }
    report = {
        'schema': 'vtx-ricochet-closed-loop-qualification-1',
        'contract': 'ricochet.live.sensor_observation -> normalize_ricochet_action -> RicochetAction -> craft.set_command',
        'all_passed': all(r['all_passed'] for r in results.values()),
        'wall_s': round(time.time() - t0, 2),
        'profiles': results,
    }
    if out_json_path is not None:
        out_p = pathlib.Path(out_json_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main() -> None:
    if len(sys.argv) >= 5 and sys.argv[1] == '--worker':
        mode = sys.argv[2]
        pid = sys.argv[3]
        out_file = pathlib.Path(sys.argv[4]).resolve()
        include_a = '--no-maneuver-a' not in sys.argv[5:]
        if mode == 'maneuver_a':
            payload = run_maneuver_a_authority_at_rest(pid)
        elif mode == 'qual':
            payload = run_profile_qualification(pid, include_maneuver_a=include_a)
        else:
            raise ValueError(f'Unknown worker mode: {mode}')
        out_file.write_text(json.dumps(payload), encoding='utf-8')
        return

    wt = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO_ROOT
    out_json = (
        pathlib.Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else wt / 'scratch' / 'complete_model' / 'closed_loop_maneuver_report.json'
    )
    if str(wt / 'src') not in sys.path:
        sys.path.insert(0, str(wt / 'src'))
    report = run_qualification_suite(out_json)
    for pid, res in report['profiles'].items():
        print(f"\n=== {pid} (all_passed={res['all_passed']}, wall={res['wall_s']}s) ===", flush=True)
        for mkey, mval in res['maneuvers'].items():
            summary = {
                k: v for k, v in mval.items()
                if k not in ('samples', 'segments', 'topology')
            }
            print(f"  [{mkey}] {json.dumps(summary)}", flush=True)
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
