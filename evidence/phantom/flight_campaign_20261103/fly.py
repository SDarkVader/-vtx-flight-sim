"""Test-pilot stick helper (2026-11-03 campaign). One pilot decision per invocation.

Uses only the human interface: GET /api/observe, POST /api/action (schema phantom-fbw-1), /api/mission, /api/stop.
`act` sends ONE pilot command chosen by the pilot (the caller), then holds it (zero-order hold) for --hold sim
seconds by re-sending an empty "keep-alive hold" action (all fields = hold) so the 5 s lease is not tripped while the
pilot thinks. It never computes a control input itself. Observations seen during the hold are printed and logged.
  fly.py start '{"departure":[..],...}'
  fly.py act '{"stability_mode":"attitude_vs","collective":0.6,"vertical_speed_m_s":0.3}' "reason" --hold 3 --every 0.5
  fly.py obs | fly.py stop "reason" | fly.py validate x y variant
"""
import argparse, json, sys, time, urllib.request, urllib.error
from pathlib import Path
URL = 'http://127.0.0.1:8766'
LOG = Path(__file__).with_name('pilot_log.jsonl')


def call(path, payload=None):
    req = urllib.request.Request(URL + path, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e:
        return dict(http_error=e.code, detail=e.read().decode()[:500])


def log(kind, d):
    with LOG.open('a') as f:
        f.write(json.dumps(dict(kind=kind, wall=time.time(), **d)) + '\n')


def line(o):
    v = o.get('velocity_world_m_s', [0, 0, 0]); a = o.get('attitude_deg', {}); r = o.get('body_rates_deg_s', {})
    return (f"t={o.get('t_s'):7.2f} xy=({o['gnss_xy_m'][0]:7.2f},{o['gnss_xy_m'][1]:7.2f}) ralt={o.get('radar_altimeter_m')} baro={o.get('baro_m')} "
            f"v=({v[0]:+.2f},{v[1]:+.2f},{v[2]:+.2f}) att(r,p,y)=({a.get('roll'):+.1f},{a.get('pitch'):+.1f},{a.get('yaw'):+.1f}) "
            f"pqr=({r.get('p'):+.1f},{r.get('q'):+.1f},{r.get('r'):+.1f}) rpm={[int(x) for x in o['fan_rpm']]} gen={o['generator_kw']} buf={o['buffer_kw']} "
            f"soc={o['buffer_soc']} unmet={o['power_unmet_kw']} wow={o['weight_on_wheels']} oleo={o['leg_compression_m']} lamps={o['warning_lamps']} pti={bool(o['pti_active'])} act={o['active']}")


ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest='m', required=True)
st = s.add_parser('start'); st.add_argument('mission')
s.add_parser('obs')
sp = s.add_parser('stop'); sp.add_argument('reason')
va = s.add_parser('validate'); va.add_argument('x'); va.add_argument('y'); va.add_argument('variant')
ac = s.add_parser('act'); ac.add_argument('cmd'); ac.add_argument('reason'); ac.add_argument('--hold', type=float, default=1.0)
ac.add_argument('--every', type=float, default=0.5); ac.add_argument('--pti')
a = ap.parse_args()
if a.m == 'start':
    r = call('/api/mission', json.loads(a.mission)); log('start', dict(request=json.loads(a.mission), response={k: v for k, v in r.items() if k != 'observation'}))
    print(r.get('run_id'), r.get('http_error'), r.get('detail', ''))
    if 'observation' in r: print(line(r['observation']))
elif a.m == 'obs':
    o = call('/api/observe'); print(line(o)); print(json.dumps({k: o[k] for k in ('lease_remaining_s', 'time_scale', 'stability_mode', 'faults', 'fuel_kg', 'pod_tilt_deg', 'leg_extension_m')}))
elif a.m == 'stop':
    r = call('/api/stop', dict(reason=a.reason)); log('stop', r); print(json.dumps(r, default=str)[:1500])
elif a.m == 'validate':
    r = call(f'/api/validate?x={a.x}&y={a.y}&variant={a.variant}'); print(r.get('ok'), r.get('reason'), r.get('surface_z_m'))
else:
    cmd = json.loads(a.cmd); o = call('/api/observe')
    p = dict(schema='phantom-fbw-1', authority='colin', observation_id=o['observation_id'], reason=a.reason, **cmd)
    if a.pti:
        ax, ty, amp, pulse = a.pti.split(':'); p['pti'] = dict(axis=ax, type=ty, amplitude=float(amp), pulse_s=float(pulse))
    r = call('/api/action', p); log('decision', dict(obs=o, action=p, response=r)); print('ACTION', json.dumps(r)); print(line(o))
    t0 = o['t_s']; last_print = t0; last_ka = time.monotonic()
    while True:
        time.sleep(0.15)
        o = call('/api/observe')
        if 'http_error' in o or not o.get('active'):
            print('INACTIVE', json.dumps(o)[:300]); break
        if time.monotonic() - last_ka > 0.5 / max(1, 1) and o.get('lease_remaining_s', 5) < 4.0:
            call('/api/action', dict(schema='phantom-fbw-1', authority='colin', observation_id=o['observation_id'], reason='keep-alive hold (zero-order hold of previous pilot command)'))
            last_ka = time.monotonic()
        if o['t_s'] - last_print >= a.every:
            print(line(o)); log('hold_obs', dict(obs=o)); last_print = o['t_s']
        if 'IMPACT' in o['warning_lamps'] and o['t_s'] - t0 > 0.3:
            print('IMPACT LAMP'); print(line(o)); break
        if o['t_s'] - t0 >= a.hold:
            break
