# Vader's Taxis — Project Roadmap and To-Do

Status: Planning document, 3 November 2026. This is a roadmap, not a claim that every feature is implemented.

## Immediate — Phantom flight first
- [ ] Continue Phantom flight trials, including the planned higher-altitude manoeuvres.
- [ ] Test articulated wheel/thruster mechanisms and control authority in flight.
- [ ] Improve attitude stability, yaw response, and landing reliability using telemetry.
- [ ] Keep physical parameters, mass, inertia, fuel and power constraints explicit.
- [ ] Preserve existing aircraft configurations and flight logs before major changes.
- [ ] Develop the cockpit passenger view: look around while the AI pilots, issue spoken instructions, and allow manual takeover.

## Existing engineering platforms
- [ ] Maintain R6 as a separate engineering/control testbed and comparison baseline.
- [ ] Continue VTX Phantom as the flagship transforming aircraft, retaining editable Blender models and mechanism variants.
- [ ] Record configuration changes and compare flight performance under repeatable conditions.
- [ ] Validate assumptions and distinguish simulation success from real-aircraft feasibility.

## First playable course — airport
- [ ] Build on the existing Gloucestershire-inspired airport layout, scenery and background traffic.
- [ ] Create a repeatable course: takeoff, checkpoints, altitude/speed requirements, manoeuvres and return-to-base landing.
- [ ] Let AI pilots operate actual controls; do not script their trajectories.
- [ ] Record completion, time, precision, constraint violations, energy/fuel use, and crashes.
- [ ] Test known courses and previously unseen courses.

## AI pilot training and evaluation
- [ ] Preserve pilot observations, decisions, control inputs, telemetry and outcomes.
- [ ] Support conversational instructions, coaching, corrections and flight debriefs.
- [ ] Compare pilots and aircraft/pilot pairings under identical conditions.
- [ ] Test whether lessons transfer between aircraft configurations and new courses.
- [ ] Separate improvements due to engineering, external memory and actual model training.
- [ ] Develop scenarios involving unexpected failures, uncertainty, alternative objectives and expert-human instruction.

## Garage and modular aircraft engineering
- [ ] Define interchangeable components: structures, wings, rotors, motors, actuators, wheels, fuel tanks, batteries, controls and sensors.
- [ ] Attach meaningful geometry, mass, inertia, performance limits, structural constraints and costs to components.
- [ ] Enable assembly, configuration changes, tests and failure analysis.
- [ ] Support multiple aircraft classes: gliders, light fixed-wing aircraft, VTOL, flying cars and experimental designs.
- [ ] Provide a sandbox with unrestricted budget as well as progression play.

## Voice-driven configuration and engineering
- [ ] Allow spoken flight commands and supervised AI control.
- [ ] Allow voice changes to permitted live settings, gains and presets.
- [ ] Queue structural or hardware changes for safe ground-based engineering updates and retesting.
- [ ] Provide confirmation, validation, undo and configuration history for changes.

## Game modes, competition and environments
- [ ] Add time trials, races, precision landing, obstacle courses and manoeuvre challenges.
- [ ] Compare entire aircraft-and-pilot combinations, not only AI models.
- [ ] Add custom course design and increasingly difficult environments, including mountains, cities and underground spaces.
- [ ] Offer realistic engineering competitions and optional arcade modes.
- [ ] Introduce temporary boosters, auxiliary fuel pickups and other power-ups with defined physics effects.

## Progression and business model — later
- [ ] Create in-game earnings from missions and challenges.
- [ ] Price parts and upgrades to make engineering trade-offs meaningful.
- [ ] Maintain a free-build/unlimited-budget sandbox.
- [ ] Explore a paid base game, expansions and cosmetic extras before considering optional purchases.
- [ ] Avoid pay-to-win mechanics and intrusive microtransactions.
- [ ] Run external playtests when a usable game loop exists; use feedback to prioritise improvements.

## Long-term research track
- [ ] Invite experienced pilots/engineers to coach agents during live or recorded simulations.
- [ ] Capture observations, interventions, disagreement, uncertainty and decision timing alongside telemetry.
- [ ] Test unfamiliar emergencies and the ability to abandon unsafe objectives.
- [ ] Evaluate whether expert coaching improves transferable decision-making beyond documentation and repeated practice.

## Guiding principles
- The player can be engineer, instructor, passenger, pilot or team manager.
- Physics-driven aircraft and AI control are the foundation; arcade modes are optional additions.
- Route waypoints may be predetermined, but actual control actions are not.
- Failures are informative and can be entertaining; do not fake successful flights.
- Immediate priority remains Phantom flight, not premature implementation of the full game.
