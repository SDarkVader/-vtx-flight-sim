import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from vtx.live_server import read_replay_frames, recorded_phantom_wheel_geometry


VARIANT = 'phantom-a10c'


def make_run(tmp_path):
    run = tmp_path / 'recorded-flight'
    run.mkdir()
    root = ET.Element('mujoco')
    ET.SubElement(ET.SubElement(root, 'default'), 'geom', friction='.75 .005 .0001')
    world = ET.SubElement(root, 'worldbody')
    airframe = ET.SubElement(world, 'body', name='airframe')
    for corner in ('FL', 'FR', 'RL', 'RR'):
        pod = ET.SubElement(airframe, 'body', name=f'pod_{corner}')
        wheel = ET.SubElement(pod, 'body', name=f'pod_{corner}_wheel', pos='0 0 0')
        ET.SubElement(wheel, 'joint', name=f'pod_{corner}_wheel')
        ET.SubElement(wheel, 'geom', name=f'tyre_{corner}', type='cylinder',
                      size='0.55 0.06', zaxis='0 1 0')
    write_model(run, root)
    return run, root


def write_model(run, root):
    xml = ET.tostring(root)
    (run / 'model.xml').write_bytes(xml)
    digest = hashlib.sha256(xml).hexdigest()
    (run / 'metadata.json').write_text(json.dumps(dict(run_id=run.name, airframe=dict(
        airframe_variant=VARIANT, model_xml_sha256=digest))), encoding='utf-8')
    return digest


def test_replay_binds_geometry_only_to_matching_recorded_frames(tmp_path):
    run, root = make_run(tmp_path)
    digest = write_model(run, root)
    def frame(model_hash, variant=VARIANT, geometry=None):
        phantom = {'joints': {}}
        if geometry is not None:
            phantom['wheel_collision_geometry'] = geometry
        return {'kind': 'physics_audit', 'payload': {'variant': variant, 'phantom': phantom,
            'provenance': {'airframe_variant': variant, 'model_xml_sha256': model_hash}}}
    existing = {'FL': {'radius_m': .47, 'half_width_m': .05}}
    entries = [frame(digest), frame('0' * 64), frame(digest, 'phantom-a10b'), frame(digest, geometry=existing)]
    path = run / 'events.jsonl'
    path.write_text(''.join(json.dumps(e) + '\n' for e in entries), encoding='utf-8')
    result = read_replay_frames(path)
    assert result['recorded_wheel_geometry']['model_xml_sha256'] == digest
    first, wrong_hash, wrong_variant, already_recorded = [f['phantom'] for f in result['frames']]
    assert first['wheel_collision_geometry'] == {
        corner: {'radius_m': .55, 'half_width_m': .06} for corner in ('FL', 'FR', 'RL', 'RR')}
    assert first['wheel_collision_geometry_source'] == 'recorded-model-verified'
    assert 'wheel_collision_geometry' not in wrong_hash
    assert 'wheel_collision_geometry' not in wrong_variant
    assert already_recorded['wheel_collision_geometry'] == existing


@pytest.mark.parametrize('damage', ['missing', 'modified', 'wrong-run', 'default-size',
                                     'duplicate', 'wrong-type', 'offset', 'wrong-axis',
                                     'missing-joint', 'include', 'malformed', 'doctype'])
def test_unreliable_recorded_model_is_not_used(tmp_path, damage):
    run, root = make_run(tmp_path)
    if damage == 'missing':
        (run / 'model.xml').unlink()
    elif damage == 'modified':
        (run / 'model.xml').write_bytes(b'<mujoco/>')
    elif damage == 'wrong-run':
        metadata = json.loads((run / 'metadata.json').read_text(encoding='utf-8'))
        metadata['run_id'] = 'another-flight'
        (run / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    elif damage in ('malformed', 'doctype'):
        xml = b'<mujoco' if damage == 'malformed' else b'<!DOCTYPE mujoco><mujoco/>'
        (run / 'model.xml').write_bytes(xml)
        metadata = json.loads((run / 'metadata.json').read_text(encoding='utf-8'))
        metadata['airframe']['model_xml_sha256'] = hashlib.sha256(xml).hexdigest()
        (run / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    else:
        geom = next(g for g in root.iter('geom') if g.get('name') == 'tyre_FL')
        body = next(b for b in root.iter('body') if b.get('name') == 'pod_FL_wheel')
        if damage == 'default-size': next(root.iter('default')).find('geom').set('size', '1 1')
        if damage == 'duplicate': ET.SubElement(body, 'geom', name='tyre_FL', type='cylinder', size='1 1', zaxis='0 1 0')
        if damage == 'wrong-type': geom.set('type', 'sphere')
        if damage == 'offset': geom.set('pos', '0.1 0 0')
        if damage == 'wrong-axis': geom.set('zaxis', '1 0 0')
        if damage == 'missing-joint': body.remove(body.find('joint'))
        if damage == 'include': ET.SubElement(root, 'include', file='external.xml')
        write_model(run, root)
    assert recorded_phantom_wheel_geometry(run) == {'status': 'unavailable'}
