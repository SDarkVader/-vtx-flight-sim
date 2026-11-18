# Phantom A10-C · fan-assisted air-braking ECU test (18 Nov 2026)

Offline engineering test, isolated worktree `vtx-a10c-airbrake-ecu-20261118`, branch
`claude/phantom-a10c-airbrake-ecu-20261118` (from `origin/main` ac9f1e7, which contains the A10-C commit 3f7fe009).
Data: `evidence/phantom/a10c_airbrake_ecu_20261118/` (indexed in its `README.md`).

Nothing live was touched. The simulator, its aircraft, its flights and checkpoints, and the primary checkout are
unchanged, and so are the aircraft identity pins. The reviewed-runtime pin was moved with the owner's
authorisation, keeping the previous runtime on record (§8). The branch was pushed for a draft PR at the owner's
request. Nothing was merged or promoted.

## 1. Objective and reference

Make the current A10-C physically fly the 9 Nov 2026 A10-B manoeuvre: 95 → 51 m/s in 6 s, peak about 0.81 g,
nose about +4°, all four pods facing down, boosters off, then a controlled decelerating turn through about 90°
ending in a hover. The manoeuvre is controlled by an ECU/FCC on board, not scripted. The pilot makes only
discrete cockpit inputs.

The reference is commit 2af24770 and `reference/phantom_a10b_20261109/` (captures/decel.json, V1–V3 telemetry
and scripts). On 9 Nov the coordination was done by a scripted test pilot (`turn_fan`: collective, pitch and
bank schedules with feedback). The aircraft had no function that did it.

**Aircraft identity, rechecked before testing (TestWorld build):**

| | Without ECU (live A10-C) | With `transition_ecu_v1` |
|---|---|---|
| Variant | phantom-a10c | phantom-a10c |
| Config SHA | 2fee0b40…7f049f | 58d12857… (new control law, so a new identity) |
| Model XML | 2fa66030…37efab | 2fa66030…37efab (unchanged: software only) |
| Parameter file | 3955457a… | 3955457a… |
| Visual | /assets/phantom-a10b-visual.glb | same |

The flat test strip changes the scene XML to 88bacb74, the same with and without the ECU. The historical A10-B
physics were not substituted. Every run is the current A10-C.

## 2. Baseline: does the A10-C have the physics?

The 9 Nov V3 `turn_fan` schedule was replayed unchanged (`tools/phantom/airbrake_baseline.py`):

| | 9 Nov A10-B | A10-B today (3ecae1a9) | A10-C today (2fee0b40) |
|---|---|---|---|
| Speed at 6 s | 51.1 m/s | 52.3 | 53.1 |
| Peak deceleration | 0.81 g | 0.79 | 0.79 |
| 90° turn | 29.4 s | 34.5 s | 34.3 s |

The airframe can do it. What it lacked was the coordination, which on 9 Nov came from the test pilot. Braking is
mostly fan ram drag (about 2.6× thrust at 95 m/s), so the fans have to carry the weight the wing gives up.

## 3. The transition ECU (what was added)

`inputs/phantom_overlays/transition_ecu_v1.json` is an opt-in overlay. Software only: no mass, geometry or
physics parameter changes.

| Function | Feedback | Actuators driven |
|---|---|---|
| Engagement (`airbrake: on`) | — | pods 90° (all four), boosters 0, vertical-speed mode, collective lever up, vertical speed 0 unless the pilot sets one |
| Lift-aware collective trim | measured non-fan vertical force m(a_z+g) − fan vertical thrust, 0.3 s filter | fan collective (4 fans) |
| Braking collective floor (0.15) | — | fans keep ram drag (the brake) and differential authority |
| Wing-unloading pitch | collective deficit below the floor | pitch attitude (−0.15 rad per unit, 1 s filter, ≤ 6°) |
| Braking attitude +4° | dynamic pressure (wing-borne weight) | stabilator/canards/fan differential through the attitude loop |
| Spoilerons (12° trailing edge up, symmetric) | wing-borne weight | ailerons: dumps lift onto the fans; 8° left for roll |
| DRS stabilator airbrake (+49° = 55°) | nose-down demand (attitude priority, 1 s filter) | stabilator |
| Turn coordination g·sinφ·cosθ/V | bank, pitch, airspeed | rudder, booster TVC, fan differential (yaw) |
| Hover drift damping (air-brake engaged only) | heading-frame ground velocity | pitch/roll attitude, 0.86° per m/s, ≤ 6° |
| Fade wing-borne → hover | dynamic pressure 50–400 Pa (9–26 m/s) | all of the above |

The physics still runs at 400 Hz and the FCC at 100 Hz. The ECU makes no random draws, so replays and
checkpoints of other aircraft stay bit-exact (tested).

**The pilot keeps control.** Stick (attitude), pedal (yaw rate), vertical speed and the collective lever keep
working while the ECU is engaged. The ECU never follows a path, holds a heading or chooses a turn.

Engaging writes its configuration into the held command, where the pilot can see and override any of it: pods
90°, boosters 0, vertical-speed mode, lever up. Releasing the air-brake (`airbrake: off`) ends the braking
functions: braking attitude, collective floor, wing unloading, spoilerons, stabilator airbrake and drift
damping. The configuration stays as it is for the pilot to change.

Lift-aware trim and turn coordination stay on whenever the ECU is fitted and the wing carries load (above
50 Pa). On the ground, or below about 9 m/s with the air-brake off, the fitted ECU changes nothing (tested
bit-exact).

**Manual control:** the Phantom manual panel (`public/phantom-controls.js`) has an **Air-brake** button. It sends
`airbrake: on/off` through `/api/action` (`phantom-fbw-1`, manual authority). Its label follows the held command
from the aircraft. It is disabled on aircraft without the ECU, and the panel feedback shows ECU state, wing-borne
weight, wing-lift estimate and attitude command. On an aircraft without the ECU the command is refused with an
`airbrake_unavailable` event. Nothing else changes for it.

## 4. Test

`tools/phantom/a10c_airbrake_test.py`: an 8 km flat strip. The wings are deployed and locked on the ground, then
the aircraft is placed at +300 m, 95 m/s, pitch +4°. Two starts:

- **reference**: the 9 Nov initial state (pods 90°, fans pre-spun to 5% of the weight, generator at take-off rating, boosters off).
- **cruise**: pods stowed, fans stopped, turbojets spooled to balance the drag. The ECU has to tilt and spool everything itself.

Input card (discrete inputs only, each logged with its cue):
1. `airbrake: on`, pitch stick centred, at t0.
2. Roll stick 2/3 at < 60 m/s (the 9 Nov cue).
3. Roll stick centred and pedal 1/2 right at < 15 m/s if the turn isn't complete.
4. Stick and pedal centred at 90° on the heading indicator, with no lead.

`--ecu off` flies the same card on the live A10-C, with input 1 replaced by its manual equivalent: pods 90,
boosters 0, vertical-speed mode, lever up, stick centred.

```bash
python tools/phantom/a10c_airbrake_test.py --start reference --ecu on  --out <results>/r5_reference_on.json
python tools/phantom/a10c_airbrake_test.py --start cruise    --ecu on  --out <results>/r5_cruise_on.json
python tools/phantom/a10c_airbrake_test.py --start reference --ecu off --out <results>/r5_reference_off.json
python tools/phantom/a10c_airbrake_test.py --start cruise    --ecu off --out <results>/r5_cruise_off.json
python -m pytest tests/test_phantom_transition_ecu.py
```

Each run writes the full 20 Hz telemetry to `.json.gz`. It covers airspeed, u, ground speed, altitude, vz,
attitude, rates, α/β, ECU state, moment demand, saturation, collective and trim. It also records the lift
estimate, fan thrust (commanded and actual), rpm, ram drag, pod tilt (commanded and actual), and the aileron,
canard, stabilator, rudder and TVC positions. Booster thrust, spool and command, aero forces and moments,
generator, buffer, delivered and unmet power, state of charge (SOC), fuel and support are recorded too.

The final runs reproduce exactly. Rerunning reference with the ECU, cruise with the ECU and reference without it
on this branch gave files identical to the recorded r5 files.

The six new ECU tests pass in about 18 s. The full Python suite passes (525), and so does the JavaScript suite
(85). The logs are in the data folder.

## 5. Results (run r5) against 9 Nov

| | 9 Nov A10-B (test pilot) | A10-C + ECU, reference start | A10-C + ECU, cruise start |
|---|---|---|---|
| Speed at 6 s | 51.1 m/s | **47.8** | 55.1 |
| Peak deceleration (1 s) | 0.81 g | **0.83 g** | 0.78 g |
| Nose while braking | ≈ +4° | **+2.8 … +4.4°** | +2.2 … +4.4° |
| Altitude excursion | ≈ +1.2 m | **−0.7 … +0.9 m** | −0.9 … +0.4 m |
| Pods | 90° | 90° (tilt error RMS 0.07°) | 0 → 90° in ≈ 1.4 s |
| Boosters | off | 0 N throughout | commanded 0; jet thrust 3.9 kN → 0.27 kN at 6 s (5 s spool-down) |
| Turn | ≈ 90°, 29 s, 480 m arc | 90.0° at release in **17.9 s**, bank ≤ 32°, \|β\| ≤ 11° (wing-borne) | 90.1° in 17.8 s, bank ≤ 32°, \|β\| ≤ 10° |
| Heading after release | ≈ 89° total | **103.6°** total (13.6° overshoot) | 103.4° |
| End state | slow drift: bank ≈ 8.5°, β ≈ −82° | **hover**: 0.009 m/s, vz −0.001 m/s, pitch 0.2°, roll 0.0° | hover: 0.015 m/s, level |
| Fan saturation / unmet power | — | 0 % / 0 W | 0 % / 0 W |

ECU commands against actuator response (reference start, whole flight):

| Actuator | RMS error | Max error |
|---|---|---|
| Pod tilt | 0.07° | 0.8° |
| Ailerons | 0.67° | 17.8° (spoileron step, rate-limited) |
| Canards | 0.43° | 12.6° (first sample) |
| Fan thrust | 167 N | 6.0 kN (spin-up from 5%) |

The stabilator airbrake reached its 55° command.

Other measurements:
- Maximum rates: p 63°/s (roll entry, the existing attitude law answering a 2/3 stick step; 64°/s without the ECU), q 4.4°/s, r 7.6°/s.
- Maximum aero drag 5.0 kN. Fan ram drag up to 13.5 kN.
- Power: peak 1.66 MW, hover 1.47 MW against a 900 kW generator, so SOC falls 0.125 per minute (0.902 → 0.819 over the 42 s flight). Fuel used 3.5 kg.

**What the ECU contributes** (same aircraft, same card, ECU off):

| | ECU on | ECU off, stick centred (r5) | ECU off, stick held at +4° (r4) |
|---|---|---|---|
| Reference start | see above | 1.24 g spike, nose −6.2°, climbs 4.2 m, turn takes 32.7 s with β up to 60° (skids, not coordinated) | 1.22 g, balloons +14.6 m, ends drifting backwards at 4.6 m/s |
| Cruise start | see above | **departure**: nose −62° within 1.4 s, fans saturated half the time, 515 kW unmet (aborted) | balloons +14.2 m, ends drifting at 4.6 m/s |

Development history: r1 departed nose-up to +68°, because the estimator started at zero, the collective went to 0
and fan authority was lost. In r2 the stabilator limit-cycled 5↔55° and the hover drift limit-cycled ±8°. r3 had
a pedal sign error in the card. In r4 an over-strong wing-unloading gain gave a −0.8° nose dip and a 1.02 g spike.
Each was fixed in the ECU or the card, never by changing the aircraft.

## 6. Verdict

**PASS for the reference start (the 9 Nov conditions).**
- Braking matches or beats the target: 47.8 against 51.1 m/s at 6 s.
- Peak 0.83 g against about 0.81.
- Nose +2.8…+4.4°.
- Pods 90° and boosters off.
- Altitude held within 0.9 m.
- A coordinated 90° decelerating turn ending in a true hover, which the 9 Nov flight did not reach: it ended in a drift.

Two remarks:
- The ECU brakes about 3 m/s harder than 9 Nov by 6 s. The plateau is 0.80 g, where 9 Nov averaged 0.75 g.
- The heading overshoots 13.6° after the pedal is centred.

**PARTIAL for the cruise start.** Everything passes except the 6-second speed: 55.1 against 51.1 m/s, because
tilting the pods and spooling the fans from rest costs about 1 s of braking, and the jets take 5 s to spool down.

## 7. Limitations (open)

1. **Endurance is set by the battery, not by height.** Hover draws about 1.47 MW against one 900 kW generator at its take-off rating, so SOC falls about 0.125 per minute. The recorded live flights bear this out. The A10-C climbs vertically past 2,500 m: 13 recorded flights went above 800 m, the highest to 3,248 m. Flight 20261117T114151-71e782 climbed at about 12 m/s to 2,564 m in about 3.7 minutes at full collective. The generator gave 900 kW and the buffer was capped at 801 kW, leaving 110–150 kW unmet, while SOC fell from 0.90 to 0.255. At about SOC 0.25 the buffer limit dropped to 200 kW, 570 kW went unmet and the aircraft lost lift. On the same figures, about 4.5 minutes of hover remain after the manoeuvre (SOC 0.82 → 0.25).
2. **Rear fans are power-limited** at about 5.6–5.7 kN at high collective. This is the hover margin, and the reason the ECU has a stick-centred braking attitude: stick plus schedule saturated the rear fans in r2.
3. **Fan ram drag acts above the CG.** It pitches the nose up between 25 and 10 m/s (+7.6° peak in the fade). This is held by the attitude loop with little margin left at higher pitch attitudes.
4. **Hover yaw stop is slow.** The existing yaw-rate law decays over about 2 s, giving a 13.6° overshoot after the pedal is centred. The law is unchanged here. A pilot leads the rollout, or a heading-hold function could be added.
5. **Flaps don't help.** At 35° they reduce drag (dFx +280 N) and are limited to 75 m/s, so the ECU doesn't use them.
6. **The stabilator airbrake's nose-up moment** (about −2 kN·m at 95 m/s) has priority logic, and gives way to nose-down demand.
7. **Hover drift damping departs from the documented "no velocity hold" rule.** It works only while the air-brake is engaged, the pilot's stick adds to it, and it is listed for review.
8. **Starts are teleported** to 300 m / 95 m/s after a ground wing deployment, not flown up to.
9. **All ECU gains are SYNTHETIC_UNVALIDATED** simulation values, each with its reason recorded in the overlay.
10. **ECU sensing is noise-free**, so the existing random sequence is untouched. It takes weight-on-wheels from contact, fan thrust from fan state and pod angle, and ground velocity from GNSS truth. Real sensor noise and lags on these signals have not been tested.

## 8. Owner decisions

- **Reviewed runtime pin: done, with the owner's authorisation (18 Nov).** The `src/vtx` edits change the runtime hash from e861234… (commit ac9f1e7, `origin/main`) to a3052315…. `inputs/flight_revisions.json` now pins a3052315…. It records e861234… and its commit under `previous_integrated_runtimes`.
  - The previous model is not lost. The A10-C and the flown revisions keep their configuration, parameter-file and visual pins.
  - Without the overlay they fly identically on both runtimes, with the same exact state digests (`analysis/same_physics_*.json`).
  - A flight running on the old runtime keeps running. If a server restarts into this build, it sets aside a checkpoint written by the old runtime instead of resuming it, as it does for any checkpoint from a different build.
- **Promotion: not done.** Fitting `transition_ecu_v1` to the live `phantom-a10c` changes its config SHA (2fee0b40 → 58d12857) and its identity pins. Until that is decided, the live A10-C has no ECU and the panel button shows as unavailable.
- **No ECU aircraft can be selected in the live game yet.** Experimental overrides can't add an overlay. A new variant would change the shared parameter file and break the existing pins. Flown revisions don't carry overlays. Flying the ECU live needs a decision on how, for example a separate flown revision with overlay support at revision level.
- The `public/app.js` change is one cache-buster string on the `phantom-controls.js` import (line 48). It doesn't touch the vehicle selector, which Codex is changing in parallel. Expect a trivial conflict at most.

## 9. Files changed

| File | Change |
|---|---|
| `src/vtx/phantom/controls.py` | `PhantomAction.airbrake`; ECU state, engagement, lift estimate, transition weight, coordination, braking attitude, floor and unloading, spoilerons, stabilator-airbrake priority, drift damping, telemetry |
| `src/vtx/phantom/plant.py` | ECU sensing (airborne, fan vertical thrust, ground velocity in the heading frame), in-flight DRS airbrake, `airbrake`/`airbrake_unavailable` events, `ecu_status()` readout, checkpoint save/restore |
| `inputs/phantom_overlays/transition_ecu_v1.json` | new overlay: all ECU parameters with units, labels and reasons |
| `public/phantom-controls.js`, `public/app.js` | Air-brake button, held-state sync, ECU feedback line; cache-buster |
| `tools/phantom/a10c_airbrake_test.py`, `tools/phantom/airbrake_baseline.py` | reproducible test and 9 Nov baseline replay |
| `tests/test_phantom_transition_ecu.py`, `tests/test_operator_controls.mjs` | opt-in identity, refusal without the ECU, engagement and release, dormant-ECU bit-exactness, checkpoint continuation, braking regression; panel held state |
| `inputs/flight_revisions.json` | reviewed runtime repinned to a3052315…; the previous runtime e861234… recorded with its commit |
| `evidence/phantom/a10c_airbrake_ecu_20261118/` | run telemetry, baselines, analysis and its scripts, test logs, checksums |
| `docs/phantom/A10C_AIRBRAKE_ECU_TEST_20261118.md` | this report |
