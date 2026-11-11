"""Persistent Phantom pilot link (keep-alive). Never invents flight setpoints.

Every command comes from tools/phantom/phantom_pilot_controls.json, written by the human or AI pilot.
The link only (re)sends that command through /api/action (schema phantom-fbw-1):
  * immediately when 'serial' changes, and
  * every 'keepalive_s' (< the 5 s command lease) while 'armed' is true and 'arm_run_id' matches the active run.
When disarmed, the run changes, or the file is invalid, nothing is sent and the simulator's own lease
failsafe (an explicit ABORT event) takes over. A 'pti' block is sent once per serial, never repeated.
Default server 127.0.0.1:8766; port 8765 is refused.

  python tools/phantom/phantom_persistent_pilot.py [--controls tools/phantom/phantom_pilot_controls.json] [--once]
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
    last_serial = None; last_sent = 0.0
    while True:
        try:
            c = json.loads(Path(a.controls).read_text())
            obs = call('/api/observe')
            run = call('/api/view').get('run_id')
            due = c.get('serial') != last_serial or time.monotonic() - last_sent >= min(4.0, float(c.get('keepalive_s', 1.0)))
            if c.get('armed') and c.get('arm_run_id') == run and obs.get('active') and due:
                p = dict(schema='phantom-fbw-1', authority=obs.get('authority', 'manual'), observation_id=obs['observation_id'],
                         reason=(c.get('reason') or 'keep-alive')[:2000], **c.get('command', {}))
                if c.get('pti') and c.get('serial') != last_serial:
                    p['pti'] = c['pti']
                r = call('/api/action', p)
                print(json.dumps(dict(t=obs.get('t_s'), serial=c.get('serial'), accepted=r.get('sequence', r))), flush=True)
                last_serial = c.get('serial'); last_sent = time.monotonic()
        except (HTTPError, URLError, ValueError, KeyError, OSError) as e:
            print('link:', type(e).__name__, str(e)[:200], flush=True)
        if a.once:
            break
        time.sleep(0.1)


if __name__ == '__main__':
    main()
