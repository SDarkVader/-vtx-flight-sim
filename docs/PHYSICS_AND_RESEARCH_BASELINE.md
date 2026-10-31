# VTX-P0-V4 — Engineering physics, mass and research baseline

**Purpose:** This is the mandatory physical model for building and flight-testing the *same* VTX aircraft represented by the saved Blendstra P0-V4 geometry. The pilot's learning system, scene renderer and collision bodies must use this shared aircraft; a massless game object is not acceptable. This document is a design baseline, not evidence of flightworthiness.

## 1. Source-of-truth and provenance

- Saved, editable Blendstra aircraft: [VTX-P0-V4 exact version](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2).
- Project `3288318a-95f4-4dda-8d0f-dbf7b8eaceb9`; version `version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2`; source geometry artifact SHA-256 `2db9abd64ba9b7078e6e539ba4c6b9177e58e335a085a8ea213b5ffa6e987e35`, as returned by the connected model record. These identifiers pin the source and do not themselves validate mechanical physics.
- Existing source reference groups P01–P11 and research records are attached to modeled parts. Extract the *actual editable geometry*, supported dimensions and pivots before assigning masses, contacts or actuators.
- Distinguish: **geometry measured in saved model**, **estimated engineering budget**, **published external reference (different hardware)**, **calculated outcome from explicit assumptions**, **experimental measurement**. Never silently convert one type to another.
- Other original project materials include historical VTX performance and parts PDFs and aero/structural literature. Where a source is unavailable to Colin, show the access blocker; do not invent contents.

## 2. Mandatory mass-bearing aircraft

Existing P0-V4 **allocation budget**, not a weighed or measured aircraft:

| Configuration | Empty allocation | Two occupants | Fuel | Total |
|---|---:|---:|---:|---:|
| Test mission | 843 kg | 170 kg | 60 kg | 1,073 kg |
| Full-fuel planning | 843 kg | 170 kg | 110 kg | 1,123 kg |

At nominal gravitational acceleration `g = 9.80665 m/s²`, the corresponding **static weight magnitudes** are approximately 10,523 N and 11,013 N. These are calculation results **conditional on the allocation budget**.

The aircraft cannot simply be assigned one lump mass with arbitrary centre of gravity. Build an inspectable mass-properties ledger for every modeled subsystem (cabin, occupants, powerplant/drive, four fans/ducts/actuators, primary structure, four fuel cells and fuel fill, six landing assemblies and avionics): `mass_kg`, body-frame centroid `r_m`, inertia tensor about its own centroid `I_kg_m2`, geometry/source reference, assumption status and uncertainty. Derive total CG and full symmetric 3x3 body inertia with the parallel-axis theorem:

`r_CG = sum(m_i * r_i) / sum(m_i)`

`I_CG = sum( I_i + m_i * ( (d_i·d_i) E - d_i d_i^T) )`, `d_i = r_i - r_CG`.

Reject zero/negative total mass, physically impossible component values and non-positive-definite full inertia. Recompute CG and inertia when fuel, passenger load, nacelle tilt or articulated mass distribution changes (at an appropriate physics fidelity). Keep empty/allocation/operating mass distinct.

Fuel layout baseline: four protected diagonal cells; modeled combined gross capacity ~195.43 L; assumed 85% usable ~166.12 L. At 0.8 kg/L Jet A-1 assumed density, 110 kg requires 137.5 L. Volumes and density are *provisional*, not measured or certified; verify geometry and capacity.

## 3. Gravitation, angular momentum and force balance: never optional

Choose and document inertial/world and body coordinate frames, sign conventions and gravity direction. Every physical timestep must use actual mass and full gravity force:

`F_g^world = m * (0,0,-g)` for world +Z up.

For constant-mass rigid-body modelling, the centre-of-mass equation is

`m * a_CG^world = F_g^world + sum(R_body_to_world * F_rotor_i^body) + F_aero^world + F_contact^world + F_other^world`.

If a rotor is off, it produces **no fictional lift**. A non-supporting craft with no sufficient lift must accelerate downward; aerodynamic drag may subsequently modify freefall. Do not pin altitude or inject corrective lift via game-engine scripts.

For the rotating rigid airframe the full angular-momentum balance (body coordinates) is

`H_body = I_body * omega_body + sum(h_spinning_rotors_body) + H_other_articulated_body`

`tau_external_body = (dH_body/dt)_body + omega_body × H_body`.

For rotor `i`, a first-order spin angular momentum model is `h_rotor_i = J_rotor_i * Omega_i * axis_i_body`. Its **magnitude, sign and direction** vary with rotor speed, rotation sense and nacelle tilt; include `d(h_rotor_i)/dt` from speed changes and axis articulation and the `omega × h_rotor_i` gyroscopic coupling. Account for rotor aerodynamic reaction torques, mechanical drive torques, shaft/bearing reactions and joint forces with an explicit consistent multibody accounting convention **without double-counting internal actions**. The simple fixed-body reduction

`I * dot(omega) + omega × (I omega) = tau_external - sum( dot(h_rotor)_body + omega × h_rotor )`

is valid only under its stated inertia, actuator and reference-frame assumptions. For articulated nacelles, variable inertia, spinning shafts and cabin gimbals, implement multibody dynamics or derive the additional terms consistently rather than assuming the reduction is exact.

Moment contributions from each rotor force and landing contact use **actual measured lever arms relative to current CG**:

`tau_rotor_i = (r_rotor_i - r_CG) × F_rotor_i + tau_reaction_i`.

Gravity through the true CG has zero moment about that CG; offset fuel/occupant movement changes the CG and hence the rotor/control/contact moment arms.

**Physical checks:** zero-power freefall under gravity; tilted rotor generates both vertical and horizontal force and corresponding moment; equal force at asymmetric lever arms changes rotational motion; equal/opposite external impulses conserve total momentum appropriately; torque-free rotation conserves inertial angular momentum within integrator tolerance; rotor spin-up and nacelle tilt give the appropriate angular momentum exchange; reversing spin sense reverses appropriate gyroscopic/reaction signs; changing fuel load shifts CG/inertia. Document conditions when momentum is exchanged with atmosphere, ground or exhaust.

## 4. Rotor aerodynamics and power transmission

The four fans are ducted and two-axis independently vectored, not idealized arbitrary Cartesian force generators. Model for each: physically permitted tilt angles/axis order and hard stops; angular travel/velocity/acceleration; shaft alignment and joint limits; local 7.5:1 gearbox **placeholder envelope**, not a validated gearbox; bearing and transmission loads; torque/speed/power balance; rotor inertia and spin sense; thrust and torque vs RPM/pitch/inflow/density (derive from documented aerodynamic theory and available geometry or a fully identified provisional map); and duct/ground-effect interactions where feasible. Never let rotor thrust exceed motor/engine torque or shaft/gearbox power availability without logging invalid physics.

For an ideal lower-bound hover estimate, derive induced velocity and minimum momentum-theory induced power from the **actual disk areas** and weight. This ideal bound is not an estimate of real achievable shaft power or a calibrated rotor map. Additional profile, tip, duct, transmission and installation losses must be explicit assumptions or calculated inputs; do not simply assign an appealing efficiency.

Use independent rotor thrust/tilt action channels and physically plausible inertia/rates. Consider thrust line offsets, rotor gyroscopic moments `J_rotor Omega × angular_rate`, bearing reactions and nacelle mass. A user-selected design option is not a numerical performance certificate.

## 5. Structural assembly, contact, collision and energy

Attach each rotor and fan bearing to plausible supporting geometry, tie primary annular rings and deep triangulated braces through continuous force paths, and attach the six landing contacts with spring/damper stroke and contact constraints. Simulate normal reactions, friction, impact, tip-over and obstacle collisions. Rotor disks and blade envelopes must not intersect their supporting frame at any permitted articulated pose.

Track source-to-sink mechanical power, rotor aerodynamic power, structural/actuator limitations, fuel depletion and engine/exhaust modeling assumptions; avoid unbounded free energy or fuel-free perpetual hover. React physically to insufficient thrust, tilt saturation, shaft limitation, control delay, loss of drive and contact failure. If detailed deformation/failure strength is not modeled, **say so**; collision visibility is not a structural crash certification.

## 6. Research — context, never automatic calibration

The original Blendstra project has canonical research records linked to assembly parts. Carry forward these references and limitations in an evidence register:
- Akturk & Camci, 2014, ducted rotor tip clearance, DOI `10.1115/1.4023469`.
- Hine et al., 2025, eVTOL liftfan design, DOI `10.1115/1.4067673`.
- Hu et al., 2021, duct mass and aerodynamic performance, DOI `10.1016/j.ast.2021.106937`.
- Critchfield & Ning, 2026, propulsion/mission multidisciplinary optimisation, DOI `10.2514/1.C038445`.
- Muniraj & Sreehari, 2021, composite sandwich impact, DOI `10.5829/ije.2021.34.04a.26`.
- Liu et al., 2024, composite aerospace structures review, DOI `10.1016/j.paerosci.2024.101002`.

These studies do not automatically validate VTX aerodynamic efficiencies, dimensions, hardware, layups, powerplant or impact survival. Reconcile citations with the six `CANONICAL_...` model records, document what evidence is actually applied and why. Treat a missing model/research input as unknown.

## 7. Verification gates (before claiming an aircraft experiment)

1. Import the exact saved aircraft and check that editable model components, physical bodies, rotor joints, mass ledger and world-scale collision geometry correspond. Report unmapped or placeholder parts.
2. Show the mathematical/implemented gravity and angular momentum equations and test them independently, including rotor spin/tilt and rigid-body momentum conservation with correct external force accounting.
3. Perform weight-versus-achievable-rotor-lift and mechanical power feasibility calculations from actual/traceable geometry and clearly marked assumptions. Do not tune lift to make hovering possible.
4. Show physical takeoff attempts from user-selected valid ground locations, including test runs where the aircraft cannot lift, tips or crashes. The pilot begins inexperienced and can learn only from allowed observations.
5. Save each result with exact airframe revision, component properties and evidence sources, environment, actions, controller checkpoint, solver settings and failures. Use the data to propose physically justified design revisions and verify consequences.

A zero-mass body, arbitrarily chosen CG/inertia, unlimited generic thrust joint, invisible stabilizer or scripted flight is **a toy, not VTX**. Such a prototype may be used for UI smoke tests but must not pass the engineering acceptance gate.
