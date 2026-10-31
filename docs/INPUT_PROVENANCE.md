# Input register and provenance — 31 October 2026

| Parameter or component | Value | Basis | Ready for 6-DOF VTX simulation? |
|---|---:|---|---|
| Four rotor centre XY coordinates | (±2.6, 0), (0, ±2.6) m | P0-V4 geometry | Positions only; rotor plane must be checked against CG |
| Four nominal disk areas | 4 m² each | P0-V4 geometry target | Nominal geometric disk, not measured thrust map |
| Nominal rotor shaft rate | 800 rpm | Conceptual drivetrain target | No RPM control/map or inertia validated |
| P0-V4 empty mass | 843 kg | Allocation budget | **NO** — neither actual weighing nor CAD material volume audit |
| Crew allowance | 170 kg combined | Scenario budget | **NO** — occupant positions/inertia not defined |
| Test/full fuel allowance | 60 / 110 kg | Scenario budget | **NO** — actual CG and usable capacity as fuel moves unknown |
| Four fuel pod gross/usable | 195.43 L / 166.12 L (85% assumed) | P0-V4 geometry/screen | No baffle, feed, CG slosh or certification data |
| Maximum nacelle tilt | 20° | Preliminary design envelope | No rated actuator mechanism |
| Passenger-friendly target | 0.8 m/s² and 0.4 m/s³ | Reference design limits | Scenario condition, not measured VTX handling |
| Centre of gravity | UNKNOWN | Needs mass register + system ID | **NO** |
| Inertia tensor | UNKNOWN | Needs full mass model + validation | **NO** |
| Rotor thrust / torque / inflow maps | UNKNOWN | Needs aerodynamic characterization | **NO** |
| Rotor shaft gyro & aero coupling | UNKNOWN | Needs rotor properties | **NO** |
| Flight computer integration | Candidate only | Veronte/IMU research | **NO** |
| Actuator closed-loop response | UNKNOWN | Needs identified actuator and tests | **NO** |

**Exact model reference**: https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=3288318a-95f4-4dda-8d0f-dbf7b8eaceb9&version=version_f01d449a46712dd351275c360854de71baa3a13bb6ca61c1707a0593d7c7dea2

**Research leads, not aircraft qualification:**
- Hine et al., eVTOL liftfan (2025): https://doi.org/10.1115/1.4067673
- Hu et al., ducted propeller hovering efficiency/weight (2021): https://doi.org/10.1016/j.ast.2021.106937
- Akturk & Camci, ducted-fan tip clearance (2014): https://doi.org/10.1115/1.4023469
- Critchfield & Ning, multidisciplinary propulsion optimisation (2026): https://doi.org/10.2514/1.C038445

P0-V1 technical and costing source PDFs are included as historical research; design values superseded by P0-V4 must not silently replace current geometry measurements.
