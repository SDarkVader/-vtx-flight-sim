import json
import numpy as np

L5 = json.loads(open("evidence/source/airframe_ledger.json").read())["parts"]
by_name = {p["name"]: p for p in L5}

# Check what parts in R5 are near z=0.420m along the 4 branches:
for p in L5:
    lo, hi = p["bounds_m"]
    if lo[2] <= 0.50 and hi[2] >= 0.35:
        if any(k in p["name"] for k in ["P01", "P03", "P05", "P06", "P07", "P10", "P11"]):
            print(f"{p['name']:52s} | x=[{lo[0]:+.3f},{hi[0]:+.3f}] y=[{lo[1]:+.3f},{hi[1]:+.3f}] z=[{lo[2]:+.3f},{hi[2]:+.3f}]")
