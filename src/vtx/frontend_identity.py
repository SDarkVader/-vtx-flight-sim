"""Identity of the server's public files; this does not attest browser content.

The snapshot intentionally covers the whole public tree: it includes the
aircraft assets, optional visual traffic and the environment/cockpit scripts.
Files in /evidence, /docs and dynamic API responses are outside its scope.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PUBLIC_ROOT = Path(__file__).resolve().parents[2] / 'public'


def _digest_file(path: Path, expected_size: int, expected_mtime_ns: int) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    current = path.stat()
    if (current.st_size, current.st_mtime_ns) != (expected_size, expected_mtime_ns):
        raise ValueError('Frontend files changed during identity capture: ' + str(path))
    return digest.hexdigest()


def server_frontend_manifest(root: Path | None = None) -> dict:
    """Hash every public file by reading its bytes.

    The snapshot describes files available to the server at capture time, not a
    handshake with a browser, cache, or already-open page. It is captured when
    the idle aircraft is selected or a flight starts and reused for checkpoints,
    so files changed during an active flight are not observed by this snapshot.
    Recovery always captures and compares a new snapshot from actual bytes.
    """
    root = (Path(root) if root is not None else PUBLIC_ROOT).resolve()
    if not root.is_dir():
        raise ValueError('Frontend public directory is missing')
    paths = sorted((p for p in root.rglob('*') if p.is_file()),
                   key=lambda p: p.relative_to(root).as_posix())
    if not paths:
        raise ValueError('Frontend public directory has no files')
    tree = hashlib.sha256(b'vtx-server-public-tree-v1\0')
    files = {}; observed = {}
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError('Frontend asset escapes the public directory: ' + str(path))
        relative = path.relative_to(root).as_posix()
        name = relative.encode('utf-8')
        stat = path.stat()
        observed[relative] = (stat.st_size, stat.st_mtime_ns)
        digest = _digest_file(path, stat.st_size, stat.st_mtime_ns)
        tree.update(len(name).to_bytes(4, 'big'));tree.update(name)
        tree.update(stat.st_size.to_bytes(8, 'big'));tree.update(bytes.fromhex(digest))
        files[relative] = dict(bytes=stat.st_size, sha256=digest)
    current = sorted((p for p in root.rglob('*') if p.is_file()),
                     key=lambda p: p.relative_to(root).as_posix())
    if [p.relative_to(root).as_posix() for p in current] != list(files):
        raise ValueError('Frontend files changed during identity capture')
    for path in current:
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != observed[path.relative_to(root).as_posix()]:
            raise ValueError('Frontend files changed during identity capture: ' + str(path))
    return dict(scheme='vtx-server-public-tree-v1', scope='server public files at selection or flight start; changes during a flight and dynamic API, /docs and /evidence are excluded',
                browser_loaded_verified=False, sha256=tree.hexdigest(), files=files)
