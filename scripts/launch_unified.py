"""Unified VTX PC entry point. Physical cockpit by default; API optional.

Never kills another simulator, changes flight authority, or selects a model
on startup. Use --port 8767 --data-root <empty directory> for isolated QA.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import socket
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
VTX_HOME = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "VTX"
DEFAULT_PORT = 8770
PORT_SEARCH = 20


def checkout_data_root(root: Path = ROOT) -> Path:
    """One data folder per checkout, so a checkpoint left by another clone or an
    older build can never block this one. Stable across updates of the same clone,
    so its own interrupted flights are still recovered."""
    root = root.resolve()
    tag = hashlib.sha256(str(root).lower().encode()).hexdigest()[:8]
    return VTX_HOME / "checkouts" / f"{root.name.strip('-') or 'vtx'}-{tag}"


DEFAULT_DATA_ROOT = Path(os.environ["VTX_DATA_ROOT"]) if os.environ.get("VTX_DATA_ROOT") else checkout_data_root()


def port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((host, port)) != 0


def first_free_port(start: int, count: int = PORT_SEARCH) -> int:
    for port in range(start, start + count):
        if port_available("127.0.0.1", port):
            return port
    raise RuntimeError(f"No free port in {start}-{start + count - 1}; another simulator may be running")


def configure(data_root: Path, port: int) -> None:
    if not (1024 <= port <= 65535):
        raise ValueError("Invalid TCP port")
    if not port_available("127.0.0.1", port):
        raise RuntimeError(f"Port {port} is already occupied; refusing to replace or stop the running flight")
    os.environ["VTX_DATA_ROOT"] = str(data_root.resolve())
    os.environ["VTX_ENFORCE_RELEASE"] = "0"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=None,
                        help=f"Fixed port (refused if busy). Default: first free port from {DEFAULT_PORT}")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check configuration without launching")
    args = parser.parse_args(argv)
    if args.port is None:
        args.port = first_free_port(DEFAULT_PORT)
    configure(args.data_root, args.port)
    checkpoint = args.data_root / "pilot" / "live-flight-checkpoint.json"
    if checkpoint.exists():
        print(f"Note: an interrupted flight is saved at {checkpoint}; it will be offered for recovery.", flush=True)
    if args.check:
        print(f"VTX unified launch OK: port={args.port}, data={args.data_root.resolve()}, no flight started", flush=True)
        return 0

    import uvicorn

    server = uvicorn.Server(uvicorn.Config(
        "vtx.dashboard_site:app", host="0.0.0.0", port=args.port, log_level="warning"
    ))
    if not args.no_browser:
        def open_when_ready():
            for _ in range(60):
                if server.started:
                    webbrowser.open(f"http://127.0.0.1:{args.port}/")
                    return
                time.sleep(0.5)
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"VTX unified cockpit: port={args.port}, data={args.data_root.resolve()}, physics mode=live", flush=True)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
