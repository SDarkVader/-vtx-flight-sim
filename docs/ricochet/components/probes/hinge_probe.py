"""Offline probe: unclipped Ricochet hinge moments vs airspeed, full deflection, fans idle/full.

Runs the real Concept A plant inside the isolated test harbour fixture; never touches live data.
Airspeed is imposed as a headwind (wind = -V along the boat's +X), so the hull stays near rest.
"""
import json
import sys
import time

sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/tests')
from test_harbour_fleet import harbour_world  # noqa: E402
from vtx.harbour_fleet import HarbourFleet  # noqa: E402

BOAT = 'ricochet-airport'
CASES = {
    'rudder+30': dict(rudder_deg=30.0),
    'rudder-30': dict(rudder_deg=-30.0),
    'elevator+20': dict(elevator_deg=20.0),
    'elevator-20': dict(elevator_deg=-20.0),
    'aileron+25': dict(aileron_deg=25.0),
    'aileron-25': dict(aileron_deg=-25.0),
}
rows = []
t0 = time.time()
for v in (0.0, 20.0, 35.0, 50.0, 65.0):
    for throttle in (0.0, 1.0):
        for name, surf in CASES.items():
            fleet = HarbourFleet(harbour_world())
            assert fleet.release(BOAT)['ok']
            craft = fleet.crafts[BOAT]
            fleet.action(BOAT, dict(throttle=throttle, **surf))
            peak = {}
            steps = int(round(3.0 / fleet_dt)) if (fleet_dt := getattr(sys.modules['vtx.harbour_fleet'], 'DT')) else 300
            for i in range(steps):
                craft.set_wind([-v, 0.0, 0.0])
                fleet.step()
                for k, hm in craft.last_aero_detail.get('hinge_moments', {}).items():
                    if abs(hm) > abs(peak.get(k, 0.0)):
                        peak[k] = hm
            surf_t = craft.control_surface_telemetry()
            rows.append(dict(
                airspeed_mps=v, throttle=throttle, case=name,
                peak_hinge_moment_nm=peak,
                final_hinge_moment_nm=craft.last_aero_detail.get('hinge_moments', {}),
                achieved_deg={k: surf_t[k].get('achieved_deg') for k in ('rudder', 'elevator', 'aileron')},
                fan_rpm=[round(x, 1) for x in craft.last_fan_rpm],
                thrust_n=[round(x, 1) for x in craft.last_thrust_per_fan_n],
            ))
            print(f'{v:5.1f} m/s thr={throttle} {name:12s} peak={ {k: round(x, 1) for k, x in peak.items()} }', flush=True)
json.dump(dict(dt=fleet_dt, rows=rows, wall_s=round(time.time() - t0, 1)), open(sys.argv[2], 'w'), indent=1)
