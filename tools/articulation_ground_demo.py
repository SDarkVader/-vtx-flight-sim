"""User-requested ground-only fan articulation demonstration.

This is a bounded actuator test, not a pilot or a flight controller. It sends
ordinary controls, records its decisions through the live API, and stops if
manual authority is taken, the simulation pauses, or the gear unloads.
"""
import argparse,json,math,time,urllib.error,urllib.request


def call(base,path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)


def run(base,duration=12.,radius=18.):
    first=call(base,'/api/observe')
    if not first['active'] or first['paused'] or first['authority']!='colin':raise RuntimeError('Colin must hold an active, unpaused ground test')
    start=first['t_s'];last_sent=-1.;phase=[90.,0.,270.,180.];sense=[1,-1,1,-1]
    while True:
        obs=call(base,'/api/observe')
        if not obs['active'] or obs['paused'] or obs['authority']!='colin':
            print('STOP: authority, pause, or active state changed',flush=True);return
        if min(obs['gear_compression_m'])<.005 or abs(obs['gnss_velocity_mps'][2])>.2 or math.hypot(*obs['gnss_velocity_mps'][:2])>.5:
            print('STOP: ground-support or speed guard',json.dumps(obs),flush=True);return
        if 'IMPACT' in obs['warning_lamps']:
            print('STOP: impact',flush=True);return
        elapsed=obs['t_s']-start
        if elapsed>=duration:break
        if obs['t_s']-last_sent>=.08:
            vectors=[]
            for a,direction in zip(phase,sense):
                angle=math.radians(a+direction*30*elapsed)
                vectors.append([radius*math.cos(angle),radius*math.sin(angle)])
            body=dict(authority='colin',observation_id=obs['observation_id'],
                reason='Operator-requested ground-only continuous fan articulation check; alternate directions, zero collective.',
                engine=1,collective_deg=[0]*4,tilt_deg=vectors,cabin_deg=[0,0,180],cabin_level=True)
            call(base,'/api/action',body);last_sent=obs['t_s']
        time.sleep(.25)
    obs=call(base,'/api/observe')
    if obs['active'] and not obs['paused'] and obs['authority']=='colin':
        call(base,'/api/action',dict(authority='colin',observation_id=obs['observation_id'],
            reason='One ground-only articulation revolution completed; hold the four tilted fans at their final directions.',
            engine=1,collective_deg=[0]*4,tilt_deg=vectors,cabin_deg=[0,0,180],cabin_level=True))
    print('DONE',json.dumps({'simulated_seconds':elapsed,'last_observation':obs['observation_id']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8765');p.add_argument('--duration',type=float,default=12.);p.add_argument('--radius',type=float,default=18.)
    a=p.parse_args();run(a.base,a.duration,a.radius)
