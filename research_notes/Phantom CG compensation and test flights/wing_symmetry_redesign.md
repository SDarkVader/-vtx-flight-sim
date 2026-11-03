# Wing symmetry redesign: A10 split-level cassette

The full write-up is in `docs/phantom/A10_WING_SYMMETRY_REVISION.md`.

**Problem.** In A9 the two deployed wings sit at different heights: the right chord plane is at z 1.0015 m and the left at 0.879 m, a 118 mm difference.

**Chosen option: (e), the split-level cassette.**
- Both panels ride in one upper level and stop short of the centreline, with stroke 1.205 m.
- Half-chord tongues run side by side in fore/aft channels in a lower level, split by a divider spar.
- The A9 0.94 m lock couple and tongue are kept, with four tongue-carried pins per wing.

**Rejected options.**
- (a) The hatch cannot be stowed, and the two sides are coupled.
- (b) Heavier, with a 0.60 m couple and a mid-span joint.
- (c) Needs about 1.65 m of bay length; 1.06 m is available.
- (d) Pin forces of 262–497 kN.

| Item | Result | Basis |
|---|---|---|
| Height residual | 0.0 mm (A9: 118 mm), common z 0.9873 | MEASURED-K |
| Incidence difference / twist | Δi 0.0°; twist −0.0353° on both sides | MEASURED-K |
| Span / S_ref / S_exp / AR | 4.858 m / 3.934 m² / 1.4445 m² / 6.00 | DERIVED |
| V_S1 | 66.4 m/s (A9: 65.4) | DERIVED |
| Max pin force, ultimate | 51.2 kN (A9: 54.3) | DERIVED |
| Divider spar pin loads | 50.3 / 17.7 kN | DERIVED |
| Flutter | 665 m/s EAS against 268 required | SYNTHETIC_UNVALIDATED |
| Slide body mass, R / L | 27.03 / 27.03 kg | DERIVED |
| Bay mass change | +9.01 kg | DERIVED |
| CG change | Δx +19.9 mm, Δz −17.0 mm (y unchanged) | DERIVED |
| Clearance sweep | 0 collisions involving A10 parts; minimum gap 0.7 mm | MEASURED-K, kinematic only |
| MuJoCo | All 28 joints reach both limits | MEASURED-K |

**CG-study requirements.** All five are met. Root stiffness and incidence under 1 g are matched by mirror-identical construction (DERIVED). Neither has been checked by FEA.

**Follow-up.** Rerun the ballast and nose-battery sizing for +9.0 kg at the new CG.

**Files.**
- Builder: `tools/phantom/build_a10_cassette.py`
- Model: `assets/derived/phantom-a10-cassette.{blend,glb}`
- Evidence: `evidence/phantom/a10_*`, `wing_loads_results.json`
- Media: `evidence/phantom/media/a10_*`
