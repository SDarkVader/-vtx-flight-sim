"""Selector transactions with real aircraft, harbour plants and isolated saves."""
import asyncio
import json

import numpy as np
import pytest
from fastapi import HTTPException
from vtx import live_server as server
from vtx.harbour_session import _restart_boat
from vtx.harbour_fleet import HarbourFleet
from vtx.phantom import identity
from test_harbour_fleet import harbour_world


def test_active_switch_reposition_restart_and_restore(tmp_path, monkeypatch):
    lab = server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, "lab", lab)
    def preview(variant, **options):
        return asyncio.run(server.model_preview(dict(airframe_variant=variant, **options)))

    mission = server.Mission(airframe_variant="phantom-a10c", environment="airport",
                             departure=[-3885, 0], phantom={"start_configuration":"road"})
    original = lab.start(mission)["run_id"]
    lab.integrate()
    before = lab.aircraft.data.qpos.copy()
    for payload in [dict(save_run_id="another-flight"), dict(save_run_id=original, departure=[1e6, 0])]:
        with pytest.raises(HTTPException):
            preview("r6", **payload)
        assert lab.active and lab.run_id == original
        np.testing.assert_array_equal(lab.aircraft.data.qpos, before)
    selected = preview("r6", save_run_id=original, departure=[300, 0], environment="airport")
    assert not selected["active"] and selected["observation"]["configuration"]["airframe_variant"] == "r6"
    checkpoint = lab.saved_flights_path / (original + ".json")
    retained = checkpoint.read_bytes()
    assert selected["rendering_truth"]["provenance"]["render_asset"] == "/assets/airframe-r6.glb"
    second = lab.start(server.Mission(airframe_variant="r6", departure=[300, 0], fuel_kg=25))["run_id"]
    restarted = asyncio.run(server.restart_flight({"run_id":second}))["run_id"]
    assert restarted != second and list(lab.aircraft.fuel_initial) == [6.25]*4
    assert lab.mission["departure"] == [300, 0]
    preview("r6", save_run_id=restarted, departure=[-700, 0], environment="sandbox")
    assert not lab.active and lab.world.environment_key == "sandbox"
    reloaded = server.Laboratory(data_root=tmp_path)
    assert reloaded.aircraft.airframe_variant == "r6" and reloaded.world.environment_key == "sandbox"
    np.testing.assert_array_equal(reloaded.aircraft.fuel_initial,[6.25]*4)
    np.testing.assert_allclose(reloaded.aircraft.data.qpos[:2], [-700, 0])
    assert checkpoint.read_bytes() == retained
    reloaded.restore_saved_flight(original)
    assert reloaded.active and reloaded.paused and reloaded.aircraft.variant == "phantom-a10c"
    np.testing.assert_array_equal(reloaded.aircraft.data.qpos, before)
    reloaded.stop("Isolated selector check")


def test_a10d_restart_and_saved_flights_keep_their_own_ecu(tmp_path, monkeypatch):
    lab = server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, "lab", lab)
    assert not lab.inspection_selection_known
    c_run = lab.start(server.Mission(airframe_variant="phantom-a10c"))["run_id"]
    d_preview = asyncio.run(server.model_preview({"airframe_variant": "phantom-a10d", "save_run_id": c_run}))
    pins = identity.pins()
    d_pin = pins["phantom-a10d"]
    selected = d_preview["observation"]["configuration"]["identity"]
    assert selected["variant"] == "phantom-a10d" and selected["verified"]
    assert selected["config_sha256"] == d_pin["config_sha256"]
    assert selected["render_asset_sha256"] == d_pin["render_asset_sha256"]
    c_checkpoint = lab.saved_flights_path / (c_run + ".json")
    c_bytes = c_checkpoint.read_bytes()

    d_run = lab.start(server.Mission(airframe_variant="phantom-a10d"))["run_id"]
    lab.accept_action(server.parse_action(dict(schema="phantom-fbw-1", authority=lab.authority,
                                               reason="A10-D selector regression", airbrake="on")))
    for _ in range(20):
        lab.integrate()
    assert lab.aircraft.ecu_status()["airbrake"] == "on"
    d_restart = asyncio.run(server.restart_flight({"run_id": d_run}))["run_id"]
    assert d_restart != d_run and lab.aircraft.variant == "phantom-a10d"
    assert lab.aircraft.ecu_status()["airbrake"] == "off"
    c_preview = asyncio.run(server.model_preview({"airframe_variant": "phantom-a10c", "save_run_id": d_restart}))
    assert c_preview["observation"]["configuration"]["airframe_variant"] == "phantom-a10c"
    assert "transition_ecu" not in c_preview["rendering_truth"]["phantom"]
    assert c_checkpoint.read_bytes() == c_bytes

    recovered = server.Laboratory(data_root=tmp_path)
    assert recovered.aircraft.variant == "phantom-a10c"
    d_checkpoint = recovered.saved_flights_path / (d_run + ".json")
    d_bytes = d_checkpoint.read_bytes()
    with monkeypatch.context() as mismatch:
        mismatch.setattr(identity, "pins", lambda: {**pins, "phantom-a10d": {**d_pin, "config_sha256": "0" * 64}})
        with pytest.raises(HTTPException, match="pinned identity"):
            recovered.restore_saved_flight(d_run)
    assert not recovered.active and d_checkpoint.read_bytes() == d_bytes
    recovered.restore_saved_flight(d_run)
    assert recovered.paused and recovered.aircraft.variant == "phantom-a10d"
    assert recovered.aircraft.ecu_status()["airbrake"] == "on"
    recovered.stop("A10-D restore checked")
    recovered.restore_saved_flight(c_run)
    assert recovered.paused and recovered.aircraft.variant == "phantom-a10c"
    assert not recovered.aircraft.fcc.transition
    recovered.stop("A10-C restore checked")


def test_ricochet_restart_preserves_other_vessel_water_and_identity():
    world = harbour_world()
    fleet = HarbourFleet(world)
    boat, other = "ricochet-marina", "ricochet-airport"
    fleet.release(other)
    fleet.action(other, {"throttle":0.1, "rudder_deg":3})
    fleet.select(boat)
    for _ in range(7):
        fleet.step()
    prior = fleet.serialize()
    with pytest.raises(ValueError):
        _restart_boat(world, fleet, {"boatId":other})
    with pytest.raises(ValueError):
        _restart_boat(world, fleet, {"boatId":boat, "position":[3000, 4000]})
    candidate = _restart_boat(world, fleet, {"boatId":boat, "position":[0, 0]})
    after = candidate.serialize()
    assert after["water"] == prior["water"] and after["boats"][other] == prior["boats"][other]
    assert after["step_count"] == prior["step_count"] and candidate.selectedId == boat
    assert fleet.serialize() == prior
    assert boat not in candidate.moorings and candidate.crafts[boat].command["throttle"] == 0
    assert candidate.public()["boats"][1]["position"][:2] == [0, 0]
    candidate.step()
    home = _restart_boat(world, candidate, {"boatId":boat})
    home.step()
    restored = HarbourFleet.restore(world, json.loads(json.dumps(home.serialize())))
    assert restored.selectedId == boat and restored.occupancy == home.occupancy
    assert restored.moorings[boat]["berth_id"] == "lantern-marina-ricochet"
