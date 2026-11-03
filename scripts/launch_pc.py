"""Launch the release-checked R6 cockpit, regardless of the Git worktree."""

import os
from pathlib import Path
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
URL = "http://127.0.0.1:8765/"

# All local worktrees share this one isolated R6 flight state. In particular,
# do not auto-restore an R5 checkpoint from an obsolete checkout.
DEFAULT_DATA_ROOT = Path(
    os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")
) / "VTX" / "r6-live"


def open_when_ready(server):
    for _ in range(60):
        if server.started:
            webbrowser.open(URL)
            return
        time.sleep(0.5)
    print("Browser not opened: inspect server startup/release check.", flush=True)


def main():
    from vtx.release import EXPECTED_RELEASE

    asset = ROOT / "public" / EXPECTED_RELEASE["render_asset"].lstrip("/")
    if not asset.is_file():
        raise SystemExit(f"R6 visual model missing; refusing to start: {asset}")

    os.environ.setdefault("VTX_DATA_ROOT", str(DEFAULT_DATA_ROOT))
    os.environ["VTX_ENFORCE_RELEASE"] = "1"
    print(
        f"VTX R6 cockpit: data={os.environ['VTX_DATA_ROOT']}, "
        f"airframe={EXPECTED_RELEASE['airframe_revision']}, "
        f"physics={EXPECTED_RELEASE['physics_revision']}",
        flush=True,
    )
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config("vtx.live_server:app", host="0.0.0.0", port=8765, log_level="warning")
    )
    threading.Thread(target=open_when_ready, args=(server,), daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
