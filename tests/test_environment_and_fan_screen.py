"""Analytical screening and selectable-environment regressions, not flight tests."""
import math
import json
import numpy as np
import pytest
from vtx.aircraft import Aircraft
from vtx.atmosphere import standard_air_density
from vtx.ducted_fan_screen import annulus_area, hover_power_w, hover_thrust_n, ideal_duct_bound_power_w
from vtx.live_server import Laboratory, Mission


def test_standard_atmosphere_and_range():
    assert standard_air_density(0) == pytest.approx(1.225, rel=1e-5)
    assert standard_air_density(5000) == pytest.approx(.7361, rel=1e-3)
    assert standard_air_density(11000) == pytest.approx(.3639, rel=1e-3)
    assert standard_air_density(11000.001) == pytest.approx(standard_air_density(11000), rel=1e-6)
    assert standard_air_density(20000) < standard_air_density(11000)
    with pytest.raises(ValueError):standard_air_density(20001)


def test_steady_wind_and_isa_affect_physical_plant():
    p=Aircraft(atmosphere_model='isa',wind_world_mps=[10,0,0])
    p.spawn(0,0,5000)
    p.step()
    rho=standard_air_density(p.data.xpos[p.bids['airframe'],2])
    assert p.data.xfrc_applied[p.bids['airframe'],0] == pytest.approx(.5*rho*1.65*100, rel=1e-4)
    assert p.aero.rho == pytest.approx(standard_air_density(p.data.xpos[p.bids['rotor4'],2]), rel=1e-4)
    assert p.physical_snapshot()['environment']['wind_world_mps'] == [10,0,0]
    actuator=p.physical_snapshot()['actuators']['nacelle'][0][0]
    assert {'request_n','applied_n','limit_n','saturated'} <= actuator.keys()
    assert abs(actuator['applied_n']) <= actuator['limit_n']
    json.dumps(p.physical_snapshot(),allow_nan=False)
    with pytest.raises(ValueError):p.set_wind([0,float('nan'),0])


def test_environment_survives_retry_and_checkpoint(tmp_path,monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory()
    lab.start(Mission(atmosphere_model='isa',wind_world_mps=[3,-4,1],time_scale=.05))
    lab.checkpoint(force=True)
    lab.audit_file.close()
    restored=Laboratory()
    assert restored.aircraft.atmosphere_model == 'isa'
    np.testing.assert_allclose(restored.aircraft.wind,[3,-4,1])
    restored.stop('test')
    restored.retry({})
    assert restored.aircraft.atmosphere_model == 'isa'
    np.testing.assert_allclose(restored.aircraft.wind,[3,-4,1])
    assert restored.time_scale == .05
    restored.stop('test')


def test_hover_screen_is_reversible_and_separates_ideal_bound():
    area=annulus_area(.245,.110)
    assert area == pytest.approx(.151,abs=.001)
    thrust=1300*9.80665/4
    power=hover_power_w(thrust,area,.8)
    assert hover_thrust_n(power,area,.8) == pytest.approx(thrust)
    open_ideal=hover_power_w(thrust,area,1.)
    assert ideal_duct_bound_power_w(thrust,area,1.)/open_ideal == pytest.approx(1/math.sqrt(2))
    with pytest.raises(ValueError):annulus_area(.1,.2)
    with pytest.raises(ValueError):hover_power_w(thrust,area,0)
