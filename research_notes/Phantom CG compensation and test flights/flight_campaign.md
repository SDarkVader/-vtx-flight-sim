# Phantom flight campaign, 2026-11-03: summary and simulator defect list

Full report: `docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md`. Numbers: `evidence/phantom/phantom_calibration_20261103.json`. Runs: `evidence/phantom/flight_campaign_20261103/evidence/flights/`.

## Summary

### `phantom` (as drawn, 1897 kg)
- **No lift-off.** Total thrust stops at 0.53 W.
- The rear pods saturate at about 3530 N and the generators are at their 1.2 MW cap.
- The desaturation logic then cuts the front pods, to keep the pitch balance.

### `phantom-fx`
- **Flies.** Hover collective is 0.648 for FX-C and 0.706 for FX-A.
- Hover power is 1.21 MW for FX-C (71 W/N) and 1.41 MW for FX-A (76 W/N).
- The front-pod share is 0.458–0.460, which matches the ledger CG.
- Derived hover endurance: 517 s for FX-C, 397 s for FX-A.

### Handling (M2 mode)
- Roll and pitch overshoot about 2x on doublets.
- Pitch oscillates in translation (±3–8 deg).
- Yaw reaches only half the commanded rate.
- The vertical axis is good.
- All four normal landings were at or below 0.5 m/s.

### Gates
- **C1 fails** for both variants.
- **C2 was not met.** The 200 m hop east, (13.7, –28.4) to (213.7, –28.4), was flown as **T-2X**. It ended in `landed` at 0.40 m/s, 1.4 m from B, after 116 s. Track and height errors exceed the T-2 tolerances.

### Crashes
- One crash: an unplanned X-1 lease expiry from 3.1 m. Touchdown at 7.1 m/s, peak contact force 863 kN.
- Plus an X-5 ladder up to 2.9 m/s with no damage flag.

## Defects and fidelity problems

Each item has an ID, a severity and its evidence.

### High severity

**D-1. Operator panel takes control behind the pilot's back.**
- The browser operator panel (`public/phantom-controls.js:26`) sends a heartbeat with `authority:'manual'`. Each one re-sends the panel's own command (collective 0).
- Any open browser tab on the port therefore overrides a machine pilot flying with the same authority. There is no warning and no arbitration.
- This contradicts the contract's "control authority must be visible, not duplicated".
- Evidence: run `20261103T144211-55c7ac`, `events.jsonl`. Its pilot_decision entries carry the reason "Manual Phantom operator controls and command heartbeat" and reset my collective steps 0.2–1.0 within about 2.5 s.
- Workaround used: fly with authority `colin`.

**D-2. Phantom gets the legacy fuel default.**
- `Mission.fuel_kg` defaults to 10 kg, and `live.make_aircraft` passes it to the Phantom whenever `load_state` is unset.
- The as-drawn aircraft therefore starts at about 1797 kg instead of 1897 kg, with 9.6 kg of fuel instead of 110 kg. Nothing flags this.
- Evidence: run `144211-55c7ac` observations show `fuel_kg` of [4.81, 4.81].

**D-3. The leg load-cell CG gate never gives an answer.**
- The gate is computed in `after_start` at t = 0. The aircraft spawns about 0.06 m above its gear, so the result is always `status: no_weight_on_legs`, never GO or NO_GO.
- Evidence: `phantom_run_keys.cg_gate` in every run.

**D-5. Lease abort removes all residual thrust.**
- After the lease abort, the fan governors brake the rotors with up to –0.3·τmax: 3600 to 40 rpm in about 0.5 s. Thrust is zero within 0.5 s, so the aircraft drops like a stone.
- From 3.1 m: touchdown at 7.14 m/s.
- The contact solver then reports an 863 kN peak (about 50 g), and the airframe origin reaches z –0.19 m, which is ground penetration.
- Evidence: run `20261103T145427-98fc81`, `phantom_steps.csv.gz` from t 37.05 to 38.05, plus `crash_ring.npz` and `lease_abort_ring.npz`.

**D-6. Attitude control is underdamped and lacks trim.**
- The attitude loops are PD with no integrator. A lateral CG offset leaves a steady bank (FX-C needs roll stick –0.13).
- Pitch step: the response peaks at 1.7x the command and settles 10–18% beyond it.
- Roll doublet: 2.2x overshoot.
- After pitch commands in translation there is a sustained pitch oscillation of ±3–8 deg, with q up to ±10 deg/s and a period of about 2–3 s.
- Ram-drag pitch moment and attitude-loop interaction is suspected.
- Evidence:
  - run `190252-3ef734`, around t 120–135 (rearward flight, constant +2 deg command);
  - run `192918-14ade4`, around t 65–80;
  - the PTI table in the calibration JSON.

**D-8. "Landed" is declared without weight on the gear.**
- The settle detector (`phantom/live.py` integrate) needs only support ≥ 3, speed < 0.15, level, and within 2 m of B. It doesn't check gear load or collective.
- The hop was declared landed with the fans at about 95% hover thrust and the oleos extended about 8 mm.
- A landing back at A can never be scored as `landed`, because the "within 2 m" test only uses B.
- Evidence: run `192918-14ade4`, last observations (fan rpm about 3430–3780, oleo –0.008 m).

**D-9. Bench and live disagree for the as-drawn aircraft.**
- `phantom_bench_results.json` gives a collective margin of –0.208 (about 0.79 W).
- The live G-3 ceiling is 0.529 W, because the attitude-priority desaturation scales the front pods to 1385 N.
- The bench margin overstates what the allocator delivers.
- Evidence: run `144550-be8193` at t 27–42.

### Medium severity

**D-4. Front oleos carry no load on the as-drawn aircraft.**
- The as-drawn aircraft sits 2.9 deg nose-up with the front oleos at –1.6 mm, i.e. extended and unloaded, and the rear oleos at 8.5 cm.
- Its CG (x –0.73) is ahead of the rear legs (x –1.18), so the front legs should carry about 20% of the weight.
- Something other than the legs, probably the rear pod tyres, is carrying load. That makes any gear-load CG check meaningless.
- Evidence: run `144550-be8193`, t 2–5.

**D-7. Yaw is weak and heading drifts.**
- Yaw authority is about 50% of the commanded rate: an 8 deg/s doublet gives 4 deg/s.
- With zero pedal the heading creeps 0.3–1 deg/s. There is no heading hold, so the pilot workload is high.
- Evidence: run `190252-3ef734`, PTI at t 45.2; run `192918`, yaw drift from –3 to +2 deg.

**D-16. No ground effect where it should show.**
- At 1.9 m the ground-effect factor is 1.002, and IGE power (1234 kW) was higher than OGE power (1210 kW).
- The 0.90 m fans sit about 1 m above the ground, so the classical IGE region shouldn't be negligible.
- The cap or the reference height may be suppressing ground effect.
- Evidence: run `144853-5e8e48` trim and `gef_FL`.

**D-14. Touchdown events chatter.**
- One touchdown produces up to 6 events in 0.2 s, some with negative "sink rate".
- The hard-landing classification is based on whichever event comes first.
- Evidence: run `194858-35a724` at t 71.35–71.57.

**D-15. Foot forces are never classed as a crash.**
- At a 2.9 m/s touchdown the foot force peaked at 17.3 kN, above `crash_force_n` of 15 kN.
- Feet are excluded from the "hard" contact sum, so no damage is ever flagged below the 3.0 m/s sink limit, whatever the force.
- Evidence: run `194858-35a724`.

### Low severity

**D-10. Spawn drop.** At spawn the aircraft is not on its gear: it falls about 0.06 m and lands at –0.32 m/s at t = 0.05. Evidence: every run's first observations.

**D-11. Brakes don't hold.** With brakes on and full collective, the as-drawn aircraft crept 0.3 m in x and 1.2 deg in yaw. Evidence: run `144550-be8193`.

**D-12. Step log unreadable mid-run.** `phantom_steps.csv.gz` can't be read while a run is active (gzip isn't flushed). An abnormal server stop would lose its tail.

**D-13. Unmet power with headroom.** `unmet_w` of 28 kW was logged at collective 0.2 on the as-drawn aircraft, with the generator far from its limit. Evidence: run `144550-be8193` at t 7–9.

**D-17. Residual fan rpm.** Fan rpm reads 20–45 with zero thrust command, on the gear after shutdown. It's a residual spin that is never fully stopped.

**D-18. Radar altimeter offset.** The radar altimeter reads about 0.40 m on the gear. The offset isn't labelled in the observation, so the pilot has to learn it.

**D-19. Interface latency for a slow pilot.** This is an interface and fidelity problem, not a bug.
- An LLM pilot's sim-time decision interval was 5–17 s at p95 even at time scale 0.1.
- The C1 requirement of p95 ≤ 0.2 s needs time scale ≤ 0.01. That is the API minimum, and it would mean hours of wall time per sortie.
- Precision cards (P-x, O-4) are impractical without a faster pilot loop.

## Not changed

No edits were made to `src/`, `tests/`, the physics or the parameters. `evidence/flights/` in the repository is untouched, because all runs went to the campaign data root.
