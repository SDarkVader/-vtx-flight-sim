import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('fan_ecu_shadow',Path(__file__).parents[1]/'tools/fan_ecu_shadow.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_combined_tilt_and_optional_speed_limit():
    result=module.evaluate([[0,0],[12,16],[15,15],[0,-20]], [1200,1200,1250,1300], max_rpm=1275)
    assert [p['tilt_outside_cone'] for p in result['fans']] == [False,False,True,False]
    assert [p['speed_above_limit'] for p in result['fans']] == [False,False,False,True]
    assert result['speed_spread_rpm']==100

def test_no_invented_speed_limit_and_nonfinite_rejected():
    assert module.evaluate([[0,0]]*4,[1200]*4)['fans'][0]['speed_above_limit'] is None
    try:
        module.evaluate([[0,0]]*4,[1200,1200,float('nan'),1200])
    except ValueError:
        return
    raise AssertionError('Non-finite input accepted')
