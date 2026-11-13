<div align="center">

# VTX — VADER'S TAXIS

### A physics-driven flight game and aircraft development sandbox

**BUILD IT. FLY IT. BREAK IT. FIGURE OUT WHY.**

<img src="docs/phantom/img/a10-visual-pass.jpg" alt="VTX Phantom aircraft artwork" width="100%"/>

*Design the aircraft. Take the controls. See what happens.*

**IN DEVELOPMENT**

</div>

VTX is a flight game built around original aircraft, hands-on flying, experimental engineering and a living airport environment. Fly from the cockpit or watch from outside, experiment with different aircraft and control systems, and explore what each machine can do.

The aircraft move through the game's physics simulation. Lift, thrust, control inputs, momentum, terrain contact and collisions shape every flight. Take off, climb, turn, hover, accelerate, descend or crash — then change something and try again.

## Fly the Phantom

![Phantom A10-C flight graphic](docs/phantom/img/a10c-flight-brief.svg)

The **Phantom FX-A** is VTX's transforming experimental aircraft family, combining wings, control surfaces, lift fans and forward propulsion.

The **A10-C** adds a turbojet development configuration and an actuated nose strut. Recent flights include runway takeoff, high-altitude climbing, turning, deceleration and low-horizontal-speed manoeuvring.

In November 2026, the A10-C recorded **1,456.98 metres of terrain clearance** in a cockpit capture, **14.31 metres per second** of positive vertical speed, and **0.18 metres per second** horizontal ground speed during ascent. A separate fans-off runway test recorded lift-off at approximately **79 metres per second**.

These flights are part of the ongoing development of the game and its aircraft.

[See the A10-C flight record](docs/phantom/A10C_OPERATOR_FLIGHTS_20261112.md) · [Fans-off runway takeoff](docs/phantom/A10C_FANS_OFF_TAKEOFF.md)

## The aircraft

| Aircraft | Description |
| :--- | :--- |
| **Phantom A10-C** | Latest Phantom development variant, with turbojets, wings, canards and lift-fan systems |
| **Phantom A10-B** | Current default Phantom configuration, with deployable wings and multiple propulsion controls |
| **Phantom A10-A** | Earlier Phantom VTOL and flight-test variant |
| **R6 Argon** | Vectored-fan aircraft developed for hovering, manoeuvring and point-to-point flights |

**Ricochet RC-01** is another aircraft design in development.

<div align="center">
<img src="reference/phantom_a10b_20261109/images/01_deploy_1.png" alt="Phantom wing deployment" width="48%"/>
<img src="reference/phantom_a10b_20261109/images/09_decel_1.png" alt="Phantom flight visual" width="48%"/>
</div>

## Inside VTX

**Fly your way.** Use the live cockpit, instruments, manual flight controls and external views. Manage thrust, control surfaces, attitude and flight path.

**Explore the airport and sandbox.** Fly around runways, taxiways, surrounding terrain and dedicated testing areas. The environments are part of the simulation, including ground contact and obstacles.

**Experiment with AI pilots.** VTX includes pilot-command interfaces and ongoing AI/voice-control development, including Colin.

**Replay the engineering.** Flight telemetry, aircraft configurations and test records help track how each design behaves across flights.

![VTX cockpit](evidence/hosted-live.png)

## How it works

VTX combines **MuJoCo physics**, a **Three.js browser cockpit**, aircraft models, flight controls and recorded telemetry. The simulation drives the aircraft's movement; the visual world follows.

Development continues across the aircraft, environments, flight controls, AI pilots and game interface.

## Run locally

On Windows, with Python 3.12 or later and a modern browser:

```powershell
git clone https://github.com/SDarkVader/-vtx-flight-sim.git
cd .\-vtx-flight-sim
.\launch-windows.bat
```

Open the local address shown by the launcher.

## Development and flight records

The project includes detailed engineering notes and flight records for anyone interested in how the aircraft and simulator are being built.

[A10-C flight record](docs/phantom/A10C_OPERATOR_FLIGHTS_20261112.md) · [A10-C runway testing](docs/phantom/A10C_FANS_OFF_TAKEOFF.md) · [A10-B model](docs/phantom/PHANTOM_A10B_MODEL.md) · [Flight index](docs/FLIGHT_INDEX.md) · [Physics and research](docs/PHYSICS_AND_RESEARCH_BASELINE.md)

---

<div align="center">

**VTX — VADER'S TAXIS**

*Build. Fly. Experiment.*

© 2026 Steven Dark / SDarkVader

</div>
