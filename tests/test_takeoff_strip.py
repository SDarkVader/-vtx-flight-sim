from vtx.world import TestWorld


def test_eastbound_takeoff_strip_is_flat_and_clear():
    world = TestWorld()
    assert world.half >= 3900
    assert all(abs(world.terrain_z(x, y)) < 1e-8
               for x in range(0, 3901, 10) for y in (-20, 0, 20))
    for obstacle in world.obstacles:
        x, y, _ = obstacle['center']
        hx, hy, _ = obstacle['half']
        assert not (x + hx >= 0 and x - hx <= 3900 and abs(y) <= hy + 8)
