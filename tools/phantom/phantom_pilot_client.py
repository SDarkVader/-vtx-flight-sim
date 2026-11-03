"""Phantom pilot client: one observation or one deliberate action per invocation. NO pilot loop.

Uses exactly the human interface endpoint (/api/action, schema phantom-fbw-1). Default server
127.0.0.1:8766 (never 8765). Examples:
  python tools/phantom/phantom_pilot_client.py observe
  python tools/phantom/phantom_pilot_client.py action --observation 12 --collective 0.55 \
      --mode attitude_vs --vs 0.5 --reason "Lift-off: VS hold 0.5 m/s"
  python tools/phantom/phantom_pilot_client.py action --observation 40 --pti pitch:doublet:0.1:1.0 --reason "PTI"
  python tools/phantom/phantom_pilot_client.py start --variant phantom-fx --load-state FX-C --time-scale 0.2
"""
import argparse, json, os, urllib.error, urllib.request

URL = os.environ.get('VTX_LAB_URL', 'http://127.0.0.1:8766').rstrip('/')
if URL.endswith(':8765'):
    raise SystemExit('Port 8765 is reserved; use 8766 for Phantom work')


def request(path, payload=None):
    req = urllib.request.Request(URL + path, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=15))
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code}: {e.read().decode()}')


def floats(s, n=None):
    v = [float(x) for x in s.split(',')]
    if n and len(v) == 1:
        v = v * n
    return v


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest='mode', required=True)
sub.add_parser('observe')
st = sub.add_parser('start')
st.add_argument('--variant', choices=['phantom', 'phantom-fx', 'phantom-a10', 'phantom-fx-a10'], default='phantom-fx'); st.add_argument('--load-state', choices=['nominal', 'FX-A', 'FX-C'])
st.add_argument('--departure', default='13.7,-28.4'); st.add_argument('--destination', default='-45,18'); st.add_argument('--time-scale', type=float, default=0.2)
st.add_argument('--authority', default='manual'); st.add_argument('--start-configuration', choices=['vtol', 'road'], default='vtol')
a = sub.add_parser('action')
a.add_argument('--observation', type=int, required=True); a.add_argument('--reason', required=True); a.add_argument('--authority', default='manual')
for f in ('engine', 'collective', 'pitch', 'roll', 'yaw'):
    a.add_argument('--' + f, type=float)
a.add_argument('--vs', type=float, help='vertical_speed_m_s (attitude_vs mode)')
a.add_argument('--mode', choices=['off', 'rate_damping', 'attitude', 'attitude_vs'])
a.add_argument('--pod-tilt'); a.add_argument('--legs'); a.add_argument('--brake'); a.add_argument('--wheel-drive'); a.add_argument('--boosters')
a.add_argument('--flap'); a.add_argument('--canard-pitch'); a.add_argument('--canard-fold', choices=['deployed', 'folded']); a.add_argument('--wing', choices=['hold', 'deploy', 'stow'])
a.add_argument('--pti', help='axis:type:amplitude:pulse_s  (type step|doublet|3211|sweep) or "abort"')
args = ap.parse_args()
if args.mode == 'observe':
    print(json.dumps(request('/api/observe'), indent=2))
elif args.mode == 'start':
    m = dict(departure=floats(args.departure), destination=floats(args.destination), authority=args.authority, airframe_variant=args.variant,
             time_scale=args.time_scale, phantom=dict(start_configuration=args.start_configuration, **({'load_state': args.load_state} if args.load_state else {})))
    print(json.dumps(request('/api/mission', m), indent=2))
else:
    p = dict(schema='phantom-fbw-1', authority=args.authority, observation_id=args.observation, reason=args.reason)
    for f in ('engine', 'collective', 'pitch', 'roll', 'yaw'):
        if getattr(args, f) is not None:
            p[f] = getattr(args, f)
    if args.vs is not None: p['vertical_speed_m_s'] = args.vs
    if args.mode: p['stability_mode'] = args.mode
    for k, f, n in (('pod_tilt', 'pod_tilt_deg', 4), ('legs', 'leg_extension_m', 4), ('brake', 'brake', 4), ('wheel_drive', 'wheel_drive', 4),
                    ('boosters', 'booster_throttle', 2), ('flap', 'flap_deg', 2), ('canard_pitch', 'canard_pitch_deg', 2)):
        if getattr(args, k):
            p[f] = floats(getattr(args, k), n)
    if args.canard_fold: p['canard_fold'] = args.canard_fold
    if args.wing: p['wing'] = args.wing
    if args.pti:
        if args.pti == 'abort':
            p['pti'] = dict(command='abort')
        else:
            ax, ty, amp, pulse = args.pti.split(':')
            p['pti'] = dict(axis=ax, type=ty, amplitude=float(amp), pulse_s=float(pulse))
    print(json.dumps(request('/api/action', p), indent=2))
