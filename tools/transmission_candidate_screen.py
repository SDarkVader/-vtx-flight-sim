"""Reproducible preliminary drivetrain arithmetic, not a qualification analysis.

Assumptions are encoded explicitly; none are material tests or actual duty data.
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ledger = json.loads((ROOT / 'evidence/source/airframe_ledger.json').read_text())
rpm_in, rpm_fan, power_w, transfer_eff = 6016., 1200., 300000., .95
fan_power = power_w * transfer_eff / 4
fan_torque = fan_power / (rpm_fan * 2 * math.pi / 60)
ring_torque = fan_torque * .75
fixed_ratio = 4.
sun_speed = rpm_in / fixed_ratio

def shaft_torsion(d_outer, d_inner, torque, length, shear_modulus):
    polar = math.pi * (d_outer**4 - d_inner**4) / 32
    stress = torque * d_outer / (2 * polar)
    strain = stress / shear_modulus
    twist = torque * length / (shear_modulus * polar)
    return dict(outer_diameter_mm=d_outer*1000, inner_diameter_mm=d_inner*1000,
                torque_nm=torque, span_m=length, shear_modulus_gpa=shear_modulus/1e9,
                shear_stress_mpa=stress/1e6, max_shear_strain_microstrain=strain*1e6,
                twist_deg=math.degrees(twist), torsional_stiffness_nm_per_rad=shear_modulus*polar/length)

speeds = []
for speed in (1100., 1200., 1300.):
    ring_rpm = (4*speed - sun_speed)/3
    speeds.append(dict(carrier_rpm=speed,sun_rpm=sun_speed,ring_rpm=ring_rpm,
                       sun_mesh_hz=abs(sun_speed-speed)*20/60,
                       fixed_ring_torque_power_kw=ring_torque*ring_rpm*2*math.pi/60/1000))

assert 60 == 20 + 2*20
assert (20+60) % 4 == 0 and (20+60) % 3 != 0
geometric_adjacency_margin_modules = (20+20)*math.sin(math.pi/4)-(20+2)
assert geometric_adjacency_margin_modules > 0
shaft_geom = next(p for p in ledger['parts'] if p['name']=='P03 | F1 radial drive shaft')['bounds_m']
shaft_diameter = shaft_geom[1][1]-shaft_geom[0][1]
inertia = ledger['bodies']['rotor1']['inertia_centroid_kg_m2'][2][2]
examples = [shaft_torsion(shaft_diameter,inner,torque,.96,79.3e9)
            for inner in (0., .066) for torque in (power_w/4/(rpm_in*2*math.pi/60),fan_torque)]
for x in examples:
    x['ideal_fixed_base_rotor_only_hz'] = math.sqrt(x['torsional_stiffness_nm_per_rad']/inertia)/(2*math.pi)
data = dict(status='illustrative arithmetic only; no component qualification',
    assumptions=dict(engine_input_rpm=rpm_in, fan_rpm=rpm_fan, mechanical_input_w=power_w,
                     overall_efficiency=transfer_eff, equal_fan_loads=True, example_gear_sun_teeth=20,
                     example_gear_planet_teeth=20,example_gear_ring_teeth=60,
                     shaft_bounds_outer_diameter_m=shaft_diameter, example_shear_modulus_pa=79.3e9,
                     gear_efficiency_in_motor_link=.95, candidate_motor_ratio=3.,
                     rotor_inertia_kg_m2_model=inertia,
                     notes='Shaft material, wall thickness, actual torque path and supports unknown; rotor inertia is allocation-based. 1300 rpm is an illustrative unapproved endpoint.'),
    nominal=dict(fan_power_w=fan_power,fan_torque_nm=fan_torque,ring_torque_nm=ring_torque,
                 input_torque_per_equal_branch_nm=power_w/4/(rpm_in*2*math.pi/60),
                 motor_torque_nm_at_3_to_1_and_95pct=ring_torque/(3*.95),
                 blade_pass_hz_4_blades=4*rpm_fan/60,turbine_shaft_hz=rpm_in/60),
    gear=dict(equal_spacing_four_planets=(20+60)/4,equal_spacing_three_planets=(20+60)/3,
              planet_tip_clearance_modules=geometric_adjacency_margin_modules,
              note='Standard unshifted external sun/planet and internal ring, same module, no proof of clearance under deflection.'),
    speed_cases=speeds,shaft_scenarios=examples)
print(json.dumps(data,indent=2))
