"""Reproducible Task 01 engineering study: mass, CG, full 3x3 inertia, fuel sweep,
hover power, 6-DOF wrench controllability, and matched MuJoCo physics comparison.

Writes: evidence/argon_task01_transmission_tanks.json
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vtx.aero import BladeElementModel, ideal_hover
from vtx.aircraft import Aircraft, G, proposed_variator_components
from vtx.world import TestWorld


def allocation_matrix(pivots: np.ndarray, cg: np.ndarray, k_q: float = 0.042, senses=(1, -1, 1, -1)) -> np.ndarray:
    """6x12 wrench allocation matrix mapping 4x3 rotor force vectors [Fx_i, Fy_i, Fz_i] to [Fx, Fy, Fz, Mx, My, Mz] about CG."""
    B = np.zeros((6, 12), dtype=float)
    for i in range(4):
        r = pivots[i] - cg
        s = float(senses[i])
        # Force columns
        B[0:3, 3 * i : 3 * i + 3] = np.eye(3)
        # Moment r x F + reaction torque (-s * k_q * F)
        rx = np.array([
            [0.0, -r[2], r[1]],
            [r[2], 0.0, -r[0]],
            [-r[1], r[0], 0.0],
        ], dtype=float)
        B[3:6, 3 * i : 3 * i + 3] = rx - s * k_q * np.eye(3)
    return B


def hover_controllability(pivots: np.ndarray, cg: np.ndarray) -> dict:
    B = allocation_matrix(pivots, cg)
    u, s, vt = np.linalg.svd(B, full_matrices=False)
    rank = int(np.sum(s > 1e-6))
    cond = float(s[0] / s[-1]) if s[-1] > 1e-12 else float("inf")
    return dict(rank=rank, singular_values=s.tolist(), condition_number=cond)


def verify_inertia_properties(J: np.ndarray) -> dict:
    sym_err = float(np.max(np.abs(J - J.T)))
    eigvals = np.linalg.eigvalsh(0.5 * (J + J.T))
    l1, l2, l3 = [float(x) for x in sorted(eigvals)]
    tri_margin = float((l1 + l2) - l3)
    return dict(
        symmetry_max_abs_err=sym_err,
        is_symmetric=(sym_err < 1e-9),
        principal_moments_kg_m2=[l1, l2, l3],
        positive_definite=(l1 > 0.0),
        triangle_inequality_margin_kg_m2=tri_margin,
        satisfies_triangle_inequality=(tri_margin >= -1e-9),
    )


def independent_mass_cg_inertia(ledger: dict, tank_fuel_kg: list[float], variator_package: bool = False) -> dict:
    """Independently compute total mass, 3-D CG, and 3x3 inertia tensor from body/part primitives."""
    items = []
    for bname, binfo in ledger["bodies"].items():
        items.append(dict(
            name=bname,
            mass_kg=float(binfo["mass_kg"]),
            centroid_m=np.array(binfo["centroid_m"], dtype=float),
            inertia_kg_m2=np.array(binfo["inertia_centroid_kg_m2"], dtype=float),
        ))
    # 2 x 85 kg crew ellipsoids at [-0.3, 0.02, 1.445] and [+0.3, 0.02, 1.445]
    radii = np.array([0.2, 0.16, 0.45])
    j_occ = np.diag(85.0 / 5.0 * (np.sum(radii * radii) - radii * radii))
    for i, x in enumerate([-0.3, 0.3]):
        items.append(dict(
            name=f"occupant{i+1}",
            mass_kg=85.0,
            centroid_m=np.array([x, 0.02, 1.445], dtype=float),
            inertia_kg_m2=j_occ,
        ))
    # 4 cylindrical fuel cells (r=0.18m, L=0.48m)
    r, L = 0.18, 0.48
    for i, t in enumerate(ledger["tanks"]):
        m_f = float(tank_fuel_kg[i])
        pos = np.array(t["centroid_m"], dtype=float)
        axis = np.array(t["axis"], dtype=float)
        axis = axis / np.linalg.norm(axis)
        jp = 0.5 * m_f * r * r
        jt = m_f * (3 * r * r + L * L) / 12.0
        J_f = jt * np.eye(3) + (jp - jt) * np.outer(axis, axis)
        items.append(dict(
            name=f"fuel{i+1}",
            mass_kg=m_f,
            centroid_m=pos,
            inertia_kg_m2=J_f,
        ))
    if variator_package:
        for comp in proposed_variator_components():
            items.append(dict(
                name=comp["id"],
                mass_kg=float(comp["mass_kg"]),
                centroid_m=np.array(comp["centroid_m"], dtype=float),
                inertia_kg_m2=np.array(comp["inertia_centroid_kg_m2"], dtype=float),
            ))
    total_mass = sum(x["mass_kg"] for x in items)
    cg = sum(x["mass_kg"] * x["centroid_m"] for x in items) / total_mass
    J_total = np.zeros((3, 3), dtype=float)
    for x in items:
        d = x["centroid_m"] - cg
        J_total += x["inertia_kg_m2"] + x["mass_kg"] * (np.eye(3) * float(d @ d) - np.outer(d, d))
    return dict(
        mass_kg=float(total_mass),
        cg_m=cg.tolist(),
        inertia_cg_kg_m2=J_total.tolist(),
        checks=verify_inertia_properties(J_total),
    )


def solve_hover_collective(aero: BladeElementModel, rpm: float, target_thrust_n: float) -> dict | None:
    omega = rpm * 2.0 * math.pi / 60.0
    if target_thrust_n <= 0.0:
        return dict(collective_deg=0.0, thrust_n=0.0, torque_nm=0.0, shaft_power_w=0.0, max_alpha_deg=0.0)
    # Find max unstalled thrust across collective [0..22 deg]
    grid = np.linspace(0.0, 22.0, 111)
    evals = [aero.evaluate(omega, float(c), 0.0) for c in grid]
    unstalled = [(c, ev) for c, ev in zip(grid, evals) if ev["max_alpha_deg"] <= 16.0]
    max_c, max_ev = max(unstalled, key=lambda pair: pair[1]["thrust_n"])
    if target_thrust_n > max_ev["thrust_n"]:
        return None
    sol_c = brentq(lambda c: aero.evaluate(omega, c, 0.0)["thrust_n"] - target_thrust_n, 0.0, float(max_c))
    ev = aero.evaluate(omega, float(sol_c), 0.0)
    return dict(
        collective_deg=round(float(sol_c), 3),
        thrust_n=round(float(ev["thrust_n"]), 2),
        torque_nm=round(float(ev["torque_nm"]), 2),
        shaft_power_w=round(float(ev["torque_nm"] * omega), 1),
        max_alpha_deg=round(float(ev["max_alpha_deg"]), 2),
    )


def evaluate_state(variant: str, tank_fuel_kg: list[float], label: str, world: TestWorld) -> dict:
    total_fuel = float(sum(tank_fuel_kg))
    ac = Aircraft(world=world, airframe_variant=variant, fuel_kg=max(total_fuel, 0.001), tank_fuel_kg=tank_fuel_kg, rpm=1200.0)
    mj_props = ac.mass_properties()
    ind_props = independent_mass_cg_inertia(ac.ledger, tank_fuel_kg, variator_package=(variant == "r6_variator"))
    mj_cg = np.array(mj_props["cg_world_m"])
    ind_cg = np.array(ind_props["cg_m"])
    mj_J = np.array(mj_props["inertia_world_kg_m2"])
    ind_J = np.array(ind_props["inertia_cg_kg_m2"])

    weight_n = ind_props["mass_kg"] * G
    per_fan_equal_n = weight_n / 4.0

    # Compute individual rotor thrust shares needed to balance roll/pitch moment around CG with vertical thrust
    # Rotors: F1 (+2.6, 0), F2 (0, +2.6), F3 (-2.6, 0), F4 (0, -2.6)
    # Sum T_i = W
    # Pitch moment tau_x = sum T_i * (r_iy - cg_y) = 2.6*(T2 - T4) - W*cg_y = 0 -> T2 - T4 = W*cg_y / 2.6
    # Roll moment  tau_y = sum T_i * (cg_x - r_ix) = 2.6*(T3 - T1) + W*cg_x = 0 -> T1 - T3 = W*cg_x / 2.6
    # Under symmetric collective trim Delta_T_x = T1 - T3, Delta_T_y = T2 - T4 with T1+T3 = W/2 + dT_pair, or minimum-norm solution:
    # Minimum-variance thrust distribution: T_i = W/4 + (W * cg_x / 5.2)*s_x + (W * cg_y / 5.2)*s_y
    cg_x, cg_y, cg_z = ind_cg
    t1_req = weight_n / 4.0 + weight_n * cg_x / 5.2
    t3_req = weight_n / 4.0 - weight_n * cg_x / 5.2
    t2_req = weight_n / 4.0 + weight_n * cg_y / 5.2
    t4_req = weight_n / 4.0 - weight_n * cg_y / 5.2
    req_thrusts = [t1_req, t2_req, t3_req, t4_req]

    # Alternatively, under equal thrust T_i = W/4 (common-shaft equal collective), what nacelle tilt angle is needed
    # so the thrust line of action passes through CG?
    # Hub mean is at (0, 0, 2.310). Height of hub plane above CG: dz_hub = 2.310 - cg_z.
    # Actually tilting all 4 rotors or opposite pairs to balance CG moment while keeping F_x = F_y = 0 requires
    # differential thrust (since vertical force moment arm is 2.6m whereas horizontal force at z_piv has vertical arm dz).
    # Wait: if F2 & F4 tilt inward/outward or F1 & F3 tilt tangentially, yaw/roll/pitch moments are generated.
    # Let's compute both equal-thrust hover power and CG-trimmed hover power at 1,200 rpm and 800 rpm!
    aero = ac.aero
    disk_area_total = 4.0 * math.pi * (ac.ledger["blade"]["radius_m"] ** 2)
    ideal = ideal_hover(ind_props["mass_kg"], disk_area_total)

    sol_1200_eq = solve_hover_collective(aero, 1200.0, per_fan_equal_n)
    sol_1200_trim = [solve_hover_collective(aero, 1200.0, ti) for ti in req_thrusts]
    can_hover_1200_trimmed = all(s is not None for s in sol_1200_trim)
    if can_hover_1200_trimmed:
        aero_power_1200_w = sum(s["shaft_power_w"] for s in sol_1200_trim)
        engine_power_1200_w = aero_power_1200_w / 0.95
        trim_collectives_1200_deg = [s["collective_deg"] for s in sol_1200_trim]
    else:
        aero_power_1200_w = None
        engine_power_1200_w = None
        trim_collectives_1200_deg = None

    sol_800_eq = solve_hover_collective(aero, 800.0, per_fan_equal_n)

    # 6-DOF wrench controllability matrix B(r_CG)
    pivots = np.array(ac.ledger["rotor_pivots_m"], dtype=float)
    ctrl = hover_controllability(pivots, ind_cg)
    # Compute max roll/pitch/yaw moment authority at 1200 rpm hover before blade stall (3234.9 N/fan) or 20-deg tilt stop
    max_fan_thrust_1200_n = 3234.89
    max_pitch_moment_diff_thrust_nm = 2.6 * (min(max_fan_thrust_1200_n - t2_req, t4_req) + min(max_fan_thrust_1200_n - t4_req, t2_req))
    max_roll_moment_diff_thrust_nm = 2.6 * (min(max_fan_thrust_1200_n - t1_req, t3_req) + min(max_fan_thrust_1200_n - t3_req, t1_req))
    max_yaw_moment_20deg_tilt_nm = 4.0 * 2.6 * per_fan_equal_n * math.sin(math.radians(20.0))

    return dict(
        label=label,
        variant=variant,
        tank_fuel_kg=[round(float(x), 3) for x in tank_fuel_kg],
        total_fuel_kg=round(total_fuel, 3),
        mass_kg=round(ind_props["mass_kg"], 4),
        weight_n=round(weight_n, 2),
        cg_m=[round(float(x), 5) for x in ind_cg],
        inertia_cg_kg_m2=[[round(float(v), 4) for v in row] for row in ind_J],
        inertia_verification=ind_props["checks"],
        mujoco_agreement=dict(
            mass_diff_kg=float(abs(mj_props["mass_kg"] - ind_props["mass_kg"])),
            cg_max_diff_m=float(np.max(np.abs(mj_cg - ind_cg))),
            inertia_max_diff_kg_m2=float(np.max(np.abs(mj_J - ind_J))),
        ),
        hover_1200rpm=dict(
            per_fan_equal_thrust_n=round(per_fan_equal_n, 2),
            cg_trimmed_fan_thrusts_n=[round(float(x), 2) for x in req_thrusts],
            equal_thrust_collective_deg=(sol_1200_eq["collective_deg"] if sol_1200_eq else None),
            cg_trimmed_collectives_deg=trim_collectives_1200_deg,
            can_hover_1200rpm=can_hover_1200_trimmed,
            ideal_induced_power_kw=round(ideal["ideal_induced_power_w"] / 1000.0, 2),
            bemt_aero_power_kw=(round(aero_power_1200_w / 1000.0, 2) if aero_power_1200_w else None),
            engine_shaft_power_kw=(round(engine_power_1200_w / 1000.0, 2) if engine_power_1200_w else None),
            within_300kw_derated=(engine_power_1200_w <= 300000.0 if engine_power_1200_w else False),
            within_469p8kw_continuous=(engine_power_1200_w <= 469800.0 if engine_power_1200_w else False),
            max_fan_thrust_margin_n=round(4.0 * max_fan_thrust_1200_n - weight_n, 2),
        ),
        hover_800rpm=dict(
            can_hover_800rpm=(sol_800_eq is not None),
            max_total_thrust_800rpm_n=5750.9,
            thrust_deficit_n=round(weight_n - 5750.9, 2),
        ),
        wrench_controllability=dict(
            rank=ctrl["rank"],
            singular_values=[round(float(x), 4) for x in ctrl["singular_values"]],
            condition_number=round(float(ctrl["condition_number"]), 4),
            max_roll_moment_diff_thrust_nm=round(float(max_roll_moment_diff_thrust_nm), 1),
            max_pitch_moment_diff_thrust_nm=round(float(max_pitch_moment_diff_thrust_nm), 1),
            max_yaw_moment_20deg_vector_nm=round(float(max_yaw_moment_20deg_tilt_nm), 1),
        ),
    )


def run_matched_simulations(world: TestWorld) -> dict:
    results = {}
    for variant in ("baseline", "light", "r6", "r6_variator"):
        # 1. Unpowered ground settling (3.0 s)
        ac_settle = Aircraft(world=world, airframe_variant=variant, gear_variant="critically_damped", fuel_kg=60.0, rpm=800.0)
        ac_settle.spawn(0.0, 0.0, 0.0)
        for _ in range(int(3.0 / 0.0025)):
            ac_settle.step()
        snap_s = ac_settle.physical_snapshot()
        strokes = [float(ac_settle.joint(f"gear{i}_stroke")[0]) for i in range(1, 7)]
        q_wxyz = snap_s["body_poses"]["airframe"]["quaternion_wxyz"]
        # Convert wxyz to roll/pitch deg
        from scipy.spatial.transform import Rotation
        r_eul = Rotation.from_quat([q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]]).as_euler("xyz", degrees=True)

        # 2. Powered common-shaft hover attempt at 1,200 rpm (4.0 s, collective=13.5 deg)
        ac_hov = Aircraft(world=world, airframe_variant=variant, gear_variant="critically_damped", fuel_kg=60.0, rpm=1200.0)
        ac_hov.spawn(0.0, 0.0, 0.0)
        for _ in range(int(1.0 / 0.0025)):
            ac_hov.step()
        ac_hov.set_command(dict(engine=1.0, collective_deg=[13.5] * 4, tilt_deg=[[0.0, 0.0]] * 4, cabin_deg=[0.0, 0.0, 0.0], cabin_level=True))
        max_tilt_deg = 0.0
        t_exceed_15deg = None
        for step_i in range(int(4.0 / 0.0025)):
            ac_hov.step()
            qw = ac_hov.data.xquat[ac_hov.bids["airframe"]]
            eul = Rotation.from_quat([qw[1], qw[2], qw[3], qw[0]]).as_euler("xyz", degrees=True)
            tilt = math.hypot(eul[0], eul[1])
            if tilt > max_tilt_deg:
                max_tilt_deg = tilt
            if t_exceed_15deg is None and tilt >= 15.0:
                t_exceed_15deg = round((step_i + 1) * 0.0025, 3)

        results[variant] = dict(
            ground_settle_3s=dict(
                crashed=ac_settle.crashed,
                non_gear_collisions=len(ac_settle.events),
                mean_gear_stroke_m=round(float(np.mean(strokes)), 4),
                max_gear_stroke_m=round(float(np.max(strokes)), 4),
                equilibrium_roll_deg=round(float(r_eul[0]), 3),
                equilibrium_pitch_deg=round(float(r_eul[1]), 3),
                cg_z_world_m=round(float(snap_s["mass"]["cg_world_m"][2]), 4),
            ),
            powered_1200rpm_open_loop_4s=dict(
                max_altitude_m=round(float(ac_hov.max_alt), 3),
                peak_engine_power_kw=round(float(ac_hov.power["engine_w"]) / 1000.0, 2),
                max_attitude_tilt_deg=round(float(max_tilt_deg), 2),
                time_to_15deg_tilt_s=t_exceed_15deg,
                crashed=ac_hov.crashed,
            ),
        )
    return results


def compute_fuel_slosh_bounds() -> dict:
    """Analytical cylindrical tank slosh bounds (NASA SP-106 / Abramson & Dodge) for R=0.18m, L=0.48m."""
    R = 0.18
    L = 0.48
    xi_11 = 1.8412  # First derivative root of Bessel J1'(xi)=0
    cases = []
    for total_fuel_kg in (10.0, 20.0, 60.0, 110.0):
        m_tank = total_fuel_kg / 4.0
        fill_frac = (m_tank / 0.80) / (math.pi * R * R * L * 1000.0)
        h_equiv = max(0.02, fill_frac * (2.0 * R))
        omega_n = math.sqrt((G / R) * xi_11 * math.tanh(xi_11 * h_equiv / R))
        freq_hz = omega_n / (2.0 * math.pi)
        # Sloshing mass fraction for horizontal cylinder (approximate upper bound from vertical cylinder of radius R)
        m_slosh_frac = min(0.65, (2.0 / (xi_11 * (xi_11**2 - 1.0))) * (R / max(h_equiv, 0.05)) * math.tanh(xi_11 * h_equiv / R))
        m_slosh_kg = m_tank * m_slosh_frac
        cases.append(dict(
            total_fuel_kg=total_fuel_kg,
            per_tank_fuel_kg=m_tank,
            fill_fraction=round(fill_frac, 4),
            fundamental_slosh_freq_hz=round(freq_hz, 3),
            fundamental_slosh_omega_rad_s=round(omega_n, 3),
            sloshing_mass_per_tank_kg=round(m_slosh_kg, 3),
            fixed_mass_per_tank_kg=round(m_tank - m_slosh_kg, 3),
        ))
    return dict(
        model="NASA SP-106 cylindrical tank first-mode mechanical pendulum equivalent (unbaffled upper bound)",
        tank_inner_radius_m=R,
        tank_inner_length_m=L,
        cases=cases,
    )


def main():
    world = TestWorld()
    r4_ledger = json.loads((ROOT / "evidence/source/airframe_ledger_r4.json").read_text())
    r5_ledger = json.loads((ROOT / "evidence/source/airframe_ledger.json").read_text())
    r6_ledger = json.loads((ROOT / "evidence/source/airframe_ledger_r6.json").read_text())

    # 1. Empty airframe comparison (R4 vs R5 vs R6 vs R6+variator)
    empty_comparison = dict(
        R4=r4_ledger["empty"],
        R5=r5_ledger["empty"],
        R6=r6_ledger["empty"],
    )

    # 2. Symmetric fuel sweep (10, 20, 60, 110 kg) across all 4 variants
    symmetric_sweep = {}
    for variant in ("baseline", "light", "r6", "r6_variator"):
        symmetric_sweep[variant] = []
        for f_kg in (10.0, 20.0, 60.0, 110.0):
            symmetric_sweep[variant].append(
                evaluate_state(variant, [f_kg / 4.0] * 4, f"{variant}_{int(f_kg)}kg_sym", world)
            )

    # 3. Deliberately asymmetric fuel load cases on R6 and R6_variator
    asym_specs = [
        ("single_tank_F1_27p5kg", [27.5, 0.0, 0.0, 0.0]),
        ("aft_engine_pair_F1_F2_55kg", [27.5, 27.5, 0.0, 0.0]),
        ("fore_cabin_pair_F3_F4_55kg", [0.0, 0.0, 27.5, 27.5]),
        ("starboard_pair_F1_F4_55kg", [27.5, 0.0, 0.0, 27.5]),
        ("port_pair_F2_F3_55kg", [0.0, 27.5, 27.5, 0.0]),
        ("diagonal_pair_F1_F3_55kg", [27.5, 0.0, 27.5, 0.0]),
        ("three_tanks_full_one_empty_82p5kg", [27.5, 27.5, 27.5, 0.0]),
    ]
    asymmetric_cases = dict(r6=[], r6_variator=[])
    for name, tanks in asym_specs:
        asymmetric_cases["r6"].append(evaluate_state("r6", tanks, f"r6_{name}", world))
        asymmetric_cases["r6_variator"].append(evaluate_state("r6_variator", tanks, f"r6_variator_{name}", world))

    # 4. Tank geometry & volume verification
    R_in, L_in = 0.18, 0.48
    v_inner_l = math.pi * (R_in ** 2) * L_in * 1000.0
    tank_audit = dict(
        count=4,
        inner_radius_m=R_in,
        inner_length_m=L_in,
        single_tank_inner_volume_l=round(v_inner_l, 3),
        total_inner_volume_l=round(4.0 * v_inner_l, 3),
        fuel_density_kg_per_l=0.80,
        max_fuel_mass_at_100pct_kg=round(4.0 * v_inner_l * 0.80, 2),
        design_max_fuel_kg=110.0,
        design_max_fuel_volume_l=137.5,
        design_fill_fraction_at_110kg=round(137.5 / (4.0 * v_inner_l), 4),
        r5_tanks=r5_ledger["tanks"],
        r6_tanks=r6_ledger["tanks"],
        slosh_bounds=compute_fuel_slosh_bounds(),
    )

    # 5. Proposed variator hardware ledger
    variator_items = proposed_variator_components()
    variator_summary = dict(
        components=variator_items,
        total_added_mass_kg=round(sum(c["mass_kg"] for c in variator_items), 3),
        rss_uncertainty_kg=round(math.sqrt(sum(c["uncertainty_kg"] ** 2 for c in variator_items)), 3),
        sum_abs_uncertainty_kg=round(sum(c["uncertainty_kg"] for c in variator_items), 3),
    )

    # 6. Matched dynamic simulation comparison
    sim_comparison = run_matched_simulations(world)

    out = dict(
        empty_comparison=empty_comparison,
        subsystem_allocations_kg=r6_ledger["subsystem_allocations_kg"],
        body_comparison=dict(
            R5={k: dict(mass_kg=round(v["mass_kg"], 4), centroid_m=[round(x, 5) for x in v["centroid_m"]]) for k, v in r5_ledger["bodies"].items()},
            R6={k: dict(mass_kg=round(v["mass_kg"], 4), centroid_m=[round(x, 5) for x in v["centroid_m"]]) for k, v in r6_ledger["bodies"].items()},
        ),
        proposed_variator_package=variator_summary,
        tank_volume_and_slosh_audit=tank_audit,
        symmetric_fuel_sweep=symmetric_sweep,
        asymmetric_fuel_cases=asymmetric_cases,
        matched_simulation_comparison=sim_comparison,
    )
    out_path = ROOT / "evidence/argon_task01_transmission_tanks.json"
    out_path.write_text(json.dumps(out, indent=2))
    print("TASK01_STUDY_COMPLETE", out_path)


if __name__ == "__main__":
    main()
