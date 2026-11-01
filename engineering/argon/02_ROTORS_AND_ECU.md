# Task 02 — Rotor/fan calculations, independent transmission and ECU linkage (AFTER Task 01)

This is an engineering analysis specification. Implement after the transmission + tank geometry baseline has passed review. Mechanical integration and regulation are *not* currently qualified.

## Newton–Euler dynamics and reaction accounting

For body frame +Z up, gravity in world frame is `m*(0,0,-g)`. Using the actual current inertia tensor and multibody dynamics:

```
m*a_CG = F_g + sum(R_body_to_world*F_rotor_i) + F_aero + F_contact + F_other
F_i = T_i(rho,Omega_i,collective_i,inflow_i)*n_i
tau_i = (r_i-r_CG) cross F_i + tau_reaction_i
H_body = I_body*omega_body + sum(J_rotor_i*Omega_i*n_i) + H_articulated
tau_external = dH_body/dt |_body + omega_body cross H_body
```

Check thrust-line moments, rotor reaction torques, spin-up/spin-down, spinning-nacelle gyroscopic coupling, thrust vector offsets, real articulated support reactions and fuel-load changes. Do NOT double-count internal joint reactions if MuJoCo integrates them.

Physically plausible dynamic fan controller variables: four rotor RPMs (independent only after an independent drive exists), four blade collectives, four two-axis nacelle tilts. Cabin yaw/level is a separate gimbal and must not silently change aircraft attitude.

## Calibration and rotor control effectiveness

The pilot's manual trim experiment `evidence/FLIGHT_173518_SETTINGS.md` shows roll worsened from around -1.5 to -13.3 degrees while trim was being altered; an 8-degree nacelle tilt request had not been physically reached by impact. Distinguish commanded vs achieved angles/collectives, power limits and contact. Diagnose via controlled perturbation on a physically trimmed state, not by assigning gain signs from the rough flight record.

Determine the local six-axis wrench Jacobian `B(x) = partial(F,M)/partial(u)` from actual model inputs and repeat tests for load/CG changes. Document controllability/rank, rate limits, saturation, actuator lag, shaft reaction, yaw authority, available energy and observation delay; account for noise and condition-dependent aerodynamic coefficients. Benchmark 0%, intermediate and 100% advisory training assistance. The existing synthetic one-second damping study did not show improvement and cannot justify active flight control.

## Planetary & motor-generator calculations

For proposed sun 20 teeth / ring 60 teeth / fan output at carrier:
```
omega_c = (omega_s + 3*omega_r)/4
omega_r = (4*omega_c - omega_s)/3
```

Option A old 4:1 upstream reduction: turbine 6016 rpm -> sun 1504 rpm; at carrier 1200 rpm ring ~1098.667 rpm. This places substantial nominal mechanical throughput at the electric ring.

Option B proposed nominal 6016/4800 upstream reduction: sun 4800 rpm, fan carrier 1200 rpm, ring 0 rpm. Ring is -133.333 rpm at fan 1100 and +133.333 at fan 1300. These are illustrative conditions and not permitted operating speed bands.

At assumed total 300 kW mechanical input / 95% idealised mechanical transfer / four equal branches, output ~71.25 kW per fan => ~566.99 N*m at 1200 rpm. For ideal 20:60 planetary, ring reaction magnitude ~425.24 N*m; a hypothetical 3:1 motor/ring stage at 95% motoring efficiency implies ~149.2 N*m at the motor. Zero ring speed does NOT imply zero holding current, thermal loss or torque.

The simplified bench `evidence/variable_drive_bench_results.json` uses rotor inertia 3.332575 kg*m^2 and +100 rpm/s acceleration => ~34.90 N*m additional inertial torque per rotor. Four simultaneous acceleration cases request ~302.54 kW at planetary suns, already above an assumed 300 kW engine budget before upstream losses. Motor peak/continuous ratings, reversing stage, electrical DC bus, braking/regeneration, zero-speed heating, cooling, clutch, fluid film, flexible shafts, common-cause faults and gear mesh resonance remain **unverified**.

Prior gear phasing warning: 20/60 with three equally spaced planets fails conventional integer phasing (80/3); with four, (20+60)/4=20 is integral. Existing three-planet graphical illustration is not an engineered tooth mesh. Recalculate shaft/mesh excitation and verify with a Campbell and dynamic modal analysis before selection.

## ECU interface and protection

The existing local PI common-shaft controller (`src/vtx/governor.py`) has Kp = 180 N*m/(rad/s) and integral time 2 s with anti-windup and a provisional overspeed fuel-cut above 101% target. It is NOT an aircraft stabiliser, and 101% is NOT a blade structural operating limit.

The current `tools/fan_ecu_shadow.py` checks only measured resultant tilt cone and, when supplied, a separately validated max RPM. It does not command rotors or infer stability. Current `src/vtx/training_assist.py` collective suggestions are not applied in the live plant.

Propose a traceable, bandwidth-aware signal chain:

```
pilot command
  -> timestamp/validity check
  -> estimator: IMU, position/velocity, rotor RPM, tilt, collective,
     shaft torque, engine availability, fuel/CG, component health
  -> optional pilot-visible rate-damping assistance
  -> constrained force/moment allocator using calibrated B(x)
  -> combined engine/shaft/DC-bus power arbitrator
  -> separate rotor drive speed/torque (ONLY when fitted),
     pitch commands and nacelle X/Y servo targets
  -> actual multibody plant (gravity/contact/lag/energy)
  -> sensor feedback + fault/report channels
```

Pilot inputs remain physical commands, not predetermined flight trajectories. The 0-100% adjustable training assist is separate from mandatory mechanical-envelope protection. Respect tilt resultant <=20 degrees, rotor spin sense, actual thermal/torque/acceleration limits and fuel/power budget. Record intervention reason and rejected commands. Define fault-specific, testable degraded states (not a generic 'stop fans') for one seized rotor, one failed branch, current or tachometer sensor invalidity, saturated gimbal, DC bus fault, engine droop and stale pilot request.

Begin with an advisory/shadow allocator that logs desired vs feasible wrench, recommended control adjustments, available authority, estimated power and actual post-step motion. Retain existing active controls until reproducible, trimmed, closed-loop tests demonstrate stability improvements. Never conclude flyable or real-world safe from a static allocation matrix or successful scripted animation.

## Acceptance evidence for later phase

Provide source-linked equations, units, measured/assumed coefficients and error bounds; energy balance and torque accounting; controlled response and failure tests; latency and stability metrics over mass/fuel envelope; unchanged baseline comparison and explicit **not yet validated** constraints. Stop for user review before enabling active ECU or independent rotor drive in the live simulation.
