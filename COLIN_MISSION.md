# VTX virtual flight-test laboratory — Colin implementation contract

## Goal

Take the **saved VTX P0-V4 aircraft geometry** and the **starter package already in this folder**, and produce one coherent, interactive cloud flight-test sandbox **and** a reproducible headless regression campaign. Complete the assignment end-to-end rather than stopping at repository setup. Work in a NEW private `vtx-flight-sim` repository, separate from `The-Node`. The production baseline is the exact saved Blendstra version in `README.md` and `docs/INPUT_PROVENANCE.md`; the current repo has no flight simulator yet.

## Primary deliverable: an aircraft actually flying in a sandbox

Read `docs/INTERACTIVE_SANDBOX_CONTRACT.md` **before coding**. The working 3D browser sandbox—not a static concept board or merely CSV output—is the user-facing deliverable. It must render the integrated 6-DOF plant state with independent F1–F4 rotor thrust and tilt; commands, telemetry and visualised motion must agree. The same canonical aircraft model is revised based on simulation evidence. The supplied image is style reference only, not geometry or validated hardware.

## Mission-critical interaction: map-selected A → B takeoff, flight and landing

**The proprietor chooses both ends of the flight.** In the interactive map, let them select **any geometrically and operationally valid departure location** and **any valid destination**, not just pre-built pads or hardcoded waypoints. Show validation reasons for invalid selections. Pressing **Fly** starts the actual 6-DOF aircraft **stationary on the ground at A**, then the autopilot must take off using rotor forces, climb/hover, fly the route under speed/jerk limits, negotiate turns and obstacles using allowed observations, approach B, physically land and settle on its gear. Do not teleport, clip through objects, use keyframed position, reset at B or mark success while airborne. Contact/impact can result in a crash, hard landing or rejected mission.

This user-selected point-to-point mission is **required Stage 1 functionality**, not optional polish after the simulator is built. Run deterministic A→B tests on multiple valid source/destination pairs, include invalid locations and unrecoverable cases, and record source/destination, route, hover/landing state, touchdown contact/velocity, fuel, stability and independent F1–F4 response. Stage 2 uses the **same interaction** on the user-supplied unseen map, loading the frozen Stage 1 learned checkpoint first. See [`docs/MAP_TO_MAP_FLIGHT_CONTRACT.md`](docs/MAP_TO_MAP_FLIGHT_CONTRACT.md) and the new `src/vtx/mission_selection.py` selection-contract skeleton. **The skeleton is not the aircraft control implementation.**

## Two-stage learning and environment handoff

The proprietor will later introduce an **unseen second environment**. Do **not** invent or pre-load it. Colin must first build a working Stage 1 environment, develop and persist learned/adaptive controller state from observable experience, and then support a future Stage 2 handoff **without resetting that experience**. Compare warm-start versus cold-start adaptation using identical seeds and physical model. Record failures rather than protecting the pilot artificially. The exact requirements are in [`docs/STAGED_ENVIRONMENT_TRANSFER.md`](docs/STAGED_ENVIRONMENT_TRANSFER.md); implement the Stage 1 interface and checkpoint workflow now. Stage 2 exposure/testing occurs only when the proprietor supplies the second environment.

## Nonnegotiable constraints

1. **Physics over animation.** Dynamics must integrate translational and rotational states from forces/moments; NEVER write state or altitude directly toward the reference trajectory. Animation is a derived visualization of the integrated state.
2. **Four independent rotor controls.** Each rotor must have its own thrust/collective state and two tilt-axis states, constraints, sign convention, actuator lag and measurements. Model yaw coupling, roll/pitch cross-coupling and any rotor reaction/gyroscopic terms explicitly.
3. **No fake calibration.** Preserve the nulls in `inputs/vtx_calibration_required.json`; no arbitrary CG, inertia, actuator or aerodynamic numbers masquerading as established VTX properties. Create separate `fixtures/SYNTHETIC_*.json`, prominently labelled uncalibrated with provenance, for numerical verification and illustrative control experiments. Never silently use synthetic parameters for a VTX claim.
4. **Keep sources and geometry version pinned.** Retain component/research provenance, link to Blendstra P0-V4, record the mass ledger as a budget, not actual mass. Source PDF figures are historical, not measurements of the V4 aircraft.
5. **Cheap cloud execution.** CPU-only browser sandbox and GitHub Actions/Codespaces initially, no paid APIs, GPUs or cloud infrastructure. Add deterministic seeds, pinned dependencies, machine-readable output and CI artifacts.
6. **No misleading success flags.** Numerical/benchmark pass is distinct from VTX calibration, physical stability, rotor-out viability and airworthiness. Document known model omissions and any untested scenario.

## Implement and execute in one assignment

### A. Reproduce and provision

- Create private repo and import starter; confirm SHA hashes, Python version, baseline `PYTHONPATH=src python -m pytest -q` (21 existing tests) and `PYTHONPATH=src python scripts/run_reference.py --out results`.
- Preserve CI and configure full regression plus headless-simulation smoke tests on push/PR. Do not accidentally commit caches, generated figures, secrets or large source artifacts. Separate deterministic review artifacts from source as appropriate.

### B. Build validated numerical plant

- Implement true coupled Newton–Euler **6-DOF** with quaternion body-to-world attitude, positive-definite body inertia, variable center-of-gravity and full 3-D moment arms. Use a fixed sign convention and explicitly defined reference frames. Include gravity, external wind/aero force and moment hooks, rotor reaction torque and gyroscopic moment hooks. Add a standard ODE integrator (`solve_ivp` is acceptable) and quaternion normalization safeguards.
- Independently model rotor thrust-magnitude state and two tilt-axis states, first-order lag/rate limits, max thrust and max tilt, physically consistent force directions, power and torque bookkeeping hooks. Limits sourced from actual data only when documented; synthetic-only limits belong in separate fixtures.
- Test static equilibrium, free-fall, inertial force/moment conservation, motor/rotor sign reversal, quaternion norm, symmetric hover, asymmetric CG, altitude coupling and a nontrivial manoeuvre against analytic benchmark solutions.

### C. Controller and allocation

- Implement a layered trajectory controller: position/velocity/altitude outer loop, orientation/rate inner loop, per-rotor constrained allocation to six-axis force/moment wrench, and actuator command generation. Clearly separate command, measured plant output and estimator (perfect state is permitted only as a `SYNTHETIC_PERFECT_STATE` baseline).
- Implement **independent controls for F1–F4**: demonstrate that a corner is NOT executed by sending identical actuator commands to all four. Log each rotor's thrust, two tilt angles, reaction torque contribution, saturation, power estimate and actuator tracking error.
- Enforce and log thrust and tilt feasibility, rate limits, power availability assumptions and numerical solver failure. Prefer a clear INFEASIBLE or SATURATED result to clipping and concealing residual moments.

### D. Run reproducible flights

- Actual ground-contact takeoff, climb, hover and destination landing from arbitrary valid user-selected map points; straight-line acceleration and deceleration; both left and right 90° turns at 10/20/30 mph; abort/braking; a mass/CG change scenario. Use the **existing jerk-limited trajectories** in `src/vtx/urban_reference.py`, not a new unrelated flight path.
- Measure actual simulated altitude/vertical speed deviation, path/heading/yaw/roll/pitch error, acceleration and jerk in the passenger frame, stop distance, energy, rotor saturation, commanded-versus-achieved wrench, end-of-run state and integration residuals. Include plots: 3D path, time histories, four-rotor commands, attitude/altitude, passenger loads and uncertainty runs.
- Disturbance envelope: controlled wind/side gust, asymmetric fuel load/CG, sensor noise, actuator delays, reduced rotor authority, actuator stuck/failed, and a rotor-out case. For each case, identify whether controllability or tracking is mathematically/physically feasible under the stated parameter fixture; do not assert survival without validated limits.

### E. Deliver and validate the interactive 3D sandbox

- Expose the integrated plant in a cloud-accessible browser 3D application. Prefer an inexpensive Python+Three.js stack or equivalent that runs in Codespaces. No pre-scripted model poses or keyframed aircraft motion. Live controls include map-click departure and destination selection with validation, Fly, Abort, takeoff and touchdown state, hover, acceleration, braking, 10/20/30 mph turns, pause/reset, and manual target velocity/heading/altitude.
- Import the exact P0-V4 GLB if available through authorized access, preserve the model version ID and scale; otherwise use an explicitly labelled geometric proxy while keeping the missing-asset gate visible. Concept image in `refs/` is not a geometry substitute.
- Display independent nacelle articulation and per-rotor thrust (F1–F4) from the solver, plus real altitude, bank, yaw rate, speed, comfort jerk and any saturation or instability. Never conceal a loss of control.
- Demonstrate at least one self-contained hover → accelerate → turn → decelerate sequence using synthetic verified fixture with numeric replay; render the achieved 3D path, not a predetermined trajectory. Include run evidence and screenshots of this actual simulator.
- Treat the runtime, geometry and mass/inertia register as a closed design/simulation feedback cycle, described in `docs/INTERACTIVE_SANDBOX_CONTRACT.md`.

### F. Analyse, test and report

- Make tests fail on impossible values (negative masses, non-PD inertia, invalid geometry, missing calibration, falsely reported stable outcomes, over-limit rotor commands, energy/power inconsistencies). Add deterministic seeds and compare time-step convergence.
- Produce `results/mission_summary.json`, `results/parameter_provenance.json`, per-scenario CSV/JSON and plots, and a short `docs/ENGINEERING_RESULTS.md` describing equations, assumptions, verification, success/failure and data needed next. Include a sensitivity table so we know which missing parameters matter most.
- Recommend the minimum **actual** VTX inputs needed to move out of `CALIBRATION_BLOCKED`: part-by-part mass and 3D centroid, inertia tensor, fuel/slosh distribution, rotor thrust/torque maps, gyroscopic rotor inertia, actuator dynamic response/limits, gearbox power losses and aerodynamic data. If any can be extracted directly from the pinned Blendstra source, calculate them with provenance; do not infer material density from appearance.

## Definition of done

- Cloud repo/CI works, all 21 starter tests remain passing, and newly added dynamics/control tests pass.
- A working Stage 1 environment and a persistent, versioned adaptive-state/checkpoint interface ready to accept the proprietor's unseen Stage 2 environment, without resetting learned state or leaking unseen parameters.
- A working interactive 3D browser sandbox and at least one **numerically integrated synthetic** ground takeoff → hover → user-selected destination route with a coordinated corner → deceleration → physical touchdown sequence run, with independently varying four-rotor controls, recorded achieved motion and in-app status labels.
- Numerical conservation, unit and convergence tests demonstrate correctness. Trajectory-tracking error and comfort criteria are **measured and reported**, not hard-coded as passed; failure is legitimate evidence.
- Runs/plots/JSON are reproducible from documented commands and exact commit SHA; reviewable PR with a clear changed-file list and output artifacts.
- `CALIBRATION_BLOCKED` remains active for all **actual VTX-P0-V4 stability/flightworthiness claims** until measured properties exist. Do not report a synthetic successful run as an aircraft flight test.

**Stop only on an actual blocker:** lost repository authorization, unexpected paid expense, no permission for cloud execution, or a design decision that materially changes the aircraft. Otherwise choose explicit, clearly labelled development defaults, run the job, and report evidence without asking what to do next.