import json
import sys
import pytest
from tools.phantom import phantom_persistent_pilot as bridge


def test_bridge_holds_commands_and_respects_manual_and_owned_sessions(tmp_path,monkeypatch):
    controls=tmp_path/'controls.json'
    controls.write_text(json.dumps({'armed':True,'arm_run_id':'r1','serial':1,'reason':'Test','command':{'collective':.2}}))
    views=iter([{'run_id':'r1','active':True,'authority':'manual'},
                {'run_id':'r1','active':True,'authority':'colin','pilot_owner':'another','pilot_epoch':1},
                {'run_id':'r1','active':True,'authority':'colin'},
                {'run_id':'r1','active':True,'authority':'colin'}])
    actions=[]
    def call(path,payload=None):
        if path=='/api/view':return next(views)
        if path=='/api/observe':return {'observation_id':7,'t_s':1}
        if path=='/api/action':actions.append(payload);return {'sequence':len(actions)}
        raise AssertionError(path)
    count=[0]
    def pause(_):
        count[0]+=1
        if count[0]==4:raise KeyboardInterrupt
    monkeypatch.setattr(bridge,'call',call);monkeypatch.setattr(bridge.time,'sleep',pause)
    monkeypatch.setattr(sys,'argv',['pilot','--controls',str(controls)])
    with pytest.raises(KeyboardInterrupt):bridge.main()
    assert len(actions)==1 and actions[0]['authority']=='colin' and actions[0]['collective']==.2
