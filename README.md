# VTX — Vader's Taxis: Experimental Flight Laboratory

## Current reviewed integration — 15 November 2026

The continuity integration is on `codex/vtx-continuity-20261115`. **Main Aircraft promotion is pending the owner's flight tests.** The two recovered Phantom candidates remain distinct under Experiments; A10-B is a pinned reference, not an automatically promoted default.

Read the [project continuity record](docs/VTX_CONTINUITY.md) before engineering work. On Steve's PC its live authoritative copy is `C:/Users/steve/Documents/Github/-vtx-flight-sim/docs/VTX_CONTINUITY.md`; the repository copy is its publication snapshot. Original flights stay in their recorded local archive and are not replaced by test output.

| Candidate | Original evidence | Current verification |
| --- | --- | --- |
| `phantom-a10c-runway-20261112` | `20261112T132734-215fcf` airport; `20261112T135625-df0959` sandbox | Recorded-control takeoff reproduced through the 400 Hz solver; first 42 s / 4,200 samples match 16 channels |
| `phantom-a10c-vtol-20261112` | `20261112T204732-17cc37`, `20261112T211016-e9d0ab` airport | Recorded-control VTOL takeoff reproduced; first 45 s / 4,500 samples match 16 channels |
| `r6-argon-20261103` | `20261103T125202-92636c`, historical valley | Recorded model/terrain recovered; original full command log remains unavailable; cockpit/flight acceptance pending |

Successful takeoffs and sustained flight remain valid evidence independently of later outcomes. Offline reproduction is not a substitute for the owner's cockpit flight acceptance. Exact parents, configuration and environment links are in [the revision registry](inputs/flight_revisions.json).

The authored wheels and pod mounts are retained. Collision dimensions and visual offsets are diagnostic data in Engineering. **Suspension schematic** is an optional physical reference, off by default, not structural actuator CAD. See [the schematic contract](docs/phantom/A10C_SUSPENSION_SCHEMATIC.md).

Use **Save flight & switch** before changing aircraft. Flight records restores supported checkpoints paused; then choose **Take control** and **Resume existing mission**. Phantom inner checkpoint format 3 retains the radar ground-reference calibration. Missing or incompatible dependencies and older insufficient checkpoints remain preserved with an explicit recovery failure, rather than being silently reset. Camera preferences are stored separately in that browser profile.

The actual ground check saved a runway state, switched to the distinct VTOL candidate and restored the same runway run paused at 55.0175 s with identical checkpoint bytes and retained calibration. Full owner flight tests, Argon acceptance and promotion remain outstanding.

> **"Build it. Fly it. Break it. Figure out why."**

![Phantom A10-B Visual Pass](docs/phantom/img/a10-visual-pass.jpg)

**VTX** is a physics-driven 3D aerospace flight-test game and engineering proving ground set in the experimental hangar of *Vader's Taxis*. Step into the shoes of a test pilot and flight-test engineer: configure cutting-edge vertical takeoff (VTOL) and transforming aircraft, command real fly-by-wire flight surfaces, take off from active international airfields or rugged mountain test ranges, collaborate with an evolving AI copilot, and analyze real black-box flight data when things go sideways.

Every flight in VTX is governed by genuine **400 Hz Newton-Euler multibody physics** powered by MuJoCo. There are no invisible autopilot rails, scripted animations masquerading as flight, or rubber-band physics: mass, aerodynamic stall, rotor gyroscopic precession, actuator rate limits, tire friction, and structural loads decide whether your vehicle climbs out over the valley or impacts the tarmac.

> [!IMPORTANT]
> **Project Status & Proprietary Notice:** VTX is an experimental prototype and flight-test sandbox, **not a finished commercial release**. All original VTX game content, vehicle designs, CAD models, lore, and software code are proprietary. No commercial exploitation or unauthorized distribution is permitted without prior written consent. See [LICENSE](LICENSE).

---

## What You Can Do in VTX

Experience the exhilaration, unpredictability, and technical precision of experimental aviation.

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

![Phantom A10-B Wing Deployment Sequence](reference/phantom_a10b_20261109/images/01_deploy_1.png)

---

### 2. Choose Your Proving Ground (Selectable Live Worlds)
Switch instantly between two distinct, high-fidelity physical environments directly from the cockpit header:

* **Main Airport (8,000 × 8,000 m):** A full-scale commercial airfield featuring dual 3,000 m parallel runways, high-speed taxiways, terminal gate complexes, ramp areas, a central control tower, and procedural approach lighting. Ideal for high-speed transition runs, long climbs, and crosswind landings.
* **Test Sandbox — Stage 1 Valley (2,000 × 2,000 m):** Current valley test environment. The separate **Historical R6 valley (1,000 × 1,000 m)** preserves the 3 November terrain. They have different collision/heightfield identities; matching labels alone do not establish the same environment.

> [!NOTE]
> Environment switching in VTX is a **true physical terrain swap**, not a cosmetic skybox. Swapping between Airport and Sandbox reloads MuJoCo collision heightfields, rebuilds ground contact geometry, updates the 2D tactical radar minimap, and computes a fresh SHA-256 model fingerprint.

![Live Cockpit and 3D Viewport](evidence/hosted-live.png)

---

### 3. Pilot the Hangar Fleet

| Aircraft Variant | Class / Architecture | Distinctive Flight Capabilities | Historic Milestone / Provenance |
| :--- | :--- | :--- | :--- |
| **Phantom A10-B** *(Pinned reference)* | Two-seat transforming aerocar (FX-A) | 7° wing incidence, active front-wheel steering, Munk hull lift, Moog 965 actuator models, rear boosters, DRS flap | Historical reference; Main promotion is not inferred from its pin |
| **Phantom FX-A A10-C** *(Earlier development; PR #41)* | Fans-off, wing-borne A10-B derivative | Four PBS TJ150-class turbojets, rate-limited takeoff-stance setting, lift fans off in the runway study | Earlier study retained in its original documentation; the recovered 12 November configurations and timings are listed separately above |
| **Phantom A10-A** | Baseline VTOL prototype | Retractable cassette wings, 4 wheel-pod fans, fixed P6 stabilator | 72-sortie November campaign benchmark (peak altitude 600.58 m) |
| **R6 Argon** | Four-pod ducted quadrotor | 4 independently articulated ducted fan pods, annular primary structure | Foundation testbed; pure hover agility and dynamic station-keeping |
| **Phantom A10 As-Drawn** | Scale CAD concept | Compact Ø0.49 m fan geometry (thrust-to-weight 0.52) | Educational study frame demonstrating hover deficit |
| **R4 / R5 Study Frames** | Aerodynamic test mules | Lightweight tubular airframes with variable mass distributions | Inertia screening and ground-resonance validation |

> **Historical model reference:** `phantom-a10b` config `3ecae1a9…` remains pinned in [aircraft identity](inputs/aircraft_identity.json). The original A10-C development variant came through [PR #41](https://github.com/SDarkVader/-vtx-flight-sim/pull/41). The two current recovered candidates have separate verified identities in [the revision registry](inputs/flight_revisions.json), while promotion remains pending. They preserve the B visual asset plus an explicitly optional schematic. [The takeoff study](docs/phantom/A10C_FANS_OFF_TAKEOFF.md) separates earlier studies from the verified 12 November recordings. Fans-off landing, endurance, crosswind and engine-out acceptance remain outstanding.

![Phantom A10-B Vertical Takeoff](reference/phantom_a10b_20261109/images/06_vtol_1.png)

---

### 4. Fly with Colin (The Evolving AI Pilot) & Voice Control
VTX is engineered around genuine human-machine collaboration:
* **The AI Pilot Contract:** Meet **Colin**, an AI copilot that interacts with the aircraft through the exact same fly-by-wire controls and sensory observations available to a human pilot. Colin does not use cheat codes, invisible route followers, or pre-baked trajectories; he observes airspeed, pitch, roll, and altitude, issues actuator commands, experiences the physical consequences, and learns through trial, error, and recovery.
* **Push-to-Talk Voice Commands (🎙 Voice):** Speak naturally into your microphone (in Chrome or Edge) to issue tactical flight commands (*"gear down"*, *"deploy wings"*, *"rotate pods vertical"*, *"climb fifty meters"*). Voice audio is parsed against a deterministic aerospace grammar; critical safety maneuvers require a clear verbal *"confirm"* before execution.
* **Dual Authority Handover:** Pass control authority back and forth seamlessly between human manual inputs and Colin during any phase of flight.

---

### 5. Investigate Crashes & Audit Flight Evidence
In VTX, a crash is not a "game over" screen—it is primary flight-test data.
* **Timestamped Telemetry Black Box:** The solver runs at 400 Hz; channels retain their recorded rates, including the Phantom's 100 Hz step log. Runs retain control demands, actuator state, energy and contact evidence.
* **2D Tactical Minimap:** Track your real-time ground track, velocity vector, altitude tape, and pad clearances on a custom vector radar canvas.
* **The 7-Gate Flight Test Dashboard (`/dashboard/`):** Evaluate completed sorties against strict aerospace validation gates. Review post-crash structural failure points, pilot audit logs, and diagnostic telemetry to adjust your airframe parameters for the next flight.

![Phantom A10-B High-Speed Deceleration Run](reference/phantom_a10b_20261109/images/09_decel_1.png)

---

## The Unified Three-Panel Cockpit

VTX integrates three complete operational workstations into a single high-performance browser interface:

```
+=======================================================================================================+
| VTX AEROSPACE proving ground · [AIRPORT] [SANDBOX] · Phantom A10-B · SORTIE STANDBY                    |
+====================================+==================================+===============================+
| PANEL 1: LIVE COCKPIT              | PANEL 2: FLIGHT TEST DASHBOARD   | PANEL 3: PHYSICS EXPERIMENTS  |
|                                    |                                  |                               |
| • 60 FPS Three.js 3D Viewport      | • Embedded Suite (`/dashboard/`) | • Independent MuJoCo Kernel   |
| • Tactical Minimap Radar (Canvas)  | • 7 Evidence Certification Gates | • Custom Mass/Inertia Sliders |
| • Floating HUD Drawers:            | • Historical Sortie Archives     | • Aerodynamic Polar Overrides |
|   - Mission: Origin & Destination  | • Black-Box JSONL Telemetry      | • Automated Batch Monte Carlo |
|   - Controls: Fly-by-wire & Voice  | • Failure Cause Classification   | • Downloadable Evidence Packs |
|   - Views: Cockpit / Orbit / Tower | • Checkpoint Restoration Engine  | • SHA-256 Provenance Fingerprint|
+====================================+==================================+===============================+
```

1. **Live Cockpit (`/`):** The primary flight station. Direct WebGL window into the simulation with interactive camera views (Cockpit 1st-person, Chase, Orbit, Tower, Runway Threshold) and floating tactical HUD drawers.
2. **Flight Test Dashboard (`/dashboard/`):** The flight operations center. Inspect every historical sortie, review certified evidence gates, download raw telemetry streams, and inspect pilot reasoning logs.
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
        FastAPI["FastAPI / Uvicorn Server<br/>(Reviewed PC port 8770)"]
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
        ColinPilot["Colin AI Pilot<br/>(Closed-Loop FBW Learning)"]
        AuditRecorder["Pilot Exchange Audit<br/>(Model Decision Ledger)"]
    end

    subgraph Storage["DURABLE EVIDENCE REPOSITORY"]
        EvidenceLedger["Local AppData / Checkpoints<br/>($env:VTX_DATA_ROOT)"]
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
  Integrated the Blendstra P0-V4 CAD geometry into a unified physics model. Defined the [Live Fly-By-Wire Pilot Contract](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md), introducing Colin—an AI copilot that learns by physical experience without pre-baked path assists.
* **Milestone 3 — The 72-Sortie Phantom A10-A Campaign (Nov 4–7, 2026):**
  Executed a 72-flight automated test campaign with the initial Phantom prototype (`70089cca`), achieving a peak altitude record of 600.58 m. Validated cassette wing extension mechanics while uncovering low-speed hover power deficits and hub drive limits.
* **Milestone 4 — Phantom A10-B Evolution (Nov 8–9, 2026):**
  Engineered the A10-B variant (`3ecae1a9`): added 7° wing incidence, active steer-by-wire front suspension, Munk hull lift polars, Moog Model 965 actuator dynamic models, and verified high-speed 0.8g fan-vectored deceleration.
* **Milestone 5 — Unified Three-Panel Cockpit & Dual Environments (Current):**
  Combined the 3D Live Cockpit, 7-Gate Flight Test Dashboard, and Independent Physics Experiments into a single-origin web workspace. Added real-time environment switching between the 8 km Main Airport and the 1 km Stage 1 Valley Sandbox with full MuJoCo terrain recreation.

---

## Quickstart: Starting the Simulator

### Prerequisites
* Windows 10/11 64-bit
* Python 3.11+ with `pip`
* A modern browser with WebGL 2.0 (Google Chrome or Microsoft Edge recommended for voice commands)

### Steve's reviewed local station

Double-click `START_VTX_REVIEWED.bat` in `C:\Users\steve\Documents\Github\-vtx-flight-sim`. That local wrapper points to the reviewed isolated checkout, existing Python environment, and original flight data directory. It does not launch the primary checkout's older code.

The tracked [launch-reviewed.bat](launch-reviewed.bat) verifies the pinned Python-tree and visual hashes, uses **port 8770**, and refuses an occupied port. It never kills a process or searches for a different port. Open or reuse one cockpit tab at **[http://127.0.0.1:8770/](http://127.0.0.1:8770/)**; the launcher does not open a second tab automatically. Keep its server window open.

For another reviewed checkout, explicitly supply its existing environment and data root:

```powershell
$env:VTX_PYTHON = 'C:\path\to\existing\.venv\Scripts\python.exe'
$env:VTX_DATA_ROOT = 'C:\path\to\existing\VTX\flight-data'
.\launch-reviewed.bat --check  # Read-only configuration/hash check; starts no server
.\launch-reviewed.bat
```

Install `requirements.txt` in a dedicated environment when setting up a new PC. Read the continuity record before choosing an archive or changing a pinned runtime. The earlier `RUN_THREE_PANEL_DEV.ps1`, port 8765/8766/18911 examples and generic per-checkout launcher are historical/development entry points; they are not Steve's reviewed continuity station.

### Verification

Current code passed 111 focused checkpoint/identity/replay tests and 29 cockpit checks, plus separate flight/actuator/contact/retry and startup/selection/world/view-preference regressions. Original-control reproduction uses [reproduce_recorded_phantom.py](tools/reproduce_recorded_phantom.py) with a new output directory outside the source checkout and original archive. Commands and local evidence paths are recorded in the continuity record; original logs remain local.

The local recovery package retains exact tested bytes. Runtime/public/input line endings are pinned for Git checkout so Windows conversion does not silently change their identity. A hash mismatch stops the reviewed launcher; it does not rewrite the pin.

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
