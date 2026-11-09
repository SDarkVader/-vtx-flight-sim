import json, os, tempfile
from vtx.live_server import Laboratory, Mission
from vtx.phantom.controls import PhantomAction

with tempfile.TemporaryDirectory(prefix='vtx-flat-run-') as root:
    os.environ['VTX_DATA_ROOT'] = root
    lab = Laboratory()
    lab.start(Mission(airframe_variant='phantom-fx', phantom={'start_configuration': 'road'}))
    obs = lab.sensor_observation()
    lab.accept_action(PhantomAction(schema='phantom-fbw-1', authority='manual', observation_id=obs['observation_id'],
        reason='Isolated test of flat runway acceleration', wing='deploy', canard_fold='deployed'))
    p = lab.aircraft
    while p.data.time < 10 and not p.crashed:
        lab.integrate()
    obs = lab.sensor_observation()
    lab.accept_action(PhantomAction(schema='phantom-fbw-1', authority='manual', observation_id=obs['observation_id'],
        reason='Accelerate along flat runway', engine=1, booster_throttle=[1, 1], wheel_drive=[1]*4, brake=[0]*4, flap_deg=[20, 20]))
    max_speed = 0
    while p.data.time < 55 and not p.crashed:
        lab.integrate()
        speed = float((p.data.qvel[:2] ** 2).sum() ** .5)
        max_speed = max(max_speed, speed)
        if speed >= 70:
            break
    obs = lab.sensor_observation()
    lab.accept_action(PhantomAction(schema='phantom-fbw-1', authority='manual', observation_id=obs['observation_id'],
        reason='Attempt takeoff rotation at 70 metres per second', stability_mode='attitude', pitch=.8))
    takeoff_x = float(p.data.qpos[0])
    for _ in range(2000):
        lab.integrate()
        if p.crashed or p.data.qpos[0] > 1550:
            break
    print(json.dumps({'speed_m_s': max_speed, 'position_m': p.data.qpos[:3].tolist(), 'time_s': float(p.data.time),
                      'rotation_x': takeoff_x, 'airborne': bool(p.airborne), 'vertical_velocity': float(p.data.qvel[2]),
                      'crashed': bool(p.crashed), 'wing': p.wing_state, 'events': p.events[-5:]}))
    lab.stop('Isolated runway test complete')
