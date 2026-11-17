"""A10 cassette inheritance and explicit, unpromoted aircraft selection.

Canned bench checks only, not flights: parameter inheritance, ledger mass delta, joint stroke,
wing deploy/stow sequencing, live-server allow-list and the browser render asset.
"""
import copy, json, sys
from pathlib import Path
from html.parser import HTMLParser
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'phantom'))
import phantom_bench as B
from vtx.phantom.params import Params, VARIANTS, DEFAULT_VARIANT, PhantomConfigError
from vtx.phantom.flight_revisions import registry
from vtx.phantom.ledger import PhantomLedger
from vtx.phantom.geometry import WING_SIDES

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [('phantom-a9', 'phantom'), ('phantom-fx-a9', 'phantom-fx')]


@pytest.mark.parametrize('a9,a10', PAIRS)
def test_a10_variant_differs_from_its_parent_only_in_cassette_revision(a9, a10):
    p9, p10 = Params(a9), Params(a10)
    assert (p9.cassette_revision, p10.cassette_revision) == ('A9', 'A10')
    t = copy.deepcopy(p9.tree); t['geometry_sources']['wing_cassette_revision'] = 'A10'
    assert t == p10.tree
    assert p9.wing_stroke_m == pytest.approx(1.37) and p10.wing_stroke_m == pytest.approx(1.205)
    assert p10.handover['aero_surfaces']['wing']['ac_height_R_m'] == p10.handover['aero_surfaces']['wing']['ac_height_L_m']


@pytest.mark.parametrize('a9,a10', PAIRS)
def test_a10_ledger_adds_the_cassette_bay_mass(a9, a10):
    m9 = PhantomLedger(Params(a9)).mass_properties(None)
    m10 = PhantomLedger(Params(a10)).mass_properties(None)
    assert m10['mass_kg'] - m9['mass_kg'] == pytest.approx(9.01, abs=0.05)   # A10 study: +9.01 kg
    assert abs(m10['cg_m'][1]) < 1e-3
    ids = {c.id for c in PhantomLedger(Params(a10)).components}
    assert 'a10_cassette_fixed' in ids and 'a9_cassette_fixed' not in ids


def test_unknown_cassette_revision_is_rejected():
    with pytest.raises(PhantomConfigError):
        Params('phantom', overrides={'geometry_sources': {'wing_cassette_revision': 'A11'}})


@pytest.mark.parametrize('variant', ['phantom', 'phantom-fx'])
def test_a10_plant_spawns_stowed_and_reports_its_render_asset(variant):
    a = B.plant(variant)
    assert a.provenance['render_asset'] == '/assets/phantom-a10-blendstra-81c823e2.glb'
    assert a.provenance['wing_cassette_revision'] == 'A10'
    assert (ROOT / 'public' / a.provenance['render_asset'].lstrip('/')).exists()
    for s in WING_SIDES:
        assert a.joint(f'wing_{s}')[0] == pytest.approx(-1.205, abs=1e-3)
        assert tuple(a.model.jnt_range[a.jid[f'wing_{s}']]) == pytest.approx((-1.205, 0.0))


def test_a10_wings_deploy_lock_and_stow_on_the_ground():
    a = B.plant('phantom-fx')
    a.set_command(dict(wing='deploy', brake=[1] * 4))
    for _ in range(int(15 / B.DT)):
        a.step()
        if all(a.wing_locked(s) for s in WING_SIDES):
            break
    assert all(a.wing_locked(s) for s in WING_SIDES), a.wing_state
    a.set_command(dict(wing='stow'))
    for _ in range(int(15 / B.DT)):
        a.step()
        if all(a.wing_state[s] == 'stowed' for s in WING_SIDES):
            break
    assert all(a.wing_state[s] == 'stowed' for s in WING_SIDES), a.wing_state
    assert not a.faults and not a.crashed
    for s in WING_SIDES:
        assert a.joint(f'wing_{s}')[0] == pytest.approx(-1.205, abs=0.005)


class AircraftMenus(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.menus = {}; self.current = None; self.option = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'select' and attrs.get('id') in ('airframe', 'main-aircraft'):
            self.current = dict(attrs=attrs, options=[])
            self.menus[attrs['id']] = self.current
        elif tag == 'option' and self.current is not None:
            self.option = dict(attrs=attrs, text='')

    def handle_data(self, text):
        if self.option is not None:
            self.option['text'] += text

    def handle_endtag(self, tag):
        if tag == 'option' and self.option is not None:
            self.current['options'].append(self.option); self.option = None
        elif tag == 'select':
            self.current = None


def test_mission_panel_requires_explicit_unpromoted_choice_and_preserves_a10_a9_references():
    from vtx.live_server import Mission
    from vtx.phantom.live import is_phantom_variant
    flown = registry()['revisions']
    variants = ('phantom-a10b', 'phantom-a10c', 'phantom', 'phantom-fx', 'phantom-a9', 'phantom-fx-a9', *flown)
    for v in variants:
        assert v in VARIANTS and is_phantom_variant(v)
        assert Mission.airframe(v) == v
    html = (ROOT / 'public/index.html').read_text(encoding='utf-8')
    menus = AircraftMenus(html).menus
    options = {row['attrs'].get('value'): row for row in menus['airframe']['options']}
    assert set(variants) <= options.keys()
    selected = [row for row in options.values() if 'selected' in row['attrs']]
    assert len(selected) == 1 and selected[0]['attrs']['value'] == ''
    assert 'disabled' in selected[0]['attrs'] and 'Select a test aircraft' in selected[0]['text']
    assert 'disabled' not in menus['main-aircraft']['attrs']
    main_options = {row['attrs'].get('value'): row for row in menus['main-aircraft']['options']}
    assert set(main_options) == {'', 'r6', 'phantom-a10c'}
    assert 'disabled' not in main_options['r6']['attrs']
    assert 'visual match pending' not in main_options['r6']['text']
    assert 'pinned reference' in options['phantom-a10b']['text']
    assert 'current development' in options['phantom-a10c']['text']
    for v, record in flown.items():
        assert 'integrated candidate' in options[v]['text'] and 'limited testing' in options[v]['text']
        assert 'promotion pending' in record['status'].lower()
    # The established parameter default remains B; it is not an automatic
    # browser choice or an owner-approved promotion of B/C/flown candidates.
    assert DEFAULT_VARIANT == 'phantom-a10b'
    assert Params('phantom-a10b').variant_info['release_stage'] == 'current_prototype'
    assert Params('phantom-fx').variant_info['release_stage'] == 'previous_prototype'
    assert all('earlier reference' in options[v]['text'] for v in ('phantom-a9', 'phantom-fx-a9'))
    raw = json.loads((ROOT / 'inputs/phantom_parameters_v1.json').read_text())
    assert raw['base']['geometry_sources']['wing_cassette_revision'] == 'A10'
    for v in ('phantom-a9', 'phantom-fx-a9'):
        assert Params(v).variant_info['release_stage'] == 'earlier_version'


def test_a10_glb_maps_every_ledger_joint():
    report = json.loads((ROOT / 'evidence/phantom/phantom_glb_export_a10.json').read_text())
    assert report and all(v != 'missing' for v in report.values())
    assert all(v['cad'].startswith(('A10_', 'JOINT_')) for v in report.values())
