"""Conservative instrument-only waypoint controller for the R6 test aircraft."""
import math

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def command(obs):
    """Return controls from current instruments; no hidden physics state."""
    target = obs["mission"]["destination"]
    x, y = obs["gnss_xy_m"]
    vx, vy, vz = obs["gnss_velocity_mps"]
    alt = obs["radar_clearance_m"]
    roll, pitch, yaw = obs["attitude_xyz_deg"]
    wx, wy, wz = obs["gyro_world_deg_s"]
    rpm = min(obs["rotor_rpm"])
    if alt is None:
        raise ValueError("No terrain clearance measurement")
    if max(abs(roll), abs(pitch)) > 10 or max(abs(v) for v in (wx,wy,wz)) > 12:
        raise ValueError("Attitude guard")
    dx, dy = target[0]-x, target[1]-y
    distance = math.hypot(dx,dy)
    # Rotor spool-up precedes blade pitch; no full collective against stationary rotors.
    if rpm < 950:
        collective = 0.0
    else:
        # Provisional trim, bounded by vertical speed feedback.
        vertical_target = clamp((8.0-alt)*0.20, -0.35, 0.65)
        collective = clamp(12.0 + 1.8*(vertical_target-vz), 7.0, 16.0)
    # Translate only after gaining clearance; limit target speed to approach distance.
    if alt < 6 or rpm < 950:
        tx = ty = 0.0
    else:
        tx = clamp(dx*0.12, -1.0, 1.0)
        ty = clamp(dy*0.12, -1.0, 1.0)
    tilt_x = clamp(1.5*(tx-vx), -3.0, 3.0)
    tilt_y = clamp(1.5*(ty-vy), -3.0, 3.0)
    return dict(engine=1.0, collective_deg=[collective]*4,
                tilt_deg=[[tilt_x,tilt_y] for _ in range(4)],
                cabin_deg=[0.0,0.0,0.0], cabin_level=True), distance
