import asyncio
import json
from starlette.requests import Request
from vtx import dashboard_site

def make_request(method, body=b""):
    async def receive():
        return {"type":"http.request", "body":body, "more_body":False}
    return Request({"type":"http", "method":method, "path":"/api/data",
                    "headers":[], "query_string":b"", "server":("localhost",80),
                    "scheme":"http"}, receive)

def test_dashboard_proxy_keeps_version_and_conflicts(monkeypatch):
    received = []
    def fake(method, body):
        received.append((method, body))
        if method == "GET":
            return 200, b'{"data":"{}", "version":4}'
        return 409, b'{"error":"Changed in another session. Reload before saving."}'
    monkeypatch.setattr(dashboard_site, "_transfer", fake)
    response = asyncio.run(dashboard_site.dashboard_data(make_request("GET")))
    assert response.status_code == 200 and json.loads(response.body)["version"] == 4
    response = asyncio.run(dashboard_site.dashboard_data(make_request("PUT", b'{"data":{},"version":3}')))
    assert response.status_code == 409 and b"another session" in response.body
    assert json.loads(received[-1][1])["version"] == 3

def test_dashboard_proxy_rejects_oversized_write(monkeypatch):
    def never(*args):
        raise AssertionError("unexpected upstream call")
    monkeypatch.setattr(dashboard_site, "_transfer", never)
    response = asyncio.run(dashboard_site.dashboard_data(make_request("PUT", b"x" * 1600001)))
    assert response.status_code == 413

def test_default_does_not_replace_existing_workspace(tmp_path):
    assert dashboard_site._new_workspace(tmp_path)
    for name in ('pilot/colin-memory.json', 'pilot/live-flight-checkpoint.json',
                 'evidence/flights', 'experiments'):
        root = tmp_path / name
        root.parent.mkdir(parents=True, exist_ok=True)
        root.touch()
        assert not dashboard_site._new_workspace(tmp_path)
        root.unlink()

def test_dashboard_local_fallback_when_upstream_unavailable(tmp_path, monkeypatch):
    import urllib.error
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path))
    def offline(*args, **kwargs):
        raise urllib.error.URLError('offline')
    monkeypatch.setattr(dashboard_site.urllib.request, 'urlopen', offline)
    res_get = asyncio.run(dashboard_site.dashboard_data(make_request("GET")))
    assert res_get.status_code == 200
    assert json.loads(res_get.body)["version"] == 1
    res_put = asyncio.run(dashboard_site.dashboard_data(make_request("PUT", b'{"data":{"notes":"test"},"version":1}')))
    assert res_put.status_code == 200
    assert json.loads(res_put.body)["version"] == 2
    res_get2 = asyncio.run(dashboard_site.dashboard_data(make_request("GET")))
    assert res_get2.status_code == 200
    assert json.loads(res_get2.body)["version"] == 2

def test_phantom_a10b_physics_endpoint_and_snapshot_linked():
    from vtx import live_server
    res = asyncio.run(live_server.phantom_physics('phantom-a10b'))
    assert res['variant'] == 'phantom-a10b'
    assert res['config_sha256'] == '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'
    assert res['characteristics']['variant'] == 'phantom-a10b'
    assert res['characteristics']['propulsion']['lift_fans']['thrust_max_each_n'] == 6552
