import json, math, sys
sys.path.insert(0, 'src'); sys.path.insert(0, 'tools/phantom')
import phantom_campaign as C
from vtx.aircraft import DT
P6 = {"p6_drs_stabilator": {"v": 1.0}, "p5_canard_area_scale": {"v": 0.5}}
for tag, eng, inc in (('fj33_7', 2.0, 7.0), ('tj150_9', 1.0, 9.0)):
    ov = {"proposals": dict(P6, p7_booster_engine={"v": eng}, p8_wing_incidence_deg={"v": inc})}
    a = C.plant('phantom', ov, start_configuration='road')
    a.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
    a.set_command(dict(flap_deg=[30, 30], canard_pitch_deg=[0, 0])); C.run(a, 2.5)
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0], stability_mode='attitude', pitch=0.0))
    t0 = a.data.time; last = None; rot = False
    for i in range(int(60 / DT)):
        a.step()
        if not rot and a.vel_body()[0] >= 80: a.set_command(dict(pitch=0.3)); rot = True
        if a.crashed:
            s = C.snapshot(a)
            print(tag, 'CRASH at t=%.2f' % (a.data.time - t0), 'u=%.1f z=%.2f pitch=%.1f sup=%d' % (s['u'], s['z'], s['pitch_deg'], s['supports']))
            print('   last events:', json.dumps(a.events[-5:], default=float)[:900])
            print('   last 1 s before:', [(round(x['t'] - t0, 2), x['u'], x['pitch_deg'], x['supports'], round(x['z'], 3)) for x in last[-6:]] if last else None)
            break
        if i % 20 == 0:
            last = (last or []) + [C.snapshot(a)]; last = last[-30:]
    else:
        print(tag, 'no crash in 60 s')
