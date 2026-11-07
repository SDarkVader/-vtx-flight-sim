"""Post-flight analysis (evidence only, never used for piloting). Reads run folders' phantom_steps.csv.gz + events.jsonl.
python analyse.py RUN_ID [RUN_ID...] -> prints JSON; writes analysis_<run>.json"""
import csv, gzip, json, sys, zlib
from pathlib import Path
import numpy as np
BASE = Path(__file__).parent / 'evidence/flights'


def rows(run):
    out = []
    try:
        for d in csv.DictReader(gzip.open(BASE / run / 'phantom_steps.csv.gz', 'rt')):
            out.append(d)
    except (EOFError, zlib.error, OSError):
        pass
    return out


def num(rs, k):
    a = []
    for r in rs:
        try: a.append(float(r[k]))
        except (ValueError, KeyError, TypeError): a.append(np.nan)
    return np.array(a)


def analyse(run):
    rs = rows(run); ev = [json.loads(l) for l in open(BASE / run / 'events.jsonl')]
    t = num(rs, 't'); res = dict(run=run, samples=len(rs))
    if not len(rs): return res
    m = num(rs, 'mass_kg'); g = 9.80665
    T = sum(num(rs, f'T_{k}') for k in ('FL', 'FR', 'RL', 'RR')); Tf = num(rs, 'T_FL') + num(rs, 'T_FR')
    P = num(rs, 'gen_w') + num(rs, 'buffer_w'); z = num(rs, 'z'); vz = num(rs, 'vz_world'); sup = num(rs, 'support')
    coll = num(rs, 'coll_applied')
    # trim windows: airborne, |vz|<0.1, no PTI, 3 s stable
    pti = np.array([r.get('pti_axis') not in ('', 'None', None) for r in rs])
    ok = (sup == 0) & (np.abs(vz) < 0.1) & ~pti
    trims = []
    i = 0
    while i < len(t):
        if ok[i]:
            j = i
            while j < len(t) and ok[j]: j += 1
            if t[j - 1] - t[i] >= 3:
                s = slice(i, j)
                trims.append(dict(t0=round(t[i], 2), t1=round(t[j - 1], 2), height_m=round(float(np.nanmean(z[s])), 2), mass_kg=round(float(np.nanmean(m[s])), 1),
                                  collective_applied=round(float(np.nanmean(coll[s])), 4), thrust_total_n=round(float(np.nanmean(T[s])), 0),
                                  T_over_W=round(float(np.nanmean(T[s] / (m[s] * g))), 4), front_share=round(float(np.nanmean(Tf[s] / T[s])), 4),
                                  elec_power_kw=round(float(np.nanmean(P[s])) / 1e3, 1), P_over_T15=round(float(np.nanmean(P[s] / T[s] ** 1.5)), 5),
                                  W_per_N=round(float(np.nanmean(P[s] / T[s])), 2), gef_FL=round(float(np.nanmean(num(rs, 'gef_FL')[s])), 4),
                                  soc_rate_per_s=round(float((num(rs, 'soc')[j - 1] - num(rs, 'soc')[i]) / (t[j - 1] - t[i])), 6),
                                  pitch_deg=round(float(np.nanmean(num(rs, 'pitch_up_deg')[s])), 2), roll_deg=round(float(np.nanmean(num(rs, 'roll_deg')[s])), 2),
                                  pil_roll=round(float(np.nanmean(num(rs, 'pil_roll')[s])), 3), saturated_frac=round(float(np.mean([rs[k]['saturated'] == 'True' for k in range(i, j)])), 3)))
            i = j
        else:
            i += 1
    res['trim_points'] = trims
    # PTI responses
    p = num(rs, 'p_deg_s'); q = num(rs, 'q_up_deg_s'); r = -num(rs, 'r_left_deg_s'); ph = num(rs, 'roll_deg'); th = num(rs, 'pitch_up_deg')
    pv = num(rs, 'pti_value'); pax = [x.get('pti_axis') for x in rs]
    out = []
    for e in ev:
        if e['kind'] == 'pti_event' and e['payload'].get('event') == 'pti_start':
            sp = e['payload']['spec']; t0 = e['payload']['t_s']; ax = sp['axis']
            s = (t >= t0) & (t <= t0 + {'step': 1, 'doublet': 2, '3211': 7}.get(sp['type'], 1) * sp['pulse_s'] + 3)
            if not s.any(): continue
            idx = np.where(s)[0]; tt = t[idx] - t0
            rate, att = {'roll': (p, ph), 'pitch': (q, th), 'yaw': (r, None), 'heave': (vz, None)}[ax]
            on = np.where(np.abs(pv[idx]) > 0)[0]
            first = idx[on[0]] if len(on) else idx[0]
            base = rate[first]; resp = rate[idx] - base
            sign = np.sign(sp['amplitude'])
            # delay: first time on-axis rate exceeds 10% of its peak in the commanded sense
            pk = np.nanmax(resp * sign)
            dl = tt[np.argmax(resp * sign > 0.1 * pk)] if pk > 0 else None
            acc = np.gradient(rate[idx], t[idx])
            d = dict(t0=round(t0, 2), axis=ax, type=sp['type'], amplitude=sp['amplitude'], pulse_s=sp['pulse_s'],
                     peak_rate=round(float(np.nanmax(np.abs(resp))), 2), peak_rate_units='deg/s' if ax != 'heave' else 'm/s',
                     peak_accel=round(float(np.nanmax(np.abs(acc[:int(0.6 / 0.01)]))), 1), delay_10pct_s=None if dl is None else round(float(dl), 3))
            if att is not None:
                d['peak_attitude_change_deg'] = round(float(np.nanmax(np.abs(att[idx] - att[first]))), 2)
                cmd = {'roll': 15, 'pitch': 10}[ax] * abs(sp['amplitude'])
                d['commanded_attitude_deg'] = cmd
                if sp['type'] == 'step':
                    hold = (tt > sp['pulse_s'] * 0.6) & (tt < sp['pulse_s'])
                    d['steady_attitude_deg'] = round(float(np.nanmean(att[idx][hold] - att[first])), 2)
                    d['steady_error_frac'] = round(1 - d['steady_attitude_deg'] / (cmd * np.sign(sp['amplitude'])), 3)
                    a90 = np.abs(att[idx] - att[first]) >= 0.632 * abs(d['steady_attitude_deg'])
                    d['time_constant_63pct_s'] = round(float(tt[np.argmax(a90)]), 3) if a90.any() else None
                off = {'roll': q, 'pitch': p}[ax]
                d['off_axis_ratio'] = round(float(np.nanmax(np.abs(off[idx] - off[first])) / max(d['peak_rate'], 1e-6)), 3)
            out.append(d)
    res['pti'] = out
    res['events'] = [e['payload'] for e in ev if e['kind'] in ('phantom_event', 'crash_capture', 'command_lease_expired')][:40]
    soc = num(rs, 'soc'); res['soc_start_end'] = [float(soc[0]), float(soc[-1])]; res['t_end'] = float(t[-1])
    res['max_height_m'] = float(np.nanmax(z)); res['saturation_time_s'] = float(np.sum([x['saturated'] == 'True' for x in rs]) * 0.01)
    return res


if __name__ == '__main__':
    for run in sys.argv[1:]:
        r = analyse(run); (Path(__file__).parent / f'analysis_{run}.json').write_text(json.dumps(r, indent=1, default=float)); print(json.dumps(r, default=float)[:4000])
