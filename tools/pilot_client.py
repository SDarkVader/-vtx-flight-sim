"""One observation or one deliberate live action per invocation. NO pilot loop.

An observation cannot reveal simulator truth. Controls are exactly the same
JSON schema and HTTP endpoint as the human interface. No step/pose API exists.
"""
import argparse
import json
import urllib.request

URL='http://127.0.0.1:8765'

def request(path,payload=None):
    req=urllib.request.Request(URL+path,data=None if payload is None else json.dumps(payload).encode(),
                               headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=15))

ap=argparse.ArgumentParser(description=__doc__)
sub=ap.add_subparsers(dest='mode',required=True)
sub.add_parser('observe')
act=sub.add_parser('action');act.add_argument('--observation',type=int,required=True)
act.add_argument('--engine',type=float,required=True);act.add_argument('--collective',required=True)
act.add_argument('--tilt',default='0,0;0,0;0,0;0,0');act.add_argument('--reason',required=True)
args=ap.parse_args()
if args.mode=='observe':print(json.dumps(request('/api/observe'),indent=2))
else:
    payload=dict(authority='colin',observation_id=args.observation,engine=args.engine,
                 collective_deg=list(map(float,args.collective.split(','))),
                 tilt_deg=[list(map(float,t.split(','))) for t in args.tilt.split(';')],
                 cabin_deg=[0.,0.],reason=args.reason)
    print(json.dumps(request('/api/action',payload),indent=2))
