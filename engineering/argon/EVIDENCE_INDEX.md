# VTX engineering — source and flight evidence index

This is a map to existing sources. Work from the actual files, not from this summary alone.

## Current source/control contracts (merged PR #4)

- `docs/PHYSICS_AND_RESEARCH_BASELINE.md` — mandatory mass-bearing aircraft, Newton–Euler, full inertia, fuel and physical tests.
- `docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md` — pilot must fly via actual live commands and state observations.
- `src/vtx/aircraft.py` — authoritative MuJoCo model, linked rotor speeds, proportional/PI local controls, tank bodies, actuator limits and fuel consumption.
- `src/vtx/aero.py` — provisional blade-element thrust, inflow and power model.
- `src/vtx/governor.py` — common shaft local PI regulator, no aircraft stabilisation.
- `src/vtx/training_assist.py` — experimental collective damping suggestion, **not applied** in production live aircraft.
- `tools/fan_ecu_shadow.py` — advisory-only cowling/speed screen.
- `tools/build_airframe.py` — assembly repair, source transform, body-geometry and mass-ledger derivation.
- `tests/test_multibody.py`, `tests/test_physics.py`, `tests/test_training_assist.py` and `tests/test_variable_drive_bench.py` — existing regression families.

## Engineering records (existing)

- `evidence/EXPERIMENT_REPORT.md`: R4/R5 mass reduction, first flights, sampled tilt clearance, unresolved physical validation.
- `evidence/PROPULSION_FUEL_REVISION.md`: 10 kg fuel run and shaft PI governor, conditional power/hover screening, exhaust unknowns.
- `evidence/FLIGHT_173518_SETTINGS.md`: manual trim and failed roll corrections, observed forces and actuation lag.
- `evidence/FAN_COWLING_ECU_CONCEPT.md`: desired sensor/actuator linkage, 20-degree resultant cone, controller boundaries.
- `evidence/TRAINING_ASSIST_RESEARCH_TEST.md`: synthetic damping study; higher assistance did NOT improve the tested pitch response.
- `evidence/FOUR_FAN_VARIABLE_TRANSMISSION_CONCEPT.md`: common shaft, four separate planetary variators, large ring-power option, kinematic corrections.
- `evidence/TRANSMISSION_HIGHER_BUDGET_OPTION.md`: proposed 4,800 rpm sun/near-zero ring nominal-speed architecture.
- `evidence/VARIABLE_DRIVE_BENCH_TEST.md`, `evidence/variable_drive_bench_results.json`: reproducible **arithmetic bench**, not tested transmission or flight.
- `evidence/TRANSMISSION_STRUCTURAL_SCREEN.md`: gear phasing, torsion assumptions, critical excitation and motor comparison.
- `evidence/FULL_ROTATION_SCREEN.md`, `evidence/full_rotation_clearance.json`: exploratory housing intersection (end-over-end) study, NOT current selected movement.
- `evidence/source/assembly_repairs.json`: proposed source-zero-transform shaft/actuator repairs and exact object IDs.
- `evidence/source/airframe_ledger.json`, `evidence/source/airframe_ledger_r4.json`: provisional mass geometry and full inertia.
- `evidence/underside_trade.json`: full-tensor independent Wolfram comparison, R4 vs R5.
- `evidence/clearance_audit.json`: 6,912 sampled poses and zero detected collisions for studied R5 configurations; not a continuous swept-volume proof.
- `evidence/flight-comparison-20261031T094649.json`: controlled-source-condition comparison with different pilot action schedules.
- `evidence/source/shaft_stored_evidence.json`: pins the original source assembly and one misplaced shaft source object.

## Historical numeric anchors (ALLOCATIONS and conditional models)

- R5 empty allocation **816.66895 kg**; +170 kg occupants +10 kg fuel => **996.66895 kg**.
- Gravity 9.80665 m/s² => **9,773.98 N** weight for that load and ideal equal hover share **2,443.50 N/fan**.
- Four rotor axis stations at radius ~2.60 m; nacelle pivots ~z=2.03 m; rotor planes ~z=2.31 m.
- R5 60 kg fuel test total **1,046.66895 kg**; old R4 60 kg fuel test total **1,079.38910 kg**.
- Provisional rotor spin inertia **~3.332575 kg·m² each**, not measured blade hardware.
- 10 kg mission / 16 m² ideal disk area / density 1.225 kg/m³ => momentum-theory ideal hover induced-power lower bound **~154.33 kW**.
- Prior synthetic polar hover estimate **~202.82 kW shaft** before actuator power at 10 kg fuel.
- Reference rotor 1,200 rpm; **300 kW** configurable test shaft ceiling; **469.8 kW** historical upper reference, not certified installed rating.
- Tank planning: four diagonal protected fuel cells, ~195.43 L combined gross volume, estimated 85% usable ~166.12 L and assumed 0.8 kg/L density. Actual plumbing, slosh and mounting not validated.
- 60 kg -> 10 kg fuel removed from low position raised CG z by ~18.66 mm in historical model; cannot infer general stability from vertical CG alone.
- Engine input example 6,016 rpm. Alternating rotor spin signs [+,-,+,-].
- Prior source variant samples 6,912 clearance poses, but full continuous swept collision and strength remain open.
- Physics model PR #4 sortie metadata identifies MuJoCo **3.17.0**, integrator dt=0.0025 s (400 Hz), 100 Hz aero, 20 Hz sensor sampling, provisional 20 ms simulated transport, 5 s action lease; these are *recorded run settings* not universal hardware requirements.

## Flight and validation history

- `20261031T060411-29e1d6`: 800 rpm, no takeoff.
- `20261031T071731-4e6434`: airborne, failed to achieve settled landing; recorded roll corrections and server shutdown.
- `20261031T081204-ce4792`: 18 decisions, near-A local touchdown, max origin height 0.9085 m, B not reached; NOT full mission success.
- `20261031T094649-bda3b7`: 71 decisions, max origin height 10.9701 m, collision, peak sampled inclination 38.45 degrees.
- `20261031T173518-46b6e2`: roll growth despite opposing trim requests. Recorded F1–F4 forces near one sample ~2469/2522/2469/2416 N. Contact, dynamics and lag are not isolated.
- PR #4 adds `evidence/flights/20261101T200514-6e7e11/`, `...T200529-75b3f1/` and `...T201531-c2c85d/`. Inspect exact primary events/metadata and available summaries: the first is explicitly **no takeoff** (0 decisions), despite its touchdown-labelled reason; the latter two have metadata but no verified full summary here. Do not promote sortie name or UI label to evidence of landing. Recorded requests show 20 kg fuel, 1,200 rpm, 300 kW and assistance 0.8, which does not mean active damping; previous provenance records assistance as shadow-only.

## Saved model versions

- Original spherical 4-fan P0-V4 master project `3288318a-95f4-4dda-8d0f-dbf7b8eaceb9` exact version `version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2`; artifact sha256 `2db9abd64ba9b7078e6e539ba4c6b9177e58e335a085a8ea213b5ffa6e987e35`.
- R5 triangulated undercarriage project `4e7f325a-905f-4fc0-b582-1aa0ecd6b11c`; version `version_f714283b5dcb36a68e5f8111df22739b53e6e9ef72d3619294c14feca5d5eb04`.
- Four-branch planetary schematic project `3955fbf5-0baa-45f9-8d8f-07b9d82ace01`; version `version_073a2c1b30d6ce06f490d16f91619e32f27109b4bfd1aef19c70169e44e60c8e`.
- Nominal-motion planetary demo project `57fa3690-f5bd-44cf-90c9-d4f22c02f24e`; version `version_de1642bda77e3639e100b7e74e5920df73ebcccf1733132ee4babd98f34c87a9`.

Model parts are source geometry, not automatically fitted geartrains, measured masses, validated stress allowables or physical flightworthiness. Keep a provenance ledger.

## Task 01 derived assets and engineering evidence (`P0-V4A-assembly-r6`)

- `engineering/argon/TASK_01_REPORT.md` — complete Task 01 engineering report covering transmission positioning, `z = 1.980 m` gimbal pivot alignment, `z = 0.945 m` diagonal fuel-tank arrangement, candidate variable-ratio transmission envelope (`+149.0 kg ± 4.69 kg RSS`), 3D BVH clearance matrix, symmetric/asymmetric fuel mass/CG/full 3×3 inertia audit, NASA SP-106 slosh bounds, hover power (`1,200 rpm` vs `800 rpm`), 6-DOF wrench controllability, and open qualification blockers.
- `evidence/source/airframe_ledger_r6.json` — derived mass, 3-D centroid, full 3×3 inertia, nacelle pivot (`z = 1.980 m`), and fuel tank (`z = 0.945 m`) ledger for `P0-V4A-assembly-r6` (731 mapped parts, `816.66895 kg` empty allocation).
- `evidence/source/assembly_repairs_r6.json` — complete `before_world_matrix` and `after_world_matrix` provenance for all 731 source CAD objects in `P0-V4A-assembly-r6`.
- `public/assets/airframe-r6.glb` and `assets/derived/p0-v4-r6.blend` — derived visual GLB and Blender scene for `P0-V4A-assembly-r6` (`assets/source/p0-v4.blend` and `public/assets/airframe-live.glb` untouched).
- `tools/check_r6_clearance.py` and `evidence/r6_clearance_audit.json` — 3D BVH collision and clearance audit proving `0` static key-pair overlaps (`21` failing pairs in `R5` -> `0` in `R6`), `0` overlaps across the full $360^\circ \times 20^\circ$ nacelle tilt cone sweep on all four fans (`min_clearance_mm = 14.52 mm`), `0` overlaps across all 6 landing gear legs (`0..0.25 m` stroke), and `0` overlaps for the 12 candidate variable-ratio transmission components.
- `tools/argon_task01_study.py` and `evidence/argon_task01_transmission_tanks.json` — full analytical + MuJoCo mass, 3-D CG, symmetric 3×3 inertia, fuel slosh, hover power, wrench controllability, and dynamic ground-settle / open-loop spool comparison across `R4`, `R5`, `R6`, and `R6 + Variator`.
- `tests/test_argon_task01.py` — automated pytest regression suite for Task 01 (`98 passed` across full repository test suite).
