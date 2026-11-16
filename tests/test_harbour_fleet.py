"""Real marine plants in a small isolated world; never a live Laboratory."""

from copy import deepcopy
import json
from types import SimpleNamespace
import numpy as np
import pytest
from vtx.harbour_fleet import HarbourFleet, DT


def harbour_world():
    variants = ["ricochet-concept-a", "ricochet-rc01-f03"]
    berths = []
    piers = []
    for key, x, y in [("airport-landing", 50.0, 50.0), ("lantern-marina", 150.0, 150.0)]:
        bid = key + "-ricochet"
        berths.append(
            dict(
                id=bid,
                name=key,
                harbour=key,
                x=x,
                y=y,
                heading=0.0,
                length=14.0,
                width=12.0,
                approachM=20.0,
                compatibleProfileIds=variants,
                approach=[[x - 20, y], [x, y]],
            )
        )
        piers.append(
            dict(
                id=bid + "-pier",
                center=[x, y + 9.0],
                length=35.0,
                width=4.0,
                heading=0.0,
                berthIds=[bid],
            )
        )
    layout = dict(
        outer=[[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]],
        islands=[],
        routes=[],
        landmarks=[],
    )
    return SimpleNamespace(
        id="isolated-harbour-test",
        version="1",
        environment_key="airport",
        seed=41031,
        half=200.0,
        n=81,
        heights=np.full((81, 81), 2.0),
        obstacles=[],
        harbour=dict(
            origin=[-100.0, 100.0],
            waterLevelM=7.0,
            layout=layout,
            docks=dict(berths=berths, piers=piers),
            accessPath=[],
        ),
    )


def test_two_actual_current_boats_native_json_restore_next_steps_exact():
    world = harbour_world()
    fleet = HarbourFleet(world)
    assert len(fleet.crafts) == 2 and all(
        c.variant == "ricochet-concept-a" for c in fleet.crafts.values()
    )
    assert fleet.release("ricochet-airport")["ok"]
    fleet.action("ricochet-airport", dict(throttle=0.12, rudder_deg=4.0, reverse_bucket=0.3))
    fleet.select("ricochet-marina")
    for _ in range(7):
        fleet.step()
    state = json.loads(json.dumps(fleet.serialize(), allow_nan=False))
    restored = HarbourFleet.restore(world, state)
    assert restored.selectedId == "ricochet-marina"
    assert restored.occupancy == fleet.occupancy and restored.moorings == fleet.moorings
    assert restored.crafts["ricochet-airport"].command == fleet.crafts["ricochet-airport"].command
    np.testing.assert_array_equal(fleet._integration_state(), restored._integration_state())
    np.testing.assert_array_equal(fleet.water.shallow.h, restored.water.shallow.h)
    assert restored.water.wakes == fleet.water.wakes
    for _ in range(13):
        fleet.step()
        restored.step()
        np.testing.assert_allclose(fleet.data.qpos, restored.data.qpos, atol=1e-13, rtol=0)
        np.testing.assert_allclose(fleet.data.qvel, restored.data.qvel, atol=1e-12, rtol=0)
        np.testing.assert_array_equal(fleet.water.shallow.h, restored.water.shallow.h)
        np.testing.assert_array_equal(fleet.water.shallow.hu, restored.water.shallow.hu)
        assert fleet.occupancy == restored.occupancy


def test_claims_commands_and_restore_validation_do_not_replace_active_fleet():
    world = harbour_world()
    fleet = HarbourFleet(world)
    assert not fleet.dock("ricochet-marina", "airport-landing-ricochet")["ok"]
    with pytest.raises(ValueError, match="Release"):
        fleet.action("ricochet-airport", dict(throttle=0.2))
    assert fleet.release("ricochet-airport")["ok"]
    assert fleet.dock("ricochet-airport", "airport-landing-ricochet")["ok"]
    fleet.step()
    state = fleet.serialize()
    before = fleet._integration_state().copy()
    for edit in ("world", "claims", "array", "asset", "variant"):
        bad = deepcopy(state)
        if edit == "world":
            bad["world_sha256"] = "wrong"
        elif edit == "claims":
            bad["occupancy"]["airport-landing-ricochet"] = "missing"
        elif edit == "array":
            bad["integration"][2] = float("nan")
        elif edit == "asset":
            bad["dependencies_sha256"] = "wrong"
        else:
            bad["definitions"][0]["variant"] = "missing-model"
        with pytest.raises((ValueError, KeyError)):
            HarbourFleet.restore(world, bad)
        np.testing.assert_array_equal(before, fleet._integration_state())
    with pytest.raises(ValueError):
        fleet.action("missing", dict(throttle=0.0))
    with pytest.raises(ValueError):
        fleet.step(0.02)


def test_explicit_historical_and_single_boat_identity_remain_exact():
    world = harbour_world()
    definition = [
        dict(
            id="explicit-f03",
            name="Historical F03 · explicit",
            variant="ricochet-rc01-f03",
            berth_id="airport-landing-ricochet",
        )
    ]
    fleet = HarbourFleet(world, vessels=definition)
    fleet.step()
    state = json.loads(json.dumps(fleet.serialize()))
    restored = HarbourFleet.restore(world, state)
    assert list(restored.crafts) == ["explicit-f03"]
    assert restored.crafts["explicit-f03"].variant == "ricochet-rc01-f03"
    assert restored.selectedId == "explicit-f03"
    with pytest.raises(ValueError, match="Unsupported"):
        HarbourFleet.restore(world, {"schema": "ricochet-1"})


def test_water_mask_two_wakes_reset_restore_and_reconfigure():
    fleet = HarbourFleet(harbour_world())
    water = fleet.water
    assert float(water.evaluate(150.0, 150.0).wet_fraction) == 0
    assert float(water.evaluate(-50.0, 50.0).wet_fraction) > 0
    for boat_id, x in [("ricochet-airport", -50.0), ("ricochet-marina", 50.0)]:
        water.apply_for(
            boat_id,
            x=x,
            y=50.0,
            heading_rad=0.0,
            vx_world=2.0,
            vy_world=0.0,
            heave_rate_mps=0.0,
            draft_m=0.5,
            submerged_vol_m3=0.9,
            hydro_reaction_xy=(10.0, 0.0),
            fan_thrust_n=100.0,
            dt=DT,
        )
    assert len(water.wakes) == 2
    state = json.loads(json.dumps(water.checkpoint_state()))
    before = water.evaluate(np.array([-65.0, 35.0, 150.0]), np.array([50.0, 50.0, 150.0])).eta
    water.reset()
    assert not water.wakes
    water.restore_state(state)
    np.testing.assert_array_equal(
        before, water.evaluate(np.array([-65.0, 35.0, 150.0]), np.array([50.0, 50.0, 150.0])).eta
    )
    water.reconfigure(dict(wind_speed_mps=1.0))
    water.step(DT)
    assert np.all(water.shallow.h[~water.grid_mask] == 0)


def test_nonflat_bathymetry_matches_actual_mujoco_triangle_diagonal():
    from vtx.harbour_water import HarbourWorld
    from vtx.world import TestWorld

    world = harbour_world()
    world.n = 3
    world.heights = np.array([[1.0, 9.0, 3.0], [4.0, 2.0, 13.0], [8.0, 17.0, 5.0]])
    adapter = HarbourWorld(world)
    for x, y in [
        (-170.0, -110.0),
        (-110.0, -170.0),
        (75.0, 135.0),
        (135.0, 75.0),
        (-50.0, 70.0),
        (10.0, -190.0),
    ]:
        assert adapter.terrain_z(x, y) == pytest.approx(TestWorld.terrain_z(world, x, y), abs=1e-12)
