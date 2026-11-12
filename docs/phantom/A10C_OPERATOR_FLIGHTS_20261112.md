# Phantom A10-C — operator flight observations (12 November 2026)

> **Evidence status:** Manual flight observations from an operator-supplied screen recording and cockpit captures. These are simulator measurements and demonstrations, **not** independently validated full-flight-envelope or real-aircraft performance. The source media and raw sortie JSONL are **not archived in this commit**. Do not infer a maximum altitude from a single frame, or combine separate captures into one sortie.

## What was observed

| Source | Captured reading / event | What it establishes |
| --- | --- | --- |
| Operator cockpit capture (`70382.dng`) | Clearance **1,456.98 m**; vertical speed **+14.31 m/s**; ground speed **5.09 m/s** | A10-C was airborne with substantial terrain clearance and climbing at the captured instant |
| Cockpit capture (`70392.png`) | Clearance **921.75 m**; vertical speed **−14.19 m/s**; ground speed **15.82 m/s** | Descending with horizontal motion, not a fixed hover |
| Cockpit capture (`70394.png`) | Clearance **19.76 m**; vertical speed **+7.90 m/s**; ground speed **0.18 m/s** | Near-zero horizontal groundspeed while climbing; not evidence of a stationary-altitude hover |
| Seven-minute screen recording (`Recording 2026-11-12 212038 … .mp4`) | Example frame: clearance **1,048.81 m**; vertical speed **+0.38 m/s**; ground speed **19.85 m/s** | Airborne forward translation at high terrain clearance |
| Same recording, final seconds | At approximately **7:03**: clearance **7.61 m**, vertical speed **−15.75 m/s**. The interface subsequently reports **IMPACT**, **HARD_LANDING**, and **POWER_LIMITED** | A high-rate descent culminating in a recorded impact |

The operator reports manually coordinating canards, yaw/rudder, bank, collective and forward thrust during runway departure, climbing, turning and deceleration. Manual handling and the control interface have therefore been exercised; they are not a claim of a proven autonomous flight envelope.

## Separate, earlier A10-C fans-off study

[The 11 November A10-C takeoff study](A10C_FANS_OFF_TAKEOFF.md) documents a **scripted** live-simulator takeoff using the turbojet development variant, with the lift fans at **0 rpm**: approximately **79 m/s** at wheel-off, **~1.0 km** ground roll and **41 m radar height** at 42 s. This is distinct from the later **manually piloted** flight imagery. Do not assume identical engine, wing or lift-fan settings without the individual sortie logs.

## Outstanding engineering questions

- Preserve and index the raw run IDs, model/configuration hashes, controls and time-aligned telemetry before quoting maxima as campaign records.
- Quantify pitch/yaw/roll authority, thrust transition, lift contributions, trim, minimum controllable speed and descent recovery.
- Reconcile screenshots and local working-tree state with GitHub: A10-B remains the pinned default; A10-C cockpit development is represented by [PR #45](https://github.com/SDarkVader/-vtx-flight-sim/pull/45) and [PR #46](https://github.com/SDarkVader/-vtx-flight-sim/pull/46) as of this note.
- Landing, engine-out, crosswind and physical aerodynamic fidelity are not established by these captures.

**Test philosophy:** If it leaves the ground, moves as commanded, descends or crashes, log what happened. A failed landing does not erase a successful departure, turn or control response.
