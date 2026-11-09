"""Single-origin cockpit and dashboard. Keep dashboard's existing versioned store."""
import asyncio
import os
import urllib.request
import urllib.error
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from vtx.live_server import app
from vtx import live_server

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

# Default only a genuinely new workspace. A saved pilot, sortie, checkpoint or
# experiment belongs to the operator and must not be silently replaced.
def _new_workspace(root):
    return not any((root / path).exists() for path in (
        'pilot/colin-memory.json', 'pilot/live-flight-checkpoint.json',
        'evidence/flights', 'experiments'))

_live_lifespan = app.router.lifespan_context

@asynccontextmanager
async def dashboard_lifespan(application):
    root = Path(os.environ.get('VTX_DATA_ROOT', str(live_server.ROOT))).resolve()
    use_default = (os.environ.get('VTX_ENFORCE_RELEASE') != '1'
                   and live_server.lab is None and _new_workspace(root))
    async with _live_lifespan(application):
        if use_default and not live_server.lab.active and not live_server.lab.recovery_blocked:
            await live_server.model_preview({'airframe_variant': 'phantom-a10b',
                                             'start_configuration': 'road'})
        yield

app.router.lifespan_context = dashboard_lifespan
