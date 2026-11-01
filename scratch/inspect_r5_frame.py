import json

L5 = json.loads(open("evidence/source/airframe_ledger.json").read())["parts"]
for p in L5:
    if any(
        k in p["name"]
        for k in [
            "P01 |",
            "P03 |",
            "P05 |",
            "Central fuel-feed",
            "supply pipe",
            "actuator 1",
            "bearing at R",
            "lower impact pivot",
            "Turbine/gearbox lower cradle",
        ]
    ):
        lo, hi = p["bounds_m"]
        print(
            f"{p['name']:52s} | z=[{lo[2]:+.3f},{hi[2]:+.3f}] x=[{lo[0]:+.3f},{hi[0]:+.3f}] y=[{lo[1]:+.3f},{hi[1]:+.3f}]"
        )
