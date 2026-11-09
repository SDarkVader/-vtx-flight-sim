# VTX — Vader's Taxis

**Build it. Fly it. Break it. Figure out why.**

VTX is a proprietary, physics-driven 3D VTOL flight game set in the world of Vader's Taxis. Pick an aircraft, set up a test, take control yourself or work with an AI pilot, then use the flight data to decide what to try next.

Every movement comes from the live physics simulation, not from a scripted path or a canned animation. Mass, inertia, thrust, actuator limits, tyre grip and ground contact decide what happens. A good flight is earned, and a crash is a real result. Crashes are part of the programme.

**Status:** playable experimental prototype / flight-test game, **not a finished commercial release**. This GitHub repository is private. **All original VTX game content and code are proprietary; no use or commercial exploitation is permitted without prior express written permission.** See [LICENSE](LICENSE).

## Choose your ride

Pick a vehicle with **Choose vehicle**, or under **Lower frame** on the mission panel.

**Phantom A10-B**: the current Phantom, and the vehicle the cockpit opens on. It is a two-seat transforming vehicle that you can:
- drive on the road, steered through its front wheels;
- deploy its wings from the cassette behind the cabin, even from a standstill;
- lift off on the four fans inside its wheel pods;
- fly, brake and turn with the fans facing down.

The canards, flaps, ailerons, fin rudders, DRS stabilator and the thrust vectoring of the two rear boosters all move under fly-by-wire. It can't yet fly on its wings alone with the fans off, or rotate off the runway on a rolling take-off. Those are the next engineering problems.

**Phantom A10-A**: the previous prototype. It is kept in the exact configuration of the 4 to 7 November flight register (72 runs, peak 600.58 m), so you can fly it again and compare.

**R6 Argon**: the four-pod aircraft that started the flight-test programme, with four independently articulated ducted fans. Use it to explore hovering, directional control and flights between selected points.

**Also in the hangar:**
- the Phantom A10 as drawn (its lift fans can't hover it; try it and see);
- the earlier A9 Phantoms;
- the R6 variator, R5 and R4 study frames.

Every Phantom figure is a labelled synthetic or derived value. A successful flight in one configuration does not establish how another behaves.

## How to play

1. Start the simulator (see [below](#start-the-windows-development-build)) and open the cockpit in your browser.
2. Choose a vehicle. Set the departure (**A**) and destination (**B**) on the map of the 1 × 1 km valley test range. Any point with ground support works; landing areas are not limited to marked pads.
3. Start a mission and take manual authority. Fly with the keyboard and the control panel; the Phantom also takes push-to-talk **🎙 Voice** commands.
4. Drive, hover, fly, land or crash. You can switch between the external view, **Free roam camera** and **Cockpit · C** at any time.
5. Open **Flight records** and **Engineering** to see what actually happened: telemetry, controller actions, events and post-flight reports. Use it to set up the next attempt.

The [flight index](docs/FLIGHT_INDEX.md) lists each retained sortie by run ID and model, with a short summary and a pointer to its PC data. The [single cockpit guide](docs/UNIFIED_RUNTIME.md) explains the vehicle selector and local archive. Keyboard mappings and flight modes are in [live access and manual controls](docs/LIVE_ACCESS.md).

## Fly with an AI pilot

VTX is designed for **real interaction between human operators, AI pilots and the simulated aircraft**. A connected pilot gets live sensor observations and sends real fly-by-wire commands. It has to respond to the simulation as it develops; it never follows a precomputed route. You can hand authority back and forth and review what happened together.

**Voice commands (Phantom).** The Phantom operator panel has a push-to-talk **🎙 Voice** button (Chrome or Edge). Speech is matched against a fixed command grammar: no language model sits in the control loop. Each command passes the same fly-by-wire heartbeat, lease and authority checks as the sliders, is read back aloud and is logged. Risky commands (stow wings, retract legs, engine off) need a spoken "confirm". See [voice pilot](docs/VOICE_PILOT.md).

**Every AI decision can be audited.** An external AI pilot's model calls can be recorded for later inspection:
- [`pilot_exchange`](docs/PILOT_EXCHANGE_AUDIT.md): one redacted record per decision, written by the caller.
- the opt-in [OpenAI pilot recorder](docs/OPENAI_PILOT_RECORDER.md): streams observations, accepted actions and model replies to `pilot-api.jsonl`. The model's reply is informational and never commands the aircraft.

The pilot's requirements are set out in the [live fly-by-wire pilot contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). Scripted paths, replay passed off as live flight, and unearned landings do not count as genuine control.

Conversational operation from a phone has been tried through an **external remote-command integration**, including live actuator demonstrations, flight observations and engineering changes. That workflow is experimental; it is **not a claim that a standalone in-game conversational voice-chat feature has shipped**.

## Start the Windows development build

Aircraft variants and configurations are selectable in the cockpit. Each version is a work in progress: a successful flight in one configuration does not establish the behaviour of another.

## From hangar to flight test

Any previously shared hosted Vercel Sandbox URL is temporary and **not** a permanent game service.

## Coming next: one connected world

We're building one connected Vader's Taxis world: the airport, the physical aircraft, cockpit controls, AI pilot interfaces and the engineering and flight-test workspace, all together. The test candidate is on the [integration development branch](https://github.com/SDarkVader/-vtx-flight-sim/tree/integration/vtx-unified-20261107):

- **A shared airport and cockpit:** an extended airfield with terrain, buildings, runways, cameras, aircraft selection and physics-driven flight. Scripted airport traffic and cockpit rides are kept separate from the physical aircraft.
- **Phantom starting configurations:** start wheels-down at the runway threshold, or with the pods at 90° and the legs extended. Pod rotation and leg extension have separate controls for testing transitions.
- **Thrust and wheel visuals:** wheel motion follows the simulated wheel joints. The wheel-pod and rear-booster effects respond to simulated thrust, with bright cores and short trails. The colours are visual cues, not temperature measurements.
- **Flight-test evidence:** the candidate records pilot summaries and engineering findings for simulated crashes and confirmed pilot-provider failures, then starts a fresh test run. Causes stay unassessed until the evidence supports a finding. The newer [dashboard candidate](https://github.com/SDarkVader/-vtx-flight-sim/tree/work/dashboard-cockpit-20261107) also serves the flight-test dashboard and its seven evidence gates alongside the cockpit.

These changes are **not yet promoted to `main`**, and the Phantom A10-B on `main` has not been merged into the candidate yet. Flight controls, model and physics compatibility, aircraft mechanisms, AI handover, persistence and mobile access still need full end-to-end acceptance testing. The [integration plan](https://github.com/SDarkVader/-vtx-flight-sim/blob/integration/vtx-unified-20261107/INTEGRATION_PLAN_20261107.md) records the sources, checks and remaining work.

## Phantom model status (for agents and integrators)

**Current, default Phantom: FX-A A10-B** (`phantom-a10b`, config `3ecae1a9`). This is the model the simulator and the game use. Full specification: [docs/phantom/PHANTOM_A10B_MODEL.md](docs/phantom/PHANTOM_A10B_MODEL.md).

A10-B is A10-A plus:
- hull lift (Munk), road suspension and wheel-drive limits;
- 7° wing incidence;
- front steer-by-wire, fin rudders and booster thrust vectoring;
- Moog Model 965 actuator calibration;
- a wing-borne control law and a wing-deployment guard.

In the plant it drives and steers, deploys its wings from a standing start (locked by 25 m/s), takes off and hovers on its wheel fans, and flies, brakes (to 0.8 g) and turns under control with the fans facing down. It cannot yet fly wing-borne with the fans off, or rotate on a rolling take-off.

**Previous: FX-A A10-A** (`phantom-fx` with the P6 stabilator, config `70089cca`; `b835295b` without P6). This is the configuration of the A10-A flight register, 4 to 7 November 2026:
* **72 run IDs:** 66 on `70089cca`, 4 on `b835295b`, and 2 on the 4 November Vercel sandbox.
* **Recorded outcomes:**

  | Outcome | Runs |
  |---|---|
  | Airborne attempt ended | 20 |
  | Collision | 12 |
  | Landed | 3 |
  | No take-off | 33 |
  | Interrupted | 1 |
  | Unclosed | 2 |
  | No formal outcome | 1 |
* **Peaks:**

  | Peak | Run |
  |---|---|
  | 600.58 m | `20261106T101512-085037` |
  | 299.94 m | `20261106T080610-01457b` |
  | 74.96 m | `20261104T023710-072007` |
  | 73.28 m | `20261105T212155-03a363` |

Those runs used the base plant: no hull lift, rigid wheels, an unlimited hub drive and the hover-tuned control law. Their numbers are not directly comparable with A10-B.

The register, the 9 November test telemetry and the images are on the reference branch [`reference/phantom-a10b-20261109`](https://github.com/SDarkVader/-vtx-flight-sim/tree/reference/phantom-a10b-20261109/reference/phantom_a10b_20261109).

**What the Phantom is.** An angular two-seat vehicle designed to:
- drive on the road;
- lift off vertically on four ducted fans inside tilting wheel pods;
- fly on retractable wings.

It has:
- two rear boosters and telescopic landing legs;
- wings that slide out of a split-level cassette behind the cabin (the A10 puts both wings at one height), with flaps and ailerons;
- two nose canards and raked twin fins.

Power is turbogenerator-electric with a battery buffer.

The FX-A design proposal has Ø0.90 m fans in Ø1.10 m fan-wheels, a 900 kW take-off turbogenerator and a nose battery. The as-drawn reference has Ø0.49 m fans and two 600 kW turbogenerators, and its lift fans cannot hover it (thrust-to-weight 0.52 in the plant). The FX-A test record is in the [flight-test report](docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md), and the first rolling take-offs are in [first take-offs and flights](docs/phantom/A10_FIRST_FLIGHTS_20261104.md).

**3D models.** GitHub does not render `.glb` files, so download them into any glTF viewer:
- [`public/assets/phantom-a10b-visual.glb`](public/assets/phantom-a10b-visual.glb): A10-B, driven joint by joint from the simulation. It includes the 7° wing incidence; the front wheels steer from the plant.
- [`public/assets/phantom-a10-visual.glb`](public/assets/phantom-a10-visual.glb): the refined A10 model, with smooth bodywork, livery, a visible wing-cassette window, a carbon and titanium DRS flap, vectoring booster cowls and alloy VTX wheels.
- [`assets/derived/phantom-a10-cassette-visual.glb`](assets/derived/phantom-a10-cassette-visual.glb): an animated preview with 28 animations (wings, hatches, canards, flaps, locks).

Add `?cad=1` to the game address to load the raw CAD export instead. How the refinement is built: [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md).

## Under the hood

The game runs on a 6-DOF Newton–Euler / MuJoCo physics model, with a Python server and a browser-based interface. The browser is the cockpit and the window into the world. Modelled forces, torques, mass properties and actuators drive the rendered motion.

You need Python and the Windows `py` launcher. From the repository root:

Phantom design changes are carried as labelled **proposals and overlays that are off by default**:
- proposals are `proposals.*` in `inputs/phantom_parameters_v1.json`, and overlays are in `inputs/phantom_overlays/`;
- each carries a unit, a source and a provenance label;
- A10-B is the variant that switches its set on.

Other tools and checks:
- `tools/phantom/phantom_campaign.py` runs the performance campaign;
- `tools/phantom/a10_cg_placement.py` screens hardware placement for mass, centre of gravity and inertia;
- CI runs the full regression suite (`PYTHONPATH=src python -m pytest -q`) on every push and pull request.

The launcher refuses to replace an existing process on its chosen port. To run an isolated candidate alongside another flight, choose a free port and a separate data directory after installing the dependencies:

- [Engineering physics and research baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md)
- [Live flight interface and keyboard controls](docs/LIVE_ACCESS.md)
- [AI pilot operating contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- [Game and pilot development mission](COLIN_MISSION.md)
- [VTX Phantom overview](docs/phantom/README.md), [Phantom in the simulator](docs/phantom/PHANTOM_SIM_INTEGRATION.md) and [Phantom A10-B model](docs/phantom/PHANTOM_A10B_MODEL.md)
- [A10 first take-offs and flights](docs/phantom/A10_FIRST_FLIGHTS_20261104.md), [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md) and [A10 airflow and CG, stage 1](docs/phantom/A10_AIRFLOW_CG_STAGE1.md)
- [Voice pilot](docs/VOICE_PILOT.md), [pilot exchange audit](docs/PILOT_EXCHANGE_AUDIT.md) and [OpenAI pilot recorder](docs/OPENAI_PILOT_RECORDER.md)
- [Development roadmap and checklist](docs/VADERS_TAXIS_ROADMAP_TODO.md)
- [Experiment findings](evidence/EXPERIMENT_REPORT.md)
- [Flight evidence and recorded tests](evidence/)

Then open [http://127.0.0.1:18901/](http://127.0.0.1:18901/). Localhost addresses refer to the device opening them. Authenticated remote and mobile access to the authoritative runtime remains development work; the current launcher listens on network interfaces, so use it only on a trusted network.

See [live access and manual controls](docs/LIVE_ACCESS.md) for control details. A hosted preview becoming available does not by itself mean it is connected to a persistent physics runtime.

## AI pilots

VTX includes pilot interfaces for sending observations and commands to the live simulation. The intended experience is to fly alongside a conversational AI pilot, hand over authority and review what happened together.

Pilot handover, reconnect and fallback behaviour, conversational voice, persistent sessions and reliable remote operation still need end-to-end development and testing. Existing voice-command experiments should not be taken as a finished conversational pilot.

## Currently in development

- **One connected world:** bring the airport, models, physical flight, cockpit and engineering workspace together without losing existing features.
- **Aircraft and engineering:** reconcile R6 and Phantom configurations, geometry, moving mechanisms, mass and centre of gravity, propulsion, aerodynamics and control response against available evidence.
- **Testing and records:** run experiments against the selected physics configuration, compare runs and preserve telemetry, pilot summaries and engineering findings. Candidate failure-reset handling is being tested.
- **Flight experience:** improve controls, cameras, visual effects, takeoff and landing behaviour, and transitions between road and vertical configurations.
- **AI and access:** develop pilot continuity, authority handover, conversation, authentication and reliable PC/mobile access.

See the [integration plan and source-of-truth comparison](INTEGRATION_PLAN_20261107.md), [physics and research baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md), [pilot contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md) and [flight evidence](evidence/) for the engineering detail and current limits.

## Ownership and licensing

Copyright © 2026 Steven Dark (SDarkVader). **All rights reserved.** VTX is proprietary software and game content, not open source. Access to this repository does not grant permission to use, run, reproduce, modify, redistribute, host, sell or otherwise exploit original VTX content without prior express written authorisation from the relevant rights holder, subject to non-excludable legal rights. See [LICENSE](LICENSE).

Third-party dependencies and externally sourced materials remain subject to their own licences and rights. For permission, collaboration or commercial enquiries, contact [SDarkVader on GitHub](https://github.com/SDarkVader).
