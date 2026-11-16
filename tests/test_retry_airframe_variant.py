"""Retry regression: preserve real aircraft configuration and flight evidence.

Starts isolated MuJoCo objects only. Never sends commands to the live simulator.
"""
import json
import asyncio
import pytest
from fastapi import HTTPException

from vtx.live_server import Laboratory, Mission
import vtx.live_server as server


def test_mission_api_requires_an_explicit_aircraft(tmp_path, monkeypatch):
    lab = Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, 'lab', lab)
    with pytest.raises(HTTPException, match='Select an aircraft explicitly'):
        asyncio.run(server.mission(Mission()))
    assert not lab.active and lab.run_id is None


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


def test_retry_without_variant_requires_explicit_choice(tmp_path, monkeypatch):
    monkeypatch.setenv("VTX_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(server, "ROOT", tmp_path)
    lab = Laboratory()
    lab.start(Mission(departure=[13.7, -28.4], destination=[-45, 18]))
    lab.stop("End legacy baseline")
    lab.retry_hint["request"].pop("airframe_variant")
    with pytest.raises(HTTPException, match="aircraft variant"):
        lab.retry({"authority": "manual"})
    assert not lab.active
    lab.retry({"authority": "manual", "airframe_variant": "r6"})
    assert lab.aircraft.airframe_variant == "r6"
    lab.stop("End explicit legacy choice")


def test_retry_does_not_guess_environment_or_end_an_active_flight(tmp_path):
    lab = Laboratory(data_root=tmp_path)
    lab.start(Mission(airframe_variant='r6', environment='sandbox'))
    checkpoint = lab.checkpoint_path.read_bytes()
    run_id = lab.run_id
    with pytest.raises(HTTPException, match='End and retain'):
        lab.retry({})
    assert lab.active and lab.run_id == run_id
    assert lab.checkpoint_path.read_bytes() == checkpoint
    lab.stop('End isolated retry safety check')
    lab.retry_hint['request']['environment'] = None
    lab.retry_hint['mission'].pop('environment_key', None)
    lab.retry_hint['mission'].pop('environment', None)
    with pytest.raises(HTTPException, match='no environment'):
        lab.retry({})
    assert not lab.active and lab.run_id == run_id
    lab.retry({'environment': 'sandbox'})
    assert lab.world.environment_key == 'sandbox'
    lab.stop('End explicit environment choice')


def test_retry_requires_recorded_physics_and_keeps_landing_intent(tmp_path):
    lab=Laboratory(data_root=tmp_path)
    lab.start(Mission(airframe_variant='r6', landing_requested=True))
    lab.stop('End recorded setup')
    lab.retry_hint['request'].pop('reference_rpm')
    with pytest.raises(HTTPException,match='reference_rpm'):
        lab.retry({})
    assert not lab.active
    lab.retry({'reference_rpm':1200.})
    assert lab.mission['landing_requested'] is True
    assert lab.aircraft.reference_rpm == 1200.
    lab.stop('End explicit retry')
