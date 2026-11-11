"""Aircraft identity pin (inputs/aircraft_identity.json) and the pilot command endpoint."""
import asyncio, json

import pytest
from fastapi import HTTPException

import vtx.live_server as server
from vtx.live_server import Laboratory, Mission, PilotCommand, pilot_command
from vtx.phantom import identity
from vtx.phantom.params import PARAMETER_FILE, Params
from vtx.phantom.plant import PhantomAircraft
from vtx.pilot_command import parse
from vtx.world import TestWorld

A10B = '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'


def test_a10b_pin_matches_the_built_aircraft():
    a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road')
    i = identity.verify(a)
    assert i['verified'] and not i['mismatches'] and i['config_sha256'] == A10B
    assert i['render_asset'] == '/assets/phantom-a10b-visual.glb' and i['render_asset_sha256'] == identity.pins()['phantom-a10b']['render_asset_sha256']
    # historical variants are preserved and simply not pinned
    h = identity.verify(PhantomAircraft(TestWorld(), 'phantom-fx', start_configuration='road'))
    assert h['pinned'] is False and h['verified'] is None


def test_parameter_file_identity_ignores_line_endings(tmp_path):
    crlf = tmp_path / 'p.json'
    crlf.write_bytes(PARAMETER_FILE.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    assert Params('phantom-a10b', path=crlf).file_sha256 == Params('phantom-a10b').file_sha256 == identity.pins()['phantom-a10b']['parameter_file_sha256']


def _lab(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path)); monkeypatch.setattr(server, 'ROOT', tmp_path)
    lab = Laboratory(); monkeypatch.setattr(server, 'lab', lab)
    return lab


def _mission(lab, **phantom):
    dep = list(lab.world.default_departure)
    return Mission(airframe_variant='phantom-a10b', departure=dep, destination=[dep[0] + 60, dep[1]], phantom=dict(start_configuration='vtol', **phantom))


def test_flight_is_refused_when_the_visual_or_physics_does_not_match_the_pin(tmp_path, monkeypatch):
    lab = _lab(tmp_path, monkeypatch)
    real = identity.pins()
    monkeypatch.setattr(identity, 'pins', lambda: {**real, 'phantom-a10b': {**real['phantom-a10b'], 'render_asset_sha256': '0' * 64}})
    with pytest.raises(HTTPException) as e:
        lab.start(_mission(lab))
    assert e.value.status_code == 409 and 'render_asset_sha256' in e.value.detail and not lab.active
    monkeypatch.setattr(identity, 'pins', lambda: {**real, 'phantom-a10b': {**real['phantom-a10b'], 'config_sha256': 'f' * 64}})
    with pytest.raises(HTTPException) as e:
        lab.start(_mission(lab))
    assert 'config_sha256' in e.value.detail and A10B in e.value.detail


def test_flight_records_its_identity_and_command_reaches_the_plant(tmp_path, monkeypatch):
    lab = _lab(tmp_path, monkeypatch)
    lab.start(_mission(lab))
    rec = json.loads((lab.log_path / 'aircraft_identity.json').read_text())
    assert rec['verified'] and rec['config_sha256'] == A10B
    assert lab.sensor_observation()['configuration']['identity']['status'] == 'verified'

    async def run():
        async def clock():
            while lab.active:
                lab.integrate(); await asyncio.sleep(0)
        task = asyncio.create_task(clock())
        try:
            up = await pilot_command(PilotCommand(text='okay pilot, take us up please', source='text'))
            risky = await pilot_command(PilotCommand(text='retract the legs'))
            junk = await pilot_command(PilotCommand(text='make me a sandwich'))
            lab.authority = 'colin'
            from vtx.live_server import parse_action
            with pytest.raises(HTTPException):
                lab.accept_action(parse_action(dict(schema='phantom-fbw-1', authority='manual', reason='wrong seat', collective=0.2)))
            lab.authority = 'manual'
            return up, risky, junk
        finally:
            lab.active = False; await task
    up, risky, junk = asyncio.run(run())
    assert up['accepted'] and up['executed'] and up['intent'] == 'vtol_takeoff' and up['applied_latency_ms'] is not None
    assert lab.aircraft.fcc.cmd['vertical_speed_m_s'] == 1.5 and lab.aircraft.fcc.cmd['stability_mode'] == 'attitude_vs'
    assert risky['needs_confirmation'] and not risky['accepted'] and not risky['executed']
    assert junk['intent'] == 'unknown' and not junk['understood'] and not junk['executed']


def test_interpreter_is_bounded_and_refuses_what_it_cannot_do():
    assert parse('take us up', {'pod_tilt_deg': [0, 0, 0, 0]})['intent'] == 'refused'          # pods not vertical
    assert parse('boost two hundred percent')['patch'] == {'booster_throttle': [1.0, 1.0]}       # clamped to the schema range
    assert parse('hard left')['patch'] == {'yaw': -1.0} and parse('turn right')['patch'] == {'yaw': 0.5}
    assert parse('stow the wings')['risky'] and parse('engine off')['risky']
