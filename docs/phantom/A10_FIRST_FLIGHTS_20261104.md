# Phantom A10: first take-offs and flights (2026-11-04)

**Headline.** The A10 left the ground under wing lift in **8 of 11 rolling take-off runs**. Wheels came off at
**69–106 m/s** (155–237 mph), and the best run climbed to **32 m**. Every flight ended in a pitch divergence. The
data below says why, and what fixes it with real hardware.

The runs used the MuJoCo plant (`PhantomAircraft`, DT 2.5 ms), the as-drawn A10 at **1,906 kg**, and canned pilot
schedules on a flat 8 km test strip (`FlatWorld`). Tool: `tools/phantom/phantom_campaign.py`. Raw data:
`evidence/phantom/campaign_*.json` and `evidence/phantom/a10_takeoff_series_20261104.json`.

## 1. Take-off series

Every run used the same set-up: wings deployed and locked, flaps 30° (they auto-retract above V_FE = 75 m/s),
canards deployed, full wheel drive and full boosters.

| Run | Technique | Wheels off (m/s) | Ground roll | Height | Pitch excursion |
|---|---|---|---|---|---|
| r50 | raw pitch 1.0, rotate 50 m/s | **74.4** | 2.51 km | — | −73 / +78° |
| r60 | raw pitch 1.0, rotate 60 m/s | **69.3** | 1.59 km | — | −75 / +63° |
| r70 | raw pitch 1.0, rotate 70 m/s | **79.1** | 1.57 km | — | −49 / +52° |
| att55 | attitude 9°, rotate 55, Kp 1.2 | **89.5** | 2.18 km | 17.6 m | −70 / +74° |
| att60 / att65 | attitude 9°, Kp 1.2 | no rotation | — | — | — |
| kp3 | attitude 9°, Kp 3 / Kd 0.6 | **90.7** | 2.29 km | **32.4 m** | −54 / +74° |
| kp5 | attitude 9°, Kp 5 / Kd 1.0 | no rotation | — | — | — |
| kp8 | attitude 9°, Kp 8 / Kd 1.6 | **84.9** | 3.54 km | 20.8 m | −58 / +39° |
| P-T1a | attitude 10° @ 70, Kp 3 / Kd 0.8, trim 0 | **103.0** | 7.18 km | 6.2 m | −77 / +81° |
| P-T1 | P-T1a + larger EDF boosters (proposal) | **106.4** | 4.91 km | 6.0 m | −70 / +77° |

Once rotated, aero lift reaches **2.2–4.1 W**, so lift is not the limit. The limits are **pitch control** and
**thrust after the wheels leave**.

## 2. Why the flights diverge

| Quantity at 95 m/s (q = 5.5 kPa) | Value | Source |
|---|---|---|
| Cm_α of the whole vehicle | **+0.72 /rad (statically unstable)** | plant aero sweep |
| contribution: canards / wing | +1.23 / −0.35 /rad | geometry (handover) |
| M_α | 13.7 kN·m/rad, time-to-double **0.33 s** | I_yy 3,018 kg·m² |
| canard moment per unit FBW demand (15°) | 6.1 kN·m | plant canard model |
| Kp needed for static stability | **≥ 2.25** (baseline 1.2) | M_α / M_δ |
| canard actuator | 40°/s, stall at 14° | handover limits |

Higher gains reach static stability (kp3 flew farthest), but the 0.33 s divergence outruns a 40°/s canard that
stalls at 14°. That is rate saturation. The canards are both the destabiliser and the only pitch control.

## 3. Why it can't hold speed once airborne

| At 95 m/s, L = W | Value |
|---|---|
| CL needed | 0.86 (S_ref 3.934 m²) |
| drag (plant CD ≈ 0.23) | **≈ 5.0–5.2 kN** |
| EDF booster thrust at that speed | **2.2 kN** (4.7 kN static: thrust lapse of a 0.0445 m² exit) |
| wheel drive | 0 once airborne |
| L/D | ≈ 3.6 |

Power is not the limit. D·V ≈ 0.5 MW, and the generators make 1.15 MW. The small EDF exits waste it.

## 4. Supporting measurements

**Mass and VTOL.** 1,906 kg against 1.152 MW electrical. Each fan is capped at 3.68 kN, and disk loading at hover
is 31 kN/m². Hover needs **2.63 MW**. Available T/W is **0.58** (power-limited) or 0.79 (thrust-limited). The VTOL
test measured **T/W 0.52** at 1.26 MW, matching the cockpit log's 53%. The maximum hover mass is 1,099 kg
(power) or 1,502 kg (thrust).

**Booster ignition** (brakes on, step command):

| Throttle | t10 | t50 | t90 | Steady thrust | T/W | Shaft power |
|---|---|---|---|---|---|---|
| 0.5 | 0.08 s | 0.18 s | 0.26 s | 1.20 kN | 0.06 | 74 kW |
| 1.0 | 0.16 s | 0.52 s | 1.24 s | **4.71 kN** | **0.25** | **577 kW** |

Throttle commands rotor speed, so thrust goes as ω²: half throttle gives a quarter of the thrust.

**Road acceleration** (flat strip):

| | 0–60 mph | 0–100 km/h | 0–200 km/h | at 45 s | peak |
|---|---|---|---|---|---|
| wheels | 8.0 s | 8.3 s | 17.4 s | 106 m/s | 0.35 g |
| wheels + boosters | **5.2 s** | **5.3 s** | **10.8 s** | 132 m/s | 0.59 g |

The plant has no tyre speed limit. Above about 85 m/s it rides on 1–2 contacts.

**Aero sweep** (wings locked, 60 m/s): flaps 30° reach CL 1.44 at α 14°. L = W at 73 m/s (flaps) or 80 m/s
(clean). CD0 is 0.183.

## 5. Real parts to close it

Data is from manufacturer and trade sources. "Estimate" marks my own arithmetic.

| Need | Part | Data | What it does here |
|---|---|---|---|
| thrust at 95 m/s ≥ 5.2 kN | **4 × PBS TJ150** turbojet | 1.5 kN, 18.9 kg, SFC 0.116–0.119 kg/N/h ([PBS](https://www.pbs.cz/en/letectvi/letecke-motory/pbs-tj150), [datasheet](https://pbs.cz:443/getmedia/27d922e1-9402-4b7a-b279-9e0f6517c190/PBS_Turbojet-engine_TJ150-_EN.pdf.aspx?ext=.pdf)) | 6.0 kN static and about 5.4 kN at 95 m/s (estimate, ~10% lapse). 75.6 kg against 70 kg for the EDF pair. About 700 kg/h of fuel at full. Frees 577 kW for the wheels |
| | **1 × Williams FJ33-5A** turbofan | 8.2–8.5 kN, about 130 kg dry, SFC 13.8 g/kN/s, certified 2016 ([Wikipedia](https://en.wikipedia.org/wiki/Williams_FJ33), [Flaris](https://www.airframer.com/news/release/34773)) | about 6.5–7 kN at 95 m/s (estimate), a positive climb gradient of about 9%, about 410 kg/h at full |
| mass (the heavy bugger) | **one 1 MW-class turbogenerator** | Honeywell 1 MW generator: 280 lb (127 kg), ~8 kW/kg, ~97%, ran 900 kW continuously ([AIN](https://backend.ainonline.com/news-article/2022-06-02/honeywell-reports-progress-one-mw-turbogenerator-tests), [AVweb](https://www.avweb.com/aviation-news/honeywell-develops-compact-generator-for-hybrid-aircraft/)); HTS900 turbine 153 kg ([Wikipedia](https://www.wikipedia.org/wiki/Honeywell_HTS900)) | about 280 kg for 0.9 MW against 540 kg for 1.15 MW now: **−260 kg** |
| lift-fan motors (check) | H3X HPDM-250 | 200 kW continuous, 18.7 kg incl. inverter and gearbox ([Sustainable Skies](https://sustainableskies.org/h3x-four-years-later/)) | the ledger's 460 kW / 38 kg pod motor is at the edge of this class |
| | magniX magni350 / magni650 | 350 kW, 128 kg / 640–700 kW, 206–220 kg ([AIN](https://www.ainonline.com/news-article/2021-06-18/magnix-expands-power-options-350-kw-and-650-kw-electric-propulsion-units)) | too heavy for the pods |
| 500–1,200 kW turbogenerator | Rolls-Royce AAM turbogenerator | announced 2022, in development ([Rolls-Royce](https://www.rolls-royce.com/media/press-releases/2022/22-06-2022-rr-advances-hybrid-electric-flight-with-new-technology.aspx)) | not yet a product |

**VTOL even after the mass cut.** At 1,646 kg, hover still needs about 2.1 MW against 0.9 MW. The in-wheel fans
cannot lift this vehicle. The A10 is a rolling take-off flying car unless its lift system changes.

## 6. Next engineering steps

1. **Pitch stability.** Make the DRS flap an all-moving stabilator in the plant (it is visual today), and apply
   the existing `p5_canard_area_scale` = 0.5. The estimate is Cm_α from +0.72 to about −0.24 /rad, which is
   statically stable. Then the canards and stabilator only have to trim and manoeuvre.
2. **Propulsion.** Add a turbojet booster model to the plant (thrust and lapse from datasheets, fuel from SFC,
   no electrical draw). Fly the 4 × TJ150 and 1 × FJ33-5A options.
3. **Mass.** Model the single 1 MW-class turbogenerator (−260 kg) and re-run the series.
4. **Actuators.** A faster pitch actuator (≥ 100°/s) as a second line of defence against rate saturation.

## 7. Proposals P6, P7 and P8, flown in the plant

All three are **off by default**: baseline behaviour and the existing tests are unchanged. The parameters are in
`inputs/phantom_parameters_v1.json` under `proposals.p6_*`, `p7_*` and `p8_*`, each with a unit, a source and a
label. Tests: `tests/test_phantom_p6_p7.py`.

**P6: the DRS flap as an all-moving stabilator.** It becomes a real surface in `SurfaceAero` (geometry and section
from `engineering/phantom/drs_flap.py`). It is driven by the FBW pitch demand through a 100°/s actuator, and it
deploys as an airbrake on the brake command while rolling, so the drag is now real. Canard area is scaled × 0.5.

| Cm_α about the ledger CG (plant, 60 m/s, flaps 0) | /rad |
|---|---|
| as drawn | **+0.837** (unstable) |
| canards × 0.5 only | +0.226 |
| stabilator only | +0.532 |
| **P6 (both)** | **−0.079** (stable, margin about 2% MAC) |

The plant omits the hull Munk moment. `wing_loads.py` estimates up to +2.2/rad with its SYNTHETIC factor. If that is
real, P6 alone is not enough for the real vehicle. This is register item U3, and it needs CFD.

**P7: turbine boosters from datasheets.** The model has datasheet static thrust, SFC fuel burn, first-order spool
and a momentum thrust lapse T = T₀(1 − V/V_j). It draws no electrical power. Engine mass enters the ledger as dry
mass × 1.15.

| Option | Static thrust (plant) | t90 | Fuel at full | Vehicle mass | CG x |
|---|---|---|---|---|---|
| EDF boosters (as drawn) | 4.7 kN | 1.2 s | (577 kW electrical) | 1,906 kg | −0.732 m |
| **4 × PBS TJ150** | **5.8 kN** (T/W 0.31) | 5 s (TJ80 anchor) | about 710 kg/h | 1,924 kg | −0.744 m |
| **1 × Williams FJ33-5A** | **8.0 kN** (T/W 0.41) | 5 s (14 CFR 33.73) | about 410 kg/h | 1,987 kg | −0.788 m |

**P8: wing incidence.** The wing cassette is mounted at +7° or +9°, so the wing lifts without the body rotating.
This is a CAD change to the cassette mount, modelled as geometric incidence of the wing surfaces.

### Flights (flat 8 km strip, attitude-hold pilot schedule)

| Run | Configuration | Static thrust | Wheels off | Ground roll | Max height | Pitch range | Outcome |
|---|---|---|---|---|---|---|---|
| p6_edf | P6 + EDF boosters | 4.7 kN | 119 m/s | 7.55 km | **4.6 m** | -87 / +87° | ran off the 8 km strip (invalid) |
| p6_tj150 | P6 + 4x TJ150 | 5.8 kN | 111 m/s | 1.55 km | **0.0 m** | -0 / +0° | bounce only, no rotation |
| p6_fj33 | P6 + FJ33-5A | 8.0 kN | 89 m/s | 0.74 km | **0.0 m** | -0 / +0° | bounce only, no rotation |
| p6_tj150_kp3 | P6 + 4x TJ150, Kp3/Kd0.8 | 5.8 kN | 117 m/s | 2.23 km | **0.0 m** | -0 / +1° | bounce only, no rotation |
| p6_fj33_kp3 | P6 + FJ33-5A, Kp3/Kd0.8 | 8.0 kN | 125 m/s | 3.47 km | **11.5 m** | -77 / +82° | lift-off, then pitch loss of control |
| p8_7_tj150 | P6+P7 TJ150+P8 7 deg | 5.8 kN | 84 m/s | 0.84 km | **0.0 m** | 0 / +1° | bounce only, no rotation |
| p8_7_fj33 | P6+P7 FJ33+P8 7 deg | 8.0 kN | 68 m/s | 0.66 km | **19.5 m** | -80 / +67° | lift-off, then pitch loss of control |
| p8_9_tj150 | P6+P7 TJ150+P8 9 deg | 5.8 kN | 65 m/s | 0.97 km | **0.9 m** | -9 / +9° | lift-off, then pitch loss of control |
| p8_9_fj33 | P6+P7 FJ33+P8 9 deg | 8.0 kN | 60 m/s | 0.65 km | **19.3 m** | -66 / +66° | lift-off, then pitch loss of control |
| sw_e1_kp0.6_kd0.5 | sweep P6+P8 7 deg + 4x TJ150, Kp 0.6 / Kd 0.5 | 5.8 kN | 95 m/s | 1.50 km | **5.8 m** | -78 / +82° | lift-off, then pitch loss of control |
| sw_e1_kp0.6_kd1.0 | sweep P6+P8 7 deg + 4x TJ150, Kp 0.6 / Kd 1.0 | 5.8 kN | 71 m/s | 0.90 km | **21.1 m** | -75 / +89° | lift-off, then pitch loss of control |
| sw_e1_kp1.2_kd1.0 | sweep P6+P8 7 deg + 4x TJ150, Kp 1.2 / Kd 1.0 | 5.8 kN | 94 m/s | 1.45 km | **11.7 m** | -77 / +80° | lift-off, then pitch loss of control |
| sw_e1_kp2.0_kd1.2 | sweep P6+P8 7 deg + 4x TJ150, Kp 2.0 / Kd 1.2 | 5.8 kN | 86 m/s | 1.03 km | **23.4 m** | -70 / +76° | lift-off, then pitch loss of control |
| sw_e2_kp0.6_kd0.5 | sweep P6+P8 7 deg + FJ33-5A, Kp 0.6 / Kd 0.5 | 8.0 kN | 69 m/s | 0.70 km | **20.4 m** | -68 / +80° | lift-off, then pitch loss of control |
| sw_e2_kp0.6_kd1.0 | sweep P6+P8 7 deg + FJ33-5A, Kp 0.6 / Kd 1.0 | 8.0 kN | 94 m/s | 1.20 km | **10.7 m** | -87 / +83° | lift-off, then pitch loss of control |
| sw_e2_kp1.2_kd1.0 | sweep P6+P8 7 deg + FJ33-5A, Kp 1.2 / Kd 1.0 | 8.0 kN | 86 m/s | 0.93 km | **0.3 m** | 0 / +12° | crash on the roll |
| sw_e2_kp2.0_kd1.2 | sweep P6+P8 7 deg + FJ33-5A, Kp 2.0 / Kd 1.2 | 8.0 kN | 86 m/s | 0.92 km | **2.3 m** | -1 / +11° | lift-off, then pitch loss of control |

### What this shows

1. **P6 works but removes rotation authority.** A statically stable 1.9 t car cannot rotate about its rear wheels
   on half-size canards. It rolls to 108–117 m/s at 0° pitch and does not lift off. The earlier lift-offs
   (section 1) happened *because* the airframe was unstable.
2. **P7 closes the thrust gap with real engines.** Both options accelerate the car well past lift-off speed.
3. **P6 + P7 + P8 takes off.** With the wing at +7–9°, the A10 leaves the ground at **60–95 m/s after 0.65–1.5 km**
   and reaches **19–23 m**. The FJ33 at 9° lifts off at 60 m/s (134 mph).
4. **Every flight still ends in pitch loss of control.** An 8-run Kp/Kd sweep does not fix it. The FBW pitch loop
   was built for fan-borne hover: PD on attitude, with no gain scheduling, no stall protection and no trim
   integrator. With 7° incidence the wing stalls at only about 10° body pitch.

**Next:** a wing-borne pitch control law. That means pitch-rate command with attitude hold, gains scheduled on q,
an α limiter, a trim integrator, and the stabilator as the primary pitch effector with the canards for trim. Design
it on a plant linearisation about the trimmed lift-off state.

Data: `evidence/phantom/a10_p6_p7_p8_series_20261104.json` and `evidence/phantom/campaign_p6_*`, `campaign_p8_*`
and `campaign_sw_*`.
