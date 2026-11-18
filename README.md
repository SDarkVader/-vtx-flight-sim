# VTX — Vader's Taxis

**A flight and watercraft game in development.** Fly experimental aircraft from Main Airport or take a Ricochet through the marked channels between the harbour islands.

[Play VTX in your browser](https://vtx-flight-sim.vercel.app/)

![Front three-quarter view of the Phantom A10-C with its wings extended and wheel-fan pods in road position](docs/readme-images/phantom-a10c-exterior.jpg)

*Studio view of the Phantom A10-C. The A10-D shares its exterior and has its own pinned configuration for testing the air-brake ECU.*

The current build brings together an 8 km square Main Airport, a 7,800 m runway with level approaches, and an airport-side harbour with islands, marked routes, docks and multiple Ricochet craft. The airport also has Argon and Phantom scenery traffic and passenger-view flights. Players can track their physical aircraft on the navigation map.

Open **Choose vehicle** for the Phantom A10-C, Argon R6, or a Ricochet at Airport Landing or Lantern Marina. **Earlier and experimental aircraft** includes the Phantom A10-D ECU test aircraft, the recovered runway and VTOL variants, and the pinned A10-B reference. At Main Airport the Phantom starts at the west runway threshold unless you choose a different departure.

| Argon R6 | Ricochet Concept A |
| --- | --- |
| ![Argon R6 exterior showing its four ducted rotors around the central cabin](docs/readme-images/r6-argon-exterior.jpg) | ![Ricochet exterior showing the canopy, twin sponsons and rear ducted fans](docs/readme-images/ricochet-exterior.jpg) |

## Current development

Controls follow the seat you choose. Selecting a Ricochet opens its helm camera. Use **View selected boat**, **Cockpit** and mouse look to change views, or **Aircraft controls** to return to the aircraft. Scenic flights have their own passenger seats. The simulator checks the selected aircraft's visual model against its recorded SHA-256 fingerprint. [Selection and camera verification](docs/VEHICLE_CONTROLS_20261117.md).

The Phantom has a cabin-mounted glass flight deck with live airspeed, heading, attitude, vertical speed, radar height, fuel and power readings. Cockpit visibility treatments clear its forward and side sightlines. The Argon keeps its fixed cabin and eye position, with a cockpit-only cutaway through nearby rotor housings; moving blades and the exterior remain intact. Missing telemetry displays a dash.

Both Ricochets use one compact, low-mounted helm display, clear reflective canopy glass and night lighting for the cabin and water ahead. The large black dashboard surround is hidden in the pilot view. These are presentation changes, with no added physical mass or changes to aircraft dynamics. The wheel-fan exhaust effect follows the opposite of the actual fan force axis, pointing down when deployed for lift. Existing VTX lettering is fitted to the Phantom skin and follows the vehicle body.

[View the Phantom flight deck, Argon cockpit and Ricochet helm in the cockpit gallery](docs/COCKPIT_GALLERY.md).

Both maps have a scale bar calculated from their current projection. Zoom with **+ / −**, the mouse wheel or a touch pinch, from a whole-world view down to a 100 m horizontal span. **Airport views → Scenic flights → Traffic** chooses **0–10** scheduled scenery aircraft, including Argons and Phantoms. These routes and passenger seats are separate from the telemetry-driven AI pilot; this update adds no scripted pilot flights.

The Windows vehicle test launcher uses a separate save folder. [Vehicle test launcher](Test-VTX-Vehicles.bat) · [Main vehicle test checklist](docs/MAIN_VEHICLE_TESTING.md).

| Candidate | Original evidence | Current verification |
| --- | --- | --- |
| `phantom-a10c-runway-20261112` | `20261112T132734-215fcf` airport; `20261112T135625-df0959` sandbox | Recorded-control takeoff reproduced through the 400 Hz solver; first 42 s / 4,200 samples match 16 channels |
| `phantom-a10c-vtol-20261112` | `20261112T204732-17cc37`, `20261112T211016-e9d0ab` airport | Recorded-control VTOL takeoff reproduced; first 45 s / 4,500 samples match 16 channels |
| `r6-argon-20261103` | `20261103T125202-92636c`, historical valley | Recorded model/terrain recovered; original full command log remains unavailable; cockpit/flight acceptance pending |

The revision registry records the configuration, environment and parent model for each recovered flight. Cockpit acceptance remains pending for the historical R6. [Revision registry](inputs/flight_revisions.json).

The authored wheels and pod mounts are retained. Collision dimensions and visual offsets are diagnostic data in Engineering. **Suspension schematic** is an optional physical reference, off by default, not structural actuator CAD. See [the schematic contract](docs/phantom/A10C_SUSPENSION_SCHEMATIC.md).

Use **Save flight & switch** before changing aircraft. Flight records restores supported checkpoints paused; then choose **Take control** and **Resume existing mission**. Phantom inner checkpoint format 3 retains the radar ground-reference calibration. Missing or incompatible dependencies and older insufficient checkpoints remain preserved with an explicit recovery failure, rather than being silently reset. Camera preferences are stored separately in that browser profile.

Saved flights are retained locally; persistence across cloud deployments is not implemented. On Windows, `Start-VTX.bat` launches the local game using the installed Python environment and preserves incompatible prior launch state in a recovery folder. If the port is occupied, the launcher checks the airport, harbour, runtime and frontend files before identifying the existing server. Local frontend responses require cache revalidation to reduce stale versions across browser profiles.

A ground test switched from the runway candidate to the VTOL candidate and restored the runway flight paused at 55.0175 s. Its checkpoint bytes and radar calibration matched the original. Full cockpit testing and Argon flight acceptance remain open.

Aircraft flight uses a **400 Hz MuJoCo physics model** with aerodynamics, actuators, contact and vehicle mass. The harbour runs its craft alongside the aircraft simulation. AI pilot development uses vehicle telemetry and individual commands, while scheduled scenic flights provide background traffic.

> [!IMPORTANT]
> **Project Status & Proprietary Notice:** VTX is an experimental prototype and flight-test sandbox, **not a finished commercial release**. All original VTX game content, vehicle designs, CAD models, lore, and software code are proprietary. No commercial exploitation or unauthorized distribution is permitted without prior written consent. See [LICENSE](LICENSE).

---

## What You Can Do in VTX

Explore the current development features below. Their models and presentation will continue to change.

### 1. Drive, Transform, and Fly
VTX lets you transition seamlessly across multiple operational modes in a single airframe:
* **Road Drive:** Steer along taxiways and service roads with functional front-wheel steer-by-wire, realistic suspension travel, and tire contact friction.
* **Wing Deployment:** Unfurl high-aspect wings from an internal split-level cassette behind the cabin. Mechanical interlocks lock deployment at speeds exceeding 25 m/s to protect against aeroelastic structural failure.
* **Vertical Takeoff (VTOL):** Tilt four ducted fan pods to 90°, spool up electric drive motors, and lift off vertically from pads, runways, or unprepared clearing sites.
* **High-Speed Cruise & Braking:** Fire twin rear booster propulsors, adjust the Drag Reduction System (DRS) flap, deploy raked fin rudders, and execute emergency 0.8g air-braking with downward-vectored fan pods.

```
          [ ROAD DRIVE ]               [ WING DEPLOYMENT ]              [ VTOL & CRUISE ]
      Front steer-by-wire,         High-aspect wings slide from     90° tilting ducted fans,
       suspension travel,          fuselage cassette; locked at     twin boosters & canards;
        tarmac tire grip               airspeeds > 25 m/s            0.8g vectored air brake
```

The airport also has scheduled Phantom and Argon scenery flights. Choose a passenger seat to ride along.

---

### 2. Choose Your Proving Ground (Selectable Live Worlds)
Choose a world from the cockpit before starting a flight:

* **Main Airport (8,000 × 8,000 m):** A 7,800 m runway, broad level approaches, taxiways and aprons, surrounded by retained terrain. The harbour beside the airport adds islands, marked water routes and docks.
* **Test Sandbox — Stage 1 Valley (2,000 × 2,000 m):** Current valley test environment. The separate **Historical R6 valley (1,000 × 1,000 m)** preserves the 3 November terrain. They have different collision/heightfield identities; matching labels alone do not establish the same environment.

> [!NOTE]
> Environment switching in VTX is a **true physical terrain swap**, not a cosmetic skybox. Swapping between Airport and Sandbox reloads MuJoCo collision heightfields, rebuilds ground contact geometry, updates the 2D tactical radar minimap, and computes a fresh SHA-256 model fingerprint.

![Navigation map showing the airport runway, aircraft position, harbour islands and marked boat routes](docs/readme-images/airport-harbour-map.png)

### Explore the harbour

Choose either of two Ricochet Concept A craft, steer around the islands, and dock at Airport Landing or Lantern Marina. Save and restore keeps both boats, their controls and their berth ownership. Boats and the aircraft run together in the shared airport environment.

![Ricochet craft alongside the docks at Lantern Marina](docs/readme-images/ricochet-marina.png)

---

### 3. Pilot the Hangar Fleet

| Aircraft Variant | Class / Architecture | Distinctive Flight Capabilities | Historic Milestone / Provenance |
| :--- | :--- | :--- | :--- |
| **Phantom A10-B** *(Pinned reference)* | Two-seat transforming aerocar (FX-A) | 7° wing incidence, active front-wheel steering, Munk hull lift, Moog 965 actuator models, rear boosters, DRS flap | Historical reference; Main promotion is not inferred from its pin |
| **Phantom FX-A A10-C** *(Current development; PR #41)* | Fans-off, wing-borne A10-B derivative | Four PBS TJ150-class turbojets, rate-limited takeoff-stance setting, lift fans off in the runway study | Current development aircraft; the recovered 12 November candidates and timings are listed separately above |
| **Phantom A10-D** *(Experimental)* | A10-C airframe with its own pinned configuration | Adds the `transition_ecu_v1` air-braking controller | Available under **Earlier and experimental aircraft**. [ECU test results and model identity](docs/phantom/A10C_AIRBRAKE_ECU_TEST_20261118.md#10-a10-d-test-aircraft) |
| **Phantom A10-A** | Baseline VTOL prototype | Retractable cassette wings, 4 wheel-pod fans, fixed P6 stabilator | 72-sortie November campaign benchmark (peak altitude 600.58 m) |
| **R6 Argon** | Four-pod ducted quadrotor | 4 independently articulated ducted fan pods, annular primary structure | Foundation testbed; pure hover agility and dynamic station-keeping |
| **Phantom A10 As-Drawn** | Scale CAD concept | Compact Ø0.49 m fan geometry (thrust-to-weight 0.52) | Educational study frame demonstrating hover deficit |
| **R4 / R5 Study Frames** | Aerodynamic test mules | Lightweight tubular airframes with variable mass distributions | Inertia screening and ground-resonance validation |

> **Historical model reference:** `phantom-a10b` config `3ecae1a9…` remains pinned in [aircraft identity](inputs/aircraft_identity.json). The original A10-C development variant came through [PR #41](https://github.com/SDarkVader/-vtx-flight-sim/pull/41). The two current recovered candidates have separate verified identities in [the revision registry](inputs/flight_revisions.json), while promotion remains pending. They preserve the B visual asset plus an explicitly optional schematic. [The takeoff study](docs/phantom/A10C_FANS_OFF_TAKEOFF.md) separates earlier studies from the verified 12 November recordings. Fans-off landing, endurance, crosswind and engine-out acceptance remain outstanding.

---

### 4. Fly with Colin (The Evolving AI Pilot) & Voice Control
VTX is engineered around genuine human-machine collaboration:
* **The AI Pilot Contract:** The experimental pilot reads the aircraft's available instrument telemetry and sends individual commands. The simulator records the observation and command exchange. The external pilot determines how it learns.
* **Push-to-Talk Voice Commands (🎙 Voice):** Speak naturally into your microphone (in Chrome or Edge) to issue tactical flight commands (*"gear down"*, *"deploy wings"*, *"rotate pods vertical"*, *"climb fifty meters"*). Voice audio is parsed against a deterministic aerospace grammar; critical safety maneuvers require a clear verbal *"confirm"* before execution.
* **Pilot Authority:** The cockpit shows the active control authority, and the operator can take control. Connection holds remain available during pilot experiments.

---

### 5. Investigate Crashes & Audit Flight Evidence
In VTX, a crash is not a "game over" screen—it is primary flight-test data.
* **Timestamped Telemetry Black Box:** The solver runs at 400 Hz; channels retain their recorded rates, including the Phantom's 100 Hz step log. Runs retain control demands, actuator state, energy and contact evidence.
* **2D Tactical Minimap:** Track your real-time ground track, velocity vector, altitude tape, and pad clearances on a custom vector radar canvas.
* **The 7-Gate Flight Test Dashboard (`/dashboard/`):** Review sortie records, pilot audit logs, and diagnostic telemetry while developing and testing the aircraft.

---

## The Unified Three-Panel Cockpit

VTX integrates three complete operational workstations into a single high-performance browser interface:

```
+=======================================================================================================+
| VTX AEROSPACE proving ground · [AIRPORT] [SANDBOX] · Phantom A10-B · SORTIE STANDBY                    |
+====================================+==================================+===============================+
| PANEL 1: LIVE COCKPIT              | PANEL 2: FLIGHT TEST DASHBOARD   | PANEL 3: PHYSICS EXPERIMENTS  |
|                                    |                                  |                               |
| • Three.js 3D Viewport            | • Embedded Suite (`/dashboard/`) | • Independent MuJoCo Kernel   |
| • Tactical Minimap Radar (Canvas)  | • 7 Flight Test Gates            | • Custom Mass/Inertia Sliders |
| • Floating HUD Drawers:            | • Historical Sortie Archives     | • Aerodynamic Polar Overrides |
|   - Mission: Origin & Destination  | • Black-Box JSONL Telemetry      | • Automated Batch Monte Carlo |
|   - Controls: Fly-by-wire & Voice  | • Failure Cause Classification   | • Downloadable Evidence Packs |
|   - Views: Cockpit / Orbit / Tower | • Checkpoint Restoration Engine  | • SHA-256 Provenance Fingerprint|
+====================================+==================================+===============================+
```

1. **Live Cockpit (`/`):** The primary flight station. Direct WebGL window into the simulation with interactive camera views (Cockpit 1st-person, Chase, Orbit, Tower, Runway Threshold) and floating tactical HUD drawers.
2. **Flight Test Dashboard (`/dashboard/`):** Inspect available sortie records, flight-test gates, telemetry and pilot exchange logs.
3. **Physics Experiments (`/experiments/`):** The engineering skunkworks. Run isolated simulation runs with experimental mass allocations, altered center-of-gravity offsets, custom aerofoil polars, and synthetic engine limits without corrupting active flight data.

---

## Architectural Blueprint

The VTX architecture pairs a lightweight, zero-compilation WebGL cockpit with an authoritative, high-rate physical simulation kernel.

```mermaid
flowchart TD
    subgraph Client["CLIENT COCKPIT (Browser / WebGL)"]
        UI_Nav["Top Navigation Bar<br/>[Airport / Sandbox Switcher]"]
        ThreeView["Three.js 3D World<br/>(Airframe Visuals & FX)"]
        MiniMap["2D Tactical Minimap<br/>(Dual-Projection Canvas)"]
        HUD["Floating HUD Drawers<br/>(Mission, Controls, Views)"]
        VoiceEngine["Voice Pilot Interface<br/>(Speech Grammar Parser)"]
    end

    subgraph API["COMMUNICATION & ROUTING BUS"]
        FastAPI["FastAPI / Uvicorn server"]
        EnvRouter["/api/environment<br/>[Sortie Lock Guard]"]
        WS_Stream["Timestamped WebSocket Telemetry"]
        REST_Ctrl["REST Endpoints<br/>(/api/model-preview, /api/runs)"]
    end

    subgraph Physics["AUTHORITATIVE PHYSICS ENGINE"]
        MuJoCo["MuJoCo 400 Hz Multibody Kernel<br/>(Newton-Euler Rigid Dynamics)"]
        Aero["Aerodynamics Polar Model<br/>(Local Flow, Dynamic Pressure, Stall)"]
        ContactSolver["Terrain & Contact Friction Solver<br/>(Tire Grip, Suspension, Impacts)"]
        SortieLock["Active Sortie Manager<br/>(HTTP 409 Invariant Lock)"]
    end

    subgraph Environments["DUAL PHYSICAL ENVIRONMENTS"]
        AirportWorld["Main Airport World<br/>(8,000m x 8,000m Airfield)"]
        SandboxWorld["Current Sandbox 2,000m square<br/>Historical R6 valley 1,000m square"]
    end

    subgraph Pilots["PILOT & OPERATOR STATIONS"]
        HumanPilot["Human Operator<br/>(Fly-by-Wire Sliders / Keyboard)"]
        ColinPilot["Colin AI Pilot<br/>(Telemetry & Commands)"]
        AuditRecorder["Pilot Exchange Audit<br/>(Model Decision Ledger)"]
    end

    subgraph Storage["DURABLE EVIDENCE REPOSITORY"]
        EvidenceLedger["Flight records and checkpoints<br/>(VTX_DATA_ROOT)"]
        BlackBox["Flight Black-Box (.jsonl)<br/>(400 Hz High-Rate Logs)"]
        Fingerprints["Model & Config Hashes<br/>(SHA-256 Provenance)"]
    end

    %% Wiring
    UI_Nav -->|POST /api/environment| EnvRouter
    EnvRouter --> SortieLock
    SortieLock -->|Build World| AirportWorld
    SortieLock -->|Build World| SandboxWorld
    AirportWorld --> MuJoCo
    SandboxWorld --> MuJoCo

    HumanPilot -->|Heartbeat Lease & Controls| REST_Ctrl
    VoiceEngine -->|Validated Actions| REST_Ctrl
    ColinPilot -->|FBW Commands| REST_Ctrl
    REST_Ctrl --> MuJoCo

    MuJoCo --> Aero
    MuJoCo --> ContactSolver
    MuJoCo -->|High-Rate State| WS_Stream
    WS_Stream --> ThreeView
    WS_Stream --> MiniMap
    WS_Stream --> HUD

    MuJoCo --> BlackBox
    ColinPilot --> AuditRecorder
    AuditRecorder --> EvidenceLedger
    BlackBox --> EvidenceLedger
    FastAPI --> Fingerprints
```

---

## Core System Rules & Physics Invariants

To preserve scientific rigor, every component of VTX adheres to strict system-level rules:

1. **Rule 1: Single Source of Truth:**
   Visual rendering is strictly a downstream consumer of the physical state. No visual script, camera matrix, or user action may alter aircraft coordinates, suppress an impact, cancel a stall, or force a stable landing.
2. **Rule 2: Active Sortie Lock (HTTP 409):**
   The simulation world cannot be swapped while an aircraft is airborne or while a sortie checkpoint is unrecovered. Attempts to alter the environment during flight return an explicit HTTP 409 Conflict, preserving data integrity.
3. **Rule 3: Crash-Consistent Durable Evidence:**
   Every sortie is tagged with a unique ISO 8601 run ID and SHA-256 model fingerprint. Crashes, mechanical jams, and actuator saturations are preserved as definitive test results. Deleting or overwriting failed runs is strictly forbidden.
4. **Rule 4: Aircraft-specific command semantics:**
   Phantom control updates are patches: omitted fields remain held. Do not assume a shared timeout automatically resets every aircraft's controls. The cockpit reports stale telemetry and explicit authority; recovery starts paused.
5. **Rule 5: Release Guard & Aeroelastic Safeguards:**
   Actuator limits and structural locks prevent impossible aerodynamic operations. Wing deployment commands issued at airspeeds exceeding 25 m/s are rejected by the flight-control computer to prevent spar failure.
6. **Rule 6: Strict Design System Uniformity:**
   Cockpit user interfaces, floating panels, radar canvases, and tactical readouts follow the aerospace token specifications defined in [`DESIGN_SYSTEM_RULES.md`](DESIGN_SYSTEM_RULES.md).

---

## DevLog: From Hangar Sketches to Dual-World Simulation

* **Milestone 1 — Ducted Quad Foundations (October 2026):**
  Engineered the initial R4, R5, and R6 Argon testbeds. Implemented 400 Hz MuJoCo multibody kinematics, four independently articulated ducted fan pods, and baseline ground-effect contact mechanics.
* **Milestone 2 — Digital Airframe & The Colin Experiment (Nov 1–3, 2026):**
  Integrated the Blendstra P0-V4 CAD geometry into a unified physics model. Defined the [Live Fly-By-Wire Pilot Contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md) for an AI pilot using instruments and physical controls.
* **Milestone 3 — The 72-Sortie Phantom A10-A Campaign (Nov 4–7, 2026):**
  Executed a 72-flight automated test campaign with the initial Phantom prototype (`70089cca`), achieving a peak altitude record of 600.58 m. Validated cassette wing extension mechanics while uncovering low-speed hover power deficits and hub drive limits.
* **Milestone 4 — Phantom A10-B Evolution (Nov 8–9, 2026):**
  Engineered the A10-B variant (`3ecae1a9`): added 7° wing incidence, active steer-by-wire front suspension, Munk hull lift polars, Moog Model 965 actuator dynamic models, and verified high-speed 0.8g fan-vectored deceleration.
* **Milestone 5 — Airport, Harbour & Navigation (Current):**
  The cockpit, flight dashboard and experiments share a workspace. Main Airport now has an extended runway and a harbour with two Ricochet craft, marked routes and docking. The current Sandbox and the separate historical R6 valley retain their own terrain identities.

---

## Run VTX locally

For a Windows installation, use Python 3.11 and a browser with WebGL 2. Open PowerShell in the repository folder and run these commands.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\launch_unified.py
```

The launcher opens the cockpit in your browser and prints the port and save folder. Keep the terminal open while playing. To choose a different save folder, pass `--data-root` with the folder path. Add `--check` to verify the configuration before starting a session.

### Verification

The selector release passed 541 Python tests and 85 JavaScript tests. Browser tests exercised vehicle switching, repositioning and checkpoint recovery after restart. [Release checks](https://github.com/SDarkVader/-vtx-flight-sim/actions/runs/44327327382).

Recorded-control comparisons cover 8,700 runway and VTOL samples. Use a new output directory when replaying archived controls. [Recorded Phantom flight reproduction](tools/reproduce_recorded_phantom.py).

---

## Cockpit Flight Controls Reference

| Control Input | Keyboard Shortcut | Function & Behavior |
| :--- | :--- | :--- |
| **Phantom flight inputs** | Use the labelled Phantom panel | Take control, then set collective, pitch/roll/yaw, surfaces, pods, legs, wheel drive and boosters; commands remain held |
| **R6 pitch / roll / yaw mix** | `W` / `S`, `A` / `D`, `Q` / `E` | Raw manual mixes after taking authority |
| **R6 collective** | `R` / `F` | Increase / decrease collective |
| **R6 thrust direction** | Arrow keys | Raw fan tilt; cockpit view follows cabin heading |
| **R6 engine / shutdown** | `X` / `Space` | Toggle engine / feather collective and shut down |
| **Wing Deploy / Stow** | Click in **Controls HUD** | Slide wings from cassette (requires airspeed < 25 m/s) |
| **Camera View** | `C` | Toggle cockpit / chase; other views use their labelled buttons |
| **Voice Push-to-Talk**| Click & hold **🎙 Voice** | Spoken tactical commands (*"gear down"*, *"abort"*) |

---

## Engineering Documentation & Design Specs

* **[Design System Rules](DESIGN_SYSTEM_RULES.md):** Complete specifications for UI tokens, color palettes, typography, Three.js asset pipelines, and DOM component patterns.
* **[Phantom A10-B Model Specification](docs/phantom/PHANTOM_A10B_MODEL.md):** Aerodynamic polars, mass breakdown, actuator travel limits, and power distribution.
* **[Phantom FX-A A10-C Fans-Off Takeoff Study](docs/phantom/A10C_FANS_OFF_TAKEOFF.md):** PR #41 development model, turbojet/nose-strut physics, verified run results and remaining limitations.
* **[Live Fly-By-Wire Pilot Contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md):** Strict architectural requirements for human and AI closed-loop control.
* **[Physics & Research Baseline](docs/PHYSICS_AND_RESEARCH_BASELINE.md):** The underlying equations of motion, momentum bounds, and verification benchmarks.
* **[Flight Index](docs/FLIGHT_INDEX.md):** Master catalog of historical sorties and black-box data archives.

---

## Licensing & Credits

Copyright © 2026 Steven Dark (SDarkVader). **All rights reserved.**<br>
VTX is proprietary software and game intellectual property. Third-party packages (MuJoCo, Three.js, FastAPI) remain subject to their respective open-source licenses. For developer collaborations or licensing inquiries, contact [SDarkVader on GitHub](https://github.com/SDarkVader).
