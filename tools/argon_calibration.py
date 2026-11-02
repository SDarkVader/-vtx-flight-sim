"""Revision-gated, read-only Argon reference for the VTX instrument pilot.

Measured hover rows come from evidence/ARGON_CALIBRATION_REPORT.md.
Interpolated rows are explicitly labelled estimates, never measured results.
No flight commands or automatic stabilisation are generated here.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "pilot" / "argon_calibration_reference.json"


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + label)
    return float(value)


def load_calibration(path=REFERENCE, *, aircraft_revision=None, fuel_kg=None):
    """Load an R6 reference, and mark any bounded interpolation as estimated."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("source") != "evidence/ARGON_CALIBRATION_REPORT.md":
        raise ValueError("Unrecognised calibration source")
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported calibration schema")
    revisions = data.get("compatible_revisions")
    if not isinstance(revisions, list) or not revisions or not all(isinstance(x, str) for x in revisions):
        raise ValueError("Invalid revision coverage")
    if aircraft_revision not in revisions:
        raise ValueError("Aircraft revision not verified against calibration")
    mass = _number(fuel_kg, "fuel mass")
    table = data.get("hover_by_fuel_kg")
    if not isinstance(table, dict) or not table:
        raise ValueError("Empty calibration table")
    rows = sorted((_number(float(key), "table fuel key"), row) for key, row in table.items())
    masses = [x for x, _ in rows]
    if len(set(masses)) != len(masses):
        raise ValueError("Duplicate fuel calibration keys")
    if not masses[0] <= mass <= masses[-1]:
        raise ValueError("Fuel mass is outside measured calibration coverage")
    for _, row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("collective_deg"), list) or len(row["collective_deg"]) != 4:
            raise ValueError("Invalid four-rotor trim")
        for key in ("rpm", "shaft_kw"):
            _number(row.get(key), key)
        for value in row["collective_deg"]:
            _number(value, "collective")
    for reference_mass, row in rows:
        if abs(mass - reference_mass) < 1e-7:
            hover = dict(row)
            basis = "measured_reference"
            bounds = [reference_mass]
            break
    else:
        lower, upper = next(((a, b) for a, b in zip(rows, rows[1:]) if a[0] < mass < b[0]), (None, None))
        if lower is None:
            raise ValueError("No calibration bracket for fuel mass")
        weight = (mass - lower[0]) / (upper[0] - lower[0])
        hover = {
            "rpm": lower[1]["rpm"] + weight * (upper[1]["rpm"] - lower[1]["rpm"]),
            "shaft_kw": lower[1]["shaft_kw"] + weight * (upper[1]["shaft_kw"] - lower[1]["shaft_kw"]),
            "collective_deg": [
                x + weight * (y - x)
                for x, y in zip(lower[1]["collective_deg"], upper[1]["collective_deg"])
            ],
        }
        basis = "bounded_linear_estimate"
        bounds = [lower[0], upper[0]]
    return {
        "source": data["source"],
        "schema_version": 1,
        "aircraft_revision": aircraft_revision,
        "fuel_kg": mass,
        "hover": hover,
        "hover_basis": basis,
        "bracketing_fuel_kg": bounds,
        "rotor_order": data["rotor_order"],
        "control_gains": data["control_gains"],
        "advisory_only": True,
        "limitations": data["limitations"],
    }


def from_instrument_observation(observation, path=REFERENCE):
    """Read the existing instrument packet without hidden simulator state."""
    if not isinstance(observation, dict):
        raise ValueError("Missing instrument observation")
    config = observation.get("configuration")
    if not isinstance(config, dict):
        raise ValueError("Missing instrument configuration")
    if config.get("airframe_variant") != "r6":
        raise ValueError("Calibration only verified for the R6 airframe variant")
    if _number(config.get("reference_rpm"), "reference RPM") != 1200.0:
        raise ValueError("R6 calibration requires 1200 RPM reference")
    if _number(config.get("engine_power_limit_kw"), "engine limit") != 300.0:
        raise ValueError("R6 calibration requires the documented 300 kW engine limit")
    if config.get("gear_variant") != "baseline":
        raise ValueError("Calibration not verified for this landing gear variant")
    tanks = observation.get("fuel_kg")
    if not isinstance(tanks, list) or len(tanks) != 4:
        raise ValueError("Expected four live fuel tank measurements")
    values = [_number(v, "tank fuel") for v in tanks]
    if any(not 0 <= v <= 27.5 for v in values):
        raise ValueError("Invalid live tank mass")
    result = load_calibration(path, aircraft_revision=config.get("airframe_revision"), fuel_kg=sum(values))
    result["fuel_tanks_kg"] = values
    result["airframe_variant"] = config["airframe_variant"]
    return result
