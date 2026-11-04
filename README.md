# VTX — Vader's Taxis

**An experimental flying-car game where the physics is the boss.** Build it, fly it, break it, fix it, then hand the controls to an AI test pilot and watch what happens.

VTX is a physics-driven 3D flight game in active development. You, or an AI pilot, fly experimental VTOL machines through a live simulation: no scripted paths, no animation tricks. Every lift, stall and crash comes from mass, forces and actuator limits, and every flight is recorded so you can see exactly what went right (or spectacularly wrong).

**Status:** playable experimental prototype / flight-test game, not a finished release. The repository is private. **All original VTX game content and code are proprietary; no use or commercial exploitation is permitted without prior express written permission.** See [LICENSE](LICENSE).

## The idea

Experimental vehicles, built under uncertainty, flown by an AI with a human steering it by intuition. Through calibration they learn to fly the thing, swap out components, climb, descend at speed, corner, and find the edge of what the machine can do. The AI pilot keeps persistent notes and feedback between flights, and can change the code to simulate a repair and make the next flight better.

That loop (fly, feel it, fix it, fly again) is what VTX is built around. Very few games let you do iterative engineering with an AI test pilot who can't cheat.

## The machines

Pick one under **Lower frame** on the mission panel.

### VTX Phantom A10

A two-seat, angular, black-and-gold flying car in Vader's Taxis colours. It drives on the road, lifts off vertically on four tilting wheel fans, and flies on wings that slide out of the body. It also has two rear boosters, telescopic legs, flaps, ailerons, nose canards and a DRS airbrake flap between its twin fins.

The current prototype is the **Phantom FX-A A10** (bigger fan-wheels, a 900 kW take-off turbogenerator, a nose battery). The as-drawn A10 and the earlier A9s are in the garage too.

**Where it's at: first lift-offs.** In the sim the Phantom has left the ground on its wings, wheels off at 60 to 106 m/s depending on the build, with a best climb of about 32 m. Then it fumbles the pitch. Getting it to fly level is the boss fight right now. A rolling start with the boosters lit does 0 to 100 km/h in 5.3 s. As drawn, the lift fans can't hover it yet (thrust-to-weight 0.52), which is what the FX-A redesign is going after.

You can swap in new parts: a tailplane that works as a stabilator, turbine boosters built from real engine figures (four PBS TJ150s or one Williams FJ33-5A), and a wing mounted at an angle. They're switches in `inputs/phantom_parameters_v1.json` under `proposals.*`, all off by default.

**The 3D model.** Smooth bodywork, livery, a window onto the wing mechanism, a carbon and titanium DRS flap, vectoring booster cowls, VTX alloy wheels:

- [`public/assets/phantom-a10-visual.glb`](public/assets/phantom-a10-visual.glb): the model the game loads.
- [`assets/derived/phantom-a10-cassette-visual.glb`](assets/derived/phantom-a10-cassette-visual.glb): an animated preview with 28 animations (wings, hatches, canards, flaps, locks).

GitHub won't preview `.glb`, so download either one into any glTF viewer. Add `?cad=1` to the game address to load the raw CAD export instead. How it's built: [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md).

### Four-fan VTOL (R6)

The original: four independently articulated ducted fans. Hover, manoeuvre around terrain and structures, and bring it down in one piece.

## Fly it

- **Manual:** the browser interface, keyboard and live cockpit instruments.
- **AI pilot:** an AI gets live observations and sends the same fly-by-wire commands you do. It has to respond to the simulation, not follow a precomputed route.
- **Voice:** the Phantom panel has a push-to-talk **🎙 Voice** button (Chrome or Edge). Say "boost fifty percent", "take-off configuration", "downforce", "nose up eight" or "status" and it does it, then talks back. Risky moves like stowing the wings need a spoken "confirm". It's a fixed command set; talking to an AI pilot like a crew chief currently runs through an external phone integration. See [voice pilot](docs/VOICE_PILOT.md).
- **Missions and exploration:** choose a departure and destination, fly the test environment, dodge obstacles, try to take off, navigate and land.
- **Real consequences:** mass, gravity, inertia, actuator limits and contact all matter, and crashes are recorded, not hidden.
- **Flight evidence:** telemetry, mission traces, controller actions and post-flight reports. An external AI pilot's model calls can be logged too, with [`pilot_exchange`](docs/PILOT_EXCHANGE_AUDIT.md) and the opt-in [OpenAI pilot recorder](docs/OPENAI_PILOT_RECORDER.md).

## Getting started: Windows development build

This is a private developer/tester build, not a public download.

1. Obtain **written authorisation** from the rights holder and access to the private repository.
2. Install a supported Python version with the Windows `py` launcher.
3. Clone the repository and run `launch-windows.bat` from its root.
4. Allow the first launch to install the packages listed in `requirements.txt`.
5. Open `http://127.0.0.1:8765/` if it does not open automatically; keep the launcher running.

See [live access and manual controls](docs/LIVE_ACCESS.md) for keyboard mappings and flight modes. Any hosted Vercel Sandbox URL you've been sent is temporary and not a permanent game service.

## Under the hood

A Python server runs a 6-DOF rigid-body physics model (MuJoCo) and a browser front end draws what the physics says. Forces, torques, mass properties and actuators drive the motion you see. The vehicle numbers are design values we keep tuning as we learn, so expect them to move.

Engineering tools for the Phantom: `tools/phantom/phantom_campaign.py` runs the performance campaign (acceleration, take-off, boosters), and `tools/phantom/a10_cg_placement.py` checks how adding or moving hardware shifts the centre of gravity. CI runs the full test suite (`PYTHONPATH=src python -m pytest -q`) on every push and pull request.

**Documents:**

- [VTX Phantom overview](docs/phantom/README.md) and [Phantom in the simulator](docs/phantom/PHANTOM_SIM_INTEGRATION.md)
- [A10 first take-offs and flights](docs/phantom/A10_FIRST_FLIGHTS_20261104.md), [A10 visual pass](docs/phantom/A10_VISUAL_PASS.md) and [A10 airflow and CG, stage 1](docs/phantom/A10_AIRFLOW_CG_STAGE1.md)
- [Engineering physics and research baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md)
- [Live flight interface and keyboard controls](docs/LIVE_ACCESS.md)
- [AI pilot operating contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- [Game and pilot development mission](COLIN_MISSION.md)
- [Development roadmap and checklist](docs/VADERS_TAXIS_ROADMAP_TODO.md)
- [Experiment findings](evidence/EXPERIMENT_REPORT.md) and [flight evidence](evidence/)

The original aircraft concept and source provenance are documented in the engineering baseline; externally sourced models and reference materials do not automatically become VTX-owned assets. VTX is separate from *The Node* project.

## Ownership, licensing and commercial enquiries

**Copyright © 2026 Steven Dark (SDarkVader). All rights reserved.**

VTX is **proprietary software and game content, not open source**. No permission is granted to use, run, reproduce, copy, modify, adapt, redistribute, publish, host, sublicense, sell, commercially exploit or train models on original VTX content without prior express written authorisation from the relevant rights holder, subject to non-excludable legal rights.

Access to this private repository is not itself a licence. For commercial licensing, collaboration, testing or other permissions, contact the owner via [GitHub](https://github.com/SDarkVader).

Third-party dependencies and externally sourced materials remain subject to **their own licences and rights**. See the full [proprietary licence notice](LICENSE). The game is not suitable for operating real aircraft or for safety-critical engineering use.
