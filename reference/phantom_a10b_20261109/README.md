# Phantom A10-B reference data (9 November 2026)

Reference data behind the canonical A10-B model. The model, its tests and its specification live on the model branch: `docs/phantom/PHANTOM_A10B_MODEL.md`.

All runs are on the MuJoCo plant (flat test strip or airborne initial conditions, canned test-pilot schedules), not piloted game flights.

| Folder | Contents |
|---|---|
| `docs/` | Investigation write-up: take-off rotation diagnosis, hull Munk moment, suspension and drive reruns (`A10_ROTATION_MUNK_SUSPENSION.md`). |
| `register/` | A10-A flight register, 4-7 Nov 2026 (72 run IDs; JSON and PDF), as supplied. |
| `telemetry/` | Per-test logs (JSON). See the table below. |
| `logs/` | Console output of each test, including W1/W1g (wing deployment) and R5 (as-drawn take-off). |
| `captures/` | Plant snapshots (body poses, joints, data) used for the images. |
| `images/` | Rendered frames with data panels: deployment, road steering, VTOL, take-off roll, fan braking, decelerating turn, A10-B model views. |
| `scripts/` | The test, capture and render scripts as run. `camp_repo.py` is the campaign helper; paths are those of the session. |

| Telemetry | Test |
|---|---|
| `t1_P6.json` | T1: instrumented take-off roll, moment budget about the rear tyre contact (A10-A) |
| `t4_*.json` | T4: dynamic rolls, full stick (as flown; 7 deg incidence; plus battery aft) |
| `t5.json` | T5: ground-contact log of the 7 deg run (tyre hops) |
| `r1_*.json` | R1/R4: rolls with hull lift + suspension (+ drive limits) |
| `r2.json` | R2: 100 Hz log around the lift-off pitch-rate spike (wheel overspin) |
| `u1.json` | U1: static pitch and yaw moments vs alpha/beta, A10-A vs hull lift |
| `v1_*.json`, `v2_*.json` | V1/V2: airborne, fans facing down; V2 trimmed deceleration, new vs old law |
| `v3_*.json` | V3: A10-B wing-borne turn (fans off), fan-assisted decelerating turn, take-off roll |
| `m2_sections.json`, `m4_cad.json`, `m5_munk.json` | Hull sections (collision meshes, CAD envelope) and Munk calculation |
