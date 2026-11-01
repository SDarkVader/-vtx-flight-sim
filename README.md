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

## Development status and engineering basis

The current prototype includes a browser-based interactive flight laboratory, instrumented aircraft dynamics, four independently controllable ducted fans, manual controls, AI control interfaces, contact/collision handling and retained flight evidence. Alternate aircraft configurations and improved world presentation are experimental.

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
