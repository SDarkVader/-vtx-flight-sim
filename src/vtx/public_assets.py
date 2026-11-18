"""Locate the exact public files used for visual pins, checkpoints and hull geometry."""
import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile


def public_directory(repo_root: Path) -> Path:
    archive = repo_root / "inputs/vercel_frontend.zip"
    if os.environ.get("VERCEL") and archive.is_file():
        return _unpack(archive)
    return repo_root / "public"


@lru_cache(maxsize=1)
def _unpack(archive: Path) -> Path:
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    parent = Path(tempfile.gettempdir())
    destination = parent / ("vtx-frontend-" + digest)
    if not destination.is_dir():
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            staged = Path(temporary) / "public"
            with ZipFile(archive) as bundle:
                bundle.extractall(staged)
            # Other workers can only see a complete tree, including on a cold start.
            try:
                staged.rename(destination)
            except OSError:
                if not destination.is_dir():
                    raise
    return destination
