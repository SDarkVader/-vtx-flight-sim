"""Argon R6 advisory-reference regression tests; no simulator controls are issued."""
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from argon_calibration import load_calibration, from_instrument_observation
from persistent_pilot import Pilot


def instrument(fuel=(2.5, 2.5, 2.5, 2.5), **config):
    metadata = dict(airframe_revision="P0-V4A-assembly-r6",
                    airframe_variant="r6", reference_rpm=1200.0,
                    engine_power_limit_kw=300.0, gear_variant="baseline",
                    initial_fuel_kg=10.0)
    metadata.update(config)
    return {"configuration": metadata, "fuel_kg": list(fuel)}


def test_measured_r6_10kg_reference():
    value = from_instrument_observation(instrument())
    assert value["hover"]["collective_deg"] == [16.95, 17.66, 16.95, 16.24]
    assert value["hover"]["shaft_kw"] == 202.5
    assert value["fuel_kg"] == 10.0
    assert value["hover_basis"] == "measured_reference"
    assert value["advisory_only"] is True


def test_live_fuel_burn_uses_bounded_estimate_not_fabricated_measurement():
    value = from_instrument_observation(instrument((2.375,)*4))
    assert value["fuel_kg"] == 9.5
    assert value["hover_basis"] == "bounded_linear_estimate"
    assert value["bracketing_fuel_kg"] == [0.0, 10.0]
    assert value["hover"]["shaft_kw"] == pytest.approx(202.395)
    assert value["hover"]["collective_deg"][1] == pytest.approx(17.6565)


@pytest.mark.parametrize("revision,fuel", [
    ("P0-V4A-assembly-r5", 10), ("unknown", 10), (None, 10),
    ("P0-V4A-assembly-r6", -1), ("P0-V4A-assembly-r6", 111),
    ("P0-V4A-assembly-r6", None)])
def test_rejects_unverified_revision_or_fuel(revision, fuel):
    with pytest.raises(ValueError):
        load_calibration(aircraft_revision=revision, fuel_kg=fuel)


@pytest.mark.parametrize("change", [
    {"airframe_variant": "r6_variator"},
    {"airframe_variant": "light"},
    {"reference_rpm": 800},
    {"engine_power_limit_kw": 469.8},
    {"gear_variant": "critical-damping-proposal"},
    {"airframe_revision": "P0-V4A-assembly-r5"}])
def test_rejects_unvalidated_aircraft_config(change):
    with pytest.raises(ValueError):
        from_instrument_observation(instrument(**change))


@pytest.mark.parametrize("fuel", [[1, 2], [2.5, 2.5, 2.5, -1], [2.5, 2.5, 2.5, "2.5"]])
def test_rejects_invalid_tanks(fuel):
    with pytest.raises(ValueError):
        from_instrument_observation(instrument(fuel))


def test_reference_persists_across_pilot_instances():
    obs = instrument()
    first, second = Pilot(), Pilot()
    first.refresh_calibration(obs)
    second.refresh_calibration(obs)
    assert first.calibration == second.calibration
    assert first.calibration_error is None
    assert second.calibration_error is None


def test_pilot_fail_closed_on_mismatch():
    pilot = Pilot()
    pilot.refresh_calibration(instrument())
    assert pilot.calibration is not None
    pilot.refresh_calibration(instrument(airframe_variant="light"))
    assert pilot.calibration is None
    assert "only verified" in pilot.calibration_error


def test_invalid_reference_source_rejected(tmp_path):
    source = json.loads((ROOT / "pilot" / "argon_calibration_reference.json").read_text())
    source["source"] = "unverified"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError):
        load_calibration(path, aircraft_revision="P0-V4A-assembly-r6", fuel_kg=10)
