"""Blender headless 3D BVH collision & swept-envelope clearance audit for R5 vs R6 (Task 01).

Usage:
  blender -b assets/source/p0-v4.blend -P tools/check_r6_clearance.py
"""
import json
import math
import re
from pathlib import Path
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]


def get_world_pts_tris(obj, deps, extra_world_xform=None):
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    mw = obj.matrix_world.copy()
    if extra_world_xform is not None:
        mw = extra_world_xform @ mw
    mesh.transform(mw)
    pts = [v.co.copy() for v in mesh.vertices]
    tris = [tuple(p.vertices) for p in mesh.polygons]
    ev.to_mesh_clear()
    return pts, tris


def make_bvh(pts, tris):
    bvh = BVHTree.FromPolygons(pts, tris)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return bvh, (lo, hi), pts, tris


def min_surface_distance_m(bvh1, pts1, bvh2, pts2):
    ov = bvh1.overlap(bvh2)
    if ov:
        return 0.0, len(ov)
    best = 1e9
    step1 = max(1, len(pts1) // 250)
    for p in pts1[::step1]:
        loc, _, _, d = bvh2.find_nearest(p)
        if d is not None and d < best:
            best = d
    step2 = max(1, len(pts2) // 250)
    for p in pts2[::step2]:
        loc, _, _, d = bvh1.find_nearest(p)
        if d is not None and d < best:
            best = d
    return float(best), 0


def make_cylinder_bvh(center, radius, length, n_radial=24):
    cx, cy, cz = center
    z0, z1 = cz - length / 2.0, cz + length / 2.0
    pts = []
    for z in (z0, z1):
        for k in range(n_radial):
            a = 2.0 * math.pi * k / n_radial
            pts.append(Vector((cx + radius * math.cos(a), cy + radius * math.sin(a), z)))
    pts.append(Vector((cx, cy, z0)))
    pts.append(Vector((cx, cy, z1)))
    c_bot, c_top = 2 * n_radial, 2 * n_radial + 1
    tris = []
    for k in range(n_radial):
        kn = (k + 1) % n_radial
        tris.append((k, kn, n_radial + kn, n_radial + k))
        tris.append((c_bot, kn, k))
        tris.append((c_top, n_radial + k, n_radial + kn))
    return make_bvh(pts, tris)


def make_box_bvh(center, dims):
    cx, cy, cz = center
    hx, hy, hz = dims[0] / 2.0, dims[1] / 2.0, dims[2] / 2.0
    pts = [
        Vector((cx - hx, cy - hy, cz - hz)),
        Vector((cx + hx, cy - hy, cz - hz)),
        Vector((cx + hx, cy + hy, cz - hz)),
        Vector((cx - hx, cy + hy, cz - hz)),
        Vector((cx - hx, cy - hy, cz + hz)),
        Vector((cx + hx, cy - hy, cz + hz)),
        Vector((cx + hx, cy + hy, cz + hz)),
        Vector((cx - hx, cy + hy, cz + hz)),
    ]
    tris = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    return make_bvh(pts, tris)


def load_scene_from_ledger(ledger_path):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / "assets/source/p0-v4.blend"))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    ledger = json.loads(ledger_path.read_text())
    repairs_file = ROOT / ("evidence/source/assembly_repairs_r6.json" if "r6" in ledger_path.name else "evidence/source/assembly_repairs.json")
    repairs = json.loads(repairs_file.read_text())
    byname = {o.name: o for o in bpy.data.objects}
    for r in repairs:
        o = byname.get(r["name"])
        if o is not None:
            o.animation_data_clear()
            o.matrix_world = Matrix(r["after_world_matrix"])
    bpy.context.view_layer.update()
    return ledger, byname


def audit_key_pairs(byname, deps, pair_specs):
    results = []
    cache = {}
    for label, name_a, name_b in pair_specs:
        for nm in (name_a, name_b):
            if nm not in cache:
                pts, tris = get_world_pts_tris(byname[nm], deps)
                cache[nm] = make_bvh(pts, tris)
        bvh1, _, pts1, _ = cache[name_a]
        bvh2, _, pts2, _ = cache[name_b]
        dist_m, ov_tris = min_surface_distance_m(bvh1, pts1, bvh2, pts2)
        results.append(dict(
            check=label,
            part_a=name_a,
            id_a=byname[name_a].get("blendstra_id"),
            part_b=name_b,
            id_b=byname[name_b].get("blendstra_id"),
            overlap_triangles=ov_tris,
            min_clearance_mm=round(dist_m * 1000.0, 2),
            clear=(ov_tris == 0),
        ))
    return results


def main():
    key_pairs = [
        ("Central 4-way gearbox vs P05 Outer pitch ring YZ", "P03 | Four way reduction gearbox", "P05 | Outer pitch ring YZ"),
        ("Central 4-way gearbox vs P05 Inner roll ring XZ", "P03 | Four way reduction gearbox", "P05 | Inner roll ring XZ"),
        ("Central 4-way gearbox vs P01 M250 turboshaft", "P03 | Four way reduction gearbox", "P01 | M250 C30P class turboshaft schematic"),
        ("Central 4-way gearbox vs P01 Turbine heat shielding", "P03 | Four way reduction gearbox", "P01 | Turbine heat shielding"),
        ("Input flexible guard vs P05 Outer pitch ring YZ", "V2 P03 | Transmission input flexible guard", "P05 | Outer pitch ring YZ"),
        ("F1 radial drive shaft vs LANDING leg1 pressure body", "P03 | F1 radial drive shaft", "V4 P10 | LANDING leg1 energy-absorber pressure body"),
        ("F1 carbon shaft enclosure vs LANDING leg1 lower impact pivot", "P03 | F1 carbon shaft enclosure", "V4 P06 | LANDING leg1 lower impact pivot"),
        ("F1 carbon shaft enclosure vs LANDING leg1 dual shear route 1", "P03 | F1 carbon shaft enclosure", "V4 P06 | LANDING leg1 dual shear route 1"),
        ("F3 radial drive shaft vs LANDING leg4 pressure body", "P03 | F3 radial drive shaft", "V4 P10 | LANDING leg4 energy-absorber pressure body"),
        ("F3 carbon shaft enclosure vs LANDING leg4 lower impact pivot", "P03 | F3 carbon shaft enclosure", "V4 P06 | LANDING leg4 lower impact pivot"),
        ("F2 radial drive shaft vs P01 M250 turboshaft", "P03 | F2 radial drive shaft", "P01 | M250 C30P class turboshaft schematic"),
        ("F2 carbon shaft enclosure vs P01 M250 turboshaft", "P03 | F2 carbon shaft enclosure", "P01 | M250 C30P class turboshaft schematic"),
        ("F2 radial drive shaft vs P01 Turbine heat shielding", "P03 | F2 radial drive shaft", "P01 | Turbine heat shielding"),
        ("F2 carbon shaft enclosure vs P01 Mount A", "P03 | F2 carbon shaft enclosure", "P01 | Mount A"),
        ("F1 vertical torque shaft vs F1 transverse hub support", "V3 P03 | F1 vertical torque shaft extension", "V4 P06 | F1 transverse hub support"),
        ("F2 vertical torque shaft vs F2 transverse hub support", "V3 P03 | F2 vertical torque shaft extension", "V4 P06 | F2 transverse hub support"),
        ("F3 vertical torque shaft vs F3 transverse hub support", "V3 P03 | F3 vertical torque shaft extension", "V4 P06 | F3 transverse hub support"),
        ("F4 vertical torque shaft vs F4 transverse hub support", "V3 P03 | F4 vertical torque shaft extension", "V4 P06 | F4 transverse hub support"),
        ("F1 nacelle-local gearbox vs F1 blade1 pitch link", "V4 P03 | F1 nacelle-local 7.5:1 reduction gearbox V4 candidate", "V2 P02 | F1 blade1 pitch link"),
        ("F1 protected fuel cell vs Ring shear diagonal outer 1", "P07 | F1 protected fuel cell", "V4 P06 | Ring shear diagonal outer 1"),
        ("F1 protected fuel cell vs Ring shear diagonal outer 2", "P07 | F1 protected fuel cell", "V4 P06 | Ring shear diagonal outer 2"),
        ("F1 protected fuel cell vs Frame vertical web outer 1", "P07 | F1 protected fuel cell", "V4 P06 | Frame vertical web outer 1"),
        ("F1 protected fuel cell vs Frame vertical web outer 2", "P07 | F1 protected fuel cell", "V4 P06 | Frame vertical web outer 2"),
        ("F1 protected fuel cell vs BAY1 saddle1 link inner lower", "P07 | F1 protected fuel cell", "V4 P06 | BAY1 saddle1 triangulated link inner lower"),
        ("F1 protected fuel cell vs BAY1 saddle1 clevis-1", "P07 | F1 protected fuel cell", "V4 P07 | BAY1 saddle1 clevis-1"),
        ("F2 protected fuel cell vs Ring shear diagonal outer 3", "P07 | F2 protected fuel cell", "V4 P06 | Ring shear diagonal outer 3"),
        ("F3 protected fuel cell vs Ring shear diagonal outer 5", "P07 | F3 protected fuel cell", "V4 P06 | Ring shear diagonal outer 5"),
        ("F4 protected fuel cell vs Ring shear diagonal outer 7", "P07 | F4 protected fuel cell", "V4 P06 | Ring shear diagonal outer 7"),
        ("Central fuel-feed manifold vs P03 Four way reduction gearbox", "V2 P07 | Central fuel-feed manifold (schematic)", "P03 | Four way reduction gearbox"),
        ("BAY1 supply pipe seg2 vs P01 M250 turboshaft", "V4 P07 | BAY1 protected supply pipe / segment2", "P01 | M250 C30P class turboshaft schematic"),
        ("BAY2 supply pipe seg2 vs P01 M250 turboshaft", "V4 P07 | BAY2 protected supply pipe / segment2", "P01 | M250 C30P class turboshaft schematic"),
        ("BAY1 supply pipe seg3 vs P11 Thermal radiator", "V4 P07 | BAY1 protected supply pipe / segment3", "P11 | Thermal radiator"),
    ]

    # 1. Audit R5 baseline key pairs
    ledger_r5, byname_r5 = load_scene_from_ledger(ROOT / "evidence/source/airframe_ledger.json")
    deps_r5 = bpy.context.evaluated_depsgraph_get()
    r5_pair_results = audit_key_pairs(byname_r5, deps_r5, key_pairs)

    # 2. Audit R6 proposed assembly key pairs + 360-deg x 20-deg tilt cone + gear stroke + variator envelope
    ledger_r6, byname_r6 = load_scene_from_ledger(ROOT / "evidence/source/airframe_ledger_r6.json")
    deps_r6 = bpy.context.evaluated_depsgraph_get()
    r6_pair_results = audit_key_pairs(byname_r6, deps_r6, key_pairs)

    # 3. Sweep all 4 nacelles/rotors across 360 deg azimuth x 0..20 deg tilt cone (coarse 10 deg + fine 2 deg)
    part_body = {p["name"]: p["body"] for p in ledger_r6["parts"]}
    airframe_bvhs = {}
    for p in ledger_r6["parts"]:
        if p["body"] == "airframe":
            pts, tris = get_world_pts_tris(byname_r6[p["name"]], deps_r6)
            airframe_bvhs[p["name"]] = make_bvh(pts, tris)

    tilt_sweep_results = {}
    for fan_idx in range(1, 5):
        piv = Vector(ledger_r6["nacelle_pivots_m"][fan_idx - 1])
        moving_names = [
            p["name"] for p in ledger_r6["parts"]
            if p["body"] in (f"nacelle{fan_idx}", f"rotor{fan_idx}")
        ]
        base_meshes = {}
        for nm in moving_names:
            pts, tris = get_world_pts_tris(byname_r6[nm], deps_r6)
            base_meshes[nm] = (pts, tris)

        # Relevant nearby stationary parts for this fan
        nearby_airframe = [
            nm for nm, (_, (lo, hi), _, _) in airframe_bvhs.items()
            if (Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0.0)) - Vector((piv.x, piv.y, 0.0))).length < 1.95
        ]

        cone_angles_deg = [0.0, 5.0, 10.0, 15.0, 20.0]
        azimuths_coarse = list(range(0, 360, 10))
        min_clear_mm = 1e9
        min_pose = None
        total_overlaps = 0
        azimuth_summary = []

        for cone_deg in cone_angles_deg:
            az_list = [0] if cone_deg == 0.0 else azimuths_coarse
            for az_deg in az_list:
                az = math.radians(az_deg)
                tx = math.radians(cone_deg) * math.cos(az)
                ty = math.radians(cone_deg) * math.sin(az)
                R = (Euler((tx, 0.0, 0.0), 'XYZ').to_matrix() @ Euler((0.0, ty, 0.0), 'XYZ').to_matrix()).to_4x4()
                M_tilt = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv)

                pose_overlaps = 0
                pose_min_mm = 1e9
                closest_pair = None
                for mname in moving_names:
                    pts0, tris0 = base_meshes[mname]
                    pts_t = [M_tilt @ p for p in pts0]
                    bvh_m, (mlo, mhi), _, _ = make_bvh(pts_t, tris0)
                    for aname in nearby_airframe:
                        bvh_a, (alo, ahi), pts_a, _ = airframe_bvhs[aname]
                        # Check duct & blades & stator & local gearbox & actuators against stationary structure
                        if mlo.x <= ahi.x + 0.15 and mhi.x >= alo.x - 0.15 and mlo.y <= ahi.y + 0.15 and mhi.y >= alo.y - 0.15 and mlo.z <= ahi.z + 0.15 and mhi.z >= alo.z - 0.15:
                            ov = bvh_m.overlap(bvh_a)
                            if ov:
                                pose_overlaps += len(ov)
                                total_overlaps += len(ov)
                                pose_min_mm = 0.0
                                closest_pair = (mname, aname)
                            elif cone_deg in (0.0, 20.0) and ("duct" in mname or "blade" in mname or "support ring" in aname or "trunnion" in aname):
                                d_m, _ = min_surface_distance_m(bvh_m, pts_t, bvh_a, pts_a)
                                d_mm = d_m * 1000.0
                                if d_mm < pose_min_mm:
                                    pose_min_mm = d_mm
                                    closest_pair = (mname, aname)
                if pose_min_mm < min_clear_mm:
                    min_clear_mm = pose_min_mm
                    min_pose = dict(cone_deg=cone_deg, azimuth_deg=az_deg, pair=closest_pair)
                if cone_deg == 20.0:
                    azimuth_summary.append(dict(
                        azimuth_deg=az_deg,
                        tx_deg=round(math.degrees(tx), 2),
                        ty_deg=round(math.degrees(ty), 2),
                        overlap_triangles=pose_overlaps,
                        min_duct_blade_to_ring_clearance_mm=round(pose_min_mm, 2),
                        closest_pair=closest_pair,
                    ))

        # Fine 2-deg sweep around closest azimuth at 20-deg cone
        best_az = min_pose["azimuth_deg"] if min_pose else 0
        fine_summary = []
        for delta_deg in range(-10, 12, 2):
            az_deg = (best_az + delta_deg) % 360
            az = math.radians(az_deg)
            tx = math.radians(20.0) * math.cos(az)
            ty = math.radians(20.0) * math.sin(az)
            R = (Euler((tx, 0.0, 0.0), 'XYZ').to_matrix() @ Euler((0.0, ty, 0.0), 'XYZ').to_matrix()).to_4x4()
            M_tilt = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv)
            ov_fine = 0
            for mname in moving_names:
                pts0, tris0 = base_meshes[mname]
                pts_t = [M_tilt @ p for p in pts0]
                bvh_m, (mlo, mhi), _, _ = make_bvh(pts_t, tris0)
                for aname in nearby_airframe:
                    bvh_a, (alo, ahi), _, _ = airframe_bvhs[aname]
                    if mlo.x <= ahi.x and mhi.x >= alo.x and mlo.y <= ahi.y and mhi.y >= alo.y and mlo.z <= ahi.z and mhi.z >= alo.z:
                        ov = bvh_m.overlap(bvh_a)
                        if ov:
                            ov_fine += len(ov)
            fine_summary.append(dict(azimuth_deg=az_deg, overlap_triangles=ov_fine))

        tilt_sweep_results[f"F{fan_idx}"] = dict(
            pivot_m=list(piv),
            total_overlaps_across_cone=total_overlaps,
            min_clearance_mm=round(min_clear_mm, 2),
            min_clearance_pose=min_pose,
            cone_20deg_azimuth_sweep=azimuth_summary,
            fine_2deg_sweep_around_min=fine_summary,
        )

    # 4. Landing gear 0..0.25m stroke sweep vs radial transmission & fuel system
    gear_stroke_results = {}
    p03_p07_airframe = [nm for nm in airframe_bvhs if ("P03" in nm or "P07" in nm)]
    for leg_idx in range(1, 7):
        gear_parts = [p["name"] for p in ledger_r6["parts"] if p["body"] == f"gear{leg_idx}"]
        stroke_overlaps = 0
        min_dist_mm = 1e9
        closest_info = None
        for stroke_m in [0.00, 0.05, 0.10, 0.15, 0.20, 0.25]:
            M_s = Matrix.Translation(Vector((0.0, 0.0, stroke_m)))
            for gname in gear_parts:
                pts_g, tris_g = get_world_pts_tris(byname_r6[gname], deps_r6, extra_world_xform=M_s)
                bvh_g, _, _, _ = make_bvh(pts_g, tris_g)
                for aname in p03_p07_airframe:
                    bvh_a, _, pts_a, _ = airframe_bvhs[aname]
                    d_m, ov = min_surface_distance_m(bvh_g, pts_g, bvh_a, pts_a)
                    stroke_overlaps += ov
                    if d_m * 1000.0 < min_dist_mm:
                        min_dist_mm = d_m * 1000.0
                        closest_info = dict(stroke_m=stroke_m, gear_part=gname, system_part=aname)
        gear_stroke_results[f"leg{leg_idx}"] = dict(
            stroke_range_m=[0.0, 0.25],
            overlaps_with_transmission_or_fuel=stroke_overlaps,
            min_clearance_to_transmission_or_fuel_mm=round(min_dist_mm, 2),
            closest_approach=closest_info,
        )

    # 5. Proposed Variable-Ratio Drive Package (EMRAX 268 + 20:60 4-Planet Epicyclic + Twin SiC Inverters + DC Bus/Cooling)
    cols = [(1, 2.6, 0.0), (2, 0.0, 2.6), (3, -2.6, 0.0), (4, 0.0, -2.6)]
    variator_checks = []
    for i, px, py in cols:
        for cname, cz, r, h in [
            (f"PROPOSED P03 | F{i} 20:60 4-planet epicyclic variator", 0.480, 0.110, 0.120),
            (f"PROPOSED P03 | F{i} EMRAX 268 motor-generator", 0.5955, 0.134, 0.091),
        ]:
            bvh_c, (clo, chi), pts_c, _ = make_cylinder_bvh([px, py, cz], r, h)
            min_struct_mm = 1e9
            closest_struct = None
            overlaps_non_coaxial = 0
            for aname, (bvh_a, (alo, ahi), pts_a, _) in airframe_bvhs.items():
                # Coaxial vertical spindle and vertical shaft pass through the hollow sun/rotor bore intentionally
                if f"F{i} rising fan spindle" in aname or f"F{i} vertical torque shaft" in aname:
                    continue
                if abs(alo.x - px) > 1.5 and abs(ahi.x - px) > 1.5:
                    continue
                d_m, ov = min_surface_distance_m(bvh_c, pts_c, bvh_a, pts_a)
                overlaps_non_coaxial += ov
                if d_m * 1000.0 < min_struct_mm:
                    min_struct_mm = d_m * 1000.0
                    closest_struct = aname
            variator_checks.append(dict(
                component=cname,
                center_m=[px, py, cz],
                envelope_m=dict(diameter_m=2 * r, length_m=h),
                non_coaxial_overlaps=overlaps_non_coaxial,
                min_structural_clearance_mm=round(min_struct_mm, 2),
                closest_part=closest_struct,
            ))

    bay_boxes = [
        ("PROPOSED P11 | Dual SiC trim inverter F1/F4", [+0.820, -0.380, 0.380], [0.300, 0.220, 0.120]),
        ("PROPOSED P11 | Dual SiC trim inverter F2/F3", [-0.820, +0.380, 0.380], [0.300, 0.220, 0.120]),
        ("PROPOSED P03 | Regenerative DC link & oil/coolant pump A", [-0.820, -0.380, 0.380], [0.260, 0.200, 0.140]),
        ("PROPOSED P03 | Regenerative DC link & oil/coolant pump B", [+0.820, +0.380, 0.380], [0.260, 0.200, 0.140]),
    ]
    for cname, center, dims in bay_boxes:
        bvh_b, _, pts_b, _ = make_box_bvh(center, dims)
        min_struct_mm = 1e9
        closest_struct = None
        overlaps_box = 0
        for aname, (bvh_a, (alo, ahi), pts_a, _) in airframe_bvhs.items():
            if (Vector(center) - Vector(((alo.x + ahi.x) / 2, (alo.y + ahi.y) / 2, (alo.z + ahi.z) / 2))).length > 1.8:
                continue
            d_m, ov = min_surface_distance_m(bvh_b, pts_b, bvh_a, pts_a)
            overlaps_box += ov
            if d_m * 1000.0 < min_struct_mm:
                min_struct_mm = d_m * 1000.0
                closest_struct = aname
        variator_checks.append(dict(
            component=cname,
            center_m=center,
            envelope_m=dict(dimensions_m=dims),
            non_coaxial_overlaps=overlaps_box,
            min_structural_clearance_mm=round(min_struct_mm, 2),
            closest_part=closest_struct,
        ))

    report = dict(
        baseline_revision=ledger_r5["revision"],
        proposed_revision=ledger_r6["revision"],
        r5_key_pair_audit=r5_pair_results,
        r6_key_pair_audit=r6_pair_results,
        r6_tilt_cone_360deg_x_20deg_audit=tilt_sweep_results,
        r6_landing_gear_stroke_audit=gear_stroke_results,
        r6_proposed_variator_envelope_audit=variator_checks,
        summary=dict(
            r5_failing_key_pairs=sum(1 for x in r5_pair_results if not x["clear"]),
            r6_failing_key_pairs=sum(1 for x in r6_pair_results if not x["clear"]),
            r6_tilt_cone_overlaps=sum(v["total_overlaps_across_cone"] for v in tilt_sweep_results.values()),
            r6_gear_stroke_overlaps=sum(v["overlaps_with_transmission_or_fuel"] for v in gear_stroke_results.values()),
            r6_variator_envelope_overlaps=sum(v["non_coaxial_overlaps"] for v in variator_checks),
        ),
    )
    out_path = ROOT / "evidence/r6_clearance_audit.json"
    out_path.write_text(json.dumps(report, indent=2))
    print("CLEARANCE_AUDIT_SUMMARY", json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
