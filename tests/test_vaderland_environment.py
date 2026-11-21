"""The new survey uses the same aircraft, with its own world and fleet identity."""
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from vtx import live_server
from vtx.aircraft import Aircraft
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


def vehicle_xml(plant):
    root=ET.fromstring(plant.xml)
    asset=root.find('asset')
    asset.remove(asset.find('hfield'))
    for mesh in list(asset.findall('mesh')):
        if mesh.get('name','').startswith('scenery-'):asset.remove(mesh)
    scenery=root.find('worldbody')
    for body in list(scenery.findall('body')):
        if body.get('mocap')=='true' and body.get('name','').startswith('environment-'):scenery.remove(body)
    size=root.find('size')
    if size is not None and 'nuserdata' in size.attrib:
        del size.attrib['nuserdata']
        if not size.attrib:root.remove(size)
    for geom in list(scenery.findall('geom')):
        scenery.remove(geom)
    return ET.tostring(root)


@pytest.mark.parametrize('variant',['r6','phantom-a10c','phantom-a10d'])
@pytest.mark.parametrize('key',['vaderland-05','vaderland-08','vaderland-10','vaderland-11','vaderland-12','vaderland-13','vaderland-14','vaderland-15','vaderland-16','vaderland-17'])
def test_vehicle_definition_is_identical_in_new_scenery(variant,key):
    def aircraft(world):
        if variant=='r6':
            return Aircraft(world,airframe_variant=variant)
        return PhantomAircraft(world,variant,start_configuration='road')
    original=aircraft(make_world('airport'))
    expanded=aircraft(make_world(key))
    assert vehicle_xml(original)==vehicle_xml(expanded)


def test_versions_keep_approaches_and_the_original_world():
    original=make_world('airport')
    assert original.environment_key=='airport' and original.version=='6' and original.n==401
    pins=set()
    for number in range(1,18):
        w=make_world(f'vaderland-{number:02}')
        assert w.half==8000 and w.runway==original.runway
        axis=np.linspace(-w.half,w.half,w.n)
        assert not np.any(w.heights[np.ix_(abs(axis)<=500,abs(axis)>=3900)])
        assert not np.any(w.heights[abs(axis)<=w.runway['width']/2])
        pins.add(live_server.world_fingerprint(w))
    assert len(pins)==17
    assert live_server.world_fingerprint(make_world('vaderland-05'))=='1db17fec0eebea557d892569c47e546e3fbb9a59e919822390762606c7d05c0f'
    assert live_server.world_fingerprint(make_world('vaderland-08'))=='812c79369610b8dfce07ff0aecb34095dd2aecf22f903b75f74f0bfb49779a62'
    assert w.heights.max() < w.height_scale_m


def test_bridge_footprint_is_supported_above_the_channel():
    from vtx.world import MapPoint
    w=make_world('vaderland-08')
    deck=live_server.landing_support(w,MapPoint(x_m=-5174,y_m=3200),'departure','phantom-a10c')
    assert deck.valid and deck.terrain_z_m==183.4
    assert w.harbour_overlaps(-5170,3155,4.1)


def test_fleet_worker_publishes_the_frozen_solver_surface(tmp_path):
    from vtx.harbour_session import HarbourSession
    w=make_world('vaderland-08')
    fleet=HarbourSession(tmp_path,w.environment_key)
    try:
        fleet.act(w,'activate',{})
        first=fleet.status(w)
        second=fleet.status(w)
        assert first['t_s']==second['t_s']==0
        assert first['water_surface']==second['water_surface']
        assert first['water_surface']['samples']==49 and len(first['water_surface']['patches'])==2
    finally:
        fleet.close()


@pytest.mark.parametrize('key',['vaderland-05','vaderland-08','vaderland-09','vaderland-10','vaderland-11','vaderland-12','vaderland-13','vaderland-14','vaderland-15','vaderland-16','vaderland-17'])
def test_new_flight_restores_only_in_its_own_environment(tmp_path,key):
    lab=live_server.Laboratory(data_root=tmp_path)
    lab.start(live_server.Mission(environment=key,airframe_variant='phantom-a10c',
        departure=(-3885.,0.),destination=(300.,0.),phantom={'start_configuration':'road'}))
    for _ in range(8):
        lab.integrate()
    lab.checkpoint(force=True)
    run=lab.run_id
    position=lab.aircraft.data.qpos.copy()
    assert lab.harbour_for('airport').directory != lab.harbour_session.directory
    assert lab.harbour_session.environment==key
    lab.aircraft.step_log.close()
    lab.audit_file.close()
    restored=live_server.Laboratory(data_root=tmp_path)
    assert restored.active and restored.paused and restored.run_id==run
    assert restored.world.environment_key==restored.flight_world.environment_key==key
    np.testing.assert_allclose(restored.aircraft.data.qpos,position,atol=1e-10)
    restored.stop('End isolated world recovery test')


def test_road_and_marine_gangway_share_both_ends_and_the_deck_height():
    from vtx.harbour_water import HarbourWorld
    w=make_world('vaderland-10')
    roads={r['name']:r for r in w.vaderland['routes']}
    access=roads['Ricochet gangway']
    assert roads['Airport landing road']['points'][-1]==access['points'][0]==w.harbour['accessPath'][-1]
    assert w.terrain_z(*access['points'][0])==pytest.approx(access['deck_z_m'])
    marine={s['id']:s for s in HarbourWorld(w).structures}
    air={o['id']:o for o in w.obstacles}
    for name in w.vaderland['landing']['chart_structures']:
        a=air['deck-'+name];m=marine[name]
        np.testing.assert_allclose(a['center'],m['center'])
        half=np.array(m['half_extents'])
        if abs(round(m['yaw_deg']))==90:half=half[[1,0,2]]
        np.testing.assert_allclose(a['half'],half)


def test_market_people_follow_the_same_clock_without_advancing_the_vehicle():
    world=make_world('vaderland-16')
    plant=PhantomAircraft(world,'phantom-a10c',start_configuration='road')
    plant.spawn(-3885,0,0)
    group=world.vaderland['quarter']['people']
    first=group[0]
    body=plant.model.body('environment-'+first['name']).id
    index=plant.model.body_mocapid[body]
    config=plant.data.qpos.copy()
    for t in [0,2.5,11.,0.]:
        plant.scenery.apply(plant.data,scene_time=t)
        phase=first['phase']+2*np.pi*t/first['period_s']
        expected=np.array(first['center'])+np.array(first['a'])*np.cos(phase)+np.array(first['b'])*np.sin(phase)
        np.testing.assert_allclose(plant.data.mocap_pos[index,:2],expected,atol=1e-7)
        np.testing.assert_array_equal(plant.data.qpos,config)
        assert plant.data.time==0 and plant.model.body_mass[body]==0


def test_market_chart_agrees_at_shores_and_between_grid_lines():
    from vtx.vaderland import Vaderland

    world = make_world('vaderland-16')
    ox, oy = world.harbour['origin']
    starts = np.column_stack((ox + world._shore[:, 0], oy - world._shore[:, 1]))
    ends = np.column_stack((ox + world._ends[:, 0], oy - world._ends[:, 1]))
    rng = np.random.default_rng(41031)
    probes = [rng.uniform(-8000, 8000, (12000, 2))]
    for fraction in (0., .25, .5, .75):
        edge = starts + fraction * (ends - starts)
        probes.extend([edge, edge + [1e-8, 0], edge - [0, 1e-8]])
    x, y = np.concatenate(probes).T
    np.testing.assert_array_equal(world.harbour_water_mask(x,y), Vaderland.harbour_water_mask(world,x,y))


def test_market_shallow_water_reuses_only_bitwise_identical_cell_neighbourhoods():
    from copy import deepcopy
    from dataclasses import replace
    from types import SimpleNamespace

    from vtx.water.repeated_faces import RepeatedFaces
    from vtx.water.shallow_water import ShallowWaterSolver

    world = SimpleNamespace(half=500, terrain_z_array=lambda x, y: np.full_like(x, -3.))
    baseline = ShallowWaterSolver(world, nx=227, ny=199)
    local = deepcopy(baseline)
    advance = RepeatedFaces(local)
    for step in range(14):
        for field in (baseline, local):
            if step == 2:
                field.hu[[0, 31, 32, 64, 128, 198], [0, 31, 63, 31, 96, 226]] = .5
                field.bed[91, 130] += .25
            if step == 6:
                field.reset(water_level_m=.3)
            if step == 8:
                field.config = replace(field.config, wind_speed_mps=2., current_speed_mps=.1)
        dt = .041 if step < 9 else .039
        baseline._advance_substep(dt)
        advance(dt)
        for name in ('h','hu','hv'):
            a, b = getattr(baseline,name), getattr(local,name)
            np.testing.assert_array_equal(a.view(np.uint64), b.view(np.uint64))


def test_harbour_worker_water_strips_preserve_the_stock_stencil():
    from concurrent.futures import ThreadPoolExecutor
    from copy import deepcopy
    from types import SimpleNamespace

    from vtx.harbour_session import _advance_water_in_strips
    from vtx.water.shallow_water import ShallowWaterSolver

    rng = np.random.default_rng(33)
    world = SimpleNamespace(half=500, terrain_z_array=lambda x, y: 2 * np.sin(x / 50))
    stock = ShallowWaterSolver(world, nx=97, ny=151)
    stock.h *= rng.uniform(0.5, 1.5, size=stock.h.shape)
    stock.hu[:] = rng.normal(0, 0.1, size=stock.h.shape)
    stock.hv[:] = rng.normal(0, 0.1, size=stock.h.shape)
    strips = deepcopy(stock)

    with ThreadPoolExecutor(max_workers=2) as executor:
        for _ in range(4):
            stock._advance_substep(0.05)
            _advance_water_in_strips(ShallowWaterSolver._advance_substep, strips, 0.05, executor=executor)
            for name in ('h', 'hu', 'hv'):
                expected = getattr(stock, name).view(np.uint64)
                actual = getattr(strips, name).view(np.uint64)
                np.testing.assert_array_equal(actual, expected)


def test_timing_rejects_overflight_and_requires_the_ordered_return():
    from vtx.course_timing import CourseTiming
    gates=[dict(center=[x,0,0],normal=[1,0],width_m=12) for x in (0,20)]
    clock=CourseTiming([dict(name='circuit',gates=gates)])
    for t,position in [(0,[-1,0,8]),(.1,[1,0,8]),(.2,[-1,0,0]),(.3,[1,0,0]),
                       (.6,[19,0,0]),(.8,[21,0,0]),(1.1,[-1,0,0]),(1.3,[1,0,0])]:
        clock.sample(t,position)
    assert clock.runs['circuit']['laps']==1
    assert clock.runs['circuit']['last']==pytest.approx(.95)
