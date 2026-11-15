"""Mid-air checkpoint recovery contracts; never touches the live server."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pytest

from vtx.live_server import Laboratory, Mission, normalize_saved_mission_request


def test_midair_restart_preserves_physics_and_requires_manual_resume():
    with TemporaryDirectory() as folder:
        root=Path(folder)
        with patch("vtx.live_server.ROOT",root):
            lab=Laboratory()
            lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18],
                              authority="colin",fuel_kg=20))
            p=lab.aircraft
            p.data.qpos[:3]=[13.7,-28.4,42.]
            p.data.qvel[:3]=[3.,-2.,5.]
            p.data.time=7.5
            p.engine_spool=.6
            p.fuel[:]=[4.9]*4
            p.pitch[:]=[6.,7.,8.,9.]
            p.governor.integral_nm=17.
            p.step_count=123
            lab.left_ground=True
            lab.checkpoint(force=True)
            run_id=lab.run_id
            lab.audit_file.close()
            lab.audit_file=None

            restored=Laboratory()
            assert restored.active
            assert restored.paused
            assert restored.run_id==run_id
            assert restored.authority=="colin"
            assert restored.left_ground
            assert restored.aircraft.data.time==pytest.approx(7.5)
            np.testing.assert_allclose(restored.aircraft.data.qpos[:3],[13.7,-28.4,42.])
            np.testing.assert_allclose(restored.aircraft.data.qvel[:3],[3.,-2.,5.])
            np.testing.assert_allclose(restored.aircraft.pitch,[6.,7.,8.,9.])
            assert restored.aircraft.engine_spool==pytest.approx(.6)
            assert restored.aircraft.governor.integral_nm==pytest.approx(17.)
            assert not (root/"evidence/flights"/run_id/"summary.json").exists()
            restored.stop("test completed")
            assert not (root/"pilot/live-flight-checkpoint.json").exists()


def test_explicit_stop_disables_recovery():
    with TemporaryDirectory() as folder:
        root=Path(folder)
        with patch("vtx.live_server.ROOT",root):
            lab=Laboratory()
            lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18]))
            lab.stop("operator stopped")
            recovered=Laboratory()
            assert not recovered.active


def test_stop_failure_retains_checkpoint_and_pauses(tmp_path, monkeypatch):
    import vtx.live_server as server
    lab=Laboratory(data_root=tmp_path)
    lab.start(Mission(airframe_variant='r6'))
    before=lab.checkpoint_path.read_bytes()
    # Failure after staging has written bytes must not publish a partial summary.
    with monkeypatch.context() as inject:
        def fail_sync(_fd):raise OSError('simulated disk failure')
        inject.setattr(server.os,'fsync',fail_sync)
        with pytest.raises(OSError,match='disk failure'):
            lab.stop('Test failed summary write')
    assert lab.active and lab.paused
    assert lab.checkpoint_path.read_bytes()==before
    assert not (lab.log_path/'summary.json').exists()
    lab.audit_file.close()
    recovered=Laboratory(data_root=tmp_path)
    assert recovered.active and recovered.paused and recovered.run_id==lab.run_id
    recovered.audit_file.close()


def test_existing_partial_summary_is_retained_and_checkpoint_is_not_resumed(tmp_path,monkeypatch):
    import asyncio
    import json
    import vtx.live_server as server
    lab=Laboratory(data_root=tmp_path)
    lab.start(Mission(airframe_variant='r6'))
    before=lab.checkpoint_path.read_bytes()
    summary=lab.log_path/'summary.json'
    summary.write_text('{partial',encoding='utf-8')
    # A pre-existing summary is evidence, even when malformed.
    with pytest.raises(FileExistsError):lab.stop('Must not replace evidence')
    assert summary.read_text(encoding='utf-8')=='{partial'
    assert lab.active and lab.paused and lab.checkpoint_path.read_bytes()==before
    lab.audit_file.close()
    recovered=Laboratory(data_root=tmp_path)
    assert not recovered.active and recovered.recovery_blocked
    assert 'summary' in recovered.error.lower() and 'retained for inspection' in recovered.error
    assert summary.read_text(encoding='utf-8')=='{partial'
    assert recovered.checkpoint_path.read_bytes()==before
    # One broken record must not hide all of the other retained flights.
    other=tmp_path/'evidence/flights/other-flight'
    other.mkdir()
    (other/'summary.json').write_text(json.dumps(dict(run_id='other-flight',outcome='landed')),encoding='utf-8')
    monkeypatch.setattr(server,'lab',recovered)
    rows=asyncio.run(server.runs())
    assert any(r['run_id']=='other-flight' and r['outcome']=='landed' for r in rows)
    assert any(r['run_id']==lab.run_id and r['outcome']=='summary unreadable; evidence retained' for r in rows)
    assert summary.read_text(encoding='utf-8')=='{partial'

def test_objective_survives_reconnect_and_checkpoint(tmp_path, monkeypatch):
    import asyncio
    import vtx.live_server as server
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    lab=Laboratory()
    monkeypatch.setattr(server,'lab',lab)
    run=lab.start(Mission(authority='colin'))['run_id']
    goal=asyncio.run(server.set_objective({'text':'Take us to the airport','run_id':run}))
    assert goal['status']=='pending' and lab.view()['objective']==goal
    with pytest.raises(server.HTTPException):
        asyncio.run(server.set_objective({'text':'Wrong flight','run_id':'stale'}))
    assert lab.objective==goal
    lab.audit_file.close();lab.audit_file=None
    recovered=Laboratory()
    assert recovered.run_id==run and recovered.objective==goal
    assert recovered.view()['objective']==goal
    monkeypatch.setattr(server,'lab',recovered)
    with pytest.raises(server.HTTPException):
        asyncio.run(server.complete_objective({'id':'stale'}))
    assert asyncio.run(server.complete_objective({'id':goal['id']}))['status']=='completed'
    recovered.stop('Objective recovery test complete')
