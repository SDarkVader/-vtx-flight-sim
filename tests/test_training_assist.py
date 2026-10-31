import pytest
from vtx.training_assist import assisted_collective


def test_assistance_is_opt_in_and_damps_both_body_rates():
    requested=[10.]*4
    assert assisted_collective(requested,[8.,-6.,0.],0.)==requested
    half=assisted_collective(requested,[8.,-6.,0.],.5)
    full=assisted_collective(requested,[8.,-6.,0.],1.)
    assert full[1]<10<full[3]  # Oppose positive X rotation.
    assert full[2]>10>full[0]  # Oppose negative Y rotation.
    assert sum(full)==pytest.approx(sum(requested))
    assert half[1]-10==pytest.approx((full[1]-10)/2)


def test_assistance_respects_collective_bounds_and_rejects_bad_values():
    assert assisted_collective([30.,0.,30.,0.],[50.,-50.,0.],1.)==[30.,0.,30.,0.]
    with pytest.raises(ValueError):assisted_collective([10.]*4,[float('nan'),0.,0.],.5)
    with pytest.raises(ValueError):assisted_collective([10.]*4,[0.,0.,0.],1.1)


def test_unvalidated_assistance_only_observes_pilot_commands():
    import mujoco as mj
    import numpy as np
    from vtx.aircraft import Aircraft
    p=Aircraft(rpm=1200,fuel_kg=10,engine_power_limit_kw=300)
    p.spawn(0,0,20);p.stability_assist=1.;p.pitch[:]=10.
    p.set_command(dict(engine=1.,collective_deg=[10.]*4,tilt_deg=[[0.,0.]]*4,cabin_deg=[0.,0.,0.],cabin_level=True))
    p.data.qvel[3]=.2
    mj.mj_forward(p.model,p.data)
    p.step()
    assert p.assisted_collective_deg!=[10.]*4
    np.testing.assert_allclose(p.pitch,[10.]*4)
    assert p.physical_snapshot()['assistance_applied'] is False


@pytest.mark.parametrize('level',[0.,.5,1.])
def test_operator_adjusts_only_shadow_level(monkeypatch,level):
    import asyncio
    import vtx.live_server as server
    lab=server.Laboratory()
    monkeypatch.setattr(server,'lab',lab)
    asyncio.run(server.operator({'stability_assist':level}))
    assert lab.aircraft.stability_assist==level
    assert lab.sensor_observation()['assistance_applied'] is False


def test_shadow_levels_do_not_change_simulated_flight_state():
    import mujoco as mj
    import numpy as np
    from vtx.aircraft import Aircraft
    states=[]
    for level in (0.,.5,1.):
        p=Aircraft(rpm=1200,fuel_kg=10,engine_power_limit_kw=300)
        p.spawn(0,0,20);p.stability_assist=level;p.pitch[:]=10.
        p.set_command(dict(engine=1.,collective_deg=[10.]*4,tilt_deg=[[0.,0.]]*4,cabin_deg=[0.,0.,0.],cabin_level=True))
        p.data.qvel[3]=.2
        mj.mj_forward(p.model,p.data)
        for _ in range(80):p.step()
        states.append(p.data.qpos.copy())
    np.testing.assert_allclose(states[0],states[1],rtol=0,atol=1e-12)
    np.testing.assert_allclose(states[0],states[2],rtol=0,atol=1e-12)
