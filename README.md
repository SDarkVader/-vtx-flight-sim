# VTX — Vader's Taxis

**A proprietary, physics-driven 3D VTOL flight game in active development.**

VTX puts the player in control of experimental VTOL aircraft in an interactive 3D world: the original four-fan aircraft and the **VTX Phantom A10**, a two-seat road, VTOL and wing-borne vehicle design. Take off, hover, manoeuvre around terrain and structures, navigate to a chosen destination and attempt a controlled landing. Aircraft movement is produced by the live physics simulation—not by a scripted flight path or a decorative animation.

**Status:** playable experimental prototype / flight-test game, **not a finished commercial release**. This GitHub repository is currently public. **All original VTX game content and code are proprietary; no use or commercial exploitation is permitted without prior express written permission.** See [LICENSE](LICENSE).

## Play the game

- **Manual flight:** take control of the four independently articulated ducted fans through the browser interface, keyboard inputs and live cockpit instruments.
- **AI-piloted flight:** connect an AI pilot that receives live observations and issues actual fly-by-wire commands. The pilot must respond to the evolving simulation rather than follow a precomputed route.
- **Missions and exploration:** choose valid departure and destination positions, fly through the test environment, avoid obstacles and attempt takeoff, navigation and landing.
- **Real consequences:** mass, gravity, inertia, actuator limits, contact dynamics and collisions affect each flight. Failures and crashes are recorded rather than concealed.
- **Flight evidence:** inspect telemetry, mission traces, controller actions and post-flight reports to understand what happened.

The [flight index](docs/FLIGHT_INDEX.md) lists each retained sortie by run ID and model, with a compact summary and a pointer to its PC data. The [single cockpit guide](docs/UNIFIED_RUNTIME.md) explains the vehicle selector and local archive.

The 3D environment, visuals, controls and AI-pilot integration are under ongoing development. Some aircraft behaviours and flight scenarios remain uncalibrated or unproven.

## Aircraft

Choose the airframe under **Lower frame** on the mission panel.

- **Four-fan VTOL (R6, default):** the original experimental aircraft, with four independently articulated ducted fans.
- **VTX Phantom A10 (opt-in, synthetic):** the option labelled **"Phantom FX-A A10 · CURRENT PROTOTYPE"** (variant `phantom-fx`), with **"Phantom A10 · as drawn reference"** (`phantom`) beside it. The A9 variants are earlier versions kept for comparison.

**What the Phantom A10 is.** An angular two-seat vehicle designed to drive on the road, lift off vertically on four ducted fans inside tilting wheel pods, and fly on retractable wings. It has two rear boosters, telescopic landing legs, and wings that slide out of a split-level cassette behind the cabin (the A10 puts both wings at one height), with flaps, ailerons, two nose canards and raked twin fins. Power is turbogenerator-electric with a battery buffer. The FX-A prototype is a design proposal with Ø0.90 m fans in Ø1.10 m fan-wheels, a 900 kW take-off turbogenerator and a nose battery; the as-drawn reference has Ø0.49 m fans and two 600 kW turbogenerators. The mass ledger puts the as-drawn A10 at 1.9 t.

**Where it stands.** Every Phantom number is a labelled synthetic or derived figure, not a measurement. As drawn, its lift fans cannot hover it (thrust-to-weight 0.52 measured in the plant). The FX-A prototype changes the fans and the power plant; its test record is in the [flight-test report](docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md). In the physics plant, on a flat test strip with canned pilot schedules (not game flights), the as-drawn A10 left the ground under wing lift in 8 of 11 rolling take-off runs, at 69 to 106 m/s, and the best reached 32 m. With the optional stabilator, turbine-booster and wing-incidence proposals it lifts off at 60 to 95 m/s. **Every flight so far ended in a pitch loss of control: none is a controlled flight, a landing or a mission.** See [first take-offs and flights](docs/phantom/A10_FIRST_FLIGHTS_20261104.md).

**3D model.** The current refined model, with smooth bodywork, livery, a visible wing-cassette window, carbon and titanium DRS flap, vectoring booster cowls and alloy VTX wheels, is here:

- [`public/assets/phantom-a10-visual.glb`](public/assets/phantom-a10-visual.glb): the model the game loads, driven joint by joint from the simulation.
- [`assets/derived/phantom-a10-cassette-visual.glb`](assets/derived/phantom-a10-cassette-visual.glb): an animated preview with 28 animations (wings, hatches, canards, flaps, locks).

GitHub does not render `.glb` files, so download either one into any glTF viewer. Add `?cad=1` to the game address to load the raw CAD export instead. How the refinement is built: [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md).

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

**Voice commands (Phantom).** The Phantom operator panel has a push-to-talk **🎙 Voice** button (Chrome or Edge). Speech is matched against a fixed command grammar: no language model sits in the control loop. Each command goes through the same fly-by-wire heartbeat, lease and authority checks as the sliders, is read back aloud and is logged. Risky commands (stow wings, retract legs, engine off) need a spoken "confirm". See [voice pilot](docs/VOICE_PILOT.md).

We have also experimented with conversational operation from a phone through an **external remote-command integration**, including live actuator demonstrations, flight observations and engineering changes. That workflow is experimental; it is **not a claim that a standalone in-game conversational voice-chat feature has shipped**.

**Model-call audit.** An external AI pilot's model calls can be recorded for later inspection: [`pilot_exchange`](docs/PILOT_EXCHANGE_AUDIT.md) (one redacted record per decision, written by the caller) and the opt-in [OpenAI pilot recorder](docs/OPENAI_PILOT_RECORDER.md) (streams observations, accepted actions and model replies to `pilot-api.jsonl`; the model's reply is informational and never commands the aircraft).

For the active pilot requirements, see the [live fly-by-wire pilot contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). Scripted paths, replay masquerading as live flight and unearned successful landings are not acceptable substitutes for genuine control.

## Development status and engineering basis

The current prototype includes a browser-based interactive flight laboratory, instrumented aircraft dynamics, four independently controllable ducted fans, the opt-in Phantom A10 with its mass and centre-of-gravity ledger, manual controls, voice commands, AI control interfaces, contact/collision handling and retained flight evidence. Alternate aircraft configurations and improved world presentation are experimental.

The underlying model is a conditional simulation. Its real-world aircraft parameters have **not** all been measured or validated. Recorded launches, airborne flights and collisions must not be confused with reliable autonomous navigation, successful end-to-end missions or real aircraft flightworthiness.

The simulation is built around a 6-DOF Newton–Euler / MuJoCo physics model, with a Python server and browser-based game interface. Modelled forces, torques, mass properties and actuators are intended to drive the rendered motion.

Phantom design changes are carried as **proposals that are off by default** (`proposals.*` in `inputs/phantom_parameters_v1.json`), each with a unit, a source and a provenance label. `tools/phantom/phantom_campaign.py` runs the performance campaign, and `tools/phantom/a10_cg_placement.py` screens hardware placement for mass, centre of gravity and inertia. CI runs the full regression suite (`PYTHONPATH=src python -m pytest -q`) on every push and pull request.

**Primary project documents:**

- [Engineering physics and research baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md)
- [Live flight interface and keyboard controls](docs/LIVE_ACCESS.md)
- [AI pilot operating contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- [Game and pilot development mission](COLIN_MISSION.md)
- [VTX Phantom overview](docs/phantom/README.md) and [Phantom in the simulator](docs/phantom/PHANTOM_SIM_INTEGRATION.md)
- [A10 first take-offs and flights](docs/phantom/A10_FIRST_FLIGHTS_20261104.md), [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md) and [A10 airflow and CG, stage 1](docs/phantom/A10_AIRFLOW_CG_STAGE1.md)
- [Voice pilot](docs/VOICE_PILOT.md), [pilot exchange audit](docs/PILOT_EXCHANGE_AUDIT.md) and [OpenAI pilot recorder](docs/OPENAI_PILOT_RECORDER.md)
- [Development roadmap and checklist](docs/VADERS_TAXIS_ROADMAP_TODO.md)
- [Experiment findings](evidence/EXPERIMENT_REPORT.md)
- [Flight evidence and recorded tests](evidence/)

The original aircraft concept and source provenance are documented in the engineering baseline; externally sourced models and reference materials do not automatically become VTX-owned assets. VTX is separate from *The Node* project.

## Ownership, licensing and commercial enquiries

**Copyright © 2026 Steven Dark (SDarkVader). All rights reserved.**

VTX is **proprietary software and game content, not open source**. No permission is granted to use, run, reproduce, copy, modify, adapt, redistribute, publish, host, sublicense, sell, commercially exploit or train models on original VTX content without prior express written authorisation from the relevant rights holder, subject to non-excludable legal rights.

Access to this private repository is not itself a licence. For commercial licensing, collaboration, testing or other permissions, contact the owner via [GitHub](https://github.com/SDarkVader).

Third-party dependencies and externally sourced materials remain subject to **their own licences and rights**. See the full [proprietary licence notice](LICENSE). The game is not suitable for operating real aircraft or for safety-critical engineering use.
