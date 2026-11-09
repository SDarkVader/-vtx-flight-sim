"""The two refined Phantom GLBs must agree material by material, and the wing-bay window must be see-through in both.

The animated preview is a Blender export (Y-up); the live-sim model is Z-up. A height test written against the file's own
Z axis left the sleeve top plate opaque in the animated file, hiding the mechanism under the glass. Standard library only
(the GLB JSON chunk is enough), so it runs in CI without a glTF package.
"""
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'public/assets/phantom-a10-visual.glb'
ANIMATED = ROOT / 'assets/derived/phantom-a10-cassette-visual.glb'
GLAZING = 'VTX visual · smoked inspection glazing'


def glb_json(path):
    data = path.read_bytes()
    magic, _version, _length = struct.unpack('<4sII', data[:12])
    assert magic == b'glTF'
    chunk_len, chunk_type = struct.unpack('<I4s', data[12:20])
    assert chunk_type == b'JSON'
    return json.loads(data[20:20 + chunk_len])


def materials_by_primitive(path):
    g = glb_json(path)
    out = {}
    for node in g['nodes']:
        if 'mesh' not in node:
            continue
        for k, prim in enumerate(g['meshes'][node['mesh']]['primitives']):
            m = g['materials'][prim['material']]
            alpha = m.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1])[3]
            out[(node.get('name', ''), k)] = (m.get('name'), m.get('alphaMode', 'OPAQUE'), round(alpha, 4))
    return out


@pytest.fixture(scope='module')
def tables():
    return materials_by_primitive(LIVE), materials_by_primitive(ANIMATED)


def test_same_primitives_and_materials_in_both_files(tables):
    live, animated = tables
    assert set(live) == set(animated)
    assert {k: (live[k], animated[k]) for k in live if live[k] != animated[k]} == {}


@pytest.mark.parametrize('which', [0, 1], ids=['live-sim', 'animated'])
def test_sleeve_top_plate_under_the_bay_window_is_glazing(tables, which):
    plates = {k: v for k, v in tables[which].items() if k[0].startswith('A10_SLEEVE_CARRY_THROUGH_BOX') and v[0] == GLAZING}
    assert len(plates) == 1                                              # exactly one plate is glazed
    assert next(iter(plates.values()))[1:] == ('BLEND', 0.12)            # and it is translucent, not opaque


def test_animated_preview_still_has_its_28_animations():
    g = glb_json(ANIMATED)
    assert len(g.get('animations', [])) == 28
