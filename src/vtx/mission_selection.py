"""Stage-1 map mission selection, not a flight controller or collision solver.

A real environment-owned validator must decide validity using support geometry,
VTX footprint/rotor clearances, map rules and observed obstacles. There is no
unqualified fallback validator and no hardcoded set of allowed launch pads.
"""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Protocol


@dataclass(frozen=True)
class MapPoint:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        if not (isfinite(self.x_m) and isfinite(self.y_m)):
            raise ValueError("Map coordinates must be finite metres")


@dataclass(frozen=True)
class SurfaceDecision:
    valid: bool
    reason: str
    terrain_z_m: float | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("Surface decision must explain its outcome")
        if self.valid and (self.terrain_z_m is None or not isfinite(self.terrain_z_m)):
            raise ValueError("Valid surface requires a finite terrain height")


class SurfaceValidator(Protocol):
    def validate(self, point: MapPoint, purpose: str) -> SurfaceDecision:
        """Check real environment geometry and operational requirements."""
        ...


@dataclass(frozen=True)
class MissionSelection:
    environment_id: str
    environment_version: str
    departure: MapPoint
    destination: MapPoint
    departure_surface_z_m: float
    destination_surface_z_m: float


def select_mission(
    environment_id: str,
    environment_version: str,
    departure: MapPoint,
    destination: MapPoint,
    validator: SurfaceValidator,
) -> MissionSelection:
    """Select a route request; does NOT assert route feasibility or flight success."""
    if not environment_id.strip() or not environment_version.strip():
        raise ValueError("Environment identity and version are mandatory")
    if hypot(departure.x_m - destination.x_m, departure.y_m - destination.y_m) == 0:
        raise ValueError("Departure and destination must be distinct points")
    if validator is None:
        raise ValueError("An environment-backed location validator is required")
    dep = validator.validate(departure, "departure")
    if not dep.valid:
        raise ValueError(f"INVALID_DEPARTURE: {dep.reason}")
    arr = validator.validate(destination, "destination")
    if not arr.valid:
        raise ValueError(f"INVALID_DESTINATION: {arr.reason}")
    return MissionSelection(
        environment_id, environment_version, departure, destination,
        dep.terrain_z_m, arr.terrain_z_m,
    )
