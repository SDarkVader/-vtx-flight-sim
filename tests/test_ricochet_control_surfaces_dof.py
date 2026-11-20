"""Comprehensive 19-DOF / 9-control-surface authority, closed-loop telemetry-only AI pilot
maneuvers, and live HarbourFleet profile-switching test suite for Ricochet RC-01
Option 1 (`rc01-planing-3pt-v1`) and Option 2 (`rc01-hydrofoil-ski-v1`)."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from test_harbour_fleet import harbour_world
from vtx.harbour_fleet import HarbourFleet
from vtx.harbour_session import _restart_boat
from vtx.ricochet.live import RicochetAction, normalize_ricochet_action, sensor_observation
from vtx.ricochet.plant import RicochetCraft
from vtx.water.datum import WaterEnvironmentConfig

ROOT = Path(__file__).resolve().parents[1]


def _load_maneuver_suite():
    suite_path = ROOT / 'docs' / 'ricochet' / 'complete_model' / 'closed_loop_maneuver_suite.py'
    spec = importlib.util.spec_from_file_location('closed_loop_maneuver_suite', suite_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_all_19_dofs_and_9_control_surfaces_authority_and_signs():
    suite = _load_maneuver_suite()
    for profile_id in ('rc01-planing-3pt-v1', 'rc01-hydrofoil-ski-v1'):
        res_a = suite.run_maneuver_a_authority_at_rest(profile_id)
        topo = res_a['topology']

        # 19 total velocity DOFs: 6 freejoint + 2 sponson slide + 2 fan spin + 9 control surfaces
        assert topo['nv'] == 19, f"{profile_id} expected 19 DOFs, got {topo['nv']}"
        assert topo['nq'] == 20, f"{profile_id} expected 20 qpos entries, got {topo['nq']}"
        assert topo['njnt'] == 14, f"{profile_id} expected 14 joints, got {topo['njnt']}"
        assert topo['nu'] == 11, f"{profile_id} expected 11 actuators (2 fan motors + 9 surface servos), got {topo['nu']}"
        assert topo['category_dofs'] == {
            'freejoint': 6,
            'sponson_slide': 2,
            'fan_spin': 2,
            'control_surface': 9,
        }

        # Verify each surface reached its exact signed deflection with rate-limited slew
        assert res_a['passed'], f"{profile_id} Maneuver A failed: {res_a}"
        assert res_a['worst_tracking_error_deg'] < 0.35
        segs = {s['segment']: s for s in res_a['segments']}

        # +aileron_deg (+25 deg right roll) -> port TE down (-25 deg), stbd TE up (+25 deg)
        assert segs['aileron_pos_25']['achieved_deg']['aileron_port_hinge'] == pytest.approx(-25.0, abs=0.25)
        assert segs['aileron_pos_25']['achieved_deg']['aileron_stbd_hinge'] == pytest.approx(25.0, abs=0.25)
        assert segs['aileron_pos_25']['control_surfaces_obs']['aileron']['achieved_deg'] == pytest.approx(25.0, abs=0.25)

        # -aileron_deg (-25 deg left roll) -> port TE up (+25 deg), stbd TE down (-25 deg)
        assert segs['aileron_neg_25']['achieved_deg']['aileron_port_hinge'] == pytest.approx(25.0, abs=0.25)
        assert segs['aileron_neg_25']['achieved_deg']['aileron_stbd_hinge'] == pytest.approx(-25.0, abs=0.25)
        assert segs['aileron_neg_25']['control_surfaces_obs']['aileron']['achieved_deg'] == pytest.approx(-25.0, abs=0.25)

        # Elevator +/-20 deg
        assert segs['elevator_pos_20']['achieved_deg']['elevator_hinge'] == pytest.approx(20.0, abs=0.25)
        assert segs['elevator_neg_20']['achieved_deg']['elevator_hinge'] == pytest.approx(-20.0, abs=0.25)
        assert segs['elevator_pos_20']['control_surfaces_obs']['elevator']['achieved_deg'] == pytest.approx(20.0, abs=0.25)

        # Rudder +/-30 deg
        assert segs['rudder_pos_30']['achieved_deg']['rudder_hinge'] == pytest.approx(30.0, abs=0.25)
        assert segs['rudder_neg_30']['achieved_deg']['rudder_hinge'] == pytest.approx(-30.0, abs=0.25)
        assert segs['rudder_pos_30']['control_surfaces_obs']['rudder']['achieved_deg'] == pytest.approx(30.0, abs=0.25)

        # Reverse buckets 0..1 -> 0..85 deg
        assert segs['reverse_bucket_deploy']['achieved_deg']['reverse_bucket_port_hinge'] == pytest.approx(85.0, abs=0.35)
        assert segs['reverse_bucket_deploy']['achieved_deg']['reverse_bucket_stbd_hinge'] == pytest.approx(85.0, abs=0.35)
        assert segs['reverse_bucket_deploy']['control_surfaces_obs']['reverse_bucket']['achieved_frac'] == pytest.approx(1.0, abs=0.01)
        assert segs['reverse_bucket_stow']['control_surfaces_obs']['reverse_bucket']['achieved_frac'] == pytest.approx(0.0, abs=0.01)

        # Main skis collective + differential
        assert segs['ski_collective_8_diff_pos_3']['achieved_deg']['ski_port_incidence'] == pytest.approx(11.0, abs=0.25)
        assert segs['ski_collective_8_diff_pos_3']['achieved_deg']['ski_stbd_incidence'] == pytest.approx(5.0, abs=0.25)
        assert segs['ski_collective_6_diff_neg_3']['achieved_deg']['ski_port_incidence'] == pytest.approx(3.0, abs=0.25)
        assert segs['ski_collective_6_diff_neg_3']['achieved_deg']['ski_stbd_incidence'] == pytest.approx(9.0, abs=0.25)

        # Aft trim ski +6 / -3 deg
        assert segs['aft_ski_pos_6']['achieved_deg']['ski_aft_incidence'] == pytest.approx(6.0, abs=0.25)
        assert segs['aft_ski_neg_3']['achieved_deg']['ski_aft_incidence'] == pytest.approx(-3.0, abs=0.25)
        assert segs['aft_ski_pos_6']['control_surfaces_obs']['aft_ski']['achieved_deg'] == pytest.approx(6.0, abs=0.25)

        # Rate-limited slew check on all 9 control surfaces
        for jn, rate in res_a['peak_slew_rate_deg_s'].items():
            assert 20.0 < rate < 220.0, f"{profile_id} joint {jn} unexpected slew rate {rate} deg/s"

        # Twin fan differential thrust check (+differential_thrust spins stbd rotor faster than port rotor)
        rpm_port, rpm_stbd = res_a['diff_thrust_fan_rpm']
        assert rpm_stbd > rpm_port > 1000.0


def test_ricochet_action_normalization_and_live_observation_loop():
    suite = _load_maneuver_suite()

    # 1. Verify all 10 control channels via aliases, unit tags, nested surfaces dict, and clamping
    raw = {
        'authority': 'colin',
        'observation_id': 7,
        'text': 'half throttle, hard port rudder',
        'surfaces': {
            'diff_thrust': '25% left',
            'stabilator': '12 deg nose up',
            'ailerons': [-10.0, 10.0],
            'reverser_deg': 42.5,
            'ski_collective': 7.5,
            'ski_diff': -2.5,
            'stern_ski': 4.0,
            'trim_ecu': 0.85,
        },
    }
    norm = normalize_ricochet_action(raw)
    act = RicochetAction.model_validate(norm)
    assert act.authority == 'colin'
    assert act.observation_id == 7
    assert act.throttle == pytest.approx(0.50)
    assert act.rudder_deg == pytest.approx(30.0)
    assert act.differential_thrust == pytest.approx(-0.25)
    assert act.elevator_deg == pytest.approx(12.0)
    assert act.aileron_deg == pytest.approx(10.0)
    assert act.reverse_bucket == pytest.approx(0.50)
    assert act.ski_incidence_deg == pytest.approx(7.5)
    assert act.ski_differential_deg == pytest.approx(-2.5)
    assert act.aft_ski_incidence_deg == pytest.approx(4.0)
    assert act.ecu_assist == pytest.approx(0.85)

    # 2. Out-of-range values clamp cleanly to schema mechanical limits
    clamped = RicochetAction.model_validate(normalize_ricochet_action({
        'throttle': 1.8,
        'differential_thrust': -2.0,
        'rudder_deg': -90.0,
        'elevator_deg': 45.0,
        'aileron_deg': -60.0,
        'reverse_bucket': 1.5,
        'ski_incidence_deg': 25.0,
        'ski_differential_deg': 9.0,
        'aft_ski_incidence_deg': -20.0,
        'ecu_assist': 2.0,
    }))
    assert clamped.throttle == pytest.approx(1.0)
    assert clamped.differential_thrust == pytest.approx(-1.0)
    assert clamped.rudder_deg == pytest.approx(-30.0)
    assert clamped.elevator_deg == pytest.approx(20.0)
    assert clamped.aileron_deg == pytest.approx(-25.0)
    assert clamped.reverse_bucket == pytest.approx(1.0)
    assert clamped.ski_incidence_deg == pytest.approx(12.0)
    assert clamped.ski_differential_deg == pytest.approx(4.0)
    assert clamped.aft_ski_incidence_deg == pytest.approx(-8.0)
    assert clamped.ecu_assist == pytest.approx(1.0)

    # 3. Verify sensor_observation() -> normalize_ricochet_action() -> RicochetAction -> set_command() loop
    world = suite.make_open_lake_world(half_x=400.0, half_y=200.0)
    cfg = WaterEnvironmentConfig(water_level_m=7.0, wave_mode='still', wake_enabled=False, whirlpools_enabled=False)
    for profile_id in ('rc01-planing-3pt-v1', 'rc01-hydrofoil-ski-v1'):
        craft = RicochetCraft(
            world, variant='ricochet-concept-a', hull_variant='concept_a',
            load_case='LC-01', water_config=cfg, profile=profile_id,
        )
        craft.spawn(-100.0, 0.0, 7.0)
        lab = suite.TelemetryOnlyPilotHarness(craft)
        obs = lab.observe()
        assert obs['action_schema'] == 'ricochet-1'
        assert obs['profile_id'] == profile_id
        assert obs['capsized'] is False
        assert set(obs['command']) == {
            'throttle', 'differential_thrust', 'rudder_deg', 'elevator_deg', 'aileron_deg',
            'reverse_bucket', 'ski_incidence_deg', 'ski_differential_deg', 'aft_ski_incidence_deg', 'ecu_assist',
        }
        assert 'skis' in obs['control_surfaces']
        assert 'aft_ski' in obs['control_surfaces']
        assert len(obs['ski_feedback_deg']) == 2
        # Ensure truth-only internal arrays are never leaked in pilot telemetry
        for forbidden_key in ('qpos', 'qvel', 'xfrc_applied', 'qfrc_applied'):
            assert forbidden_key not in obs

        lab.act({'ski_incidence': 5.0, 'ski_diff': 2.0, 'aft_ski': 3.0, 'ecu': 0.0})
        for _ in range(int(round(0.6 / craft.DT))):
            craft.step()
        obs2 = lab.observe()
        assert obs2['ski_feedback_deg'][0] == pytest.approx(7.0, abs=0.2)
        assert obs2['ski_feedback_deg'][1] == pytest.approx(3.0, abs=0.2)
        assert obs2['control_surfaces']['aft_ski']['achieved_deg'] == pytest.approx(3.0, abs=0.2)


def test_closed_loop_maneuvers_option1_and_option2():
    suite = _load_maneuver_suite()
    out_json = ROOT / 'scratch' / 'complete_model' / 'closed_loop_maneuver_report.json'
    report = suite.run_qualification_suite(out_json, include_maneuver_a=False)
    assert out_json.is_file()
    assert report['all_passed'] is True

    expected_revisions = {
        'rc01-planing-3pt-v1': 'RC01-P1-R1',
        'rc01-hydrofoil-ski-v1': 'RC01-H1-R1',
    }
    for profile_id, exp_rev in expected_revisions.items():
        prof_rep = report['profiles'][profile_id]
        assert prof_rep['all_passed'] is True
        assert prof_rep['model_revision'] == exp_rev
        m_b = prof_rep['maneuvers']['B_takeoff_and_cruise']
        m_c = prof_rep['maneuvers']['C_coordinated_s_turn']
        m_d = prof_rep['maneuvers']['D_reverse_bucket_braking']

        # Maneuver B: Closed-Loop Takeoff -> Hump Clearance -> High-Speed Cruise
        assert m_b['passed'] is True
        assert m_b['hull_liftoff_t_s'] is not None and m_b['hull_liftoff_t_s'] < 10.0
        assert m_b['t_to_12mps_s'] is not None and m_b['t_to_12mps_s'] < 16.0
        assert m_b['peak_speed_mps'] > 18.0
        assert m_b['min_vol_hull_m3'] < 0.02
        assert m_b['max_abs_roll_deg'] < 5.0
        assert m_b['capsized'] is False

        # Maneuver C: High-Speed Coordinated S-Turn at 12-18+ m/s
        assert m_c['passed'] is True
        assert m_c['max_port_yaw_deg'] >= 5.0
        assert m_c['min_stbd_yaw_deg'] <= -4.0
        assert m_c['heading_swing_deg'] >= 10.0
        assert m_c['max_abs_roll_deg'] < 18.0
        assert m_c['max_abs_yaw_rate_deg_s'] < 45.0
        assert m_c['capsized'] is False

        # Maneuver D: High-Speed Reverse-Bucket Water Braking & Stop
        assert m_d['passed'] is True
        assert m_d['entry_speed_mps'] > 15.0
        assert m_d['final_speed_mps'] < 2.0
        assert m_d['min_nose_up_deg'] > -6.0
        assert m_d['max_reverse_bucket_fraction'] > 0.95
        assert m_d['final_reverse_bucket_fraction'] < 0.05
        assert m_d['capsized'] is False
        assert 'IMPACT' not in m_d['warning_lamps']


def test_harbour_live_profile_switching_both_selectable():
    world = harbour_world()
    fleet = HarbourFleet(world)

    # Initially both vessels are Legacy Concept A (profile=None, revision RC01-CA-0, 16 DOFs each -> 32 shared DOFs)
    assert fleet.crafts['ricochet-airport'].profile_id is None
    assert fleet.crafts['ricochet-airport'].model_revision == 'RC01-CA-0'
    assert fleet.crafts['ricochet-marina'].profile_id is None
    assert fleet.crafts['ricochet-marina'].model_revision == 'RC01-CA-0'
    assert fleet.crafts['ricochet-airport'].model.nv == 16
    assert fleet.crafts['ricochet-marina'].model.nv == 16
    assert fleet.model.nv == 32

    # Release ricochet-airport and drive it underway so it builds velocity and an active wake
    assert fleet.release('ricochet-airport')['ok']
    assert fleet.action('ricochet-airport', {'throttle': 0.45, 'rudder_deg': 4.0})['ok']
    for _ in range(25):
        fleet.step()

    pos_airport_before, heading_airport_before, vel_airport_before = fleet._pose('ricochet-airport')
    assert float(np.linalg.norm(vel_airport_before[3:5])) > 0.05
    assert 'ricochet-airport' in fleet.water.wakes
    wake_before = dict(fleet.water.wakes['ricochet-airport'])

    # 1. Switch ricochet-marina live using its Model Revision Name 'RC01-P1-R1' (Option 1: 'rc01-planing-3pt-v1', 19 DOFs)
    fleet.select('ricochet-marina')
    fleet = _restart_boat(world, fleet, {'boatId': 'ricochet-marina', 'profile': 'RC01-P1-R1'})
    assert fleet.crafts['ricochet-marina'].profile_id == 'rc01-planing-3pt-v1'
    assert fleet.crafts['ricochet-marina'].model_revision == 'RC01-P1-R1'
    assert fleet.crafts['ricochet-marina'].model.nv == 19
    assert fleet.crafts['ricochet-airport'].profile_id is None
    assert fleet.crafts['ricochet-airport'].model.nv == 16
    assert fleet.model.nv == 35  # 16 + 19

    # Verify ricochet-airport preserved its exact state, command, undocked status, and wake
    pos_after_1, heading_after_1, vel_after_1 = fleet._pose('ricochet-airport')
    np.testing.assert_allclose(pos_after_1, pos_airport_before, atol=1e-12)
    assert heading_after_1 == pytest.approx(heading_airport_before, abs=1e-12)
    np.testing.assert_allclose(vel_after_1, vel_airport_before, atol=1e-12)
    assert fleet.crafts['ricochet-airport'].command['throttle'] == pytest.approx(0.45)
    assert 'ricochet-airport' not in fleet.moorings
    assert fleet.water.wakes.get('ricochet-airport') == wake_before

    # Exercise Option 1 ski controls on ricochet-marina and step the mixed fleet
    assert fleet.action('ricochet-marina', {'ski_incidence_deg': 6.0, 'aft_ski_incidence_deg': 3.0, 'ecu_assist': 0.0})['ok']
    for _ in range(15):
        fleet.step()
    vg_opt1 = fleet.visual_geometry('ricochet-marina')
    assert {'ski_port', 'ski_stbd', 'ski_aft'}.issubset({m['name'] for m in vg_opt1['meshes']})

    # 2. Switch ricochet-marina live from Option 1 -> Option 2 using Model Revision Name 'RC01-H1-R1' ('rc01-hydrofoil-ski-v1', 19 DOFs)
    pos_airport_before_2, heading_airport_before_2, vel_airport_before_2 = fleet._pose('ricochet-airport')
    wake_before_2 = dict(fleet.water.wakes['ricochet-airport'])
    fleet = _restart_boat(world, fleet, {'boatId': 'ricochet-marina', 'profile': 'RC01-H1-R1'})
    assert fleet.crafts['ricochet-marina'].profile_id == 'rc01-hydrofoil-ski-v1'
    assert fleet.crafts['ricochet-marina'].model_revision == 'RC01-H1-R1'
    assert fleet.crafts['ricochet-marina'].model.nv == 19
    assert fleet.crafts['ricochet-marina'].profile['skis']['hydro_mode'] == 'hydrofoil_ski'
    assert fleet.crafts['ricochet-marina'].surface_limits['aft_ski_incidence_deg']['min'] == pytest.approx(-6.0)
    assert fleet.model.nv == 35

    pos_after_2, heading_after_2, vel_after_2 = fleet._pose('ricochet-airport')
    np.testing.assert_allclose(pos_after_2, pos_airport_before_2, atol=1e-12)
    assert heading_after_2 == pytest.approx(heading_airport_before_2, abs=1e-12)
    np.testing.assert_allclose(vel_after_2, vel_airport_before_2, atol=1e-12)
    assert fleet.water.wakes.get('ricochet-airport') == wake_before_2

    # Exercise Option 2 hydrofoil-ski negative trim and verify bit-exact serialize/restore
    assert fleet.action('ricochet-marina', {'ski_incidence_deg': -2.5, 'aft_ski_incidence_deg': -4.5, 'ecu_assist': 0.0})['ok']
    for _ in range(15):
        fleet.step()
    saved_state = json.loads(json.dumps(fleet.serialize(), allow_nan=False))
    restored = HarbourFleet.restore(world, saved_state)
    assert restored.crafts['ricochet-marina'].profile_id == 'rc01-hydrofoil-ski-v1'

    # 3. Switch ricochet-marina live from Option 2 -> Legacy Concept A (None, 16 DOFs)
    pos_airport_before_3, _, vel_airport_before_3 = fleet._pose('ricochet-airport')
    fleet = _restart_boat(world, fleet, {'boatId': 'ricochet-marina', 'profile': None})
    assert fleet.crafts['ricochet-marina'].profile_id is None
    assert fleet.crafts['ricochet-marina'].model.nv == 16
    assert fleet.model.nv == 32
    pos_after_3, _, vel_after_3 = fleet._pose('ricochet-airport')
    np.testing.assert_allclose(pos_after_3, pos_airport_before_3, atol=1e-12)
    np.testing.assert_allclose(vel_after_3, vel_airport_before_3, atol=1e-12)
    assert 'ricochet-airport' in fleet.water.wakes
