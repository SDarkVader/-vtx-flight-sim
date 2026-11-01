"""Visualization reads the solver's signed rotor rates; pilot observations remain separate."""
import mujoco as mj
import pytest
from vtx.aircraft import Aircraft
from vtx.live_server import Laboratory


def test_rotor_signed_speed_is_physical_rendering_truth():
    p=Aircraft();p.spawn(0,0,0)
    rates=[11.,-22.,33.,-44.]
    for i,rate in enumerate(rates,1):
        p.data.qvel[p.vadr[f'rotor{i}_spin']]=rate
    mj.mj_forward(p.model,p.data)
    truth=p.physical_snapshot()
    assert truth['rotor_spin_rad_s']==pytest.approx(rates)
    obs=Laboratory().sensor_observation()
    assert 'rotor_spin_rad_s' not in obs
