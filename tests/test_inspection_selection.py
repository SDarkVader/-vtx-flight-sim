"""An explicit idle aircraft and environment survive a process restart."""
import asyncio
import json
import pytest
from fastapi import HTTPException
from vtx import live_server as server


def test_explicit_inspection_selection_survives_restart(tmp_path, monkeypatch):
    lab=server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server,'lab',lab)
    assert lab.view()['inspection_selection_known'] is False
    with pytest.raises(HTTPException,match='Select an aircraft explicitly'):
        asyncio.run(server.set_environment({'environment':'sandbox'}))
    variant='phantom-a10c-vtol-20261112'
    selected=asyncio.run(server.model_preview({'environment':'sandbox','airframe_variant':variant,
        'start_configuration':'vtol','departure':[-700,0]}))
    model=selected['rendering_truth']['provenance']['model_xml_sha256']
    saved=lab.inspection_path.read_bytes()
    restarted=server.Laboratory(data_root=tmp_path)
    assert restarted.inspection_selection_known and not restarted.recovery_blocked
    assert restarted.aircraft.variant==variant and restarted.world.environment_key=='sandbox'
    assert restarted.aircraft.provenance['model_xml_sha256']==model
    assert restarted.inspection_path.read_bytes()==saved


def test_incompatible_inspection_selection_is_retained(tmp_path, monkeypatch):
    lab=server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server,'lab',lab)
    asyncio.run(server.model_preview({'airframe_variant':'r6','departure':[-700,0]}))
    state=json.loads(lab.inspection_path.read_text(encoding='utf-8'))
    state['runtime_source_sha256']='f'*64
    lab.inspection_path.write_text(json.dumps(state),encoding='utf-8')
    before=lab.inspection_path.read_bytes()
    restarted=server.Laboratory(data_root=tmp_path)
    assert restarted.recovery_blocked and not restarted.inspection_selection_known
    assert 'requires runtime' in restarted.error
    assert restarted.inspection_path.read_bytes()==before
