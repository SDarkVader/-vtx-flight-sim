"""The supported cockpit must refuse wrong airframe, physics or renderer."""

import pytest
from vtx.release import EXPECTED_RELEASE, actual_release, assert_expected_release


def test_r6_release_identity_matches_loaded_plant():
    from vtx.aircraft import Aircraft
    from vtx.world import TestWorld
    p = Aircraft(TestWorld(), airframe_variant="r6",
                 gear_variant="critical-damping-proposal",
                 rpm=1200, fuel_kg=10, engine_power_limit_kw=300)
    assert assert_expected_release(p.provenance) == EXPECTED_RELEASE


@pytest.mark.parametrize("key,replacement", [
    ("revision", "P0-V4A-assembly-r5"),
    ("airframe_variant", "light"),
    ("physics_revision", "obsolete"),
    ("render_asset", "/assets/airframe-live.glb"),
])
def test_release_guard_rejects_stale_components(key, replacement):
    p = dict(revision=EXPECTED_RELEASE["airframe_revision"],
             airframe_variant=EXPECTED_RELEASE["airframe_variant"],
             physics_revision=EXPECTED_RELEASE["physics_revision"],
             render_asset=EXPECTED_RELEASE["render_asset"])
    p[key] = replacement
    with pytest.raises(RuntimeError, match="refused to start"):
        assert_expected_release(p)


def test_release_guard_returns_actual_model_not_release_label():
    p = dict(revision="P0-V4A-assembly-r5", airframe_variant="light",
             physics_revision="old", render_asset="/assets/airframe-live.glb")
    assert actual_release(p)["airframe_revision"].endswith("-r5")


def test_enforced_runtime_rejects_legacy_mission(monkeypatch, tmp_path):
    import vtx.live_server as server
    from fastapi import HTTPException

    monkeypatch.setenv("VTX_ENFORCE_RELEASE", "1")
    monkeypatch.setenv("VTX_DATA_ROOT", str(tmp_path))
    lab = server.Laboratory()
    with pytest.raises(HTTPException) as exc:
        lab.start(server.Mission(airframe_variant="light"))
    assert exc.value.status_code == 409
    assert lab.aircraft.provenance["revision"] == EXPECTED_RELEASE["airframe_revision"]
