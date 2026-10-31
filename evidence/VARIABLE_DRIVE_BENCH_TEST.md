# Revised variable drive: arithmetic bench test

This is a point-by-point ideal planetary power and torque calculation, **not a flight, dynamic gearbox, structural, thermal or resonance test**. The actual simulator currently couples all four fan speeds through equality constraints in `src/vtx/aircraft.py`; it does not model independent electronically controlled transmissions. No live test of the proposed component was performed.

The reproducible calculation and its numerical output are in `tools/bench_variable_drive.py` and `evidence/variable_drive_bench_results.json`; checks are in `tests/test_variable_drive_bench.py`. It assumes fixed 4,800 rpm sun speed, 20:60 gearing, 3:1 motor-to-ring stage, 95% control gearing efficiency, constant 566.99 N m fan load and 3.333 kg m² rotor inertia. It omits motor/inverter loss and inertia, thermal limits, actual fan load curves, compliance, startup, engine response and failures. The range and acceleration rate are illustrative, not approved limits.

| Case | Ring rpm | Ring mechanical power per fan | Control motor torque estimate | Sun power per fan |
| --- | ---: | ---: | ---: | ---: |
| Steady 1,100 rpm | −133.3 | −5.94 kW | 134.7 N m generating | 71.25 kW |
| Steady 1,200 rpm | 0 | 0 kW | 149.2 N m holding estimate | 71.25 kW |
| Steady 1,300 rpm | +133.3 | +5.94 kW | 149.2 N m motoring | 71.25 kW |
| Passing 1,200 rpm at +100 rpm/s | 0 | 0 kW | 158.4 N m holding estimate | 75.64 kW |

The code checks `sun power + ring power = carrier power` at every case. A four-fan example at 1,100 / 1,200 / 1,250 / 1,300 rpm has approximately 2.97 kW net ring power but 15.02 kW total absolute motor-shaft throughput after hypothetical gear losses. A shared bus must be designed for individual branch currents and conversion losses, not net power alone. The generating-side torque assumes the stated simplified directional gear efficiency; motor electrical generation and bus flows are not calculated. At zero speed the assumed holding torque does not establish the motor's electrical consumption or thermal rating.

Four simultaneous illustrative +100 rpm/s accelerations through 1,200 rpm demand approximately **302.5 kW at the planetary suns alone**, above the earlier 300 kW total input assumption even before upstream losses. Similarly, four steady fans at 1,300 rpm consume 308.75 kW at the carriers under the constant-torque assumption; this is not feasible within the earlier 300 kW input assumption without changing that budget or load. The flight controller would need an engine-power-aware acceleration and thrust allocator, supported by actual engine and rotor data.

Results do not prove supplier motor suitability, torque margin at zero speed, controllability, torsional stability, gear strength, safe clearance, or flight performance. Full transient simulation requires implementing the differential dynamics and four separate actuators with measured or defensible component data, failure behavior and a power/thermal model; frame and resonance checks require geometry and stiffness.

## Independent Wolfram arithmetic check

Wolfram Language independently evaluated the same assumed equations and returned ring speeds −133.33/0/+133.33 rpm, corresponding ring powers −5.9375/0/+5.9375 kW, 425.24 N m ring torque, and 149.21 N m estimated 3:1/95% motor torque. At the nominal condition the ideal 20-tooth planet absolute spin is −2,400 rpm as its carrier orbits at +1,200 rpm. It returned 34.90 N m extra fan inertia torque at 100 rpm/s and 302.54 kW for four ideal planetary sun inputs at that acceleration. The four-planet phasing integer is (20+60)/4 = 20. These confirm arithmetic under the stated assumptions, not assumptions or stability of the real machine.
