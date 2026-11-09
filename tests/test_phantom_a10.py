"""A10 corrected wing cassette is the main Phantom (phantom, phantom-fx); A9 stays as the earlier version (phantom-a9, phantom-fx-a9).

Canned bench checks only, not flights: parameter inheritance, ledger mass delta, joint stroke,
wing deploy/stow sequencing, live-server allow-list and the browser render asset.
"""
import copy, json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'phantom'))
import phantom_bench as B
from vtx.phantom.params import Params, VARIANTS, PhantomConfigError
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
    assert a.provenance['render_asset'] == '/assets/phantom-a10.glb'
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


def test_live_server_and_mission_panel_offer_a10_main_and_a9_earlier():
    from vtx.live_server import Mission
    from vtx.phantom.live import is_phantom_variant
    for v in ('phantom-a10b', 'phantom', 'phantom-fx', 'phantom-a9', 'phantom-fx-a9'):
        assert v in VARIANTS and is_phantom_variant(v)
        assert Mission.airframe(v) == v
    html = (ROOT / 'public/index.html').read_text(encoding='utf-8')
    assert '<option value="phantom-a10b" selected>Phantom FX-A A10-B · CURRENT PROTOTYPE' in html and '<option value="phantom">Phantom A10 ·' in html
    assert '<option value="phantom-fx">Phantom FX-A A10-A · previous prototype' in html
    assert Params('phantom-a10b').variant_info['release_stage'] == 'current_prototype'
    assert Params('phantom-fx').variant_info['release_stage'] == 'previous_prototype'
    assert html.count('A9 · EARLIER VERSION') == 2
    raw = json.loads((ROOT / 'inputs/phantom_parameters_v1.json').read_text())
    assert raw['base']['geometry_sources']['wing_cassette_revision'] == 'A10'
    for v in ('phantom-a9', 'phantom-fx-a9'):
        assert Params(v).variant_info['release_stage'] == 'earlier_version'


def test_a10_glb_maps_every_ledger_joint():
    report = json.loads((ROOT / 'evidence/phantom/phantom_glb_export_a10.json').read_text())
    assert report and all(v != 'missing' for v in report.values())
    assert all(v['cad'].startswith(('A10_', 'JOINT_')) for v in report.values())
