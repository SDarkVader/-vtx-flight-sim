"""Run-aware Phantom pilot link: send changed, explicitly armed commands once.

Commands are held by the simulator until changed. Disconnection or disarming
never triggers an automatic cut or a replacement flight. Manual control and
explicitly owned pilot sessions are not overridden by this legacy bridge.
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
URL = os.environ.get('VTX_LAB_URL', 'http://127.0.0.1:8766').rstrip('/')


def call(path, payload=None):
    req = Request(URL + path, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=10) as r:
        return json.load(r)


def main():
    # The unified cockpit can also run Phantom on 8765. Never infer aircraft
    # type from the port; verify the observed aircraft before each action.
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--controls', default=str(ROOT / 'tools/phantom/phantom_pilot_controls.json'))
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--health', action='store_true', help='Read-only connection and aircraft check')
    a = ap.parse_args()
    if a.health:
        view = call('/api/view')
        variant = ((view.get('observation') or {}).get('configuration') or {}).get('airframe_variant')
        print(json.dumps({'connected': True, 'variant': variant, 'active': view.get('active'),
                          'authority': view.get('authority'), 'phantom_bridge_compatible':
                          isinstance(variant, str) and variant.startswith('phantom')}), flush=True)
        return
    last_action_key = None
    while True:
        try:
            c = json.loads(Path(a.controls).read_text(encoding='utf-8-sig'))
            view = call('/api/view')
            run = view.get('run_id')
            action_key = (run, c.get('serial'))
            variant = ((view.get('observation') or {}).get('configuration') or {}).get('airframe_variant')
            # For the unified endpoint, refuse any control if R6 (or an unknown
            # airframe) is selected. Preserve historical 8766 bridge semantics.
            aircraft_ok = (not URL.endswith(':8765') or
                           (isinstance(variant, str) and variant.startswith('phantom')))
            if (c.get('armed') and aircraft_ok and c.get('arm_run_id') == run and view.get('active')
                    and not view.get('paused') and view.get('authority') == 'colin'
                    and view.get('pilot_owner') is None and not view.get('pilot_epoch', 0)
                    and action_key != last_action_key):
                obs = call('/api/observe')
                p = dict(schema='phantom-fbw-1', authority='colin', expected_run_id=run, observation_id=obs['observation_id'],
                         reason=(c.get('reason') or 'Pilot command')[:2000], **c.get('command', {}))
                if c.get('pti'):
                    p['pti'] = c['pti']
                r = call('/api/action', p)
                print(json.dumps(dict(t=obs.get('t_s'), serial=c.get('serial'), accepted=r.get('sequence', r))), flush=True)
                last_action_key = action_key
        except (HTTPError, URLError, ValueError, KeyError, OSError) as e:
            print('link:', type(e).__name__, str(e)[:200], flush=True)
        if a.once:
            break
        time.sleep(0.1)


if __name__ == '__main__':
    main()
