"""Preserve incompatible idle state before launching a newer Windows build."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

root = Path(__file__).resolve().parents[1]


def prepare(data_root):
    pilot = Path(data_root) / "pilot"
    current = json.loads((root / "inputs/flight_revisions.json").read_text(
        encoding="utf-8"))["integrated_runtime_sha256"]
    candidates = []
    for name in ("live-flight-checkpoint.json", "inspection-selection.json"):
        path = pilot / name
        if not path.exists():
            continue
        payload = path.read_bytes()
        state = json.loads(payload)
        if state.get("runtime_source_sha256") != current:
            candidates.append((path, payload))
    if not candidates:
        return None
    archive = pilot / "launcher-recovery" / uuid.uuid4().hex
    archive.mkdir(parents=True)
    for path, payload in candidates:
        backup = archive / path.name
        with backup.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if hashlib.sha256(backup.read_bytes()).digest() != hashlib.sha256(payload).digest():
            raise RuntimeError("Could not verify saved flight backup")
    for path, payload in candidates:
        if path.read_bytes() != payload:
            raise RuntimeError("Flight data changed while preparing the game")
    for path, _ in candidates:
        shutil.move(str(path), str(archive / ("original-" + path.name)))
    return archive


if __name__ == "__main__":
    try:
        saved = prepare(sys.argv[1])
        if saved:
            print(f"Older flight data preserved at {saved}")
    except (OSError, ValueError, IndexError) as error:
        print(f"Could not prepare retained flight data: {error}", file=sys.stderr)
        raise SystemExit(1)
