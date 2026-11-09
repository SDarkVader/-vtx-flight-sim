"""Check the supplied R6 meshes and simulator articulation assignments."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest(path):
    data = path.read_bytes()
    assert data[:4] == b'glTF'
    length = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20 + length])


def meshes_by_id(doc):
    return {node['extras']['blendstra_id']: node for node in doc['nodes']
            if 'mesh' in node and node.get('extras', {}).get('blendstra_id')}


def test_reference_meshes_and_body_rig_are_preserved():
    source = manifest(ROOT / 'assets/reference/r6-blendstra-reference.glb')
    rig = manifest(ROOT / 'public/assets/airframe-r6-blendstra-rig.glb')
    old = manifest(ROOT / 'public/assets/airframe-r6.glb')
    s, r, o = map(meshes_by_id, (source, rig, old))
    assert len(s) == len(r) == 691 and s.keys() == r.keys()
    for key in s:
        source_primitives = source['meshes'][s[key]['mesh']]['primitives']
        rig_primitives = rig['meshes'][r[key]['mesh']]['primitives']
        assert len(source_primitives) == len(rig_primitives) == 1
        for attr in ('POSITION', 'NORMAL'):
            a = source['accessors'][source_primitives[0]['attributes'][attr]]['count']
            b = rig['accessors'][rig_primitives[0]['attributes'][attr]]['count']
            assert a == b
        if key in o:
            assert r[key]['extras']['physical_body'] == o[key]['extras']['physical_body']
    for name in ('airframe','cabin',*[f'{kind}{i}' for kind, n in
                  [('rotor',4),('nacelle',4),('gear',6),('shaft',4)] for i in range(1,n+1)]):
        before = next(n for n in old['nodes'] if n.get('name') == name)
        after = next(n for n in rig['nodes'] if n.get('name') == name)
        assert before.get('translation',[0,0,0]) == after.get('translation',[0,0,0])
    for i in range(1,5):
        for kind in ('Lip_Glow','Livery_Band'):
            node = next(n for n in rig['nodes'] if n.get('name') == f'Phase2_Duct_{kind}_F{i}')
            assert node['extras']['physical_body'] == f'nacelle{i}'
    assert sum('pitch_axis' in n.get('extras',{}) for n in rig['nodes']) == 16
