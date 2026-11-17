"""Offline ASGI checks; no cockpit, process or flight is started."""
import asyncio
import importlib.util
from pathlib import Path

from vtx.dashboard_site import app


spec = importlib.util.spec_from_file_location(
    "vtx_windows_launcher", Path(__file__).resolve().parents[1] / "scripts" / "launch_unified.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def request(application, path, method="GET", headers=()):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": list(headers),
        "server": ("test", 80), "client": ("test", 1), "root_path": "",
    }
    asyncio.run(application(scope, receive, send))
    start = next(message for message in messages if message["type"] == "http.response.start")
    return start["status"], dict(start["headers"])


def test_static_frontend_and_conditional_responses_revalidate():
    application = launcher.RevalidateFrontend(app)
    for path in ("/", "/app.js", "/vtx-env/airfield.js", "/style.css"):
        status, headers = request(application, path)
        assert status == 200
        assert headers[b"cache-control"] == b"no-cache"
        status, conditional_headers = request(
            application, path, headers=[(b"if-none-match", headers[b"etag"])]
        )
        assert status == 304
        assert conditional_headers[b"cache-control"] == b"no-cache"
        status, head_headers = request(application, path, method="HEAD")
        assert status == 200
        assert head_headers[b"cache-control"] == b"no-cache"


def test_api_is_forwarded_unchanged():
    forwarded = []

    async def downstream(scope, receive, send):
        forwarded.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})

    wrapped = launcher.RevalidateFrontend(downstream)
    status, headers = request(wrapped, "/api/view")
    assert status == 200
    assert b"cache-control" not in headers
    assert forwarded[0]["path"] == "/api/view"
