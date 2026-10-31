# VTX-P0-V4 Flight Simulation

**Independent private repository for Vader's Taxis VTX flight simulation.** Not related to The Node.

**Current state:** repository scaffolding only. A fully coupled, interactive 3D flight simulator does not yet exist, and no VTX flightworthiness or calibrated stability result is claimed.

## Non-negotiable: Colin flies by wire

[Live fly-by-wire piloting contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). The proprietor selects start and destination; **Colin pilots through live controls from observations**, including physical takeoff and landing attempts. No autopilot pretending to be an agent, no precomputed trajectory driving motion and no playback substituted for flight. Deterministic replay is post-flight audit only.

## Required physics and source register

[PHYSICS_AND_RESEARCH_BASELINE.md](docs/PHYSICS_AND_RESEARCH_BASELINE.md) is the authoritative engineering baseline. Current published repository has design requirements and physics research only; it does **not** yet contain the complete starter source or validated executable aircraft. No flight or unit-test results have been independently verified on GitHub.

## Primary engineering reference

[Saved P0-V4 Blendstra aircraft](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2)

Four independently tilt-vectoring ducted rotors, central two-seat spherical cabin, annular composite structure, four fuel cells, six landing contacts. Concept illustration is not verified CAD or measured dynamics.

## Colin's assignment

Implement a deterministic 6-DOF Newton–Euler flight dynamics model with quaternion attitude, four independently actuated ducted rotor thrust vectors, feedback control, saturation and gyroscopic effects, realistic contacts/collisions and a reproducible browser-hosted 3D interactive flight sandbox. Physics state must drive animation, never the reverse.

The user chooses **any valid takeoff position and destination on the map**. Colin must personally issue fly-by-wire controls based on live pilot observations to attempt ground takeoff, hover, navigation, turning, approach, touchdown and settling under simulated physics. Show failures and crashes; do not script success or suppress instability.

Stage 1 is a training/test world Colin builds. Persist versioned controller learning and experience. The proprietor later introduces a **previously unseen Stage 2 world**. No advance access or training on Stage 2. Evaluate transfer with continued learned state, and compare against fresh-start. Record failures and adaptation.

Use explicitly synthetic fixtures where VTX calibration is missing. Real CG/inertia, thrust/torque maps, actuators, drag, structural limits and aerodynamic effects must remain in a `CALIBRATION_BLOCKED` evidence register until established. Same seed, environment, input and integrator should reproduce the same trajectories/failures.

Acceptance: live playable browser preview; arbitrary map-valid A-to-B physics-driven takeoff-to-land attempt; independently commanded 4 rotors; deterministic success AND failure cases; complete telemetry, seeds, parameter provenance, scenario traces, learning checkpoints and test evidence. Preserve all source art/model provenance. Work independently and deliver reviewable PR and exact run commands.

See `COLIN_MISSION.md` for the execution contract. The user's earlier full starter package (`vtx-flight-sim-map-missions.zip` and Git bundle) is still the source for the existing 31 numerical and mission-selection tests; **those local files have not yet been fully imported into this remote repository**.
