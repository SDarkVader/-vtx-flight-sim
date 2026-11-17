"""Identify an existing local server without changing its flight or fleet state."""
import json
import argparse
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def read(path, port=8770):
    with urlopen(f'http://127.0.0.1:{port}' + path, timeout=3) as response:
        return response.read()


def check_server(root=ROOT, reader=read):
    world = json.loads(reader('/api/world'))
    view = json.loads(reader('/api/view'))
    expected = json.loads((root / 'inputs/flight_revisions.json').read_text(encoding='utf-8'))['integrated_runtime_sha256']
    if not (world.get('environment') == 'airport' and world.get('harbour')
            and view.get('runtime_source_sha256') == expected):
        raise ValueError('A different VTX version is running on port 8770.')
    # app.js alone cannot identify a build: selectors, cameras and styling are
    # separate modules. Validate every frontend text file without issuing POSTs.
    for file in sorted((root / 'public').rglob('*')):
        if file.is_file() and file.suffix.lower() in {'.html', '.js', '.css', '.json'}:
            uri = '/' + file.relative_to(root / 'public').as_posix()
            if reader(uri) != file.read_bytes():
                raise ValueError('The running frontend differs at ' + uri)
    return view


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    try:
        check_server(reader=lambda path: read(path, args.port))
        print(f'The current airport and harbour build is already running at http://127.0.0.1:{args.port}/')
    except (OSError, ValueError, KeyError) as error:
        print(f'Cannot verify the server on port {args.port}:', error)
        raise SystemExit(1)
