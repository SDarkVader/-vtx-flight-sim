"""Restore authored A10 joint extras omitted by a web GLB export.

The old and new exports must have the same named joints. This copies only the
joint control metadata, leaving the new mesh data, glass and animation clips.
"""
import argparse
import json
import struct
from pathlib import Path


def chunks(path):
    blob = Path(path).read_bytes()
    magic, version, size = struct.unpack_from('<III', blob)
    if magic != 0x46546C67 or version != 2 or size != len(blob):
        raise ValueError(f'{path}: invalid GLB header')
    result = []
    offset = 12
    while offset < len(blob):
        length, kind = struct.unpack_from('<II', blob, offset)
        offset += 8
        result.append((kind, blob[offset:offset + length]))
        offset += length
    if not result or result[0][0] != 0x4E4F534A:
        raise ValueError(f'{path}: JSON chunk missing')
    return json.loads(result[0][1]), result[1:]


def pack(manifest, other_chunks):
    payload = json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    payload += b' ' * (-len(payload) % 4)
    parts = [(0x4E4F534A, payload), *other_chunks]
    size = 12 + sum(8 + len(data) for _, data in parts)
    return struct.pack('<III', 0x46546C67, 2, size) + b''.join(
        struct.pack('<II', len(data), kind) + data for kind, data in parts)


def main(old_path, new_path):
    old, _ = chunks(old_path)
    new, other_chunks = chunks(new_path)
    source = {n['name']: n['extras'] for n in old['nodes'] if n.get('extras', {}).get('phantom_joint')}
    if len(source) != 28:
        raise ValueError(f'Expected 28 authored controls, found {len(source)}')
    names = []
    for node in new['nodes']:
        if node.get('name') in source:
            extras = dict(source[node['name']])
            # The legacy GLB keeps Blender's Z-up coordinates. The newer web
            # export converts every node to glTF Y-up: (x,y,z) -> (x,z,-y).
            # Axes are parent-local vectors and must follow that same basis.
            for key in ('axis_parent', 'axis_world'):
                if key in extras:
                    x, y, z = extras[key]
                    extras[key] = [x, z, -y]
            node['extras'] = {**node.get('extras', {}), **extras}
            names.append(node['name'])
    if len(names) != 28 or set(names) != set(source) or len(new.get('animations', [])) != 28:
        raise ValueError('New GLB does not retain the exact 28 named joints and clips')
    if not any(m.get('alphaMode') == 'BLEND' and 'smoked inspection glazing' in m.get('name', '')
               for m in new.get('materials', [])):
        raise ValueError('New GLB is missing transparent inspection glazing')
    Path(new_path).write_bytes(pack(new, other_chunks))
    print(f'Restored {len(names)} authored joint records to {new_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('old_glb')
    parser.add_argument('new_glb')
    args = parser.parse_args()
    main(args.old_glb, args.new_glb)
