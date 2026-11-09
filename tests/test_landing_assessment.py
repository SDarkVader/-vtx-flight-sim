"""Landing evidence is independent of waypoint precision and does not stop physics."""
import json
import pytest
from vtx.live_server import Laboratory, Mission

@pytest.mark.parametrize('variant',['r6','phantom-fx'])
@pytest.mark.parametrize('tolerance,expected',[(None,'not_specified'),(2.,'missed'),(3.,'met')])
def test_supported_landing_off_waypoint_is_recorded_without_stopping(tmp_path,monkeypatch,variant,tolerance,expected):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path))
    lab=Laboratory();run=lab.start(Mission(airframe_variant=variant,departure=[0,0],destination=[30,20],landing_precision_m=tolerance))['run_id']
    try:
        lab.left_ground=True
        lab.aircraft.data.qpos[0:2]=[32.58,20]
        for _ in range(42):lab.update_landing_evidence(support=4,level=True,speed=.01,loaded=True)
        landing=lab.view()['landing_assessment']
        assert lab.active and lab.run_id==run
        assert landing['physical']=='supported_stable'
        assert landing['destination_distance_m']==pytest.approx(2.58)
        assert landing['precision']==expected
        rows=[json.loads(x) for x in (lab.log_path/'events.jsonl').read_text().splitlines()]
        assert sum(r['kind']=='supported_landing_observed' for r in rows)==1
        lab.checkpoint(force=True)
        if getattr(lab.aircraft,'is_phantom',False):lab.aircraft.step_log.close()
        lab.audit_file.close();lab.audit_file=None
        restored=Laboratory()
        assert restored.run_id==run and restored.active and restored.last_landing==landing
        assert restored.landing_recorded
        summary=restored.stop('End flight test')
        assert summary['outcome']=='landed' and summary['landing_assessment']==landing
    finally:
        if lab.audit_file:lab.stop('cleanup')

@pytest.mark.parametrize('support,level,speed,loaded,crashed',[(0,True,0,True,False),(3,False,0,True,False),(3,True,1,True,False),(3,True,0,False,False),(3,True,0,True,True)])
def test_touch_or_unsafe_state_is_not_stable_landing(tmp_path,monkeypatch,support,level,speed,loaded,crashed):
    monkeypatch.setenv('VTX_DATA_ROOT',str(tmp_path));lab=Laboratory();lab.start(Mission())
    try:
        lab.left_ground=True;lab.aircraft.data.qpos[:2]=lab.mission['destination'];lab.aircraft.crashed=crashed
        for _ in range(45):lab.update_landing_evidence(support=support,level=level,speed=speed,loaded=loaded)
        assert lab.last_landing is None and lab.settled_s==0 and lab.active
    finally:lab.stop('End test')
