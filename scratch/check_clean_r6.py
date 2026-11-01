import json
import numpy as np

L5 = json.loads(open("evidence/source/airframe_ledger.json").read())["parts"]
by_name = {p["name"]: p for p in L5}

for name in [
    "P03 | Four way reduction gearbox",
    "V2 P03 | Power turbine flexible coupling (schematic)",
    "V2 P03 | Transmission input flexible guard",
    "P01 | Turbine heat shielding",
    "P01 | M250 C30P class turboshaft schematic",
    "P01 | Compressor shell",
    "P01 | Mount A",
    "P01 | Mount B",
    "V2 P07 | Central fuel-feed manifold (schematic)",
    "P05 | Outer pitch ring YZ",
    "P05 | Inner roll ring XZ",
    "P04 | CFRP lower spherical sandwich",
]:
    p = by_name[name]
    print(f"{name:52s} | bounds={np.round(p['bounds_m'], 3).tolist()}")
