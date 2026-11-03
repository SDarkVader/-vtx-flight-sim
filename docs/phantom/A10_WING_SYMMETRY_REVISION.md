# VTX Phantom A10: common-height wings (split-level telescopic cassette)

**Status:** built, kinematically verified, loads re-screened. No FEA, CFD, aeroelastic model or flight test. Blender sweeps prove geometric fit through the motion only; loads are closed-form screening (`engineering/phantom/wing_loads.py`, case `A10_split_level`).

**Labels:** MEASURED-K (measured from the CAD by script), DERIVED (closed-form calculation from labelled inputs), SYNTHETIC_UNVALIDATED (declared assumption with bounds), MANUFACTURER, REGULATORY_REFERENCE (CS-23 pattern used as design practice, not a compliance claim).

## 1. Problem

A9 stows its two telescopic wings stacked: right wing in the upper sleeve cell, left in the lower. Each stowed wing spans almost the whole sleeve width, so it lies over the other wing's tongue, and the stack has to be preserved all the way to the deployed position. Measured at frame 240 (`evidence/phantom/a10_compare_a9_wing_heights.json`, MEASURED-K): right chord plane z 0.9873 m, left 0.8693 m, **stagger 118.0 mm**. The owner called this a severe problem.

The CG study (`research_notes/Phantom CG compensation and test flights/cg_and_compensation.md` §4) set the A10 requirements:

| Requirement | Limit |
| --- | --- |
| Residual left/right height difference | ≤ 10 mm |
| Incidence match incl. root fit; twist under 1 g | ≤ 0.05° |
| Root bending stiffness match | ≤ 5% |
| Mass match per side | ≤ 0.2 kg |
| Common wing height | z 0.94–1.00 m |

## 2. Why A9 had to stagger

Stowed, the right wing occupies y −1.189…+1.225 (tongue −1.189…−0.139, panel −0.139…+1.225); the left mirrors it. In plan view the two wings overlap across |y| < 1.19, and that overlap only ends in the last 0.18 m of the 1.37 m stroke. Any arrangement in which two rigid single-stage wings cross the centreline therefore needs them on different levels wherever they overlap. The panels themselves, however, overlap only in the centre |y| < 0.139. **It is the tongues that cross the other wing.** That observation drives the chosen option.

## 3. Options (numbers per side unless stated; A9 reference: S_ref 4.06 m², span 5.19 m, couple 0.94 m, 54.3 kN ultimate pin force)

| | (a) End-of-stroke vertical shift | (b) Per-side two-stage telescopic | (c) Fore/aft tandem cells | (d) Swing/fold (Stage 1 A/R) | **(e) Split-level: coplanar panels, side-by-side tongues (chosen)** |
| --- | --- | --- | --- | --- | --- |
| Principle | A9 kept; after full stroke each wing drops/rises 59 mm on ramps to z 0.9405; mid-plate removed | each side its own cassette; outer stage nests in inner stage (MAK-10/MAK-123 precedent) | both cells at one height, one in front of the other | wing rotates about a pin into the deck | panels share one level and never cross the centreline; only the tongues cross, side by side in fore/aft channels below |
| Residual height | 0 by design (shift-stop tolerance) | 0 | 0, but **x-stagger 0.82 m** | 0 | **0.0 mm MEASURED-K** |
| Span / S_ref | 5.19 m / 4.06 m² | ≈ 5.4 m / exposed 0.82 m² (stepped planform), DERIVED | fails at full chord: needs 2 × 0.80 m + 3 walls ≈ 1.65 m of bay; 1.06 m available (seat back x −0.62 to fin root −1.675). At 0.5 m chord S_exp −37% | 6.2 m / 5.3 m² (A8) | **4.86 m / 3.93 m²** (−6.4% / −3.0%), DERIVED |
| Root couple / ultimate pin force | 0.94 m / 54 kN | 0.60 m root + 0.42 m mid-span joint / ≈ 63 kN root, plus a second lock set outside the hull, DERIVED | 0.94 m (if it fitted) | 0.079–0.16 m depth couple / 262–497 kN (Stage 1) | **0.94 m / 51.2 kN**, DERIVED |
| Mass vs A9 | ≈ +5 kg (ramps, shift EMAs, slot shutters), SYNTHETIC | ≈ +8–10 kg/side (inner-stage tube, second lock set and drive), SYNTHETIC | — | — | see §6 (MEASURED-K from parts) |
| Actuation | slide as A9 + shift ≈ 0.75 kN, 59 mm, ≈ 30 W; +2 s | 2 drives per side, sequenced | — | 1 rotary + lock | slide 164 N, 40 W, 1.2 m in 5 s (DERIVED) |
| Slot / hatch | slot grows 0.088 → 0.16 m. A 0.16 m door has no stowage room: 0.03 m of flank above the right slot; below the left slot it hits the rear-tyre rotation sweep. Needs 2–3 closures per side | single-height slot, clamshell doors | — | ≈ 1.4 m side slot | **A9 right-door design on both sides, unchanged size** |
| Failure modes | a jam on one side blocks the other's shift (they overlap until both are out), so asymmetric stagger returns | 2× the locks and drives; mid-span joint exposed; flaps limited by the nested stage | CG/AC shift; left/right AC split in x | load path | as A9 (slide jam, pin not home); sides independent |
| Load path | as A9 | root couple −36%; mid-span joint in a 0.096 m section | — | depth-limited, infeasible | as A9: tongue → pins → walls/divider spar → box → posts → sills |

**Decision: (e).** It is the only option that gives a common height *by construction* and keeps A9's 0.94 m couple, tongue, lock pins and slot/door size, without adding a degree of freedom. It also makes left and right mechanically independent and mirror-identical in mass and stiffness. Its cost is span: panels cannot cross the centreline, so stroke ≤ 1.205 m and exposed span 1.198 m (A9 1.364 m). The tip chord grows from 0.32 to 0.42 m to keep area: S_exp falls 5.5% and S_ref 3.0%. Induced drag at equal lift rises roughly with (5.19/4.86)² ≈ +14% (DERIVED). V_S1 rises 65.4 → 66.4 m/s. (a) keeps the span but fails on hatch packaging and couples the two sides; (b) works but is heavier, with a lower root couple and a second exposed joint.

## 4. A10 design (`tools/phantom/build_a10_cassette.py`)

The builder imports A9 (`A9_IMPORT_ONLY=1`) and overrides only what A10 changes. A9 files are never written.

- **Upper level** (z 0.948–1.051, the A9 upper cell): both panels. Stroke 1.205 m; stowed roots at |y| 0.026, so neither panel crosses the centreline.
- **Lower level** (z 0.830–0.944): half-chord tongues, each 1.05 m × 0.394 m × 0.095 m. They run side by side in fore/aft channels split by a divider spar at x −1.0555; the right tongue is in the front channel, the left in the rear. A Ti root joggle frame joins each panel to its tongue.
- **Locks:** four tongue-carried pins per wing, at |y| 1.17 and 0.24, a 0.94 m couple (as A9). Pin-pair separation is 0.41 m. The right wing pins into the front wall and the divider, the left into the divider and the rear wall, so the layout is identical on both sides.
- **Drive and guides:** a rotating-nut ball screw on each tongue runs on a stationary 20 mm screw anchored in the mouth flanges. Each tongue has PTFE shoes on Ti floor rails, flanged pin bushings and inboard elastomer stops.
- **Hatches:** both use the A9 right-door design, hinged at z 0.9405 and flipping 180° outward.
- **Support posts:** x −0.70, −1.0555 and −1.30, with top and base fittings and Ti diagonal braces.
- **Planform:** tip chord 0.42 m, tip at y 2.429 m, x_le_tip −1.04, straight trailing edge at −1.46.
- **Timeline:** unchanged from A9 (reference frame 240, stowed frame 1, end 530).

## 5. Measured geometry (MEASURED-K, `evidence/phantom/a10_wing_heights.json`)

| | A9 | A10 |
|---|---:|---:|
| Chord-plane z, right / left (m) | 1.0015 / 0.879 | 0.98733 / 0.98733 |
| Height residual | 118.0 mm | 0.0 mm |
| Incidence difference (geometric) | — | 0.0° |
| Twist, root to tip (both sides) | — | −0.0353° |

The comparison is in `a10_compare_a9_wing_heights.json`.

## 6. Clearance sweep (MEASURED-K, kinematic only; `a10_sweep.json`, `a10_sweep_summary.md`)

The sweep covers 178 frames at 10 mm sampling. **No collision involves an A10 moving part.** All 32 flagged pairs are pre-existing A8–A8 pairs (legs and wheels).

Minimum clearances:

| Part | Minimum clearance (mm) |
|---|---:|
| Panels | 0.7 |
| Aileron | 0.8 |
| Flap | 0.9 |
| Root plate, shoes | 1.0 |
| Pins, nut, tongue, joggle | 1.5 |
| Doors | 1.5 |
| Canard | 1.7 |

These gaps are CAD-nominal and include no tolerance stack or deflection.

Static residuals:
- **Carried over from A9:**
  - canard root pod vs nose panel (36 triangle pairs);
  - ducts vs booster fairings (6 and 4 pairs).
- **New in A10:** carry-through box vs `A10_SLEEVE_R_FLOOR_RAIL_0` (9 pairs). The rail is bonded to the box floor, so this is a modelled bonded joint, not an interference.

## 7. Loads (DERIVED / SYNTHETIC_UNVALIDATED, `wing_loads.py` case `A10_split_level`)

| | A9 | A10 |
|---|---:|---:|
| S_ref (m²) / span (m) / AR | 4.055 / 5.19 / 6.64 | 3.934 / 4.858 / 6.00 |
| S_exp, both wings (m²) | 1.512 | 1.4445 |
| V_S1 (m/s) | 65.4 | 66.4 |
| Root Mx, ultimate × fitting factor (kN·m) | 36.7 | 33.0 |
| Root V, ultimate × fitting factor (kN) | 65.0 | 65.1 |
| Max pin force (kN) | 54.3 | 51.2 |
| Station force, outboard / inboard (kN) | 104.5 / 39.5 | 100.5 / 35.5 |
| Sleeve facesheet stress (MPa) / buckling margin | 179 / +0.64 | 172 / +0.70 |
| Flutter (m/s EAS; 268 required) | 677 | 665 |
| Bending / torsion frequency (Hz) | 30.6 / 146.5 | 39.5 / 142.3 |
| Aileron reversal / divergence (m/s) | 716 / 781 | 779 / 849 |
| Wing structure mass, both (kg) | 17.44 | 15.61 |
| Slide force / power | 182 N / 50 W | 164 N / 40 W |
| Roll rate at V_A (°/s) | 317 | 351 |

**Tongue:** caps 2.67 mm, webs 4.4 mm, 7.8 kg.

**Divider spar** (new): pin loads 50.3 / 17.7 kN, bending 7.0 kN·m, cap 6.2 mm × 30 mm, web 3.7 mm.

**Root stiffness:** identical left and right by construction (same couple, pair separation and pin and bushing parts). It is not an FEA value.

## 8. Mass and CG (DERIVED from the two handover JSONs)

| | A9 | A10 | Δ |
|---|---:|---:|---:|
| Slide body, R / L (kg) | 20.74 / 20.74 | 27.03 / 27.03 | +6.29 each; L−R = 0.00 |
| Articulated mass, total (kg) | 62.97 | 75.55 | +12.58 |
| Bay total, cassette + chassis (kg) | 140.45 | 149.46 | **+9.01** |
| CG, deployed (x, y, z in m) | (−0.6547, 0.001, 0.9217) | (−0.6348, 0.000, 0.9047) | Δx +19.9 mm, Δz −17.0 mm |
| CG shift, stowed → deployed | 0.2 mm | 1.5 mm x, 1.3 mm z | — |

- **Mass sources:** articulated mass rose because the tongue, joggle, pins, nut and motor now ride on each wing. Fixed structure fell by 3.57 kg (77.48 → 73.91 kg).
- **COM x offset:** the two wing COMs differ in x by 0.235 m because of the fore/aft tongue channels. That gives a small Ixy term, but no lateral CG offset.
- **Ballast:** the CG study's ballast and nose-battery sizing must be rerun against these numbers.

## 9. Requirement compliance (CG study)

| Requirement | A10 | Status |
|---|---|---|
| Height residual ≤ 10 mm | 0.0 mm | MET (MEASURED-K) |
| Incidence and twist matched within 0.05° under 1 g | Geometric: Δi 0.0°, twist equal on both sides. Under 1 g, Δ ≈ 0 because the structure is mirror-identical | MET geometrically (MEASURED-K); 1 g value DERIVED, not FEA |
| Root stiffness matched within 5% | Identical by construction | MET (DERIVED) |
| Mass matched within 0.2 kg per side | 27.03 / 27.03 kg | MET (DERIVED) |
| Common z 0.94–1.00 | 0.9873 | MET (MEASURED-K) |
| 0 moving collisions | 0 | MET (MEASURED-K, kinematic) |

## 10. Not validated

The following have not been validated:
- **Structures:** no FEA of the tongue, joggle, divider spar, pins or bushings. Stresses are beam sizing on stand-in allowables.
- **Aerodynamics:** no CFD. The aerodynamics are strip and DERIVED, and the section is a stand-in.
- **Aeroelasticity:** flutter, divergence and reversal come from the simplified models in `wing_loads.py`.
- **Actuators:** ball-screw, motor and EMA authority are not taken from a datasheet. Stall force (2500 N) is carried over from A9 as a SYNTHETIC value.
- **Tolerances:** clearances are nominal CAD values with no tolerance stack or thermal analysis.
- **Stiffness under load:** incidence under 1 g is inferred from symmetry, not computed.

## 11. Reproduce

```
blender -b --python tools/phantom/build_a10_cassette.py -- assets/derived/phantom-a10-cassette.blend assets/derived/phantom-a10-cassette.glb
blender -b assets/derived/phantom-a10-cassette.blend --python tools/phantom/measure_wing_heights.py
blender -b assets/derived/phantom-a10-cassette.blend --python tools/phantom/export_handover.py
python tools/phantom/mujoco_articulation_check.py --rev a10
python engineering/phantom/wing_loads.py
blender -b assets/derived/phantom-a10-cassette.blend --python tools/phantom/change_register.py -- <ABSOLUTE path to phantom-a9-cassette.blend> evidence/phantom/a10_change_register.json
```

The change register lists 10 roles removed, 54 added and 38 changed relative to A9.
