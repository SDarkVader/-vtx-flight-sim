# VTX live experiment: implemented scope and actual outcomes

31 October 2026. This report follows `FIRST_REPORT.md`; that initial checkpoint
is preserved. These are conditional numerical experiments, not measured aircraft
performance or an airworthiness finding.

## Source and physical baseline

The verified handoff, original engineering PDFs and exact Blendstra P0-V4A
assembly are imported. Current GitHub mission/fly-by-wire contracts were
preserved. Historical P0-V1 calculations and reference trajectories supply
engineering context, never flight controls. Component geometry, blade chord and
radius, pivot positions and exact surface moments are recoverable. Component
masses are source allocation targets distributed over surfaces; material
densities, actual weights and internal mass distribution are unknown.

The original master contains misplaced drive/actuation objects. Independent
GLB/native-source checks and ground-fault records preserve that finding. R2–R4
repair those assembly placements, extend the landing contacts with an explicit
material allowance and lower the gimbal bearing stack to separate the blades
from stationary structure. No master source was overwritten.

## What actually runs

One authoritative MuJoCo process integrates gravity, full multibody inertia,
rotor/shaft angular momentum, internal drive and tilt/cabin actuator reactions,
bounded drive and tilt/cabin power, fuel depletion, provisional blade-element
aerodynamics and world contact.
The browser renders solver states with separately articulated nacelles, rotors,
cabin and six sliding feet. A 1 km terrain world contains obstacles, roofs,
water exclusions and map-selectable valid A/B coordinates. The world is Stage 1.

Manual keyboard/sliders and Colin use the same engine, pitch and two-axis tilt
channels. Local shaft-speed and actuator-position loops are the only automatic
control. No aircraft stabilization, navigation controller, flight path or flight
animation is installed. Colin's recorded decisions cite permitted instrument
observations while the independent clock continues. Post-flight state playback
is labelled audit and cannot control the live plant.

The keyboard guide opens as a native closable dialog, including Escape and a
reopen button. Retrying a crash archives the failed run and starts a fresh
aircraft at that mission's A. It preserves the pilot checkpoint and records the
lineage. A live intact sortie cannot be silently reset through Retry.

## Actual piloting evidence

| Run | Operator and result |
| --- | --- |
| `20261031T060411-29e1d6` | Colin, three actual decisions, 800 rpm reference. Remained gear-supported; no takeoff. Two command leases expired and a stale action was rejected. |
| `20261031T061653-5f6bb3` | Brief 1200 rpm ground trial. One Colin engine-start/feathered-blade decision was applied; the proprietor ended it before takeoff and selected a new mission. No separate learning lesson was inferred from this short trial. |
| `20261031T062325-eb8ab0` | Colin, seven accepted decisions on proprietor-selected A (−205.7, −117.6) and B (144.3, 173.2), 1200 rpm proposal. Left ground, rolled and impacted. Recovery attempts failed. Explicit engine/collective abort followed. Collision; no completed navigation or landing. |
| `20261031T071731-4e6434` | Colin, R5 retry at the same A/B and 1200 rpm/critical-damping configuration. Twenty applied decisions: incremental lift, slow takeoff with trim, a small vector test, repeated rate-braking corrections and return/flare attempt. Two feet contacted, then the aircraft became airborne again. Final feather request rejected as stale. Graceful hosting shutdown ended the run; no settled landing. |

The last run reached a maximum **airframe-origin height** of 4.323 m in this
world. This is not rotor clearance or validated flight performance. Fuel use
was 0.2657 kg under the provisional SFC. Peak rigid-contact solver force was
about 1.93 MN; no structural allowable, damage or injury interpretation follows
from that solver peak. Events retain the rejected correction as well as actual
applied commands. No offline command sequence was used to pilot these runs.

The R5 retry reached 2.164 m maximum airframe-origin height and used 0.3550 kg
fuel under the same provisional SFC. Peak gear/contact force was 18.84 kN.
Its recorded outcome is **airborne attempt ended**, reason **server shutdown**;
it is not classified as a rotor/body crash and it did not satisfy landing.
The pilot's attempted feather/idle request was rejected and never applied.
The final saved state is a powered airborne bounce after partial contact.
The 45-minute hosting limit is an execution limitation, separate from the
physical outcome. Restoring the web service starts inspection mode and offers
an explicit new-sortie retry; it does not silently continue or reset that run.

Smaller lift steps and a pre-lift trim bias improved the observed departure,
but this is not an isolated demonstration of a better frame: pilot behaviour
and clock scale also changed. The later alternating roll overshoots expose
pilot latency, pitch response and gimbal/gyro coupling. The third retained
lesson records the need to release braking earlier based on measured rates.

A user clock change to 1× caused scheduling backlog in the software renderer/
physics environment. Explicit clock/pause actions are logged. The scheduler now
rebases unintegrated wall-clock backlog on an explicit clock change without
changing physical state. Native low-latency pilot transport avoids shell-review
delays. This is a numerical time-scale accommodation, not flight stabilization.

## Underside reduction: R5 experiment

R4 remains selectable and its ledger/GLB/editable derivative are retained. R5
retires all 32 members of the four legacy P06 box-spar modules that coexist with
the newer triangulated lower frame. It retains the newer primary trusses,
annular rings, fuel cells, six contacts, drive and rotor mechanisms. Retained
part masses are unchanged: there is no reallocation that gives the removed
mass back to other parts. Removed IDs and allocations are in the ledger.

| Quantity | R4 | R5 |
| --- | ---: | ---: |
| Allocated empty mass, kg | 849.3891 | 816.6689 |
| Test mass with 170 kg occupants and 60 kg fuel, kg | 1079.3891 | 1046.6689 |
| Neutral CG Z, m in source coordinates | 1.2067317 | 1.2019404 |
| Neutral Ixx / Iyy / Izz, kg m² | 1908.408 / 1872.892 / 2758.420 | 1844.310 / 1809.005 / 2632.791 |

Wolfram independently subtracted the removed components with the parallel-axis
theorem. Its CG and tensor agree with the rebuilt multibody model to numerical
precision (largest tensor discrepancy 2.65e−9 kg m²). `wolfram_underside.json`
retains the exact query/result; `underside_trade.json` links component IDs and
both configurations. The **32.7202 kg** reduction is 3.03% of test mass. Ideal
actuator-disk hover power at the same disk area would fall 4.51%; that is a
theoretical lower-bound scaling, not a measured efficiency or achieved flight.

This deletion changes the load paths. **Global stiffness, strength, fatigue and
failure margins are unknown.** The deletion is an experimental design variant,
not a substantiated safe hardware improvement. Landing springs/dampers retain
the same R4 hardware constants across variants. Their rates are not reduced
automatically to make the lighter aircraft behave better.

## Verification and unresolved engineering

The original 31 starter tests pass unchanged. Independent additional checks
cover full-tensor parallel-axis mass accounting, gravity, force/moment arms,
torque-free angular momentum, rotor spin-up reaction and gyroscopic magnitude/
spin sign, power/fuel constraints, ground support, map collision correspondence,
actuation boundaries, repeatability and crash/retry retention. The R5 sampled
triangle audit covers 6,912 blade/tilt/pitch/spin configurations with no detected
intersection. It is not a continuous swept-volume, tolerance or elastic proof.

At the documented synthetic polar, 800 rpm cannot support either allocated
test mass. The 1200 rpm experiment proposes a different reduction ratio at the
same 6016 rpm engine input and raises centrifugal loading 2.25×. Neither the
gearset nor the blade rating is qualified. The crash shows that available
conditional thrust does not establish a controllable aircraft.

Remaining blockers include measured masses/material schedules, actual rotor
polars and duct/wake/edgewise/descent interactions, installed engine/transmission
ratings, actuator dynamics and supply capacity, CV/gear compliance, all-part
self-contact, laminate/gear failure allowables and deformable structural
behaviour. Present contact damage is an envelope strike and loss of intact
rotor aerodynamics, not material fracture. Collective pitch is a rate/lag-limited
aerodynamic state and rendered blade rotation: individual blade-pitch bearing
dynamics, pitch-servo work and pitch-dependent blade inertia are not resolved.
Engine internal rotors, vertical shaft rotation and air/exhaust reaction loads
are also unresolved. These limitations prevent a claim
that the real VTX has been validated or that every original engineering
requirement is complete. No controlled A-to-B landing has been achieved.

The subsequent low-fuel/power revision and actual local-return test are recorded
in `PROPULSION_FUEL_REVISION.md`; they do not retroactively change these runs.

The pilot's four observed lessons are in `pilot/colin-memory.json`, with flight
checkpoint copies and a transfer manifest. They are explicit learned experience,
not pretrained VTX control weights. No unfamiliar Stage 2 world has been built
or accessed.
