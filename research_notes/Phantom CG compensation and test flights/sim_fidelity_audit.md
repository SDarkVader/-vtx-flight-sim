# VTX four-fan simulator: fidelity and configuration audit (frames, rotor and duct model, engine and governor, numerics, sensors, config, logging, tests) with a patch-ready fix list

*Audit date: 2026-11-03. Code basis: branch `research/phantom-a9-cassette` at `bce9339`; MuJoCo 3.17.0, numpy 2.5.4, scipy 1.18.1, node v24.21.0.*

*Method:*
- *No tracked file was modified.*
- *All experiments (E1 to E10) ran offline in a byte-identical scratch mirror of the worktree. No server was started, and port 8765 was never touched.*
- *Scripts and JSON results are in `C:\Users\steve\AppData\Local\Temp\claude\C--Users-steve-Documents-Github--vtx-flight-sim--claude-worktrees-dreamy-khayyam-7059f0\38a34963-97f9-41b6-85d4-74b9f5683e04\scratchpad\audit\` (results in `results\`).*
- *Unless stated otherwise, the configuration is the R6 calibration one: `airframe_variant='r6'`, 1200 rpm, 10 kg fuel, 300 kW, gear `baseline`.*

*Line numbers are at `bce9339`. The Phantom build is editing `src/vtx/live_server.py`, so patches there are given by code anchor, not line number.*

*Labels:*
- *Priority: P0 = frame or physics error that reaches live control or evidence; P1 = large fidelity gap; P2 = other.*
- *Class: (a) physics or frame error, (b) fidelity gap, (c) config, units or docs, (d) logging or UI.*
- *"Phantom: yes" = the defect sits on a seam the Phantom will share.*

## Key Question: Are the body frames, sign conventions and rate signals correct, and what caused the Argon yaw cross-coupling?

### Takeaway
There is one genuine P0 frame bug in the simulator.

**The training-assist loop reads body rates in the wrong frame.** It reads them in the airframe's principal-inertia frame, whose first axis is roughly body z, instead of body x/y/z. With the experimental wire on, which is the persistent-pilot default, a roll disturbance turns into a sustained pitch rate of about 10 deg/s instead of being damped.

**The instrument packet publishes world-frame rates only.** The Argon calibration report "fixes" this by rotating both rates and Euler angles by R_z(-ψ). That is right in spirit for rates and position errors, but wrong for Euler roll and pitch: in the ZYX convention the packet uses, they are already heading-relative. So the Argon cross-coupling at 90 deg yaw was a pilot-side frame error fed by a world-frame-only packet, not a physics error.

The other sign conventions check out: rotor senses, yaw reaction, diamond indexing, quaternion order, cabin-level target and shaft axis.

### Cited Findings
- **F1 (P0, class a, Phantom: yes). The training assist gets principal-axis rates.**
  - *Where:* `aircraft.py:413` calls `mj_objectVelocity(..., mjOBJ_BODY, airframe, ..., flg_local=1)`. `training_assist.py:22-26` then treats the result as [roll x, pitch y, yaw z] [Source](../../src/vtx/aircraft.py) [Source](../../src/vtx/training_assist.py).
  - *Why it is wrong:* MuJoCo's `mjOBJ_BODY` with `flg_local` rotates into `ximat` (the inertial frame), while `mjOBJ_XBODY` uses `xmat` [Source](https://raw.githubusercontent.com/google-deepmind/mujoco/2.3.7/src/engine/engine_support.c). `mju_eig3` orders the principal axes by decreasing eigenvalue [Source](https://raw.githubusercontent.com/google-deepmind/mujoco/2.3.7/src/engine/engine_util_solve.c).
  - *E1, inertia frame:* airframe `body_iquat` = [0.484, 0.516, -0.429, 0.561]; principal inertia [1027.6, 670.5, 616.4]. Principal axis 0 ≈ body +z, axis 1 ≈ -x, axis 2 ≈ -y.
  - *E1, rate injection:* with 10 deg/s of body roll injected, the code path reads [0.008, -9.865, 1.636] deg/s. The assist therefore moves the E/W pair, [9.605, 10, 10.395, 10], instead of the N/S pair, [10, 9.6, 10, 10.4]. `mjOBJ_XBODY` local and `qvel[3:6]` both return the injected rates exactly.
  - *E1, closed loop at hover trim with 10 deg/s roll injected:*

    | Assist | Body rate response |
    |---|---|
    | Off | Roll decays to 2.1 deg/s by 3 s |
    | Current code | Pitch rate 9.5 to 10 deg/s from 1.5 s to 3 s |
    | Fixed frame | Roll 2.65 deg/s at 0.75 s, -0.2 deg/s at 3 s |

  - *Same bug elsewhere:* `tools/bench_rate_assist_dynamics.py:17` has the identical call. Its committed output `evidence/training_assist_dynamic_check.json` shows the wrong pair moving. The unit test `tests/test_training_assist.py:22` only checks that "something changed" [Source](../../tools/bench_rate_assist_dynamics.py) [Source](../../tests/test_training_assist.py).
  - *Exposure:* `tools/persistent_pilot.py:34` defaults `experimental_assist_wire=True` with `stability_assist=1.0` [Source](../../tools/persistent_pilot.py).
- **F2 (P0, class a/d, Phantom: yes). The packet frames are mixed, and Argon §4.1 is half wrong.**
  - *Where:* in `live_server.py` (anchor `def sensor_observation`), attitude is `Rotation.from_quat(...).as_euler('xyz')`. That is extrinsic xyz, i.e. ZYX yaw-pitch-roll. `gyro_world_deg_s` comes from `mj_objectVelocity(..., flg_local=0)`, which is world frame [Source](../../src/vtx/live_server.py).
  - *E2, attitude:* for R = Rz(90)·Ry(5) the packet Euler is [0, 5, 90]. Those are already the correct body roll and pitch. The Argon R_z(-ψ) transform gives roll 5, pitch 0, which is wrong [Source](../../evidence/ARGON_CALIBRATION_REPORT.md).
  - *E2, rates at yaw 90:* with 0.2 rad/s body roll, `gyro_world` = [0, 0.2, 0] while the body rate is [0.2, 0, 0].
  - *E2, error of the yaw-only rate rotation when tilted:* for a 0.3 rad/s body yaw rate:

    | Tilt (roll / pitch) | Error |
    |---|---|
    | 10 / 0 deg | 0.052 rad/s |
    | 10 / 10 deg | 0.074 rad/s |
    | 20 / 15 deg | 0.129 rad/s |

    The exact body rate is Rᵀω = `qvel[3:6]`.
- **Verified correct**, by code reading plus tests [Source](../../tests/test_multibody.py) [Source](../../src/vtx/aircraft.py):
  - Rotor spin senses [1,-1,1,-1], with the net yaw reaction through the equality constraints.
  - Rotor gyroscopics are emergent and tested (`tests/test_multibody.py:119`).
  - E/N/W/S indexing matches the ledger pivots.
  - The quaternion reorder to scipy [x,y,z,w].
  - `cabin_level_target` (`tests/test_live_interface.py:172`).
  - The R6 shaft principal-axis fix (`aircraft.py:164-169`).
  - The assist's sign logic: once fed true body rates, it opposes the rate on the correct pair (E1 fixed case).

### Inferences
- The Argon "yaw cross-coupling" was most likely the pilot damping world-frame rates and closing a world-frame position loop as if they were body-frame. At 90 deg of heading that swaps the roll and pitch channels exactly. The fix belongs in the packet (publish body rates and body velocity) plus a correction to the pilot reference, not in rotating Euler angles.
- Any new body-frame quantity must use `xmat`, `mjOBJ_XBODY` or `qvel[3:6]`, never `mjOBJ_BODY` with `flg_local=1`. That includes the Phantom wing-surface airflow `v + ω×r`. The Phantom fuselage inertia will have its own principal frame, so the same bug would scramble its rates differently.

### Gaps
- The Argon pilot code is not in this repo. The root cause is therefore inferred from the report text and the packet code, not from a replay of its control law.
- The MuJoCo source was read at tag 2.3.7. E1 confirms the semantics are unchanged at 3.17.0: BODY-local differs from XBODY-local, which equals `qvel`.

## Key Question: How faithful is the rotor and ducted-fan aerodynamic model (momentum, figure of merit, duct share, edgewise flow, descent and VRS, ground effect, pitch-to-thrust map)?

### Takeaway
The rotor model is uniform-inflow blade-element/momentum theory (BEMT) on an **open** rotor: κ=1, no tip loss, no duct. Using only the axial velocity, it is internally consistent, and it reproduces the documented hover point exactly (16.95 deg, 202.8 kW total).

But it is not a ducted fan, and it ignores in-plane and descent effects:
- An ideal ducted VTX fan (σd ≈ 1) would need about 28% less rotor power in hover.
- Nothing happens to thrust or drag in edgewise flow. There is no translational lift and no ducted momentum drag. At 10 m/s that drag is about 1.1 kN per fan, against 101 N of total modelled body drag.
- There is no vortex-ring loss in descent and no windmilling.

The Argon trim table is consistent with a static moment balance; this corrects the plan's F10, with residuals of at most 8 N·m. What is wrong is the report's 268 N/deg sensitivity: the model gives 210 N/deg.

### Cited Findings
- **E3, hover characterisation.**
  - *Blade:* R6, R = 1.1284 m (A = 4.000 m²), four blades, zero twist, solidity 0.206. Tip speed is 141.8 m/s (M 0.417) at 1200 rpm.
  - *Hover point:* at T = 2443.5 N per rotor, the model gives:

    | Quantity | Value |
    |---|---|
    | Collective | 16.951 deg |
    | dT/dθ | 210.0 N/deg |
    | dQ/dθ | 46.4 N·m/deg |
    | Rotor power | 48.17 kW |
    | Total power (rotor power ÷ 0.95, four rotors) | 202.82 kW, matching `evidence/PROPULSION_FUEL_REVISION.md` |
    | Figure of merit (FM) | 0.801 (0.715 if κ = 1.15) |
    | Induced velocity vi | 15.79 m/s |
    | Max section α | 13.9 deg, no section CL-clipped |

  - *Model location:* `aero.py:43-56`, with momentum `2ρA·vi·|V+vi|` at line 48 [Source](../../src/vtx/aero.py) [Source](../../evidence/PROPULSION_FUEL_REVISION.md).
- **E3, collective sweep at 1200 rpm.** Thrust peaks at about 3587 N near 27 deg, then stalls to 3491 N at 30 deg. The thrust-to-weight margin at full collective is therefore about 1.47.
  - At 800 rpm and 30 deg, T = 1552 N per rotor, which cannot hover the 10 kg-fuel aircraft. This matters because `retry()` defaults to 800 rpm (see the config question).
- **F5 (P1, class b, Phantom: yes). There is no duct.**
  - *E3, ideal σd = 1 ducted fan:* v_d = 22.33 m/s. The rotor carries 1221.7 N at 17.51 deg, with rotor power 34.6 kW, 0.719× the open model. The ideal is 27.3 kW per fan.
  - *Pereira, UMD shrouded-rotor tests:* up to 94% more thrust at equal power, or 62% less power at equal thrust, at small scale [Source](https://windtunnel.umd.edu/event/3047/phd-defense-announcement---jason-pereira-hover-and-wind-tunnel-testing-of-shrouded-rotors) [Source](https://inderjitchopra.umd.edu/?p=127).
  - *TU Delft ducted-fan study:* the duct carried about 40% of total thrust [Source](https://repository.tudelft.nl/file/File_77f2bae9-aa1c-49bf-bd58-a65cd883c51a).
  - *Practitioner summary:* about +28% static thrust for an ideal duct [Source](https://www.kitplanes.com/wind-tunnel-12/).
  - *Provenance strings* declare "duct gain=1" (`aircraft.py:327-339`) [Source](../../src/vtx/aircraft.py).
- **F6 (P1, class b, Phantom: yes, critical). In-plane flow is only flagged.**
  - *Where:* `aircraft.py:371-376` uses `axial=relative@axis` and only sets `EDGEWISE_FLOW_UNCALIBRATED` above 5 m/s [Source](../../src/vtx/aircraft.py).
  - *E3, Glauert inflow at fixed hover pitch:*

    | Edgewise speed | Thrust gain | Ducted momentum drag ρA·v_d·V, per fan | Modelled body drag, total (`aircraft.py:447`) |
    |---|---|---|---|
    | 5 m/s | +2.1% | 547 N | 25 N |
    | 10 m/s | +7.8% | 1094 N | 101 N |
    | 15 m/s | +15.9% | 1641 N | 227 N |
    | 20 m/s | +24.7% | 2188 N | 404 N |

- **F7 (P1, class b, Phantom: yes). Descent, vortex-ring state (VRS) and windmilling are only flagged.**
  - *E3, axial sweep at hover pitch from V = -20 to +10 m/s:* thrust rises smoothly from 2443 to 3383 N in descent, with no loss or roughness near V ≈ -v_h (15.8 m/s).
  - *E3, windmill case (pitch 0, V = -15 m/s):* thrust is clamped to 0, and torque is clamped to ≥ 0 (`aero.py:55`), so a windmill or autorotation torque cannot appear.
  - Johnson's NASA TP-2005-213477 gives an empirical VRS inflow model suitable for real-time use [Source](https://rotorcraft.arc.nasa.gov/Publications/files/Johnson%20TP-2005-213477.pdf) [Source](../../src/vtx/aero.py).
- **Ground effect (verified minor).**
  - *E3, hub height:* with the gear compressed, hub z = 2.439 m, so z/R = 2.16.
  - *Cheeseman-Bennett:* 1/(1-(R/4z)²) gives +1.36% on the ground and +0.68% at 1 m clearance. The formula is valid for z/R > 0.6 [Source](https://icas.org/ICAS_ARCHIVE/ICAS2008/PAPERS/085.PDF).
  - Omitting it is acceptable for VTX.
- **F10, corrected (P2, class c/d). Argon trim table and sensitivity.**
  - *E3b, static BEMT trim:* with the live CG (y = 0.0785) and moment balance, the solve gives [16.954, 17.643, 16.959, 16.238] deg.
  - *The Argon table is consistent:* [16.95, 17.66, 16.95, 16.24] leaves residuals of 1.25 N, 8.3 N·m roll, -2.7 N·m pitch and 1.5 N·m yaw.
  - *The sensitivity is wrong:* the report's 268 N/deg compares with 210 N/deg from the model.
  - *Rows are mislabelled:* `tools/argon_calibration.py:55` labels exact table rows `measured_reference`, but the 0, 30, 60 and 110 kg rows were never flown [Source](../../tools/argon_calibration.py) [Source](../../evidence/ARGON_CALIBRATION_REPORT.md).
- **Yaw authority (E3, for allocation).**

  | Channel | Authority |
  |---|---|
  | Differential collective (4·dQ/dθ) | 185.5 N·m/deg |
  | Tangential nacelle tilt | about 443.5 N·m/deg |

  Rotor angular momentum is 418.8 N·m·s per rotor.

### Inferences
- Every hover-power, endurance and collective number in the repo is an open-rotor number. If the fans are truly ducted:
  - hover power is overstated by roughly 25-30%;
  - collective changes by about +0.6 deg;
  - the pitch-to-thrust slope changes;
  - so the trim tables and the 300 kW margin are affected.
- The missing momentum drag is the larger handling error: translation is about 10× too cheap at 10 m/s.
- For Phantom (target 178.8 m/s), an axial-only fan model is unusable in forward flight. Edgewise inflow, momentum drag and duct moment are prerequisites, not refinements.
- Since crashes are acceptable data, VRS and windmill fidelity matter only where a sortie descends steeply. Implement them before steep-descent cards, not before hover cards.

### Gaps
- No VTX duct geometry exists in the repo (lip radius, tip gap, diffuser ratio σd). σd = 1 is therefore an ideal bound, not a prediction.
- Pereira's primary dissertation (DTIC) returned HTTP 403. Only the UMD and TU Delft secondary summaries were read.
- No accessible source was found for VRS onset and severity in ducted fans.
- The scite literature tool needs a paid plan and was unavailable.

## Key Question: Are the engine, governor and fuel/energy models correct (M250-C30P ratings, governor dynamics, fuel accounting)?

### Takeaway
**The fuel draw is wrong once a tank is empty.** The burn is split equally across four tanks, and an empty tank's quarter is silently discarded. That under-books fuel by 25% while the engine keeps full power. This is a P0 energy-accounting bug.

**The governor works but is slow:**
- about 16 rpm (1.3%) droop on a 12 deg collective step;
- 2-3 s to recover, matching the analytic slow pole (about 0.45 rad/s);
- an integrator dump on overspeed, latent in these tests.

**The engine has no gas-generator lag and no ratings:** no time-limited ratings, no temperature or altitude lapse, and a constant SFC.

**"Engine 0" is a shutdown that the UI calls "idle".**

### Cited Findings
- **F3 (P0, class a, Phantom: yes if multi-tank). Fuel draw.**
  - *Where:* `aircraft.py:459-461`:
    ```
    engine_power=torque*max(omega,0)/.95+servo_power
    burn=engine_power/3.6e6*.4*DT
    if burn>0:self.fuel=np.maximum(self.fuel-burn/4,0.)
    ```
  - *E6, tanks [0.1, 2, 2, 2] kg, 12 deg collective on the ground:*
    - tank 1 empties at 36.5 s;
    - after that, booked burn is 0.0720 kg against ∫P·SFC = 0.0960 kg, exactly 75%;
    - over the whole 45 s, 0.472 kg is booked against 0.496 kg;
    - the engine stays powered.
  - *Test gap:* the existing test `tests/test_multibody.py:164` uses equal tanks only [Source](../../src/vtx/aircraft.py) [Source](../../tests/test_multibody.py).
- **F8a (P2, class b). Governor dynamics.**
  - *E4, on the gear at 1200 rpm, PI gains Kp 180 / Ki 90:*

    | Step | Response |
    |---|---|
    | 0→12 deg | 1199.6 → min 1179.0 rpm. After 6 s it reads 1194.4 rpm, still recovering, about 0.5% low. |
    | 12→0 deg | Peaks at 1211.5 rpm, just under the 1.01× fuel-cut threshold (1212 rpm). The integrator unwinds to 0. |
    | 0→12 deg again | Identical to the first step. |

  - *Overspeed dump:* in `governor.py:27-35`, `cap=0` on overspeed, then `integral=max(0,min(integral,cap))`. So the integrator is zeroed on any overspeed.
  - *Analytic check:* J ≈ 13.9 kg·m² on the rotor side gives poles at -14.3 and -0.45 rad/s, matching the 2-3 s recovery [Source](../../src/vtx/governor.py).
- **F8b (P2, class b/c). Engine model and ratings.**
  - Torque is capped at 484.7 kW / ω_out (`aircraft.py:449-458`) and available instantly. The only lag is the 2 s spool ramp (`aircraft.py:406`).
  - 484.7 kW equals 650 shp, the published 250-C30 takeoff rating at 1368 °F [Source](https://docs.marketpath.com/415fcc1e-33b0-41f6-ba6b-55d1178dfa87/document/432fda8a-5f15-40f9-9b25-d6139d9cd5ee/m250-engine-designations-and-applications.pdf).
  - "469.8 kW maximum continuous" (`evidence/PROPULSION_FUEL_REVISION.md:20`) has no source in the repo.
  - SFC is a constant 0.4 kg/kWh, with no part-power rise [Source](../../evidence/PROPULSION_FUEL_REVISION.md).
- **F8c (P2, class d). "Idle" is really a shutdown.** The lease-expiry path logs "engine idle" (`live_server.py`, anchor `command_lease_expired`) but sets `engine=0`. `engine=0` ramps the spool to 0 and removes all drive torque. The keyboard help in `public/index.html` also says "X Engine on / idle" [Source](../../src/vtx/live_server.py) [Source](../../public/index.html).
- **Rotor stored energy (derived from E3 inertia).** About 26 kJ per rotor, 110 kJ total at 1200 rpm. That is roughly 0.55 s of hover power, so a power loss is unrecoverable within about a second.

### Inferences
- In any unequal-tank sortie (Task 01 and the CG studies use `tank_fuel_kg`), the simulator:
  - over-predicts endurance once a tank runs dry;
  - drifts the CG toward the wrong tank;
  - never stops the engine on exhaustion.
- The slow integral pole means a pilot sees about 1-1.5% rpm droop (about 2-3% thrust) for several seconds after each collective step, and will tend to over-correct. This is a fidelity choice, not a bug, but it should be documented.
- Phantom has a different engine and drive. It should not inherit the VTX governor gains without its own inertia check.

### Gaps
- The M250-C30P maximum-continuous rating and output-shaft speed could not be verified: the EASA TCDS PDF returned binary that could not be extracted.
- No source was found for a part-power SFC curve.

## Key Question: Do actuators and sensors match their documentation and the Argon diagnosis?

### Takeaway
**Actuators are slew-limited, not first-order:**
- nacelle tilt is 5 deg/s;
- collective is 4 deg/s with a 0.15 s lag.

So the Argon report's "τ = 0.08 s" actuator diagnosis is wrong by about 10×: a 5 deg tilt takes 0.95 s to reach 90%. The advertised `nacelle_command_rate_deg_s=20` is unused.

**Sensors** have white noise only and are near-perfect.

**The "radar clearance" is a fixed point on the cabin sphere above the airframe origin.** It reads 0.75 m with the aircraft sitting on its gear, and it ignores trees.

### Cited Findings
- **F9 (P1, class c/b). Actuator rates.**
  - *E5, time to 90% (steps from rest):*

    | Step | Time to 90% |
    |---|---|
    | Tilt 1 deg | 0.26 s |
    | Tilt 2 deg | 0.415 s |
    | Tilt 5 deg | 0.95 s (overshoots to 5.16 deg, 3%) |
    | Collective 2 deg, from 0 and from 16.95 | 0.515 s |

  - *Where:* slews at `aircraft.py:417` (collective) and `aircraft.py:424` (`math.radians(5)*DT`). The unused `nacelle_command_rate_deg_s=20.` is at `aircraft.py:329`. Argon claims τ = 0.08 s [Source](../../src/vtx/aircraft.py) [Source](../../evidence/ARGON_CALIBRATION_REPORT.md).
  - *E5, audit contents:* `physical_snapshot()` has no active command, no rate-limited target, and no actuator force or saturation (`has_active_command_in_audit = false`). Requested-vs-achieved therefore cannot be reconstructed from the physics audit alone.
- **F4 (P0, class d/c, Phantom: yes). Radar clearance.**
  - *Where:* `live_server.py`, anchor `radar_clearance_m=round(float(pos[2]+1.56-.95-surface`. 1.56 is the cabin pivot z and 0.95 is the `cabin_shell` sphere radius (`aircraft.py:225`).
  - *E9, on the gear after 4 s:* 0.7532 m (r6), 0.7532 m (light), 0.7513 m (baseline). The committed Argon samples read 0.78-0.82 m on the ground.
  - *E9, trees:* `world.surface_z` (`world.py:51-56`) adds boxes only. At tree-0 it returns 0.0, though the tree top is at 7.61 m and trees are in the MuJoCo model (`aircraft.py:139`).
  - *E9, attitude:* at a 10 deg bank the formula does not change [Source](../../src/vtx/live_server.py) [Source](../../src/vtx/world.py).
- **F12 (P2, class b). Sensor realism.**
  - *Noise (white only):* GNSS σ 0.015 m, baro 0.01 m, radar 0.005 m, attitude 0.008 deg, gyro 0.008 deg/s, velocity 0.005 m/s. No bias, drift, latency or vibration.
  - *Baro* is geometric z.
  - *Heading* is ENU, counter-clockwise from East.
  - *`shaft_torque_nm`* is the aero torque per rotor, not shaft torque.
  - *Sensor RNG:* seeded per run, but the draw sequence depends on API polling cadence (0.05 s cache in `sensor_observation`) [Source](../../src/vtx/live_server.py).

### Inferences
- The 6.5 s Argon yaw oscillation is better explained by the 5 deg/s nacelle slew plus world-frame damping (F2) than by a 0.08 s actuator. Any controller tuned against τ = 0.08 s is about 10× too aggressive for the real slew limit.
- A radar that reads 0.75 m on the ground makes any "touchdown when clearance < x" rule wrong. Every pilot landing gate must be re-derived after the fix.

### Gaps
- There is no hardware source for the 5, 4 or 20 deg/s actuator rates. All are declared hypotheses in the provenance.

## Key Question: Is the numerical integration and contact model adequate for spinning rotors and ground contact?

### Takeaway
**`implicitfast` at dt = 2.5 ms integrates the spinning-rotor gyroscopics poorly.**
- In a torque-free tumble, total angular momentum drifts 49% in 20 s, and rotor speed changes 10.6 rpm with no torque applied.
- `implicit` cuts this to 0.04% and RK4 to 6e-7.
- `implicit` costs the same in hover: 0.44 against 0.42 wall-s per sim-s.
- In closed hover, the governor and aero mask the difference. So this is P2, not P0, but switching is cheap and removes a hidden spurious-torque source, mainly about yaw.

**Ground contact:**
- Static gear compression matches design: 56.2 mm against 57.7 mm from the spring rate, and Argon's 56.1 mm.
- Hard impacts produce very large contact forces from the stiff `solref .008`: 223 kN on a 4.3 m/s airframe strike, and 2.34 MN in the Argon run.
- The equality-constraint `solref .003` is silently raised to 2·dt = 0.005.

### Cited Findings
- **F11a (P2, class b, Phantom: yes). Integrator choice.**
  - *Where:* `aircraft.py:129` sets `integrator='implicitfast'`, with `DT=.0025` (`aircraft.py:25`).
  - *E7/E7b setup:* gravity 0, no aero or governor, rotors at 1200 rpm, initial body rate [0.05, -0.03, 0.02] rad/s, 20 s.

    | Integrator | Relative ΔH | Other |
    |---|---|---|
    | implicitfast, dt | 0.487 | ΔH_body = [-18.3, -11.1, -51.6] N·m·s; rotor +10.6 rpm |
    | Euler, dt | 0.487 (identical) | — |
    | implicitfast, dt/2 | 0.0085 | — |
    | implicit, dt | 0.00039 | rotor -0.002 rpm |
    | RK4, dt | 6.3e-7 | — |

  - *E7c, closed hover over 10 s:* body rates agree between implicitfast and implicit to 0.001 deg/s. Wall time is 0.419 against 0.437 s per sim-s.
  - *Docs:* MuJoCo's modeling docs say `implicitfast` drops the Coriolis/centrifugal derivative terms, and recommend `implicit` for fast-spinning bodies [Source](https://mujoco.readthedocs.io/en/stable/modeling.html) [Source](../../src/vtx/aircraft.py).
- **F11b (P2, class c). Equality solref below the safe minimum.**
  - `aircraft.py:251` and `253` set `solref='.003 1'`. MuJoCo enforces a time constant of at least 2·timestep (0.005 here), so the effective value differs from the file [Source](https://mujoco.readthedocs.io/en/stable/modeling.html).
  - *E7:* worst branch-speed mismatch in a tumble is 0.020 rad/s, negligible.
- **F11c (P2, class b). Contact stiffness and the impact metric.**
  - *Contact defaults:* geom `solref='.008 1'`, `solimp='.98 .999 .001'` (`aircraft.py:133`).
  - *E7, drops from 0.5 m:*

    | Initial descent | Result |
    |---|---|
    | 1 m/s | Peak single-contact force 9.8 kN |
    | 3 m/s (about 4.3 m/s at touchdown) | Gear bottoms (0.25 m stroke); airframe hits at 223 kN, about 23× weight; `crashed=True` |

  - *Static "impact":* sitting on the ground already logs `max_impact_n` = 2483 N. Gear loads count as "impact", and only the first contact of each geom pair is read (`aircraft.py:490`).
  - *Argon:* the 10 m run logged 2,338,465 N [Source](../../src/vtx/aircraft.py) [Source](../../evidence/argon_live_stability_calibration.json).
- **Gear statics (verified).**
  - *Spring rate:* stiffness = m_ref·g/(0.25/4), with m_ref = empty + 170 + 60 kg (`aircraft.py:172-176`).
  - *Compression at 996.67 kg:* expected 57.71 mm. Measured 56.16 mm (baseline) and 56.05 mm (critical-damping). The 1.5 mm gap is the unsprung gear mass.
- **Determinism.** MuJoCo stepping is deterministic (`tests/test_multibody.py:201`). But commands apply at issue time + 0.02 s on a wall-clock scheduler, with at most 40 steps per tick (`live_server.py`, anchors `issued_t_s` and the scheduler loop around `accum+=delta*lab.time_scale`). Live sorties are therefore not bit-reproducible from the command log alone [Source](../../src/vtx/live_server.py).

### Inferences
- Peak contact forces are solver-stiffness artefacts. Do not read them as structural loads or use them as crash-severity thresholds without a compliant contact model, or at least a stated filter.
- Switching to `implicit` changes the numerics of every sortie slightly. It needs a revision-ledger entry even though hover is unchanged to 0.001 deg/s.

### Gaps
- Free-flight drift was measured with aero and the governor removed. No full-model drift budget in manoeuvring flight was run.

## Key Question: Is the model free of atmosphere and wind effects that matter?

### Takeaway
There is no atmosphere model and no wind:
- ρ = 1.225 is hard-coded in the rotor model and the body drag;
- `self.wind` is a zero vector with no setter.

For VTX this is negligible: terrain tops out at about 57 m, a density change of about 0.5%. For Phantom it is a prerequisite, given an M 0.53 cruise and altitude-dependent engine power and SFC.

### Cited Findings
- **F13 (P2 for VTX, P1 for Phantom; class b).**
  - `aero.py:14` sets `rho=1.225`.
  - `aircraft.py:447` computes drag with a literal 1.225.
  - `aircraft.py:304` sets `self.wind=np.zeros(3)`. It is used at `aircraft.py:371` and `446` but never set [Source](../../src/vtx/aero.py) [Source](../../src/vtx/aircraft.py).
- **Terrain height.** The terrain maximum is about 57 m in the `TestWorld` heightfield (`world.py`), which the ray test at `tests/test_multibody.py:194` verifies [Source](../../src/vtx/world.py).

### Inferences
- Adding an ISA density and a wind/gust input is low risk for VTX. The wind plumbing already exists in both force paths, so a setter plus a mission field is enough for steady wind.

### Gaps
- There is no turbulence or gust specification for the test range.

## Key Question: Are configuration values, units, defaults and documentation consistent?

### Takeaway
There are several configuration drifts:
- the live mission, `retry()` and the `Aircraft` constructor each have different defaults;
- the calibration gate rejects the default gear;
- the Argon gains disagree between the report and its own evidence JSON;
- Argon gives a world-frame hub height as body-frame;
- smaller items: a stale docstring, a test-only G = 9.81, and a deliberate R6 override that the input file does not reflect.

### Cited Findings
- **F15 (P2, class c), from E10.**
  - *Three sets of defaults:*

    | Source | rpm | Gear | Fuel | Power | Time scale | Airframe |
    |---|---|---|---|---|---|---|
    | `Mission` (`live_server.py`, anchors `time_scale:float=Field(default=1.` and `gear_variant:str='critical-damping-proposal'`) and `Laboratory.__init__` | 1200 | critical-damping-proposal | 10 kg | 300 kW | 1.0 | not set |
    | `retry()` (anchor `reference_rpm=old.get('reference_rpm',800.)`) | 800 | baseline | 60 kg | 469.8 kW | 0.1 | not set |
    | `Aircraft.__init__` (`aircraft.py:265`) | 800 | not set | 60 kg | 469.8 kW | not set | light |

    E3 shows 800 rpm cannot hover: 1552 N per rotor at 30 deg against 2443 N needed.
  - *Calibration gate:* `tools/argon_calibration.py:101` rejects any gear other than `baseline`, while the live default is `critical-damping-proposal`.
  - *Argon gains:*

    | Source | kp | kd | ki | Position | kp_yaw | kd_yaw |
    |---|---|---|---|---|---|---|
    | Report | 0.62 | 0.32 | 0.24 | kp_pos 0.32 | 0.45 | 0.85 |
    | `evidence/argon_live_stability_calibration.json` | 0.58 | 0.30 | 0.22 | kp_vel 0.35 | 0.8 | 0.5 |

  - *Hub height:* rotor hub z is 2.31 m in the body frame (`evidence/source/airframe_ledger_r6.json` `rotor_pivots_m`, and `inputs/vtx_calibration_required.json`). Argon's "body geometry" uses 2.517, which is the world height at rest.
  - *Bearing offset:* `inputs/live_mechanism.json` gives `bearing_below_rotor_m` 0.28. R6 uses 0.33 (pivot z 1.98) through a deliberate override at `tools/build_airframe.py:123`; the input file was not updated.
  - *Gravity:* `physics_model.py:26` uses G = 9.81, against 9.80665 elsewhere. It is used only by `tests/test_physics.py`.
  - *Docstring:* `aircraft.py:49` says z 0.420..0.641, but the code uses 0.660..0.881 (`aircraft.py:61-81`).

  [Source](../../src/vtx/live_server.py) [Source](../../tools/argon_calibration.py) [Source](../../evidence/argon_live_stability_calibration.json) [Source](../../tools/build_airframe.py) [Source](../../inputs/live_mechanism.json)

### Inferences
- A crash after "Retry" is likely a configuration artefact: 800 rpm cannot hover even at 30 deg collective. Because crashes are treated as data, this would pollute the data set with non-physical lessons. It is the most consequential config drift.

### Gaps
- It is not possible to tell from the repo which Argon gain set was actually flown. The Argon run IDs are not retained under `evidence/flights`.

## Key Question: Are logging, evidence and the UI faithful to the physics (keyboard frames, horizon, labels, evidence side effects)?

### Takeaway
**In the cockpit, the keyboard's forward/back is correct but left/right is reversed.** The cockpit camera looks along cabin -Y, so the pilot's right is world -X, while D and ArrowRight act toward +X.

**The attitude horizon is built for X-forward.** In the -Y-forward cockpit it shows rotation about X as bank, but that rotation is actually pitch.

**Importing `vtx.live_server` writes into tracked evidence.**

**The physics audit cannot reconstruct requested-vs-achieved actuator states.**

### Cited Findings
- **F14 (P1 for pilot experience, class d; Phantom: yes, X-forward).**
  - *Camera:* the cockpit camera (`public/app.js:341`) looks along (0, -1, 0) in the cabin frame with up +Z, so the pilot's right is (-1, 0, 0) (E8).
  - *E8, closed hover for 1 s at trim, with the keyboard mix from `public/app.js:257-266`:*

    | Input | Response | Pilot's view |
    |---|---|---|
    | ArrowRight (tilt y +3 deg) | Δx = +0.063 m; body rate about +Y 6.46 deg/s | Moves and banks toward +X, the pilot's left |
    | KeyD (roll +0.3 deg differential) | Body rate about +Y 6.34 deg/s | Banks toward +X, left |
    | ArrowUp (tilt x +3 deg) | Δy = -0.064 m | Forward, correct |
    | KeyW (pitch +0.3 deg) | +X rate 5.86 deg/s | Nose (-Y) down, correct |

  - *Help text:* `public/index.html` says "The same controls work in the cockpit and external view".
  - *Horizon:* `public/app.js:315` maps `attitude[1]` to vertical offset and `attitude[0]` to bank.
  - *Engineering panel:* labels `gyro_world_deg_s` as `angular_rate_deg_s` (`public/app.js:296`) [Source](../../public/app.js) [Source](../../public/index.html).
- **F16 (P2, class d). Evidence and logging.**
  - *Import side effect:* `live_server.py` ends with a module-level `lab=Laboratory()`. With no checkpoint, the constructor writes an `outcome='interrupted'` `summary.json` into the newest unfinished run folder (anchor `interrupted=dict(run_id=meta['run_id']`). So importing the module from the repo root, as several tests do, mutates evidence.
  - *In this checkout:* `evidence/flights/20261101T201531-c2c85d/summary.json` already existed before this audit, dated 2026-11-02 22:20:51, from an earlier import. It was left untouched.
  - *Snapshot gaps:* `physical_snapshot()` lacks the active command and rate-limited targets (E5).
  - *Impact metric:* `max_impact_n` includes gear loads and reads only the first contact of a geom pair (`aircraft.py:484-490`).
  - *Retention:* the Argon run IDs cited in its report are not retained under `evidence/flights` [Source](../../src/vtx/live_server.py) [Source](../../src/vtx/aircraft.py).

### Inferences
- A pilot or LLM that learns in the cockpit view learns left and right backwards. Making the mixing view-relative, or just fixing the help text, is cheap. It avoids a whole class of "crash as data" sorties that teach nothing about the aircraft.

### Gaps
- The UI was checked by vector math and simulation only, not in a running browser, because no server was started.

## Key Question: What does the existing test suite cover, and what does it miss?

### Takeaway
The suites pass: pytest 133 passed with 1 warning in about 19 s, and node 5 of 5. None of the P0 defects above is caught, because the relevant tests:
- check only that an output changed (assist);
- use symmetric inputs (fuel);
- run with stationary rotors (angular momentum);
- or do not exist (packet frames, radar).

### Cited Findings
- **Test runs, in the scratch mirror to avoid the F16 side effect:**
  - `PYTHONPATH=src python -m pytest -q -p no:cacheprovider`: 133 passed, 1 warning, exit 0.
  - `node --test tests/test_camera_zoom.mjs tests/test_rotor_visual.mjs tests/test_tilt_direction.mjs`: 5 pass.
  - Outputs are in `scratchpad\audit\pytest_output.txt` and `node_test_output.txt` (in the scratch folder named in the preamble).
- **Coverage gaps:**

  | Test | Gap | Misses |
  |---|---|---|
  | `tests/test_training_assist.py:22-34` | Checks a change, not which pair moves | F1 |
  | `tests/test_multibody.py:164` | Equal tanks only | F3 |
  | `tests/test_multibody.py:101` | Torque-free test with stationary rotors | F11a |
  | None | Packet frames, radar on the ground, cockpit keyboard direction, "import does not write evidence" | F2, F4, F14, F16 |
  | `tests/test_tilt_direction.mjs` | Checks only the azimuth-to-xy mapping | — |

  [Source](../../tests/test_training_assist.py) [Source](../../tests/test_multibody.py) [Source](../../tests/test_tilt_direction.mjs)

### Inferences
- Each patch below comes with the test that would have caught its defect. Adding those tests first, expected to fail, gives a clean red/green record for the fix step.

### Gaps
- No coverage tool was run, so line coverage is unknown.

## Key Question: What should be patched, in what order, and how does each fix interact with four-fan flight behaviour and with Phantom?

### Takeaway
Patch order:
1. P0: the assist rate frame.
2. P0: fuel draw and exhaustion.
3. P0: body-frame packet channels.
4. P0: radar.
5. P1: config defaults.
6. P1: cockpit keyboard mixing.
7. P2: integrator `implicit`.
8. P2: governor integrator.
9. P2: logging and the import side effect.
10. P2: docs and labels.
11. P1 but larger: the aero upgrades (ducted momentum, edgewise inflow and momentum drag, VRS and windmill), behind flags.

Items 1, 2, 4, 5 and 7 change four-fan flight behaviour, as does 11 when its flag is on. Each of these needs a revision-ledger entry. Patches to `live_server.py` must wait for the Phantom build and are given by anchor.

### Cited Findings
Each item lists the exact change, the test that proves it, whether it changes flight behaviour, and how it interacts with Phantom. Evidence is in the sections above; sources are the files named.

1. **Assist rate frame (F1, P0).**
   - *Change:* in `src/vtx/aircraft.py:413`, replace `mjOBJ_BODY` with `mjOBJ_XBODY`:
     ```
     mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_XBODY,self.bids['airframe'],body_velocity,1)
     ```
     Make the same change at `tools/bench_rate_assist_dynamics.py:17`, then regenerate `evidence/training_assist_dynamic_check.json`.
   - *Test:* in `tests/test_training_assist.py`, build an R6 `Aircraft` with `stability_assist=1` and `_bench_apply_experimental_assist=True`. Set `qvel[3]=radians(10)` and step once. Assert that N (index 1) drops below the request, S (index 3) rises, and E/W are unchanged. Repeat with `qvel[4]`: E rises, W drops. Add a closed-loop check (the E1 case): roll rate below 1 deg/s at 1.5 s with the assist, against above 4 deg/s without.
   - *Flight behaviour:* changes whenever the wire is on. Needs a ledger entry.
   - *Phantom:* use the same helper for any body-frame velocity.

   [Source](../../src/vtx/aircraft.py)
2. **Fuel draw and exhaustion (F3, P0).**
   - *Change:* replace `aircraft.py:461` with a draw that conserves the total:
     ```
     if burn>0:
         remaining=burn
         while remaining>1e-15 and (self.fuel>0).any():
             live=self.fuel>0;share=remaining/live.sum()
             take=np.minimum(self.fuel[live],share);self.fuel[live]-=take;remaining-=take.sum()
         if not (self.fuel>0).any():self.flags.add('FUEL_EXHAUSTED')
     ```
     In `step()`, before the governor call, add `if 'FUEL_EXHAUSTED' in self.flags: self.engine_spool=0.`
     A defined feed schedule, such as fullest tank first, may replace the proportional split if the owner prefers.
   - *Test:* with `tank_fuel_kg=[0.1,2,2,2]` at 12 deg for 45 s, assert `abs(Σused - energy_engine_j/3.6e6*0.4) < 1e-6`. With all tanks at 0.01 kg, assert engine torque reaches 0 after exhaustion.
   - *Flight behaviour:* changes only with unequal tanks or exhaustion. Needs a ledger entry.
   - *Phantom:* reuse it if Phantom has more than one tank.

   [Source](../../src/vtx/aircraft.py)
3. **Body-frame packet channels (F2, P0).**
   - *Change:* in `live_server.py`, anchor `gyro_world_deg_s=np.round(`. Keep the world fields and add derived fields that use **no new RNG draws**, so the existing noise sequence and determinism are preserved:
     ```
     Rb=d.xmat[bid].reshape(3,3); gw=np.array(obs['gyro_world_deg_s']); vw=np.array(obs['gnss_velocity_mps'])
     obs['gyro_body_deg_s']=np.round(Rb.T@gw,3).tolist(); obs['velocity_body_mps']=np.round(Rb.T@vw,3).tolist()
     ```
     Also correct `evidence/ARGON_CALIBRATION_REPORT.md` §4.1 and the pilot reference: do not rotate the Euler roll/pitch, and use the body fields for rate damping and position-error rotation.
   - *Test:* at yaw 0, 90 and 180 with an injected body roll rate of 0.2 rad/s, assert `gyro_body ≈ [11.46, 0, 0]` deg/s within noise. Assert that attitude roll/pitch are invariant to yaw.
   - *Flight behaviour:* none; observation only.
   - *Phantom:* this is the shared seam, and Phantom is X-forward, so the body channels are what its pilot needs.

   [Source](../../src/vtx/live_server.py)
4. **Radar clearance (F4, P0).**
   - *Change:* in `live_server.py`, anchor `radar_clearance_m=round(float(pos[2]+1.56-.95-surface`, replace the formula with a downward ray from just below the lowest contact foot. Cache `foot_gids` once per aircraft: geoms whose body name starts with `gear`, or a ledger list for Phantom. This adds no RNG draw beyond the existing one.
     ```
     low=min(d.geom_xpos[g][2]-m.geom_size[g][0] for g in p.foot_gids); x,y=d.xpos[bid][:2]
     gid=np.zeros(1,np.int32); dist=mj.mj_ray(m,d,np.array([x,y,low-1e-3]),np.array([0,0,-1.]),None,1,-1,gid)
     radar=(dist if dist>=0 else low)+1e-3
     ```
     The ray uses the MuJoCo scene, so trees and boxes are included automatically.
   - *Test:* on the ground (r6, light, baseline), assert radar is within 0.01 of 0. Spawned 20 m above flat terrain, it should be within 0.01 of 20 minus the foot offset. Over a tree, it should read the tree top.
   - *Flight behaviour:* none in the physics, but every pilot landing gate changes. Record it in the ledger as an instrument change.
   - *Phantom:* needs its own foot list (skids or wheels).

   [Source](../../src/vtx/live_server.py)
5. **Config defaults (F15, P1).**
   - *Change:* in `live_server.py`, anchor `reference_rpm=old.get('reference_rpm',800.)`, change the fallbacks to the `Mission` defaults: 1200 rpm, `critical-damping-proposal`, 10 kg fuel, 300 kW, time_scale 1.0. Better still, read them from the `Mission` model so there is a single source of truth.
   - *Owner choice:* either relax `tools/argon_calibration.py:101` to accept the live default gear, or change the live default to `baseline`.
   - *Test:* `retry()` with an empty old request produces a mission equal to the `Mission()` defaults.
   - *Flight behaviour:* changes retried sorties. Needs a ledger entry.
   - *Phantom:* Phantom needs its own defaults block and must not inherit the VTX 800 rpm fallback.
6. **Cockpit keyboard mixing (F14, P1).**
   - *Change:* in `public/app.js:257-266`, when `cameraMode==='cockpit'`, rotate the (tx, ty) and (pitch, roll) inputs by cabin yaw plus the -Y-forward offset before mixing. At zero cabin yaw that gives `ty_world=-ty` and `roll_world=-roll`. In `app.js:315`, change the horizon to use bank = rotation about the view-forward axis.
   - *Alternative:* keep the mixing and change the `index.html` help text to "external view, +X right".
   - *Test:* a node unit test on an extracted pure mixing function: in the cockpit, ArrowRight gives a world tilt toward -X.
   - *Flight behaviour:* no physics change; pilot inputs change.
   - *Phantom:* Phantom is X-forward and needs its own forward axis.
7. **Integrator (F11a, P2).**
   - *Change:* in `aircraft.py:129`, change `integrator='implicitfast'` to `'implicit'`. Optionally set the equality `solref` at `aircraft.py:251,253` to `'.005 1'` so the file states what is actually effective.
   - *Test:* the torque-free E7b case (gravity 0, rotors at 1200 rpm, 20 s): assert |ΔH|/|H| < 1e-3. Keep the existing hover tests green.
   - *Flight behaviour:* changes slightly. Needs a ledger entry.
   - *Phantom:* benefits, since it also has spinning rotors.
8. **Governor overspeed integrator (F8a, P2).**
   - *Change:* in `governor.py:35`, clamp to the physical cap rather than the overspeed-zeroed cap: `self.integral_nm=max(0.,min(self.integral_nm,torque_cap_nm))`. Hold the integrator (no accumulation) while `overspeed` is true.
   - *Test:* force the speed to 1.02× target for 0.1 s, then return. Assert the integrator equals its pre-overspeed value ± Ki·error·dt.
   - *Flight behaviour:* changes only after overspeed events. Needs a ledger entry.
9. **Logging and the import side effect (F16, F9 logging; P2).**
   - *Changes:*
     - In `live_server.py`, move `lab=Laboratory()` (anchor `lab=Laboratory()`) into the server start-up path, such as a FastAPI lifespan or a lazy `get_lab()`, so that importing writes nothing.
     - Add `command`, `target_angles`, `cabin_target` and per-actuator saturation to `physical_snapshot()`.
     - Split `max_impact_n` into `max_gear_load_n` and `max_nongear_impact_n`, summing all contacts per body (`aircraft.py:484-490`).
   - *Test:* import `vtx.live_server` with `VTX_DATA_ROOT` pointing at a temporary copy that contains an unfinished run, and assert no file is created.
   - *Flight behaviour:* none.
   - *Phantom:* shared seam; Phantom adds its own surface actuators to the snapshot.
10. **Docs and labels (F8c, F9, F10, F15; P2).** No flight-behaviour change.
    - Rename "engine idle" to "engine shutdown" in the lease-expiry log, `index.html` and `docs/LIVE_LAB_IMPLEMENTATION.md`, or implement a real ground-idle spool level.
    - Delete or implement `nacelle_command_rate_deg_s=20` (`aircraft.py:329`).
    - Correct the Argon report: the actuator is a 5 deg/s slew, not τ = 0.08 s; the sensitivity is 210 N/deg, not 268; and use the evidence gain set.
    - Relabel the unflown rows at `tools/argon_calibration.py:55` as `model_reference`.
    - Fix the `aircraft.py:49` docstring.
    - Relabel `angular_rate_deg_s` as world (`app.js:296`).
11. **Aero model upgrades (F5, F6, F7, F13; P1, larger).**
    - *Changes in `src/vtx/aero.py`:* add optional `duct_sigma`, `kappa`, `tip_loss` and an edgewise speed `V_inplane`, and implement:
      - Glauert inflow: `T=2ρA·vi·sqrt((V_axial+vi)²+V_inplane²)`;
      - the ducted relation `T_total=ρA_exit·v_e·…`, with rotor share `T_rotor=T_total/(2σd)` in the ideal limit;
      - a momentum-drag vector `-ṁ·V_inplane`, returned to `aircraft.py:367-377` and applied at the hub;
      - Johnson's VRS inflow correction for -2 < V_axial/v_h < 0;
      - signed torque, by removing the `max(0,…)` clamps at `aero.py:55`.
    - *Atmosphere and wind:* add ISA ρ(z) and a wind setter, `Aircraft.set_wind(v)`.
    - *Flag:* keep everything behind `aero_model='open_bemt_v1'|'ducted_v2'` so existing evidence stays reproducible.
    - *Tests (closed form):*
      - the σd = 1 ideal power ratio is 0.707;
      - Glauert vi at 10 m/s matches the analytic value;
      - momentum drag = ρA·vi·V;
      - a VRS thrust dip appears at V = -v_h;
      - torque is negative at pitch 0 and V = -15 m/s.
    - *Flight behaviour:* large change. Needs a ledger entry and a new evidence baseline.
    - *Phantom:* required before any Phantom forward-flight card.

### Inferences
- Items 1-4 are small (1-15 lines each), independently testable, and together remove every P0.
- Items 1 and 2 live in `aircraft.py` and could land before the Phantom build finishes. Items 3, 4, 5 and 9 touch `live_server.py` and should be applied after it, by anchor.
- Item 11 is the main fidelity gap but needs duct geometry the repo does not have. Ship it flagged, with the ideal σd = 1 bound available and the open-rotor model as default.

### Gaps
- No patch was applied or run against the full suite, as the instruction was audit-only. The proposed tests are specified, not written.
- The revision-ledger format was not checked against each item.
