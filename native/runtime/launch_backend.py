"""Start one private VTX runtime for a native Windows game process."""

import argparse
import asyncio
from contextlib import asynccontextmanager
import ctypes
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import socket
import sys
import traceback


PHANTOM = "phantom-a10d"
ENVIRONMENT = "vaderland-33"
WORLD_VERSION = "33.1"
WORLD_HASH = "3333e153ac809f473db60750c57f181207e0378e99e078a872a9a3d854317bed"


class WindowsParent:
    """Hold the original process handle so PID reuse cannot keep this server alive."""

    def __init__(self, pid):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel32.WaitForSingleObject.restype = ctypes.c_ulong
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        self.kernel32 = kernel32
        self.handle = kernel32.OpenProcess(0x00100000, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def is_running(self):
        # WAIT_TIMEOUT means the parent process has not signaled its exit.
        return self.kernel32.WaitForSingleObject(self.handle, 0) == 258

    def close(self):
        self.kernel32.CloseHandle(self.handle)


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def serve(root, session, parent_pid):
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))
    sys.dont_write_bytecode = True
    os.environ["VTX_DATA_ROOT"] = str(session)
    os.environ["VTX_DEFAULT_ENVIRONMENT"] = ENVIRONMENT
    os.environ["VTX_ENFORCE_RELEASE"] = "0"
    os.environ.pop("VERCEL", None)
    access_token = secrets.token_urlsafe(32)
    os.environ["VTX_CLOUD_ACCESS_TOKEN"] = access_token

    import uvicorn
    from vtx import live_server as simulator

    parent = WindowsParent(parent_pid)
    candidate_lifespan = simulator.app.router.lifespan_context
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(
                simulator.app,
                host="127.0.0.1",
                port=port,
                access_log=False,
                use_colors=False,
                timeout_graceful_shutdown=5,
            ))

            async def watch_parent():
                while parent.is_running() and not (session / "stop-server.flag").exists():
                    await asyncio.sleep(0.25)
                server.should_exit = True

            @asynccontextmanager
            async def native_lifespan(app):
                simulator.get_lab()
                await simulator.model_preview({
                    "airframe_variant": PHANTOM,
                    "environment": ENVIRONMENT,
                    "start_configuration": "vtol",
                })
                identity = await simulator.identity()
                if identity.get("variant") != PHANTOM or identity.get("verified") is not True:
                    raise ValueError("The selected Phantom A10-D failed the candidate identity checks.")
                world = await simulator.world()
                if (
                    world.get("id") != ENVIRONMENT
                    or world.get("version") != WORLD_VERSION
                    or world.get("displayed_world_sha256") != WORLD_HASH
                ):
                    raise ValueError("The runtime did not load the reviewed Vaderland 33.1 world.")
                if not parent.is_running() or (session / "stop-server.flag").exists():
                    raise RuntimeError("The native game closed during startup.")
                async with candidate_lifespan(app):
                    watcher = asyncio.create_task(watch_parent())
                    try:
                        write_json(session / "initial-world.json", world)
                        write_json(session / "ready.json", {
                            "pid": os.getpid(),
                            "port": port,
                            "token": access_token,
                            "identity": identity,
                            "world_hash": WORLD_HASH,
                        })
                        yield
                    finally:
                        watcher.cancel()
                        await asyncio.gather(watcher, return_exceptions=True)

            simulator.app.router.lifespan_context = native_lifespan
            server.run(sockets=[listener])
            if not server.started:
                raise RuntimeError("The local simulator failed to start. See backend.log.")
    finally:
        parent.close()
        (session / "ready.json").unlink(missing_ok=True)
        (session / "initial-world.json").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    args = parser.parse_args()
    session = args.session.resolve(strict=True)
    root = Path(__file__).resolve().parent
    if not session.is_dir() or session == root or session.is_relative_to(root):
        parser.error("Use a separate native session directory.")
    if not (root / "src" / "vtx" / "live_server.py").is_file():
        parser.error("Missing bundled VTX runtime sources.")
    with (session / "backend.log").open("w", encoding="utf-8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        try:
            serve(root, session, args.parent_pid)
        except Exception as error:
            traceback.print_exc(file=log)
            write_json(session / "error.json", {"message": str(error)})
            return 1
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
