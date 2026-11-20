"""Check whether the probe's high-wind cases leave the water / depart (offline, isolated fixture)."""
import math
import sys

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet, DT  # noqa: E402

BOAT = 'ricochet-airport'
for v, thr, surf in ((35.0, 1.0, dict(rudder_deg=30.0)), (50.0, 1.0, dict(rudder_deg=30.0)),
                     (65.0, 0.0, dict(aileron_deg=-25.0)), (65.0, 0.0, dict())):
    fleet = HarbourFleet(harbour_world())
    fleet.release(BOAT)
    c = fleet.crafts[BOAT]
    fleet.action(BOAT, dict(throttle=thr, **surf))
    z0 = None
    worst = dict(dz=0.0, roll=0.0, pitch=0.0, yaw=0.0, beta=0.0)
    for i in range(int(round(3.0 / DT))):
        c.set_wind([-v, 0.0, 0.0])
        fleet.step()
        s = c.control_surface_telemetry  # noqa: F841 (touch API)
        qp = c.data.qpos[:7]
        if z0 is None:
            z0 = float(qp[2])
        w, x, y, zq = (float(t) for t in qp[3:7])
        roll = math.degrees(math.atan2(2 * (w * x + y * zq), 1 - 2 * (x * x + y * y)))
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (w * y - zq * x)))))
        yaw = math.degrees(math.atan2(2 * (w * zq + x * y), 1 - 2 * (y * y + zq * zq)))
        for k, val in (('dz', float(qp[2]) - z0), ('roll', roll), ('pitch', pitch), ('yaw', yaw)):
            if abs(val) > abs(worst[k]):
                worst[k] = round(val, 2)
    print(f'V={v} thr={thr} {surf}: max dz={worst["dz"]} m roll={worst["roll"]} pitch={worst["pitch"]} yaw={worst["yaw"]} deg; crashed={c.crashed} flags={sorted(c.flags)}', flush=True)
