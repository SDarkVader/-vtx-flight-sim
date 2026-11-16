"""VTX pilot connection for any AI assistant (Model Context Protocol, stdio).

This is a thin door onto the simulator's existing pilot interface, the same one Colin's sessions used:
GET /api/pilot/status, GET /api/observe, POST /api/action, POST /api/pilot/handover, POST /api/objective.
It holds no aircraft state and runs no physics. Every command goes through the server's own authority,
run and schema checks, and is reported as applied only after the plant's telemetry is read back.

  set VTX_LAB_URL=http://127.0.0.1:8765          (default)
  set VTX_CLOUD_ACCESS_TOKEN=...                 (only if the simulator requires it)
  python tools/vtx_pilot_mcp.py                  (the AI client starts this; it speaks JSON-RPC on stdin/stdout)

Standard library only, so it can ship inside a packaged Windows build."""
from __future__ import annotations
import json, os, sys, time, uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = os.environ.get('VTX_LAB_URL', 'http://127.0.0.1:8765').rstrip('/')
TOKEN = os.environ.get('VTX_CLOUD_ACCESS_TOKEN', '')
PILOT_ID = os.environ.get('VTX_PILOT_ID') or 'ai-pilot-' + uuid.uuid4().hex[:6]
seat = dict(run_id=None, epoch=None)          # this process's ownership of the Colin seat, per flight
last_instruments = None

KEYS = ('t_s', 'gnss_xy_m', 'baro_m', 'radar_altimeter_m', 'airspeed_m_s', 'velocity_world_m_s', 'velocity_body_m_s', 'attitude_deg',
        'body_rates_deg_s', 'weight_on_wheels', 'fan_rpm', 'pod_tilt_deg', 'leg_extension_m', 'wing_state', 'flap_deg', 'canard_pitch_deg',
        'generator_kw', 'buffer_soc', 'fuel_kg', 'stability_mode', 'warning_lamps', 'faults', 'observation_id', 'run_id',
        'attitude_xyz_deg', 'gyro_body_deg_s', 'gnss_velocity_mps', 'radar_clearance_m', 'rotor_rpm', 'collective_feedback_deg')


def call(path, payload=None):
    headers = {'Content-Type': 'application/json'}
    if TOKEN:
        headers['Authorization'] = 'Bearer ' + TOKEN
    req = Request(URL + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    try:
        with urlopen(req, timeout=20) as r:
            return json.load(r)
    except HTTPError as e:
        body = e.read().decode(errors='replace')
        try:
            detail = json.loads(body).get('detail', body)
        except ValueError:
            detail = body
        raise RuntimeError(f'Simulator refused ({e.code}): {detail}')
    except (URLError, OSError) as e:
        raise RuntimeError(f'Simulator not reachable at {URL}: {e}')


def telemetry(o):
    return {k: o[k] for k in KEYS if k in o}


def status(_):
    v = call('/api/pilot/status')
    o = call('/api/observe')
    instrument_packet = remember(o)
    config = o.get('configuration') or {}
    ident = config.get('identity') or {}
    return dict(simulator=URL, run_id=v.get('run_id'), active=v.get('active'), paused=v.get('paused'), authority=v.get('authority'),
                pilot_owner=v.get('pilot_owner'), pilot_epoch=v.get('pilot_epoch'), this_pilot=PILOT_ID,
                this_pilot_holds_seat=bool(v.get('pilot_owner') == PILOT_ID), objective=v.get('objective'), mission=o.get('mission'),
                aircraft=dict(variant=config.get('airframe_variant'), config_sha256=config.get('config_sha256'),
                              **{k: ident[k] for k in ('name', 'git_commit', 'verified', 'status') if k in ident}),
                telemetry=instrument_packet)


def remember(observation):
    global last_instruments
    last_instruments = telemetry(observation)
    return last_instruments


def observe(_):
    return remember(call('/api/observe'))


def take_seat(a):
    """Become the Colin-seat pilot for the current flight (run-scoped handover; the previous owner is fenced off)."""
    v = call('/api/pilot/status')
    if not v.get('active'):
        raise RuntimeError('No flight is running. Ask the operator to start a mission in the cockpit.')
    if v.get('authority') != 'colin':
        if not a.get('request_authority'):
            raise RuntimeError("The manual operator holds authority. Ask the user; if they agree, call again with request_authority=true.")
        call('/api/operator', dict(authority='colin')); v = call('/api/pilot/status')
    r = call('/api/pilot/handover', dict(run_id=v['run_id'], pilot_id=PILOT_ID, expected_epoch=v.get('pilot_epoch', 0)))
    seat.update(run_id=v['run_id'], epoch=r.get('pilot_epoch', r.get('epoch')))
    return dict(seat='held', pilot_id=PILOT_ID, run_id=seat['run_id'], pilot_epoch=seat['epoch'], objective=r.get('objective'))


def command(a):
    """One phantom-fbw-1 action through /api/action, then telemetry read back after it is applied."""
    fields = dict(a['controls'])
    if not fields or fields.keys() - CONTROLS['properties'].keys():
        raise ValueError('Supply named aircraft controls for one command.')
    obs = last_instruments
    v = call('/api/pilot/status')
    if (not v.get('active') or v.get('paused') or v.get('authority') != 'colin' or
            seat['run_id'] != v['run_id'] or seat['epoch'] != v.get('pilot_epoch') or
            PILOT_ID not in (v.get('pilot_owner'), v.get('pending_pilot'))):
        raise RuntimeError('An active flight and the current pilot seat are required.')
    if (not obs or a.get('run_id') != v['run_id'] or obs.get('run_id') != v['run_id'] or
            a.get('observation_id') != obs['observation_id']):
        raise ValueError('Read current instruments and supply their run_id and observation_id.')
    act = dict(schema='phantom-fbw-1', authority='colin', expected_run_id=v['run_id'],
               observation_id=obs['observation_id'], reason=a['reason'][:2000], pilot_id=PILOT_ID,
               pilot_epoch=seat['epoch'], pilot_run_id=v['run_id'], **fields)
    t0 = time.perf_counter(); ack = call('/api/action', act)
    wait = float(a.get('observe_after_s', 1.0)); time.sleep(max(0.1, min(wait, 10.0)))
    after = observe({})
    return dict(accepted=True, sequence=ack.get('sequence'), apply_t_s=ack.get('apply_t_s'), accept_latency_ms=round((time.perf_counter() - t0 - max(0.1, min(wait, 10.0))) * 1000, 1),
                telemetry_before=obs, telemetry_after=after)


def objective(a):
    v = call('/api/pilot/status')
    return call('/api/objective', dict(text=a['text'], run_id=v.get('run_id')))


CONTROLS = dict(type='object', additionalProperties=False, description='phantom-fbw-1 fields; send only what should change, the simulator holds the rest.', properties=dict(
    engine=dict(type='number', minimum=0, maximum=1), collective=dict(type='number', minimum=0, maximum=1),
    vertical_speed_m_s=dict(type='number', minimum=-3, maximum=3, description='used in stability_mode attitude_vs'),
    pitch=dict(type='number', minimum=-1, maximum=1), roll=dict(type='number', minimum=-1, maximum=1), yaw=dict(type='number', minimum=-1, maximum=1, description='+1 = nose right; steers the front wheels on the road'),
    stability_mode=dict(type='string', enum=['off', 'rate_damping', 'attitude', 'attitude_vs']),
    pod_tilt_deg=dict(type='array', items=dict(type='number'), minItems=4, maxItems=4, description='0 = road, 90 = fans facing down'),
    leg_extension_m=dict(type='array', items=dict(type='number'), minItems=4, maxItems=4), wheel_drive=dict(type='array', items=dict(type='number'), minItems=4, maxItems=4),
    brake=dict(type='array', items=dict(type='number'), minItems=4, maxItems=4), booster_throttle=dict(type='array', items=dict(type='number'), minItems=2, maxItems=2),
    flap_deg=dict(type='array', items=dict(type='number'), minItems=2, maxItems=2), canard_pitch_deg=dict(type='array', items=dict(type='number'), minItems=2, maxItems=2),
    canard_fold=dict(type='string', enum=['deployed', 'folded']), wing=dict(type='string', enum=['hold', 'deploy', 'stow'])))
TOOLS = {
    'vtx_status': (status, 'Flight status: run ID, authority, who holds the pilot seat, aircraft identity and pinned physics configuration, and current telemetry. Call this first.', dict(type='object', properties={})),
    'vtx_observe': (observe, 'Fresh pilot-visible telemetry from the running physics (position, altitude, speed, attitude, fans, wings, power, warnings). Use it before and after every command; never report an outcome you have not observed.', dict(type='object', properties={})),
    'vtx_take_seat': (take_seat, 'Take the AI pilot seat for the current flight (run-scoped handover). If a human holds manual authority, ask them first and pass request_authority=true only with their agreement.', dict(type='object', properties=dict(request_authority=dict(type='boolean')))),
    'vtx_command': (command, 'Send one flight-control action to the aircraft and get telemetry from before and after it was applied. The simulator holds the last command, so the aircraft keeps flying between calls.', dict(type='object', required=['run_id', 'observation_id', 'controls', 'reason'], properties=dict(run_id=dict(type='string'), observation_id=dict(type='integer'), controls=CONTROLS, reason=dict(type='string', description='why, from the telemetry you observed'), observe_after_s=dict(type='number', minimum=0.1, maximum=10)))),
    'vtx_set_objective': (objective, "Record the user's current goal for the flight (kept across pilot reconnects and handovers). It is not a control command.", dict(type='object', required=['text'], properties=dict(text=dict(type='string')))),
}
INSTRUCTIONS = ("You are the pilot of the VTX Phantom in a live physics simulator. Talk with the user naturally. Fly only through these tools: "
                "observe, decide, command, then observe again and tell the user what the telemetry shows. Say a command was carried out only "
                "after telemetry confirms it. The aircraft keeps its last command while you talk.")


def handle(msg):
    m = msg.get('method'); p = msg.get('params') or {}
    if m == 'initialize':
        return dict(protocolVersion=p.get('protocolVersion', '2025-03-26'), capabilities=dict(tools={}), serverInfo=dict(name='vtx-pilot', version='1.0'), instructions=INSTRUCTIONS)
    if m == 'ping':
        return {}
    if m == 'tools/list':
        return dict(tools=[dict(name=n, description=d, inputSchema=s) for n, (_, d, s) in TOOLS.items()])
    if m == 'tools/call':
        fn = TOOLS.get(p.get('name'))
        if not fn:
            raise KeyError(p.get('name'))
        try:
            return dict(content=[dict(type='text', text=json.dumps(fn[0](p.get('arguments') or {})))], isError=False)
        except Exception as e:   # the model sees the simulator's own refusal text
            return dict(content=[dict(type='text', text=str(e))], isError=True)
    raise KeyError(m)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if 'id' not in msg:
            continue   # notification
        try:
            out = dict(jsonrpc='2.0', id=msg['id'], result=handle(msg))
        except KeyError as e:
            out = dict(jsonrpc='2.0', id=msg['id'], error=dict(code=-32601, message=f'Unknown method or tool: {e}'))
        sys.stdout.write(json.dumps(out) + '\n'); sys.stdout.flush()


if __name__ == '__main__':
    main()
