"""Regression and verification tests for Argon Task 01:
Transmission positioning, fuel-tank arrangement, mass/CG/3x3 inertia,
360-deg x 20-deg tilt cone clearance, and hover power / wrench controllability.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import pytest
from vtx.aircraft import Aircraft, G, proposed_variator_components

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_r4_and_r5_preserved():
    ac_r4 = Aircraft(airframe_variant="baseline", fuel_kg=60.0)
    ac_r5 = Aircraft(airframe_variant="light", fuel_kg=60.0)
    assert ac_r4.ledger["revision"] == "P0-V4A-assembly-r4"
    assert ac_r5.ledger["revision"] == "P0-V4A-assembly-r5"
    assert len(ac_r4.ledger["parts"]) == 763
    assert len(ac_r5.ledger["parts"]) == 731
    assert math.isclose(ac_r4.ledger["empty"]["mass_kg"], 849.389097757846, rel_tol=1e-9)
    assert math.isclose(ac_r5.ledger["empty"]["mass_kg"], 816.6689476043954, rel_tol=1e-9)
    # Common-shaft equality constraints remain intact in Task 01
    assert ac_r5.model.neq == 7


def test_r6_derivative_assets_and_provenance():
    ledger_path = ROOT / "evidence/source/airframe_ledger_r6.json"
    repairs_path = ROOT / "evidence/source/assembly_repairs_r6.json"
    glb_path = ROOT / "public/assets/airframe-r6.glb"
    blend_path = ROOT / "assets/derived/p0-v4-r6.blend"
    assert ledger_path.exists()
    assert repairs_path.exists()
    assert glb_path.exists() and glb_path.stat().st_size > 1_000_000
    assert blend_path.exists() and blend_path.stat().st_size > 1_000_000

    ledger = json.loads(ledger_path.read_text())
    repairs = json.loads(repairs_path.read_text())
    assert ledger["revision"] == "P0-V4A-assembly-r6"
    assert ledger["source_sha256"] == "2db9abd64ba9b7078e6e539ba4c6b9177e58e335a085a8ea213b5ffa6e987e35"
    assert len(ledger["parts"]) == 731
    assert math.isclose(ledger["empty"]["mass_kg"], 816.6689476043954, rel_tol=1e-9)
    assert len(repairs) > 100
    for r in repairs:
        assert r.get("id"), f"Missing blendstra_id on {r.get('name')}"
        assert len(r["before_world_matrix"]) == 4
        assert len(r["after_world_matrix"]) == 4

    # Verify lowered gimbal bearing stack at z=1.980m (0.33m below rotor hub z=2.310m)
    assert math.isclose(ledger["mechanism"]["bearing_below_rotor_m"], 0.33, abs_tol=1e-9)
    for piv in ledger["nacelle_pivots_m"]:
        assert math.isclose(piv[2], 1.980, abs_tol=1e-6)
        assert math.isclose(math.hypot(piv[0], piv[1]), 2.600, abs_tol=1e-6)

    # Verify 4 fuel tanks centered at R=1.474m, Z=0.945m inside octagonal bays
    assert len(ledger["tanks"]) == 4
    for t in ledger["tanks"]:
        cx, cy, cz = t["centroid_m"]
        assert math.isclose(math.hypot(cx, cy), 1.474, abs_tol=1e-3)
        assert math.isclose(cz, 0.945, abs_tol=1e-3)


def test_r6_and_r6_variator_fuel_sweep_and_inertia_tensors():
    study_path = ROOT / "evidence/argon_task01_transmission_tanks.json"
    assert study_path.exists()
    study = json.loads(study_path.read_text())

    # Check variator package mass delta (+149.0 kg point-symmetric)
    comps = proposed_variator_components()
    assert len(comps) == 12
    assert math.isclose(sum(c["mass_kg"] for c in comps), 149.0, abs_tol=1e-9)

    for variant in ("r6", "r6_variator"):
        for fuel_kg in (10.0, 20.0, 60.0, 110.0):
            ac = Aircraft(airframe_variant=variant, fuel_kg=fuel_kg, rpm=1200.0)
            mp = ac.mass_properties()
            expected_empty = 816.6689476043954 + (149.0 if variant == "r6_variator" else 0.0)
            assert math.isclose(mp["mass_kg"], expected_empty + 170.0 + fuel_kg, abs_tol=1e-5)
            J = np.array(mp["inertia_world_kg_m2"])
            # Full 3x3 inertia matrix must be symmetric, positive definite, and obey triangle inequality
            assert np.max(np.abs(J - J.T)) < 1e-9
            eigvals = sorted(np.linalg.eigvalsh(J))
            assert eigvals[0] > 0.0
            assert eigvals[0] + eigvals[1] > eigvals[2]

    # Verify asymmetric fuel loads shift CG or products of inertia accurately
    ac_sym = Aircraft(airframe_variant="r6", tank_fuel_kg=[13.75, 13.75, 13.75, 13.75])
    ac_single = Aircraft(airframe_variant="r6", tank_fuel_kg=[27.5, 0.0, 0.0, 0.0])
    ac_diag = Aircraft(airframe_variant="r6", tank_fuel_kg=[27.5, 0.0, 27.5, 0.0])

    cg_sym = np.array(ac_sym.mass_properties()["cg_world_m"])
    cg_single = np.array(ac_single.mass_properties()["cg_world_m"])
    cg_diag = np.array(ac_diag.mass_properties()["cg_world_m"])

    # Single tank in F1 (+X, +Y) shifts CG toward +X and +Y
    assert cg_single[0] - cg_sym[0] > 0.025
    assert cg_single[1] - cg_sym[1] > 0.025
    # Diagonal tanks F1+F3 (+X,+Y and -X,-Y) preserve horizontal CG while shifting I_xy
    assert np.max(np.abs(cg_diag[:2] - cg_sym[:2])) < 1e-4
    J_sym = np.array(ac_sym.mass_properties()["inertia_world_kg_m2"])
    J_diag = np.array(ac_diag.mass_properties()["inertia_world_kg_m2"])
    assert abs(J_diag[0, 1] - J_sym[0, 1]) > 25.0

    # Verify every state in study JSON matches MuJoCo to < 1e-6
    for variant, states in study["symmetric_fuel_sweep"].items():
        for st in states:
            assert st["inertia_verification"]["is_symmetric"]
            assert st["inertia_verification"]["positive_definite"]
            assert st["inertia_verification"]["satisfies_triangle_inequality"]
            assert st["mujoco_agreement"]["mass_diff_kg"] < 1e-6
            assert st["mujoco_agreement"]["cg_max_diff_m"] < 1e-6
            assert st["mujoco_agreement"]["inertia_max_diff_kg_m2"] < 1e-5
            assert st["wrench_controllability"]["rank"] == 6


def test_r6_clearance_audit_zero_overlaps():
    audit_path = ROOT / "evidence/r6_clearance_audit.json"
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text())
    summary = audit["summary"]
    assert summary["r5_failing_key_pairs"] == 21
    assert summary["r6_failing_key_pairs"] == 0
    assert summary["r6_tilt_cone_overlaps"] == 0
    assert summary["r6_gear_stroke_overlaps"] == 0
    assert summary["r6_variator_envelope_overlaps"] == 0

    for fan in ("F1", "F2", "F3", "F4"):
        fan_audit = audit["r6_tilt_cone_360deg_x_20deg_audit"][fan]
        assert fan_audit["total_overlaps_across_cone"] == 0
        assert fan_audit["min_clearance_mm"] >= 14.0
        assert len(fan_audit["cone_20deg_azimuth_sweep"]) == 36


def test_r6_ground_settling_and_1200rpm_hover_power():
    study = json.loads((ROOT / "evidence/argon_task01_transmission_tanks.json").read_text())
    for variant in ("r6", "r6_variator"):
        for st in study["symmetric_fuel_sweep"][variant]:
            assert st["hover_1200rpm"]["can_hover_1200rpm"] is True
            assert st["hover_1200rpm"]["within_469p8kw_continuous"] is True
            assert st["hover_1200rpm"]["max_fan_thrust_margin_n"] > 500.0
            # At 800 rpm (7.52:1 overall ratio), blade stall prevents hover
            assert st["hover_800rpm"]["can_hover_800rpm"] is False
            assert st["hover_800rpm"]["thrust_deficit_n"] > 3500.0

        sim = study["matched_simulation_comparison"][variant]["ground_settle_3s"]
        assert sim["crashed"] is False
        assert sim["non_gear_collisions"] == 0
        assert 0.04 < sim["mean_gear_stroke_m"] < 0.12
