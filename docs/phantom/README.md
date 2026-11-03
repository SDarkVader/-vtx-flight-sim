# VTX Phantom — minimum functional flight rig

**Status:** the Phantom is VTX's second vehicle and runs in the simulator ([integration guide](PHANTOM_SIM_INTEGRATION.md)). The current prototype is **Phantom FX-A A10** (`phantom-fx`); the A9 cassette stays selectable as the earlier version. The FX-A has hovered and flown a 200 m hop in simulation but has not passed the controllability gate. This package is not an airworthiness, CFD or structural approval.

**Design lock:** VTX Phantom angular two-seat vehicle, driver and passenger only; retractable wings hidden behind the body, two inboard flaps, two outboard ailerons, two nose canards, four road/wheel thrusters, two rear boosters, telescopic landing legs, actual engine/radiator/brake cooling and side pressure-relief vents. Rolling or VTOL take-off/landing; minimum 200 mph road *top speed* and 400 mph flight *maximum target*, **neither a mandatory take-off nor cruise speed**.

[Exact Blendstra A8 appearance reference](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=b77e9377-f1b3-4177-ba4e-c1af1d4ed8b2&version=version_a5589426caea8f9c2a6b690671aa8a9387ceff32eaef358186236dbd4de18752) — reference CAD only; the currently clipping wing path and incomplete load-bearing root must be redesigned.

## What makes it fly in our simulation?

The full exterior does **not** have to be manufactured or completely modelled. The rig does need:

- **A mass-bearing, colliding hull**, full CG/inertia ledger, two occupant masses, fuel and energy masses; gravity and genuine ground contact.
- **Actuated propulsors**: four wheel thrusters with direction, spool, torque, power, inertia and limits; two aft units with finite response and force application coordinates.
- **Aerodynamic lifting surfaces**: left/right wings, outboard ailerons, inboard flaps and nose canards that apply lift/drag and pitch/roll/yaw moments from **relative airflow**, not from pre-scripted poses.
- **Deployment mechanics**: left/right side hatch, wing slide, wing fold, flight locks, landing legs and wheel conversion, all finite-rate and with real collision sweeps.
- **Electric and energy model**: finite turbine/generator or synthetic generator, HV distribution, peak-power buffer, motors, cooling consumption and protection/fault states; source and sink energy accounting.
- **One pilot interface**: human and Colin use the same commands; no future trajectory injection, altitude rescue or perfect hidden stabiliser.
- **Instrumented simulation**: requested vs achieved position/force/torque, mass and CG, power, SOC/fuel, heat, collision and fault traces.

Existing code is already split into **`src/vtx/aircraft.py` (MuJoCo), `src/vtx/aero.py` (provisional rotor aerodynamics), `src/vtx/live_server.py` (live controller/evidence), and `src/vtx/physics_model.py` (separate 6-DOF study)**. These are the factual integration seams. The old aircraft's nominal engine ceiling and rotor allocation must **not** be silently transplanted onto the Phantom.

## Four documents to use

1. [Flight system and controls contract](SYSTEMS_CONTRACT.md) — control ports, force calculation and power/electrical interfaces.
2. [Manufacturer and physics reference register](SOURCE_REGISTER.md) — official documents, what the sources establish and what remains unknown.
3. [Synthetic component specification](SYNTHETIC_COMPONENTS.md) — substitute missing hardware with accountable code, not magic forces.
4. [Phased testing and acceptance](TEST_PLAN.md) — independent flight progression and measurable failure tests.
5. [Wing cassette Stage 1 study](WING_CASSETTE_STUDY.md) — measured A8 defects, load envelope, root-joint comparison and the configuration decision for the retractable wing.
6. [A9 wing cassette revision](A9_WING_CASSETTE_REVISION.md) and [A9 MuJoCo handover](A9_MUJOCO_HANDOVER.md) — earlier version: built telescopic cassette, flaps, ailerons and canards, verified clearances, component sizing and integration data.
7. [A10 wing symmetry revision](A10_WING_SYMMETRY_REVISION.md) — the corrected, current wing configuration: split-level cassette with both wings at one height.
8. [Phantom sim integration](PHANTOM_SIM_INTEGRATION.md), [2026-11-03 flight test](PHANTOM_FLIGHT_TEST_20261103.md) and [cockpit log](PHANTOM_COCKPIT_LOG_2026-11-03.md) — how it is flown in the simulation and what has been flown.

**Version boundary:** documentation on a separate `docs/phantom-flight-systems-20261102` branch; preserve the currently flown four-fan aircraft, any live pilot checkpoints and the working-tree changes on `fix/mobile-flight-view-performance`.

**Source provenance:** [Phantom engineering investigation in Notion](https://app.notion.com/p/40c59e49d35c8105b78de2af8c276039). Sources and figures are screening examples until physically identified for the Phantom.

## Simplest path to a genuine test

1. Build the isolated Phantom **hover** plant with 4 finite-thrust pods, energy source and contact.
2. Demonstrate a power-on hover and genuine descent/power-off freefall; log actual physics.
3. Add two fixed lifting surfaces + canards + ailerons + flaps; test force/moment response in air relative to wind.
4. Add independent wing cassette/hatch and wheel retraction, with clearance checks throughout the full path.
5. Increase airspeed through validation gates, **not** by choosing values to make the test pass.

Success means Colin or the human pilot can take off, manoeuvre and land by **real commands**, while power, energy and control authority remain finite and auditable. A render, static lift calculation or scripted flight does not count.
