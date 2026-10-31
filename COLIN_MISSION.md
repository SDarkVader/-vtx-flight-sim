# Colin — VTX physical aircraft and experiential flight laboratory

**Objective:** Build the actual VTX-P0-V4 as a coherent mechanical *digital aircraft*, place it in an explorable physical 3D test world, and let an initially inexperienced pilot learn to operate it through attempts and consequences. Use results to revise the design. This is an engineering development experiment, not a flight-demo animation or a predetermined stable autopilot.

## 1. Build the aircraft before pretending to fly it

Use the saved Blendstra P0-V4 design and available engineering records as the baseline. Establish **one authoritative, editable aircraft assembly**: spherical two-passenger cabin, four independently vectored ducted fans, annular primary structure, genuine two-axis bearing/actuator mounting, central-to-local mechanical power path, four protected fuel cells and six landing contacts.

Identify actual dimensions, material choices, mass distribution, CG, inertia, clearances, hinge loads, power transmission, rotor forces and contact geometry from the design and calculations. Check structural and mechanical plausibility. **Do not invent hardware, magical joints, rotor performance or mass properties to make the aircraft fly.** Where measurements are absent, derive defensible bounds/physics relationships, identify assumptions, run sensitivity studies, and report what remains unknown. A graphical placeholder must never silently stand in for a completed mechanism. Keep visual design ideas separate from modelled components.

The aircraft's physical implementation and its simulation must describe the same object. Changes to a rotor, joint, mass, gear, structure or landing assembly must change the corresponding geometry and physics; track each revision.

## 2. Build a real test world

Provide a usable, navigable, world-scale **3D flight environment**, not a small embedded visualisation of scripted motion. Include terrain, structures/obstacles, collision/contact mechanics, landing surfaces and room for unrestricted flight attempts. Give the proprietor a map to select **any valid departure location** and **any valid destination**; validate ground support, rotor clearance and approach feasibility without restricting missions to fixed pads.

The aircraft starts on its landing gear at A and must attempt to spool up, lift off, climb, navigate, avoid obstacles, approach B and physically touch down. Landing is only recognised when the model is supported and stationary. If it hits something, tips, stalls, over-rotates or cannot take off, show and record that physical outcome. Never teleport, force a waypoint, overwrite aircraft pose, suppress impacts or award success by checking a script.

## 3. An inexperienced pilot must learn by experience

Create a pilot/controller with **explicitly limited observations and controls** consistent with sensors and actuators on the model. It begins without a prelearned VTX-specific flying solution. It must interact with the aircraft, experience its responses, make mistakes and update its policy/controller from those outcomes. Do not solve the missions in advance with a perfectly tuned position/attitude controller disguised as learning. Distinguish immutable equations of motion from *mutable learned behaviour*.

A crash is a valid and potentially expected result. Persist outcomes, observations, control actions, failures, learner updates and checkpoints. Keep failed runs; do not tune the mechanics or restart invisibly until a test passes. Provide manual inspection/replay and an understandable account of what was learned versus hardcoded.

## 4. Engineering feedback loop

Use actual failure modes, load calculations, stability boundaries and operating data to identify weaknesses in the aircraft and propose design changes. Update the model, rerun comparable experiments and report the differences. Alternative engineering options are welcome where calculations justify them; do not pick a design because the illustration is attractive.

Reproducible initial states, seeds, physical parameters and software versions are needed **to audit why behaviour occurred**; determinism must not guarantee good flying. Unit/physics tests verify laws, geometry and code, not a preordained successful flight. Performance claims must state whether the relevant properties are measured, calculated, provisional or unknown.

## 5. Later unseen environment

**Stage 1:** Build the aircraft and initial test environment; run experience-based learning, preserving the trained state. **Stage 2:** The proprietor will later introduce a different environment of their choosing. Do not create, view, pretrain on, guess or preload Stage 2. Carry learned experience forward, allow learning from new observations and measure transfer/failure against a fresh start.

## Deliverables and decision points

Provide a working 3D aircraft assembly, physically interactive test world, map-selected ground-to-ground flight attempts, independently responsive four-rotor actuation, observed learning and persistent checkpoints, reproducible crash/failure evidence, and a revision ledger linking engineering changes to outcomes. Run the system: do not stop with a repo, diagrams, numerical solver, scripted successful demo or screenshots.

**Engineering honesty:** If parts of the real P0-V4 cannot yet be implemented from available properties, implement what is supportable, explicitly identify blockers and never fabricate an aircraft that flies by assumption. The objective is to discover what works, what fails and what must change—not to guarantee success.

Current repository: `SDarkVader/-vtx-flight-sim`, separate from The Node. Primary model: https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2.
