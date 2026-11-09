"""An older inspection request cannot replace a later aircraft selection."""
import asyncio
import threading
import pytest
from fastapi import HTTPException
import vtx.live_server as server


def test_late_preview_cannot_replace_newer_selection(tmp_path, monkeypatch):
    lab = server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server, 'lab', lab)
    original = server.phantom_live.make_aircraft
    first_started = threading.Event()
    release_first = threading.Event()

    def delayed(world, request, **kwargs):
        if request.airframe_variant == 'phantom-a10b':
            first_started.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError('Preview test did not release first request')
        return original(world, request, **kwargs)

    monkeypatch.setattr(server.phantom_live, 'make_aircraft', delayed)
    async def run():
        first = asyncio.create_task(server.model_preview({'airframe_variant': 'phantom-a10b', 'departure': [0, 0]}))
        assert await asyncio.to_thread(first_started.wait, 10)
        newer = await server.model_preview({'airframe_variant': 'phantom-fx', 'departure': [0, 0]})
        assert newer['observation']['configuration']['airframe_variant'] == 'phantom-fx'
        release_first.set()
        with pytest.raises(HTTPException) as error:
            await first
        assert error.value.status_code == 409
        assert lab.aircraft.variant == 'phantom-fx'
    try:
        asyncio.run(run())
    finally:
        release_first.set()
