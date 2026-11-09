"""Single-origin cockpit and dashboard. Keep dashboard's existing versioned store."""
import asyncio
import urllib.request
import urllib.error
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from vtx.live_server import app

DASHBOARD_STORE = "https://vtx-phantom-a10-flight-test.tawnyzinnia4.chatgpt.site/api/data"

def _transfer(method, body):
    request = urllib.request.Request(DASHBOARD_STORE, data=body, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0 VTX-Flight-Test"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return 502, b'{"error":"Dashboard storage unavailable"}'

async def dashboard_data(request: Request):
    body = await request.body() if request.method == "PUT" else None
    if body is not None and len(body) > 1600000:
        return Response(b'{"error":"Record too large"}', status_code=413, media_type="application/json")
    status, data = await asyncio.to_thread(_transfer, request.method, body)
    return Response(data, status_code=status, media_type="application/json",
                    headers={"Cache-Control":"no-store"})

# Register ahead of the root static-file mount.
app.router.routes.insert(0, APIRoute("/api/data", dashboard_data, methods=["GET","PUT"]))

# Cockpit and dashboard share the selected runtime; startup does not change aircraft.
