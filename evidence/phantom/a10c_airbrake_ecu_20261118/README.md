# Phantom A10-C air-braking ECU test: data (18 Nov 2026)

The data behind `docs/phantom/A10C_AIRBRAKE_ECU_TEST_20261118.md`. Everything was flown offline in TestWorld, in
the isolated worktree on branch `claude/phantom-a10c-airbrake-ecu-20261118`. No live simulator, live flight or
checkpoint was touched. The only live data used is one recorded flight and the flight summaries, read only
(see `analysis/`).

| Folder | Contents |
|---|---|
| `runs/` | Runs of `tools/phantom/a10c_airbrake_test.py`. Each `.json.gz` holds the identity (variant, config, overlays, model XML), the mass, the input card (every input with the cue that triggered it), events, the full 20 Hz telemetry and the metrics. Each `.out` is the console summary. |
| `baseline/` | The 9 Nov `turn_fan` schedule replayed unchanged on today's A10-B and A10-C (`tools/phantom/airbrake_baseline.py`). |
| `analysis/` | Outputs of the scripts in `scripts/`. |
| `scripts/` | Analysis scripts. Paths are taken from the command line or from the repository root. |
| `tests/` | Test-suite logs. |
| `SHA256SUMS` | Checksums of every file here. |

## Aircraft and runtime identity

| | |
|---|---|
| Aircraft | `phantom-a10c`. Config 2fee0b40… without the ECU (the live aircraft). 58d12857… with the `transition_ecu_v1` overlay, which is used in tests only and not promoted. |
| Model XML | 2fa66030… with or without the ECU (software only). The flat test strip makes the scene 88bacb74…. |
| Reviewed runtime | a3052315… on this branch. The previous runtime e861234… (commit ac9f1e7) is kept in `inputs/flight_revisions.json` under `previous_integrated_runtimes`. |

## Runs

| Run | Produced by | Outcome |
|---|---|---|
| `r1_reference_on` | first ECU draft | Departed nose-up to +68°: the lift estimate started at zero, the collective went to 0 and fan authority was lost. |
| `r2_reference_on` | second draft | Stabilator limit-cycled 5↔55°; hover drift limit-cycled ±8°. |
| `r3_reference_on` | third draft | Pedal sign error in the input card. |
| `r4_{reference,cruise}_{on,off}` | overlay with wing-unloading gain 0.6 rad per unit collective and a 0.5 s filter; the no-ECU card held the stick at +4° | 1.02 g spike and a −0.8° nose dip with the ECU; the no-ECU runs balloon by about 14 m. |
| `r5_{reference,cruise}_{on,off}` | this branch (gain 0.15, 1.0 s filter; the no-ECU card has the stick centred) | The results in the report. |

r1 to r4 came from intermediate code that was never committed. They are kept as the development record and can't
be regenerated from this branch.

r5 does regenerate from this branch. Rerunning reference with the ECU, cruise with the ECU and reference without
it gave files identical to these: same telemetry, input card, events and metrics.

`r5_cruise_off` is short (19.6 KB). Without the ECU the cruise start departs nose-down to −62° within 1.4 s, so
the run is aborted.

## Analysis

| File | Script | What it shows |
|---|---|---|
| `actuator_power_summary.jsonl` | `actuator_power_summary.py` | ECU command against actuator response: pod tilt, ailerons, canards, fan thrust. Also maximum rates, aero moments and drag, fan ram drag, power, generator, SOC, hover power and fuel. Covers the r5 runs (except the aborted cruise run without the ECU) and the r4 runs with the ECU. |
| `unload_sweep.txt` | `unload_sweep.py` | How the braking responds to the unloading gain, its filter, the spoileron angle and the offset limit (chosen: 0.15, 1.0 s, 12°, 6°). This is braking only: 8 s with the stick centred and no turn inputs. Its peak uses a 0.2 s window, so it reads higher than the report's 1 s figure, and its 6 s speed differs slightly from the full input card. |
| `same_physics_previous_runtime.json`, `same_physics_this_runtime.json` | `same_physics.py` | The previous model is unchanged. Three cases give identical exact state digests on the previous runtime (e861234…, commit ac9f1e7) and on this one (a3052315…): the A10-C without the ECU (vertical take-off, manoeuvre, vertical-speed hold); the pinned flown revision `phantom-a10c-runway-20261112` (road start, wing deployment, runway roll); and the airborne manual air-braking card. Each digest covers positions, velocities, actuator states, fuel, the random-generator state and buffer charge. |
| `live_flight_20261117T114151-71e782_power.txt` | `live_flight_power.py` | Read-only extract of the recorded 17 Nov live A10-C flight that climbed vertically to 2,564 m: fan thrust, pod tilt, generator, buffer, SOC and unmet power through the climb, and the loss of lift once the buffer dropped to 200 kW at SOC 0.25. The step log's SHA-256 is on the first line. |
| `high_altitude_flights.txt` | `high_altitude_flights.py` | Recorded flights above 800 m: 13, all `phantom-a10c`, the highest at 3,248 m. |

## Tests

- `tests/py_tests_before_repin.out`: full Python suite before the repin. 519 passed and 6 failed, all six on the reviewed-runtime pin (e861234… expected, a3052315… loaded).
- `tests/py_tests_after_repin.out`: after the owner-authorised repin. 525 passed.
- `tests/js_tests.out`: JavaScript suite on the final tree. 85 passed, including the new air-brake button test.

## Reproduce

From the repository root with the project's Python environment. On Windows, give paths Windows Python can read,
not Git Bash's `/tmp`.

```bash
python tools/phantom/a10c_airbrake_test.py --start reference --ecu on  --out out/r5_reference_on.json
python tools/phantom/a10c_airbrake_test.py --start cruise    --ecu on  --out out/r5_cruise_on.json
python tools/phantom/a10c_airbrake_test.py --start reference --ecu off --out out/r5_reference_off.json
python tools/phantom/a10c_airbrake_test.py --start cruise    --ecu off --out out/r5_cruise_off.json
python tools/phantom/airbrake_baseline.py phantom-a10b out/baseline_a10b.json
python tools/phantom/airbrake_baseline.py phantom-a10c out/baseline_a10c.json
```

```bash
D=evidence/phantom/a10c_airbrake_ecu_20261118
python $D/scripts/actuator_power_summary.py $D/runs/r5_reference_on.json.gz $D/runs/r5_reference_off.json.gz $D/runs/r5_cruise_on.json.gz $D/runs/r4_reference_on.json.gz $D/runs/r4_cruise_on.json.gz
python $D/scripts/unload_sweep.py
git archive ac9f1e72b5a5fc9830dd13554885bc48537400a1 src inputs evidence/phantom evidence/source | tar -x -C <empty folder>
python -I $D/scripts/same_physics.py <that folder>
python -I $D/scripts/same_physics.py .
python $D/scripts/live_flight_power.py "$LOCALAPPDATA/VTX/checkouts/vtx-flight-sim-d1e44131/evidence/flights/20261117T114151-71e782"
python $D/scripts/high_altitude_flights.py "$LOCALAPPDATA/VTX" <other data roots>
python -m pytest -q tests
node --experimental-loader ./tests/vendor-three-loader.mjs --test tests/*.mjs
```
