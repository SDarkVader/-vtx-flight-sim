# VTX-P0-V4 — Colin engineering source handoff

Repository: https://github.com/SDarkVader/-vtx-flight-sim
Current Blendstra model: https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2

## Contents and limits

- `starter/vtx-flight-sim-map-missions.zip`: source and existing numerical/mission-selection tests (reported 31 passing LOCALLY before handoff). It is an earlier snapshot of the brief: do NOT overwrite the newer GitHub `COLIN_MISSION.md`, `COLIN_FIRST_TASK.md`, README or docs/ contracts with older copies. Import source/tests/configuration selectively and verify against main.
- `engineering/VTX_P0_V1_Technical_Performance.pdf`, `engineering/VTX_P0_V1_Parts_Cost_RnD.pdf`, and `engineering/VTX_P0_V1_Engineering_Blueprints.pptx`: authentic historical *P0-V1* concept references. These are not the P0-V4 configuration and their 671 kg empty target is superseded by P0-V4 843 kg allocation.
- `engineering/VTX_P0_V4_Physics_Model.py` and `engineering/VTX_P0_V4_Required_Inputs.json`: earlier conceptual physics inputs/source, not a flight-tested or calibrated physical plant.
- `engineering/VTX_urban_reference_simulation.py` and `engineering/VTX_urban_reference_results.json`: reference urban-trajectory analyses, NOT the path Colin must fly. Treat as comparative calculations, not an executable autopilot or flight replay.
- `engineering/VTX_P0_V5_Independent_Rotor_Control_Screen.csv`: later illustrative rotor control screen, not calibrated.
- `SHA256SUMS.txt`: hash provenance for every packed file.

## What Colin should do

1. Load the bundle files into the GitHub repository without overwriting the current authoritative contracts. Preserve source attribution and original PDFs.
2. Read mandatory GitHub `docs/PHYSICS_AND_RESEARCH_BASELINE.md` and `docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md`.
3. Open the exact P0-V4 Blendstra source; compare its actual assembly with the historical PDFs and use traceable geometry, mass allocation, inertia, gravity and rotor gyroscopic physics, without invented thrust/CG/structural parameters.
4. Build the mechanical aircraft, a physically interactive 3D world and a live fly-by-wire control interface. Pilot aircraft through repeated real-time observation/action, not a pre-scripted trajectory or replay. Crashes are valid results.
5. The user chooses any valid departure and destination. Preserve Colin's experiential learning for a later unknown second environment; don't prebuild that environment.

## Engineering caution

No material in this archive certifies airworthiness, rotor performance, mass properties, controller stability or actuator sizing. The starter tests verify limited numerical/reference and map-selection behavior, not a complete mass-bearing six-degree-of-freedom flight simulation.
