import importlib.util
import math
from pathlib import Path


spec = importlib.util.spec_from_file_location('drive_bench', Path(__file__).parents[1] / 'tools/bench_variable_drive.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_planetary_kinematics_and_power_in_both_directions():
    for rpm, expected in [(1100, -400/3), (1200, 0), (1300, 400/3)]:
        p = bench.point(rpm)
        assert math.isclose(p['ring_rpm'], expected, abs_tol=1e-10)
        assert math.isclose(p['sun_power_kw'] + p['ring_power_kw'], p['fan_power_kw'], abs_tol=1e-10)
    assert bench.point(1100)['motor_shaft_power_kw'] < 0 < bench.point(1300)['motor_shaft_power_kw']


def test_rotor_acceleration_adds_inertia_load():
    steady, ramp = bench.point(1200), bench.point(1200, 100)
    expected = bench.ROTOR_INERTIA * 100 * bench.RAD_S_PER_RPM
    assert math.isclose(ramp['carrier_torque_nm'] - steady['carrier_torque_nm'], expected, abs_tol=1e-10)
    assert ramp['motor_torque_nm'] > steady['motor_torque_nm']
