import mujoco as mj
import numpy as np

from vtx.phantom.terrain_ray import GROUND_GROUP, TerrainRay


def test_shallow_ray_retains_nearest_scenery_and_native_terrain():
    model = mj.MjModel.from_xml_string("""
        <mujoco>
          <asset><hfield name="ground" nrow="9" ncol="9" size="80 80 20 2"/></asset>
          <worldbody>
            <geom name="terrain" type="hfield" hfield="ground"/>
            <geom name="fixed" type="box" pos="-8 -6 2" size="2 4 2"/>
            <body name="moving" mocap="true" pos="-24 -11.5 2">
              <geom name="moved" type="box" size="2 3 2"/>
            </body>
          </worldbody>
        </mujoco>
    """)
    # A finite ramp in the exact native heightfield representation.
    model.hfield_data[:] = np.tile([0, 0, 0, 0, 0, .2, .4, .6, .8], 9)
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    query = TerrainRay.build(model, data, model.geom("terrain").id)
    assert query is not None
    point = np.array([-40., -17., 2.])
    vec = np.array([.9, .31, -.014])
    assert query.suitable(point, vec)
    geom = np.empty(1, dtype=np.int32)

    def expected_hit(name, p):
        dist = mj.mj_ray(model, data, p, vec, GROUND_GROUP, True, -1, geom)
        assert geom[0] == model.geom(name).id
        assert query.hit(p, vec) == (dist, geom[0])

    expected_hit("moved", point)
    data.mocap_pos[0, 1] = 0
    mj.mj_forward(model, data)
    expected_hit("fixed", point)
    model.geom_rgba[model.geom("fixed").id, 3] = 0
    expected_hit("terrain", point)
    assert query.hit(np.array([-80., -17., 2.]), vec) is None
    assert query.hit(np.array([-40., -40., 2.]), np.array([.7, .7, -.014])) is None
