# Colin — start here

**Build our VTX aircraft, not a convenient mathematical substitute.**

**Colin must directly fly the simulated aircraft via actual live fly-by-wire inputs.** Read [docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). User selects only start and destination. Colin, not an autopilot or scripted replay, chooses controls continuously from observations, takes off, navigates, tries to land and learns from consequences. Give Colin the exact same input interface as a human pilot. Never substitute a precomputed path for actual piloting.

**First read [docs/PHYSICS_AND_RESEARCH_BASELINE.md](docs/PHYSICS_AND_RESEARCH_BASELINE.md).** No aircraft physics work is accepted without gravity, full body inertia, rotor angular momentum, ground contact, real moment arms and source-provenanced design properties. A massless visual proxy is not the aircraft.

1. Import and inspect the actual P0-V4 model and engineering data. Build a coherent editable mechanical 3D aircraft, including real rotor tilt joints, power path, mass/CG/inertia, fuel placement, structure and landing contacts. Document unknowns; do not invent performance to force flight.
2. Create a full navigable 3D **physical flight-test world** with terrain, obstacles, collision and landing physics. The proprietor selects any valid A and B on the map. The aircraft must attempt ground takeoff, fly there and land through its own modelled forces, or visibly fail.
3. Implement an **inexperienced pilot that learns by operating this aircraft** using permitted observations, actuators, crashes and other outcomes. Do not give it a pre-tuned perfect autopilot, scripted motion or artificial stability. Record the learning and preserve checkpoints.
4. Use the observed physics and failures to test design changes against the original, updating aircraft geometry and mechanics together. Reproducibility is for scientific inspection, not a guarantee of success.
5. Prepare for a second, **unseen environment provided later by the proprietor**. Do not design, access or train on it now. Transfer Stage 1 learning without resetting the pilot.

Run the experiment, show the working world and aircraft, preserve failures and report evidence, uncertainties and engineering changes. Do not claim a successful VTX flight based on synthetic data or an animation.

**Acceptance:** one integrated mechanical digital aircraft, one interactive world, user-chosen ground-to-ground mission attempts with real physics and consequences, actual experience-based updates, persistent learned state and verifiable failure/feedback records. A crash is not a test-framework failure.

Read `COLIN_MISSION.md` as the authoritative contract. Earlier instructions requesting preset successful paths, perfect-state controllers or synthetic hover demonstrations are superseded.
