# VTX — Vader's Taxis

**Build it. Fly it. Break it. Figure out why.**

VTX is an experimental flight simulation and development game set in the world of Vader's Taxis. Pick an aircraft, set up a test, take control yourself or work with an AI pilot, then use the flight data to decide what to try next.

The airport is your playground and your test range. You might be working through a careful hover, taking the Phantom down the runway, exploring the terrain, or discovering exactly which part of your latest engineering idea needs another look. Crashes are part of the programme.

> **In active development:** this is a playable experimental prototype, not a finished game. Aircraft, controls, visuals and flight behaviour are still being built, compared and tuned.

## Choose your ride

**R6 Argon** — the four-pod aircraft that started the flight-test programme. Explore hovering, directional control and flights between selected points.

**Phantom A10** — a transforming flight-test vehicle with rotating wheel pods, wings, control surfaces and rear boosters. Try a wheels-down runway start or a vertical configuration, then experiment with the mechanisms and flight controls.

Aircraft variants and configurations are selectable in the cockpit. Each version is a work in progress: a successful flight in one configuration does not establish the behaviour of another.

## From hangar to flight test

1. Start the simulator and open the cockpit in your browser.
2. Choose an aircraft and a departure and destination. For the Phantom, select a road or vertical starting configuration; the runway-start button places the departure near the long runway threshold.
3. Take manual control, inspect the instruments and experiment with the aircraft's controls. The Phantom has separate controls for its pods, legs, wings, canards and other systems.
4. Fly, drive, hover, land or crash. The physical aircraft responds to the running simulation, including its modelled forces, mass, inertia, actuators and ground contacts.
5. Inspect the telemetry and flight records. Use what happened to set up the next attempt.

The airport includes terrain, runways, buildings, vehicles, cameras and aircraft presentation. Visual airport traffic has its own scripted behaviour; your physical aircraft is driven by the simulator.

## How it works

The browser is the cockpit and window into the world. A persistent **Python and MuJoCo** runtime maintains the aircraft state, advances the physics and supplies telemetry to the interface. The 3D model follows that state, and flight controls send commands to the same runtime.

The Phantom's wheel animation follows simulated wheel motion. Its wheel-pod and rear-booster glows and trails respond to simulated thrust; the colours are visual effects, not temperature measurements. The aircraft's simulated mass distribution and forces determine its motion—there is no fixed, scripted vehicle rotation point.

Some engineering values are still estimated or provisional. Flight records and test results describe what happened in the simulation; they are evidence for further development, not proof of real-world performance.

## Start the Windows development build

You need Python and the Windows `py` launcher. From the repository root:

1. Run `launch-windows.bat`.
2. On the first run, allow it to create a virtual environment and install the dependencies in `requirements.txt`.
3. Keep the launcher open and use [http://127.0.0.1:8765/](http://127.0.0.1:8765/) on the same PC.

The launcher refuses to replace an existing process on its chosen port. To run an isolated candidate alongside another flight, choose a free port and a separate data directory after installing the dependencies:

```powershell
.venv\Scripts\python.exe scripts\launch_unified.py --port 18901 --data-root .\my-test-data
```

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
