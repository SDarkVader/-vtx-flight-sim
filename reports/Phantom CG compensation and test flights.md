# Nose packaging and FBW rescue the Phantom

The VTX Phantom's pitch-balance problem is a packaging problem first and a control problem second. The as-drawn aircraft is too tail-heavy, and its CG sits **0.54–0.58 m behind the four-pod thrust centroid**. The fix is to move the buffer battery and avionics into the nose and put fuel in the vacated under-floor bay. That moves the CG about 0.27 m forward (option N2: x ≈ −0.31 m) for +6 kg of harness. It has to be paired with mandatory fly-by-wire (FBW) relaxed-stability augmentation, front/rear pod thrust differential for hover pitch trim, and probably a larger canard with a flap. The A10 split-level wing cassette removes the A9's 118 mm left/right wing-height stagger completely, at a cost of +9 kg. In the simulator, the as-drawn `phantom` (1,897 kg) **cannot lift off**: its thrust tops out at 53% of weight. The repackaged `phantom-fx` hovers at 1.21–1.41 MW and flew a 200 m hop east to a 0.40 m/s touchdown 1.4 m from the target. It still failed the "controllable" gate (C1) because of about 2x attitude overshoot, a pitch oscillation, weak yaw and a pilot who decided only every 5–17 s. The campaign also exposed 19 simulator defects. The worst were a browser panel silently overriding the pilot, a legacy 10 kg fuel default, a CG gate that never produced an answer, and a "landed" verdict given while the fans still carried the weight. Most of these were fixed with 17 new regression tests. Contact-stiffness and failsafe-policy items were deferred. Every number here comes from a simulator model labelled SYNTHETIC_UNVALIDATED, so none of it is validated aircraft performance.

## The CG sits half a metre behind the thrust, and only packaging moves it enough

The independent ledger puts the baseline CG at **x −0.56 m (5–95%: −0.60 to −0.50) at about 1,610 kg**. The simulator's own build-up is worse: **1,897 kg at x −0.734**, which gives the rear pods 36% of the weight each against 14% for each front pod ([CG ledger](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/cg_ledger_from_build.md)). Configuration changes barely matter. Wing deploy and canard fold give Δx ≈ 0, the legs give Δz −0.011, driver-only seating gives Δy −0.016, and fuel burn gives about ±0.01. The cassette moves mass only sideways, so no transient needs mechanical compensation. Scheduling FBW trim on configuration state at about 1 Hz is enough ([CG study](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/cg_and_compensation.md)).

The approved fix has two variants:

| Option | Layout | CG x | Crush length ahead of the pack |
|---|---|---|---|
| N1 | Battery centroid at x 1.60 | −0.29 | ~0.6 m |
| N2 (recommended) | Battery behind the front bulkhead, radiator moved forward | −0.31 | ~1.1 m |

N2 is preferred because the road car's nose is its crush zone, and the extra crush length is worth the 0.023 m of CG it gives up. The concrete hardware:

- **Battery.** A 192s10p Molicel P50B pack: 34.6 kWh, 800 V bus, about 400 kW continuous, about 193 kg. It sits on a CFRP or titanium cradle sized for **53 kN forward** (193 kg × 28 g, from the ECE R100 shock pulse) ([Molicel P50B](https://www.fsaeonline.com/content/Molicel-TDS--INR-21700-P50B-80122.pdf); [TÜV SÜD R100](https://www.tuvsud.com/en-us/industries/mobility-and-automotive/automotive-and-oem/automotive-testing-solutions/battery-testing/un-ece-r100)).
- **Avionics.** About 18 kg in the nose, with triplex flight computers of the Veronte 4x class ([Veronte 4x](https://www.NWUAV.com/media/veronte/Autopilot-4x-datasheet.pdf)).
- **Fuel.** An ATL-type bladder of about 85 L under the floor plus a 22 kg cell under the sleeve, with Weldon 8150-B boost pumps ([ATL](https://atlinc.com/ATL-33-Gallon-Sprint-Fuel-Cell.html)).

The active alternatives were rejected on the numbers:

| Option | CG shift | Problem |
|---|---|---|
| Battery sled on a Thomson Electrak HD, 0.3–0.6 m stroke | 0.036–0.071 m | Mass, jam and runaway failure modes ([Thomson](https://thomsonlinear.com/en/products/linear-actuators/electrak-hd)) |
| Fuel transfer, 30 kg over 1 m | 0.019 m in about 15 min | Too slow and too small. Concorde needed about 20 t to move its CG about 2 m ([Heritage Concorde](https://www.heritageconcorde.com/fuel-transfer)) |
| Seat rails | ±0.010 m | Negligible |

Ballast stays useful only as a per-test-card simulator body. A leg load-cell weight-and-balance estimate should gate every take-off. Accuracy of about 0.02 m is enough, because in hover a CG error shows up directly as pod differential.

## Packaging alone cannot close hover or slow wingborne trim

Moving the CG is necessary but not sufficient. With 3,700 N per pod, no packaging option hovers at the ledger mass: the most-loaded pod would need **1.26–1.44 × T_max**. Pod tilt acts about the X axis, so pitch trim in hover can only come from the front/rear thrust split. That split costs ideal power of **+4.5% at baseline and +1.1% at N1** ([CG study](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/cg_and_compensation.md)).

Wingborne, the vortex-lattice neutral point is −0.72 m without the body. Body pitching moment is uncertain by a factor of about 4, and it pushes the static margin at N1 anywhere from −1% to −130% MAC. **The vehicle is probably statically unstable in pitch.** That makes canard-based FBW in the style of the X-29 and YF-16 mandatory: the X-29 flew at −35% MAC with a time to double of about 0.14 s ([NASA NTRS 19900002437](https://ntrs.nasa.gov/citations/19900002437); [NTRS 19760024050](https://ntrs.nasa.gov/citations/19760024050)).

The sharpest conflict is the canard. For the canard to stall before the wing, the CG must be aft of about −0.54 m. A hover-friendly CG instead pushes the canard-limited minimum speed to **about 81–90 m/s at N1**, against a wing-only stall of 65 m/s. The proposed resolution:

- **P5:** canard area ×1.5 with a plain flap. This gives Vmin of 59–69 m/s across the CG range. It follows the Piaggio P.180 and Beech Starship approach to the same flap-plus-canard trim problem ([Starship](https://en.wikipedia.org/wiki/Beechcraft_Starship); [three-surface aircraft](https://en.wikipedia.org/wiki/Three-surface_aircraft)).
- **P3:** about 2 kN of downward booster thrust in hover, using the existing directional nozzles. This is the cheapest hover enabler.
- Mass reduction toward 1,300–1,400 kg, and pods uprated to at least 5 kN.

All of these are proposals that need owner approval.

## The A10 cassette zeroes a stagger that mattered structurally, not aerodynamically

The A9 wings sat at z 1.0015 and 0.879, a **118 mm stagger**. Potential-flow analysis showed this stagger had no effect on the neutral point and only a small rolling-moment effect (Cl −0.0003 to +0.0008, about 0.15–0.35° of aileron). A 0.1° left/right incidence mismatch would matter twice as much. The real case for a common height is symmetry of junction flow, stall onset, root stiffness and aeroelastic twist ([CG study](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/cg_and_compensation.md)).

The study set these A10 requirements: height residual ≤ 10 mm, incidence match ≤ 0.05°, matched twist under 1 g, root stiffness within 5%, and side masses within 0.2 kg. The chosen split-level cassette meets all five. Both panels ride in one upper level, and half-chord tongues run side by side in a lower level divided by a spar.

| A10 result | Value |
|---|---|
| Height residual | 0.0 mm (common z 0.9873) |
| Incidence difference | 0.0° |
| Slide body masses | 27.03 / 27.03 kg |
| Bay mass change | +9.01 kg |
| CG change | Δx +19.9 mm, Δz −17 mm |
| Max ultimate pin force | 51.2 kN (A9: 54.3) |
| Clearance sweep | 0 collisions |
| MuJoCo joints | All 28 reach both limits |

Four other layouts were rejected. One could not stow the hatch, one was heavier, one was too long for the bay, and one needed pin forces of 262–497 kN ([A10 redesign](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/wing_symmetry_redesign.md)). Root stiffness and twist rest on mirror-identical construction and have not been checked by FEA. The nose-battery sizing still has to be rerun for the extra 9 kg.

## Low-speed calibration flights: the FX hovers and hops but is not controllable

The campaign was flown in M2 mode (attitude command, vertical-speed command, yaw-rate pedal), with nothing holding position ([flight test](../docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md); [campaign summary](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/flight_campaign.md)).

**As drawn.** In the on-gear thrust test (G-3), the rear pods saturated at about 3,530 N at 8,480 rpm, with the generators at their 1.2 MW cap. The attitude-priority allocator then cut the front pods to about 1,385 N, capping total thrust at **0.529 W**. The bench had claimed 0.79 W.

**FX.** Thrust was linear at 1.54 W per unit collective. Trim results out of ground effect (O-2):

| Load | Collective | Power | Front share | Roll stick | Derived endurance |
|---|---|---|---|---|---|
| FX-C (1 occupant) | 0.648 | 1.21 MW (71 W/N) | 0.458 | −0.13 | 517 s |
| FX-A (2 occupants) | 0.706 | 1.41 MW (76 W/N) | 0.460 | 0 | 397 s |

The front share matches the ledger CG of about −0.15 m.

**Handling (O-3).**

| Axis | Result |
|---|---|
| Roll | 3° doublet peaked at 6.6°, about 2.2x overshoot |
| Pitch | 1.7x overshoot, settling 10–18% beyond the command |
| Yaw | 4 deg/s achieved for 8 deg/s commanded |
| Vertical | Within ±0.05 m/s; the one honest axis |

**Minimal-speed card (L).** Speed was 1.6, 3.1 and 4.8 m/s at −1.6, −3.6 and −4.0° pitch, roughly 1° per m/s and dominated by ram drag. Power at 4.8 m/s was 5% below hover. There was no measurable ground effect: the factor was 1.002 at 1.9 m, and power in ground effect was higher than out of it. Translation produced a **sustained ±3–8° pitch oscillation** with a period of 2–3 s. Speeds above 5 m/s and wings-deployed flight were not reached, so the wingborne minimum-speed results above remain analytical. With a wing loading of about 3.1 kN/m², everything below 60–70 m/s is powered lift ([test methods](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/flight_test_methods.md)).

**The hop.** Gate C1 failed, so the hop was flown as **T-2X ("expected to fail")** in run `192918-14ade4`:

- **Route:** 200 m due east, from (13.7, −28.4) to (213.7, −28.4). It was chosen as validator-passed, flat, turn-free and clear of trees.
- **Profile:** climb to 18 m, nose down 4.5° to 4.9 m/s, then decelerate with 5° commanded. The aircraft reached 8°.
- **Track:** ended 12 m right of track (tolerance ±3 m), with height ranging 15–18.7 m (tolerance ±1.5 m).
- **Landing:** 0.40 m/s touchdown, 1.4 m from B, after 116 s.
- **Cost:** 131.5 MJ, 10.2 kg of fuel, and 12% of the buffer.

**Crashes.** An unplanned lease expiry (X-1) from 3.1 m braked the fans from 3,600 to 40 rpm in 0.5 s. The aircraft hit at **7.14 m/s**, and the solver reported a **863 kN** peak with the airframe 0.19 m below ground. A hard-landing ladder (X-5) up to 2.91 m/s produced a 17.3 kN foot force and no damage flag.

**Data collected.** All run folders are under `evidence/phantom/flight_campaign_20261103/`:

- `phantom_steps.csv.gz` at 100 Hz;
- the physics audit at 20 Hz;
- `events.jsonl` with every pilot decision and its reason;
- PTI events;
- `crash_ring.npz` and `lease_abort_ring.npz`;
- a calibration JSON, a cards index and a pilot log.

## From inside the model: a JSON cockpit where latency is the aircraft

The AI pilot's cockpit log is blunt: "I don't sit anywhere". The cockpit is a JSON observation, with no acceleration cues and no sound, and the aircraft keeps flying on the last command between looks ([cockpit log](../docs/phantom/PHANTOM_COCKPIT_LOG_2026-11-03.md)). Each decision cost **3 s of flight at time scale 0.25 and 5–15 s at 0.1**. The p95 interval was 10–17 s against the 0.2 s target, which is 25–80x too slow.

The cockpit view also hid several failures:

- **"Dead fans."** These looked like an engine fault. In fact a browser panel was re-sending collective 0.
- **Lease crash.** It appeared only as an IMPACT lamp after a silence.
- **"Landed" at B.** The sortie was ended with the fans still loud and carrying nearly the whole weight.

The pilot left with six rules:

1. Pre-spool the generator on the gear before lift-off.
2. Trim roll −0.13 with one occupant.
3. Always run a keep-alive link. It was added after the crash and resends "hold" every 0.1 s of sim time.
4. Use half-size stick inputs.
5. Use one degree of pitch per m/s of speed.
6. Remember that the yaw pedal (+ = nose right) and the gyro reading (+ = nose left) use opposite signs.

The pilot's verdict: the FX "will hover and carry me 200 m to a gentle touchdown" but is not yet controllable, and the as-drawn Phantom "is not an aircraft at all".

## Simulator errors: control, accounting and frame bugs fixed, contact and control laws deferred

The fixes were tested by pytest (163 → 180 tests) and node (5 → 8), and the physics changes were recorded as R-1 to R-6 ([sim fixes](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/sim_fixes.md)).

**Fixed:**

| ID | Problem | Fix |
|---|---|---|
| D-1 | Browser panel silently overrode the pilot | Panel is inert until engaged and shows "PANEL ENGAGED" |
| D-2 | Legacy 10 kg fuel default | Default as-drawn mass now 1,897 kg (R-6) |
| D-3 | CG gate ran at t = 0, before the aircraft settled | Gate runs after settling |
| D-8 | "Landed" without weight on the gear | Landing needs ≥ 80% of the weight off the fans; landing back at A is now scored |
| D-14 | Touchdown chatter | Air/ground state debounced at 0.25 s |
| D-12 | Step log unreadable mid-run | Log flushed each sim-second |
| D-9 | Bench claimed more thrust than the allocator delivers | Bench reports an allocator ceiling: 0.520 W against 0.529 W live |
| D-18, F4 | Radar altimeter read 0.75 m on the gear | Reference is now a downward ray from the lowest foot (R-5) |
| F1 | Training assist read body rates in principal-inertia axes; a roll disturbance became about 10 deg/s of pitch | Corrected frame (R-1) |
| F3 | Fuel draw | Draw conserves the total burn (R-2) |
| F8a | Governor | Integrator held, not dumped, during an overspeed cut (R-3) |
| F11a | `implicitfast` integrator drifted angular momentum 49% in 20 s | Switched to `implicit`, about 0.04% (R-4) |
| F14 | Cockpit keyboard left/right reversed | Controls made pilot-relative |
| F16 | Importing the server wrote into evidence | Import no longer writes |

The commit also lists a tyre `solref` change. The notes do not detail it.

**Deferred as design decisions rather than bugs:**

- the lease-abort fan brake (D-5);
- the 863 kN contact artefacts from the stiff `solref .008` and `solimp` setting, and foot forces never classed as a crash (D-15);
- unloaded front oleos on the as-drawn aircraft (D-4);
- underdamped attitude with no trim or heading hold (D-6, D-7);
- the missing ground effect (D-16), brake creep and unmet power (D-11, D-13);
- the missing duct, edgewise-flow and VRS models (F5–F7) ([fidelity audit](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/sim_fidelity_audit.md)).

A separate visual-only graphics pass changed only `public/` and left the physics untouched. It added quality tiers, terrain-draped paint and trees fitted to their colliders ([graphics](../research_notes/Phantom%20CG%20compensation%20and%20test%20flights/graphics_changes.md)).

## Conclusion

The campaign turned the CG problem from a debate into a measurement. The FX's hover front-pod share of 0.458 matched the ledger's predicted CG, which validates the mass build-up as a design tool even though its inputs are synthetic. The open problems now lie elsewhere. Hover is limited by thrust and power, and the wingborne envelope is limited by canard size. Neither moves the CG, so further packaging work has diminishing returns. The next gains come from P5 (larger canard with a flap), P3 (booster assist) and body-Cm data.

Three things must come before any C1 retry. First, the D-6/D-7 control-law work: trim integrators, heading hold, and damping of the pitch oscillation. Second, a pilot loop at least 25x faster. Third, a decision on contact compliance and failsafe policy, so that crash data can be read as structural loads. Until then, the simulator will keep scoring slow pilots and stiff contacts more than it scores the aircraft.
