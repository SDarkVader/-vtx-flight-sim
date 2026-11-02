# VTX Phantom A9: telescopic wing cassette, flaps, ailerons and two-axis canards

**Milestone status:** first deliverable built and kinematically verified. The Blendstra revision, verified results, assumptions register and MuJoCo handover are all included.

**What has not been done:** no FEA, CFD, coupled aeroelastic analysis or flight test. The Blender sweeps prove geometric fit through the motion only. The loads come from closed-form screening in `engineering/phantom/wing_loads.py`, and the stage-1 basis is in [WING_CASSETTE_STUDY.md](WING_CASSETTE_STUDY.md).

## 1. Revision and preservation

| Item | Value |
| --- | --- |
| Base | Blendstra A8 `version_a5589426…` (SHA-256 `ae22a71a…`), unchanged |
| Build | `tools/phantom/build_a9_cassette.py`: one deterministic script, run locally (Blender 5.2.3) and as the Blendstra revision (Blender 4.5.3) |
| Local A9 file | `assets/derived/phantom-a9-cassette.blend` (gitignored: derived from a private source; public repo) |
| Blendstra A9 version | **not yet submitted.** The build script is ready (53 KB, within the 61 KB inline limit) but runs on Blendstra's hosted Blender 4.5.3, which hasn't been verified; local verification used Blender 5.2.3. |
| A8 parts retired | 27: the A8 wing plates, vertical-pin hinges, root fairings, bearing blocks, flush covers, `MOUNT_001` carry-through, canard blades/hinges/clevises, shoulder-inlet curves |
| A8 parts changed | 38 (full list in `evidence/phantom/a9_change_register.json`); originally 32: hull (shoulder union, root-profile slots, cassette cavity, duct tunnels); rear quarter glass and gasket trimmed aft of x −0.613; fenders, aft fairings, fender ridges, side blades, tub roof longerons and rear shear walls trimmed by the bay; fins shortened 22% in x and moved aft; forward dorsal removed; wheel-pod and leg keys retimed |

## 2. What was built

- **Cassette:** a twin-cell CFRP sandwich sleeve (1.5/12/1.5 mm) spanning \|y\| ≤ 1.238 behind the seats (x −0.62…−1.49, z 0.815…1.066). It *is* the wing carry-through box, replacing `MOUNT_001`, which intersected the seats. It sits on four Ti posts on the torsion sills at \|y\| 0.62, and its front wall takes the trimmed roof longerons. The +Y wing runs in the upper cell, the −Y wing in the lower.
- **Wings:**
  - NACA 2411→2410 stand-in sections;
  - root chord 0.80 m, tip 0.32 m, exposed span 1.35 m per side, overall span 5.19 m, S_ref 4.06 m²;
  - leading-edge sweep 19.6° with a straight trailing edge, so every outboard section fits inside the root profile and can pass the slot.
  - A **1.05 m full-chord tongue** stays in the sleeve when deployed, and a Ti **root stop/seal plate** seats on the **mouth flange**, which is the outboard hard stop.
- **Locks:** four Ø32 mm PH13‑8Mo pins per wing at two stations, \|y\| 1.17 and 0.24 (0.94 m apart). Front pins are driven from inside the tongue into front-wall bushings; rear pins from sleeve-mounted EMAs. Bending reaches the sleeve as a vertical couple between the stations. The slide rollers and drive carry no flight load.
- **Drive:** a ball screw behind the rear wall with a nut-carriage arm through a rear-wall slot. Stroke 1.37 m, 5 s.
- **Hatches:** one flush door per side, hinged along X at z 0.9405. It covers the root-profile slot when stowed and flips 180° to lie on the blank cell face when deployed; the root plate then fills the slot.
- **Control surfaces:** independent flaps (η 0.05–0.50) and ailerons (η 0.55–0.95), c_f/c 0.28. Each has a nose arc concentric with its hinge, so the gap stays constant at any deflection, a rotary EMA in an under-wing fairing that stays inside the root profile, and an amber trailing-edge accent on the aileron.
- **Canards:** all-moving NACA 0009 blades, 0.278 m² each. Each sits on a Ti spindle (OD 43 mm) in an angular fold yoke carrying the spindle bearings and pitch EMA (−20/+25°).
  - The yoke turns on a vertical fold pin at (1.95, ±1.20) seated in a **faceted root pod** on the front-fender corner, with spherical plain bearings at z 0.80 and 0.91.
  - The pod is the node of a **Ti A-frame**: two Ø30 mm struts run inside the fender to a bolted node bracket on top of the front wheel-pod reaction pylon. They are routed outside that wheel's rotation sweep and clear of the radiator ram inlet; measured minimum tyre clearance 26.7 mm.
  - Deployed span is \|y\| 1.26–1.84 ahead of the front wheel. Stowed, the blade folds 90° aft and lies over the front fender.
- **Body:** a faceted cassette haunch around the sleeves.
  - A central spine continues the canopy line (z 1.165 → 1.105).
  - Twin haunch crests rise aft (z 1.11 → 1.135) to the raked fins, which are shortened and moved aft. Each crest carries an amber crease line.
  - Forward-raked blades run behind each door, and the haunch tapers into the tail at x −2.12.
  - The flank sits at the fender line, \|y\| 1.245, and the underside is held at z ≥ 0.80 outboard of \|y\| 0.68, clear of the rear-wheel rotation sweep. The skin over the cassette cavity is at least 10 mm everywhere. Engine induction moves from the shoulder to inlets in the rear-fender front face, ducted under the sleeve to the A8 engine interface (2 × 0.0084 m²; mass flow not sized).
- **Sequence** (frames at 24 fps): road (1) → legs and pods to VTOL (30–80, A8) → hatches open (84–108) → canards unfold (96–132) → wings slide out (108–228) → pins lock (228–240) → flap/aileron/canard demonstration (246–318) → unlock, retract, close and fold (322–480) → pods and legs back to road (481–520).

## 3. Kinematic verification (MEASURED-K)

The sweep (`tools/phantom/sweep_clearance.py`) covered frames 1–530, sampling every 3rd frame (178 frames), on the final A9 file (`a9_sweep.json`, summary in `a9_sweep_summary.md`). It checked 70 moving parts, including the A8 wheel pods and legs, against every object, for each pair that involves an A9 part. Method:

- a BVH triangle-overlap screen;
- any flagged pair between closed solids is confirmed by sample-in-solid containment (both nearest-face normal and ray parity must agree);
- clearance is measured as the nearest distance from 10 mm surface samples.

Two measurement artifacts were found and fixed along the way; both are documented in the tool:

- stale frame-1 matrices in nested joints right after file load;
- orientation-dependent triangulation of faces wrapped round holes.

**Result: no moving part intersects anything at any sampled frame.**

| Moving part | Closest partner | Minimum clearance | Note |
| --- | --- | ---: | --- |
| Wing panel through the mouth-flange slot | sleeve / flange | 0.7 mm | the slot is the root profile + 3 mm; tight, so production tolerances need checking |
| Flap / aileron passing the slot (neutral) | flange | 0.9 / 0.8 mm | surfaces are interlocked at neutral during transit |
| Root seal/stop plate | flange | 1.0 mm | seated stop (seal compression) |
| Lock pins (8) | bushings / housing bores | 1.5 mm | radial bore clearance |
| Slide nut | ball screw | 1.5 mm | nut bore |
| Hatch doors | hull flank | 1.5 mm | both closed and flipped |
| Canard spindle | yoke bore | 1.7 mm | through ±20° pitch and 90° fold |
| Canard blade | yoke | 10 mm | — |
| Internal flap/aileron EMAs | slot | 7.9–8.4 mm | inside the wing, no external fairings |
| Rear legs (retracted) | sleeve bottom | 15 mm | — |
| Front tyres through 90° pod rotation | canard A-frame | 26.7 mm | node pads ≥ 18 mm outside the rotation envelope |
| Rear tyres through pod rotation | induction duct / haunch | ≥ 30 mm | haunch underside held at z ≥ 0.80 |

**Static residuals.** These involve only A8 *cosmetic* panels and nothing that moves:

- the right canard root pod still overlaps the A8 nose-to-wheel shoulder panel by 36 triangle pairs (the tunnel boolean is incomplete on that side);
- the induction duct's final bend overlaps the A8 booster-fairing panel by 4–6 triangle pairs, at most 5 mm deep.

They should be cleaned when the induction is sized and the nose panels are re-surfaced.

**Joint drive check (MuJoCo 3.17, `a9_mujoco_check.json`):** all 20 A9 joints reach both range limits under gravity, within the declared actuator caps.

## 4. Loads, structure and component sizing (DERIVED; see wing_loads.py, case `A9_cassette_build`)

| Quantity | Value |
| --- | --- |
| Envelope | +6/−3 g limit, ×1.5 ultimate; gusts don't govern (Pratt: 3.2 g at V_C, 1050 kg) |
| Speeds | V_S1 65 m/s, V_A 160 m/s, V_C 178.8 m/s, V_D 223.5 m/s (M 0.66) |
| Root ultimate × 1.15 fitting factor, conservative (no body lift) | V 65.0 kN, M_x 36.7 kN·m, torsion 3.2 kN·m |
| Lock-station forces (ultimate) | outboard 104 kN, inboard 40 kN; maximum pin-lug force 54 kN (min. shear Ø 6.2 mm; Ø32 hollow pin chosen for bearing, bending and wear) |
| Same loads through the A8 46 mm plate hinge | 831 kN per lug: infeasible |
| Wing box (root) | depth 79 mm, CFRP caps 4.0 mm, webs 2.8 mm; EI 3.7×10⁵ N·m², GJ 2.6×10⁵ N·m² |
| Mass per wing | panel 10.1 kg, tongue 7.4 kg, assembly with surfaces and pins 23.3 kg (Raymer statistical check: 12.6 kg metal panel) |
| Sleeve / carry-through | overhang moment 57.5 kN·m at the support; facesheet 179 MPa vs 210 MPa allowable (+17%); sandwich buckling 294 MPa (+64%). A 6 mm monolithic plate would **buckle** (−77%) |
| Flutter (typical section, validated against Hodges & Pierce 2.184 vs 2.17) | 677 m/s EAS vs 1.2 V_D = 268; reversal 716 m/s, divergence 781 m/s (screening only) |
| Roll (I_xx 660 kg·m², SYNTHETIC) | 317°/s at V_A, 232°/s at V_C, 141°/s at V_D; 90° of bank in 0.47–0.94 s. **The FCS must limit roll rate.** |
| Aileron / flap actuators | 72 / 60 N·m stall; 80 / 15°/s; stiffness ≥ 6.9 / 27 kN·m/rad |
| Canard | hinge moment 257 N·m nominal, 420 N·m stall; spindle OD ≥ 38 mm (43 mm fitted); 30 kN bearing load at ultimate |
| Cassette transit (q ≤ 600 Pa) | slide force 182 N, 50 W, 1.4 m in 6 s; roller reaction 1.5 kN; hatch latch 2.1 kN at V_D; stowed retention 1.5 kN at 9 g forward |

**Bearings:** the lock stations use pins in self-lubricating bushings (Ti‑6Al‑4V double-shear lugs). Spherical plain bearings aren't needed there: SKF GE 80 TXE‑2LS (C0 1900 kN) would have more than 30× static margin. Spherical plain bearings are recommended only for the canard fold pin. With 0.11 m between the pod-base and yoke bearings, the ultimate radial load is about 56 kN (4.8 kN·m / 0.11 m + 13 kN), well within an SKF GEH 50 TXE-2LS (C0 1160 kN); the A-frame then carries the pod loads into the wheel-pod pylon. Supplier selection is still open.

## 5. Interference with the systems that had to be kept

| System | Result |
| --- | --- |
| Two-seat safety cell | sleeve front wall 19.5 mm aft of the head restraints; the A8 carry-through intersection with the seats is removed |
| Four wheel-thrusters and legs | rear tyre top 0.78 m vs sleeve bottom 0.815 m; full pod rotation swept (section 3) |
| Twin rear propulsion units | unchanged; lock and slide drives sit above the reaction boxes |
| Engine induction | moved to the rear-fender front face; the shoulder inlets conflicted with the cassette. Routing is geometric; flow is unsized |
| Radiator, brake cooling, pressure-relief ducts | unchanged; the canard pylon and strut clear the front ducts (section 3) |
| Energy storage and electronics | the A8 under-floor battery bay is unchanged. The bay under the sleeve (x −0.63…−1.39, z 0.40…0.81, about 0.3 m³) is reserved for motor controllers, cooling and the generator interface |

## 6. Unverified-assumption register (additions to the stage-1 register U1–U12)

| # | Assumption | Value | Retire by |
| --- | --- | --- | --- |
| U13 | Sandwich sleeve allowables and joints | E 60 GPa facesheet, 3500 µε, 48 kg/m³ core | coupon tests, FEA of the box with real supports |
| U14 | Pin/bushing radial stiffness | 3×10⁸ N/m per pin | joint test |
| U15 | Root plate–flange seal and outboard hard-stop impact | elastomer stop, ≤ 0.3 m/s | rig test |
| U16 | Slide rollers/liner friction | μ_pad 0.08 | supplier data |
| U17 | Canard mass, CLα 3.0 /rad, pivot at 25% MAC | — | CFD / tunnel |
| U18 | Induction duct area 0.0168 m² total | geometric only | engine selection |
| U19 | Body pitching moment and CG (decide canard size) | NP −0.15 m with body Munk, −0.57 without | CFD + mass ledger |
| U20 | Wing height stagger 0.12 m | aerodynamic effect not quantified | CFD |

## 7. Remaining limitations

- The **mass ledger and CG are still missing**. Pitch stability with this wing is between neutral and unstable (NP −0.15 m against an estimated CG of −0.25 m). The canards can't trim alone below about 70 m/s; until then the wheel-thrusters must keep pitch authority.
- Canard stowage is **external**: blades fold over the front fender. The A8 nose shoulder, a 0.70–0.85 m thin shell, has no internal volume for them without reshaping the nose.
- The cassette shoulders raise the rear haunches to about 1.09 m, and the rear quarter glass is shorter. The **0.12 m left/right wing-height stagger** is inherent to stacked sleeves.
- Door opening kinematics for the A8 "inverted spear" doors were not modelled. The cassette overhang sits 28 mm above the door top edge.
- Pre-existing A8 issues outside this scope remain: seat backs intersecting roof longerons, tyres intersecting fender panels.
