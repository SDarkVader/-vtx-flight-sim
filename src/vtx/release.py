"""Canonical VTX live-cockpit release identity (not a pilot policy)."""

EXPECTED_RELEASE = {
    "airframe_revision": "P0-V4A-assembly-r6",
    "airframe_variant": "r6",
    "physics_revision": "audit-fixes-20261103-r3",
    "render_asset": "/assets/airframe-r6-blendstra-rig.glb",
}


def actual_release(provenance):
    """Read the loaded MuJoCo model identity and visual asset, not a UI label."""
    return {
        "airframe_revision": provenance.get("revision"),
        "airframe_variant": provenance.get("airframe_variant"),
        "physics_revision": provenance.get("physics_revision"),
        "render_asset": provenance.get("render_asset"),
    }


def assert_expected_release(provenance):
    actual = actual_release(provenance)
    mismatch = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in EXPECTED_RELEASE.items() if actual[key] != expected
    }
    if mismatch:
        raise RuntimeError(
            "VTX refused to start the wrong aircraft/physics/visual release: " + repr(mismatch)
        )
    return actual
