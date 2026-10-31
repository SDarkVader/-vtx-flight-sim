"""Advisory-only ECU screen. Does not issue or modify aircraft commands."""
import math


def evaluate(tilt_deg, fan_rpm, tilt_limit_deg=20.0, *, max_rpm=None):
    """Report individual geometry limits and group asymmetry without a control law.

    Four tilt pairs are X/Y components in degrees. 20 degrees is the requested
    resultant cone, not two independent +/-20 degree limits. max_rpm is optional
    and must come from an actual validated operating envelope.
    """
    if len(tilt_deg) != 4 or len(fan_rpm) != 4:
        raise ValueError('Exactly four fan tilts and speeds are required')
    if not math.isfinite(tilt_limit_deg) or tilt_limit_deg <= 0:
        raise ValueError('Tilt limit must be positive and finite')
    if max_rpm is not None and (not math.isfinite(max_rpm) or max_rpm <= 0):
        raise ValueError('Speed limit must be positive and finite')
    fans=[]
    for i, (tilt, rpm) in enumerate(zip(tilt_deg, fan_rpm), 1):
        if len(tilt) != 2 or not all(math.isfinite(v) for v in (*tilt, rpm)) or rpm < 0:
            raise ValueError('Invalid fan state')
        angle=math.hypot(*tilt)
        fans.append(dict(fan=i, tilt_deg=angle, tilt_outside_cone=angle > tilt_limit_deg,
                         speed_rpm=rpm, speed_above_limit=(rpm > max_rpm) if max_rpm is not None else None))
    return dict(mode='advisory only', fans=fans,
                speed_spread_rpm=max(fan_rpm)-min(fan_rpm),
                warnings=['Speed spread is informational: its safety depends on thrust, torque, tilt and aircraft state.',
                          'Sensor health, power, thermal limits, rates, stability and actuator failures are not evaluated.'])
