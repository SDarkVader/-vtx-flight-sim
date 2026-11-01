import json
import numpy as np

L5 = {p["name"]: p for p in json.loads(open("evidence/source/airframe_ledger.json").read())["parts"]}
L6 = {p["name"]: p for p in json.loads(open("evidence/source/airframe_ledger_r6.json").read())["parts"]}
for name, p6 in L6.items():
    p5 = L5.get(name)
    if not p5:
        continue
    b5 = np.array(p5["bounds_m"])
    b6 = np.array(p6["bounds_m"])
    s5 = b5[1] - b5[0]
    s6 = b6[1] - b6[0]
    c5 = np.array(p5["centroid_m"])
    c6 = np.array(p6["centroid_m"])
    if np.linalg.norm(s6 - s5) > 0.10 or b6[0, 2] < 0.05 or np.linalg.norm(c6 - c5) > 0.25:
        print(
            f"{name:55s} | body={p6['body']:8s} | z:[{b5[0,2]:+.3f},{b5[1,2]:+.3f}]->[{b6[0,2]:+.3f},{b6[1,2]:+.3f}] | "
            f"span:{np.round(s5,2).tolist()}->{np.round(s6,2).tolist()}"
        )
