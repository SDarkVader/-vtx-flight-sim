"""Idealized four-branch planetary bench; not a flight simulation or gearbox validation."""
import json
import math

SUN_RPM = 4800.0
LOAD_NM = 566.9894847648771  # fixed illustrative aerodynamic load
ROTOR_INERTIA = 3.3325749872301054  # allocation-based, fan rotor only
RATIO = 3.0
EFFICIENCY = .95  # hypothetical control gearing, not inverter/motor efficiency
RAD_S_PER_RPM = 2 * math.pi / 60


def point(fan_rpm, accel_rpm_s=0.0):
    """Positive output torque drives the fan; positive ring power enters the gearset."""
    torque = LOAD_NM + ROTOR_INERTIA * accel_rpm_s * RAD_S_PER_RPM
    ring_rpm = (4 * fan_rpm - SUN_RPM) / 3
    sun_torque, ring_torque = torque / 4, 3 * torque / 4
    fan_power = torque * fan_rpm * RAD_S_PER_RPM
    ring_power = ring_torque * ring_rpm * RAD_S_PER_RPM
    sun_power = sun_torque * SUN_RPM * RAD_S_PER_RPM
    # An ideal gearset conserves instantaneous mechanical power, including inertia.
    assert math.isclose(sun_power + ring_power, fan_power, abs_tol=1e-8)
    # Reverse power uses the opposite loss direction. Motor electrical losses excluded.
    motor_power = ring_power / EFFICIENCY if ring_power >= 0 else ring_power * EFFICIENCY
    motor_torque = motor_power / (RATIO * ring_rpm * RAD_S_PER_RPM) if ring_rpm else ring_torque / (RATIO * EFFICIENCY)
    return dict(fan_rpm=fan_rpm, acceleration_rpm_s=accel_rpm_s,
                ring_rpm=ring_rpm, motor_rpm=RATIO * ring_rpm,
                carrier_torque_nm=torque, ring_torque_nm=ring_torque,
                motor_torque_nm=motor_torque, sun_power_kw=sun_power/1000,
                ring_power_kw=ring_power/1000, motor_shaft_power_kw=motor_power/1000,
                fan_power_kw=fan_power/1000,
                mesh_hz=20*abs(SUN_RPM-fan_rpm)/60)


def main():
    # Quasi-static samples of a commanded ramp, no actuator dynamics assumed.
    cases = {
        'steady_1100': point(1100), 'steady_1200': point(1200),
        'steady_1300': point(1300), 'ramp_up_1200': point(1200, 100),
        'ramp_down_1200': point(1200, -100),
    }
    mixed = [point(s) for s in (1100, 1200, 1250, 1300)]
    output = dict(description='Idealized single-step arithmetic bench, not an aircraft test',
                  assumptions={'constant_sun_rpm': SUN_RPM, 'fixed_aerodynamic_torque_nm': LOAD_NM,
                               'fan_rotor_inertia_kg_m2': ROTOR_INERTIA,
                               'four_equal_branches_for_totals': True,
                               'control_gear_efficiency': EFFICIENCY,
                               'omissions': ['motor/inverter losses and thermal behavior', 'gear compliance and dynamics',
                                             'gearbox and motor inertia', 'actual fan load curve',
                                             'starting and fault behavior', 'engine response',
                                             'bearing/frame loads', 'four quadrant duty validation']},
                  cases=cases,
                  mixed_four_branch=dict(fan_rpm=[p['fan_rpm'] for p in mixed],
                      sum_ring_mechanical_kw=sum(p['ring_power_kw'] for p in mixed),
                      sum_motor_shaft_kw=sum(p['motor_shaft_power_kw'] for p in mixed),
                      gross_abs_motor_shaft_kw=sum(abs(p['motor_shaft_power_kw']) for p in mixed)),
                  equal_four_branch_1200_ramp_up_sun_kw=4*cases['ramp_up_1200']['sun_power_kw'])
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
