import json
import pytest
from vtx.pilot_exchange import record_exchange, sha256_bytes

def test_record_and_redact(tmp_path):
    path = record_exchange(tmp_path, flight_id='flight_1', decision_id='decision_1',
        observation_id=7, sim_time_s=1.25,
        request_payload={'messages':[{'role':'user','content':'hold'}], 'api_key':'sensitive'},
        response_payload={'text':'Holding', 'authorization':'Bearer sensitive'},
        raw_request_sha256=sha256_bytes(b'original'))
    row = json.loads(path.read_text())
    assert row['request_payload']['messages'][0]['content'] == 'hold'
    assert row['request_payload']['api_key'] == '[REDACTED]'
    assert row['response_payload']['authorization'] == '[REDACTED]'
    assert row['observation_id'] == 7
    assert row['raw_request_sha256'] == sha256_bytes(b'original')

def test_no_overwrite(tmp_path):
    args = dict(flight_id='flight_1', decision_id='decision_1',
                request_payload={}, response_payload={})
    path = record_exchange(tmp_path, **args)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        record_exchange(tmp_path, **args)
    assert path.read_bytes() == before

@pytest.mark.parametrize('bad', ['../escape', 'a/b', '', 'space here'])
def test_bad_id(tmp_path, bad):
    with pytest.raises(ValueError):
        record_exchange(tmp_path, flight_id=bad, decision_id='one',
                        request_payload={}, response_payload={})

def test_nonfinite(tmp_path):
    with pytest.raises(ValueError):
        record_exchange(tmp_path, flight_id='one', decision_id='two',
                        request_payload={'bad':float('nan')}, response_payload={})
