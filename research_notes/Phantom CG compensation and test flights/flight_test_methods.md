# Flight-test and calibration methods for the VTX Phantom's first hover and low-speed campaign (simulator test cards, logging specification, model validation, `phantom` vs `phantom-fx`)

*Research dates: 2026-11-02 to 03. Scope: the VTX MuJoCo simulator only. No real-flight safety or airworthiness claim is made or implied. Phantom numbers marked "indicative" were computed in this research from the repo's declared or SYNTHETIC values and from textbook momentum and lift theory; they are planning numbers, not validated data.*

*Owner direction (relayed by the coordinator on 2026-11-03), applied throughout:*
- *Crashes are acceptable and are treated as data ("failure is a great teacher"), within a structured build-up.*
- *The cards compare two simulator variants:*
  - *`phantom`, the as-drawn baseline;*
  - *`phantom-fx`, a feasibility design point with a nose battery and avionics, sized propulsion and, later, wings at a common height.*
- *Testing progresses to a hop to another map location once the criteria are met.*

*No `phantom-fx` parameters exist in the repository yet (searched 2026-11-03), so fx-specific figures below are sensitivities, not values. Feet and knots from sources are converted to SI (1 ft = 0.3048 m; 1 kt = 0.5144 m/s).*

## 1. Build-up sequence and abort (knock-it-off) criteria, adapted to a simulator with a slow LLM pilot

### Takeaway
Real eVTOL programmes expand the envelope block by block: ground, hover, low speed, transition. They check simulation-vs-flight correlation before each harder block. The VTX campaign should keep that order but has three needs real programmes don't share:
1. **A slow pilot.** At 0.2–2 decisions per second, the pilot can only fly through disclosed FBW attitude/vertical-speed augmentation and a slower simulation clock.
2. **A 5 s command lease.** When it expires the server feathers collective and idles the engine, with no rescue.
3. **A small energy buffer.** It may allow only tens of seconds to minutes of hover.

Crashes are acceptable data, so aborts split into two kinds. *Data-validity stops* end a point because its data can't be interpreted. *Consequence events* let the physics run, record to rest, then analyse and retry. A one-variable-at-a-time build-up still matters, because a crash only teaches something when exactly one thing changed since the last success.

### Cited Findings
- **Eve (2025–26), building-block expansion.** Eve described a "building-block" strategy: expand the envelope progressively and validate simulation predictions against flight data before more demanding phases.
  - **Hover and low-speed block:** 59 flights, about 2.5 h, more than 100 test points.
  - **Speed steps:** first below 15 mph, then about 23 mph ground speed with simultaneous four-axis manoeuvres. Peak height was 215 ft (65 m) and the longest flight 3 min 48 s.
  - **What was validated:** control laws, downwash, thermal behaviour and the propulsion model at low speed; aero and loads models at ~23 mph.
  - **Firsts:** autoland and a "simplified fly-by-wire mode" (a secondary control layer).
  - Transition flights were to follow — [Aerospace Testing International](https://www.aerospacetestinginternational.com/news/eve-evtol-completes-hover-and-low-speed-tests.html)
- **Archer (2021).** The first hover was followed by "hover expansion", then transition envelope expansion, with the envelope widened at increasing climb/descent rates and airspeeds — [Archer press release](https://s206.q4cdn.com/823642595/files/doc_news/Archer-Takes-to-the-Skies-with-First-Hover-Flight-of-Maker-Aircraft-2021.pdf); [CompositesWorld](https://compositesworld.com/news/first-hover-flight-takes-archer-aviations-maker-aircraft-to-the-skies)
- **Judging a build-up.** The Flight Test Safety Committee suggests two criteria for whether a build-up is appropriate and complete: test-point execution complexity, and the aircraft's attitude/behaviour at the end of each point — [Flight Test Safety Fact 21-01](https://flighttestsafety.org/images/Flight_Test_Safety_Fact_21-01edit.pdf). Its card-creation best practice builds cards from standard references, a configuration section and the pilot-checklist matrix, with test conductors finalising each card — [FTSC card creation](https://flighttestsafety.setp.org/images/stories/best-practices/crdcreat1.docx)
- **Automated test cards.** An automated-test-card patent describes cards with initial configuration, initial conditions, limits and action lists. Status is determined by comparing recorded parameters against limits and targets — [US patent 12515814](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12515814)
- **Small-UAS example.** Cards carry explicit "knockoff criteria": loss of control, loss of telemetry and battery failsafes mean land immediately. Another card sets a 10 V battery threshold and a 5-min flight-time limit — [UWARG test cards](https://uwarg-docs.atlassian.net/wiki/x/NgNUk). This is one team's practice, not a standard.
- **Ground-based thrust calibration.** Helicopter hover-performance testing uses a vertical thrust stand or tethered hover. Thrust = gross weight + load-cell cable tension. IGE/OGE data were taken at skid heights 2–60 ft, with free hover at 100 ft to confirm OGE, in winds under 3 kt — [DTIC AD0901652](https://apps.dtic.mil/sti/pdfs/AD0901652.pdf); [DTIC AD0785000 test manual](https://apps.dtic.mil/sti/pdfs/AD0785000.pdf). A tethered hover varies effective weight without ballast; the load cell is accurate to about 10 lbf, and cable length sets height (10–100 ft) — [ITPS Canada](https://itpscanada.com/video-of-tethered-hover-test-in-bell-206/)
- **Live piloting contract: augmentation.** Colin must fly through the same FBW interface as a human. A "disclosed control allocator or limited augmentation" is allowed, but a "flight-perfect autopilot, invisible stabilizer and direct pose/velocity/force injection are forbidden". A slow AI interface "may require substeps and limited control augmentation", and pilot-action rates, zero-order-hold/failsafe behaviour, latency and coupling must be documented. There is no automatic rescue. Canned inputs in physics unit tests are "not a flight demonstration" — [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- **Failures are required evidence.** The contract's acceptance demonstration must include "at least one genuine failure/incorrect input with consequential physics", followed by pilot adaptation, "not a concealed reset or arbitrary tuning of physical parameters" — [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). Map missions "may fail at any phase"; real ground reaction, impacts, loss of control, energy limits and rotor constraints determine the outcome — [MAP_TO_MAP_FLIGHT_CONTRACT.md](../../docs/MAP_TO_MAP_FLIGHT_CONTRACT.md)
- **Phantom test plan on failure.** A manual pilot must be able to "land or crash naturally". One stopped pod "may make failure inevitable". "Disappearing crashes" are a rejection criterion — [TEST_PLAN.md](../../docs/phantom/TEST_PLAN.md)
- **Station crash handling.** A recorded crash permits up to five automatic restarts by default, with a cooldown, each retrying the retained mission at departure in neutral idle. A server restart can't resume mid-air physics; such sorties are recorded as interrupted — [PERSISTENT_PILOT_STATION.md](../../docs/PERSISTENT_PILOT_STATION.md)
- **Server timing.**
  - Commands are applied at `t + 0.02 s` sim.
  - If no command arrives for more than **5 s of simulated time**, the server sets engine 0 and collective 0 and logs `command_lease_expired`, "feather collective, engine idle; no flight rescue".
  - Physics steps at DT = 0.0025 s (400 Hz).
  - Sources: [live_server.py](../../src/vtx/live_server.py); [aircraft.py](../../src/vtx/aircraft.py)
- **Lab rates.** Physics runs at 400 Hz, aero at 100 Hz and sensor observations at 20 Hz. "Agent mode uses a slower clock to accommodate reasoning latency" — [LIVE_LAB_IMPLEMENTATION.md](../../docs/LIVE_LAB_IMPLEMENTATION.md). `time_scale` (sim s per wall s) ranges 0.01–1 — [live_server.py](../../src/vtx/live_server.py)
- **Argon's calibrated sorties were flown at controller rate, not LLM rate.**
  - Samples and commands are about 0.05 s apart in sim time, with apply lag about 0.042–0.048 s.
  - The 10 m climb run logged 6,700 decisions in 197.3 sim-s / 336 wall-s and ended in "collision".
  - The report publishes PID-type gains.
  - Sources: [argon_live_stability_calibration.json](../../evidence/argon_live_stability_calibration.json); [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md)
- **LLM-rate data point.** The Raymond "flight two" recovery run (`20261101T152613-3de759`) made 98 decisions in 50.27 sim-s / 205.4 wall-s, about 0.5 decisions per wall-second and an average clock ratio of about 0.25. It left the ground, reached a 4.92 m maximum and ended in collision. The log adds that existing records must be reviewed before saying who made which decisions. The earlier flight-two mission (`20261101T151650-a47d96`) was created with time scale 0.05 and stability assistance 0; the recovery run's own settings aren't stated — [RAYMOND_COCKPIT_LOG_2026-11-01.md](../../docs/RAYMOND_COCKPIT_LOG_2026-11-01.md)
- **Existing assist.** The current experimental assist is body-rate damping on collective pairs only: gain −0.04° per °/s, capped at ±0.5°, with no yaw. It is opt-in, reported in `observation.assistance_applied`, and "not certified or established as beneficial" — [training_assist.py](../../src/vtx/training_assist.py); [PERSISTENT_PILOT_STATION.md](../../docs/PERSISTENT_PILOT_STATION.md)
- **Argon spool-up lesson.** Hold zero collective and zero tilt until mean rpm ≥ 1,180 and max |tilt feedback| ≤ 1.0° before lift-off; this removes ground tip-over moments during spool-up — [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md)

### Inferences
- **Decision rate vs. what must be stabilised.** An LLM at 0.2–2 decisions per wall-second can't provide the 20–35 Hz attitude stabilisation the Argon sorties used, so attitude and vertical-speed stabilisation must sit in a disclosed FBW layer. The LLM closes only the slow loops: position, velocity, heading targets and task sequencing. NASA used the same split in piloted eVTOL evaluations (ACAH/RCDH/RCHH/TRC response types; see §4).
- **Recommended FBW mode set** (identical in both variants and disclosed in the versioned action schema):
  - **M0 DIRECT:** inceptor → allocator → per-pod thrust/tilt. No feedback; ground cards only.
  - **M2 ACAH–VSC–RCDH (default airborne mode):**
    - roll/pitch attitude command, attitude hold;
    - vertical-speed command without height integral, so height can drift;
    - yaw-rate command, direction hold;
    - no position or velocity hold.
  - **M3 TRC:** research only, reported separately and not counted toward "controllable".
  - Gains may differ per variant only if each variant's tuning is disclosed and logged. Otherwise the variant comparison mixes airframe and control-law effects.
- **Time scale as the main lever.** Choose `time_scale` so the decision interval *in sim time* is:
  - ≤ 0.2 s for MTE, landing and approach cards;
  - ≤ 0.5 s for trim shots and PTI monitoring;
  - ≤ 1 s for ground cards.

  With a 2 s wall decision interval, ts ≤ 0.1 gives 0.2 s; with 5 s, ts ≤ 0.04. At ts = 0.1 the 5 s sim lease is 50 s wall; at 0.05 it is 100 s. Physics is unchanged in sim time, so ADS-33/HQTE time tolerances apply unscaled in sim seconds.
- **Two kinds of stop** (consistent with "crashes are data" and "no rescue"):
  - **(D) Data-validity stops.** The test point ends and is flagged invalid; the airframe carries on under the pilot's held command. Triggers:
    - lease expiry, except on card X-1, which studies it;
    - observation age above 1 s sim, or decision interval above twice the card plan;
    - a logging gap;
    - a PTI timing fault;
    - the wrong variant or configuration loaded;
    - `scheduler_backlog_s` above 0.1 s.
  - **(C) Consequence events.** The simulation is never stopped for these. On identification cards the PTI stops at the limit line so the record stays near-linear, then the pilot attempts recovery. On task and boundary cards nothing stops; the outcome (recovery or crash) is the data.
  - **Limit lines** (proposed) for either kind:
    1. Roll or pitch beyond ±15° (±10° on IGE cards).
    2. Roll/pitch rate above 30°/s, or yaw rate above 20°/s.
    3. Unintended height below 0.3 m (IGE) or 5 m (OGE), or sink above 2 m/s within 10 m AGL.
    4. Outside the card box (twice the adequate tolerance).
    5. Any effector saturated or rate-limited for more than 0.5 s, or fan-speed droop above 3%.
    6. Power above 95% of available for more than 1 s, buffer at joker or bingo, any fault or protection event, or any IMPACT lamp.
    7. A first-point response whose sign is opposite to the model prediction or whose magnitude is off by more than 50%.
- **Crash protocol** (proposed):
  1. **Capture:** the server crash record plus a 20 s pre-event ring buffer of truth channels at 400 Hz.
  2. **Classify:** LOC-I (attitude divergence), hard landing (contact sink > 2.0 m/s), tip-over on gear, ground or obstacle strike, energy exhaustion, lease expiry, actuator or propulsion failure.
  3. **Attribute** the cause to pilot decision/policy, FBW or allocator design, model defect, or vehicle infeasibility (insufficient control power, power or energy). Attribution is per variant.
  4. **Record** the lesson in Colin's memory (the contract requires adaptation), or raise a model revision if a defect is found.
  5. **Re-fly** the same point (same seed, same variant) to show adaptation.
  6. **Back off** after three crashes on the same point without new understanding: drop back one build-up step.

  Each of the station's five automatic restarts should follow a classified crash, not be consumed blindly.
- **Build-up order.** Ground (power off → actuators → spool → thrust/power on gear → light-on-gear) → IGE hover (lift-off, height sweep, heading invariance, small steps) → IGE low speed (2.5→10 m/s, then wind azimuths) → OGE hover (trim, steps, 3-2-1-1, sweeps) → precision tasks (HQTE, then ADS-33) → consequence cards → "controllable" gate → local pattern → hop. Change one variable per step: height, speed, amplitude, wind, time scale, *or variant*. Following Eve's rule, compare each block's results with the model's pre-test prediction before advancing.
- **Energy budgeting.** Hover demand is about 1.6 MW for the as-drawn disks (SYSTEMS_CONTRACT). Every airborne card needs:
  - `E_card = P_est × t_card × 1.2`;
  - a **joker** (energy to finish and land, plus reserve);
  - a **bingo** (1.5 × energy to land from present height).

  The buffer deficit depends on generator output. At 1.2 MW generation the buffer supplies 0.4 MW (about 9 s of hover per usable kWh); at 0.6 MW it supplies 1.0 MW (about 3.6 s per kWh). Running out is legitimate data in card X-4, but on other cards it is a consequence event to classify.

### Gaps
- USNTPS FTM-106/FTM-107 and FAA AC 29-2C / AC 27-1B weren't accessible as text, so their first-hover procedures and limits aren't cited.
- No authoritative published set of numerical knock-it-off thresholds for first hover was found; the limit lines above are proposals.
- Eve's source doesn't say whether the hover/low-speed block was crewed or tethered.
- No NASA AAM National Campaign test-card material was retrieved.

## 2. Calibration manoeuvres: trim shots, steps, doublets, 3-2-1-1 and frequency sweeps

### Takeaway
Each manoeuvre identifies something different:
- **Stabilised trim shots:** trim and CG. This is where the as-drawn and fx CG differ most visibly.
- **Small steps:** the time-domain control response that FSTD tolerances are written against.
- **Doublets and 3-2-1-1s:** short time-domain identification and verification.
- **Frequency sweeps or multisines:** frequency-domain identification of control power, damping, coupling and delay.

For an unstable, over-actuated vehicle like the Phantom, NASA identifies dynamics with a stabilising controller engaged, excites "virtual effector" reference inputs, and uses ~90 s sweeps from 0.5 to 30 rad/s at ±10%. At ~1.6 MW hover power (as drawn), one 90 s sweep costs about 40 kWh, so sweeps must be segmented or replaced by multisines. The fx propulsion sizing will change that budget.

### Cited Findings
- Tischler & Remple recommend the frequency sweep for frequency-domain identification because it gives "fairly uniform spectral excitation over the frequency range of interest"; flight records must contain the dynamics the model must capture — [Tischler & Remple ch. 5 (GlobalSpec)](https://www.globalspec.com/reference/21919/203279/chapter-5-collection-of-time-history-data)
- **NASA eVTOL practice (lift+cruise and tiltwing VMS models).**
  - "Ninety second sine sweeps from 0.5 rad/s to 30 rad/s" per reference input, processed in CIFER.
  - Amplitude ±10% of steady-state value (rotor speed) or maximum deflection (surfaces).
  - A simple PID SAS held trim. Eight sweeps were needed for the lift+cruise and ten for the tiltwing at hover.
  - Being bare-airframe unstable in hover, "frequency sweeps must be performed with a controller engaged".
  - Over-actuation makes the mixer's bare-airframe inputs highly correlated, so symmetric/differential "virtual effectors" are excited for higher SNR and coherence.
  - Linear models were verified against nonlinear-model sweeps for all input–output pairs.
  - Source: [Caudle, Singh, Malpica et al., VFS 2025 (NASA)](https://ntrs.nasa.gov/api/citations/20250003865/downloads/DevelopmentFDModels_VFS25_David%20Caudle.pdf)
- **NASA heave coupling analysis.** Heave sweeps were injected at the pilot throttle at 5 ft/s amplitude in ACAH to get roll and pitch rate due to heave. Roll-due-to-pitch and pitch-due-to-roll (ADS-33E-PRF metrics) were computed as off-axis/on-axis ratios averaged between on-axis bandwidth and neutral-stability frequencies. Coupling peaked near 3 rad/s — [Altamirano et al., VFS Forum 79, 2023 (NASA)](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf)
- **3-2-1-1 structure.** Seven Δt units with switches at 3Δt, 5Δt and 6Δt (search excerpt) — [arXiv 1711.10010](https://arxiv.org/pdf/1711.10010). Pulse width sets the excited band: 0.3 s pulses give about 1–9 rad/s and 0.1 s pulses about 3–27 rad/s — [UMN report](https://conservancy.umn.edu/server/api/core/bitstreams/c1878924-e05b-41f3-a89a-337a72e2b986/content)
- **Input comparison** (attribution from a search excerpt; not verified in full text). The 3-2-1-1 gave the best estimation accuracy among doublet, Mehra, Schulz and DUT inputs, and only doublets and 3-2-1-1 excited responses above 1 Hz enough — [arXiv 1711.10010](https://arxiv.org/pdf/1711.10010)
- **Sweep amplitude, small vehicles.** About 10% of the maximum limit is typical — [arXiv 1508.04886](https://arxiv.org/pdf/1508.04886) (secondary, small quadcopter). Ivler & Rowe note that published small-UAV papers rarely describe sweep design, and they ran a parametric amplitude study — [Ivler & Rowe, VFS 2019](https://www2.sjsu.edu/researchfoundation/docs/VFS_2019_Ivler.pdf)
- **Shorter tests.** Compressed multi-stack sweeps kept the critical data in about a quarter of the original duration — [US patent 6446015](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6446015). SIDPAC includes experiment-design routines — [NASA NTRS (Morelli, SIDPAC)](https://ntrs.nasa.gov/citations/20030006686)
- **FSTD control-response tests.** Hover control-response tests are short-time *step* inputs, IGE, augmentation on and off. Control-system dynamics tests use 25–50% displacement. Snapshot tests must show steady state from 4 s before to 1 s after — [14 CFR Part 60 App. C (Cornell LII)](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60)
- **Argon identification history.**
  - **Sensitivities.** ∂T/∂c ≈ 268 N/deg per rotor (1,072 N/deg total) and ±1,394 N·m/deg roll/pitch.
  - **Yaw oscillation.** Yaw via nacelle tilt (τ = 0.08 s plus 20 ms delay) gave a ~6.5 s-period lightly damped yaw oscillation.
  - **CG trim.** A +0.0792 m lateral CG was trimmed by a 0.71° collective bias.
  - Source: [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md)

### Inferences
- **What each manoeuvre identifies** (both variants):
  - **Trim shots** (10 s stabilised, four headings): per-pod thrust, tilt, power, attitude and canard/flap state. From these come trim, CG offset (from thrust differential × arm / W, cross-checked with static gear-load weighing), the ground-effect curve (height sweep) and low-speed trim tilt and attitude vs speed.
  - **Steps** (attitude, yaw-rate or vertical-speed command held 3–5 s): rise time, overshoot, steady rate and attitude change, plus the off-axis trend.
  - **Doublets:** short-term damping and control power; verification. A doublet of half-width Δt peaks spectrally at ω ≈ 2.33/Δt (derived from |X(ω)| = 4 sin²(ωΔt/2)/ω). For roll/pitch near 2 rad/s, Δt ≈ 1.2 s; for yaw/heave near 1 rad/s, Δt ≈ 2.3 s.
  - **3-2-1-1:** a broader band in 7Δt. Scaling the UMN examples gives roughly 0.3/Δt to 2.7/Δt rad/s. For 0.5–4.5 rad/s, Δt ≈ 0.6 s (4.2 s total); for 0.2–1.8 rad/s (heave, yaw, translation), Δt ≈ 1.5 s (10.5 s total).
  - **Sweeps/multisines:** frequency responses for bandwidth, phase delay, damping, coupling ratios and equivalent delay. Control power comes from the low-frequency gain or the initial angular acceleration per unit input.
- **Sweep recommendation:**
  - roll/pitch 0.5–20 rad/s, yaw and heave 0.3–10 rad/s (the yaw band covers Argon's ~0.97 rad/s mode);
  - ±10% of the reference-input range, falling back to ±5% near limit lines;
  - engaged in M2 at the FBW reference input, using virtual-effector channels: collective, roll differential, pitch differential, yaw differential tilt/torque, booster;
  - 90 s per axis if energy allows, otherwise 2–3 segments of 30–45 s, or one 30–60 s orthogonal multisine on all four axes.
  - **Identical across variants:** use the same PTI definitions (in % of each variant's own reference-input range) so the responses are directly comparable.
- **Programmed Test Inputs.** Precise inputs (3-2-1-1 Δt ≈ 0.6 s, sweeps up to 20–30 rad/s) can't be timed by a 0.2–2 Hz decision loop. They should be **FBW-executed PTIs**: pilot-armed, disclosed, logged as PTI, and cancelled on any pilot input on that axis or at a limit line. The LLM remains pilot-in-command, flies the other axes and decides when to arm or abort. PTI runs are identification bench events, not "piloting demonstrations", consistent with the contract's canned-input clause.
- **Step amplitudes** (M2, OGE unless noted): pitch and roll attitude ±5°, each held 4 s then returned; yaw rate 10°/s for 3 s; vertical speed 0.5 m/s for 4 s.
- **Argon CG cross-check** (computed from the report's numbers): 2 × 2.6 m × 268 N/deg × 0.71° = 989 N·m. At 996.67 kg that implies y_CG ≈ 0.101 m, against the 0.0792 m ledger (+28%; the ledger CG needs only about 0.56°). The Phantom trim cards should reconcile ledger, gear-load weighing and hover-trim CG estimates *per variant*. The fx nose battery and avionics are meant to move the CG, and the trim cards are where that shift is first measured objectively.

### Gaps
- The full Tischler & Remple and Morelli & Klein guideline tables weren't accessible: record-length rules, CIFER coherence and cost-function thresholds, and multisine design rules.
- The doublet and 3-2-1-1 band rules above are derived, not quoted.
- Whether CIFER concatenation of energy-segmented sweeps is appropriate needs checking in the CIFER documentation.

## 3. Logging: parameters, rates, and comparison with flight-test and Part 60 practice

### Takeaway
The repo's flight evidence contract already goes beyond an FSTD QTG in scope: it covers effectors, per-surface aero, energy and contact. It still needs six additions:
- an explicit identification-grade logging rate;
- body-axis rates and Euler angles in the pilot channel (Argon's gyro was world-frame);
- a per-decision pilot-loop timing record (wall and sim);
- PTI and augmentation state;
- variant and policy-version keys for the A/B comparison;
- a pre-crash ring buffer so crashes are usable data.

Part 60 helicopter practice is the benchmark. It favours time histories over snapshots, requires snapshots to be steady from 4 s before to 1 s after, records at light and heavy weights, sets 100–150 ms transport-delay limits, and asks for a block-diagrammed latency path.

### Cited Findings
- **Phantom evidence contract.** Every run retains:
  - config hash and source-status map;
  - physics clock and pilot action timing;
  - actual and commanded position of every effector;
  - per-surface aero F,M and per-pod thrust/torque;
  - mass, CG and inertia;
  - generator, buffer, shaft and propulsor power and energy;
  - thermal states, contact/impact, faults and protections, and outcome.

  The report must state whether synthetic assumptions control success — [TEST_PLAN.md](../../docs/phantom/TEST_PLAN.md). Logging is "at physics and action cadence", with mission id, variant, config hash, seed, requested/actual effectors, local airspeed, F/M breakdown, mass/inertia, engine/generator/buffer state, energy residual, contact and protection events — [SYSTEMS_CONTRACT.md §6](../../docs/phantom/SYSTEMS_CONTRACT.md)
- **Argon observation fields:** gnss_xy_m, baro_m, radar_clearance_m, attitude_xyz_deg, gyro_world_deg_s, gnss_velocity_mps, rotor_rpm, shaft_torque_nm, collective_feedback_deg, assistance flags, tilt_feedback_deg, gear_compression_m, fuel_kg, engine_shaft_kw, warning_lamps, scheduler_backlog_s, authority, paused, time_scale — [argon_live_stability_calibration.json](../../evidence/argon_live_stability_calibration.json). Attitude and gyro are in the **world ENU frame**, and omitting the heading rotation caused cross-axis feedback at ψ → 90° — [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md)
- **Audit and live log.** The physics audit and sensor observation are produced every 0.05 s sim — [live_server.py](../../src/vtx/live_server.py). The contract asks for a synchronised log of "observation → Colin's decision → issued fly-by-wire input → achieved actuator states → observed motion/consequence", and for persistence of learned-policy changes across attempts — [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)
- **Part 60 App. C (helicopter FFS)** — [Cornell LII](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60):
  - Time histories are required unless Table C2A says otherwise.
  - Snapshots must show steady state from 4 s before to 1 s after.
  - Results are labelled with tolerances and units, and data resolution must suffice to determine compliance.
  - Hover and vertical climb are recorded at light and heavy gross weights.
  - Transport delay runs from control input through host to motion, instrument and visual outputs, and must be within 150 ms or 100 ms depending on level. The extraction suggests 150 ms for Level B and 100 ms for Levels C/D; verify against Table C1A.
  - A 60 Hz simulator "may have a difference of as much as 16.67 msec", which isn't a failure by itself.
  - Signals used for transport-delay calculation should be shown on a block diagram.
  - Synchronised video must resolve at least half the tolerance.
  - Level C/D need an automatic-test driver program.
  - The text carries an amendment at 90 FR 42525 (Sept 3, 2025).
- **CS-FSTD(H).** Initial issue 26 June 2012, and recurrent evaluations use the same CS version as the initial evaluation — [EASA CS-FSTD(H)](https://www.easa.europa.eu/en/downloads/1737/en). An EASA presentation on newer CS-FSTD material groups tests into on-ground, IGE and OGE sections (search excerpt) — [EASA download 140067](https://www.easa.europa.eu/ro/downloads/140067/en)

### Inferences
**Logging specification (proposed).** "Truth" channels are audit-only; "pilot" channels are what Colin may see.

| Group | Signals (units, frame) | Source | Rate | Used by |
|---|---|---|---|---|
| Run metadata | run_id, **variant (`phantom` / `phantom-fx`) and variant config hash**, design-point diff list vs baseline, source-status map, seed, model revision, MQTG id, card/point id, **attempt number and A/B order slot**, weight/CG case, wing state, wind/turbulence, time_scale, FBW mode and disclosed gains, PTI definition, **pilot policy/memory version** | config | once + on change | all |
| Pilot loop timing | observation_id; obs sim time; obs wall time; decision wall start/end; command sequence; send wall time; accept and apply sim time; lease remaining; scheduler_backlog_s; LLM latency; stated reason | server + pilot | per decision | all; delay ID |
| Pilot inceptors | lateral, longitudinal, pedal, heave (−1..1); discrete selects (tilt schedule, flap, gear, mode, PTI arm/abort) | pilot | per decision + ZOH trace at 100 Hz | all |
| FBW internals | command-model outputs (φ_cmd, θ_cmd, r_cmd, ḣ_cmd); PTI signal; integrators; allocator virtual commands (collective, roll/pitch/yaw differential, booster); saturation flags | FBW | 100 Hz (400 Hz for ID) | ID, limits |
| Effectors (each) | commanded vs achieved pod thrust, rpm, tilt and tilt rate, booster thrust, canard/flap/aileron deflection and rate, leg extension; hinge/shaft torque; actuator power; fault/jam state | plant | 100 Hz (400 Hz for ID) | G-cards, ID |
| Rigid body (truth) | world position; world and body velocity (u,v,w); Euler φ,θ,ψ; quaternion; body rates p,q,r; angular acceleration; body specific force; height AGL; mass; CG; inertia | plant | 100 Hz (400 Hz for ID) | all |
| Pilot sensors | the same through the modelled sensors (noise, quantisation, latency), **with body-axis p,q,r and explicit frame labels**, plus radar height, ground speed, airspeed | sensor model | 20 Hz | MTE scoring (pilot view) |
| Aero | per-surface α, β, q̄, CL, CD, Cm, F and M about the CG; fan inflow/ram-drag terms; ground-effect factor per pod | plant | 100 Hz | L-cards, H-2 |
| Power/energy | generator shaft and electrical power, buffer power/SOC/energy, bus V/I, per-motor power, losses, energy residual, joker/bingo flags | plant | 20–100 Hz | all |
| Thermal | motor/inverter/generator temperatures, cooling power, derates | plant | 10–20 Hz | endurance |
| Contact | per-leg compression, normal force, friction, contact flags, impact impulses, sink rate at first contact, bounce events | plant | 400 Hz (event-captured) | G-3, landing, crashes |
| Crash capture | **20 s pre-event ring buffer of all truth channels at 400 Hz**; crash classification; impact velocity and attitude; peak loads; damage/failure flags; post-crash state to rest | server | event | crash analysis |
| Environment | wind vector, turbulence state, density | env | 20–100 Hz | low-speed cards |
| Events | limit-line crossings (which limit and value, D or C class), lease expiry, PTI start/stop/cancel, mode changes, faults, protections | server | event | all |

- **Logging rates for identification.** Log inputs and outputs at ≥ 100 Hz with any decimation filter documented; 400 Hz raw is preferred. At the 30 rad/s (4.8 Hz) top sweep frequency, 20 Hz gives about 4 samples per cycle and 100 Hz about 21.
- **Time stamping.** Stamp everything with sim time, and decisions with sim and wall time, so that pilot-loop delay (sim) = obs-to-apply wall latency × time_scale + 0.02 s + observation age.
- **Part 60 latency analogue.** Measure the FBW transport delay (input → first effector motion → first body response) separately from the pilot-loop delay. Hold the former to ≤ 100 ms and target the latter at ≤ 0.2–0.3 s sim for precision cards.
- **A/B comparability.** Both variants must use the same schema, channel names, units and frames. A comparison script should refuse to diff runs whose seed, card, time_scale, wind or FBW mode differ unless the difference is the declared test variable.

### Gaps
- AC 120-40B (airplane simulator qualification, superseded by Part 60) wasn't retrieved.
- No public instrumentation standard giving handling-qualities or system-identification sample rates was retrieved; the ≥ 100 Hz recommendation rests on sampling arithmetic.
- CS-FSTD(H) test tables weren't extracted.

## 4. "Controllable" criteria: ADS-33E-PRF MTEs and FAA/NASA HQTEs, scaled for the simulator and an LLM pilot

### Takeaway
Use the NASA/FAA-style HQTEs (ADS-33-like precision with relaxed aggressiveness) as the primary scoring tasks and the ADS-33E Cargo/Utility GVE MTEs as stretch tasks. Keep tolerances in sim time: the time scale already gives the LLM human-like decision density. Score objectively from logs, using desired/adequate performance plus workload and PIO proxies, and report "Level-1/2-equivalent (objective)", never an HQR. A crash is simply a failed attempt. Score each variant separately, and interleave variants so Colin's learning doesn't favour whichever is flown second.

### Cited Findings
- **ADS-33E-PRF structure.** MTEs are in §3.11 (3.11.1 Hover, 3.11.2 Landing, ...) — [ADS-33E-PRF (scanned PDF)](https://www.robertheffley.com/docs/HQs/ADS-33E-PRF.pdf). Full-scale rotorcraft MTEs include Hover, Acceleration/Deceleration, Landing, Sidestep, Hovering Turn, Transient Turn, Pirouette, Pullup/Pushover, Depart/Abort, Turn to Target, Lateral Reposition, Decelerating Approach, Slalom and Missed Approach — [arXiv 2302.10087](https://arxiv.org/pdf/2302.10087)
- **Hover MTE (ADS-33, Cargo/Utility, GVE) vs. Precision Hover HQTE** — [Malpica et al. 2023, Table 2](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf); [Altamirano et al. 2023, Table 13](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf):
  - **Shared tolerances:** horizontal ±3/6 ft (±0.91/1.83 m), altitude ±2/4 ft (±0.61/1.22 m), heading ±5/10°.
  - **Deceleration time:** 5/8 s (MTE) vs 8/12 s (HQTE).
  - **Course:** entry ground speed 6–10 kt (3.1–5.1 m/s), 45° reference line, 20 ft (6.1 m), stable hover 30 s.
- **Vertical Maneuver MTE vs. Vertical Reposition and Hold HQTE** — [Altamirano et al. 2023, Table 11](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf):
  - horizontal ±3/6 ft (±0.91/1.83 m), altitude ±3/6 ft, heading ±5/10°, Δaltitude 25 ft (7.62 m);
  - completion 13/18 s (MTE) vs 24/29 s (HQTE);
  - stabilise 2 s (MTE) vs 5 s (HQTE).
- **Lateral Reposition MTE (ADS-33 C/U GVE)** — [Malpica et al. 2023, Table 3](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf):
  - longitudinal ±10/20 ft (±3.05/6.10 m), altitude ±10/15 ft (±3.05/4.57 m), heading ±10/15°;
  - completion 18/22 s;
  - initial altitude 40 ft (12.2 m), course 400 ft (121.9 m), endpoint ±10 ft.
- **Lateral Reposition and Hold HQTE** — [Malpica et al. 2023, Table 3](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf); [Altamirano Table 12](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf):
  - longitudinal ±5/10 ft (±1.52/3.05 m), altitude ±5/10 ft, heading ±10/20°;
  - ground speed 10 ± 2/4 kt (5.14 ± 1.03/2.06 m/s);
  - initial altitude 20 ft, course 120 ft (36.6 m), endpoint ±5 ft, maximum overshoot 5 ft;
  - hold 5 s.
- **Why HQTEs.** The HQTEs emphasise higher precision and lower aggressiveness: a target speed of 8–12 kt instead of a completion time, and a shorter course — [Malpica et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf). FAA-supported work describes HQTE manoeuvres as having relaxed aggressiveness compared with ADS-33 MTEs, in a certification approach mirroring ADS-33. This attribution comes from a search excerpt and wasn't verified in full text — [NASA NTRS 20230005195](https://ntrs.nasa.gov/citations/20230005195). The "UAM standards" used smaller targets, shorter courses and/or more time — [Aires et al., VFS Forum 78 (NASA)](https://ntrs.nasa.gov/api/citations/20220004746/downloads/VFS%20Forum%2078%20Final%20(Fixed).pdf)
- **Response types and HQ results:**
  - NASA's eVTOL VMS evaluations used ACAH, RCAH and TRC for roll/pitch, RCDH for yaw and RCHH for heave — [Malpica et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf); [Aires et al.](https://ntrs.nasa.gov/api/citations/20220004746/downloads/VFS%20Forum%2078%20Final%20(Fixed).pdf)
  - TRC with 0.33 rad/s bandwidth improved HQ over ACAH in the high-precision hover tasks, and ACAH alone didn't give Level 1 from all evaluators in either hover task. Ratings of 4.5 were allowed as a compromise — [Malpica et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf)
  - A baseline tuned to predicted Level 1 "with margin" drew average Level 2 ratings — [Aires et al.](https://ntrs.nasa.gov/api/citations/20220004746/downloads/VFS%20Forum%2078%20Final%20(Fixed).pdf)
- **NASA design targets for Level 1 "limited agility" ACAH:**
  - roll and pitch ω_BW = 2 rad/s, Δφmax = Δθmax = 15°, phase delay about 80 ms;
  - gain margin 6 dB and phase margin 45°;
  - disturbance-rejection bandwidth: heave 1.0, roll 0.9, pitch 0.5, yaw 0.7 rad/s;
  - disturbance-rejection peak 5 dB;
  - minimum crossover: heave 0.5, roll 2.5, pitch 2.0 rad/s.
  - Source: [Malpica et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf)
- **Powertrain limits and HQ.** Powertrain saturation or rate limits can cause sudden, severe HQ degradation. The torque limit was reached 3.9% of the time in Lateral Reposition, with impulsive requests lasting under 3 s — [Malpica et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf)
- **Run procedure and failures.** Runs started in hover, and pilots waited 7 s before initiating. Propulsion failures were injected 5–7 s after run start, with a master caution and tone; pilots re-stabilised afterwards — [Altamirano et al. 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf)
- **Scoring non-human pilots.** For scaled MTEs flown by UAVs, a trajectory-tracking (TTA) score has been used with desired = Level 1 and adequate = Level 2 thresholds:
  - **Nominal:** Lateral Reposition and Depart/Abort ≥ 75 / 70–75; Pirouette ≥ 73 / 68–73.
  - **Aggressive:** Lateral Reposition and Depart/Abort ≥ 82 / 77–82; Pirouette ≥ 80 / 75–80.
  - Kinematic scaling based on maximum cruise velocity gives spatial, velocity and time scale factors.
  - Source: [arXiv 2302.10087](https://arxiv.org/pdf/2302.10087)
- **EASA SC-VTOL.** Handling qualities fall under VTOL.2135, .2140 and .2145. The proposed MoC is the Modified HQ Rating Method (MHQRM): a minimum acceptable rating per flight phase and condition with probability above 10⁻⁹, using Cooper-Harper by default — [NLR/ERF paper](https://dspace-erf.nlr.nl/bitstreams/f1adc6bb-0ec3-460f-bb55-7d61a35d07d4/download); [EASA CRD MOC SC-VTOL](https://www.easa.europa.eu/sites/default/files/dfu/CRD%20MOC%20SC%20VTOL%20Issue%201_12-May-2021.pdf). EUROCAE ED-295 complements the MHQRM — [UAM News](https://urbanairmobilitynews.com/emerging-regulations/eurocae-publishes-new-standard-to-comply-with-easa-sc-vtol-handling-quality-rules)
- **ED-295 hover tolerances (from search excerpt; the page returned 403).** ED-295 is reported to allow up to 10 ft (~3 m) deviation for desired performance in hover-type tasks, which authors judged too loose for a small eVTOL. They tightened altitude to 3 ft desired / 6 ft adequate — [MDPI Aerospace 12(6):559](https://www.mdpi.com/2226-4310/12/6/559)
- **Passenger quadrotor.** In one piloted simulation the baseline achieved only adequate performance in the Hover MTE; a modified variant reached desired, though roll-axis deficiencies remained — [CEAS Aeronautical Journal](https://link.springer.com/article/10.1007/s13272-023-00705-7)
- **Learning across attempts.** The contract requires persisting learned state and testing learning "by varying physical states and map missions" — [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)

### Inferences
- **Scaling.** The Phantom's dimensions (~5 m span, two seats) are close to the small rotorcraft and eVTOL these courses were designed for. Use course dimensions and tolerances **unscaled in metres and sim seconds**; kinematic scaling is for much smaller UAVs. The LLM adaptation is the **time scale**, not the tolerance.
- **Objective scoring** (per attempt, from 100 Hz truth logs):
  1. Task windows come from log events: entry gate, deceleration start, stabilisation deadline, hold window.
  2. **Desired** = every hold-window sample inside the desired bounds and all timing limits met. **Adequate** = the same against adequate bounds. **Fail** = otherwise, including any crash or data-validity stop.
  3. **Workload proxies:**
     - control reversals per minute per axis;
     - RMS inceptor rate;
     - decisions per task;
     - fraction of time any effector is above 90% of authority.
  4. **PIO flag:** ≥ 2 consecutive attitude oscillation cycles of ≥ 2° with the pilot command in phase opposition.
  5. **Classification:**
     - "L1-equivalent (objective)" = desired, no PIO flag and workload below the baseline set from the first passing runs;
     - "L2-equivalent" = adequate, or desired with high workload;
     - "L3/fail" = otherwise.

  Never call these Cooper-Harper ratings: NASA found that a predicted Level 1 baseline still drew Level 2 human ratings.
- **Repeatability and A/B design:**
  - n ≥ 3 scoring attempts per task, condition and variant: all adequate and ≥ 2 of 3 desired;
  - flown at two headings 90° apart (Argon frame lesson) at the declared time_scale;
  - variants interleaved A-B-B-A, with the policy/memory version logged per attempt.

  If learning visibly carries over (for example, the second variant flown always improves), repeat with the order reversed. Alternatively, freeze a policy snapshot for the scoring block and keep learning to the build-up attempts. Report p50/p95/p99 sim-time decision intervals and pilot-loop delay for every variant.
- **ACAH vs. TRC.** NASA's TRC benefit suggests better scores under M3. Contract compliance favours scoring "controllable" under M2, with any M3 results reported separately.
- **Pilot-loop crossover.** The achievable position-loop crossover is about 1/(5–10 × decision interval) rad/s, a sampled-data heuristic rather than a cited rule. That is about 0.5–1 rad/s at 0.2 s sim, but only 0.1–0.2 rad/s at 1 s sim, which would need TRC-like augmentation. This is why the time_scale is fixed before scoring, and why card X-6 measures where each variant's controllability fails as decision density falls.

### Gaps
- ADS-33E-PRF **Landing, Pirouette, Hovering Turn and Depart/Abort** tolerances couldn't be read: the available copy is a scanned, image-only PDF and no text reproduction was found. The related cards use *project-defined* criteria, labelled as such, until ADS-33E §3.11 is transcribed.
- The Cooper-Harper wording and Level boundaries (HQR 3.5/6.5) weren't retrieved from a primary source.
- There is no validated way to map an LLM's self-assessment onto HQR.

## 5. Minimal-speed testing: powered-lift minimum speeds, stall, power-required curve, back side and transition corridor

### Takeaway
At 1,300 kg the small wing gives very high wing loading (≈ 3.1 kN/m², 320 kg/m²). The indicative 1-g wing stall is about 65 m/s (127 kt) clean and 57 m/s (110 kt) flapped, so everything below ~60–70 m/s is powered-lift flight with the fans carrying most of the weight. With the as-drawn fans' ~81 m/s induced velocity there's almost no translational-lift benefit at hover-taxi speeds: power stays at about 1.5–1.6 MW up to 20 m/s unless the wing is loaded. The power-required curve runs on its back side from hover to ~60–70 m/s. The fx "sized propulsion" is the main lever. Hover power scales as m^1.5/R, so, for example, 0.35 m fans would cut the 1.6 MW estimate to about 1.1 MW at the same mass. The first campaign should map only 0–20 m/s; stall determination comes later, approached at ≤ 1 kt/s.

### Cited Findings
- **Phantom wing and controls (repo):**
  - S_ref 4.06 m², span 5.19 m, MAC 0.872 m, CLα ≈ 4.0/rad, CLmax 1.2 clean / 1.6 flapped, cm0 −0.04;
  - right-wing chord plane at z ≈ 1.00 m and left at 0.88 m, "a 0.12 m stagger", so each wing's force is modelled at its own height;
  - canards 0.278 m² each, CLα 3.0/rad (SYNTHETIC), pitch −20/+25° at 40°/s;
  - flaps 15°/s, inhibited above 75 m/s; ailerons 80°/s.
  - Source: [A9_MUJOCO_HANDOVER.md](../../docs/phantom/A9_MUJOCO_HANDOVER.md)
- **Pitch stability (repo).** Pitch stability is "between neutral and unstable" (NP −0.15 m vs estimated CG −0.25 m). The canards can't trim alone below ~70 m/s, so until then the wheel-thrusters must keep pitch authority. The mass ledger and CG are still missing — [A9_WING_CASSETTE_REVISION.md](../../docs/phantom/A9_WING_CASSETTE_REVISION.md)
- **Hover power (repo).** Ideal hover is about 1.04 MW for four 0.25 m-radius disks at 1,300 kg, and about 1.6 MW electrical at an illustrative 65%. One Safran TG600 gives 600 kW; 1.2 MW needs two and may still need a buffer. Effective disk area can't be inferred from tyre diameter — [SYSTEMS_CONTRACT.md §4](../../docs/phantom/SYSTEMS_CONTRACT.md). Earlier "75 m/s" wing-only figures were conditional — [same §3](../../docs/phantom/SYSTEMS_CONTRACT.md). Rolling take-off speed must come from the computed lift/weight margin — [TEST_PLAN.md](../../docs/phantom/TEST_PLAN.md)
- **Stall test practice.** From stabilised trim, decelerate at no more than **1 kt/s** (14 CFR 25.103(c)), and V_SR may not be below the 1-g stall speed — [14 CFR 25.103 (federal-regs)](https://federal-regs.com/title/14/part-25/25.103/); [Cornell LII 25.103](https://www.law.cornell.edu/cfr/text/14/25.103). Turning-flight stall demonstrations allow up to 3 kt/s — [14 CFR 25.201](https://www.law.cornell.edu/cfr/text/14/25.201)
- **Tiltrotor conversion corridor.** The XV-15 has an airspeed-vs-nacelle-angle conversion corridor — [NASA TM 81244 (NTRS)](https://ntrs.nasa.gov/api/citations/19810001546/downloads/19810001546.pdf); [MDPI Aerospace 9(3):155](https://www.mdpi.com/2226-4310/9/3/155/html). Its numerical boundaries weren't extracted.
- **FSTD low-speed checks (Part 60).** These cover sideward, rearward and forward translational flight IGE plus 45 kt forward, with augmentation on and off: torque ±3%, pitch ±1.5°, bank ±2°, controls ±5%. The critical-azimuth test uses three relative wind directions within the critical quadrant — [Part 60 App. C](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60)
- **Jet-borne ground effects.** Jet impingement forms a wall jet whose entrainment causes suckdown, while multi-jet fountains add lift. Effects depend strongly on height, and earlier prediction methods overestimated fountain lift and extra suckdown and missed pitching moments. These points summarise NASA Ames reports such as TM-102268 (Kuhn et al.), from search excerpts — [NASA NTRS jet-induced ground-effect report](https://ntrs.nasa.gov/api/citations/19920024374/downloads/19920024374.pdf); [SAE 872305](https://www.sae.org/publications/technical-papers/content/872305/)

### Inferences
Indicative, computed here (ISA sea level, ρ = 1.225 kg/m³).
- **Wing-only 1-g stall at 1,300 kg:**
  - W/S = 3,140 N/m²; AR = 6.63; V_s = √(2W/(ρ S CLmax)).
  - **Clean:** V_s 65.4 m/s (127 kt); 1.1 V_s 71.9; 1.2 V_s 78.4; 1.3 V_s 85.0 m/s.
  - **Flapped:** V_s 56.6 m/s (110 kt); 1.1 V_s 62.3; 1.2 V_s 67.9; 1.3 V_s 73.6 m/s.
  - Canard area at the same CL would give a 61.3 / 53.1 m/s bound.
  - Flapped 1.3 V_s sits only about 1.4 m/s under the 75 m/s flap inhibit.
  - Stall speed scales as √m, so an fx mass change shifts all of these.
- **Hover power vs fan size and mass** (momentum theory, four disks, electrical at 0.65; this is the fx-sizing sensitivity):

| Mass | R = 0.25 m (as drawn) | 0.30 m | 0.35 m | 0.40 m | 0.50 m |
|---|---|---|---|---|---|
| 1,300 kg | 1.60 MW (v_h 81 m/s; 26.6 kWh/min) | 1.33 MW | 1.14 MW | 1.00 MW | 0.80 MW (v_h 41 m/s) |
| 1,400 kg | 1.78 MW | 1.49 MW | 1.27 MW | 1.12 MW | 0.89 MW |
| 1,500 kg | 1.98 MW | 1.65 MW | 1.41 MW | 1.24 MW | 0.99 MW |

  The scaling is P ∝ m^1.5/R. The buffer deficit and hover seconds per kWh follow from (P_hover − P_generation). Card durations must be recomputed per variant once the fx values are declared.
- **CG compensation sensitivity in hover** (four-pod geometry; formula, not Phantom data). Moving the CG by Δx shifts the front-pair share of hover thrust by Δx/L, where L is the front–rear pod spacing. Each 10 mm is about 0.33–0.42% of W (42–53 N) for L = 2.4–3.0 m, and 100 mm is 3.3–4.2%. That share is pitch-control margin consumed by trim. The trim cards (G-3, H-2, O-2) measure it directly per variant. The fx nose battery and avionics should shrink it if the as-drawn CG lies aft of the pod centroid, and enlarge it if they overshoot.
- **Wing height.** The as-drawn 0.12 m stagger offsets left and right wing lift lines vertically, so side force and drag produce small asymmetric moments. At hover-campaign speeds (≤ 10–20 m/s, q ≤ 245 Pa) these are small. They matter in L-2/L-3 and conversion, where the later fx common-height wing should remove a measurable roll/yaw trim asymmetry. Compare the variants' trim aileron/differential at matched q.
- **Open-rotor ground effect.** The Cheeseman–Bennett image model (textbook, not re-verified here) gives T_IGE/T_OGE = 1/(1−(R/4z)²). For R = 0.25 m this is 1.067 at z = 0.25 m, 1.016 at 0.5 m and 1.004 at 1 m, so it is negligible above ~2R. Larger fx fans extend the classical IGE height in proportion to R. Jet-type suckdown/fountain effects will likely dominate; the sim must declare its model, and H-2 identifies it per variant.
- **Ram (momentum) drag of edgewise ducted fans** (momentum estimate). Mass flow ≈ ρ A v_h ≈ 78 kg/s for the as-drawn fans, rising to ~110 kg/s at R = 0.35 m. Ram drag ≈ ṁV ≈ 0.39 / 0.78 / 1.57 / 2.35 kN at 5 / 10 / 20 / 30 m/s for the as-drawn case. That is about ten times the body drag (≈ 31 / 123 / 276 N at 10 / 20 / 30 m/s for CdA = 0.5 m²), and implies trim fan tilt of roughly 1.8° / 3.5° / 7° / 10.4°. Larger fx fans move more air and so have *more* ram drag at a given speed. Measure trim tilt vs speed on both variants.
- **Indicative transition corridor, as drawn (R = 0.25 m)** — fans tilt τ from vertical; body CdA 0.5 m²; wing CD0 0.01 + flap 0.02; e = 0.8; Glauert momentum theory ÷ 0.65; wing CL capped at CLmax/1.21 (1.1 V_s margin); no ram drag or wing–fan interference:

| V (m/s / kt) | Wing share at CL cap, clean / flapped | Tilt range clean (wing unloaded .. at cap) | P_elec clean (unloaded .. at cap) | P_elec flapped at cap |
|---|---|---|---|---|
| 0 / 0 | 0% / 0% | 0° | 1.60 MW | 1.60 MW |
| 10 / 19 | 2% / 3% | 0.1–0.2° | 1.59 .. 1.54 MW | 1.53 MW |
| 20 / 39 | 8% / 10% | 0.6–0.9° | 1.57 .. 1.40 MW | 1.34 MW |
| 30 / 58 | 17% / 23% | 1.3–2.3° | 1.55 .. 1.16 MW | 1.05 MW |
| 40 / 78 | 31% / 41% | 2.4–5.0° | 1.52 .. 0.87 MW | 0.70 MW |
| 50 / 97 | 48% / 64% | 3.7–10.3° | 1.50 .. 0.57 MW | 0.39 MW |
| 60 / 117 | 70% / 93% | 5.3–24° | 1.48 .. 0.35 MW | 0.28 MW |
| 70 / 136 | 95% / 100% | 7.3–74° | 1.47 .. 0.31 MW | 0.35 MW |
| 80 / 156 | 100% / 100% | 9.4–90° | 1.49 .. 0.40 MW | 0.45 MW |

- **Reading the corridor table:**
  - The lower tilt bound is set by the wing being unloaded, the upper by the wing reaching its CL cap; beyond that lies stall.
  - Full conversion is possible from ~72 m/s clean or ~62 m/s flapped at the 1.1 V_s margin, and ~85 / 74 m/s at 1.3 V_s.
  - The wing-borne aero-power minimum (CdA 0.4–0.8 m²) would sit at 40–48 m/s, *below* stall, so in wing-borne flight the vehicle is always on its front side.
  - The back side lives entirely in the powered-lift region from hover to ~60–70 m/s. There, power falls with speed, and speed isn't self-stabilising at fixed power.
  - Indicative wing-borne aero power: 140–224 kW at 70 m/s and 284–529 kW at 100 m/s.
  - Larger fx fans lower the low-speed end of the curve (the R table above) but not the wing-borne end.
- **Incremental approach to minimum speeds:**
  1. **First campaign (0–20 m/s):** stabilised trim shots at 2.5 m/s steps, forward, rearward and sideward, on both variants.
  2. **Later corridor probing:** at fixed tilt schedules, take stabilised points at 1.3 → 1.2 → 1.1 × the *predicted* boundary, then use ≤ 1 kt/s (0.51 m/s²) ramps. These take about 22–25 s from 1.2 V_s to V_s and 33–38 s from 1.3 V_s.
  3. **End-of-ramp lines:**
     - wing CL ≥ 0.9 CLmax;
     - α ≥ α_stall − 2°;
     - uncommanded roll-off above 5°;
     - power above 95%;
     - joker.

     Pure stall determination (fans unloaded) comes last, clean then flapped. Departures beyond these lines are acceptable consequence data in the later campaign, once the clean points exist to interpret them.

### Gaps
- Kimberlin's stall and power-required chapters weren't accessed.
- No source was retrieved for powered-lift minimum-speed definitions (FAA powered-lift SFAR, SC-VTOL MOC) or for XV-15/V-22 corridor values.
- `phantom-fx` mass, CG, fan size and generator/buffer values aren't defined yet.
- CdA, wing–fan interference, ram drag, duct behaviour and the ground-effect model are unknown or SYNTHETIC for both variants.

## 6. Simulator calibration and validation: system-identification methods and tools, FSTD objective tolerances, comparing the simulator against itself across revisions and variants

### Takeaway
Calibrate bottom-up:
1. Actuators and fan maps from the ground cards.
2. Bare-airframe and closed-loop frequency responses, identified with the FBW engaged (CIFER-style frequency domain, cross-checked with time-domain output-error).
3. MTE-level task performance.

Validate with the Part 60 App. C hover/low-speed tolerances wherever an independent reference exists. Across revisions, adopt Part 60's MQTG discipline: a frozen set of deterministic test inputs, re-run on every revision, with every non-repeatable difference explained. Across variants, run the same drivers on both and audit every difference against the declared design changes (CG, propulsion, wing height). A difference with the wrong sign is a model or integration defect until shown otherwise.

### Cited Findings
- **CIFER.** Frequency-domain identification developed by the US Army and NASA — [SJSU CIFER page](https://sjsu.edu/researchfoundation/resources/flight-control/cifer.php). It computes frequency responses by Chirp-Z transform with coherence, and uses coherence-weighted fitting — [arXiv 0804.3881](https://arxiv.org/pdf/0804.3881)
- **SIDPAC** (NASA Langley MATLAB toolbox) covers experiment design, data conditioning, compatibility analysis, model-structure determination, and equation-error and output-error estimation in time and frequency domains, plus real-time and recursive methods. Morelli reports frequency-domain equation-error giving accuracy comparable to time-domain output-error with much less computation. Grauer notes that frequency-domain equation-error needs an extra step for bias parameters and doesn't directly optimise the time-domain output fit, and that frequency-domain output-error is limited to linear systems. Attribution is from search excerpts of NTRS listings — [NTRS (Morelli, SIDPAC)](https://ntrs.nasa.gov/citations/20030006686); [NTRS (Morelli, frequency-domain)](https://ntrs.nasa.gov/citations/20000080000)
- **Unstable, over-actuated vehicles.** NASA identifies eVTOL models with a stabilising controller and virtual-effector reference inputs, and verifies linear against nonlinear models across all input–output pairs — [Caudle et al. 2025](https://ntrs.nasa.gov/api/citations/20250003865/downloads/DevelopmentFDModels_VFS25_David%20Caudle.pdf)
- **Part 60 App. C hover/low-speed tolerances (Table C2A)** — [Cornell LII](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60):
  - **1.d Hover IGE/OGE:** torque ±3%, pitch and bank ±1.5°, controls ±5%; light and heavy GW.
  - **1.e Vertical climb:** ±100 fpm (0.50 m/s) or ±10%; directional and collective ±5%.
  - **1.f Level flight:** torque ±3%, pitch ±1.5°, sideslip ±2°, controls ±5%.
  - **1.c.1 Takeoff:** airspeed ±3 kt, altitude ±20 ft, torque ±3%, rotor speed ±1.5%, vertical velocity ±100 fpm or 10%, pitch ±1.5°, bank and heading ±2°, controls ±10%.
  - **1.j.1 Landing:** airspeed ±3 kt, altitude ±20 ft, torque ±3%, rotor speed ±1.5%, pitch and bank ±1.5°, heading ±2°, controls ±10%.
  - **1.j.3 Balked landing:** same tolerances, from a stabilised approach at the landing decision point.
  - **2.b.1 Trimmed controls, translational IGE:** torque ±3%, pitch ±1.5°, bank ±2°, controls ±5%.
  - **2.b.2 Critical azimuth:** same tolerances, three wind directions.
  - **2.b.3 Hover control response (steps):** pitch rate ±10% or ±2°/s and attitude ±10% or ±1.5°; roll rate ±10% or ±3°/s and attitude ±10% or ±3°; yaw rate ±10% or ±2°/s and heading ±10% or ±2°; vertical ±0.1 g. Unaugmented off-axis trends must be correct.
  - **2.c.3.a Long-term dynamics:** ±10% period, ±10% time to half/double, or ±0.02 ζ; non-periodic: pitch ±3° and airspeed ±5 kt over 20 s.
  - **2.c.3.b Short-term dynamics:** pitch ±1.5° or ±2°/s; ±0.1 g.
  - **2.d.3.a Lateral-directional oscillations:** ±0.5 s or ±10% period; ±10% time to half/double or ±0.02 ζ; 20% or 1 s bank–sideslip peak difference.
  - **2.a.6 Freeplay:** ±0.10 in.
  - **Tolerance rules:** with two tolerances the less restrictive may be used; percentage-only tolerances apply to the maximum normal-range value.
  - **Engineering data:** engineering-derived data should replicate flight-test results within 20% of the flight-test tolerances.
- **MQTG regression (Part 60).** Continuing-qualification results are compared to the MQTG, with "no suggested tolerances" between them. Differences other than unexplained repeatability variations "should be investigated". An electronic MQTG is required for initial qualifications after May 30, 2014. Evaluations take place every 12 months (≤ 36 with a QMS) — [Part 60 App. C](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60)
- **MUAD and allowable-error envelopes.** Maximum unnoticeable added dynamics (MUAD) envelopes are frequency-dependent, asymmetric bounds within which added dynamics go unnoticed by pilots. They are used to judge low-order equivalent systems and simulator validation. Liverpool compared fidelity metrics, including MUAD and allowable-error envelopes, for a Level-D rotorcraft simulation, and the thesis notes rotorcraft tolerances were often read across from fixed-wing without justification — [TU Delft thesis](https://repository.tudelft.nl/file/File_d2b00f3a-e42b-44d3-9133-07e756845e21); [Bell 412 Level-D fidelity (TU Delft)](https://research.tudelft.nl/en/publications/bell-412-modeling-and-model-fidelity-assessment-for-level-d-train/)
- **Integration bugs found by flying:**
  - **NASA:** pilots noticed longitudinal drift on purely lateral inputs, traced to a "stitched dynamics model implementation issue", and roll-to-yaw coupling in fixed-pitch RPM configurations — [Aires et al.](https://ntrs.nasa.gov/api/citations/20220004746/downloads/VFS%20Forum%2078%20Final%20(Fixed).pdf)
  - **Argon:** omitting the heading rotation was harmless at |ψ| < 35° but fed back cross-axis at ψ → 90° — [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md)
- **Contract on replay.** Replays and deterministic initial conditions are permitted for evidence and debugging, including to "compare airframe revisions" — [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)

### Inferences
- **Calibration chain** (per variant):
  1. **Component (G-cards):** actuator travel, rate, delay and hysteresis; fan thrust/power maps; P ∝ T^1.5 check; energy residual; static CG.
  2. **Trim (H-2, O-2, H-5):** against model predictions within Part 60 1.d / 2.b.1 tolerances.
  3. **Dynamics (H-4, O-3, O-4):** steps against 2.b.3. Sweeps feed transfer-function and state-space models: control power, damping (L_p, M_q, N_r, Z_w), coupling and τ_e. Verify on held-out doublets and 3-2-1-1s.
  4. **Tasks:** HQTE/MTE scores.

  Fix failures with a revision id and re-run from that level. Never tune physical parameters to make a task pass.
- **MQTG per variant.** Freeze deterministic drivers: PTIs, ground ramps, and recorded pilot traces from passing runs, used as replay evidence only. Each has a seed, checkpoint, weight/CG and environment. On every revision:
  - **Self-regression:** numerical-noise agreement for unchanged subsystems. Measure the noise by running the same revision twice. Explain anything larger.
  - **Reference agreement:** against `src/vtx/physics_model.py` or analytical predictions, within Part 60 tolerances tightened to 20% of the band for engineering-type references.
  - **Frequency-domain fidelity:** overlay revisions N and N−1 within MUAD/AEE-style envelopes.
  - **Coupling sentinels:** lateral and longitudinal steps at headings 0/90/180/270°. Body-axis responses must match within ±10%, and off-axis ratios must not change by more than 0.1.
- **Cross-variant difference audit** (proposed). List every parameter that differs between `phantom` and `phantom-fx` (mass, CG, inertia, battery and avionics location, fan radius and maps, generator/buffer, later wing height), with the *expected* sign of each card metric change:
  - forward CG shift → changed front-pair trim share in G-3/O-2;
  - larger fans → lower hover power, higher ṁ and ram drag, larger IGE height;
  - common-height wing → smaller translation roll/yaw trim asymmetry.

  Run identical drivers on both variants and compare observed against expected. A wrong-sign or unexplained difference is treated as a defect until explained. Shared components (same actuator models, same FBW code) must give identical component-level results in both variants.
- **Method choice.** Frequency-domain identification for the stabilised hover dynamics, since it is robust to the LLM's low-frequency corrections and gives delay and bandwidth directly. Time-domain output-error (or equation-error for quick estimates) for nonlinear and trim-dependent effects such as ground effect vs height, ram drag vs speed and wing CL–α. Cross-check on held-out data.
- **Crash data in validation.** Crashes test the contact, gear and failure models. Compare impact velocities, peak strut loads and post-impact motion between variants and against analytical expectations (e.g. free-fall impact speed √(2gh) after lease expiry). Classify a crash as a model defect if the physics is inconsistent, for example energy appearing or contact forces non-physical.

### Gaps
- CIFER acceptance guidelines (coherence and cost-function thresholds) weren't confirmed from a primary source.
- CS-FSTD(H) tolerance tables weren't extracted.
- Theil inequality coefficients and other time-domain fit metrics weren't sourced.
- MUAD/AEE boundary values weren't extracted.

## 7. Translation to another location: hover taxi, air taxi, short low-level transit, approach and landing criteria, go-around triggers

### Takeaway
The first hop should be a short hover-taxi or air-taxi transit:
- about 5 m/s, later ≤ 10 m/s (20 kt, the FAA hover-taxi/air-taxi boundary);
- at 6–15 m AGL, well under 100 ft;
- flown in the same M2 FBW mode as the "controllable" gate;
- ending in a stabilised hover over B judged by Precision Hover tolerances, then a vertical landing scored on sink rate, drift and settle.

Each variant flies its hop once it clears its own gates. Energy dominates: at the as-drawn ~1.6 MW, a 100 m hop needs ≈ 75 s, or about 33 kWh. Sized fx propulsion would cut that roughly in proportion to hover power, per the §5 table. A failed or crashed hop attempt is valid data, provided the gate was met before the attempt.

### Cited Findings
- **FAA definitions (JO 7110.65 §3-11).** *Hover taxi* is helicopter movement "normally below 20 knots" in ground effect. It burns fuel quickly, and downwash grows with larger, heavier helicopters. *Air taxi* is movement above 20 kt, with the pilot expected to remain below 100 ft AGL unless otherwise requested or instructed and solely responsible for selecting a safe airspeed — [FAA JO 7110.65 §3-11](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap3_section_11.html)
- **Landing-gear drop tests (14 CFR 27.725).** The limit drop test uses 13 in, or lower but not below 8 in if that gives a contact velocity equal to the greatest probable sink speed in normal power-off landings — [14 CFR 27.725](https://www.law.cornell.edu/cfr/text/14/27.725). The CS 27.727 reserve-energy drop is 1.5 × the CS 27.725(a) height — [EASA CS-27](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-small-rotorcraft-cs-27-0?page=21)
- **Part 60 landing and balked-landing tests.** Landing tests cover Category A/B approaches. The balked landing starts from a stabilised approach at the landing decision point — [Part 60 App. C](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60)
- **Mission rules.** Valid A and B require terrain support, stability and footprint, rotor/obstacle clearance and landing area, with reasons for refusal. Colin must fly, and A and B don't authorise an autopilot. "Touchdown is not success unless supported and settled" — [MAP_TO_MAP_FLIGHT_CONTRACT.md](../../docs/MAP_TO_MAP_FLIGHT_CONTRACT.md)
- **Current "landed" logic.** The aircraft must have left the ground, then have ≥ 3 gear supporting, be within 2 m of the destination, be "level" (R33 > 0.98, i.e. tilt < ~11.5°), have speed < 0.15 m/s and not have crashed, for 2 s sim — [live_server.py](../../src/vtx/live_server.py)
- **NASA UAM approach.** The task began in RCAH with turn coordination, then pilots manually switched to RCDH and ACAH or TRC for the low-speed portion — [Aires et al.](https://ntrs.nasa.gov/api/citations/20220004746/downloads/VFS%20Forum%2078%20Final%20(Fixed).pdf)

### Inferences
- **Equivalent sink speeds** (√(2gh)): 8 in → 2.00 m/s (393 ft/min); 13 in → 2.54 m/s; 19.5 in → 3.12 m/s.
- **Proposed touchdown scoring** (simulator, not a structural claim):
  - **Sink at first contact:** desired ≤ 0.5 m/s, adequate ≤ 1.0 m/s, fail > 2.0 m/s. Above 2.54 m/s is a hard-landing event for gear-model review.
  - **Drift at contact:** desired ≤ 0.25 m/s, adequate ≤ 0.5 m/s.
  - **Position:** ±0.91 / 1.83 m.
  - **Heading:** ±5 / 10°.
  - **Attitude:** ≤ 3° / 6°.
  - **No bounce.**
  - **Settle:** the server's 2 s rule, tightened to tilt ≤ 5°.
- **Short-transit profile (T-2)**, each step go/no-go:
  1. Vertical take-off to 3 m and a 5 s hover check.
  2. Climb at ≤ 1 m/s to 10 m.
  3. Turn to the track.
  4. Accelerate at ≤ 0.5 m/s² to 5 m/s (later ≤ 10 m/s), holding height ±1.5 m and track ±3 m.
  5. Decelerate to a hover 6 m over B in ≤ 12 s and stabilise for 10 s.
  6. Descent gate at 3 m: Precision Hover adequate bounds, ground speed ≤ 0.3 m/s, sink ≤ 0.5 m/s.
  7. Land.
  8. Shut down after settle.
- **Go-around triggers** at or below the 6 m hover / 3 m gate:
  - any Precision Hover adequate bound exceeded, or sink > 1 m/s below 3 m;
  - ground speed > 0.5 m/s below 3 m;
  - attitude > 10° or rate > 20°/s;
  - saturation > 0.5 s, power > 95%, or joker;
  - timing outside plan, or lease margin < 50%;
  - observed landing-area invalidity.

  Action: arrest descent, climb to ≥ 6 m, re-stabilise, then re-approach once or return to A. Whether Colin goes around correctly is itself scored. A crash after a correct or incorrect go-around decision is data for the crash protocol.
- **Energy:** 15 s climb + 5 s check + 20 s transit (100 m at 5 m/s) + 15 s deceleration/hover + 10 s stabilised + 10 s descent ≈ 75 s.
  - **As drawn (1.6 MW):** ≈ 33 kWh, with the buffer supplying ≈ 8.3 kWh at 1.2 MW generation or ≈ 21 kWh at 0.6 MW.
  - **fx:** scale by its hover power (e.g. ~1.14 MW at R = 0.35 m, 1,300 kg → ≈ 24 kWh).
  - Card budget = 1.2× plus a bingo reserve for an immediate landing from 15 m.

### Gaps
- The AIM §4-3 wording wasn't retrieved (JO 7110.65 was used).
- No eVTOL-specific stabilised-approach gates or touchdown sink targets were found; the criteria above are proposals anchored on 14 CFR 27.725 and HQTE hover tolerances.
- ADS-33 Landing MTE values should replace the project-defined landing criteria once transcribed.

## 8. Deliverable: concrete test cards, variant comparison, and recommended order from first spool-up to the hop

### Takeaway
Thirty-three cards and two gates, flown on both `phantom` and `phantom-fx`:
- **Clean-data cards:** ground (G), IGE hover (H), OGE hover and identification (O), precision tasks (P), low speed (L) and translation (T).
- **Consequence cards (X):** deliberately drive to failure (lease expiry, pod failure, control-power and decision-density limits, energy exhaustion, hard landings, wind) because crashes are data.
- **Comparison card (V-1):** reports per-phase deltas between the variants.
- **Gates:** C1 "controllable" and C2 "cleared for hop", each passed per variant.

A variant that can't pass, such as an infeasible as-drawn baseline, still yields a classified failure dossier, which is a valid result.

### Cited Findings
- **Tolerance sources:** [Part 60 App. C](https://law.cornell.edu/cfr/text/14/appendix-C_to_part_60) (trim/response); [Malpica 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1306-Malpica.pdf) and [Altamirano 2023](https://rotorcraft.arc.nasa.gov/Publications/files/79-2023-1286-Altamirano.pdf) (Hover/Vertical/Lateral MTE and HQTE; failure injection 5–7 s after start); [14 CFR 27.725](https://www.law.cornell.edu/cfr/text/14/27.725) (sink); [FAA JO 7110.65](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap3_section_11.html) (taxi definitions); [14 CFR 25.103](https://federal-regs.com/title/14/part-25/25.103/) (1 kt/s).
- **Practice sources:** [Caudle 2025](https://ntrs.nasa.gov/api/citations/20250003865/downloads/DevelopmentFDModels_VFS25_David%20Caudle.pdf) (sweeps); [Eve](https://www.aerospacetestinginternational.com/news/eve-evtol-completes-hover-and-low-speed-tests.html) (build-up).
- **Repo constraints:** [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](../../docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md) (failure plus adaptation required; no rescue); [TEST_PLAN.md](../../docs/phantom/TEST_PLAN.md) (one-pod-stopped test; land or crash naturally); [PERSISTENT_PILOT_STATION.md](../../docs/PERSISTENT_PILOT_STATION.md) (up to five automatic restarts after a crash); [ARGON_CALIBRATION_REPORT.md](../../evidence/ARGON_CALIBRATION_REPORT.md).

### Inferences

#### Common conventions for every card
- **Variants.** Every card is flown on `phantom` and `phantom-fx` with identical seed, initial conditions, environment, time_scale, FBW mode and PTI definitions. Ground and identification cards run once per variant plus one repeat (deterministic). Scoring cards use n ≥ 3 per variant, interleaved A-B-B-A (§4).
- **Configuration baseline:**
  - 1,300 kg nominal for `phantom`; `phantom-fx` at its declared mass. Light/heavy and CG-shifted cases come later.
  - Pods in VTOL mode, legs extended.
  - **Wing state W0 (stowed)** for G/H/O/P/T; repeat H-2, O-2, O-4 and P-1 in **W1 (deployed, locked)** before L-cards.
  - ISA sea level, calm unless stated; PTI disarmed unless stated.
- **Entry conditions:**
  - previous card closed, with any crash classified;
  - model revision, variant hash and policy version logged;
  - time_scale meets the card's decision-interval target (≤ 1 s sim ground, ≤ 0.5 s trim, ≤ 0.2 s precision), confirmed over the first 10 decisions;
  - buffer ≥ card budget + joker, or deliberately not on X-4;
  - stabilised ≥ 5 s before each point;
  - Argon spool gate before lift-off: tilt within 1° of commanded, rpm stable, all pods responding.
- **Data:** the full §3 specification, including the crash ring buffer.
- **Scoring:** desired / adequate / fail per §4, where a crash counts as a fail for that attempt. "Pass" = desired; "Adequate" allows progression only where stated.
- **Limits:** §1 limit lines.
  - **Clean-data cards:** the PTI stops at a line, then the pilot recovers. A subsequent crash is classified and the point re-flown.
  - **X-cards:** nothing stops.

#### Phase G: on the gear
- **G-0 Configuration and instrumentation check.**
  - **Config:** power off, on gear.
  - **Inputs:** none. Static frame checks at spawned headings 0/90/180/270°.
  - **Data:** channel presence and rates; variant hash; mass/CG/inertia ledger; frame labels.
  - **Pass:** 100% channels; gear-load CG (Σ N_i r_i / Σ N_i) within ±5 mm of the ledger; inertia positive-definite; zero-power gravity check passes.
  - **Fail:** missing channel or CG mismatch > 10 mm.
  - **Variant output:** static CG difference vs the declared fx design shift.
- **G-1 Actuator sweeps (no thrust).**
  - **Config:** fans unpowered or at minimum rpm with thrust disabled.
  - **Inputs (M0):** uninterrupted ramp to each stop and back (Part 60 2.a style) for pod tilt 0→90→0°, canards −20→+25°, flaps, ailerons and legs; then 10% and 50% steps.
  - **Data:** commanded vs achieved position and rate, torque, power, delay.
  - **Pass:** both limits reached; rate ±5% of declared; delay ±10 ms; freeplay ≤ 0.25°; sign correct.
  - **Adequate:** rate ±10%.
  - **Fail:** wrong sign, stop not reached, jam.
  - **Variant output:** identical results expected for shared actuators.
- **G-2 Spool-up and zeroing gate.**
  - **Inputs (M0):** start to idle; fans to idle rpm; hold zero thrust with tilt at the VTOL angle until rpm is stable and tilt within 1°; then step to 10% hover thrust and hold 10 s.
  - **Data:** spool time constants, generator/buffer power, bus V/I, droop, tilt, gear loads.
  - **Pass:** time constants ±10% of model; no gear unloading; energy residual < 1%.
  - **Fail:** any pod mismatch > 20% or uncommanded tilt.
  - **Limit lines:** IMPACT lamp, wheel load < 10% static, faults.
- **G-3 Thrust/power calibration on the gear** (thrust-stand / tethered-hover analogue).
  - **Config:** M0, brake on.
  - **Inputs:**
    - (a) symmetric steps of 10, 20 ... 80% of W, 10 s each;
    - (b) single-pod +10% W increments from a 50% W base;
    - (c) booster idle → 20% → idle.
  - **Data:** per-pod commanded vs actual thrust, rpm, shaft/electrical power, buffer, gear normal forces, energy residual, P_ideal/P_elec per step.
  - **Pass:**
    - thrust vs model ±3%;
    - P/T^1.5 consistent within ±3% across steps, with any trend explained (includes ground proximity);
    - moment arms from single-pod steps ±2% of geometry;
    - static CG ±5 mm;
    - residual ≤ 1%.
  - **Adequate:** ±5%.
  - **Limit lines:** wheel < 10% static before the 80% step, uncommanded tilt > 1°, power > rated, joker.
  - **Variant output:** thrust/power maps (fx sizing check against momentum theory, §5 table) and the front/rear trim share needed for the measured CG.
- **G-4 Light-on-gear control checks.**
  - **Config:** M2 on gear, integrators frozen until lift-off.
  - **Inputs:** 90% W thrust, then PTI pulses of roll ±3° for 1 s, pitch ±3° for 1 s and yaw ±5°/s for 2 s.
  - **Pass:** predicted load or rate change with correct sign and magnitude within ±10%; no lift-off.
  - **Fail:** wrong sign, or magnitude error > 30%.
  - **Limit lines:** wheel unload, roll/pitch > 3°, yaw rate > 5°/s.

#### Phase H: IGE hover
- **H-1 First lift-off and set-down.**
  - **Config:** M2, decision interval ≤ 0.2 s sim.
  - **Inputs (LLM):** raise heave to the G-3 trim at ≤ 0.3 m/s; hold 0.5–1.0 m for 10 s; descend at ≤ 0.3 m/s.
  - **Pass:** drift ±0.91 m, height 0.5–1.5 m, heading ±5°, sink ≤ 0.5 m/s.
  - **Adequate:** ±1.83 m, ±10°, ≤ 1.0 m/s.
  - **Limit lines (IGE set):** attitude > 10°, rate > 20°/s, drift > 3 m, height > 3 m, lease margin < 50%.
  - Repeat until three consecutive passes per variant.
- **H-2 IGE trim shots and ground-effect height sweep.**
  - **Inputs:** stabilised 10 s hovers at 0.5, 1, 2, 3 and 5 m, each at headings 0/90/180/270° (slow turns ≤ 10°/s).
  - **Data:** power, thrust split, attitude, controls; mean and std over the last 6 s.
  - **Pass:** across headings, power ±3%, pitch/roll ±1.5°, controls ±5% (Part 60 1.d); ground-effect factor vs model ±3% at each height.
  - **Adequate:** ±5%.
  - **Variant output:** IGE curves (fx larger fans extend the classical IGE height) and trim CG shares.
- **H-3 Heading invariance** (blocking).
  - **Config:** M2, 2 m.
  - **Inputs:** at 0/90/180/270°, PTI roll +3° for 2 s then −3° for 2 s, and the same in pitch.
  - **Pass:** on-axis body-axis peaks identical across headings within ±10%; off-axis/on-axis ≤ 0.2.
  - **Fail:** heading-dependent sign, or ratio change > 0.1. A failure blocks all L and T cards for that variant.
- **H-4 IGE small-amplitude control response** (Part 60 2.b.3 equivalent).
  - **Inputs (PTI):** steps of pitch 5° and roll 5° for 4 s, yaw rate 10°/s for 3 s, vertical speed 0.5 m/s for 4 s; doublets of roll/pitch Δt = 1.2 s at ±3° and yaw Δt = 2.3 s at ±8°/s.
  - **Pass:** pitch rate ±10% or ±2°/s; pitch attitude ±10% or ±1.5°; roll rate ±10% or ±3°/s; roll attitude ±10% or ±3°; yaw rate ±10% or ±2°/s; heading ±10% or ±2°; n_z ±0.1 g; equivalent delay ≤ 100 ms; off-axis trend correct.
  - **Variant output:** control power and damping deltas (fx inertia and CG changes).
- **H-5 Low-speed IGE translations and critical azimuth** (Part 60 2.b.1/2.b.2 equivalent).
  - **Config:** M2, 3 m.
  - **Inputs (LLM):** 10 s stabilised at 2.5, 5, 7.5 and 10 m/s, forward, rearward, left and right, one new speed per sortie direction. Then steady wind of 2.5 and 5 m/s from 0, 45 ... 315° relative, then three repeats at the worst azimuth.
  - **Pass:** power ±3%, pitch ±1.5°, bank ±2°, controls ±5%; every effector ≤ 80% of authority; trim tilt vs speed within ±1° of the ram-drag-inclusive prediction.
  - **Adequate:** ±5%, 90% authority.

#### Phase O: OGE hover and identification
- **O-1 Vertical climb to OGE.**
  - **Inputs (LLM):** from 3 m, climb at 0.5 then 1.0 m/s to 10 m and hold 10 s; then repeat to 20 m.
  - **Pass:** vertical speed ±0.5 m/s or ±10%; controls ±5%; energy within plan.
- **O-2 OGE trim shots.**
  - **Inputs:** stabilised 10 s at 10 and 20 m, at four headings.
  - **Pass:** power ±3%, attitude ±1.5°, controls ±5%. Trim-derived CG agrees with G-3 and the ledger within ±10 mm or the difference is explained (cf. the 28% Argon mismatch).
  - **Fail:** unexplained > 20 mm.
  - **Variant output:** hover power and energy rate; CG-compensation margin consumed.
- **O-3 OGE steps, doublets and 3-2-1-1s.**
  - **Config:** M2, 15 m.
  - **Inputs (PTI):** as H-4, plus 3-2-1-1 roll/pitch Δt = 0.6 s at ±3° and yaw/heave Δt = 1.5 s at ±8°/s / ±0.5 m/s; two repeats each.
  - **Pass:** as H-4; predicted 3-2-1-1 responses within ±10% peak and ±0.05 s timing.
- **O-4 OGE frequency sweeps / multisines.**
  - **Config:** M2, PTI at virtual-effector reference inputs, 15–20 m.
  - **Inputs:**
    - roll/pitch 0.5–20 rad/s, yaw/heave 0.3–10 rad/s;
    - ±10% (±5% fallback);
    - 90 s if energy allows, else 2–3 segments of 30–45 s, or one 30–60 s orthogonal multisine;
    - the LLM adds only low-frequency position corrections, and those are logged.
  - **Pass:**
    - match the model within MUAD-style envelopes or ±1 dB / ±10° where coherence is good;
    - roll/pitch bandwidth ≥ 2 rad/s and phase delay ≤ 0.1 s;
    - coupling ≤ 0.2.
  - **Adequate:** bandwidth ≥ 1.5 rad/s and delay ≤ 0.15 s.
  - **Variant output:** bandwidth, delay, damping and coupling comparison.

#### Phase P: precision tasks (LLM-flown, M2, ≤ 0.2 s sim decisions)
- **P-1 Precision Hover HQTE.**
  - **Course:** approach at 3.1–5.1 m/s on a 45° line at 6.1 m; decelerate to hover; hold 30 s.
  - **Desired:** ±0.91 m horizontal, ±0.61 m altitude, ±5° heading, deceleration ≤ 8 s.
  - **Adequate:** ±1.83 m, ±1.22 m, ±10°, ≤ 12 s.
  - **Stretch:** ADS-33 timing 5/8 s.
- **P-2 Vertical Reposition and Hold HQTE.**
  - **Course:** from 6.1 m, climb 7.62 m, stabilise, return.
  - **Desired:** ±0.91 m horizontal, ±0.91 m altitude, ±5°, ≤ 24 s, 5 s stabilise.
  - **Adequate:** ±1.83 m, ±1.83 m, ±10°, ≤ 29 s.
  - **Stretch:** ADS-33 13/18 s with a 2 s stabilise.
- **P-3 Lateral Reposition and Hold HQTE** (both directions).
  - **Course:** 36.6 m at 5.14 m/s, stop, hold 5 s.
  - **Desired:** longitudinal ±1.52 m, altitude ±1.52 m, heading ±10°, speed ±1.03 m/s, endpoint ±1.52 m, overshoot ≤ 1.52 m.
  - **Adequate:** ±3.05 m, ±3.05 m, ±20°, ±2.06 m/s.
  - **Stretch:** ADS-33 Lateral Reposition (121.9 m from 12.2 m; ±3.05/6.10 m, ±3.05/4.57 m, ±10/15°, 18/22 s), after an energy check.
- **P-4 Hovering turn (project-defined).**
  - **Course:** at 6.1 m, yaw 180°.
  - **Desired:** ≤ 15 s, ±0.91 m, ±0.61 m, final heading ±5°.
  - **Adequate:** ≤ 20 s, ±1.83 m, ±1.22 m, ±10°.
- **P-5 Depart/abort-lite (project-defined).**
  - **Course:** from a 6.1 m hover, accelerate to 7.5 m/s, then stop at a marker 60 m away.
  - **Desired:** track ±1.52 m, height ±1.52 m, stop ±1.52 m, ≤ 25 s.
  - **Adequate:** ±3.05 m and ≤ 30 s.
- **P-6 Precision vertical landing (project-defined, 27.725-anchored).**
  - **Course:** from a 6.1 m hover over the pad.
  - **Desired:** sink ≤ 0.5 m/s, drift ≤ 0.25 m/s, ±0.91 m, ±5°, attitude ≤ 3°, no bounce, settle 2 s at tilt ≤ 5°.
  - **Adequate:** ≤ 1.0 m/s, ≤ 0.5 m/s, ±1.83 m, ±10°, ≤ 6°.
  - **Fail:** > 2.0 m/s, bounce, or no settle.

#### Phase X: consequence cards (crashes expected and recorded; each follows its clean counterpart, on both variants)
- **X-1 Lease-expiry consequence** (after H-1).
  - **Course:** hover at 0.5 m, then 1 m, then (optionally) 3 m, and deliberately withhold commands beyond the 5 s sim lease.
  - **Data:** feather/idle sequence, descent, impact.
  - **Expected:** free-fall upper bounds of 3.1 / 4.4 / 7.7 m/s impact; residual spool thrust will lower these.
  - **Output:** a verified failsafe consequence and contact-model check.
- **X-2 One-pod failure** (after H-4/O-3; required by TEST_PLAN).
  - **Course:** hover at 1 m IGE, later 10 m OGE. Fail one pod 5–7 s after stabilisation (NASA practice), with an annunciation; the pilot then attempts recovery and landing.
  - **Data:** time to each limit line, residual controllability (which axis is sacrificed), allocator behaviour, impact.
  - **Output:** recoverability per variant and per failed pod.
- **X-3 Control-power ladder** (after O-3).
  - **Inputs:** steps at increasing amplitude (attitude 5, 10, 15, 20, 30°; yaw rate 10, 20, 40°/s; heave 0.5, 1, 2, 3 m/s) until saturation or departure.
  - **Output:** maximum achieved angular accelerations and rates, saturation onset and the "cliff". NASA saw sudden HQ degradation at powertrain saturation.
- **X-4 Energy-exhaustion hover** (after O-2).
  - **Course:** hover at 3 m until the buffer reaches its limit with generation below hover demand, then fly the power-limited descent and landing.
  - **Output:** measured endurance vs the §5 prediction, and power-limited landing sink rate. This is a key variant discriminator.
- **X-5 Hard-landing ladder** (after P-6).
  - **Inputs:** deliberate touchdowns at 0.5, 1.0, 1.5, 2.0, 2.5 and 3.0 m/s.
  - **Output:** strut stroke, peak loads, bounce, damage flags; gear-model validation against the 2.0 / 2.54 / 3.12 m/s anchors.
- **X-6 Decision-density ladder** (after P-1 passes).
  - **Inputs:** repeat P-1 with the sim-time decision interval raised 0.2 → 0.3 → 0.5 → 0.75 → 1.0 s via time_scale, until adequate fails or a crash.
  - **Output:** controllability boundary vs pilot-loop delay, per variant.
- **X-7 Wind ladder** (after H-5).
  - **Inputs:** hover and P-1 in steady wind of 5 → 7.5 → 10 m/s from the critical azimuth, then light and moderate Dryden turbulence.
  - **Output:** wind limit per variant.

#### Phase V: variant comparison
- **V-1 Variant comparison report** (after each of phases G, H, O, P, X, L and T). A paired table per card covering:
  - static and trim CG, and front/rear trim share (CG-compensation margin);
  - hover power, energy rate and endurance;
  - control margins in trim and at peak;
  - identified bandwidth, delay, damping, coupling and control power;
  - IGE curve and ram-drag/trim-tilt slope;
  - HQTE pass rates and objective levels;
  - crash counts by class, and recovery rates on X-cards;
  - hop outcome.

  Each delta is checked against the expected sign from the §6 difference audit. An unexpected sign opens a model-defect investigation before the next phase.

#### Gate C1: declare "controllable" (per variant, hover and low speed, M2)
All of the following:
1. G-0 to G-4, H-1 to H-5 and O-1 to O-4 passed, or adequate with every discrepancy explained and a revision recorded; MQTG baseline frozen.
2. **H-3:** pass.
3. **P-1:** adequate in all and desired in ≥ 3 of 4, at two headings 90° apart.
4. **P-2 and P-6:** adequate in all and desired in ≥ 2 of 3; no touchdown > 1.0 m/s.
5. **P-3 each direction:** adequate in all and desired in ≥ 1 of 2.
6. **P-4 and P-5:** adequate.
7. **Margins in the scoring runs:**
   - no data-validity stop;
   - no saturation > 0.5 s;
   - hover power ≤ 90% of available;
   - trim authority ≤ 80% per effector.
8. **O-4:** bandwidth ≥ 2 rad/s, delay ≤ 0.1 s, coupling ≤ 0.2, no PIO flag, FBW transport delay ≤ 100 ms.
9. **Pilot loop:** p95 ≤ 0.2 s and p99 ≤ 0.5 s sim decision interval; effective delay ≤ 0.3 s sim; time_scale stated.
10. **MQTG self-regression:** pass.
11. **X-cards:** X-1, X-2 and X-5 flown at least once, with every crash in the build-up classified and its lesson or revision recorded. Crashes don't block C1; unexplained crashes do.

#### Phase L: low speed (after C1; first campaign stops at 20 m/s)
- **L-1 Forward low-speed trim shots and power curve.**
  - **Config:** M2 OGE (10–15 m), W0 then W1.
  - **Inputs (LLM):** stabilised 10 s at 5, 7.5, 10, 12.5, 15, 17.5 and 20 m/s, then a ±2 m/s speed-stability check at fixed power.
  - **Pass:** power ±3%, trim tilt ±1°, attitude ±1.5°, back-side trend (dP/dV ≤ 0) reproduced.
  - **Adequate:** ±5%.
- **L-2 Corridor probing** (later campaign). Stabilised points at 1.3 → 1.2 → 1.1 × the predicted boundary, then ≤ 1 kt/s ramps to the §5 end lines.
  - **Pass:** CL–α and boundary speed within ±5% of model.
  - **Wing-height check:** compare roll/yaw trim asymmetry, as-drawn staggered wing vs fx common-height wing.
- **L-3 Stall-speed determination** (later campaign). Clean then flapped, fans unloaded, after L-2. Departures are consequence data.

#### Phase T: translation
- **T-1 Local pattern rehearsal.**
  - **Course:** at A, lift off to 6 m, hover-taxi 30 m out at ≤ 2.5 m/s, hover 10 s, return and land.
  - **Pass:** P-1 adequate at both hovers, P-6 desired at landing, energy ≤ 110% of prediction.
- **Gate C2: cleared for hop** (per variant):
  - C1 holds and T-1 has passed;
  - B validated by the map contract;
  - 1.5 × hop energy ≤ energy available above bingo;
  - wind no worse than demonstrated in H-5/X-7.
- **T-2 Hop A→B** (first at 5 m/s over 100–150 m, later ≤ 10 m/s over 150–300 m).
  - **Profile and go-around triggers:** as in §7.
  - **Pass:** track ±3 m, height ±1.5 m, Precision Hover adequate over B (desired preferred), P-6 desired touchdown, and a "landed" outcome with tilt ≤ 5°.
  - **Adequate:** P-6 adequate touchdown.
  - **Fail:** collision, no settle, or a data-validity stop.
- **T-2X Consequence hop** (optional). A variant that hasn't cleared C2, such as the as-drawn baseline if infeasible, may fly the same hop labelled "expected-to-fail" for comparison data. It never counts as a hop success.

#### Recommended order
1. G-0 → G-1 → G-2 → G-3 → G-4 on both variants, then V-1(G).
2. H-1 (to three consecutive passes) → H-2 → H-3 (blocking) → H-4 → H-5, then X-1 and X-7 (calm and low wind first), then V-1(H).
3. O-1 → O-2 → X-4 → O-3 → X-3 → O-4, then model update and frozen MQTG per variant, then V-1(O).
4. P-1 → P-2 → P-6 → X-5 → P-3 → P-4 → P-5 → X-6, with X-2 at any point after O-3, then V-1(P/X).
5. **Gate C1** per variant.
6. W1 repeats of H-2, O-2, O-4 and P-1 → L-1 → T-1.
7. **Gate C2** per variant.
8. T-2 at 5 m/s, then T-2 at ≤ 10 m/s (and T-2X if used), then V-1(T).
9. Later campaign: L-2 → L-3 and conversion.

Throughout: interleave variants A-B-B-A within each card; change one variable per step; compare with the model's pre-test prediction (Eve's building-block rule); re-run the MQTG after any model change; and raise time_scale only after three clean runs.

### Gaps
- Several tolerances are project-defined proposals, not standards: ±5 mm static CG, ±10 mm trim-CG, actuator ±5% rate, ±1° trim tilt, P-4/P-5/P-6 values and the limit-line numbers. Review them against ADS-33E §3.11 once transcribed, and against FTM-107 practice.
- `phantom-fx` parameters aren't defined in the repository yet, so its energy budgets, expected trim shares and fan IGE height must be filled in when declared. The as-drawn plant architecture and buffer size are also still undecided.
- Pod positions, FBW gains and sensor models aren't defined for either variant. Predicted values for each tolerance check must come from the model at the time each card is run.
