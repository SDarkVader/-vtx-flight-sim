"""Local shaft-speed regulator only; no aircraft state or flight policy."""
from __future__ import annotations
import math


class ShaftGovernor:
    """Proposed PI regulator with conditional anti-windup and bounded torque.

    Kp retains the prior180 Nm/(rad/s). Ti=2s is an explicit design choice,
    not a measured turbine response. The plant still imposes spool, torque,
    shaft-power and fuel limits. No attitude/navigation inputs are accepted.
    """
    def __init__(self,mode='pi',kp=180.,integral_time_s=2.):
        if mode not in ['pi','legacy-p']:raise ValueError('Unknown shaft governor')
        self.mode=mode;self.kp=kp;self.ki=kp/integral_time_s
        self.integral_nm=0.;self.telemetry={}

    def update(self,target_rad_s,speed_rad_s,torque_cap_nm,dt,powered):
        target_rad_s,speed_rad_s,torque_cap_nm,dt=map(float,
            [target_rad_s,speed_rad_s,torque_cap_nm,dt])
        values=[target_rad_s,speed_rad_s,torque_cap_nm,dt]
        if not all(math.isfinite(x) for x in values) or torque_cap_nm<0 or dt<=0:
            raise ValueError('Invalid governor inputs')
        error=target_rad_s-speed_rad_s
        # Proposed governor fuel-cut threshold, NOT a blade structural rating.
        # Only drive torque is removed; stored spin energy is never clipped.
        overspeed=target_rad_s>1. and speed_rad_s>1.01*target_rad_s
        cap=torque_cap_nm if powered and not overspeed else 0.
        if not powered:self.integral_nm=0.
        if self.mode=='pi' and powered:
            raw=self.kp*error+self.integral_nm
            # Integrate within authority, or when the error unwinds saturation.
            if 0<=raw<=cap or (raw>cap and error<0) or (raw<0 and error>0):
                self.integral_nm+=self.ki*error*dt
            self.integral_nm=max(0.,min(self.integral_nm,cap))
        else:self.integral_nm=0.
        raw=self.kp*error+self.integral_nm
        torque=max(0.,min(raw,cap))
        self.telemetry=dict(mode=self.mode,target_rad_s=target_rad_s,
            speed_error_rad_s=error,integral_nm=self.integral_nm,
            torque_request_nm=raw,torque_applied_nm=torque,
            torque_cap_nm=cap,saturated=raw<0 or raw>cap)
        self.telemetry['overspeed_fuel_cut']=overspeed
        return torque
