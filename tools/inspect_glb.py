"""Print structural evidence for comparing VTX GLB revisions."""
import json
import struct
import sys
from pathlib import Path


def inspect(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from('<III', data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError(f'{path}: invalid GLB')
    chunk_length, chunk_type = struct.unpack_from('<II', data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f'{path}: missing JSON chunk')
    gltf = json.loads(data[20:20 + chunk_length])
    nodes = gltf.get('nodes', [])
    names = [node.get('name', '') for node in nodes]
    materials = gltf.get('materials', [])
    relevant = [name for name in names if any(term in name.lower() for term in
                ('hatch', 'glass', 'glaz', 'wing', 'slide', 'pin_', 'aileron', 'flap_'))]
    transparent = [dict(name=m.get('name'), alphaMode=m.get('alphaMode', 'OPAQUE'),
                        alpha=m.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1])[3])
                   for m in materials if m.get('alphaMode') == 'BLEND' or
                   m.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1])[3] < 1]
    animated = sorted({names[channel['target']['node']] for animation in gltf.get('animations', [])
                       for channel in animation.get('channels', []) if channel.get('target', {}).get('node', -1) < len(names)})
    return {'path': str(path), 'bytes': len(data), 'nodes': len(nodes),
            'meshes': len(gltf.get('meshes', [])), 'animations': len(gltf.get('animations', [])),
            'animatedNodes': animated, 'transparent': transparent,
            'relevantNames': relevant}


if __name__ == '__main__':
    for filename in sys.argv[1:]:
        print(json.dumps(inspect(filename), indent=2))
