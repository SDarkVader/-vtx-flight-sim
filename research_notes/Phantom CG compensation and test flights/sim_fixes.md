# Simulator fixes, 2026-11-03: audit and flight-campaign defects

**Inputs:** `sim_fidelity_audit.md` (F-items) and `flight_campaign.md` (D-items).

**Physics change records:** `docs/SIM_REVISION_LEDGER_20261103.md` (R-1 to R-6).

**Regression tests:**
- `tests/test_sim_fixes_20261103.py` (17 tests)
- `tests/test_operator_controls.mjs` (3 tests)

**Constraints kept:**
- Nothing was committed.
- Terrain, buildings, colliders and mission points are unchanged.
- No parameter was tuned.
- `evidence/flights/` is clean. The only ignored file there, `20261101T201531-c2c85d/summary.json`, predates this work (audit F16).

## Test counts
| Suite | Before | After |
|---|---|---|
| pytest | 163 passed | 180 passed (2 collection warnings, pre-existing) |
| node (`node --test tests/*.mjs`) | 5 passed | 8 passed |

## Fixed

### Frames and instruments
- **F1 (assist rate frame).**
  - The assist used `mjOBJ_BODY` with `flg_local`, which gives principal-inertia axes. It now uses `mjOBJ_XBODY`, in `aircraft.py` and `tools/bench_rate_assist_dynamics.py`.
  - `evidence/training_assist_dynamic_check.json` was regenerated.
  - Test: roll moves N/S and pitch moves E/W.
  - Ledger R-1.
- **F2 (packet frames).**
  - New fields `gyro_body_deg_s`, `velocity_body_mps` and `frame_labels`. They are derived from the already-noised world channels, so there are no new RNG draws.
  - Tests: yaw 0/90/180 body-rate check and RNG-sequence check.
- **F4 (radar clearance).**
  - It is now a downward ray from the lowest gear foot. It reads about 0.002 m on the gear (was 0.75 m), 20.01 m at 20 m, and the tree top over a tree.
  - Instrument change, ledger R-5. Pilot landing gates must be re-derived.
- **D-18 (Phantom radar offset).** `radar_altimeter_ground_reference_m` and a frame label were added.

### Accounting
- **F3 (fuel draw).** `Aircraft.draw_fuel` conserves the total burn and flags `FUEL_EXHAUSTED`. Ledger R-2.
- **D-9 (bench thrust ≠ flight thrust).**
  - The bench gains `allocator_ceiling`. The as-drawn delivered peak is 0.520 W, against the ideal `collective_margin` figure of 0.792 W. The live run gave 0.529 W.
  - The old field is kept and documented as ideal.

### Gates
- **D-3 (CG gate at t = 0).**
  - The gate now runs once the aircraft has settled (t ≥ 1 s, speed < 0.05 m/s) and before lift-off.
  - It is logged as `cg_gate`, stored in the checkpoint, and included in the summary.
  - `phantom_run_keys.cg_gate` now reads `pending`.
- **D-8 ("landed" while fans carry the weight).**
  - A landing now needs at least 80% of the weight off the lift fans. This is measured from modelled fan thrust; single-step contact forces scatter by ±20%.
  - Landing back at A is scored `landed_at_departure`.
- **D-14 (touchdown chatter).** Air/ground state is debounced at 0.25 s, giving one touchdown per landing with a positive sink rate.

### Defaults
- **D-2 (legacy fuel default on the Phantom).**
  - The Phantom uses `Mission.fuel_kg` only if the operator set it. Otherwise it uses the load-state fuel or full tanks.
  - Retry and checkpoint restore honour this through `fuel_kg_explicit`.
  - Default as-drawn mass: 1797.1 → 1897.1 kg. Ledger R-6.

### Import-time evidence write
- **F16.** `lab` is created lazily, in the server lifespan or on first use. Importing `vtx.live_server` writes nothing. Test: subprocess import against a data root that holds an unfinished run.

### Control-authority conflicts
- **D-1 (operator panel overrides the pilot).**
  - The Phantom panel is now inert until the operator touches a control or presses "Take control".
  - It shows "PANEL ENGAGED", and disengages when the run or authority changes.
  - Test: pure `heartbeatDue()` in node.
- **F14 (cockpit keyboard).**
  - Cockpit-view arrows and A/D are pilot-relative (`cockpitToBody`, rotated by cabin yaw). Help text updated.
  - Node test: ArrowRight in the cockpit tilts toward −X.

### Other
- **D-12.** The step log is sync-flushed once per simulated second, so it is readable mid-run. Test included.
- **F8a.** The governor integrator is held, not dumped, during an overspeed fuel cut. Ledger R-3.
- **F11a.** The VTX integrator is now `implicit`. Torque-free ΔH over 20 s: 0.496 → 0.00039. Ledger R-4.
- **F8c and F10 (labels).**
  - "engine idle" became "engine shutdown" in the lease log, metadata, `index.html` and `LIVE_LAB_IMPLEMENTATION.md`.
  - The `aircraft.py` variator docstring z-range was corrected.
  - The engineering panel now labels world and body channels.

## Four-fan (VTX) behaviour changes
Each is a demonstrated error, recorded in the ledger:

| Entry | Change | When it shows |
|---|---|---|
| R-1 | Assist frame | Only with the experimental assist wire on |
| R-2 | Fuel draw | Only with unequal tanks or tank exhaustion; equal tanks are bit-identical |
| R-3 | Governor | Only after an overspeed event |
| R-4 | Integrator | Small numerics change in every sortie; `model_xml_sha256` changes, so older VTX checkpoints are refused rather than overwritten |

R-5 (radar) changes only an instrument reading. R-6 is Phantom-only.

## Deferred, with reasons
- **D-5 (lease-expiry fan brake, 3600 → 40 rpm in about 0.5 s).** The brake follows the coded failsafe: collective 0, with the governor braking at up to −0.3·τmax. Whether a lease abort should freewheel, brake or hold a descent is an owner decision about failsafe policy, not a demonstrated physics error. Changing it would change crash outcomes.
- **863 kN contact spike and −0.19 m origin penetration, plus D-15 (foot force never classed as a crash).**
  - These are artefacts of contact stiffness and solimp with `solref .008` and a 1 mm `solimp` width (audit F11c).
  - A compliant or crush contact model and a gear-load limit would change every touchdown and need a design decision and sources. Not tuned here.
  - Peak forces should not be read as structural loads.
- **D-4 (front oleos unloaded on the as-drawn aircraft).** The cause (pod tyres or contact geometry) is uncertain, and fixing it would touch colliders, which was out of scope. The D-3 gate is now evaluated properly, but its estimate stays unreliable on the as-drawn aircraft until D-4 is resolved.
- **D-6 and D-7 (underdamped attitude, no trim or heading hold, weak yaw).** These are FBW control-law design changes, not simulator errors. Changing them would be tuning.
- **D-10 (spawn drop of about 0.06 m).** This needs an equilibrium spawn that would change every sortie's start transient. It is low value, and D-3 now waits it out.
- **D-11 (brakes creep), D-13 (unmet power with headroom), D-16 (ground effect about 1.002 at 1.9 m).** Not diagnosed. Each needs its own investigation of the brake friction model, bus allocation and ground-effect reference.
- **D-17 (residual 20–45 rpm).** The governor releases torque below 5 rad/s (about 48 rpm), and there is no bearing friction. This is a modelling simplification, not an accounting error.
- **D-19 (slow-pilot latency).** An interface limit, not a bug.
- **F5, F6, F7, F13 (duct, edgewise inflow and momentum drag, VRS and windmilling, ISA and wind).** These are large, need duct geometry the repository lacks, and should ship flagged with their own baseline (audit item 11).
- **F15 (`retry()` fallbacks of 800 rpm, baseline, 60 kg, light).**
  - Not changed. These fallbacks apply only to historical metadata that predates those fields, and they are what that old metadata represented. Existing tests encode this.
  - New metadata always carries every field.
  - The `argon_calibration` gear gate is an owner choice.
- **F10 remainder.**
  - Relabelling the `argon_calibration` `measured_reference` rows: which rows were actually flown is unknown, and a test pins the label.
  - Correcting the Argon report text, and the unused `nacelle_command_rate_deg_s` provenance hypothesis: left as is.
- **Attitude horizon for the −Y-forward cockpit (F14, second half).** Render-only, not done.
- **`implicit` integrator for Phantom.** Not measured for Phantom, so not applied.
- **`physical_snapshot()` actuator command and saturation, and the `max_impact_n` gear/non-gear split (F16 remainder).** Logging additions that are not needed for the fixes above.
