"""R5 (from R4): does the 4 Nov as-drawn campaign result survive the hub-motor power limit?
Same canned schedule as the campaign (takeoff_climb: flaps 30, rotate 70 m/s, attitude mode); as-drawn 'phantom'."""
import sys, json
sys.path.insert(0, sys.argv[1]); import camp_repo as C
from vtx.phantom import overlays
tag = sys.argv[2]
ov = None if tag == 'base' else overlays.load('wheel_drive_limits_v1')
r = C.takeoff_climb('phantom', ov)
m = C.flight_metrics(r.pop('trace'))
print(json.dumps(dict(tag=tag, **{k: r[k] for k in ('rotate_at_s', 'liftoff_t_s', 'liftoff_u_m_s', 'liftoff_ground_roll_m', 'airborne_s', 'max_height_m', 'pitch_range_deg', 'crashed')}, metrics=m), default=float))
