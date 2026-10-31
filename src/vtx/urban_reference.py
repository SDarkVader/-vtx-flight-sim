#!/usr/bin/env python3
"""VTX P0-V4 urban flight trajectory reference, 31 Oct 2026.

Reproducible reference-trajectory simulator. This solves kinematics only.
It does NOT model attitude dynamics, fan thrust maps, nacelle gyroscopic
moments, control delays, aircraft CG/inertia, wind or obstacle clearance.

Empirical screening targets (not certified aircraft limits):
  acceleration <= 0.8 m/s^2, resultant jerk <= 0.4 m/s^3.

For each selected peak speed, construct:
  1. jerk-limited S-curve launch along x
  2. constant-speed, quintic-curvature entry/exit into a 90-degree left turn
  3. jerk-limited S-curve braking along final heading.

Both launch and braking have two constant-jerk ramps, with a constant
acceleration plateau when required. Jerk has discontinuities at phase
boundaries (snap not limited); real control needs smoothing and tracking.
The curvature-ramp time uses a conservative bound on vector jerk.

Usage: python VTX_urban_reference_simulation.py
Output: VTX_urban_reference_results.json (same directory)
"""
from __future__ import annotations
import json
import math
from pathlib import Path

G = 9.80665
MPH_TO_MPS = 0.44704
A_MAX = 0.8
J_MAX = 0.4
DT = 0.005  # s, numerical integration step for corner


def smoothstep5(s: float) -> float:
    s = min(1.0, max(0.0, s))
    return 10*s**3 - 15*s**4 + 6*s**5


def smoothstep5_derivative(s: float) -> float:
    s = min(1.0, max(0.0, s))
    return 30*s*s - 60*s*s*s + 30*s**4


def from_rest(target_v: float) -> dict:
    if target_v <= 0:
        raise ValueError('target speed must be positive')
    ramp = A_MAX / J_MAX
    plateau = target_v / A_MAX - ramp
    if plateau < 0:  # triangular acceleration profile
        ramp = math.sqrt(target_v / J_MAX)
        plateau = 0.0
    duration = 2*ramp + plateau
    distance = target_v*duration/2
    return {'time_s': duration, 'distance_m': distance,
            'ramp_s': ramp, 'plateau_s': plateau,
            'max_acceleration_mps2': min(A_MAX, J_MAX*ramp),
            'max_jerk_mps3': J_MAX}


def turn_90(speed: float, sample_rate: float = DT) -> dict:
    if speed <= A_MAX*A_MAX/J_MAX:
        raise ValueError('speed too low for this quintic turn-ramp bound')
    omega = A_MAX/speed
    # Upper bound on jerk along rotating tangent/normal basis:
    # |da_normal/dt| <= (15/8)*A_MAX/T;
    # |a_normal * heading_rate| <= A_MAX^2 / speed.
    # Taking the Euclidean vector bound guarantees |jerk| <= J_MAX.
    in_plane_jerk = A_MAX*A_MAX/speed
    ramp = (15/8)*A_MAX/math.sqrt(J_MAX**2-in_plane_jerk**2)
    plateau = (math.pi/2)/omega - ramp
    if plateau < 0:
        raise ValueError('Cannot complete 90deg turn with a plateau at max acceleration; adjust turn planner')
    duration = 2*ramp + plateau

    def a_lat(t: float) -> tuple[float, float]:
        if t < ramp:
            s=t/ramp
            return A_MAX*smoothstep5(s), A_MAX*smoothstep5_derivative(s)/ramp
        if t <= ramp+plateau:
            return A_MAX, 0.0
        s=(t-ramp-plateau)/ramp
        return A_MAX*(1-smoothstep5(s)), -A_MAX*smoothstep5_derivative(s)/ramp

    # Midpoint integration of exact stated kinematics dx=v*cos(psi),
    # dy=v*sin(psi), dpsi=a_lat/v. This is not rotor dynamics.
    t=x=y=psi=0.0
    max_j=max_lat=max_rollrate=0.0
    samples=[{'t_s':0.0,'x_m':0.0,'y_m':0.0,'yaw_deg':0.0,
              'lateral_acceleration_mps2':0.0,'jerk_mps3':0.0,'cabin_lean_deg':0.0}]
    while t < duration-1e-11:
        step=min(sample_rate,duration-t)
        mid=t+step/2
        an,dan=a_lat(mid)
        psid=an/speed
        psi_mid=psi+0.5*psid*step
        x+=speed*math.cos(psi_mid)*step
        y+=speed*math.sin(psi_mid)*step
        psi+=psid*step
        jerk=math.hypot(dan,an*psid)
        roll_rate=abs(dan/G/(1+(an/G)**2))
        max_j=max(max_j,jerk)
        max_lat=max(max_lat,an)
        max_rollrate=max(max_rollrate,roll_rate)
        t+=step
        # Store at 100ms intervals and the exact final sample.
        if len(samples)==1 or t-samples[-1]['t_s']>=0.099999 or duration-t<1e-9:
            samples.append({'t_s':round(t,6),'x_m':round(x,6),
              'y_m':round(y,6),'yaw_deg':round(math.degrees(psi),6),
              'lateral_acceleration_mps2':round(an,6),
              'jerk_mps3':round(jerk,6),
              'cabin_lean_deg':round(math.degrees(math.atan(an/G)),6)})

    assert abs(math.degrees(psi)-90.0)<0.001
    assert max_j<=J_MAX+1e-8
    assert max_lat<=A_MAX+1e-8
    assert abs(x-y)<1e-3  # symmetric left-turn trajectory

    return {'time_s':duration,'distance_travelled_m':speed*duration,
            'steady_radius_m':speed*speed/A_MAX,
            'turn_entry_duration_s':ramp,'steady_corner_duration_s':plateau,
            'steady_heading_rate_degps':math.degrees(omega),
            'final_heading_deg':math.degrees(psi),'turn_dx_m':x,'turn_dy_m':y,
            'peak_total_jerk_mps3':max_j,'peak_lateral_acceleration_mps2':max_lat,
            'max_cabin_lean_deg':math.degrees(math.atan(A_MAX/G)),
            'max_cabin_lean_rate_degps':math.degrees(max_rollrate),
            'trace_100ms':samples}


def make_scenario(mph: float) -> dict:
    v=mph*MPH_TO_MPS
    start=from_rest(v)
    corner=turn_90(v)
    brake=from_rest(v)
    # 90-degree left turn from +x to +y. Start and stop vectors use the
    # local tangent; no physically fictitious instantaneous heading jump.
    final_x=start['distance_m']+corner['turn_dx_m']
    final_y=corner['turn_dy_m']+brake['distance_m']
    return {'speed_mph':mph,'speed_mps':v,'start':start,
            'turn_90_degrees':corner,'brake':brake,
            'route_total_time_s':start['time_s']+corner['time_s']+brake['time_s'],
            'route_length_m':start['distance_m']+corner['distance_travelled_m']+brake['distance_m'],
            'destination_m':{'x':final_x,'y':final_y,'height':'not modelled'},
            'vertical_acceleration_mps2':0.0,
            'reference_altitude_error_m':0.0}


def main():
    scenarios=[make_scenario(v) for v in [10.0,20.0,30.0]]
    result={'study':'VTX P0-V4 urban reference trajectory, planar kinematics',
       'date':'2026-10-31',
       'status':'REFERENCE TRAJECTORY ONLY — NOT CLOSED-LOOP AEROSPACE STABILITY',
       'limits':{'max_lateral_acceleration_mps2':A_MAX,
          'max_longitudinal_acceleration_mps2':A_MAX,
          'max_resultant_jerk_mps3':J_MAX,
          'max_total_acceleration_when_overlapping_axes_mps2':A_MAX,
          'gravity_mps2':G},
       'limitations':['CG and inertia tensor have not been identified from component masses',
          'No measured rotor thrust-vs-pitch/tilt/rpm response or efficiency',
          'No real actuator dynamics, motor torque limits or feedback control',
          'No drag, wind, gear torque reaction, gyroscopic forces or cabin vibration',
          'The vehicle exactly tracks the reference curve by construction',
          'Acceleration-jerk assumptions are screening criteria from road transport research, not VTX certification'],
       'references':['de Winkel et al. Applied Ergonomics (2023) DOI:10.1016/j.apergo.2022.103881',
           'VeriCAV (2021) Assessing Occupant Comfort final report'],
       'scenarios':scenarios}
    path=Path(__file__).with_name('VTX_urban_reference_results.json')
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    for item in scenarios:
        t=item['turn_90_degrees']
        print(f"{item['speed_mph']:.0f} mph: accel {item['start']['time_s']:.3f}s / {item['start']['distance_m']:.2f}m, "
              f"turn {t['time_s']:.3f}s / R={t['steady_radius_m']:.2f}m, "
              f"peak jerk={t['peak_total_jerk_mps3']:.3f} m/s^3, "
              f"yaw={t['final_heading_deg']:.6f}deg")
    print('Saved',path)

if __name__=='__main__':
    main()
