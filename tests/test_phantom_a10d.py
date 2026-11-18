"""Phantom A10-D test aircraft (inputs/phantom_test_variants_v1.json): the A10-C with the transition ECU fitted.

The A10-D is listed outside the pinned parameter file, so the A10-C, the A10-B pin and the flown A10-C revisions keep
their identities. It must be the A10-C plus the ECU and nothing else, and it must never stand in for the A10-C."""
import hashlib, json, re

import pytest

import vtx.live_server as server
from vtx.live_server import Laboratory, Mission, parse_action
from vtx.phantom import identity, overlays
from vtx.phantom.flight_revisions import registry
from vtx.phantom.live import is_phantom_variant
from vtx.phantom.params import (PARAMETER_FILE, ROOT, TEST_VARIANT_FILE, VARIANTS, Params, PhantomConfigError,
                                load_test_variants)
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld

A10B = '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01'
A10C = '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f'
A10D = '58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3'   # A10-C + transition_ecu_v1
PARAMETER_FILE_PIN = '3955457a00f9b3eadea50c4d919730099202a36d2063130e95261b466067ee3b'


def test_a10d_is_the_a10c_plus_the_ecu_and_the_a10c_is_unchanged():
    c, d = Params('phantom-a10c'), Params('phantom-a10d')
    assert c.config_sha256 == A10C and 'fbw_transition' not in c.tree and c.test_variant_file_sha256 is None
    assert d.config_sha256 == A10D and d.tree == Params('phantom-a10c', overlays.load('transition_ecu_v1')).tree
    assert c.file_sha256 == d.file_sha256 == PARAMETER_FILE_PIN          # the pinned parameter file is not touched
    assert d.variant_info['inherits'] == 'phantom-a10c' and d.variant_info['overlay_files'] == ['transition_ecu_v1']
    assert d.variant_info['release_stage'] == 'test_aircraft'
    lf = hashlib.sha256(TEST_VARIANT_FILE.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    assert d.snapshot()['test_variant_file_sha256'] == lf and 'test_variant_file_sha256' not in c.snapshot()
    raw = json.loads(PARAMETER_FILE.read_text(encoding='utf-8'))
    assert 'phantom-a10d' not in raw['variants'] and 'phantom-a10d' not in registry()['revisions']
    for revision in registry()['revisions'].values():                    # the flown A10-C revisions keep their pins
        assert revision['config_sha256'] == A10C and revision['parameter_file_sha256'] == PARAMETER_FILE_PIN


def test_a10d_has_the_ecu_on_the_a10c_airframe_and_visual():
    world = TestWorld()
    c, d = PhantomAircraft(world, 'phantom-a10c'), PhantomAircraft(world, 'phantom-a10d')
    assert not c.fcc.transition and d.fcc.transition
    assert c.mass_properties()['mass_kg'] == d.mass_properties()['mass_kg']
    assert c.xml.replace('VTX-PHANTOM-phantom-a10c', 'VTX-PHANTOM-phantom-a10d', 1) == d.xml   # only the model name differs
    assert c.provenance['render_asset'] == d.provenance['render_asset'] == '/assets/phantom-a10b-visual.glb'
    c.set_command(dict(airbrake='on')); d.set_command(dict(airbrake='on'))
    assert c.events[-1]['event'] == 'airbrake_unavailable' and 'transition_ecu' not in c.physical_snapshot()['phantom']
    assert d.events[-1]['event'] == 'airbrake' and d.command['pod_tilt_deg'] == [90.0] * 4
    assert d.physical_snapshot()['phantom']['transition_ecu']['airbrake'] == 'on'


def test_a10d_is_pinned_and_the_existing_pins_are_unchanged():
    check = identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10d'))
    assert check['pinned'] and check['verified'] and not check['mismatches'] and check['config_sha256'] == A10D
    pins = identity.pins()
    assert pins['phantom-a10d']['release_stage'] == 'test_aircraft' and pins['phantom-a10d']['config_sha256'] == A10D
    assert pins['phantom-a10b']['config_sha256'] == A10B and pins['phantom-a10b']['parameter_file_sha256'] == PARAMETER_FILE_PIN
    plain = identity.verify(PhantomAircraft(TestWorld(), 'phantom-a10c'))   # the A10-C is unchanged and still not pinned here
    assert 'phantom-a10c' not in pins and plain['pinned'] is False and plain['config_sha256'] == A10C


@pytest.mark.parametrize('variants, refusal', [
    ({'phantom-a10c': {'inherits': 'phantom-a10b'}}, 'reuses the name'),
    ({'phantom-a10c-runway-20261112': {'inherits': 'phantom-a10c'}}, 'reuses the name'),
    ({'phantom-x': {'inherits': 'phantom-a10c-runway-20261112'}}, 'must inherit'),
    ({'phantom-x': {}}, 'must inherit'),
    ({'phantom-x': {'inherits': 'phantom-a10c', 'overlay': {'mass': {}}}}, 'only named overlay_files'),
    ({'phantom-x': {'inherits': 'phantom-a10c', 'overlay_files': ['no_such_overlay']}}, 'unknown overlay'),
])
def test_a_test_aircraft_cannot_shadow_or_alter_an_existing_variant(tmp_path, variants, refusal):
    path = tmp_path / 'test_variants.json'
    path.write_text(json.dumps(dict(schema=1, variants=variants)), encoding='utf-8')
    with pytest.raises(PhantomConfigError, match=refusal):
        load_test_variants(path)


def test_the_test_aircraft_file_is_optional_and_versioned(tmp_path):
    assert load_test_variants(tmp_path / 'missing.json') == ({}, None)
    (tmp_path / 'v2.json').write_text(json.dumps(dict(schema=2, variants={})), encoding='utf-8')
    with pytest.raises(PhantomConfigError, match='schema'):
        load_test_variants(tmp_path / 'v2.json')


def test_a10d_is_offered_as_a_test_aircraft_and_never_as_the_main_a10c():
    assert 'phantom-a10d' in VARIANTS and is_phantom_variant('phantom-a10d') and Mission.airframe('phantom-a10d') == 'phantom-a10d'
    html = (ROOT / 'public/index.html').read_text(encoding='utf-8')
    airframe = re.search(r'<select id="airframe">(.*?)</select>', html, re.S).group(1)
    groups = dict(re.findall(r'<optgroup label="([^"]*)">(.*?)</optgroup>', airframe, re.S))
    current = next(v for k, v in groups.items() if k.startswith('Current aircraft'))
    earlier = next(v for k, v in groups.items() if k.startswith('Earlier and experimental'))
    assert 'value="phantom-a10d"' not in current and 'value="phantom-a10c"' in current
    option = re.search(r'<option value="phantom-a10d">([^<]*)</option>', earlier)
    assert option and 'test aircraft' in option.group(1) and 'A10-C' in option.group(1)
    main = re.search(r'<select id="main-aircraft"[^>]*>(.*?)</select>', html, re.S).group(1)
    assert 'phantom-a10d' not in main
    look = (ROOT / 'public/vtx-env/phantom-look.js').read_text(encoding='utf-8')
    assert f"'phantom-a10d': '{A10D}'" in look and f"'phantom-a10c': '{A10C}'" in look


def test_a10d_flight_starts_verified_and_the_air_brake_reaches_the_ecu(tmp_path, monkeypatch):
    monkeypatch.setenv('VTX_DATA_ROOT', str(tmp_path)); monkeypatch.setattr(server, 'ROOT', tmp_path)
    lab = Laboratory(); monkeypatch.setattr(server, 'lab', lab)
    dep = list(lab.world.default_departure)
    lab.start(Mission(airframe_variant='phantom-a10d', departure=dep, destination=[dep[0] + 60, dep[1]],
                      phantom=dict(start_configuration='vtol')))
    try:
        record = json.loads((lab.log_path / 'aircraft_identity.json').read_text())
        assert record['variant'] == 'phantom-a10d' and record['verified'] and record['config_sha256'] == A10D
        assert lab.sensor_observation()['configuration']['identity']['status'] == 'verified'
        lab.accept_action(parse_action(dict(schema='phantom-fbw-1', authority=lab.authority, reason='manual panel', airbrake='on')))
        for _ in range(20):   # the action applies 0.02 s after it is issued
            lab.integrate()
        assert lab.aircraft.fcc.cmd['airbrake'] == 'on' and any(e.get('event') == 'airbrake' for e in lab.aircraft.events)
    finally:
        lab.active = False
