"""Independent shaft equation/load cases; canned benches are not flights."""
import pytest
from vtx.governor import ShaftGovernor


def integrate(mode,load,seconds=20):
    g=ShaftGovernor(mode);w=100.;dt=.0025;j=13.90207224855
    for _ in range(int(seconds/dt)):
        t=g.update(100.,w,3000.,dt,True)
        w+=(t-load)/j*dt
        assert 0<=t<=3000
    return w,g


def test_integral_removes_load_droop_without_flight_feedback():
    old,_=integrate('legacy-p',1600.)
    new,g=integrate('pi',1600.)
    assert old==pytest.approx(100-1600/180,abs=1e-7)
    assert new==pytest.approx(100,abs=.001)
    assert g.integral_nm==pytest.approx(1600,abs=.2)


def test_impossible_load_does_not_wind_up_or_generate_idle_torque():
    g=ShaftGovernor()
    for _ in range(8000):assert g.update(100,0,500,.0025,True)==500
    assert g.integral_nm==0
    assert g.update(100,0,500,.0025,False)==0
    assert g.integral_nm==0
    # Overspeed must remove drive, never impose a fictitious negative brake.
    assert g.update(100,120,500,.0025,True)==0

def test_overspeed_fuel_cut_removes_drive_without_changing_measured_speed():
    g=ShaftGovernor();g.integral_nm=2000
    assert g.update(100,102,3000,.0025,True)==0
    assert g.telemetry['overspeed_fuel_cut'] is True

def test_selected_engine_power_ceiling_applies_to_actual_plant_and_fuel_burn():
    from vtx.aircraft import Aircraft,DT
    p=Aircraft(rpm=1200,fuel_kg=10,engine_power_limit_kw=100)
    p.spawn(0,0,30);p.command['engine']=1;p.command['collective_deg']=[25]*4
    for _ in range(2000):
        p.step()
        assert p.power['engine_w']<=100000*p.engine_spool+1e-6
    assert p.fuel_initial.sum()==10
    assert float((p.fuel_initial-p.fuel).sum())==pytest.approx(p.energy['engine_j']*.4/3.6e6,abs=1e-9)
