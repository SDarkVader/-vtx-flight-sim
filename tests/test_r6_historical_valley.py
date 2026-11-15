"""Historical R6 world reconstruction; no live simulator or original data writes."""
import hashlib
import json

import numpy as np
import pytest

from vtx.aircraft import Aircraft
from vtx.mission_selection import MapPoint
from vtx.r6_historical_valley import R6HistoricalValley, R6_HISTORICAL_VARIANT, R6_HISTORICAL_ENVIRONMENT
from vtx.world import SandboxWorld, make_world, resolve_environment_key
import asyncio
from vtx import live_server as server


def test_recovered_world_matches_preserved_historical_data():
    world=R6HistoricalValley()
    heights=np.ascontiguousarray(world.heights,dtype='<f8').tobytes()
    obstacles=json.dumps(world.obstacles,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    assert hashlib.sha256(heights).hexdigest()=='de71fbb67da06357b1f92bd2fdc6c78a6c66f22cb06d3553382bd271653bb32e'
    assert hashlib.sha256(obstacles).hexdigest()=='d2403b2dad7eee42c6b9d7a737b755c0d2464ddde2074651b69e8a004f6d9776'
    assert len(world.obstacles)==38 and world.half==500 and world.n==101
    assert world.water=={'x':-265.,'y':30.,'half_x':28.,'half_y':80.}
    assert world.terrain_z(300,0)==pytest.approx(12.179183898472647)
    assert world.validate(MapPoint(0,0),'departure').valid
    later=SandboxWorld()
    assert (world.id,world.version)==(later.id,later.version)
    assert world.environment_key!=later.environment_key and world.terrain_z(300,0)!=later.terrain_z(300,0)
    # The recorded generic id still denotes the later sandbox; the historical
    # world is reached only through its distinct explicit key.
    assert resolve_environment_key('stage1-valley')=='sandbox'
    assert isinstance(make_world(R6_HISTORICAL_ENVIRONMENT),R6HistoricalValley)


def test_historical_xml_and_heightfield_are_reproducible_without_changing_default_floor():
    world=R6HistoricalValley()
    options=dict(gear_variant='critical-damping-proposal',rpm=1200.,fuel_kg=10.,airframe_variant='r6',
                 engine_power_limit_kw=300.,atmosphere_model='constant',wind_world_mps=[0,0,0])
    current=Aircraft(world,**options)
    assert 'name="boundary_floor"' in current.xml
    # The explicitly derived, unpromoted candidate retains the original
    # no-boundary-floor geometry while standard R6 remains unchanged.
    options['airframe_variant']=R6_HISTORICAL_VARIANT
    candidate=Aircraft(world,**options)
    assert 'name="boundary_floor"' not in candidate.xml
    assert candidate.provenance['model_xml_sha256']=='d5b83de425ad8da24e128faafaff399dd3e457474a2dabb7bbf4165c56220d16'
    hfield=np.ascontiguousarray(candidate.model.hfield_data,dtype='<f4').tobytes()
    assert hashlib.sha256(hfield).hexdigest()=='ad25be0331e7b7a3a7c8e728172a027e4f1ab56118e4ecfc0921c32f8cfa10af'
    assert candidate.provenance['render_asset']=='/assets/airframe-r6.glb'
    assert candidate.provenance['flight_revision']['evidence'][0]['run_id']=='20261103T125202-92636c'
    assert 'unavailable' in candidate.provenance['flight_revision']['limitations']
    with pytest.raises(ValueError,match='requires its explicitly identified'):
        Aircraft(SandboxWorld(),**options)


def test_candidate_requires_explicit_historical_environment_and_keeps_identity(tmp_path,monkeypatch):
    lab=server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server,'lab',lab)
    original_world,original_aircraft=lab.world,lab.aircraft
    with pytest.raises(ValueError,match='requires its explicitly identified'):
        lab.start(server.Mission(airframe_variant=R6_HISTORICAL_VARIANT,environment='sandbox'))
    assert not lab.active
    assert lab.world is original_world and lab.aircraft is original_aircraft
    view=asyncio.run(server.model_preview({'airframe_variant':R6_HISTORICAL_VARIANT,
        'environment':R6_HISTORICAL_ENVIRONMENT,'departure':[13.7,-28.4]}))
    assert view['environment']['key']==R6_HISTORICAL_ENVIRONMENT
    assert view['observation']['configuration']['airframe_variant']==R6_HISTORICAL_VARIANT
    assert view['rendering_truth']['provenance']['flight_revision']['evidence'][0]['run_id']=='20261103T125202-92636c'
    lab.start(server.Mission(airframe_variant=R6_HISTORICAL_VARIANT,environment=R6_HISTORICAL_ENVIRONMENT,
        departure=[13.7,-28.4],destination=[-45,18]))
    assert lab.aircraft.provenance['model_xml_sha256']=='d5b83de425ad8da24e128faafaff399dd3e457474a2dabb7bbf4165c56220d16'
    lab.stop('End isolated historical candidate test')


def test_historical_pilot_record_is_accessible():
    response=asyncio.run(server.r6_historical_pilot_record())
    assert response.path.name=='PILOT_RECORD.md'
    assert '20261103T125202-92636c' in response.path.read_text(encoding='utf-8')
