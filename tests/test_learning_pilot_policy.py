"""Ordinary pilot gateways; offline fixtures only, no live connections."""

import asyncio
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi import HTTPException
import vtx.live_server as server


def legacy_action(lab, observation, **changes):
    values = dict(
        authority=lab.authority,
        expected_run_id=lab.run_id,
        observation_id=observation["observation_id"],
        reason="Observed current instruments",
        engine=0.2,
        collective_deg=[0.0] * 4,
        tilt_deg=[[0.0, 0.0]] * 4,
    )
    values.update(changes)
    return server.Action(**values)


def test_ai_actions_need_current_run_and_unsuperseded_permitted_observation(tmp_path):
    lab = server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(authority="colin"))
    try:
        obs = lab.sensor_observation()
        with pytest.raises(HTTPException, match="current run"):
            lab.accept_action(legacy_action(lab, obs, expected_run_id=None))
        with pytest.raises(HTTPException):
            lab.accept_action(legacy_action(lab, obs, expected_run_id="other"))
        # A model may think slowly while the last controls/connection hold stay
        # unchanged. No arbitrary simulation-time latency limit is imposed.
        lab.aircraft.data.time = 20.0
        accepted = lab.accept_action(legacy_action(lab, obs))
        assert accepted["accepted"] and lab.action_log[-1]["observation"] == obs
        before = lab.aircraft.data.qpos.copy()
        count = len(lab.action_log)
        with pytest.raises(HTTPException, match="superseded"):
            lab.accept_action(legacy_action(lab, obs))
        assert len(lab.action_log) == count
        np.testing.assert_array_equal(lab.aircraft.data.qpos, before)
        lab.last_sensor_t = -1.0
        lab.last_obs = None
        fresh = lab.sensor_observation()
        assert lab.accept_action(legacy_action(lab, fresh))["accepted"]
    finally:
        lab.stop("Offline pilot envelope check")


def test_manual_controls_do_not_acquire_an_ai_freshness_requirement(tmp_path):
    lab = server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(authority="manual"))
    try:
        assert lab.accept_action(
            legacy_action(lab, {"observation_id": None}, expected_run_id=None)
        )["accepted"]
    finally:
        lab.stop("Offline human controls check")


def test_ai_text_macro_refused_but_human_instant_configuration_and_status_remain(
    tmp_path, monkeypatch
):
    actions = []
    obs = dict(
        observation_id=7, t_s=1.0, pod_tilt_deg=[90.0] * 4, weight_on_wheels=True
    )

    def accept(action):
        actions.append(action)
        return dict(sequence=len(actions), apply_t_s=1.02)

    lab = SimpleNamespace(
        aircraft=SimpleNamespace(is_phantom=True),
        active=True,
        paused=True,
        run_id="unit-run",
        authority="manual",
        data_root=tmp_path,
        sensor_observation=lambda: dict(obs),
        log=lambda *args: None,
        accept_action=accept,
    )
    monkeypatch.setattr(server, "lab", lab)
    refused = asyncio.run(
        server.pilot_command(server.PilotCommand(text="take us up", source="ai"))
    )
    assert (
        refused["rejected"] == "AI text macros are disabled"
        and not refused["accepted"]
        and not actions
    )
    assert "patch" not in refused
    status = asyncio.run(
        server.pilot_command(server.PilotCommand(text="status", source="ai"))
    )
    assert status["intent"] == "status" and not actions
    human = asyncio.run(
        server.pilot_command(
            server.PilotCommand(text="takeoff configuration", source="text")
        )
    )
    assert human["accepted"] and len(actions) == 1
    assert actions[0].wing == "deploy" and actions[0].flap_deg == [30.0, 30.0]


def test_station_bridge_rejects_preprogrammed_waypoint_mode(tmp_path):
    import json
    from tools.persistent_pilot import DEFAULT, load_config

    path = tmp_path / "controls.json"
    path.write_text(json.dumps(dict(DEFAULT, waypoint_mode=True)))
    with pytest.raises(ValueError, match="waypoint navigation is offline only"):
        load_config(path)
    path.write_text(
        json.dumps(
            dict(DEFAULT, waypoint_mode=False, armed=True, arm_run_id="unit", serial=1)
        )
    )
    assert load_config(path)["armed"]


def test_legacy_live_navigator_cannot_open_game_connection():
    from tools.closed_loop_pilot import main

    with pytest.raises(SystemExit, match="offline only"):
        main()


def test_ai_cannot_arm_a_timed_fcc_program_but_can_abort_one():
    from vtx.phantom.controls import PhantomAction

    lab = SimpleNamespace(
        active=True,
        run_id="unit-run",
        authority="colin",
        aircraft=SimpleNamespace(is_phantom=True, data=SimpleNamespace(time=1.0)),
        fallback_controller=None,
        pilot_owner=None,
        pending_pilot=None,
        pilot_epoch=0,
        action_log=[],
        observations={7: {"t_s": 1.0}},
        action_sequence=0,
        log=lambda *args: None,
        clock_lag_s=0.0,
        time_scale=1.0,
    )
    base = dict(
        schema="phantom-fbw-1",
        authority="colin",
        expected_run_id="unit-run",
        observation_id=7,
        reason="Observed instruments",
    )
    for kind in ("step", "doublet", "3211", "sweep"):
        with pytest.raises(HTTPException, match="Timed test excitation"):
            server.Laboratory.accept_action(
                lab, PhantomAction(**base, pti={"type": kind})
            )
    accepted = server.Laboratory.accept_action(
        lab, PhantomAction(**base, pti={"command": "abort"})
    )
    assert accepted["accepted"] and len(lab.action_log) == 1


def test_command_readback_does_not_claim_cancelled_action_was_executed(
    tmp_path, monkeypatch
):
    obs = dict(observation_id=7, t_s=1.0, pod_tilt_deg=[90.0] * 4)
    lab = SimpleNamespace(
        aircraft=SimpleNamespace(
            is_phantom=True,
            data=SimpleNamespace(time=1.03),
            fcc=SimpleNamespace(cmd={"wing": "deploy"}),
        ),
        active=True,
        paused=False,
        run_id="unit-run",
        authority="manual",
        data_root=tmp_path,
        sensor_observation=lambda: dict(obs),
        log=lambda *args: None,
        action_log=[dict(sequence=1, cancelled=True)],
    )
    lab.accept_action = lambda action: dict(sequence=1, apply_t_s=1.02)
    monkeypatch.setattr(server, "lab", lab)
    monkeypatch.setattr(
        server, "get_recorder", lambda *args: SimpleNamespace(emit=lambda *args: None)
    )
    result = asyncio.run(server.pilot_command(server.PilotCommand(text="deploy wings")))
    assert (
        result["accepted"]
        and not result["executed"]
        and "cancelled" in result["not_applied"]
    )
