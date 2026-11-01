import json
import numpy as np

L5 = json.loads(open("evidence/source/airframe_ledger.json").read())["parts"]
by_name = {p["name"]: p for p in L5}

# Check bounds of LANDING leg1/4 parts near F1/F3 (x = +/- 1.86, y = 0):
for p in L5:
    if "LANDING leg1" in p["name"] or "LANDING leg4" in p["name"] or "P01 |" in p["name"] or "P11 |" in p["name"]:
        print(f"{p['name']:48s} | x={np.round([p['bounds_m'][0][0], p['bounds_m'][1][0]],3).tolist()} y={np.round([p['bounds_m'][0][1], p['bounds_m'][1][1]],3).tolist()} z={np.round([p['bounds_m'][0][2], p['bounds_m'][1][2]],3).tolist()}")
