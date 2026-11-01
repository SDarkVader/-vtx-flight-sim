import json

d = json.load(open('evidence/source/airframe_ledger.json'))
print("Overall keys:", list(d.keys()))
if 'parts' in d:
    all_lo = [999, 999, 999]
    all_hi = [-999, -999, -999]
    for p in d['parts']:
        lo, hi = p['bounds_m']
        for i in range(3):
            all_lo[i] = min(all_lo[i], lo[i])
            all_hi[i] = max(all_hi[i], hi[i])
    print(f"Overall bounds: X: [{all_lo[0]:.2f}, {all_hi[0]:.2f}] (width: {all_hi[0]-all_lo[0]:.2f}m)")
    print(f"                Y: [{all_lo[1]:.2f}, {all_hi[1]:.2f}] (length: {all_hi[1]-all_lo[1]:.2f}m)")
    print(f"                Z: [{all_lo[2]:.2f}, {all_hi[2]:.2f}] (height: {all_hi[2]-all_lo[2]:.2f}m)")
