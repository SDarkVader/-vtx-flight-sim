# Phantom A10-C: automatic law selection and battery-assisted wheel drive (13 November 2026)

Companion to `A10C_GROUND_ROLL_VEER.md`. Same code base and runway; scripts and outputs in `engineering/phantom/a10c_ground_roll/`.

## 1. Automatic law selection (`stability_mode: auto`, now the default)

The pilot no longer preselects a stability law. The flight computer resolves the phase from pilot-visible state only
(weight on wheels, airborne flag, mean pod tilt with hysteresis, wings out) and picks the law:

| Phase | Sensed as | Law |
|---|---|---|
| ground | pods road, wheels loaded, wings stowed | attitude |
| takeoff_roll | pods road, wheels loaded, wings out | attitude, plus yaw-rate feedback to the nosewheels |
| hover | pods in fan mode (45 deg, leaves below 35 deg) | attitude |
| transition | pods between road and fan mode | attitude |
| wingborne | pods road, airborne | attitude (gains already schedule on dynamic pressure) |

Phase and resolved law are logged in `fcc.last`, reported in the observation (`flight_phase`, `stability_mode_resolved`)
and shown on the live panel. `off`, `rate_damping`, `attitude` and `attitude_vs` stay selectable for test work and PTI.
The ground feedback is an ECU constant (30 deg of nosewheel per rad/s of yaw rate, inside the existing 2 deg take-off
lock), not a parameter: the A10-B parameter file is pinned by hash and is untouched. Tests: `tests/test_phantom_auto_law.py`;
full suite 363 passed.

Effect on the slow roll that spun on 12 November (half drive, no boosters): in auto it reaches 46 m/s 0.5 m off the
centreline with 0.1 deg of yaw (`out_base_auto.txt`). The rear-pod fight described in the veer note is still present
underneath; the wheels now hold the heading through it.

## 2. Battery power into the wheels for the take-off roll

What the energy bus allows: one 600 kW generator (900 kW take-off rating for 5 min) and a 311 kg buffer good for
800 kW continuous, 1.2 MW for 30 s. The four hub motors are rated 600 N m and 60 kW each, 240 kW in all, so the
wheels are limited by their own rating and by tyre traction, not by the battery. The sweep scales the hub-motor rating
(torque and power together) with and without the four turbojets. Full wheel drive, wings and flaps out, auto law,
rotate at 55 m/s:

| Jets | Hub rating per wheel | Lift-off | Ground roll | Peak buffer draw | Buffer energy | Peak wheel slip | Fuel |
|---|---|---|---|---|---|---|---|
| on | 600 N m, 60 kW (today) | 79 m/s, 23.2 s | 1,140 m | 68 kW | 0.06 kWh | 30 % | 5.9 kg |
| on | 1,200 N m, 120 kW | 78 m/s, 16.5 s | 859 m | 219 kW | 0.13 kWh | 30 % | 4.7 kg |
| on | 2,400 N m, 240 kW | 78 m/s, 13.8 s | 789 m | 348 kW | 0.24 kWh | 70 % | 4.3 kg |
| off | 600 N m, 60 kW | none: 69 m/s after 60 s, drag-limited | - | 12 kW | 0.06 kWh | 4 % | 1.5 kg |
| off | 1,200 N m, 120 kW | crash: wheel-spin above 40 m/s as the wing unloads the tyres, then a spin | - | 311 kW | 0.19 kWh | 173 % | - |
| off | 2,400 N m, 240 kW | crash: same, earlier | - | 882 kW | 0.41 kWh | 70 % | - |

Reading:

* **Battery energy is not the constraint.** The largest case drew 0.41 kWh of the 64 kWh usable and peaked under the
  buffer's continuous rating. The buffer can feed the wheels for the whole roll with no generator uprate.
* **The hub motors and the tyres are.** Doubling the hub rating with the jets on shortens the roll from 1,140 m to
  859 m (25 %) and the time to lift-off from 23 s to 16.5 s, at 30 % wheel slip. Quadrupling buys only 70 m more and
  runs the tyres at 70 % slip for most of the roll: the wing has unloaded the wheels by then.
* **Wheels alone cannot replace the jets.** At today's rating the aircraft levels off at 69 m/s under drag, below
  the 79 m/s it leaves the ground at. Bigger motors without the jets spin the unloaded wheels above 40 m/s, and the
  traction-control overlay (15 % slip) is not enough to stop that at these torques; the runs end in a spin.
* **The useful option is both:** jets for the second half of the roll where the wheels have lost their load, wheels
  for the first half where traction is plentiful and the jets are at their weakest. Whether a 1,200 N m / 120 kW hub
  motor fits the pod (today's is 11 kg rotor plus stator) is a hardware question this sweep does not answer.
