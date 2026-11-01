import urllib.request
import json
import time

def api(endpoint, data=None):
    url = f'http://127.0.0.1:8768{endpoint}'
    body = json.dumps(data).encode('utf-8') if data else None
    headers = {'Content-Type': 'application/json'} if data else {}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

print('Validating destination [-14, 222]...')
val = api('/api/validate?x=-14&y=222')
print('Validation result:', val)

if val['valid']:
    print('Starting sortie to Volcano Basement...')
    r = api('/api/mission', {
        'departure': [0, 0],
        'destination': [-14, 222],
        'authority': 'manual',
        'time_scale': 1.0,
        'stability_assist': 0.8,
        'reference_rpm': 1200,
        'gear_variant': 'critical-damping-proposal',
        'airframe_variant': 'light',
        'fuel_kg': 20.0,
        'engine_power_limit_kw': 300.0,
        'label': 'Sortie: VTX Flight Academy Stand 1 to Volcano Basement LZ'
    })
    print('Sortie started:', r)
    time.sleep(1.0)
    obs = api('/api/observe')
    print('Initial observation:', obs.get('gnss_xy_m'), 'radar alt:', obs.get('radar_clearance_m'))
else:
    print('Destination validation failed:', val['reason'])
