# VTX Phantom flight test, 2026-11-03

**Pilot:** AI test pilot ("colin" authority), flying through the live interface: `/api/observe` and `/api/action`, schema `phantom-fbw-1`.

**Server:** 127.0.0.1:8766, with `VTX_DATA_ROOT=evidence/phantom/flight_campaign_20261103/`.

**Model:** every number comes from `inputs/phantom_parameters_v1.json`. That model is SYNTHETIC_UNVALIDATED, so nothing here is validated aircraft performance.

**Where the data is:**
- Calibration numbers: `evidence/phantom/phantom_calibration_20261103.json`.
- Run folders: `evidence/phantom/flight_campaign_20261103/evidence/flights/<run>/`.
- Card-to-run index: `cards.txt`.
- My decision log: `pilot_log.jsonl`.

## How it was flown

### Flight-control mode
- I flew in M2 (`attitude_vs`): attitude command and hold, vertical-speed command, and a yaw-rate pedal.
- There is no position, velocity, altitude or heading hold.
- Ground cards were flown in `rate_damping` or M0-like direct collective.

### Decision tool
- `fly.py act` sends one command that I chose.
- It then holds that command for a set time by sending empty actions, where every field means "hold". This is a zero-order hold.
- Every deliberate decision is logged with its reason.

### Keep-alive link
- `ka.py` sends empty hold actions every second of wall time (about 0.1 s of sim time), so slow decisions don't trip the lease.
- It only runs while `ka_run.txt` names the active run.
- It was added after the unplanned lease crash (X-1 below).
- It never sets a control value.

### Time scale
- 0.25 for the first sorties, then 0.1.
- The time scale is logged in each run's keys and in every action's timing block.

### Pilot loop: the C1 item-9 shortfall

| Sortie | Median interval | p95 interval |
|---|---|---|
| O/L sortie | 7.6 s | 10.4 s |
| Hop | 5.8 s | 16.7 s |

- These are sim-time intervals between deliberate decisions.
- Keep-alive p95 was 0.107 s.
- This is 25 to 80 times slower than the card target of 0.2 s at p95.

### What wasn't used
No teleport, setPose, scripted path or replayed trace was used. The analysis scripts (`analyse.py`, `build_calibration.py`) read truth logs only after each flight and were never used to pilot.

## Card results

### G: ground

**G-0 (configuration check).** Partial.
- Channels were present on every run.
- The leg load-cell CG gate is evaluated at t = 0, before the aircraft has settled on its gear, so it always reports `no_weight_on_legs` (D-3). The gear-load CG check could not be done.
- On the gear, the as-drawn aircraft sits 2.9 deg nose-up with the front oleos unloaded (D-4).

**G-1 (actuator sweeps).** Not flown separately; bench tests cover it.

**G-2 (spool-up and zeroing).**
- Generator idle is about 90 kW, which charges the buffer.
- The generator ramp limit is 0.3 P/s, so it takes about 3 s to reach 900 kW.
- Lesson: on H-1 attempt 2 I lifted off before pre-spooling, and the buffer took a 960 kW transient. After that I pre-spooled at 0.45 collective on the gear.

**G-3 (thrust and power on the gear).**

| Collective | phantom (1897 kg) T/W | phantom kW | FX-C (1734 kg) T/W | FX-C kW |
|---|---|---|---|---|
| 0.1 | – | – | 0.167 | 119 |
| 0.2 | 0.165 | 256 | 0.316 | 244 |
| 0.4 | 0.318 | 612 | 0.616 | 588 |
| 0.6 | 0.474 | 1088 | 0.925 | 1055 |
| 0.8 | **0.529 (saturated)** | 1254 | – | – |
| 1.0 | **0.529 (saturated)** | 1253 | – | – |

- As drawn:
  - The rear pods reach about 3530 N at 8480 rpm and stop there.
  - The generators are at their 1.2 MW cap.
  - The attitude-priority desaturation then cuts the front pods to about 1385 N, so total thrust is 53% of weight. **No lift-off.**
  - There were two attempts: a collective ladder, and 10 s in `attitude_vs` at +0.5 m/s commanded climb with brakes off. Run `20261103T144550-be8193`.
  - The bench claims 0.79 W for this aircraft; the live G-3 ceiling is 0.53 W (D-9).
- FX-C: thrust is linear at 1.54 W per unit collective, and the front pods carry a share of 0.458.
- My first G-3 attempt (`144211-55c7ac`) is void. A browser operator panel connected to 8766 kept resetting the collective to 0 every heartbeat (D-1), and the aircraft had been given 10 kg of fuel by a legacy default (D-2).

**G-4 (light-on-gear control checks, FX-C at 0.45 collective).**
- The PTI pulses produced the correct-sign rpm splits.
- There was almost no attitude response (0.07–0.3 deg) and no lift-off. **Pass.**

### H: in ground effect

**H-1 (first lift-off and set-down, FX-C).**
- Attempt 1 (time scale 0.25):
  - Lift-off rolled the aircraft to +2.7 deg and it drifted right at 0.7 m/s.
  - My decision delay was about 3 s of sim time, so I overshot to 2.1 m and drifted 4.6 m. This crosses the limit line, so the attempt fails.
  - Set-down was at 0.25 m/s.
- Attempt 2 (time scale 0.1, roll pre-trim):
  - Height 1.37 m, drift up to 1.6 m over 10 s, heading change 2 deg.
  - Rated **adequate** (height desired, drift adequate).
- The three consecutive passes the card asks for were not achieved.

**H-2 (IGE trims and height sweep).** Points at 1.4, 1.9, 3 and 9 m, at one heading only.
- IGE power at 1.9 m was 1234 kW; OGE power was 1210 kW.
- The ground-effect factor at 1.9 m was 1.002, so there is no measurable IGE benefit (D-16).

**H-3, H-4, H-5.** Not flown. H-3 is a blocking card, so it blocks C1.

### O: out of ground effect

**O-1 (climb).**
- Climbed at 0.5 m/s to 9 m and at 1.0 m/s to 18 m (on the hop).
- Vertical speed held within ±0.05 m/s. **Pass.**

**O-2 (OGE trim).**

| Load | Collective | T/W | Front share | Electrical power | Buffer draw | Roll stick | Hover CG vs ledger |
|---|---|---|---|---|---|---|---|
| FX-C | 0.648 | 1.000 | 0.458 | 1210 kW (71 W/N) | 310 kW | –0.13 | agrees (front share matches the -0.15 m CG) |
| FX-A | 0.706 | 1.00 | 0.460 | 1407 kW (76 W/N) | 470 kW | 0 | – |

- FX-C needs the roll stick at –0.13 because of its one-occupant lateral CG.
- One heading only.

**O-3 (steps, doublets and 3-2-1-1s, FX-C at 9–11 m).**

| Axis | Delay | Response |
|---|---|---|
| Roll | 0.07–0.12 s | 3 deg doublet peaks at 6.6 deg (overshoot about 2.2x). Step time constant 0.50 s, steady error 4%. Off-axis ratio 0.18–0.43. |
| Pitch | 0.10–0.15 s | Step overshoot 1.7x, and the attitude settles 10–18% *beyond* the command. Time constant about 1.0 s. |
| Yaw | 0.17 s | 8 deg/s doublet achieved only 4 deg/s. |
| Heave | 0.14 s | 0.51 m/s command gave 0.57 m/s. |

Against the H-4 tolerances, the attitude overshoot fails ±10%, and yaw fails.

**O-4 (frequency sweeps).** Not flown. This blocks C1 item 8.

### P: precision tasks

Not flown as scored HQTEs. The landings give informal P-6 evidence:

| Landing | Sink rate | P-6 result |
|---|---|---|
| H-1 #1 | 0.25 m/s | desired |
| O/L sortie | 0.35 m/s | desired |
| Hop | 0.40 m/s | desired |
| FX-A | 0.47 m/s | desired |

### L: low speed (FX-C, wings stowed, 9–18 m)

| Speed | Pitch |
|---|---|
| 1.6 m/s | –1.6 deg |
| 3.1 m/s | –3.6 deg |
| 4.8 m/s | –4.0 deg |
| –2.2 m/s (rearward) | +2 deg commanded |

- The trend is about –1 deg per m/s, and it is dominated by ram drag.
- Power at 4.8 m/s was 1154 kW, about 5% below hover.
- **Finding:** after pitch inputs in translation, a sustained pitch oscillation appeared: ±3–8 deg, with pitch rate up to ±10 deg/s and a period of about 2–3 s. It happened in rearward flight at a constant +2 deg command, and on the hop deceleration, where 5 deg was commanded and 8 deg was reached. No PTI was active (D-6).
- Speeds above 5 m/s and W1 (wings deployed) were not flown.

### X: crash cards

**X-1 (lease expiry), unplanned, from 3.1 m.** Run `20261103T145427-98fc81`.
- The pilot went silent in a 3.1 m hover (a usage-limit interruption).
- Lease ABORT fired at 37.07 s.
- The fans were braked from 3600 to 40 rpm in about 0.5 s, so almost no residual spool thrust was left.
- The aircraft fell freely and touched down at 7.14 m/s. That is close to the 7.7 m/s free-fall bound, so residual thrust was negligible.
- Results:
  - collision flag set;
  - peak contact force 863 kN;
  - airframe origin went to z –0.19 m, which means ground penetration;
  - `crash_ring.npz` and `lease_abort_ring.npz` were kept (D-5).
- Lesson: I added the keep-alive link.

**X-5 (hard-landing ladder, FX-A).** Rungs at 0.47, 1.75 and 2.91 m/s.
- At 2.91 m/s: oleo stroke 9.5 cm, peak foot force 17.3 kN, rebound +1.04 m/s, re-contact at 1.27 m/s.
- No hard-landing flag, because the gear limit is 3.0 m/s.
- Contact chatter produced 6 touchdown events in 0.2 s (D-14).

**X-2, X-3, X-4, X-6, X-7.** Not flown. X-4 endurance is derived instead:
- FX-C: 517 s.
- FX-A: 397 s. FX-A after the take-off rating needs an 807 kW buffer draw, which is over the 800 kW continuous limit.

## Gates

**C1 "controllable": FAIL for both variants.**
- `phantom` cannot lift off.
- `phantom-fx` fails or did not complete these items:
  - item 1: H-3/H-4/H-5/O-4 were not flown or not passed;
  - item 2: H-3;
  - items 3–6: P-1 to P-5 not scored;
  - item 8: O-4;
  - item 9: pilot loop p95 of 10–17 s against 0.2 s;
  - item 11: X-2.
- The attitude overshoot and the pitch oscillation are also handling-qualities fails.
- **Positives for `phantom-fx`:**
  - well-behaved vertical axis;
  - adequate hover;
  - four gentle landings below 0.5 m/s;
  - trim front share matches the ledger;
  - no saturation;
  - no energy residual;
  - hover power about 80% of the available 1.5 MW (generator 900 kW plus buffer peak).

**C2 "cleared for hop": not met.** C1 failed and T-1 wasn't flown, so the hop had to be flown as T-2X.

## The hop: T-2X "expected to fail" (phantom-fx FX-C)

- **Run:** `20261103T192918-14ade4`, time scale 0.1.
- **From A to B:** A is (13.7, –28.4), B is (213.7, –28.4).
- **Why I chose this destination:**
  - It is exactly 200 m due east, along the spawn heading, so the transit is pure forward flight with no turn.
  - `/api/validate` with `phantom-fx` passed it ("four-leg support … clear").
  - The terrain is flat at z 0 at both ends.
  - The obstacles nearest the track are 11–16 m to the side with tops under 12 m, so they're cleared at an 18 m cruise.
  - Alternatives I rejected:
    - (263.7, –28.4): uneven support;
    - (–236.3, –28.4): water;
    - (13.7, 221.6): valid but needs a 90 deg turn;
    - (200, 120): valid but 239 m away on a diagonal.
- **Profile:**
  - pre-spool on the gear;
  - vertical climb at 1.0 m/s to about 18 m;
  - nose down 4.5 deg, accelerating to 4.9 m/s;
  - transit for about 40 s;
  - deceleration at 5 deg commanded (8 deg reached), stopping in about 4 s;
  - hover-taxi reposition (pitch and roll oscillation seen here);
  - descent at 0.8 then 0.5 then 0.4 m/s.
- **Track:**
  - I drifted 4 m left, overcorrected, and ended 12 m right of track at the deceleration. That fails the ±3 m tolerance.
  - Height ranged 15–18.7 m, against ±1.5 m. Also fails.
- **Outcome:** `landed` ("supported stationary landing at destination").
  - Touchdown at 0.40 m/s, 1.4 m from B, heading –3 deg, attitude under 0.5 deg.
  - 116 s of sim time.
  - 131.5 MJ propulsion energy, 10.2 kg fuel, SOC from 0.90 to 0.78.
- **Caveat on "landed":** the settle detector declared the landing while the fans were still near hover thrust and the oleos were extended. It doesn't check load on the gear (D-8).
- **Classification:** T-2X consequence hop. The landing would be P-6 desired, but track and height fail. Under the card rules it does not count as a hop success.

## Lessons (pilot technique only; the physics was not changed)

1. Pre-spool the generator on the gear before lift-off.
2. Pre-trim roll at –0.13 for FX-C. FX-A needs none.
3. Decision latency decides everything. At time scale 0.25, 3 s of sim between decisions cost the H-1 attempt. At 0.1, slow loops were fine, but the hover-taxi was still sloppy.
4. A keep-alive is mandatory for an AI pilot; without it, any interruption is X-1.
5. Use small, short attitude inputs. The attitude loops overshoot about 2x, and large pitch commands start an oscillation.
6. The yaw pedal sign is easy to get backwards: +1 is nose right, while the sensor's r is positive nose-left. I got it wrong once.
7. Rule of thumb for speed: about 1 deg of nose-down per m/s.

## Simulator defects

See `research_notes/Phantom CG compensation and test flights/flight_campaign.md`, D-1 to D-18.
