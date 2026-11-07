"""Compare explicit file bytes with a recorded SHA-256 manifest.

This checks supplied artifacts, not the identity of a running process, the
meaning of a configuration hash, or model/physics compatibility on its own.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, manifest: dict) -> dict:
    root = root.resolve()
    entries = manifest.get('artifacts')
    if not isinstance(entries, list) or not entries:
        raise ValueError('artifacts must be a non-empty list')
    results = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('each artifact must be an object')
        name, expected = entry.get('path'), entry.get('sha256')
        if not isinstance(name, str) or not name or not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            raise ValueError('each artifact needs a path and a full SHA-256')
        candidate = (root / name).resolve()
        if not candidate.is_relative_to(root) or candidate in seen:
            raise ValueError('paths must be unique and remain inside the root')
        seen.add(candidate)
        actual = sha256_file(candidate) if candidate.is_file() else None
        results.append({'path': name, 'expected_sha256': expected.lower(), 'actual_sha256': actual, 'match': actual == expected.lower()})
    return {'match': all(item['match'] for item in results), 'artifacts': results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.root, json.loads(args.manifest.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f'Identity check failed: {error}\n')
    print(json.dumps(result, indent=2))
    return 0 if result['match'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
