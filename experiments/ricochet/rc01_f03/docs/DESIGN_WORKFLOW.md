# VTX model-design workflow — RC-01 evidence-based baseline (2026-11-11)

This describes the **design-development process** used today. It is provisional and should be reused as a pattern, not a claim that the aircraft is certified or flightworthy.

1. **Mission & acceptance questions:** specify intended operation, not artistic constraints. RC-01 is a single-seat buoyant forward-propelled amphibious craft; *hover is not a requirement*. Test forward motion, controlled yaw/pitch/roll, flotation and recoverability before water takeoff.
2. **Evidence & axes:** pin the simulator's gravity, air reference and coordinate frames, and record source revisions. VTX MuJoCo +X forward/+Y left/+Z up is distinct from early RC-01 labelled +Y starboard. Reflect polar and axial vectors correctly; never reinterpret Euler angles without an explicit world/body convention.
3. **F01 structural skeleton:** dimension principal frame (199 primary members, 107 nodes) with connected load paths, shared junctions and zero non-shared crossings in the *geometric check*. Reserve real joints and actuators upfront.
4. **F02 internal structure:** add 7 bulkhead webs, 15 putative bond-interface standoffs and 15 movable-part envelopes. Record local positions and provisional masses. This is a layout, not structurally qualified or watertight construction.
5. **F03 sealed-geometry candidate:** loft the six hull stations, check that the triangle mesh is manifold and oriented, and compute gross volume. This does not prove that real shells, hatches or penetrations seal.
6. **Initial statics and dynamic probe:** calculate submerged volume/force, buoyancy centre, CG/inertia assumptions, restoring roll/pitch, drag and thrust. Use shared SI gravity and nominal atmosphere. Munk-type terms remain identified *sensitivities*, not coefficients from experiments. Run stable and destabilizing cases; record them all.
7. **Independent numerical and visual audit:** timestep sensitivity (0.02 vs 0.01 s), heading projection, body-forward velocity, sign tests and visual/trajectory agreement. The F03 animation initially failed the yaw-offset visual check; record a corrective change without altering recorded physics.
8. **Evidence archive:** store source, model revision, test configuration, raw time series, convergence, renders, failures and authoritative version links. Mirror to Drive; commit compact, reproducible sources and key raw data to GitHub. Never make generated media a substitute for original telemetry.
9. **Isolated game adapter:** create a new opt-in lake-fixture and RC-01 runtime variant only when the geometry/physics contract passes. Do not change R6/Phantom canonical physics, landing validators, save schemas or live cockpit implicitly.
10. **Iteration:** compare revised hull, keel, float movement, propulsive moments and mass distribution against F03 with identical test cases. Record revision diffs, mass and inertia deltas, load-path failures, source references and invalid runs without excluding data.

### Required run record

`run_id`, UTC timestamp, git commit, model revision and sha256, parameter/solver hash, world seed, explicit lake geometry and bed depth, gravity/atmosphere/water density, time step and integrator, CG and inertia tensor, mass ledger, thrust schedule, hinge/joint definitions, commands, force/moment histories, body pose and velocity in both frames, equilibrium residuals, stability metrics, pass/fail gates, and raw failure classification.

### Non-negotiable quality gates

- No unconnected load path or unqualified mechanical part presented as fabricated structure.
- No collider/mesh mismatch, invented watertightness, or force surface outside submerged hull.
- No hidden altitude/yaw corrections to make a test look successful; controller action is force/moment based, with authority and saturation logged.
- No dynamic joint response claimed from section-force arrows alone.
- No mixing the F03 reduced-order test with the game MuJoCo integration results.
- No merge to main before independent frame, hydrostatic, thrust/drag, mass-ledger, run reproducibility, and real-scene isolation checks.
