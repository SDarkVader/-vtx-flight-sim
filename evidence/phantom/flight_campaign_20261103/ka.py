"""Keep-alive link: while file ka_run.txt names the active run, sends an EMPTY phantom-fbw-1 action (all fields hold)
every ~1 s wall so a slow pilot does not trip the 5 s lease. Never sets any control value. Delete ka_run.txt to disarm."""
import json, time, urllib.request
from pathlib import Path
F = Path(__file__).with_name('ka_run.txt'); URL = 'http://127.0.0.1:8766'
def call(p, b=None):
    r = urllib.request.Request(URL + p, data=None if b is None else json.dumps(b).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=10))
while True:
    try:
        if F.exists():
            run = call('/api/view').get('run_id'); o = call('/api/observe')
            if o.get('active') and F.read_text().strip() == run:
                call('/api/action', dict(schema='phantom-fbw-1', authority='colin', observation_id=o['observation_id'], reason='keep-alive link: hold previous pilot command'))
    except Exception as e:
        print('ka', e, flush=True)
    time.sleep(1.0)
