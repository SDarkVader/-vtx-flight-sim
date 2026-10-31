"""Tests of selection contract, NOT simulated flight or VTX safety."""
import random
import pytest
from vtx.mission_selection import (
    MapPoint, SurfaceDecision, select_mission,
)


class SyntheticTerrain:
    """Explicit illustrative map, not a VTX-validated landing terrain.

    Each free coordinate is supported. This intentionally checks arbitrary map
    locations; it does not maintain a list of numbered approved launch pads.
    """
    def validate(self, point, purpose):
        if not (0 <= point.x_m <= 100 and 0 <= point.y_m <= 100):
            return SurfaceDecision(False, "outside synthetic terrain bounds")
        if 40 <= point.x_m <= 60 and 40 <= point.y_m <= 60:
            return SurfaceDecision(False, "obstacle and restricted test area")
        return SurfaceDecision(True, "supported by synthetic terrain", 0.0)


def test_arbitrary_map_points_not_fixed_pads():
    rng = random.Random(151)
    terrain = SyntheticTerrain()
    selected = []
    while len(selected) < 5:
        dep = MapPoint(rng.uniform(0, 100), rng.uniform(0, 100))
        arr = MapPoint(rng.uniform(0, 100), rng.uniform(0, 100))
        try:
            mission = select_mission("stage1", "synthetic-v1", dep, arr, terrain)
            selected.append(mission)
        except ValueError:
            continue
    assert len({(m.departure.x_m, m.destination.y_m) for m in selected}) == 5
    assert all(m.departure_surface_z_m == 0 for m in selected)


@pytest.mark.parametrize("bad,reason", [
    (MapPoint(150, 10), "outside synthetic terrain"),
    (MapPoint(50, 50), "obstacle"),
])
def test_invalid_departure_rejected(bad, reason):
    with pytest.raises(ValueError, match="INVALID_DEPARTURE:.*" + reason):
        select_mission("stage1", "v1", bad, MapPoint(10, 10), SyntheticTerrain())


@pytest.mark.parametrize("bad,reason", [
    (MapPoint(-3, 12), "outside synthetic terrain"),
    (MapPoint(42, 55), "obstacle"),
])
def test_invalid_destination_rejected(bad, reason):
    with pytest.raises(ValueError, match="INVALID_DESTINATION:.*" + reason):
        select_mission("stage1", "v1", MapPoint(10, 10), bad, SyntheticTerrain())


def test_identical_points_rejected():
    with pytest.raises(ValueError, match="distinct"):
        select_mission("stage1", "v1", MapPoint(10, 10), MapPoint(10, 10), SyntheticTerrain())


def test_nonfinite_coordinates_rejected():
    with pytest.raises(ValueError, match="finite"):
        MapPoint(float("nan"), 1)
    with pytest.raises(ValueError, match="finite"):
        MapPoint(1, float("inf"))


def test_missing_environment_validation_rejected():
    with pytest.raises(ValueError, match="validator"):
        select_mission("stage1", "v1", MapPoint(10, 10), MapPoint(20, 20), None)


def test_replayable_mission_selection():
    a = select_mission("stage1", "v1", MapPoint(3.14, 17.5), MapPoint(24.1, 7.5), SyntheticTerrain())
    b = select_mission("stage1", "v1", MapPoint(3.14, 17.5), MapPoint(24.1, 7.5), SyntheticTerrain())
    assert a == b


def test_valid_decision_requires_terrain_height():
    with pytest.raises(ValueError, match="terrain height"):
        SurfaceDecision(True, "supported", None)
