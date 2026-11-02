# Phantom retractable wing — Stage 1: measurement, defects, loads and architecture

**Status:** Stage 1 analysis. Option T was **approved on 2026-11-02** and built as revision A9; see [A9_WING_CASSETTE_REVISION.md](A9_WING_CASSETTE_REVISION.md). The A9 build moved the shoulder flank out to the fender line, \|y\| = 1.245 m, which gives a 5.19 m span, a 1.05 m tongue and 0.94 m between lock stations. The figures below are the Stage 1 values.
No new Blender revision has been made, and nothing has been written to Blendstra.

**Kinds of evidence.** Every number below is tagged with one of these:

- **MEASURED-K:** kinematic or geometric, measured from the pinned CAD by script.
- **DERIVED:** closed-form calculation (`engineering/phantom/wing_loads.py`).
- **SYNTHETIC:** a declared assumption with bounds.

There is **no FEA, CFD or coupled aeroelastic analysis** in this document. Blender intersection results show geometric fit only; they say nothing about strength or aerodynamics.

## 1. Source and preservation

| Item | Value |
| --- | --- |
| Blendstra project / version | `b77e9377-f1b3-4177-ba4e-c1af1d4ed8b2` / `version_a5589426caea8f9c2a6b690671aa8a9387ceff32eaef358186236dbd4de18752` (selected = current head, not accepted) |
| Title in Blendstra | "VTX Phantom A1 — Scale Chassis and Articulation Rig" (A8 exterior) |
| Local copy | `assets/source/phantom-a8/phantom-a8.blend` (**not committed: private source, public repo**; re-export with Blendstra `artifact_export kind:source`), SHA-256 `ae22a71a88f19397c25851f4a34420fd787b5b7419d610e96939d569e4e5cd83` (matches Blendstra record), file marked read-only |
| Handling | Opened only with `blender -b --disable-autoexec`; the source is never saved. Blendstra version unchanged. |
| Inventory | `evidence/phantom/a8_inventory.json`: 222 objects, frames 1–140 @ 24 fps, Blender 5.2.3 |

## 2. Measured vehicle (MEASURED-K, metres, model frame X forward / Z up)

| Feature | Measurement |
| --- | --- |
| Hull (closed manifold) | x −2.40…+2.45 (4.85 long), \|y\| ≤ 1.011, z 0.17…1.19; volume 4.35 m³; planform 8.51 m² |
| Overall width over fenders | \|y\| ≤ 1.25 |
| Wheel/thruster pods | pivots (+1.54 / −1.59, ±1.04, 0.42); tyre Ø 0.72 × 0.106; rotate 90° about X (frames 50→80) |
| Landing legs | slide z 0.79 → 0.27 (frames 30→50) at x +1.10 / −1.18, \|y\| 0.53 |
| Seats (two, side by side) | x −0.60…+0.12; seat backs to x −0.587, head restraints to x −0.600 |
| Side glass / doors | glass x −0.99…+0.75, z 0.84…1.15; doors x −0.90…+0.78, z 0.38…0.76 |
| Carry-through box `MOUNT_001` | x −0.86…−0.44, \|y\| ≤ 0.685, z 0.685…0.855 (170 mm deep) |
| Rear motor bulkhead | x −1.51…−1.39, z ≤ 0.715; rear tub shear walls x −1.37…−1.19, \|y\| 0.44…0.60, z ≤ 0.895 |
| Shoulder induction inlets | x −1.53…−0.97, \|y\| 0.51…0.80, z 0.75…0.93 |
| Twin raked fins / dorsal | fins x −2.23…−1.28, \|y\| 0.47…0.64, z 0.73…1.46; dorsal x −1.81…−0.75, \|y\| < 0.34, z 0.82…1.19 |
| Rear exterior deck height | 0.60…0.91 m behind the cabin (`evidence/phantom/a8_packaging_map_f140.json`) |
| A8 wing | 8-vertex **flat plate, 46 mm thick**; one **vertical-axis** hinge at (−0.79, ±0.91, 0.885); folds 90°; span 6.16 m deployed |
| A8 canard | 27 mm flat plate ~0.32 m²/side; vertical-axis hinge at (1.82, ±0.69, 0.53), 45° fold |

**Frame naming:** objects named LEFT sit at −Y. In the right-handed X‑forward/Z‑up frame, −Y is the vehicle's starboard side. Either the names use a viewer's convention or the frame is mirrored. This must be settled explicitly before MuJoCo import.

## 3. Mechanical defects found (MEASURED-K, sweep `evidence/phantom/a8_sweep_baseline.json`)

The sweep covered every 3rd frame of 1–140. It tested BVH triangle overlap, ray-parity containment and 2 cm surface-sampled clearance (`tools/phantom/sweep_clearance.py`).

1. **The wing intersects structure at every swept frame**, stowed, in transit and deployed:
   - rear fender at all frames;
   - hull at frames 1–67 and 130–140;
   - left rear **tub shear wall** at 1–64;
   - side glass at 1–55;
   - raked fin at 1–61;
   - dorsal at 1–52;
   - **induction inlet** at 1–67;
   - its own root fairing at 64–130 (fully deployed).
2. **The stowed wing is external.** It lies on the rear deck at z 0.87–0.99 and **overhangs the tail by 0.56 m** (x to −2.96 against a hull end of −2.40).
3. **No load path.** The wing is a 46 mm plate cantilevered from one vertical pin. The bending moment would have to be reacted over ≤ 46 mm of depth: about **1.25 MN per pin** at the loads in section 5. That exceeds the SKF GEH 50 TXE-2LS C0 of 1160 kN, and a GE 80 (120 mm OD) can't physically fit in the plate.
4. **The carry-through box intersects both seat backs** (86 triangle pairs each) and the hull. Its titanium bearing blocks intersect the side glass.
5. **The canard passes through the front wheel.** The blade intersects the tyre, structural disc and thrust duct in the stowed and transit frames (1–73, 124–140). It intersects the **wheel reaction pylon and Ti hinge bracket in every frame**. Its clevis mount intersects the pylon and the radiator ram-inlet perimeter.
6. **No aerofoil, control surfaces, locks, actuators or hatches exist** on either wing or canard.
7. **Outside this task's scope:** seat backs and head restraints intersect the roof longerons, sills and hull, and the tyres intersect the fender and splitter panels (wheel arches aren't cut).

## 4. Preliminary load envelope (DERIVED / SYNTHETIC)

The structure is designed to **+6.0 / −3.0 g limit, ×1.5 = +9.0 / −4.5 g ultimate**. This follows the CS‑23 aerobatic-category pattern, used here as design practice, not as a compliance claim. The reasons:

- A FBW **operational g-limit of about +4.4 / −1.8 g** is recommended for untrained occupants. The structural limit sits above it to cover overshoot, rolling pull-ups and gusts. The earlier **+8 / +12 g** figure exceeds what occupants can tolerate without anti‑g equipment and costs about 33% more root moment. It's kept in the results as a sensitivity case.
- Gusts don't govern. The Pratt formula (CS‑23.341, 15.24 m/s at V_C, 7.62 m/s at V_D) gives n = 3.2 / −1.2 at V_C for the 1050 kg minimum flying weight, against the 6 g manoeuvre.
- Speeds: V_C = 178.8 m/s (the 400 mph target) and V_D = 1.25 V_C = 223.5 m/s (M 0.66 at sea level). For the recommended wing: V_S1 = 68 m/s and V_A = 167 m/s.
- Conditions evaluated: symmetric PHAA/PLAA/negative; gust ±; rolling pull‑up at 2/3 n with 100% / 60% side load and aileron at V_A (full), V_C (2/3) and V_D (1/3); flaps 30° at n = 2.
- **Body lift share is unknown.** Schrenk loading treats the body as wing, which puts only 21% of the lift on each exposed panel. Sizing uses a **conservative bound where the panels carry all the lift**. CFD has to settle this.

**Still unknown:** real lift-curve slope, body lift and pitching moment, Mach effects above M 0.6, how well the FCS g-limiter works, VTOL/conversion loads with the pods, landing and road loads through the cassette, and the fatigue spectrum.

## 5. Root loads and joint options (recommended wing, per side, ultimate × 1.15 fitting factor)

The root loads, at the body-side station and conservative, are:

- shear V = 56.5 kN
- bending M_x = 32.0 kN·m
- torsion = 4.6 kN·m

If the body shares lift (Schrenk), they drop to 23.5 kN, 15.0 kN·m and 1.9 kN·m. The earlier 91.8 kN·m figure used the full 12 g load at a 1.2 m arm on each side.

| Joint principle | Couple separation | Max pin force | Notes |
| --- | --- | --- | --- |
| A8 vertical pin, 46 mm plate (A8 loads) | 0.046 m | **1250 kN** | infeasible |
| Depth-limited lug couple at root box | 0.079 m | 497 kN | geometry-limited, heavy fittings |
| A8 fairing height, if it were structure | 0.160 m | 262 kN | fairing is not structure |
| **Spanwise tongue couple in carry-through sleeve** | **0.76 m** | **59 kN** (4 pins) | **8× lower than depth-limited**; shear-governed pin diameter 6.4 mm, chosen 20 mm PH13‑8Mo pins in Ti‑6Al‑4V double-shear lugs, governed by bearing, wear and bending |

The mechanical advantage comes from where the couple acts. A sliding (telescopic) wing keeps its root box running inboard as a **tongue** inside a sleeve, and the bending moment is reacted as a vertical force couple between the sleeve mouth and the tongue end, 0.76 m apart. A fold hinge has to react it across the 46–80 mm thickness of the wing. The rotation and slide bearings carry no flight bending: they are unloaded once the locks engage.

## 6. Wing structure, control surfaces and aeroelastic screen (recommended wing)

- **Box:** CFRP torsion box at 15–60% chord, sized from strain (3500 µε ultimate, SYNTHETIC). At the root: depth 79 mm, width 0.32 m, caps 4.0 mm, webs 2.8 mm; EI = 3.7×10⁵ N·m², GJ = 2.6×10⁵ N·m².
- **Mass per wing:** about 16 kg (box 3.3 + secondary 6.8 + tongue 6.0). Raymer's general-aviation statistical estimate gives 12.6 kg per exposed panel in metal.
- **Ailerons** (η 0.55–0.95, c_f/c = 0.28): 0.067 m² each, ±20°, 80°/s. Maximum hinge moment 48 N·m nominal. Actuator stall torque ≥ 78 N·m, 78 W peak electrical. The wing is only **25 mm deep at the hinge**, so the actuator needs an under-wing fairing that stays inside the root profile so it can pass the slot, or the surface needs aerodynamic balance.
- **Flaps** (η 0.05–0.50): 0.114 m² each, −5…+35°, 15°/s, hinge moment 37 N·m, stall torque ≥ 60 N·m. Speed-scheduled; locked out above the flap limit speed.
- **Roll** (I_xx ≈ 660 kg·m², SYNTHETIC): steady 349°/s at V_A, 246°/s at V_C and 147°/s at V_D. 90° of bank takes 0.45–0.93 s. **An FCS roll-rate limit is required** for occupants and inertial loads.
- **Aeroelastic screen** (typical section at 70% span, Theodorsen k-method; matches the Hodges & Pierce reference case, 2.184 vs 2.17):
  - bending 31 Hz, torsion 147 Hz;
  - flutter 678 m/s EAS against the required 1.2 V_D = 268 m/s;
  - reversal 717 m/s, divergence 782 m/s (unswept estimate).

  The torsion frequency depends on a SYNTHETIC section inertia. **Control-surface flutter isn't modelled.** The requirement instead is mass balance to the hinge line, with actuator stiffness ≥ 6.9 kN·m/rad on the aileron and 27 kN·m/rad on the flap.

## 7. Canards and longitudinal balance: the main open issue

- The **neutral point** comes out at x ≈ −0.09 m when the destabilising pitching moment of the 4.35 m³ hull (its Munk moment, SYNTHETIC factor) is included, and −0.54 m without it. The CG is **unknown**, because there's no mass ledger yet; the estimate is −0.25 m. The vehicle may therefore be statically unstable in pitch by up to about 18% MAC. **CFD of the body pitching moment and a mass ledger are needed before the canard size and final wing station can be fixed.**
- With the A8 canard (0.64 m² total) and CG at −0.25 m, trimming needs canard **CL > 0.9 below about 70 m/s**. The wheel thrusters can be fully withdrawn only above about 70 m/s; below that they have to keep supplying pitch authority, or the canard has to grow.
- Canard as an all-moving surface pivoted at 22% MAC: maximum hinge moment 359 N·m, actuator stall torque ≥ 583 N·m, ±20/+25°, 40°/s. The Ti spindle needs OD ≥ 43 mm, carrying 40 kN ultimate across a 0.20 m bearing spacing. It also **has to move out of the front wheel** (defect 5).

## 8. Architecture comparison

| | A: A8 external fold (fix in place) | R: rotate into a raised rear deck (A8 brief) | **T: telescopic stacked-sleeve cassette** |
| --- | --- | --- | --- |
| Stowed behind panels | no | yes, with a full rear deck raised to ~1.0 m and fins moved | yes, under raised shoulders, x −0.63…−1.48 |
| Hatch | none | **long side slot ≈ 1.4 m** | **small flush slot ≈ 0.84 × 0.11 m per side** |
| Root couple | depth ≤ 46–160 mm | depth-limited: the tongue would sweep into the cabin | **spanwise 0.76 m** |
| Degrees of freedom per wing | 1 rotation | slide + rotate + lock | 1 slide + lock pins + 2 hatch doors |
| Wing | 6.16 m / 5.26 m² | ~1.5 m exposed, chord ≤ 0.6 m | **4.94 m / 3.75 m²**, 0.76 m² exposed per side, LE sweep 20°, straight TE |
| Precedent | — | — | Makhonine Mak‑10, telescopic wing, flew 1931 |

**Recommendation: T.** It's the only arrangement measured to give internal stowage, small hatches and a load path not limited by wing depth at the same time. Its costs:

- a smaller wing: fully wing-borne from about 70 m/s at CG −0.25 to −0.50 m. The A8 planform, given the same A8 canard, manages 60–90 m/s depending on CG;
- a straight trailing edge;
- a **0.12 m height stagger** between left and right wings (the sleeves are stacked).

The sleeve doubles as the carry-through box, replacing `MOUNT_001`, which intersects the seats.

## 9. Changes that need approval before building

Option T materially changes the A8 in these ways:

1. Rear shoulders raised from about 0.88 m to about **1.08 m** between x −0.63 and −1.50 (the "cassette shoulders"), with flush slot hatches on the haunch flanks at \|y\| ≈ 1.12.
2. **Rear quarter side glass shortened** from x −0.99 to about −0.62.
3. **Shoulder induction inlets relocated** to the existing cheek-inlet positions, x −0.90…−0.25, ducted below the sleeves.
4. `MOUNT_001` removed and replaced by the twin-cell sleeve box, supported on the rear shear walls and a new frame at x −0.63. The rear shear walls are trimmed to z 0.80.
5. Wing planform changes to a straight trailing edge with a smaller span and area, and the left and right wings sit 0.12 m apart in height.
6. The canard moves out of the front-wheel volume: above the tyre into the nose shoulder at z ≈ 0.82, or forward of x 1.92. It's re-mounted on a spindle with a pitch actuator; area is held until there's a CG ledger.

Packaging renders (Workbench, not appearance renders) are in `evidence/phantom/renders/`. `f001_A8_*` shows the baseline and `f001_T_*` shows Option T's sleeve bay and wing overlaid on the A8.

## 10. Unverified-assumption register (key items; the full list with bounds is in `wing_loads_results.json` → `inputs`)

| # | Assumption | Value / bounds | Retire by |
| --- | --- | --- | --- |
| U1 | Gross / minimum flying mass | 1300 / 1050 kg (1100–1500) | mass ledger |
| U2 | CG | −0.25 m (−0.75…−0.25) | mass ledger |
| U3 | Body lift share and pitching moment | Schrenk vs zero-body bound; Munk factor 0.85 | CFD / wind tunnel |
| U4 | Section polars, C_m0 −0.04, CL_max 1.2 / 1.6 | NACA 64A2xx class | aerofoil selection + CFD |
| U5 | Hinge coefficients | C_hδ −0.70, C_hα −0.35 per rad, ×0.7…×1.3 | CFD / wind tunnel |
| U6 | CFRP allowables | E_cap 105 GPa, 3500 µε, τ 150 MPa | coupon / allowables |
| U7 | Secondary structure mass | 9 kg/m² | detailed design |
| U8 | Pin and bushing stiffness | 3×10⁸ N/m | joint test / FEA |
| U9 | Transit limit and normal-force coefficient | q ≤ 600 Pa, C_N 1.2 | CFD of transit with pod downwash |
| U10 | Roll / pitch inertia | 660 / 2300 kg·m² ±30% | mass ledger |
| U11 | Ti lug notched endurance | 200 MPa max stress at 10⁷ cycles, R = 0.1 | MMPDS S‑N data for the chosen product form |
| U12 | Operational g-limit | +4.4 / −1.8 g | human-factors review |

## 11. Reproduce

```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend --python tools/phantom/inspect_a8.py -- evidence/phantom/a8_inventory.json
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend --python tools/phantom/sweep_clearance.py -- evidence/phantom/a8_sweep_baseline.json --step 3 --sample 0.02
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend --python tools/phantom/packaging_map.py -- evidence/phantom/a8_packaging_map_f140.json --frame 140 --x -2.45 0.3 --y -1.3 1.3 --dx 0.05
python engineering/phantom/wing_loads.py
```
