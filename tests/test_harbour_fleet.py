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
    for key, x, y in [
        ("airport-landing", 50.0, 50.0),
        ("lantern-marina", 150.0, 150.0),
    ]:
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
    fleet.action(
        "ricochet-airport", dict(throttle=0.12, rudder_deg=4.0, reverse_bucket=0.3)
    )
    fleet.select("ricochet-marina")
    for _ in range(7):
        fleet.step()
    state = json.loads(json.dumps(fleet.serialize(), allow_nan=False))
    restored = HarbourFleet.restore(world, state)
    assert restored.selectedId == "ricochet-marina"
    assert restored.occupancy == fleet.occupancy and restored.moorings == fleet.moorings
    assert (
        restored.crafts["ricochet-airport"].command
        == fleet.crafts["ricochet-airport"].command
    )
    np.testing.assert_array_equal(
        fleet._integration_state(), restored._integration_state()
    )
    np.testing.assert_array_equal(fleet.water.shallow.h, restored.water.shallow.h)
    assert restored.water.wakes == fleet.water.wakes
    for _ in range(13):
        fleet.step()
        restored.step()
        np.testing.assert_allclose(
            fleet.data.qpos, restored.data.qpos, atol=1e-13, rtol=0
        )
        np.testing.assert_allclose(
            fleet.data.qvel, restored.data.qvel, atol=1e-12, rtol=0
        )
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
    with pytest.raises(ValueError, match="incompatible development dynamics"):
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
    before = water.evaluate(
        np.array([-65.0, 35.0, 150.0]), np.array([50.0, 50.0, 150.0])
    ).eta
    water.reset()
    assert not water.wakes
    water.restore_state(state)
    np.testing.assert_array_equal(
        before,
        water.evaluate(
            np.array([-65.0, 35.0, 150.0]), np.array([50.0, 50.0, 150.0])
        ).eta,
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
        assert adapter.terrain_z(x, y) == pytest.approx(
            TestWorld.terrain_z(world, x, y), abs=1e-12
        )


def test_selected_cadence_is_fleet_only_and_checkpoint_phase_is_validated():
    from vtx.harbour_fleet import CADENCE, HYDRO_STRIDE
    from vtx.ricochet.plant import RicochetCraft, DT as ORIGINAL_DT

    world = harbour_world()
    fleet = HarbourFleet(world)
    assert ORIGINAL_DT == RicochetCraft.DT == 0.0025
    assert fleet.model.opt.timestep == DT == 0.01
    assert all(
        c.DT == c.model.opt.timestep == DT and c.hydro_stride == HYDRO_STRIDE == 5
        for c in fleet.crafts.values()
    )
    original = RicochetCraft(
        fleet.world, variant="ricochet-concept-a", hull_variant="concept_a"
    )
    assert original.model.opt.timestep == original.DT == 0.0025
    for _ in range(17):
        fleet.step()
    state = fleet.serialize()
    assert state["cadence"] == CADENCE and state["step_count"] == 17
    assert fleet.water.shallow.t == pytest.approx(0.1)
    assert fleet.water._swe_accum_s == pytest.approx(0.07)
    before = fleet._integration_state().copy()
    for edit in ("cadence", "counter", "boat_counter", "phase", "grid", "v1"):
        bad = deepcopy(state)
        if edit == "cadence":
            bad["cadence"]["hydro_stride_steps"] = 4
        elif edit == "counter":
            bad["step_count"] += 1
        elif edit == "boat_counter":
            bad["boats"]["ricochet-airport"]["native"]["step_count"] += 1
        elif edit == "phase":
            bad["water"]["native"]["shallow"]["t"] += 0.01
            bad["water"]["native"]["_swe_accum_s"] -= 0.01
        elif edit == "grid":
            bad["water"]["grid"]["origin_xy_m"][0] += 5
        else:
            bad["schema"] = "vtx-airport-harbour-fleet-v1"
        with pytest.raises(ValueError):
            HarbourFleet.restore(world, bad)
        np.testing.assert_array_equal(before, fleet._integration_state())


def test_interrupted_tick_cannot_be_saved_or_silently_continued(monkeypatch):
    fleet = HarbourFleet(harbour_world())

    def interrupted():
        raise RuntimeError("injected interruption during force update")

    monkeypatch.setattr(
        fleet.crafts["ricochet-airport"], "_compute_aero_and_propulsion", interrupted
    )
    with pytest.raises(RuntimeError, match="injected"):
        fleet.step()
    with pytest.raises(ValueError, match="interrupted"):
        fleet.serialize()
    with pytest.raises(ValueError, match="interrupted"):
        fleet.step()


def test_disabled_shallow_water_checkpoint_keeps_scheduled_phase():
    world = harbour_world()
    fleet = HarbourFleet(
        world,
        water_config=dict(
            water_level_m=7.0, wave_mode="still", shallow_water_enabled=False
        ),
    )
    for _ in range(17):
        fleet.step()
    restored = HarbourFleet.restore(world, json.loads(json.dumps(fleet.serialize())))
    for _ in range(14):
        fleet.step()
        restored.step()
        np.testing.assert_array_equal(fleet.data.qpos, restored.data.qpos)
        np.testing.assert_array_equal(fleet.water.shallow.h, restored.water.shallow.h)
    assert restored.water.shallow.t == pytest.approx(0.3)
    assert restored.water._swe_accum_s == pytest.approx(0.01)


def test_airport_crop_keeps_global_lattice_and_offset_sample_impulses_exact():
    from vtx.harbour_water import HarbourWorld, HarbourWater
    from vtx.water.datum import WaterEnvironmentConfig
    from vtx.water.shallow_water import ShallowWaterSolver
    from vtx.world import TestWorld

    source = TestWorld()
    terrain = source.heights.copy()
    world = HarbourWorld(source)
    water = HarbourWater(world, WaterEnvironmentConfig(water_level_m=7.0))
    s = water.shallow
    grid = water.grid_identity
    assert grid["shape"] == [127, 209]
    assert grid["bounds_m"] == [-3040.0, 1120.0, -3020.0, -500.0]
    assert grid["cell_spacing_m"] == [20.0, 20.0]
    assert grid["origin_xy_m"] == [-960.0, -1760.0]
    assert (s.half_x, s.half_y) == (2080.0, 1260.0)
    np.testing.assert_array_equal(source.heights, terrain)
    full = ShallowWaterSolver(world, water.config, nx=source.n, ny=source.n)
    xx, yy = np.meshgrid(full.xs, full.ys)
    mask = world.mask(xx, yy)
    full.bed[~mask] = 27.0
    full.reset(water_level_m=7.0)
    j0, i0 = grid["slice_start"]
    ny, nx = grid["shape"]
    for x, y in [(157.0, -655.0), (853.0, -1223.0)]:
        full.apply_momentum_impulse(x, y, 250.0, -80.0, DT)
        s.apply_momentum_impulse(x, y, 250.0, -80.0, DT)
    np.testing.assert_array_equal(s.hu, full.hu[j0 : j0 + ny, i0 : i0 + nx])
    np.testing.assert_array_equal(s.hv, full.hv[j0 : j0 + ny, i0 : i0 + nx])
    # Compare the gather with the previous full-grid masked interpolation.
    rng = np.random.default_rng(57)
    x = rng.uniform(-3000, 1100, 300)
    y = rng.uniform(-3000, -520, 300)
    fx = np.clip((x + full.half_x) / full.dx, 0, full.nx - 1.000001)
    fy = np.clip((y + full.half_y) / full.dy, 0, full.ny - 1.000001)
    ix = fx.astype(int)
    iy = fy.astype(int)
    tx = fx - ix
    ty = fy - iy
    ids = iy * full.nx + ix
    ids = np.stack((ids, ids + 1, ids + full.nx, ids + full.nx + 1), axis=1)
    weights = (
        np.stack(((1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty), axis=1)
        * mask.ravel()[ids]
    )
    weights /= np.maximum(weights.sum(axis=1)[:, None], 1e-12)
    expected = np.sum((full.bed + full.h).ravel()[ids] * weights, axis=1)
    np.testing.assert_array_equal(s.sample(x, y, eta_only=True)[0], expected)
    snapshot = water.elevation_grid(nx=7, ny=5)
    assert (
        snapshot["origin_xy_m"] == grid["origin_xy_m"]
        and snapshot["bounds_m"] == grid["bounds_m"]
    )


@pytest.mark.parametrize("wave_mode", ["still", "regular", "irregular"])
def test_shared_query_cache_is_exact_for_overlapping_wakes_shores_and_new_steps(
    wave_mode,
):
    from vtx.harbour_water import HarbourWorld, HarbourWater
    from vtx.water.shallow_water import HybridWaterField
    from vtx.water.datum import WaterEnvironmentConfig

    class UncachedWater(HarbourWater):
        def _base_components(self, x, y, z, t, eta_only):
            return HybridWaterField._base_components(self, x, y, z, t, eta_only)

        @staticmethod
        def _zero_wake_contribution(wake, x, y):
            return False

    world = harbour_world()
    world.harbour["layout"]["islands"] = [
        dict(ring=[[90.0, 90.0], [110.0, 90.0], [110.0, 110.0], [90.0, 110.0]])
    ]
    world = HarbourWorld(world)
    config = WaterEnvironmentConfig(
        water_level_m=7.0, wave_mode=wave_mode, wave_height_m=0.25, wind_speed_mps=1.0
    )
    cached = HarbourWater(world, config)
    reference = UncachedWater(world, config)
    x = np.array([-100.01, -99.99, -35.0, 0.0, 30.0, 99.99, 100.01, 115.0])
    y = np.array([0.0, -45.0, 20.0, 0.0, -10.0, 35.0, 0.0, 0.0])
    for separation in (30.0, 500.0):
        wakes = {}
        for key, wx in [("a", -20.0), ("b", separation)]:
            wake = cached._default_wake_state()
            wake.update(
                active=True,
                x=wx,
                y=0.0,
                speed_mps=2.0,
                vx_mps=2.0,
                vy_mps=0.0,
                heave_rate_mps=0.2,
                draft_m=0.5,
            )
            wakes[key] = wake
        cached.wakes = deepcopy(wakes)
        reference.wakes = deepcopy(wakes)
        for _ in range(2):
            for eta_only in (False, True):
                actual = cached.evaluate(x, y, z=5.0, eta_only=eta_only)
                expected = reference.evaluate(x, y, z=5.0, eta_only=eta_only)
                for field in (
                    "eta",
                    "depth",
                    "normal",
                    "velocity",
                    "acceleration",
                    "dynamic_pressure",
                    "wet_fraction",
                ):
                    assert (
                        getattr(actual, field).tobytes()
                        == getattr(expected, field).tobytes()
                    ), field
                assert cached._query_base_cache is None
            cached.step(DT)
            reference.step(DT)


def test_water_query_cache_clears_after_interruption(monkeypatch):
    from vtx.harbour_water import HarbourWorld, HarbourWater
    from vtx.water.datum import WaterEnvironmentConfig

    water = HarbourWater(
        HarbourWorld(harbour_world()), WaterEnvironmentConfig(water_level_m=7.0)
    )
    original = water.open_water.evaluate

    def interrupted(*args, **kwargs):
        raise RuntimeError("injected query interruption")

    monkeypatch.setattr(water.open_water, "evaluate", interrupted)
    with pytest.raises(RuntimeError, match="query interruption"):
        water.evaluate(-50.0, 50.0)
    assert water._query_base_cache is None
    monkeypatch.setattr(water.open_water, "evaluate", original)
    assert float(water.evaluate(-50.0, 50.0).wet_fraction) > 0


def test_calm_turn_has_bounded_roll_after_docking_release_and_native_restore():
    from vtx.world import TestWorld
    from vtx.harbour_fleet import CADENCE

    fleet = HarbourFleet(TestWorld())
    assert CADENCE["hydro_force_reconstruction"] == "causal-linear-midpoint-ab2-v1"
    ids = list(fleet.crafts)
    peak_roll = 0.0
    peak_wrench = 0.0

    def advance(count):
        nonlocal peak_roll, peak_wrench
        for _ in range(count):
            fleet.step()
            assert fleet.data.ncon == 0
            for boat in ids:
                r = fleet.data.xmat[fleet.mappings[boat]["bid"]].reshape(3, 3)
                peak_roll = max(
                    peak_roll, abs(float(np.degrees(np.arctan2(r[2, 1], r[2, 2]))))
                )
            peak_wrench = max(
                peak_wrench, float(np.max(np.abs(fleet.data.xfrc_applied)))
            )

    advance(50)
    assert not fleet.dock(ids[1], "airport-landing-ricochet")["ok"]
    assert fleet.release(ids[0])["ok"]
    assert fleet.dock(ids[0], "airport-landing-ricochet")["ok"]
    advance(25)
    for boat in ids:
        assert fleet.release(boat)["ok"]
        fleet.action(boat, dict(throttle=0.3, reverse_bucket=1.0, rudder_deg=0.0))
    advance(1000)
    for boat, sign in zip(ids, (1.0, -1.0)):
        fleet.action(boat, dict(rudder_deg=sign * 8.0))
    advance(500)
    for boat, sign in zip(ids, (-1.0, 1.0)):
        fleet.action(boat, dict(throttle=0.25, rudder_deg=sign * 5.0))
    advance(503)
    restored = HarbourFleet.restore(
        TestWorld(), json.loads(json.dumps(fleet.serialize()))
    )
    for _ in range(12):
        fleet.step()
        restored.step()
        np.testing.assert_array_equal(fleet.data.qpos, restored.data.qpos)
        np.testing.assert_array_equal(fleet.data.qvel, restored.data.qvel)
        np.testing.assert_array_equal(fleet.water.shallow.h, restored.water.shallow.h)
    assert peak_roll < 0.1  # The delayed force interpolation grew past5deg here.
    assert peak_wrench < 3e4
    assert not any(c.crashed for c in fleet.crafts.values())


def test_optional_lantern_clock_restores_order_and_leaves_base_fleets_unchanged():
    from vtx.harbour_trial import LanternTrialFleet, fleet_type

    world = harbour_world()
    assert fleet_type(world) is HarbourFleet
    course = {
        'id': 'test-water-event', 'name': 'Test Water Event',
        'gates': [
            {'center': [x, -18., 7.], 'normal': [1., 0.],
             'width_m': 16., 'marks': [f'gate-{i}-a', f'gate-{i}-b']}
            for i, x in enumerate((0., 30., 60.))
        ],
    }
    world.harbour['timeTrial'] = course
    for gate in course['gates']:
        x, y, _ = gate['center']
        for side, key in zip((-10., 10.), gate['marks']):
            world.obstacles.append(
                dict(id=key, kind='cylinder', center=[x, y+side, 7.],
                     half=[.6, .6, 4.], role='race-mark', landable=False)
            )
    fleet = fleet_type(world)(world)
    assert isinstance(fleet, LanternTrialFleet)
    boat_id = 'ricochet-marina'
    fleet.release(boat_id)
    for _ in range(32):
        fleet.step()
    clock = fleet.race_clocks[boat_id]
    for t, x in ((.05, 3.), (.10, -3.), (.15, 3.), (.20, 60.), (.25, 23.), (.30, 34.)):
        clock.sample(t, (x, -18., 7.))
    run = clock.runs[course['name']]
    assert run['laps'] == 0 and run['next'] == 2

    restored = LanternTrialFleet.restore(world, json.loads(json.dumps(fleet.serialize())))
    assert restored.public()['lantern_trial'] == fleet.public()['lantern_trial']
    persisted = restored.race_clocks[boat_id]
    for t, x in ((.35, 57.), (.40, 64.), (.45, -5.), (.50, 4.)):
        persisted.sample(t, (x, -18., 7.))
    run = persisted.runs[course['name']]
    assert run['laps'] == 1 and run['last'] == run['best']
    restored.reset_trial(boat_id, 'Course marker contact')
    assert run['start'] is None and run['next'] == 0 and run['laps'] == 1
    assert restored.public()['lantern_trial']['runs'][boat_id]['foul'] == 'Course marker contact'
