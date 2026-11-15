"""Read-only validation of the exact reviewed Python tree and visual assets."""
from pathlib import Path
import hashlib
import json
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / 'src/vtx'
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*.py'), key=lambda p: p.relative_to(source).as_posix()):
        name = path.relative_to(source).as_posix().encode('utf-8')
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, 'big')); digest.update(name)
        digest.update(len(data).to_bytes(8, 'big')); digest.update(data)
    registry = json.loads((root / 'inputs/flight_revisions.json').read_text(encoding='utf-8'))
    if digest.hexdigest() != registry['integrated_runtime_sha256']:
        raise ValueError('Python files differ from the reviewed runtime. Read the continuity record; do not repin automatically.')
    checked = set()
    for revision in registry['revisions'].values():
        artifacts = [(revision['render_asset'], revision['render_asset_sha256'])]
        schematic = revision.get('suspension_schematic')
        if schematic:
            artifacts.append((schematic['asset'], schematic['sha256']))
        for uri, expected in artifacts:
            if (uri, expected) in checked:
                continue
            path = (root / 'public' / uri.lstrip('/')).resolve()
            if not path.is_relative_to((root / 'public').resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('Reviewed visual asset differs: ' + uri)
            checked.add((uri, expected))
    print('Reviewed runtime verified: ' + digest.hexdigest())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as error:
        print('VTX launch refused: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
