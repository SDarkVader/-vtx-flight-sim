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
    if URL.endswith(':8765'):
        raise SystemExit('Port 8765 is reserved; use 8766 for Phantom work')
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--controls', default=str(ROOT / 'tools/phantom/phantom_pilot_controls.json'))
    ap.add_argument('--once', action='store_true'); a = ap.parse_args()
    last_action_key = None
    while True:
        try:
            c = json.loads(Path(a.controls).read_text())
            view = call('/api/view')
            run = view.get('run_id')
            action_key = (run, c.get('serial'))
            if (c.get('armed') and c.get('arm_run_id') == run and view.get('active')
                    and not view.get('paused') and view.get('authority') == 'colin'
                    and view.get('pilot_owner') is None and not view.get('pilot_epoch', 0)
                    and action_key != last_action_key):
                obs = call('/api/observe')
                p = dict(schema='phantom-fbw-1', authority='colin', observation_id=obs['observation_id'],
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
