"""ECU command against actuator response, rates, forces, power and energy from test-run telemetry.
    python evidence/phantom/a10c_airbrake_ecu_20261118/scripts/actuator_power_summary.py runs/r5_reference_on.json.gz ...
One JSON line per run."""
import gzip, json, sys
from pathlib import Path
import numpy as np

for path in sys.argv[1:]:
    d = json.load(gzip.open(path)); L = d['log']
    def pair(cmd, act):
        e = np.array([np.subtract(r[cmd], r[act]) if isinstance(r[act], list) else [r[cmd] - r[act]] for r in L if r[cmd] is not None])
        return dict(max=round(float(np.abs(e).max()), 2), rms=round(float(np.sqrt((e ** 2).mean())), 2))
    out = dict(run=Path(path).name)
    out['pod_tilt_deg'] = pair('tilt_cmd', 'tilt')
    out['aileron_deg'] = pair('ail_cmd', 'ail')
    out['canard_deg'] = pair('canard_cmd', 'canard')
    out['fan_thrust_n'] = pair('fan_Tcmd', 'fan_T')
    st = [(r['stab_ab_cmd'], r['stab']) for r in L if r['stab_ab_cmd']]
    out['stab_airbrake_cmd_max_deg'] = round(max(s[0] for s in st), 1) if st else None
    out['power_max_kw'] = round(max((r['delivered_w'] or 0) for r in L) / 1e3)
    out['generator_max_kw'] = round(max((r['gen_w'] or 0) for r in L) / 1e3)
    out['soc'] = [round(L[0]['soc'], 3), round(L[-1]['soc'], 3)]
    hover = [r for r in L if r['t'] > L[-1]['t'] - 10]
    out['hover_power_kw_mean_last10s'] = round(float(np.mean([(r['delivered_w'] or 0) for r in hover])) / 1e3)
    out['soc_rate_per_min_last10s'] = round((hover[-1]['soc'] - hover[0]['soc']) / (hover[-1]['t'] - hover[0]['t']) * 60, 4)
    out['fuel_kg'] = round(L[0]['fuel_kg'] - L[-1]['fuel_kg'], 2)
    out['max_abs_rates_deg_s'] = dict(p=round(max(abs(r['p']) for r in L), 1), q=round(max(abs(r['q']) for r in L), 1), r=round(max(abs(r['r']) for r in L), 1))
    out['max_abs_aero_moment_nm'] = [round(max(abs(r['aero_M'][i]) for r in L)) for i in range(3)]
    out['max_aero_drag_n'] = round(-min(r['aero_F'][0] for r in L))
    out['max_fan_ram_drag_n'] = round(max(sum(r['ram']) for r in L))
    print(json.dumps(out))
