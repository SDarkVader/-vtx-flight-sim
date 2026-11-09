import math
import numpy as np
import pytest
from vtx.aircraft import DT
from vtx.phantom.params import Params
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.surface_aero import SurfaceAero
from vtx.world import TestWorld as World

P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}

def test_both_canards_track_independent_commands_and_drs_tracks_pitch():
    world = World()
    a = PhantomAircraft(world, 'phantom', overrides=P6)
    a.spawn(0, 0, world.surface_z(0, 0))
    a.set_command(dict(canard_fold='deployed', canard_pitch_deg=[12, -8], stability_mode='off', pitch=0.5))
    for _ in range(int(4 / DT)): a.step()
    left = math.degrees(a.joint('canard_left')[0]); right = math.degrees(a.joint('canard_right')[0])
    assert left > right + 8
    assert a.physical_snapshot()['phantom']['drs_deg'] == pytest.approx(13.5, abs=1)
    state = a.checkpoint_state()
    b = PhantomAircraft(world, 'phantom', overrides=P6)
    b.restore_state(state)
    assert b.stab_te_up == pytest.approx(a.stab_te_up)

def test_drs_is_physical_surface_and_deflection_changes_aerodynamics():
    aero = SurfaceAero(Params('phantom', P6))
    assert any(x.name == 'drs_stab' for x in aero.surfaces)
    state = dict(wing_frac=dict(left=0., right=0.), wing_locked=dict(left=False,right=False), flap=dict(left=0.,right=0.), aileron=dict(left=0.,right=0.), canard_pitch=dict(left=0.,right=0.), canard_deployed=dict(left=False,right=False))
    results=[]
    for angle in (6., 55.):
        state['stab_te_up']=math.radians(angle)
        result=aero.compute(np.array([40.,0.,0.]),np.zeros(3),np.zeros(3),state)
        results.append(next(x for x in result['surfaces'] if x['name']=='drs_stab')['force_n'])
    assert not np.allclose(results[0], results[1])
