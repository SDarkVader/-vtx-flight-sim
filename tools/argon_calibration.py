"""Read-only, revision-scoped Argon calibration reference; never issues controls."""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "pilot" / "argon_calibration_reference.json"

def load_calibration(path=REFERENCE, *, aircraft_revision=None, fuel_kg=None):
    """Return verified advisory data. Fail closed on unknown revision or fuel state."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("source") != "evidence/ARGON_CALIBRATION_REPORT.md":
        raise ValueError("Unrecognised calibration source")
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported calibration schema")
    revisions = data.get("compatible_revisions")
    if not isinstance(revisions, list) or not revisions or not all(isinstance(x,str) for x in revisions):
        raise ValueError("Invalid revision coverage")
    if aircraft_revision is None or aircraft_revision not in revisions:
        raise ValueError("Aircraft revision not verified against calibration")
    table = data.get("hover_by_fuel_kg", {})
    if fuel_kg is None or isinstance(fuel_kg,bool) or not isinstance(fuel_kg,(int,float)) or not math.isfinite(fuel_kg):
        raise ValueError("Fuel state not verified")
    key = str(int(fuel_kg)) if float(fuel_kg).is_integer() else str(fuel_kg)
    if key not in table:
        raise ValueError("No measured calibration for this fuel state; interpolation not authorised")
    row = table[key]
    if len(row.get("collective_deg",[])) != 4:
        raise ValueError("Invalid four-rotor trim")
    for val in [row.get("rpm"),row.get("shaft_kw"),*row["collective_deg"]]:
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val):
            raise ValueError("Nonfinite calibration value")
    return {"source":data["source"],"schema_version":1,"aircraft_revision":aircraft_revision,
            "fuel_kg":fuel_kg,"hover":row,"rotor_order":data["rotor_order"],
            "control_gains":data["control_gains"],"advisory_only":True,
            "limitations":data["limitations"]}
