# Ricochet RC-01 — component register

Single place for the real, off-the-shelf parts the Ricochet is modelled on. Each part keeps its archived manufacturer datasheet (PDF plus extracted text), its SHA-256 and its source link. Machine-readable values are in [`components.json`](components.json); the simulator should read limits from there, never from hand-typed numbers.

**Status: provisional selection, not validated.** A part is accepted only after offline tests, MuJoCo simulation and piloted flight (owner or AI pilot) all pass. Record each stage below.

## Selected parts

| Function | Part | Rated / peak torque | Speed (no load / rated) | Mass | Datasheet |
|---|---|---|---|---|---|
| Rudder | **Volz DA 58-D (duplex)** — owner decision 20 Nov, full travel at all speeds | 80 / 200 N·m | 100 / 80 °/s | 5.6 kg | [Rev C](datasheets/Volz_DA-58-Duplex_Datasheet_RevC.pdf) |
| Elevator | Volz DA 30-HT-D | 36 / 64 N·m | 165 / 115 °/s | 1.85 kg | same |
| Ailerons (×2) | Volz DA 30-HT-D | 36 / 64 N·m | 165 / 115 °/s | 1.85 kg each | same |
| Reverse buckets (×2) | Volz DA 58-D (duplex) + mechanical over-centre lock (default taken; owner had no preference) | 80 / 200 N·m | 100 / 80 °/s | 5.6 kg each | [Rev C](datasheets/Volz_DA-58-Duplex_Datasheet_RevC.pdf) |
| Fan motors (×2) | EMRAX 228 MV, combined cooling | 130 cont. (LC) / 220 N·m | 6,500 rpm limit | 13.2 kg | [v1.7](datasheets/EMRAX-228_Datasheet_v1.7.pdf) |
| 0.9 m ducted fans | none found off the shelf | — | — | — | custom / provisional |

Added actuator mass: 3 × 1.85 + 3 × 5.6 = **22.35 kg**, bucket locks extra (not yet in the mass register).

Decisions (20 Nov): rudder → DA 58-D (owner). Buckets → lock + DA 58-D and speed envelope → keep 65 m/s sizing with lift-off near 61 m/s flagged for flight test (defaults taken; owner had no preference; either can be revisited).

Why one actuator type for all four aerodynamic surfaces: worst-case hinge moments (Vne 65 m/s, full deflection, tail in fan slipstream) are about 53 N·m rudder, 33 N·m elevator and 17 N·m per aileron. The DA 30-HT-D covers all four within its 64 N·m peak, is duplex (a single channel failure leaves 14 / 26 N·m), and one spare part fits every surface. The simplex DA 30 (16 N·m peak) cannot hold an aileron at Vne.

## Alternatives on file

| Part | Why not chosen | Datasheet |
|---|---|---|
| Volz DA 30 (simplex) | 8 / 16 N·m: too weak at Vne, no redundancy | [Rev B](datasheets/Volz_DA-30_Datasheet_RevB.pdf) |
| Volz DA 26 (simplex) | 2.7 / 5 N·m: trim tabs only | [Rev B](datasheets/Volz_DA-26_Datasheet_RevB.pdf) |
| Moog Model 220 | ~5.6–9 N·m: too weak. Kept because it publishes bandwidth (> 12–15 Hz) and stiffness, which Volz does not | [datasheet](datasheets/Moog_Model-220_Rotary_Servo_Actuator.pdf) |
| Liebherr EMA demonstrator (70 / 151 N·m) | Demonstrator, not a catalogue part | — |

## Known gaps in the data

- Volz does not publish rotor inertia, position-loop bandwidth or how long peak torque can be held. These will be marked `assumed` in the model, not presented as datasheet values.
- The reverse-bucket hinge moment is not modelled in `plant.py` at all. First geometric estimate (20 Nov): at 85° the shell centroid sits ≈ 0.42 m aft and 0.11 m below the hinge axis (`concept_a_builder.py` bucket loft, r 0.495–0.528 m, 24–156° arc); the plant reverses up to 1.55 × 1,450 N ≈ 2,250 N per fan, giving **≈ 250 N·m** at full reverse and full throttle. That is above the DA 58-D peak (200 N·m) **for this hinge placement** — a gap to iterate, not a failed part. The moment is the jet load times its offset from the hinge, so the first iteration is geometric: move the hinge axis toward the bucket's centre of pressure (≈ 0.09 m offset brings it to ≈ 200 N·m, ≈ 0.04 m to ≈ 90 N·m, inside the 80 N·m rated band with the lock carrying the rest), then a lever/linkage ratio, and only then a bigger actuator. Default taken: over-centre lock + DA 58-D; hinge-axis iteration to be calibrated against the plant once the bucket hinge moment is modelled.
- Backlash (≤ 0.6°) needs a separate joint to model faithfully; first pass records it but does not simulate it.

## Findings from offline probes (20 Nov, isolated fixture)

1. **Free-hull headwind probe is invalid above ~35 m/s.** With an imposed 50–65 m/s headwind the boat lifted and inverted (65 m/s, controls centred: +21.7 m, roll −180°, pitch +90°). *Correction (20 Nov, later):* that probe built a bare `RicochetCraft` without the harbour water config, so its datum sat below the 2.0 m bed and the hull was never in water — it was an aero-only run. The lift-and-tumble still shows the airframe's aero pitch behaviour, but not water behaviour. Its hinge readings (up to 812 N·m) are tumbling artefacts. Sizing uses the pinned "wind tunnel" probe (aero only, unaffected). Every water probe now passes the fleet's water config (level 7.0 m, still).
2. **Capsize is not classified as a crash.** In those runs the plant reported `crashed=False` with no flags while upside down. Needs a capsize/inversion outcome (same class of problem as the A10-D outcome bookkeeping) and a test.
3. **The wing out-lifts the boat below Vne.** At zero angle of attack the plant's wing (S 15.5 m², CL 0.25 at α = 0) carries 900 kg at about 61 m/s, below the 65 m/s Vne used for sizing. The speed envelope or wing incidence needs a decision; until then the surface loads are sized for 65 m/s.

4. **Pinned-hull wind-tunnel probe (`probes/tunnel_probe.*`, 128 cases).** The real Concept A plant at 20/35/50/65 m/s, fans idle or full, α −5…+10°, β 0/±8°, full deflection both ways; steady-state unclipped hinge moments. Worst cases: rudder 52.8 N·m at only 22.4° achieved (65 m/s, full throttle, β 8°) ⇒ **≈ 68 N·m at full 30°**; elevator 32.7 N·m at 15.4° (α 10°) ⇒ ≈ 40 N·m at 20°; aileron 15.7 N·m at 22.9° ⇒ ≈ 17 N·m at 25°. Fan slipstream roughly doubles tail loads.
5. **The rudder needs more than the DA 30-HT-D at Vne.** 68 N·m > 64 N·m peak; its 36 N·m rating is exceeded at full rudder and full throttle from about 50 m/s. Either a speed-scheduled rudder travel limiter (≈ ±15° above 45 m/s keeps it near 35 N·m; common practice on real aircraft) or a DA 58-D on the rudder. **Owner decision.** Elevator (≈ 40 N·m) stays inside the DA 30-HT-D peak; ailerons have ≈ 3.8× margin.
6. **The existing idealised servos sag under load.** Commanded 30° rudder reaches 22.4° at Vne with full throttle; today's game already gives less authority than the slider shows. Real actuators with torque-speed limits will make that visible in telemetry instead of silent.

## Skis, CG / CB / Munk and mass distribution (20 Nov, offline probes)

Evidence: `probes/hydrostatic_probe.*` (exact plant meshes, free-trim solve), `probes/towing_probe.*` (towed in the real plant: x, y, heading held; heave, pitch, roll free; throttle 0.7; wake off), `probes/free_run_probe.*` (nothing held, full throttle, wake on). All isolated fixture, nothing live.

**Static (rest, still water)** — whole-vehicle CG from the built MuJoCo model equals the mass register exactly in all three cases.

| Case | Mass | CG x / z (m) | CB x / z (m) | Keel draft | Trim | Displ. hull + 2 skis (m³) | Waterplane hull / ski (m²) |
|---|---|---|---|---|---|---|---|
| LC-03 empty | 815 kg | 0.423 / 0.694 | 0.419 / 0.437 | 0.553 m | 0.9° bow up | 0.662 + 2 × 0.077 | 4.68 / 0.51 |
| **LC-01 design** | **900 kg** | **0.506 / 0.704** | **0.504 / 0.447** | **0.563 m** | 0.3° bow up | 0.740 + 2 × 0.081 = **0.901** | 5.04 / **0.50** |
| LC-05 max | 1050 kg | 0.483 / 0.682 | 0.482 / 0.465 | 0.588 m | 0.4° bow up | 0.867 + 2 × 0.092 | 5.58 / 0.42 |

Matches the spec sheet: displacement 0.90 m³, draft ≈ 0.56 m, ski waterplane 0.50 m² ("A"). The harbour fleet's own crafts float at 0.9008 m³, the same as this independent solve. Spec labels "B 0.90 / D 0.62" are not mapped yet (need the drawing legend).

Stability: small-angle GM_T is very large (13.8 m at design) only because both skis are already in the water. **Each ski is 0.102 m³ gross and sits ~80 % submerged at rest**, so a 2° heel fully immerses the low ski and GZ flattens at **0.37–0.51 m from 2° to 30°**, about 4.5 kN·m righting at most (the spec's "GM 0.35–0.55 m" agrees with this plateau). Roll stiffness beyond 2° is capped by ski reserve buoyancy (~20 % of each ski's volume).

Selected actuators (+22.35 kg at the surface hinges) move the design CG **6.5 cm aft and 2 cm up** (0.441 / 0.724 m): about 0.4° more bow-up trim at rest. Restore by moving the 170 kg pack ≈ 0.35 m forward, or 15 kg of ballast to the bow.

**Under way (towed, design load).** Positive heading offset ψ = nose left; a stable craft gives a negative yaw moment.

| V (m/s) | Hull vol (m³) | Each ski vol / lift | Trim | Yaw moment ψ 3° / 6° (N·m) | Hydro Munk at 6° (N·m) | Back to ψ 0° |
|---|---|---|---|---|---|---|
| 3 | 0.73 | 0.066 / 0.69 kN | 0.4° | +26 / +55 (weakly unstable) | +213 | recovers |
| 6 | 0.62 | 0.060 / 0.81 kN | −0.3° | +74 / +19 (neutral) | +698 | −165 |
| 10 | 0.45 | 0.043 / 0.97 kN | −1.2° | −600 / −1,344 (stable) | +1,292 | −287 |
| 15 | 0.29 | 0.023 / 0.94 kN | −1.9° | −1,406 / **+832** | +1,407 | **−7,963 (latched)** |
| 20 | 0.22 | 0.013 / 0.85 kN | −2.1° | −549 / −4,830 | +760 | **+7,874 (latched)** |
| 25 | 0.14 | 0.004 / 0.45 kN | −2.3° | −5,029 / −10,066 | +1,185 | **−4,119 (latched)** |
| 30 | 0.10 | 0.001 / 0.21 kN | −2.6° | −1,527 / −9,116 | +754 | lifts off |
| 40, 50 | — | — | — | airborne and pitches over | — | — |

Findings:

7. **The Munk moment is destabilising at every speed**, as theory says: +0.7 to +1.4 kN·m at 6° (N_ψ ≈ 7–13 kN·m/rad) from 6 to 30 m/s, largest while the hull is still half-immersed (10–15 m/s). Restoring yaw comes from the skis, whose centre (x = −0.34 m) is 0.85 m aft of CG and acts as a skeg.
8. **Above ~15 m/s that restoring moment comes from one ski catching.** At 6° one ski unloads completely while the other digs in. After returning to ψ = 0 the asymmetry stays latched (±4–8 kN·m yaw, ±4–7 kN·m roll). This is the "linear tracking at speed" problem: the plain float skis give no symmetric, linear side force once the hull lifts.
9. **The craft cannot reach planing speed under its own power.** Free run at full throttle: 2 × 1,387 N thrust at 5,090 rpm, and speed settles at **7–8 m/s** (resistance/weight ≈ 0.31 at hump; planing craft typically 0.15–0.2). The towed runs above 8 m/s are speeds the boat cannot currently reach. Also logged: 4° yaw drift in 40 s with centred controls, and the local water surface fell ~1.7 m under the boat after x ≈ −30 m with wake on (water-model anomaly, to investigate separately).
10. **Lift-off near 30 m/s (throttle 0.7, towed), then the airframe pitches nose-up and over at 40–50 m/s** — the earlier "61 m/s lift-off" was wing-only arithmetic; with planing lift and trim the hand-off happens far earlier, and there is no pitch damping/balance across it. An aero pitch-balance item, separate from the skis.

**Iteration proposed (calibrate, don't condemn): make the outboard sponsons true hydro-skis.**

- *Planing ski on each pod*, flat (or low-deadrise) bottom, **beam 0.50 m, wetted length ≈ 2.0 m (λ ≈ 4)**. Savitsky planing lift at **8° incidence: 4.0 kN per ski at 10 m/s**. With the wing, that is 91 % of the 9.1 kN all-up weight, for 2 × 0.72 kN drag against 2.77 kN measured thrust, so the hump drops from R/W ≈ 0.31 to ≈ 0.16–0.2 and the hull lifts clear. At 15 m/s the same ski at 4° gives 3.6 kN, so incidence must come down as speed rises.
- *Actuated ski incidence* (≈ 2°–9°), one actuator per ski. **Collective** incidence controls running height and trim and gets the craft over the hump. **Differential** incidence gives roll: ±1 kN at a 3.8 m arm is ±3.8 kN·m, which banks the craft into turns and cancels the latch in finding 8.
- *Fixed fin (keel) at each ski's trailing edge*, ≈ 1.1 m aft of CG. It supplies a linear side force for straight tracking that does not depend on which ski is touching. Sized against the measured Munk derivative with a 1.5× margin: A·CLα ≈ 0.17 m²/rad per fin at 10 m/s, i.e. **≈ 0.09–0.10 m² per fin** (e.g. 0.30 × 0.30 m). Fin load grows with V², so tracking stiffens with speed; turning at speed comes from bank (differential incidence) plus rudder and differential thrust.
- *Fore-aft placement / mass distribution.* The thrust line (z 1.56 m) sits 0.84 m above CG and gives 2.3 kN·m nose-down at full thrust. To hold trim, the **ski lift centre must sit 0.26–0.39 m ahead of CG** (for 9–6 kN of ski lift). With CG at 0.44 m (actuators fitted), put the ski hinge and centre of pressure at **x ≈ 0.75–0.8 m** and the fin at its aft end (x ≈ −0.6 m). Alternatively keep the pods where they are and move CG aft by the same amount, but that disturbs the static trim (LCB 0.504 m). The pack shift above returns the static LCG to the LCB.
- *Ski-incidence actuator.* The hinge goes as close to the ski's centre of pressure as the CP travel allows. At ±5 cm CP travel and 4.5 kN, the steady moment is ≈ 225 N·m before slam factors (×3–5). That is beyond rotary EMAs on the register, so the candidate class is a linear EMA on a lever. Selected register entry: **Exlar (Curtiss-Wright) GSX30-0602** (2-stack, 0.2 in lead, 152.4 mm stroke, 3,219 N continuous motor-limited thrust, 254 mm/s max speed) on a 0.44 m lever arm (`1,416.4 N·m` continuous/peak hinge rating, `33.08 °/s` max rate, `19.95°` stroke travel).
- Plant work this needs (opt-in profile, legacy Concept A unchanged): an incidence hinge joint per ski, an aft stern trim ski/foil hinge joint, a fin side-force term, ski geometry in `visual_geometry()`, capsize/ski-catch flags, and closed-loop qualification tests.

## Resolved Blocker #1 (SWE reflective-wall root cause) & 19-DOF / 9-Surface Architecture (20 Nov, worktree `ricochet_control_surfaces`)

### 1. Root cause and resolution of Blocker #1 ("ski energy at rest" & `-1.7 m` water-surface drop)
- **Root cause (`src/vtx/water/shallow_water.py`):** In `ShallowWaterSolver._advance_substep()`, the internal Rusanov face fluxes (`x_flux_hu`, `y_flux_hv`) include the hydrostatic pressure term $\frac{1}{2} g h^2$, whereas the four outer grid boundary faces (`x_flux_hu[:, 0]`, `x_flux_hu[:, -1]`, `y_flux_hv[0, :]`, `y_flux_hv[-1, :]`) were left at `0.0`. On any wet-wall basin (`harbour_world()` / `HarbourWater`, where `h = 5.0 m` up to the outer boundary), the missing wall pressure reaction created a net outward momentum acceleration of $\frac{1}{2} g h^2 / \Delta x \approx 9.8\text{ m/s}^2$ at every wall cell. Within 14 s of simulation time, water piled up to $h = 70.27\text{ m}$ at the boundaries, drained the interior basin by $1\text{–}2\text{ m}$, and radiated a massive reflection wave back through `x = -180 m` just as the bench sweep reached the ski-collective segment. This single boundary defect caused both Blocker #1 (`z` climbing to `9.3 m` at rest) and the `-1.7 m` water-surface drop noted in Finding 9 above.
- **Fix & verification:** Enforced reflective ghost-cell hydrostatic boundary fluxes ($\frac{1}{2} g h_{\text{wall}}^2$ with zero normal mass flux) on all four outer boundaries of `_advance_substep()`, paired with $C^1$ smooth strip-theory added inertia (`dof_armature`), strictly dissipative Wagner water-entry slamming damping $-\max(\dot{I}_a, 0)\dot{q}$ (`dof_damping`), regularized submerged centre of pressure, centroidal low-speed heave drag, 6-strip chordwise rotational pitch-rate damping, and smooth 6-strip plate buoyancy in `src/vtx/ricochet/real_components.py`:
  - Wet-wall lake-at-rest error over 10 s: `0.0 m` (`< 1e-12 m`), solitary pulse reflection relative mass error: `1.42e-16`.
  - Full 19-s rest bench sweep (`test_rest_bench_sweep_passive_and_tracks_skis`): airframe heave remains within `z ∈ [6.434, 6.440] m` (`6 mm` ripple), pitch `< 0.56°`, peak rest ski hinge moment `18.85 N·m` (`< 1,416.4 N·m` Exlar GSX30 rating), and ski collective/differential holds track `12.0° / 6.0°` and `6.0° / 12.0°` within `0.02°`.

### 2. 19-DOF & 9-Control-Surface MuJoCo Topology
When an opt-in 3-point profile (`rc01-planing-3pt-v1` or `rc01-hydrofoil-ski-v1`) is loaded on Concept A (`profile=None` preserves the 16-DOF legacy plant and `public/assets/ricochet-concept-a.glb` 100% unchanged), the compiled MuJoCo model has **`nv = 19` velocity DOFs (`nq = 20`, `njnt = 14`, `nu = 11`)**:

| Category | DOFs (`nv`) | MuJoCo Joints | Actuators & Real Part Mapping |
|---|---|---|---|
| Airframe rigid body | 6 | `root` (`freejoint`) | Free 6-DOF rigid body in `HybridWaterField` |
| Sponson suspension | 2 | `sponson_port_flex_z`, `sponson_stbd_flex_z` (`slide`, `±0.06 m`) | Passive structural flex joints + 6-axis force/torque mount sensors |
| Twin ducted fans | 2 | `fan_rotor_port_hinge`, `fan_rotor_stbd_hinge` (`hinge`, counter-rotating) | `fan_motor_port`, `fan_motor_stbd` — **2 × EMRAX 228 MV** (`200 N·m`, `68 kW`, `6,500 rpm`) |
| Ailerons (Surfaces 1–2) | 2 | `aileron_port_hinge`, `aileron_stbd_hinge` (`hinge`, `[-25°, +25°]`) | `aileron_port_servo`, `aileron_stbd_servo` — **2 × Volz DA 30-HT-D** (`36 / 64 N·m`, `165 / 115 °/s`) |
| Elevator (Surface 3) | 1 | `elevator_hinge` (`hinge`, `[-20°, +20°]`) | `elevator_servo` — **1 × Volz DA 30-HT-D** (`36 / 64 N·m`, `165 / 115 °/s`) |
| Rudder (Surface 4) | 1 | `rudder_hinge` (`hinge`, `[-30°, +30°]`, `rudder_cove_clear=True`) | `rudder_servo` — **1 × Volz DA 58-D** (`80 / 200 N·m`, `100 / 80 °/s`, 0 fin-interference vertices) |
| Reverse buckets (Surfaces 5–6) | 2 | `reverse_bucket_port_hinge`, `reverse_bucket_stbd_hinge` (`hinge`, `[0°, 85°]`) | `reverse_bucket_port_servo`, `reverse_bucket_stbd_servo` — **2 × Volz DA 58-D** + over-centre lock |
| Main outboard skis (Surfaces 7–8) | 2 | `ski_port_incidence`, `ski_stbd_incidence` (`hinge`, collective + differential) | `ski_port_actuator`, `ski_stbd_actuator` — **2 × Exlar GSX30-0602** on `0.44 m` lever (`1,416.4 N·m`, `33.08 °/s`) |
| Aft stern trim ski/foil (Surface 9) | 1 | `ski_aft_incidence` (`hinge`) | `ski_aft_actuator` — **1 × Volz DA 58-D** (`80 / 200 N·m`, `100 / 80 °/s`) |

All 9 control surfaces and twin fans are driven across 10 command channels (`throttle`, `differential_thrust`, `rudder_deg`, `elevator_deg`, `aileron_deg`, `reverse_bucket`, `ski_incidence_deg`, `ski_differential_deg`, `aft_ski_incidence_deg`, `ecu_assist`) exposed in `RicochetAction` (`src/vtx/ricochet/live.py`), `HarbourFleet` (`src/vtx/harbour_fleet.py`), and the Harbour UI (`public/vtx-env/harbour.js`).

### 3. Option 1 (`rc01-planing-3pt-v1`) vs Option 2 (`rc01-hydrofoil-ski-v1`) MuJoCo Comparison & Selectability
Both architectural options preserve the Concept A main hull and buoyant outboard sponsons at rest (`0.150–0.163 m³` static sponson submerged volume for roll stability), use real Raymer mesh drag build-up (`CdA = 0.545–0.550 m²`) and real strut profile + Hoerner spray drag, and are selectable side-by-side in `RicochetCraft(..., profile=...)` and live in `HarbourFleet` / `harbour_session._restart_boat`:

| Metric | Legacy Concept A (`profile=None`) | Option 1: 3-Pt Planing (`rc01-planing-3pt-v1`) | Option 2: Hydrofoil-Section Skis (`rc01-hydrofoil-ski-v1`) |
|---|---|---|---|
| DOFs (`nv`) / Control surfaces | 16 DOFs / 6 surfaces | **19 DOFs / 9 surfaces** | **19 DOFs / 9 surfaces** |
| Main outboard ski geometry | None | Savitsky `4°` deadrise planing ski (`1.90 × 0.62 m`) on `0.48 m` strut | Cambered NACA 4412 hydrofoil-ski (`0.48 m` chord × `1.18 m` span, `AR 2.46`) on `0.58 m` strut |
| Aft stern trim ski/foil | None | Savitsky `6°` deadrise planing ski (`0.95 × 0.56 m`) | Cambered hydrofoil-ski (`0.34 m` chord × `0.72 m` span) |
| Total mass (`LC-01` + hardware) | `900.0 kg` | `973.99 kg` | `971.49 kg` |
| Static rest sponson volume | `0.162 m³` | `0.1502 m³` | `0.1633 m³` |
| Hull liftoff time (`vol_hull < 0.02 m³`) | Does not lift (`~0.50 m³`) | **`8.01 s`** (`min_vol_hull = 0.0 m³`) | **`3.74 s`** (`min_vol_hull = 0.0 m³`) |
| Time to clear `12 m/s` hump | Stuck at `7.76 m/s` | **`14.52 s`** | **`8.24 s`** |
| Speed at `22 s` / `26 s` (`2 × EMRAX 228`) | `7.76 m/s` | **`18.70 m/s` / `21.08 m/s`** | **`22.20 m/s` / `23.43 m/s`** |
| Peak main ski hinge moment (vs `1,416.4 N·m` Exlar) | — | **`1,124.4 N·m` (`79.4 %`)** | **`672.9–773.1 N·m` (`47.5–54.6 %`)** |
| Peak aft ski hinge moment (vs `200 N·m` DA 58-D) | — | **`81.7–96.1 N·m`** | **`51.0–52.3 N·m`** |
| Closed-Loop Maneuvers A–D (`closed_loop_maneuver_suite.py`) | — | **PASS (4/4 maneuvers)** | **PASS (4/4 maneuvers)** |

## Validation ladder

| Stage | Result | Evidence |
|---|---|---|
| Offline unit tests | **PASS** | `tests/test_ricochet_real_components.py`, `tests/test_ricochet_control_surfaces_dof.py`, `tests/test_harbour_fleet.py`, `tests/harbour-helm-controls.test.mjs` |
| MuJoCo scenario runs (incl. A10-D lessons below) | **PASS** | `docs/ricochet/complete_model/compare_hydro_options.py`, `scratch/complete_model/option1_vs_option2_comparison.json` |
| Piloted flight — owner | pending owner choice | Both `rc01-planing-3pt-v1` (Option 1) and `rc01-hydrofoil-ski-v1` (Option 2) selectable live in Harbour UI |
| Piloted flight — AI pilot (telemetry-only closed-loop) | **PASS** | `docs/ricochet/complete_model/closed_loop_maneuver_suite.py`, `scratch/complete_model/closed_loop_maneuver_report.json` (Maneuvers A, B, C, D on Option 1 & Option 2) |

Lessons carried over from the A10-D live records (19 Nov): neutral-stick ground loops → test centred-control tracking at speed and low-speed steering; the 422 vertical-speed rejection → command bounds must equal actuator capability; the slow transition crash → re-test stopping and docking with real bucket rates; commanded-versus-achieved logging → per-surface torque and saturation telemetry.

## Files

`datasheets/*.pdf` are the manufacturer files as downloaded on 2026-11-20; `datasheets/*.txt` are text extractions for search. Hashes are in `components.json`.
