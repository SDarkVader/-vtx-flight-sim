# Simulator revision ledger, 2026-11-03

Branch `research/phantom-a9-cassette`. Sources: `research_notes/Phantom CG compensation and test flights/sim_fidelity_audit.md` (F-items) and `flight_campaign.md` (D-items). Regression tests: `tests/test_sim_fixes_20261103.py` and `tests/test_operator_controls.mjs`.

Every entry below fixes a demonstrated error. No parameter was tuned, and nothing was changed to make a flight succeed. Terrain, buildings, colliders and mission points are unchanged.

Entries that change four-fan (VTX) flight behaviour: R-1, R-2, R-3 and R-4. R-5 changes an instrument reading, not the physics. R-6 changes the Phantom's default initial mass.

## R-1. Training-assist body rates read in the wrong frame (audit F1)
- **Changed:** `src/vtx/aircraft.py` `step()`. The assist reads airframe rates with `mjOBJ_XBODY` (body axes) instead of `mjOBJ_BODY` with `flg_local=1`, which gives principal-inertia axes. The same fix was made in `tools/bench_rate_assist_dynamics.py`, and `evidence/training_assist_dynamic_check.json` was regenerated.
- **Why:** the principal-axis frame of the R6 airframe has axis 0 ≈ body +z. A body roll therefore drove the E/W pair, not the N/S pair.
- **Evidence:** audit E1. A 10 deg/s injected roll was read as [0.008, -9.865, 1.636] deg/s.
- **Before → after:**
  - The bench's own rate reading at t = 0.0025 s after a 10 deg/s roll injection: before -0.016 deg/s (wrong axis); after 10.0 deg/s.
  - Roll rate at 1.0 s: no assist -3.81; assist 0.5 → -4.80; assist 1.0 → -5.26 deg/s.
  - Pitch injection, rate at 1.0 s: no assist 6.64; assist 0.5 → 3.87; assist 1.0 → 1.97 deg/s.
  - The test checks that the correct pair moves for roll (N down, S up) and for pitch (W down, E up).
- **Behaviour change:** only when the experimental assist wire is on (`_bench_apply_experimental_assist`, the persistent-pilot default). It is off by default in the live server.

## R-2. Fuel draw discarded an empty tank's share (audit F3)
- **Changed:** `Aircraft.draw_fuel()`. It replaces `fuel -= burn/4`. The burn is drawn equally from the tanks that still hold fuel, the total is conserved, and `FUEL_EXHAUSTED` is flagged when all tanks are empty. The engine already loses drive when the total is ≤ 1 g.
- **Evidence:** audit E6, with tanks [0.1, 2, 2, 2] kg. Once tank 1 was empty, booked burn was 75% of ∫P·SFC.
- **Before → after:** booked/consumed ratio after the first tank runs dry goes from 0.75 to 1.000000000 (test: rel 1e-9 over 2 s with tank 1 emptied).
- **Behaviour change:** only for unequal tanks or tanks that run dry (endurance and CG drift). Equal-tank sorties are bit-identical.

## R-3. Governor integrator dumped on overspeed (audit F8a)
- **Changed:** `src/vtx/governor.py`. While the 1.01× overspeed fuel cut is active, the integrator is held (no accumulation), and it is clamped to the physical torque cap instead of the zeroed cap. Applied torque during the cut is still 0.
- **Evidence:** audit, `governor.py:27-35`. The clamp `min(integral, cap=0)` zeroed the trim torque after every overspeed, so the next recovery started from zero.
- **Before → after:** integrator after 40 overspeed steps: before 0 N·m; after the pre-overspeed value, unchanged.
- **Behaviour change:** only after an overspeed event, for example a sharp collective reduction. It shortens the rpm droop on the next load step.

## R-4. Integrator `implicitfast` → `implicit` (audit F11a)
- **Changed:** `build_model()` option `integrator='implicit'`. The model XML, and therefore `model_xml_sha256`, changes. Checkpoints saved with the old model are refused, as designed, and are not overwritten.
- **Why:** `implicitfast` drops the Coriolis and centrifugal derivative terms. MuJoCo recommends `implicit` for fast-spinning bodies.
- **Evidence:** torque-free tumble (gravity 0, rotors at 1200 rpm, 20 s):

  | Integrator | Relative ΔH | Rotor speed change with no torque |
  |---|---|---|
  | `implicitfast` (before) | 0.496 | +6.27 rpm |
  | `implicit` (after) | 0.00039 | -0.002 rpm |

- **Behaviour change:** small. Audit E7c found closed hover rates matching to 0.001 deg/s. An open-loop, unstabilised 10 s lift at 17.2 deg diverged slightly differently: end z 3.385 → 3.474 m. That run is open-loop unstable, so this is sensitivity, not a trim change. Wall cost is about the same (0.44 against 0.42 s per sim-s, from the audit).
- **Not applied to Phantom** (`phantom/plant.py` still uses `implicitfast`). No Phantom drift measurement was made; see the deferred list.

## R-5. Radar clearance instrument (audit F4)
- **Changed:** `live_server.foot_clearance_m()`. A ray cast straight down from 5 cm above the lowest gear foot, under the airframe centre, against the MuJoCo scene (terrain, boxes and trees). It replaces `z + 1.56 − 0.95 − surface_z`, a fixed point on the cabin sphere that ignored trees. It uses the same single noise draw.
- **Before → after:** on the gear, after 4 s:

  | Configuration | Before | After |
  |---|---|---|
  | r6 / baseline | 0.7532 m | 0.0018 m |
  | r6 / critical-damping | 0.7524 m | 0.0004 m |
  | light / baseline | 0.7532 m | 0.0018 m |

  20 m above flat ground: 20.01 m. Over a tree, it reads the tree top.
- **Behaviour change:** none in the physics. **Every pilot gate based on `radar_clearance_m` must be re-derived**: on the gear it reads about 0 instead of 0.75 m.

## R-6. Phantom inherited the legacy 10 kg fuel default (campaign D-2)
- **Changed:** `phantom/live.make_aircraft`. `Mission.fuel_kg` reaches the Phantom only when the operator set it explicitly (`model_fields_set`). Otherwise the Phantom uses the load-state fuel, or full tanks (2 × 55 kg).
- **Also:** `mission_dump` records `fuel_kg_explicit` for Phantom requests. Checkpoint restore and `retry()` honour it, so a retry no longer re-imposes 10 kg either. Old metadata without the flag restores exactly as it was flown.
- **Before → after:** as-drawn `phantom` default mass goes from 1797.1 kg with 10 kg fuel to 1897.1 kg with 110 kg fuel. FX-A and FX-C, and explicit fuel, are unchanged.
- **Behaviour change:** Phantom default sorties start 100 kg heavier, as the design intends. Four-fan VTX is unaffected.

## Non-physics corrections (no ledger impact; listed for traceability)
- **Packet body channels** `gyro_body_deg_s` and `velocity_body_mps`, plus `frame_labels` (F2). They are derived from the already-noised world channels, so there are no new RNG draws.
- **Import side effect** (F16): `lab` is created lazily. Importing `vtx.live_server` writes nothing.
- **D-1:** the Phantom operator panel sends nothing until the operator engages it, and disengages on a run or authority change.
- **D-3:** the leg load-cell CG gate is evaluated once the aircraft has settled (t ≥ 1 s, speed < 0.05 m/s) and before lift-off. It is logged as `cg_gate`.
- **D-8:** "landed" needs ≥ 80% of the weight off the lift fans. Landing back at the departure point is scored `landed_at_departure`.
- **D-9:** the bench reports `allocator_ceiling`. The as-drawn delivered peak is 0.520 W against the ideal 0.792 W, which matches the live 0.529 W.
- **D-12:** the step log is sync-flushed once per simulated second.
- **D-14:** air/ground state is debounced (0.25 s), so there is one touchdown event per landing.
- **D-18:** the radar ground reference is published and labelled.
- **F14:** cockpit keyboard mixing is pilot-relative.
- **Labels:** "engine idle" relabelled "engine shutdown" (F8c), the `aircraft.py` docstring fixed, and the engineering-panel world/body labels fixed.
