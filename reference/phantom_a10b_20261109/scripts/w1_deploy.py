"""W1: wing deployment from a standing start with no brakes (full wheel drive + boosters), deploy commanded at a given
speed. Speed and dynamic pressure at each sequence step; peak q while the wing is in transit; model interlock events."""
import sys, json, math, numpy as np
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
v_cmd = float(sys.argv[2])
OV = overlays.load('hull_lift_v1', 'road_suspension_v1', 'wheel_drive_limits_v1', 'control_effectors_v1',
                   extra={'proposals': {'p6_drs_stabilator': {'v': 1.}, 'p8_wing_incidence_deg': {'v': 7.}}})
a = C.plant('phantom-fx', OV, start_configuration='road'); d = a.data; P = a.P
qlim = P.handover['control_limits']['wing_slide']['transit_q_limit_Pa']
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], canard_fold='deployed'))
t0 = float(d.time); st = dict(cmd=None); steps = []; prev = dict(a.wing_state); peak = dict(q=0.0, v=0.0)
def watch(a):
    u = float(a.vel_body()[0]); q = 0.5 * 1.225 * u * u; t = float(d.time) - t0
    if st['cmd'] is None and u >= v_cmd:
        st['cmd'] = (round(t, 2), round(u, 1)); a.set_command(dict(wing='deploy'))
    for s in ('left',):
        if a.wing_state[s] != prev[s]:
            steps.append((a.wing_state[s], round(t, 2), round(u, 1), round(q))); prev[s] = a.wing_state[s]
    if a.wing_state['left'] in ('hatch_opening', 'sliding_out', 'pinning'):
        if q > peak['q']: peak.update(q=round(q), v=round(u, 1))
    return a.wing_state['left'] == 'locked' or t > 60
C.run(a, 70, every=0.02, stop=watch)
ev = [e for e in a.events if e.get('event') in ('wing_transit_blocked_by_q',)]
print(json.dumps(dict(deploy_commanded_at=st['cmd'], steps=steps, peak_q_in_transit_pa=peak['q'], at_speed=peak['v'], q_limit_pa=qlim,
                      locked=a.wing_state['left'] == 'locked', interlock_events=ev[:2], flags=sorted(a.flags))))
