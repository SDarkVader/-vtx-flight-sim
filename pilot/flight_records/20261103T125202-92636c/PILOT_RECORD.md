# Pilot's record — R6 flight to B

**Date:** 3 November 2026  
**Run:** `20261103T125202-92636c`  
**Aircraft:** P0-V4A R6, simulator physics revision `audit-fixes-20261103-r3`  
**Purpose:** Test the recovered Argon control logic with the revised cabin gimbal, hover near 10 m, fly from A to B, and descend.

## Setup

Departure (east, north) was (0, 0) m and destination B was (-50, 20) m in the Stage 1 valley. Configuration was R6, 10 kg starting fuel, 1,200 rpm reference, 300 kW engine limit, critical-damping proposal gear, constant air density and zero steady wind. The cabin's powered level control and passive gimbal damping were enabled. The separate experimental rate-assist wire was off; an external pilot ran the recovered Argon-based attitude, position, yaw and altitude control logic through simulator commands. Time scale began at 0.25× and changed to 0.5× for transit and landing.

The four archived Python files are the exact phase-specific pilot scripts used on this sortie, retained as evidence, not an installed default controller. They contain hard-coded connection details and scripted phases and must not be mistaken for a general flight-control system. The pilot briefly paused the physical clock for transfers between hover, transit, descent and settling control. The original Argon script is also retained under `tools/argon_reference/`.

## Flight and outcome

The rotors were spooled at zero collective and the aircraft lifted off, climbed to a peak instrumented radar clearance of **10.207 m** and hovered. It then flew toward B, briefly overshot, settled near the destination, and descended at approximately 0.18–0.22 m/s. At touchdown the six gear legs showed compression. The last observation placed the aircraft at approximately (-47.67, 21.11) m: **2.58 m from B**, with horizontal speed approximately 0.01 m/s and no warning lamps.

The simulator summary classified the sortie as **“airborne attempt ended”**, because its automatic landing criterion requires the aircraft to settle within 2 m of the destination. Thus six-gear ground contact was observed, but the simulator did not award its formal landing outcome. Maximum non-gear impact force recorded was zero. Total simulated duration was 200.215 s, with about 4.391 kg of fuel used.

Across 3,837 recorded observations, for samples with radar clearance above 1 m, the maximum absolute airframe roll or pitch was 0.511° and the maximum absolute cabin roll or pitch was 0.271°. These are sampled sensor values, not continuous extrema. No warning lamps were recorded in those observations.

## Evidence and limits

`metadata.json`, `summary.json`, and the exact MuJoCo `model.xml` are saved with this record. The full compressed event log is at `evidence/flights/20261103T125202-92636c/events.jsonl.gz` in this worktree. Earlier models and flight records remain intact. This is a conditional R6 simulator result, not a flight test of the Phantom A10 or a demonstration of real aircraft performance. The Argon pilot is not yet installed as the simulator's default stability controller.
