#!/usr/bin/env python3
"""Generate cloud CI artifacts. No calibrated aircraft flight is performed."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from vtx import physics_model as model
from vtx.urban_reference import make_scenario


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,default=ROOT/'results')
    args=ap.parse_args()
    out=args.out
    out.mkdir(exist_ok=True,parents=True)
    model.self_test()
    inputs=json.loads((ROOT/'inputs/vtx_calibration_required.json').read_text())
    try:
        model.validate_configuration(inputs)
    except ValueError as ex:
        calibration={'state':'CALIBRATION_BLOCKED','reason':str(ex),
                     'must_not_claim':'Measured VTX stability, flightworthiness or closed-loop controller success'}
    else:
        # Populated nominal schema alone still does not establish fidelity.
        calibration={'state':'INPUT_SCHEMA_PRESENT_NOT_CALIBRATED',
                     'reason':'Additional measured response data and time-domain validation required'}
    trajectories=[make_scenario(s) for s in (10.,20.,30.)]
    result={'status':'REFERENCE_ONLY',
            'model':'VTX-P0-V4 separate algebraic and planar kinematics screening',
            'source':'VTX_urban_reference_simulation.py and VTX_P0_V4_Physics_Model.py',
            'not_tested':['real rotor dynamics','passive stability','real CG/inertia','actuator delay','crosswinds',
                          'fault response','airworthiness'],
            'calibration':calibration,
            'scenarios':trajectories}
    (out/'reference_only.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'calibration_gate.json').write_text(json.dumps(calibration,indent=2)+'\n')
    print('REFERENCE_ONLY: 10, 20, 30 mph planar trajectories output')
    print('CALIBRATION GATE:',calibration['state'])
    print('Result files:',out.resolve())

if __name__=='__main__':
    main()
