"""The R6 the game flies and the R6 it shows are one aircraft: the 3 November A-to-B R6 physics,
displayed with the owner-confirmed connected assembly."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('r6_unified', ROOT / 'tools/visual_r6/r6_unified.py')
r6_unified = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r6_unified)


def test_r6_model_physics_and_display_are_the_flown_a_to_b_aircraft():
    report = r6_unified.report()
    failed = [name for name, ok in report['checks'].items() if not ok]
    assert not failed, failed
    assert report['model_xml_sha256'] == r6_unified.MODEL_XML_SHA256
    assert report['display_sha256'] == r6_unified.DISPLAY_SHA256


def test_no_r6_entry_shows_the_disconnected_assembly():
    text = (ROOT / 'public/vtx-env/vehicle-registry.js').read_text(encoding='utf-8')
    for digest, name in r6_unified.RETIRED_DISPLAY_SHA256.items():
        assert digest not in text and name not in text
