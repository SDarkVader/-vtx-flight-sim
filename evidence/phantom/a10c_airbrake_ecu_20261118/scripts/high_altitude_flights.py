"""Read-only: list recorded flights (summary.json) above a height, newest data roots first.
    python evidence/phantom/a10c_airbrake_ecu_20261118/scripts/high_altitude_flights.py <data root> [...] [--min 800]"""
import glob, json, os, sys

args = sys.argv[1:]; floor = 800.0
if '--min' in args:
    i = args.index('--min'); floor = float(args[i + 1]); del args[i:i + 2]
seen = set(); rows = []
for root in args:
    for s in glob.glob(os.path.join(root, '**', 'summary.json'), recursive=True):
        if '.venv' in s or 'node_modules' in s:
            continue
        try:
            d = json.load(open(s, encoding='utf-8'))
        except Exception:
            continue
        alt = d.get('max_airframe_origin_altitude_m')
        if alt is None or alt < floor:
            continue
        run = os.path.basename(os.path.dirname(s)); fin = d.get('final') or {}
        key = (run, round(alt, 2))
        if key not in seen:
            seen.add(key)
            rows.append((alt, run, fin.get('variant') or (d.get('phantom') or {}).get('variant'), (fin.get('config_sha256') or '')[:8], d.get('outcome')))
for r in sorted(rows, reverse=True):
    print('%8.1f m  %s  %-28s %s  %s' % r)
