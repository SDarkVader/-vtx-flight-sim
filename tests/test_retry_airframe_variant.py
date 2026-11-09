"""Retry regression: preserve real aircraft configuration and flight evidence.

Starts isolated MuJoCo objects only. Never sends commands to the live simulator.
"""
import json

from vtx.live_server import Laboratory, Mission
import vtx.live_server as server


def test_r6_retry_preserves_variant_and_all_flight_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VTX_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(server, "ROOT", tmp_path)
    lab = Laboratory()
    original = Mission(
        departure=[13.7, -28.4], destination=[-45, 18],
        authority="manual", airframe_variant="r6",
        gear_variant="baseline", reference_rpm=1200.0,
        engine_power_limit_kw=300.0, fuel_kg=20.0,
    )
    first = lab.start(original)
    first_id = first["run_id"]
    lab.stop("End isolated retry configuration check")
    first_summary = (tmp_path / "evidence/flights" / first_id / "summary.json").read_bytes()

    second = lab.retry({"authority": "manual"})
    assert second["run_id"] != first_id
    assert lab.aircraft.airframe_variant == "r6"
    assert lab.aircraft.provenance["revision"] == "P0-V4A-assembly-r6"
    assert lab.aircraft.reference_rpm == 1200.0
    assert lab.aircraft.gear_variant == "baseline"
    assert lab.aircraft.engine_power_limit_w == 300000.0
    assert lab.aircraft.fuel_initial.sum() == 20.0
    assert lab.action_log == []
    assert lab.authority == "manual"
    metadata = json.loads((lab.log_path / "metadata.json").read_text())
    assert metadata["request"]["airframe_variant"] == "r6"
    assert (tmp_path / "evidence/flights" / first_id / "summary.json").read_bytes() == first_summary
    lab.stop("End isolated R6-preserving retry")

    lab.retry({"authority": "manual", "airframe_variant": "light"})
    assert lab.aircraft.airframe_variant == "light"
    assert lab.action_log == []
    lab.stop("End isolated explicit variant-change retry")


def test_legacy_retry_without_variant_defaults_light(tmp_path, monkeypatch):
    monkeypatch.setenv("VTX_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(server, "ROOT", tmp_path)
    lab = Laboratory()
    lab.start(Mission(departure=[13.7, -28.4], destination=[-45, 18]))
    lab.stop("End legacy baseline")
    lab.retry_hint["request"].pop("airframe_variant")
    lab.retry({"authority": "manual"})
    assert lab.aircraft.airframe_variant == "light"
    lab.stop("End legacy compatibility check")
