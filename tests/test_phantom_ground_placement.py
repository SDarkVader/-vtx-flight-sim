import asyncio
import math

import numpy as np
import pytest

from vtx import live_server as server
from vtx.mission_selection import MapPoint
from vtx.phantom.live import make_aircraft
from vtx.world import make_world


@pytest.mark.parametrize("configuration,prefix", [("road", "tyre"), ("vtol", "foot")])
def test_phantom_preview_and_start_fit_the_slope(tmp_path, monkeypatch, configuration, prefix):
    lab = server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, "lab", lab)
    world = lab.world
    x = np.linspace(-world.half, world.half, world.n)
    world.heights[:] = 80.0 + math.tan(math.radians(3.0)) * x
    departure = [-700.0, 0.0]
    heading = 212.3
    point = MapPoint(*departure)
    assert not world.validate(point, "departure").valid
    assert server.landing_support(world, point, "departure", "phantom-a10d").valid
    assert not server.landing_support(world, MapPoint(115, 115), "departure", "phantom-a10d").valid

    selection = dict(airframe_variant="phantom-a10d", departure=departure, departure_heading_deg=heading)
    preview = asyncio.run(server.model_preview({**selection, "start_configuration": configuration}))
    preview_pose = lab.aircraft.data.qpos[:7].copy()
    assert preview["departure_heading_deg"] == heading
    forward = lab.aircraft.R()[:, 0]
    actual_heading = (90.0 - math.degrees(math.atan2(forward[1], forward[0]))) % 360.0
    assert actual_heading == pytest.approx(heading)
    assert lab.aircraft.R()[:, 2] == pytest.approx([-math.sin(math.radians(3)), 0., math.cos(math.radians(3))], abs=2e-5)

    lab.start(server.Mission(**selection, phantom={"start_configuration": configuration}))
    np.testing.assert_array_equal(lab.aircraft.data.qpos[:7], preview_pose)
    assert lab.mission['departure_heading_deg'] == heading
    try:
        lab.integrate()
        assert all(contact.dist >= 0 for contact in lab.aircraft.data.contact)
        for _ in range(399):
            lab.integrate()
        assert not lab.aircraft.crashed
        assert set(lab.aircraft.support) == {f"{prefix}_{pod}" for pod in ("FL", "FR", "RL", "RR")}
    finally:
        lab.stop("Ground placement test complete")


def test_vaderland_road_crossfall_and_grade_change():
    world = make_world("vaderland-33", seed=41031)
    for departure, heading in (([-26.4, 1237.7], 90.0), ([-7.65, 638.87], 180.0)):
        mission = server.Mission(airframe_variant="phantom-a10d", departure=departure,
                                 departure_heading_deg=heading, phantom={"start_configuration": "road"})
        decision = server.landing_support(world, MapPoint(*departure), "departure", mission.airframe_variant)
        assert decision.valid
        craft = make_aircraft(world, mission)
        server.place_at_departure(craft, mission, decision.terrain_z_m)
        craft.step()
        assert all(contact.dist >= 0.0 for contact in craft.data.contact)
        for _ in range(399):
            craft.step()
        assert craft.support_count() == 4
        assert not craft.crashed
