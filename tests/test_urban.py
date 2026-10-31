import pytest
from vtx.urban_reference import from_rest,turn_90,make_scenario,MPH_TO_MPS,A_MAX,J_MAX

@pytest.mark.parametrize('mph',[10.,20.,30.])
def test_reference_trajectory_heading_and_jerk(mph):
    x=make_scenario(mph)
    turn=x['turn_90_degrees']
    assert abs(turn['final_heading_deg']-90)<1e-3
    assert turn['peak_total_jerk_mps3']<=J_MAX+1e-8
    assert turn['peak_lateral_acceleration_mps2']<=A_MAX+1e-8
    assert turn['turn_dx_m']>0 and turn['turn_dy_m']>0
    assert x['route_total_time_s']>turn['time_s']

@pytest.mark.parametrize('mph',[10.,20.,30.])
def test_urban_braking_distance_and_time_are_positive(mph):
    st=from_rest(mph*MPH_TO_MPS)
    assert st['time_s']>0 and st['distance_m']>0
    assert st['max_jerk_mps3']<=J_MAX
    assert st['max_acceleration_mps2']<=A_MAX+1e-12


def test_lower_speed_gives_smaller_corner_radius():
    assert turn_90(20*MPH_TO_MPS)['steady_radius_m'] < turn_90(30*MPH_TO_MPS)['steady_radius_m']
