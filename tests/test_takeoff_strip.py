from vtx.world import TestWorld
import numpy as np

from vtx.aircraft import Aircraft
from vtx.phantom.plant import PhantomAircraft


def test_eastbound_takeoff_strip_is_flat_and_clear():
    world = TestWorld()
    assert world.half >= 3900
    assert all(abs(world.terrain_z(x, y)) < 1e-8
               for x in range(0, 3901, 10) for y in (-20, 0, 20))
    for obstacle in world.obstacles:
        x, y, _ = obstacle['center']
        hx, hy, _ = obstacle['half']
        assert not (x + hx >= 0 and x - hx <= 3900 and abs(y) <= hy + 8)


def test_main_airport_has_full_runway_and_level_return_approaches_with_outer_hills():
    world = TestWorld()
    runway = world.public()['runway']
    assert runway['x1'] - runway['x0'] == 7800.
    assert runway['x0'] == -3900. and runway['x1'] == 3900.
    assert world.default_departure == runway['default_start'] == [-700., 0.]
    # Include interpolated points near both world edges and the buffer edges.
    for x in (-3990., -3900., -700., 0., 3900., 3990.):
        for y in (-500., -499., -100., 0., 100., 499., 500.):
            assert world.terrain_z(x, y) == 0.
    assert world.terrain_z(2000., 520.) < 1.
    assert world.terrain_z(2000., 900.) > 20.
    assert world.terrain_z(-3500., -1500.) > 20.  # west of the harbour's graded banks
    assert world.terrain_z(3000., 3000.) > 20.
    for obstacle in world.obstacles:
        x, y, _ = obstacle['center']
        hx, hy, _ = obstacle['half']
        assert not (x + hx >= runway['x0'] and x - hx <= runway['x1']
                    and abs(y) <= hy + runway['width'] / 2.)


def test_runway_buffer_uses_the_same_heightfield_for_both_aircraft_families():
    world = TestWorld()
    for aircraft in (Aircraft(world, airframe_variant='r6'),
                     PhantomAircraft(world, 'phantom-a10c', start_configuration='road')):
        actual = np.asarray(aircraft.model.hfield_data).reshape(world.heights.shape)
        assert np.allclose(actual * 70., world.heights, rtol=1e-7, atol=1e-5)
        assert aircraft.model.opt.timestep == .0025
