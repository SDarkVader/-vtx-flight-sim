import asyncio

import pytest

from tools import vtx_pilot_mcp as pilot
from vtx import live_server


def test_pilot_read_endpoints_do_not_request_visual_truth(tmp_path, monkeypatch):
    lab = live_server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(live_server, 'lab', lab)
    monkeypatch.setattr(lab.aircraft, 'physical_snapshot', lambda: pytest.fail('pilot requested renderer state'))
    status = asyncio.run(live_server.pilot_status())
    reading = asyncio.run(live_server.observe())
    assert status['run_id'] == reading['run_id']
    assert reading['gnss_xy_m'] and reading['observation_id']
    assert status['airframe_variant'] == reading['configuration']['airframe_variant']
    for packet in (status, reading):
        assert {'rendering_truth', 'harbour', 'chart', 'track', 'camera'}.isdisjoint(packet)


def test_mcp_uses_the_actual_observed_sample_and_current_seat(monkeypatch):
    state = dict(run_id='a', active=True, paused=False, authority='colin',
                 pilot_owner=None, pending_pilot=pilot.PILOT_ID, pilot_epoch=3)
    monkeypatch.setattr(pilot, 'seat', dict(run_id='a', epoch=3))
    monkeypatch.setattr(pilot, 'last_instruments', None)
    monkeypatch.setattr(pilot.time, 'sleep', lambda _: None)
    latest = iter([14, 15])
    actions = []

    def call(path, payload=None):
        if path == '/api/pilot/status':
            return dict(state)
        if path == '/api/observe':
            return dict(run_id='a', observation_id=next(latest), gnss_xy_m=[20, 30])
        if path == '/api/action':
            actions.append(payload)
            return dict(sequence=1)
        pytest.fail(f'Unexpected pilot endpoint {path}')

    monkeypatch.setattr(pilot, 'call', call)
    assert 'vtx_instruct' not in pilot.TOOLS
    request = dict(run_id='a', observation_id=14, controls={'collective': .3}, reason='Respond to altitude reading')
    with pytest.raises(ValueError):
        pilot.command(request)
    assert pilot.observe({})['observation_id'] == 14
    for invalid in (dict(observation_id=13), dict(run_id='old'), dict(controls={'authority':'manual'})):
        with pytest.raises(ValueError):
            pilot.command({**request, **invalid})
    state['authority'] = 'manual'
    with pytest.raises(RuntimeError):
        pilot.command(request)
    state['authority'] = 'colin'
    result = pilot.command(request)
    assert [a['observation_id'] for a in actions] == [14]
    assert result['telemetry_before']['observation_id'] == 14
    assert result['telemetry_after']['observation_id'] == 15
    with pytest.raises(ValueError):
        pilot.command(request)
