"""Instrument-only closed-loop waypoint pilot for the R6 research simulator."""
import math

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def navigate(obs, destination, hover, *, target_altitude=8.0):
    """Compute one bounded command from measured state; no position teleportation."""
    xy = obs["gnss_xy_m"]
    vel = obs["gnss_velocity_mps"]
    altitude = obs["radar_clearance_m"]
    if altitude is None:
        raise ValueError("No radar clearance: navigation unavailable")
    attitude = obs["attitude_xyz_deg"]
    rates = obs["gyro_world_deg_s"]
    if any(not math.isfinite(float(v)) for v in [*xy,*vel,altitude,*attitude,*rates,*destination]):
        raise ValueError("Nonfinite instrument reading")
    # Hold horizontal translation until safely above the departure surface.
    dx, dy = destination[0]-xy[0], destination[1]-xy[1]
    dist = math.hypot(dx, dy)
    travel = altitude >= target_altitude-1.0
    vx = clamp(dx*0.08, -1.2, 1.2) if travel else 0.0
    vy = clamp(dy*0.08, -1.2, 1.2) if travel else 0.0
    ax = clamp((vx-vel[0])*0.45, -0.6, 0.6)
    ay = clamp((vy-vel[1])*0.45, -0.6, 0.6)
    # Rotor axis vectors in the body frame. Small-angle tilt is capped.
    tx = clamp(math.degrees(math.atan2(ax, 9.81)), -3.5, 3.5)
    ty = clamp(math.degrees(math.atan2(ay, 9.81)), -3.5, 3.5)
    # Calibration is a reference, not a guarantee: damp climb and descent.
    vz_target = clamp((target_altitude-altitude)*0.22, -0.35, 0.5)
    collective_adjust = clamp((vz_target-vel[2])*0.7, -1.3, 1.3)
    base = [clamp(float(c)+collective_adjust, 0, 30) for c in hover]
    # Conservative differential trim opposes roll/pitch and their rates.
    roll = clamp(-0.06*attitude[0]-0.025*rates[0], -1.2, 1.2)
    pitch = clamp(-0.06*attitude[1]-0.025*rates[1], -1.2, 1.2)
    collective = [clamp(base[0]+roll,0,30), clamp(base[1]+pitch,0,30),
                  clamp(base[2]-roll,0,30), clamp(base[3]-pitch,0,30)]
    return dict(engine=1.0, collective_deg=collective,
                tilt_deg=[[tx,ty] for _ in range(4)],
                cabin_deg=[0.0,0.0,0.0], cabin_level=True), dist
