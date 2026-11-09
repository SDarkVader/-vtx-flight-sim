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
