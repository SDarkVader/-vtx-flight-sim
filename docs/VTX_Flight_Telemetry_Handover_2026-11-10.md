# VTX Phantom flight telemetry: engineering handover

**Prepared:** 10 November 2026  
**Purpose:** Preserve the evidence, source directories and test priorities for the next A10-B PC session.  
**Scope:** The 6 November A10-A 600 m and 300 m flight records, the 10 November cloud A10-B connector flight, and the 9 November A10-B engineering record.  
**Method:** Read-only inspection of original local events.jsonl and phantom_steps.csv.gz on Steve_PC; reported A10-B cloud-flight figures are identified separately.

## 1. Executive findings

- **A10-A reached 600.811 m in 100 Hz samples** (600.5806 m in the flight summary). It spent **124.62 sampled seconds above 500 m** in two intervals, including **122.34 continuous seconds** with significant horizontal translation. This is high-altitude fan-supported flight, not a stationary position hold for that entire interval.
- That run contains **32 pilot_decision events, 32 control_applied events, 10,014 observations and 52,405 telemetry samples** over **524.06 simulated seconds**. Its logged authority is **manual**, meaning the interface's authority channel, not proof of the human or AI actually providing instructions.
- **A10-A held approximately 300 m** in a separate run: from **t=208.14 to 225.43 s**, altitude **299.72–299.89 m**, **5.46 m** of horizontal displacement. Its raw applied controls carry **colin** authority, despite the earlier register describing this run as manual. It logged **29 decisions and 29 applied controls**.
- **A10-B's 10 November connector flight** is a different revision and objective: **77 seconds, five AI decisions, 20 m reported peak against about 8 m intended, landing about 20 m west of departure**. The original cloud events and sample telemetry were **not located** in the accessible PC archives. These A10-B metrics come from the session report, not locally verified raw samples.
- The 600 m A10-A run later encountered **power saturation, attitude divergence and an uncontrolled descent** during booster experiments. Preserve both its demonstrated high-altitude operation and its later instability; the terminal status is **'airborne attempt ended'**, not a completed landing.

## 2. Flight comparison and evidence strength

| Item | A10-A high-altitude | A10-A 300 m | A10-B AI connector |
|---|---|---|---|
| Run ID | 20261106T101512-085037 | 20261106T080610-01457b | 20261110T193941-97e128 |
| Aircraft/configuration | phantom-fx / 70089cca | phantom-fx / 70089cca | phantom-a10b / 3ecae1a9 |
| Runtime source (prefix) | e7351705 | cd9d671d | Not verified from local archive |
| Recorded authority | manual | colin in raw applied commands | AI pilot ('colin') in cloud report |
| Duration (simulated) | 524.06 s | 366.65 s | 77 s reported |
| Maximum altitude | 600.811 m raw; 600.5806 m summary | 299.887 m raw; 299.942 m summary | 20 m reported |
| Decisions / applied controls | 32 / 32 | 29 / 29 | 5 reported / raw log unavailable |
| Observation entries | 10,014 | 7,020 | 1,490 reported |
| Recorded conclusion | Airborne attempt ended | Collision | Landed ~20 m west of start |
| Evidence | Local raw events + 100 Hz telemetry | Local raw events + 100 Hz telemetry | Cloud-session written report |

**Comparison caution:** The A10-A source and A10-B revision differ; mission, controller, authority, physical parameters and energy/initial state are not matched. The A10-B flight is evidence that the connector operated a complete VTOL flight, not an altitude-envelope comparison.

## 3. Original 600 m flight: control and telemetry reconstruction

**Run:** 20261106T101512-085037. Environment stage1-valley, time_scale 0.5, recorded wind [0,0,0] m/s. The log states 400 Hz physics, 100 Hz aero/sample data, 20 Hz sensors and a 20 ms simulated command transport delay. Accepted targets are held between commands. Config 70089cca; runtime e7351705; software commit f22e4efa.

| Sim time | Applied decision or experiment | Measured response |
|---|---|---|
| 122–158 s | Engine on; collective ramped from 0.12 to 0.75 | On ground; fans spun up progressively |
| 162.46 s | Reduce collective to 0.68 after liftoff | 5.51 m; vertical speed +2.41 m/s |
| 186.70 s | Collective 0.73 after descent-recovery manoeuvre | 52.39 m; vertical speed +11.23 m/s |
| 198.66 s | Engage attitude mode and neutral pitch target | 158.05 m; pitch -17.10 degrees |
| 266.38 s | Deploy wings, retract legs, reduce collective to 0.40 | 493.25 m; +8.91 m/s before command takes effect |
| 273.92 s | Increase collective to 0.64 | 446.72 m; -18.50 m/s |
| 347.41 s | Reduce collective and request level attitude | 534.49 m; pitch +18.39 degrees; +6.79 m/s |
| 358.74 s | Vertical-speed assist, target +1.0 m/s | 504.69 m; vertical speed -2.20 m/s; applied collective 0.973 |
| 390.54 s | Hold attitude/VS; introduce 10% boosters | 536.65 m; +1.00 m/s; near-level pitch |
| 433.11 s | 15% symmetric boosters; maintain target | 579.10 m; +1.00 m/s; near-level pitch |
| 454.17 s | Full symmetric boosters | 600.10 m; +1.00 m/s |
| 455.42 s | Telemetry peak | 600.811 m; vertical speed +0.012 m/s; unmet power ~779 kW |
| 462.88 s | Abort boosters, vertical-speed zero, attitude mode | 529.73 m; -16.75 m/s; roll -33.5 degrees |
| 482.69 s | Recovery: rate damping, collective 0.68 | 227.23 m; -34.38 m/s; power limited |

**Above 500 m:** t=267.36–269.62 s (2.26 s), and t=342.33–464.67 s (122.34 s). During the long interval the sampled horizontal displacement was approximately 410.22 m, so it is not evidence of stationary hover for all 122 seconds. During t~390–433 s, vertical speed was controlled close to +1.0 m/s and front/rear fans ran near 3,810/4,135 RPM. Generator output was near 900 kW, buffer near 380 kW, with unmet power zero at the t=390.54 s sample. At the peak, generator was ~600 kW, buffer ~905 kW and unmet demand ~779 kW. The flight later deteriorated during the high-power booster test. Its terminal label does not erase prior flight results.

## 4. Original 300 m run: stable height and forward-control experiment

**Run:** 20261106T080610-01457b. The 17.29-second interval at t=208.14–225.43 s remained within 299.72–299.89 m altitude and shifted 5.46 m horizontally. At ~219 s the logged vertical-speed target was 0, applied collective approximately 0.702, front fans around 3,800 RPM, rear fans around 4,125 RPM; generator ~900 kW and no unmet power.

The pilot first climbed toward 100 m (2.0 m/s target), corrected the altitude, then climbed toward 300 m, stepped down to 0.5 m/s and commanded a zero vertical-speed hold. At t=208.04 s the pilot retracted legs, deployed wings/canards and prepared for forward flight. From t=218.91 s, symmetric boosters were used for progressive forward acceleration; at t=261.94 s full booster power was commanded. By t=269.43 s unmet power was ~409 kW and pitch had reached +28.6 degrees. Later tests included modest fan tilt and canard corrections. The run ended in a collision after marked loss of attitude and altitude control.

**Raw authority discrepancy:** A10-A register says manual; events.jsonl has an authority_change at t=0 from manual to colin, and all 29 control_applied records identify colin. Preserve the difference rather than silently changing the register.

## 5. A10-B configuration from 9 November engineering record

**Model:** phantom-a10b / config 3ecae1a9; prior A10-A config 70089cca. **Mass:** ~1,933 kg. **Wheel-fan system:** four fans of 6.55 kN each, thrust-to-weight ~1.38. **Hover demand:** approximately 1.3–1.4 MW. **Electrical supply:** 900 kW generator for up to 300 s, 600 kW continuous, 80 kWh buffer. **Wings:** 7-degree incidence, 4.858 m span. A10-B adds hull-lift modelling, road suspension, wheel drive limits, deployment guard and flight-control effectors. It has demonstrated VTOL hover, fan-assisted braking and a decelerating 90-degree turn in scripted MuJoCo tests; **fans-off wing-borne flight and rolling rotation remain unresolved** in that record.

The 9 November document flags a possible unified-launcher identity bug that forces P6 on every variant, potentially changing A10-B's configuration ID from 3ecae1a9 to 71bb4a67. **Check the current launcher rather than assuming this remains unfixed.** The original A10-B flight was via the cloud connector, not a PC voice test; voice was not demonstrated by that session.

## 6. File locations and provenance

### Primary folders independently opened on PC

- **600 m original raw flight:** C:\Users\steve\Documents\Github\vtx-flight-repair-data\evidence\flights\20261106T101512-085037\
- **300 m original raw flight:** C:\Users\steve\AppData\Local\VTX\unified-live\evidence\flights\20261106T080610-01457b\
- **Current unified PC worktree:** C:\Users\steve\Documents\Github\vtx-three-panel-20261110\
- **Live runtime flight archive root:** C:\Users\steve\AppData\Local\VTX\unified-live\evidence\flights\

Both recovered original flight directories contain metadata.json, summary.json, events.jsonl, phantom_steps.csv.gz, phantom_parameters.json, phantom_ledger.json and model.xml. The 600 m original contains pilot-before.json as well. **Read-only examination:** No original flight data was edited.

### Additional source roots documented in the 8 November A10-A flight register

- 4 November backup: C:\Users\steve\Documents\VTX-flight-logs-backup\
- Fresh 5 November runtime: C:\Users\steve\AppData\Local\VTX\unified-fresh-20261105\evidence\flights\
- Earlier Git checkout evidence: C:\Users\steve\Documents\Github\-vtx-flight-sim\evidence\flights\
- 6 November runway runs: C:\Users\steve\AppData\Local\VTX\unified-a10-20261106\evidence\flights\
- 7 November cockpit QA: C:\Users\steve\AppData\Local\VTX\dashboard-cockpit-qa-20261107\evidence\flights\

Those supplemental locations are **register references**; they were not all separately re-audited during this handover.

### Repository and reference documents

- GitHub PR #39: https://github.com/SDarkVader/-vtx-flight-sim/pull/39 — connector and 10 November A10-B cloud sortie; do not treat passing CI as a completed PC/voice test.
- 8 November: VTX_Phantom_A10A_Flight_Register_2026-11-08.pdf — 72-run A10-A index; its page 9 maps the source-directory codes.
- 9 November: VTX_Phantom_A10-B_Flight_and_Engineering_Record_2026-11-09.pdf — A10-B design, test campaign, power/actuator specifications, limitations and configuration.
- The original 10 November A10-B cloud run events.jsonl and 100 Hz flight trace were not found on the PC. The cloud session report describes five decisions and 1,490 observations, but there is no local raw sample to compare actuator and power traces directly.

## 7. Tomorrow's test plan — suggested, not pass/fail criteria

1. Open the unified launcher from the PC worktree. Confirm actual aircraft variant, configuration SHA, model XML / parameter SHA, runtime source SHA and whether the P6 overlay changes A10-B identity. Avoid confusing launch success with physics-runtime selection.
2. Establish a new timestamped run and preserve metadata.json, events.jsonl, phantom_steps.csv.gz and summary.json. Note authority (manual/colin), time_scale, wind, fuel/energy, position and initial attitude. Retain failures, aborts and partial runs without reclassification.
3. Demonstrate A10-B's vertical control at a chosen safe test altitude. Log each issued and applied action, its timestamp, commanded and measured vertical speed, pitch/roll/yaw, collective, each fan's RPM/thrust, generator/buffer power, state of charge and unmet power. Compare against the 300 m A10-A near-level interval.
4. If proceeding to higher altitude, separate sustained VTOL/climb, wing deployment and booster/forward-acceleration phases in the log. The A10-A 600 m run shows that a level attitude and high altitude can coexist with horizontal translation, while power demand and booster transitions can destabilise the aircraft.
5. Run the connector and voice interface as distinct checks. The cloud MCP sortie establishes typed conversational control; it does **not** establish working PC voice control.
6. Archive every run and generate a concise per-run evidence record: flight ID, model/config/runtime identity, objective, commands applied, time series, observed behaviour, terminal event and open engineering questions. Do not overwrite the historical A10-A baselines.

**Bottom line:** The raw logs substantiate the earlier 300 m near-level hold and the 600 m high-altitude operation. They also identify exactly where commanded collective, vertical-speed control, boosters, fan loading and electrical limits diverged. The next useful evidence is a raw A10-B PC sortie logged under its pinned configuration, not another summary without its samples.