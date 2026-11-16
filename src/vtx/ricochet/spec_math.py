"""Engineering specifications, hydrostatics, aero-drag, and dynamic rigidity math for VTX Ricochet RC-01.

Implements analytical & semi-empirical compliance models grounded in:
- RC-01 Concept A design sheets (900 kg design mass, 750-1050 kg study range,
  9.60 m wingspan, 6.80 m length, 1.60 m hull beam, 7.60 m float stance,
  0.56 m design waterline draft, V_wt >= 1.80 m^3, twin Ø0.90 m ducted fans)
- RC-01 F01/F02 structural materials (CFRP T700/Epoxy, Corecell M80, Ti-6Al-4V, Lexan MR10)
- Scientific literature references:
  - Amphibious hull wave-load reduction & hydrofoil/chine hydrodynamics: https://arxiv.org/abs/2311.06516v1
  - Seaplane water impact & spray wave dynamics: https://arxiv.org/abs/2306.12149v1
  - Boat/hull hydrostatic-to-planing lift transition: https://arxiv.org/abs/1808.03313v2
  - Flexible wing bending-torsion & boundary damping stability: https://arxiv.org/abs/1703.10182v3
  - Discrete-module hydroelastic floating structural dynamics: https://arxiv.org/abs/2203.13744v1
  - Streamlined body & laminar forebody drag reduction: https://arxiv.org/abs/2603.23843v2, https://arxiv.org/abs/2603.02779v1
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np

from vtx.water.datum import G_SI, RHO_AIR_ISA, RHO_FRESHWATER_15C


# ---------------------------------------------------------------------------
# RC-01 Canonical Design Envelope & Dimensions
# ---------------------------------------------------------------------------
RC01_OVERALL_LENGTH_M = 6.80
RC01_WINGSPAN_M = 9.60
RC01_WING_AREA_M2 = 15.50
RC01_HULL_BEAM_M = 1.60
RC01_FLOAT_STANCE_M = 7.60
RC01_OVERALL_HEIGHT_M = 2.35
RC01_TAIL_PYLON_HEIGHT_M = 1.60
RC01_COCKPIT_LENGTH_M = 3.30
RC01_DUCT_DIAMETER_M = 0.90
RC01_DESIGN_MASS_KG = 900.0
RC01_MIN_STUDY_MASS_KG = 750.0
RC01_MAX_STUDY_MASS_KG = 1050.0
RC01_DESIGN_DRAFT_M = 0.56
RC01_DESIGN_DISPLACEMENT_M3 = RC01_DESIGN_MASS_KG / RHO_FRESHWATER_15C
RC01_MIN_WATERTIGHT_VOLUME_M3 = 1.80
RC01_HULL_GM_T_MIN_M = 0.35


# ---------------------------------------------------------------------------
# Material Properties (RC-01 F01/F02 Composite & Metallic Bill of Materials)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StructuralMaterial:
    name: str
    youngs_modulus_pa: float
    shear_modulus_pa: float
    yield_or_allowable_stress_pa: float
    density_kg_m3: float
    allowable_strain: float
    damping_ratio: float


MAT_CFRP_SPAR = StructuralMaterial(
    name='CFRP T700/Epoxy Structural Box',
    youngs_modulus_pa=70.0e9,
    shear_modulus_pa=5.0e9,
    yield_or_allowable_stress_pa=520.0e6,
    density_kg_m3=1560.0,
    allowable_strain=0.0045,
    damping_ratio=0.035,
)

MAT_CFRP_HIGH_MOD = StructuralMaterial(
    name='CFRP HM Tail Pylon Laminate',
    youngs_modulus_pa=85.0e9,
    shear_modulus_pa=5.2e9,
    yield_or_allowable_stress_pa=560.0e6,
    density_kg_m3=1600.0,
    allowable_strain=0.0040,
    damping_ratio=0.030,
)

MAT_HULL_SANDWICH = StructuralMaterial(
    name='CFRP/Corecell-M80 Monocoque Sandwich',
    youngs_modulus_pa=58.0e9,
    shear_modulus_pa=4.8e9,
    yield_or_allowable_stress_pa=420.0e6,
    density_kg_m3=1320.0,
    allowable_strain=0.0042,
    damping_ratio=0.040,
)

MAT_TI_6AL_4V = StructuralMaterial(
    name='Ti-6Al-4V Grade 5 Alloy Struts',
    youngs_modulus_pa=114.0e9,
    shear_modulus_pa=44.0e9,
    yield_or_allowable_stress_pa=880.0e6,
    density_kg_m3=4430.0,
    allowable_strain=0.0077,
    damping_ratio=0.015,
)

MAT_LEXAN_CANOPY = StructuralMaterial(
    name='Polycarbonate Lexan MR10 Curved Shell',
    youngs_modulus_pa=2.40e9,
    shear_modulus_pa=0.86e9,
    yield_or_allowable_stress_pa=62.0e6,
    density_kg_m3=1200.0,
    allowable_strain=0.0180,
    damping_ratio=0.045,
)


# ---------------------------------------------------------------------------
# Component Rigidity & Compliance Specifications (Derived from Mechanics)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ComponentRigiditySpec:
    component_id: str
    material: StructuralMaterial
    effective_span_m: float
    second_moment_m4: float
    torsion_constant_m4: float
    section_half_depth_m: float
    effective_mass_kg: float
    design_limit_load_n: float
    stiffness_n_per_m: float
    damping_ns_per_m: float
    first_mode_hz: float
    max_elastic_deflection_m: float
    limit_stress_pa: float
    safety_factor: float
    is_rigid_primary: bool


def derive_component_rigidity_specs() -> dict[str, ComponentRigiditySpec]:
    """Derive exact Euler-Bernoulli stiffness, modal frequency, deflection & SF for each assembly."""
    # 1. Hull girder ("solid floating rock"): simply-supported / free-free equivalent spine L=5.05m
    l_hull = 5.05
    i_hull = 1.85e-3
    j_hull = 3.20e-3
    m_hull_eff = 480.0
    f_hull_slam = 4.0 * RC01_DESIGN_MASS_KG * G_SI
    k_hull = 48.0 * MAT_HULL_SANDWICH.youngs_modulus_pa * i_hull / (l_hull ** 3)
    d_hull = f_hull_slam / k_hull
    sig_hull = (f_hull_slam * l_hull * 0.25) * 0.34 / i_hull
    fn_hull = (1.0 / (2.0 * math.pi)) * math.sqrt(k_hull / m_hull_eff)
    c_hull = 2.0 * MAT_HULL_SANDWICH.damping_ratio * math.sqrt(k_hull * m_hull_eff)

    # 2. Main Wing Semi-Span (CFRP NACA 2414 box spar h=0.21m: bends cleanly within CFRP strain limit)
    b_wing = 4.28  # root shoulder y=0.52m to tip y=4.80m
    i_wing_eff = 1.15e-5  # Taper-weighted EI/E -> EI_eff = 8.05e5 N m^2
    j_wing_eff = 5.40e-5
    r_cp = 1.85  # center of pressure / effective point load arm
    f_wing_limit = 3.8 * (0.5 * RC01_DESIGN_MASS_KG * G_SI)
    # Using centroid-to-tip cantilever deflection delta = F * r^2 * (3L - r) / (6 EI)
    ei_wing = MAT_CFRP_SPAR.youngs_modulus_pa * i_wing_eff
    d_wing = f_wing_limit * (r_cp ** 2) * (3.0 * b_wing - r_cp) / (6.0 * ei_wing)
    k_wing_cp = f_wing_limit / d_wing
    m_wing_eff = 48.0  # modal generalized mass of one semi-span wing panel
    fn_wing = (3.516 / (2.0 * math.pi * (b_wing ** 2))) * math.sqrt(ei_wing / (77.5 / b_wing))
    c_wing = 2.0 * MAT_CFRP_SPAR.damping_ratio * math.sqrt(k_wing_cp * m_wing_eff)
    sig_wing = (f_wing_limit * r_cp) * 0.105 / (1.85e-5)  # root spar depth 0.210 m, I_root=1.85e-5

    # 3. Sponson + Titanium Strut Suspension (Series compliance of Ti V-strut + outer wing tip at y=3.80m)
    l_strut = 0.78
    a_strut_pair = 3.8e-4
    # Twin V-strut truss effective axial/vertical stiffness + wing outrigger arm y_out=3.28m
    k_strut_local = (MAT_TI_6AL_4V.youngs_modulus_pa * a_strut_pair / l_strut) * 0.0085  # ~1.58e5 N/m incl lug/bend
    y_sp_arm = 3.80 - 0.52  # 3.28 m outboard from fuselage carry-through
    k_wing_at_sp = 3.0 * ei_wing / (y_sp_arm ** 3) * 0.85  # outboard spar compliance ~ 58.2 kN/m
    k_sp_series = 1.0 / (1.0 / k_strut_local + 1.0 / k_wing_at_sp)  # ~ 42.5 kN/m series Ti + CFRP stiffness
    m_sp_eff = 12.0 + 38.0  # 12 kg structural + ~38 kg hydrodynamic added mass when half-submerged
    fn_sp = (1.0 / (2.0 * math.pi)) * math.sqrt(k_sp_series / m_sp_eff)
    # Include hydrodynamic radiation + Ti/CFRP composite damping zeta_eff ~ 0.16
    c_sp = 2.0 * 0.16 * math.sqrt(k_sp_series * m_sp_eff)
    f_sp_slam = 1800.0  # 3g sponson water slap load (N)
    d_sp = f_sp_slam / k_sp_series
    sig_sp = (f_sp_slam / math.sin(math.radians(48.0))) / a_strut_pair + (f_sp_slam * 0.12 * 0.018 / 2.6e-8)

    # 4. Tail Pylon + T-Tail Box (High-modulus CFRP: minimal torsion/bend under thrust + rudder)
    h_pylon = 1.60
    i_pylon = 4.50e-6
    ei_pylon = MAT_CFRP_HIGH_MOD.youngs_modulus_pa * i_pylon
    f_pylon_lat = 1200.0
    k_pylon = 3.0 * ei_pylon / (h_pylon ** 3)
    d_pylon = f_pylon_lat / k_pylon
    m_pylon_eff = 38.0
    fn_pylon = (3.516 / (2.0 * math.pi * (h_pylon ** 2))) * math.sqrt(ei_pylon / (38.0 / h_pylon))
    c_pylon = 2.0 * MAT_CFRP_HIGH_MOD.damping_ratio * math.sqrt(k_pylon * m_pylon_eff)
    sig_pylon = (f_pylon_lat * h_pylon) * 0.065 / i_pylon

    # 5. Duct Cross-Arm & Shroud Ring (CFRP twin-duct saddle arm, L_arm=0.78m)
    l_arm = 0.78
    i_arm = 2.10e-6
    ei_arm = MAT_CFRP_HIGH_MOD.youngs_modulus_pa * i_arm
    k_arm = 3.0 * ei_arm / (l_arm ** 3)
    f_fan_limit = 2200.0  # peak thrust + 4g vertical inertia
    d_arm = f_fan_limit / k_arm
    m_fan_eff = 28.0
    fn_arm = (1.0 / (2.0 * math.pi)) * math.sqrt(k_arm / m_fan_eff)
    c_arm = 2.0 * MAT_CFRP_HIGH_MOD.damping_ratio * math.sqrt(k_arm * m_fan_eff)
    sig_arm = (f_fan_limit * l_arm) * 0.045 / i_arm

    # 6. Compound-Curved Polycarbonate Canopy Shell (dome thickness t=6mm, effective arch R=0.44m)
    r_can = 0.44
    t_can = 0.006
    l_can = RC01_COCKPIT_LENGTH_M
    # Curved shell radial/arch stiffness scales as ~ E * t^3 / (R^3 * 0.15) + membrane E*t/R
    k_can = (MAT_LEXAN_CANOPY.youngs_modulus_pa * t_can / r_can) * 0.012  # local panel bending + arch membrane ~ 393 kN/m
    p_dyn_max = 0.5 * RHO_AIR_ISA * (65.0 ** 2)  # ~2587 Pa @ 65 m/s Vne
    f_can_load = p_dyn_max * 1.45  # exposed projected frontal pressure load (N)
    d_can = f_can_load / k_can
    m_can_eff = 16.0
    fn_can = (1.0 / (2.0 * math.pi)) * math.sqrt(k_can / m_can_eff)
    c_can = 2.0 * MAT_LEXAN_CANOPY.damping_ratio * math.sqrt(k_can * m_can_eff)
    sig_can = p_dyn_max * r_can / t_can + (p_dyn_max * (0.28 ** 2)) / (t_can ** 2)

    specs = {
        'hull_girder': ComponentRigiditySpec(
            component_id='hull_girder',
            material=MAT_HULL_SANDWICH,
            effective_span_m=l_hull,
            second_moment_m4=i_hull,
            torsion_constant_m4=j_hull,
            section_half_depth_m=0.34,
            effective_mass_kg=m_hull_eff,
            design_limit_load_n=f_hull_slam,
            stiffness_n_per_m=k_hull,
            damping_ns_per_m=c_hull,
            first_mode_hz=fn_hull,
            max_elastic_deflection_m=d_hull,
            limit_stress_pa=sig_hull,
            safety_factor=MAT_HULL_SANDWICH.yield_or_allowable_stress_pa / max(1.0, sig_hull),
            is_rigid_primary=True,
        ),
        'main_wing': ComponentRigiditySpec(
            component_id='main_wing',
            material=MAT_CFRP_SPAR,
            effective_span_m=b_wing,
            second_moment_m4=i_wing_eff,
            torsion_constant_m4=j_wing_eff,
            section_half_depth_m=0.068,
            effective_mass_kg=m_wing_eff,
            design_limit_load_n=f_wing_limit,
            stiffness_n_per_m=k_wing_cp,
            damping_ns_per_m=c_wing,
            first_mode_hz=fn_wing,
            max_elastic_deflection_m=d_wing,
            limit_stress_pa=sig_wing,
            safety_factor=MAT_CFRP_SPAR.yield_or_allowable_stress_pa / max(1.0, sig_wing),
            is_rigid_primary=False,
        ),
        'sponson_strut_assembly': ComponentRigiditySpec(
            component_id='sponson_strut_assembly',
            material=MAT_TI_6AL_4V,
            effective_span_m=l_strut,
            second_moment_m4=2.6e-8,
            torsion_constant_m4=4.5e-8,
            section_half_depth_m=0.018,
            effective_mass_kg=m_sp_eff,
            design_limit_load_n=f_sp_slam,
            stiffness_n_per_m=k_sp_series,
            damping_ns_per_m=c_sp,
            first_mode_hz=fn_sp,
            max_elastic_deflection_m=d_sp,
            limit_stress_pa=sig_sp,
            safety_factor=MAT_TI_6AL_4V.yield_or_allowable_stress_pa / max(1.0, sig_sp),
            is_rigid_primary=False,
        ),
        'tail_pylon_t_tail': ComponentRigiditySpec(
            component_id='tail_pylon_t_tail',
            material=MAT_CFRP_HIGH_MOD,
            effective_span_m=h_pylon,
            second_moment_m4=i_pylon,
            torsion_constant_m4=6.2e-6,
            section_half_depth_m=0.065,
            effective_mass_kg=m_pylon_eff,
            design_limit_load_n=f_pylon_lat,
            stiffness_n_per_m=k_pylon,
            damping_ns_per_m=c_pylon,
            first_mode_hz=fn_pylon,
            max_elastic_deflection_m=d_pylon,
            limit_stress_pa=sig_pylon,
            safety_factor=MAT_CFRP_HIGH_MOD.yield_or_allowable_stress_pa / max(1.0, sig_pylon),
            is_rigid_primary=True,
        ),
        'duct_shroud_and_arm': ComponentRigiditySpec(
            component_id='duct_shroud_and_arm',
            material=MAT_CFRP_HIGH_MOD,
            effective_span_m=l_arm,
            second_moment_m4=i_arm,
            torsion_constant_m4=3.4e-6,
            section_half_depth_m=0.045,
            effective_mass_kg=m_fan_eff,
            design_limit_load_n=f_fan_limit,
            stiffness_n_per_m=k_arm,
            damping_ns_per_m=c_arm,
            first_mode_hz=fn_arm,
            max_elastic_deflection_m=d_arm,
            limit_stress_pa=sig_arm,
            safety_factor=MAT_CFRP_HIGH_MOD.yield_or_allowable_stress_pa / max(1.0, sig_arm),
            is_rigid_primary=True,
        ),
        'canopy_dome': ComponentRigiditySpec(
            component_id='canopy_dome',
            material=MAT_LEXAN_CANOPY,
            effective_span_m=l_can,
            second_moment_m4=7.5e-7,
            torsion_constant_m4=1.2e-6,
            section_half_depth_m=t_can * 0.5,
            effective_mass_kg=m_can_eff,
            design_limit_load_n=f_can_load,
            stiffness_n_per_m=k_can,
            damping_ns_per_m=c_can,
            first_mode_hz=fn_can,
            max_elastic_deflection_m=d_can,
            limit_stress_pa=sig_can,
            safety_factor=MAT_LEXAN_CANOPY.yield_or_allowable_stress_pa / max(1.0, sig_can),
            is_rigid_primary=True,
        ),
    }
    return specs


COMPONENT_RIGIDITY_SPECS: dict[str, ComponentRigiditySpec] = derive_component_rigidity_specs()


# ---------------------------------------------------------------------------
# Aerodynamic Canopy + Forebody Parasitic Drag Model (Hoerner / Sears-Haack)
# ---------------------------------------------------------------------------
def canopy_and_craft_cd0(
    windshield_rake_deg: float,
    canopy_fineness_ratio: float,
    frontal_canopy_area_m2: float = 0.44,
    s_ref_m2: float = RC01_WING_AREA_M2,
) -> dict[str, float]:
    """Compute canopy incremental Cd and full-craft parasitic Cd0 from fineness ratio & rake.

    References:
    - Hoerner Fluid-Dynamic Drag: blunt flat windshield (~0.70) vs curved compound canopy (~0.08-0.14)
    - Streamlined body pressure+skin-friction transition drag (https://arxiv.org/abs/2603.23843v2)
    """
    sin_th = math.sin(math.radians(max(5.0, min(89.0, windshield_rake_deg))))
    f_r = max(1.2, canopy_fineness_ratio)
    # Streamlined dome form factor + inclined stagnation component (flat brick -> sin^2~1.0, sleek rake -> 0.18)
    cd_canopy_local = 0.055 * (1.0 + 1.5 / f_r + 7.0 / (f_r ** 3)) + 0.32 * (sin_th ** 3)
    delta_cd0_canopy = cd_canopy_local * (frontal_canopy_area_m2 / s_ref_m2)
    # Clean wing + hull + tail + shrouded nacelles base Cd0 ~ 0.0325
    cd0_airframe_clean = 0.0325
    cd0_total = cd0_airframe_clean + delta_cd0_canopy
    return {
        'cd_canopy_local': float(cd_canopy_local),
        'delta_cd0_canopy': float(delta_cd0_canopy),
        'cd0_airframe_clean': float(cd0_airframe_clean),
        'cd0_total': float(cd0_total),
    }


def evaluate_mesh_curve_stability(
    hull_verts: np.ndarray,
    hull_faces: np.ndarray,
    sponson_port_verts: np.ndarray,
    sponson_port_faces: np.ndarray,
    sponson_mount_z_m: float,
    sponson_mount_y_m: float = 3.80,
    mass_kg: float = RC01_DESIGN_MASS_KG,
    cg_z_m: float = 0.704,
) -> dict[str, Any]:
    """Evaluate exact hydrostatic equilibrium draft, hull GM_T, total multi-hull GM_T, and sponson depth."""
    from vtx.water.hydrodynamics import _clip_submerged_triangles, _submerged_volume_and_centroid

    z_keel = float(np.min(hull_verts[:, 2]))
    target_vol = mass_kg / RHO_FRESHWATER_15C

    def eval_draft(draft: float, compute_moments: bool = True) -> dict[str, float]:
        z_wl = z_keel + draft
        # Clip hull using per-vertex submergence depth (water_z - vert_z)
        s_h = z_wl - hull_verts[:, 2]
        wet_h, _, _, cap_h = _clip_submerged_triangles(hull_verts, hull_faces, s_h)
        if len(wet_h):
            v_h, cb_h = _submerged_volume_and_centroid(wet_h, cap_h, np.array([0.0, 0.0, z_wl]))
        else:
            v_h, cb_h = 0.0, np.array([0.0, 0.0, z_keel])
        sp_w = sponson_port_verts.copy()
        sp_w[:, 1] += sponson_mount_y_m
        sp_w[:, 2] += sponson_mount_z_m
        s_sp = z_wl - sp_w[:, 2]
        wet_sp, _, _, cap_sp = _clip_submerged_triangles(sp_w, sponson_port_faces, s_sp)
        if len(wet_sp):
            v_sp, cb_sp = _submerged_volume_and_centroid(wet_sp, cap_sp, np.array([0.0, sponson_mount_y_m, z_wl]))
        else:
            v_sp, cb_sp = 0.0, np.array([0.0, sponson_mount_y_m, sponson_mount_z_m])
        v_tot = v_h + 2.0 * v_sp
        if not compute_moments:
            return {'draft_m': float(draft), 'total_disp_m3': float(v_tot)}
        a_wl_h, i_t_h, _ = _waterplane_moments(hull_verts, hull_faces, z_wl)
        a_wl_sp, i_t_sp_loc, _ = _waterplane_moments(sp_w, sponson_port_faces, z_wl)
        cb_z_tot = (v_h * cb_h[2] + 2.0 * v_sp * cb_sp[2]) / max(1e-9, v_tot)
        cb_x_tot = (v_h * cb_h[0] + 2.0 * v_sp * cb_sp[0]) / max(1e-9, v_tot)
        bm_hull = i_t_h / max(1e-6, v_h)
        gm_hull = float(cb_h[2] + bm_hull - cg_z_m)
        i_t_tot = i_t_h + 2.0 * (i_t_sp_loc + a_wl_sp * (sponson_mount_y_m ** 2))
        gm_total = float(cb_z_tot + (i_t_tot / max(1e-6, v_tot)) - cg_z_m)
        sp_bottom_z = float(np.min(sp_w[:, 2]))
        sp_immersion_m = float(z_wl - sp_bottom_z)
        return {
            'draft_m': float(draft),
            'total_disp_m3': float(v_tot),
            'hull_disp_m3': float(v_h),
            'sponson_disp_each_m3': float(v_sp),
            'lcb_x_m': float(cb_x_tot),
            'vcb_z_m': float(cb_z_tot),
            'hull_awl_m2': float(a_wl_h),
            'sponson_awl_each_m2': float(a_wl_sp),
            'gm_hull_only_m': gm_hull,
            'gm_total_m': gm_total,
            'sponson_immersion_m': sp_immersion_m,
            'sponson_buoyancy_each_n': float(v_sp * RHO_FRESHWATER_15C * G_SI),
        }

    lo, hi = 0.05, 1.15
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if eval_draft(mid, compute_moments=False)['total_disp_m3'] < target_vol:
            lo = mid
        else:
            hi = mid
    res = eval_draft(0.5 * (lo + hi), compute_moments=True)
    res['mass_kg'] = float(mass_kg)
    res['target_disp_m3'] = float(target_vol)
    return res


def _waterplane_moments(verts: np.ndarray, faces: np.ndarray, z_wl: float) -> tuple[float, float, float]:
    """Compute exact waterplane area A_WL, transverse I_T (about y-mean), and longitudinal I_L from horizontal slice."""
    tris = verts[faces]
    z = tris[:, :, 2] - z_wl
    # Find triangles straddling z = 0
    above = z >= 0.0
    n_above = np.sum(above, axis=1)
    straddle = (n_above == 1) | (n_above == 2)
    segs = []
    for t, zv, na in zip(tris[straddle], z[straddle], n_above[straddle]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            zi, zj = zv[i], zv[j]
            if (zi >= 0.0) != (zj >= 0.0):
                alpha = -zi / (zj - zi) if abs(zj - zi) > 1e-12 else 0.5
                p = t[i] + alpha * (t[j] - t[i])
                pts.append(p[:2])
        if len(pts) == 2:
            segs.append((pts[0], pts[1]))
    if len(segs) < 3:
        return 0.0, 0.0, 0.0
    # Compute 2D Green's theorem moments using unoriented segment centroid pairing:
    # Build closed boundary half-width or sort around centroid of intersection points
    # More robustly: estimate transverse breadth B(x) along X grid from crossing segments!
    pts_all = np.array([p for s in segs for p in s])
    xmin, xmax = float(pts_all[:, 0].min()), float(pts_all[:, 0].max())
    if xmax - xmin < 1e-4:
        return 0.0, 0.0, 0.0
    nx = 64
    xs = np.linspace(xmin, xmax, nx)
    dx = xs[1] - xs[0]
    area = 0.0
    it = 0.0
    il = 0.0
    x_bar = float(np.mean(pts_all[:, 0]))
    y_bar = float(np.mean(pts_all[:, 1]))
    for x0 in xs:
        ys_cross = []
        for p0, p1 in segs:
            x1, y1 = p0
            x2, y2 = p1
            if (x1 <= x0 < x2) or (x2 <= x0 < x1):
                t = (x0 - x1) / (x2 - x1)
                ys_cross.append(y1 + t * (y2 - y1))
        if len(ys_cross) >= 2:
            y_lo = min(ys_cross) - y_bar
            y_hi = max(ys_cross) - y_bar
            b = max(0.0, y_hi - y_lo)
            area += b * dx
            it += ((y_hi ** 3 - y_lo ** 3) / 3.0) * dx
            il += b * ((x0 - x_bar) ** 2) * dx
    return float(area), float(it), float(il)


def compute_structural_loads_snapshot(
    aero_force_body_n: np.ndarray,
    sponson_port_z_force_n: float,
    sponson_stbd_z_force_n: float,
    hull_hydro_z_n: float,
    fan_thrust_port_n: float,
    fan_thrust_stbd_n: float,
    dynamic_pressure_pa: float,
    sponson_port_deflection_m: float = 0.0,
    sponson_stbd_deflection_m: float = 0.0,
) -> dict[str, dict[str, float]]:
    """Compute real-time elastic deflections & structural margin ratios across RC-01 components."""
    specs = COMPONENT_RIGIDITY_SPECS
    w_lift_per_side = 0.5 * abs(float(aero_force_body_n[2]))
    wing_spec = specs['main_wing']
    wing_defl_m = w_lift_per_side / max(1.0, wing_spec.stiffness_n_per_m)
    wing_stress_ratio = w_lift_per_side / max(1.0, wing_spec.design_limit_load_n)

    hull_spec = specs['hull_girder']
    hull_load_n = max(abs(hull_hydro_z_n), RC01_DESIGN_MASS_KG * G_SI)
    hull_defl_m = hull_load_n / max(1.0, hull_spec.stiffness_n_per_m)

    sp_spec = specs['sponson_strut_assembly']
    sp_max_f = max(abs(sponson_port_z_force_n), abs(sponson_stbd_z_force_n))
    sp_defl_m = max(abs(sponson_port_deflection_m), abs(sponson_stbd_deflection_m), sp_max_f / sp_spec.stiffness_n_per_m)

    pylon_spec = specs['tail_pylon_t_tail']
    asym_thrust = abs(float(fan_thrust_port_n) - float(fan_thrust_stbd_n))
    pylon_lat_load = asym_thrust * 0.65 + abs(float(aero_force_body_n[1])) * 0.25
    pylon_defl_m = pylon_lat_load / max(1.0, pylon_spec.stiffness_n_per_m)

    can_spec = specs['canopy_dome']
    can_load = float(dynamic_pressure_pa) * 1.45
    can_defl_m = can_load / max(1.0, can_spec.stiffness_n_per_m)

    return {
        'hull_girder': {
            'deflection_m': float(hull_defl_m),
            'stiffness_n_m': float(hull_spec.stiffness_n_per_m),
            'first_mode_hz': float(hull_spec.first_mode_hz),
            'utilization': float(hull_load_n / max(1.0, hull_spec.design_limit_load_n)),
        },
        'main_wing': {
            'deflection_m': float(wing_defl_m),
            'stiffness_n_m': float(wing_spec.stiffness_n_per_m),
            'first_mode_hz': float(wing_spec.first_mode_hz),
            'utilization': float(wing_stress_ratio),
        },
        'sponson_strut_assembly': {
            'deflection_m': float(sp_defl_m),
            'stiffness_n_m': float(sp_spec.stiffness_n_per_m),
            'first_mode_hz': float(sp_spec.first_mode_hz),
            'utilization': float(sp_max_f / max(1.0, sp_spec.design_limit_load_n)),
        },
        'tail_pylon_t_tail': {
            'deflection_m': float(pylon_defl_m),
            'stiffness_n_m': float(pylon_spec.stiffness_n_per_m),
            'first_mode_hz': float(pylon_spec.first_mode_hz),
            'utilization': float(pylon_lat_load / max(1.0, pylon_spec.design_limit_load_n)),
        },
        'canopy_dome': {
            'deflection_m': float(can_defl_m),
            'stiffness_n_m': float(can_spec.stiffness_n_per_m),
            'first_mode_hz': float(can_spec.first_mode_hz),
            'utilization': float(can_load / max(1.0, can_spec.design_limit_load_n)),
        },
    }


def rigidity_spec_summary() -> dict[str, Any]:
    return {k: asdict(v) for k, v in COMPONENT_RIGIDITY_SPECS.items()}
