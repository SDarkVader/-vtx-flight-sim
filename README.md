# VTX-P0-V4 Flight Simulation

**Independent private repository for Vader's Taxis VTX flight simulation.** Not related to The Node.

**Current state:** recovered P0-V4 assembly, conditional multibody physics and a live interactive Stage 1 flight laboratory. Actual Colin control attempts include a failed takeoff and an airborne collision; no controlled A-to-B landing or real VTX flightworthiness is claimed.

[Open the live laboratory](https://sb-6iqplfebw9l2.vercel.run) · [Run locally and use keyboard controls](docs/LIVE_ACCESS.md) · [Engineering and flight findings](evidence/EXPERIMENT_REPORT.md). Hosting is a temporary, resumable Vercel Sandbox. Keyboard controls open in a closable pop-up; crash retries retain the failed run and pilot checkpoint. R4 and the experimental lighter R5 underside are selectable.

For Windows, download or clone this branch, install Python with the Windows `py` launcher, and run `launch-windows.bat` from the repository folder. The first launch installs the packages in `requirements.txt`; keep the command window open while using the game. It opens a local browser at `http://127.0.0.1:8765/`. The existing hosted URL is temporary and may no longer run the latest revision.

## Non-negotiable: Colin flies by wire

[Live fly-by-wire piloting contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). The proprietor selects start and destination; **Colin pilots through live controls from observations**, including physical takeoff and landing attempts. No autopilot pretending to be an agent, no precomputed trajectory driving motion and no playback substituted for flight. Deterministic replay is post-flight audit only.

## Required physics and source register

[PHYSICS_AND_RESEARCH_BASELINE.md](docs/PHYSICS_AND_RESEARCH_BASELINE.md) is the authoritative engineering baseline. The verified handoff source, original tests and historical PDFs are imported. The exact current Blendstra source and derivative component ledgers are retained. Independent conservation/mechanical checks and actual live attempts are recorded, with unresolved mass, aerodynamic and structural calibration explicit in [the experiment report](evidence/EXPERIMENT_REPORT.md). The executable model is conditional, not a validated physical aircraft.

## Primary engineering reference

[Saved P0-V4 Blendstra aircraft](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2)

Four independently tilt-vectoring ducted rotors, central two-seat spherical cabin, annular composite structure, four fuel cells, six landing contacts. Concept illustration is not verified CAD or measured dynamics.

## Colin's assignment

Implement a deterministic 6-DOF Newton–Euler flight dynamics model with quaternion attitude, four independently actuated ducted rotor thrust vectors, feedback control, saturation and gyroscopic effects, realistic contacts/collisions and a reproducible browser-hosted 3D interactive flight sandbox. Physics state must drive animation, never the reverse.

The user chooses **any valid takeoff position and destination on the map**. Colin must personally issue fly-by-wire controls based on live pilot observations to attempt ground takeoff, hover, navigation, turning, approach, touchdown and settling under simulated physics. Show failures and crashes; do not script success or suppress instability.

Stage 1 is a training/test world Colin builds. Persist versioned controller learning and experience. The proprietor later introduces a **previously unseen Stage 2 world**. No advance access or training on Stage 2. Evaluate transfer with continued learned state, and compare against fresh-start. Record failures and adaptation.

Use explicitly synthetic fixtures where VTX calibration is missing. Real CG/inertia, thrust/torque maps, actuators, drag, structural limits and aerodynamic effects must remain in a `CALIBRATION_BLOCKED` evidence register until established. Same seed, environment, input and integrator should reproduce the same trajectories/failures.

Acceptance: live playable browser preview; arbitrary map-valid A-to-B physics-driven takeoff-to-land attempt; independently commanded 4 rotors; deterministic success AND failure cases; complete telemetry, seeds, parameter provenance, scenario traces, learning checkpoints and test evidence. Preserve all source art/model provenance. Work independently and deliver reviewable PR and exact run commands.

See `COLIN_MISSION.md` for the execution contract. The verified `VTX_COLIN_ENGINEERING_HANDOFF.zip` supplied the starter snapshot and all 31 original tests. Its older instruction files remain archived and did not overwrite the current GitHub contracts. The earlier Git bundle/history at e768250 was not in the handoff; this provenance gap does not prevent running the imported snapshot.

New test defaults use 10 kg fuel, a 300 kW engine shaft ceiling and the 1200 rpm proposed gearset with bounded PI shaft regulation. A brief live low-fuel test lifted off and returned to supported rest near departure; no A-to-B mission or stable-flight qualification is claimed. [Fuel, power, exhaust calculations and the actual test](evidence/PROPULSION_FUEL_REVISION.md). Downward exhaust lift remains disabled pending installed flow/backpressure data.
