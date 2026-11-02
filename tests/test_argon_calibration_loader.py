"""Read-only Argon calibration regression tests (no server or flight required)."""
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from argon_calibration import load_calibration

def test_r6_10kg_hover_reference():
    result=load_calibration(aircraft_revision="P0-V4A-assembly-r6",fuel_kg=10)
    assert result["hover"]["collective_deg"] == [16.95,17.66,16.95,16.24]
    assert result["hover"]["shaft_kw"] == 202.5
    assert result["advisory_only"] is True

@pytest.mark.parametrize("revision,fuel",[
    ("P0-V4A-assembly-r5",10),("unknown",10),(None,10),
    ("P0-V4A-assembly-r6",20),("P0-V4A-assembly-r6",None)])
def test_fail_closed_on_unverified_state(revision,fuel):
    with pytest.raises(ValueError):
        load_calibration(aircraft_revision=revision,fuel_kg=fuel)

def test_survives_new_loader_call():
    a=load_calibration(aircraft_revision="P0-V4A-assembly-r6",fuel_kg=10)
    b=load_calibration(aircraft_revision="P0-V4A-assembly-r6",fuel_kg=10)
    assert a==b

def test_invalid_source_rejected(tmp_path):
    source=json.loads((ROOT/"pilot"/"argon_calibration_reference.json").read_text())
    source["source"]="unverified"
    p=tmp_path/"bad.json"
    p.write_text(json.dumps(source))
    with pytest.raises(ValueError):
        load_calibration(p,aircraft_revision="P0-V4A-assembly-r6",fuel_kg=10)
