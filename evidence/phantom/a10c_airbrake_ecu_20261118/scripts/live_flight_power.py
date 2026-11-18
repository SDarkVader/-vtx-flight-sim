"""Read-only: altitude, vertical speed, fan thrust and tilt, generator, buffer, state of charge and unmet power from a
recorded live flight's step log (phantom_steps.csv.gz), at about 1 sample per 2.5 % of the flight.
    python evidence/phantom/a10c_airbrake_ecu_20261118/scripts/live_flight_power.py <flight folder> [...]"""
import csv, gzip, hashlib, math, sys
from pathlib import Path

for folder in sys.argv[1:]:
    log = Path(folder) / 'phantom_steps.csv.gz'
    rows = []
    with gzip.open(log, 'rt', encoding='utf-8') as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i % 40 == 0:
                rows.append(row)
    fl = lambda row, k: float(row[k]) if row.get(k) not in (None, '', 'None') else float('nan')
    print('==', Path(folder).name, 'step log sha256', hashlib.sha256(log.read_bytes()).hexdigest())
    for x in rows[::max(1, len(rows) // 40)] + [rows[-1]]:
        T = [fl(x, 'T_' + k) for k in ('FL', 'FR', 'RL', 'RR')]
        tilt = [abs(fl(x, 'tilt_' + k)) for k in ('FL', 'RL')]
        V = math.sqrt(fl(x, 'u') ** 2 + fl(x, 'v') ** 2 + fl(x, 'w') ** 2)
        print('t %7.1f z %7.1f vz %+6.2f V %5.1f pitch %+5.1f mode %-11s coll %.2f T %5.0f %5.0f %5.0f %5.0f tilt %3.0f %3.0f gen %5.0f kW buffer %+6.0f kW soc %.3f unmet %4.0f kW mass %6.1f' % (
            fl(x, 't'), fl(x, 'z'), fl(x, 'vz_world'), V, fl(x, 'pitch_up_deg'), x['mode'], fl(x, 'coll_applied'), *T,
            *[math.degrees(t) if t < 3.2 else t for t in tilt], fl(x, 'gen_w') / 1e3, fl(x, 'buffer_w') / 1e3, fl(x, 'soc'), fl(x, 'unmet_w') / 1e3, fl(x, 'mass_kg')))
    print('   max z %.1f' % max(fl(x, 'z') for x in rows))
