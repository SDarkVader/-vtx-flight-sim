import json
import numpy as np

for label, path in [("R5", "evidence/source/airframe_ledger.json"), ("R6", "evidence/source/airframe_ledger_r6.json")]:
    L = json.loads(open(path).read())
    print(f"=== {label} ({L['revision']}) ===")
    for p in sorted(L["parts"], key=lambda x: x["bounds_m"][0][2]):
        lo, hi = p["bounds_m"]
        if lo[2] < 0.65:
            print(
                f"  z=[{lo[2]:+.3f},{hi[2]:+.3f}] x=[{lo[0]:+.2f},{hi[0]:+.2f}] y=[{lo[1]:+.2f},{hi[1]:+.2f}] "
                f"| body={p['body']:8s} | {p['name']} | mats={p['materials']}"
            )
