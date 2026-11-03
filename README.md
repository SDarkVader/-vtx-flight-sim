# VTX — Vader's Taxis

**A proprietary, physics-driven 3D VTOL flight game in active development.**

VTX puts the player in control of an experimental four-fan aircraft in an interactive 3D world. Take off, hover, manoeuvre around terrain and structures, navigate to a chosen destination and attempt a controlled landing. Aircraft movement is produced by the live physics simulation—not by a scripted flight path or a decorative animation.

**Status:** playable experimental prototype / flight-test game, **not a finished commercial release**. The repository is private. **All original VTX game content and code are proprietary; no use or commercial exploitation is permitted without prior express written permission.** See [LICENSE](LICENSE).

## Play the game

- **Manual flight:** take control of the four independently articulated ducted fans through the browser interface, keyboard inputs and live cockpit instruments.
- **AI-piloted flight:** connect an AI pilot that receives live observations and issues actual fly-by-wire commands. The pilot must respond to the evolving simulation rather than follow a precomputed route.
- **Missions and exploration:** choose valid departure and destination positions, fly through the test environment, avoid obstacles and attempt takeoff, navigation and landing.
- **Real consequences:** mass, gravity, inertia, actuator limits, contact dynamics and collisions affect each flight. Failures and crashes are recorded rather than concealed.
- **Flight evidence:** inspect telemetry, mission traces, controller actions and post-flight reports to understand what happened.

The 3D environment, visuals, controls and AI-pilot integration are under ongoing development. Some aircraft behaviours and flight scenarios remain uncalibrated or unproven.

## Getting started — Windows development build

This is a private developer/tester build, not a public download.

1. Obtain **written authorisation** from the rights holder and access to the private repository.
2. Install a supported Python version with the Windows `py` launcher.
3. Clone the repository and run `launch-windows.bat` from its root.
4. Allow the first launch to install the packages listed in `requirements.txt`.
5. Open `http://127.0.0.1:8765/` if it does not open automatically; keep the launcher running.

See [live access and manual controls](docs/LIVE_ACCESS.md) for the current keyboard mappings, flight modes and operational limits. Any previously shared hosted Vercel Sandbox URL is temporary and **not** a permanent game service.

## AI pilots and conversation

VTX is designed for **actual interaction between human operators, AI pilots and the simulated aircraft**. A connected agent can observe aircraft state, select controls, react to the resulting motion and participate in the flight-test workflow. AI flights are auditable through preserved records.

We have also experimented with conversational operation from a phone through an **external remote-command integration**, including live actuator demonstrations, flight observations and engineering changes. That workflow is experimental; it is **not a claim that a standalone in-game voice-chat feature has shipped**.

For the active pilot requirements, see the [live fly-by-wire pilot contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). Scripted paths, replay masquerading as live flight and unearned successful landings are not acceptable substitutes for genuine control.

## Second vehicle: VTX Phantom

The **Phantom** is VTX's second vehicle: an angular two-seat road car with four tilting wheel-fan pods, retractable wings, flaps, ailerons, nose canards, telescopic landing legs and two rear boosters. It is an opt-in, physically modelled variant (`src/vtx/phantom/`) and does **not** change the four-fan aircraft.

**Models.** Every Phantom number in `inputs/phantom_parameters_v1.json` carries a provenance label, mostly `SYNTHETIC_UNVALIDATED`; none is validated aircraft performance.

| Airframe option in the sim | Variant id | Wing cassette | Status |
|---|---|---|---|
| Phantom FX-A A10 · CURRENT PROTOTYPE | `phantom-fx` | A10 | Current prototype. FX-A propulsion and packaging design point (1.10 m fan-wheels, TG900 turbogenerator, nose battery), about 1,897 kg. |
| Phantom A10 · as drawn reference | `phantom` | A10 | The CAD as drawn, about 1,906 kg. Cannot lift off (thrust ceiling about 0.53 of weight); kept as the reference. |
| Phantom A9 · EARLIER VERSION | `phantom-a9` | A9 | Earlier wing cassette, kept for comparison with earlier flights. |
| Phantom FX-A A9 · EARLIER VERSION | `phantom-fx-a9` | A9 | FX-A with the earlier cassette. All 2026-11-03 campaign flights used this configuration. |

The **A10 split-level wing cassette** is the corrected wing configuration: both wings deploy at one height (A9 stacked them 118 mm apart), slide stroke 1.205 m, span 4.86 m, +9 kg. It passed a full clearance sweep with zero collisions and a MuJoCo check of all 28 joints. Source model: `assets/derived/phantom-a10-cassette.blend`; browser model: `public/assets/phantom-a10.glb`; Blendstra project *VTX Phantom A10 — Cassette model*.

**How it is flown in the simulation.**

1. Pick a Phantom option under **LOWER FRAME**, set departure A and destination B on the map, then start the sortie. The mission validator uses the Phantom's own footprint and wing span.
2. Fly it through the **Phantom FBW** panel (click **Take control** first; the panel is inert until engaged) or through the API with schema `phantom-fbw-1`. Humans and AI pilots use the same commands: collective, vertical-speed hold, pitch/roll/yaw, pod tilt (VTOL/road), legs, brakes, wing deploy/stow and canards.
3. The FBW has no position hold. A pilot must keep sending commands: if none arrives within 5 s of sim time, the command lease aborts and the fans brake.
4. Every run writes evidence to its run folder: the exact parameters and mass ledger, a 100 Hz step log, events with each pilot decision and its reason, and crash rings.

**Flight status (simulation only).** The FX-A has hovered and flown a 200 m hop to a 0.40 m/s touchdown 1.4 m from the target, but it has not passed the "controllable" gate (attitude overshoot, a pitch oscillation and weak yaw). Wings-deployed flight and speeds above 5 m/s have not been flown, and the A10 cassette has so far only been tested on the ground (deploy, lock and stow). See the [Phantom sim integration guide](docs/phantom/PHANTOM_SIM_INTEGRATION.md), the [A10 wing revision](docs/phantom/A10_WING_SYMMETRY_REVISION.md) and the [2026-11-03 flight test](docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md).

## Development status and engineering basis

The current prototype includes the Phantom second vehicle described above, a browser-based interactive flight laboratory, instrumented aircraft dynamics, four independently controllable ducted fans, manual controls, AI control interfaces, contact/collision handling and retained flight evidence. Alternate aircraft configurations and improved world presentation are experimental.

The underlying model is a conditional simulation. Its real-world aircraft parameters have **not** all been measured or validated. Recorded launches, airborne flights and collisions must not be confused with reliable autonomous navigation, successful end-to-end missions or real aircraft flightworthiness.

The simulation is built around a 6-DOF Newton–Euler / MuJoCo physics model, with a Python server and browser-based game interface. Modelled forces, torques, mass properties and actuators are intended to drive the rendered motion.

**Primary project documents:**

- [Engineering physics and research baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md)
- [Live flight interface and keyboard controls](docs/LIVE_ACCESS.md)
- [AI pilot operating contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- [Game and pilot development mission](COLIN_MISSION.md)
- [Experiment findings](evidence/EXPERIMENT_REPORT.md)
- [Flight evidence and recorded tests](evidence/)

The original aircraft concept and source provenance are documented in the engineering baseline; externally sourced models and reference materials do not automatically become VTX-owned assets. VTX is separate from *The Node* project.

## Ownership, licensing and commercial enquiries

**Copyright © 2026 Steven Dark (SDarkVader). All rights reserved.**

VTX is **proprietary software and game content, not open source**. No permission is granted to use, run, reproduce, copy, modify, adapt, redistribute, publish, host, sublicense, sell, commercially exploit or train models on original VTX content without prior express written authorisation from the relevant rights holder, subject to non-excludable legal rights.

Access to this private repository is not itself a licence. For commercial licensing, collaboration, testing or other permissions, contact the owner via [GitHub](https://github.com/SDarkVader).

Third-party dependencies and externally sourced materials remain subject to **their own licences and rights**. See the full [proprietary licence notice](LICENSE). The game is not suitable for operating real aircraft or for safety-critical engineering use.
