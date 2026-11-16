import asyncio
from copy import deepcopy
import json

import pytest
from fastapi import HTTPException
from vtx import live_server
from vtx.live_server import Laboratory, Mission, world_fingerprint
from vtx.mission_selection import MapPoint
from vtx.phantom.mission import validate_phantom
from vtx.world import make_world


def test_native_airport_harbour_support_and_identity():
    world = make_world("airport")
    assert world.harbour["accessPath"] == [[205, -112.5], [205, -550]]
    assert len(world.harbour["docks"]["berths"]) == 8
    assert "harbour" not in make_world("sandbox").public()
    assert world.validate(MapPoint(-700, 0), "departure").valid
    water = MapPoint(-2130, -1955)
    assert not world.validate(water, "departure").valid
    assert not validate_phantom(world, water, "phantom-a10c")["ok"]
    assert 0 <= world.terrain_z(water.x_m, water.y_m) < world.harbour["waterLevelM"]
    assert world.terrain_z(205, -500) == 0
    assert world.harbour_water_mask(water.x_m, water.y_m)
    assert not world.harbour_water_mask(-700, 0)
    old = world_fingerprint(world)
    world.harbour["docks"]["berths"][0]["width"] += 0.1
    assert world_fingerprint(world) != old


def test_native_save_and_restore_flight_includes_both_boats_and_berths(tmp_path, monkeypatch):
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, "lab", lab)

    def act(action, **values):
        return asyncio.run(live_server.harbour_action(dict(action=action, **values)))

    try:
        original = act("activate")
        ids = [b["id"] for b in original["boats"]]
        assert len(ids) == 2 and all(
            b["variant"] == "ricochet-concept-a" for b in original["boats"]
        )
        assert lab.aircraft.airframe_variant == "r6"
        act("select", boatId=ids[1])
        act("save")
        act("undock", boatId=ids[0])
        flight = lab.start(
            Mission(
                environment="airport",
                airframe_variant="r6",
                departure=[-700, 0],
                destination=[-700, 0],
            )
        )
        parked = lab.save_flight_for_switching(flight["run_id"])
        assert parked["saved"]
        saved = lab.saved_flights_path / (flight["run_id"] + ".json")
        checkpoint = json.loads(saved.read_bytes())
        assert checkpoint["harbour_fleet"]["schema"] == "airport-harbour-gzip-1"
        assert act("restore")["occupancy"] == original["occupancy"]
        # Corrupt fleet data must leave the parked flight and current fleet usable.
        damaged = deepcopy(checkpoint)
        damaged["harbour_fleet"]["sha256"] = "0" * 64
        saved.write_text(json.dumps(damaged), encoding="utf-8")
        with pytest.raises(HTTPException, match="digest mismatch"):
            lab.restore_saved_flight(flight["run_id"])
        assert not lab.active and saved.is_file()
        assert lab.harbour_session.status(lab.world)["occupancy"] == original["occupancy"]
        saved.write_text(json.dumps(checkpoint), encoding="utf-8")
        assert lab.restore_saved_flight(flight["run_id"])["paused"]
        restored = lab.harbour_session.status(lab.world)
        assert restored["selectedId"] == ids[1]
        assert restored["boats"][0]["dockedAt"] is None
        assert restored["boats"][1]["dockedAt"] == original["boats"][1]["dockedAt"]
        assert [b["position"] for b in restored["boats"]] == [
            b["position"] for b in original["boats"]
        ]
        assert lab.aircraft.airframe_variant == "r6"
    finally:
        lab.harbour_session.close()
        if lab.audit_file:
            lab.audit_file.close()
