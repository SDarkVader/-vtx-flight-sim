# Phantom FX-A A10-B: model specification

**A10-B is the current, default Phantom** in the physics plant and the game (`phantom-a10b`). It is the flown A10-A configuration plus the model fixes and control systems found and calibrated in the 9 November 2026 take-off and flight investigation.

All numbers below come from the canonical model:
* characteristics: `PYTHONPATH=src python tools/phantom/a10b_spec.py` writes `evidence/phantom/a10b_characteristics.json`;
* behaviour: test runs on the plant, listed in section 7.

Raw telemetry, the rendered test images and the investigation write-up are on the reference branch [`reference/phantom-a10b-20261109`](https://github.com/SDarkVader/-vtx-flight-sim/tree/reference/phantom-a10b-20261109/reference/phantom_a10b_20261109).

Every Phantom number is a labelled DERIVED, MANUFACTURER or SYNTHETIC_UNVALIDATED figure (see the parameter files), not a measurement of a built vehicle.

## 1. Use it

```python
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld
a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road')   # or 'vtol'
```

* **Game:** the model selector lists *Phantom FX-A A10-B · CURRENT PROTOTYPE* first and selected. On page load, an idle server on its boot R6 switches the inspection aircraft to A10-B. A cockpit pinned to R6 (`VTX_ENFORCE_RELEASE=1`) refuses the switch. The API defaults (`Mission()`, the lab's boot aircraft) stay R6 for the R6 pilot tooling.
* **Visual model:** `public/assets/phantom-a10b-visual.glb` (built by `tools/phantom/build_a10b_visual.py`).
* **Configuration identity:** A10-B is config `3ecae1a9`. A10-A as flown (`phantom-fx` + P6) is still `70089cca`, and its P6-off sibling `b835295b`; a test pins both.

## 2. What it can do now

| Capability | Status | Evidence |
|---|---|---|
| Drive and steer on the road | **Yes.** Front steer-by-wire, ±35° lock, speed-scheduled to 0.8 g lateral; 18.2 m radius at 11 m/s (kinematic 16.9 m). | U2 / steering tests |
| Deploy the wings from a standing start | **Yes.** Locked at 25.1 m/s, 386 Pa (limit 600 Pa = 31.3 m/s). The guard refuses a late start and closes the hatch. | W1, W1g |
| VTOL take-off and hover | **Yes.** Thrust-to-weight 1.38. Hover about 1.3–1.4 MW (900 kW take-off rating for 300 s plus buffer). | VTOL capture, V2 |
| Fan-assisted wing flight, fans facing down | **Yes.** Stable with the wing-borne law. | V2, V3b |
| Decelerate with the nose held | **Yes.** 95 → 51 m/s in 6 s, peak 0.81 g, nose held at 4° (one 1.5 s dip to −0.8°), altitude within 1.3 m. | V2 |
| 90° turn, decelerating | **Yes.** 30° bank from 60 m/s: 90° in 29.4 s along a 480 m arc, ending in hover; nose 2.3–5.0°, altitude −0.1 m. | V3b |
| Wing-borne flight with the fans off | **No.** At 90 m/s it departs nose-down within about 2 s even with surfaces and TVC saturated: the hull lift makes it unstable (Cm_α +2.9/rad) beyond the aerodynamic control power. | V3a |
| Rolling (conventional) take-off | **No.** It cannot rotate: about 27 kN·m is needed about the rear tyres against about 8–10 kN·m available at 85 m/s. Speed tops out at 85–99 m/s. | T1–T4, R4, TB |

## 3. Alterations from A10-A

| Change | Why | Parameters (label) |
|---|---|---|
| **Hull lift / Munk term** (forebody K 9.28 m² at x +1.81 m; yaw side profile 1.66 m² at +1.30 m) | The base plant had no body lift. Vortex lattice of the CAD hull: dCm/dα +5.3/rad (Multhopp check +5.7). | `aero.hull_lift.*` (DERIVED) |
| **Road suspension** (slide joint per wheel, 1.6 Hz, damping 0.35, preloaded, travel −0.12/+0.08 m) | The rigid wheels hopped at speed (tyre only, 3.7 Hz, damping 0.18, 18.6 mm sag). | `suspension.*` (SYNTHETIC) |
| **Wheel-drive limits** (60 kW per hub motor, slip limiter 0.15) | The base plant ignored the rated hub power. An unloaded wheel overspun to 452 rad/s and touched down with a 208 kN one-step contact force. | `drive.*` (SYNTHETIC) |
| **Wing incidence 7°** (P8) | Raises lift at low body angle so the forebody instability is exposed less. | `proposals.p8_wing_incidence_deg` |
| **P6 DRS stabilator** (as flown in A10-A) | Pitch control and road downforce. | `proposals.p6_*` |
| **Front steer-by-wire** (hinge joint per front wheel, 660 N·m per wheel, 40°/s; take-off lock ±2° at 10°/s once the wings leave the hull) | The car could not turn on the road (0.0° with the yaw stick; 0.6° by skid steer). The turn comes from tyre forces: with zero friction the same steered wheels give +0.1°. | `effectors.steering.*` |
| **Fin rudders** (30 % chord, τ 0.55, ±25°) | No yaw control existed in wing-borne flight; the hull makes the airframe directionally unstable (Cn_β −0.03/rad). | `effectors.rudder.*` |
| **Booster thrust vectoring** (±20°, pitch and yaw) | Fast pitch and yaw authority independent of airspeed: about ±2.3 kN·m at 95 m/s. | `effectors.tvc.*` |
| **Actuator calibration** (canards, stabilator, rudders, TVC on Moog Model 965: 70°/s) | Real hardware rates and torques (the canards were a synthetic 40°/s). | `effectors.canard_rate_deg_s`, `proposals.p6_stab_rate_deg_s` (MANUFACTURER) |
| **Wing-borne control law** (gains scheduled on dynamic pressure 400 → 2000 Pa: pitch 12/rad, 2.0 s; roll 2/rad, 0.5 s; yaw 1.0 s; sideslip 3/rad; bank to 45°) | The hover-tuned law (1.2/rad, 0.25 s) let the airframe depart in 1.4 s (V2 old-law run). | `fbw_wingborne.*` (DERIVED) |
| **Wing deployment guard** | The base sequencer checked dynamic pressure only when the slide started (one run locked at 43.7 m/s, 1,171 Pa) and could leave the hatch open (to 6.4 kPa). | sequencer logic, handover `transit_q_limit_Pa` |
| **Added mass** 35.6 kg (actuators, rudders, steering) | The new systems are mass-bearing. | `effectors.added_components` |

## 4. Model characteristics

**Mass properties:**
* mass 1,933 kg;
* CG (body frame) x −0.174 m, z 0.564 m;
* inertia diagonal Ixx 903, Iyy 4,280, Izz 4,990 kg·m².

**Geometry:**
* length 4.89 m, body width 2.50 m, wheelbase 3.13 m, track 2.50 m, tyre radius 0.55 m;
* wing S_ref 3.934 m², span 4.858 m, MAC 0.872 m, AR 6.0, aerodynamic centre x −0.806 m, incidence 7°;
* wing loading 4,819 Pa.

**Aerodynamics** (95 m/s, wings out, flaps 0):
* Cm_α +2.9/rad (unstable; A10-A was −2.7);
* Cn_β −0.03/rad (directionally unstable; A10-A +0.10);
* free pitching moment −6.2 kN·m at 0° body angle, −2.4 kN·m at 4°, +2.8 kN·m at 8°, +12.2 kN·m at 12°;
* lift 12.7 kN at 0°, 23.2 kN at 4°.

**Propulsion and power:**
* four wheel fans: 6.55 kN each, 0.59 m² disk each, thrust-to-weight 1.38, rotor inertia 0.6 kg·m²;
* two EDF boosters: 2.57 kN static, 1.55 kN at 95 m/s;
* hub motors: 600 N·m, 60 kW;
* generator: 600 kW continuous, 900 kW for 300 s;
* buffer: 80 kWh at x +1.80 m (nose).

**Chassis:**
* spring rates 42.3 kN/m front, 51.6 kN/m rear;
* dampers 2.9–3.6 kN·s/m;
* tyre contact tuned on the 19 kg unsprung wheel;
* steering servo critically damped at about 15 Hz.

**Wing deployment:**
* sequence 5.52 s (hatch 1.0, slide 4.0, pins 0.5);
* transit limit 600 Pa (31.3 m/s).

**90° level turn** (coordinated):

| Speed | Bank | Radius | 90° arc | Time | Yaw momentum (Izz·ω) |
|---|---|---|---|---|---|
| 30 m/s | 45° | 92 m | 144 m | 4.8 s | 1,630 N·m·s |
| 45 m/s | 30° | 358 m | 562 m | 12.5 s | 630 N·m·s |
| 95 m/s | 45° | 920 m | 1,446 m | 15.2 s | 520 N·m·s |

Each fan rotor carries 251 N·m·s at hover speed. The four spin in opposing pairs, so the total cancels; the gyroscopic moment per pod in these turns is 7–82 N·m.

## 5. Parts and real components

| System | Component | Data used | Source / label |
|---|---|---|---|
| Canard, stabilator, rudder and TVC actuators | **Moog Model 965** rotary servo actuator | 2,200 / 2,500 lb-in (249 / 282 N·m), 70°/s no-load at 28 VDC, ±90°, 5.2 kg | [Moog datasheet](https://www.moog.com/content/dam/moog/literature/products/actuation/model-965-rotary-actuator-technical-datasheet.pdf), MANUFACTURER |
| Front steering actuator | **ZF AKC 2nd generation** class central actuator | 11 kN, for vehicles to 3.5 t; speed not published | [ZF press release](https://press.zf.com/press/en/releases/release_20547.html), MANUFACTURER (force) |
| Steering reference designs | Schaeffler Intelligent Corner Module; Hyundai Mobis e-Corner | Up to 90° wheel angle, steer-by-wire; no steering-torque data published | [eeNews](https://www.eenewseurope.com/en/vehicle-concept-combines-wheel-hub-drive-with-90-degree-steering), [WardsAuto](https://www.wardsauto.com/news/archive-auto-hyundai-mobis-e-corner-system-ces-in-wheel-motors-crab-drive/704326/) |
| Steering rate reference | Chalmers rear-steer actuator study | At least 25°/s | [Chalmers](https://odr.chalmers.se/items/dc4affcf-cca2-476c-8b54-c7b4ee79aece/full) |
| Considered, not used | Volz DA 58-D (80 N·m continuous, >200 N·m peak, 5.6 kg); Ultra Motion T-Series (12.2 N·m at 310°/s) | No published rate (Volz); too little torque for the rudder at 120 m/s (Ultra Motion) | secondary sources |

Masses with no published figure (steering actuator 8 kg, rudder surfaces 0.8 kg each) are SYNTHETIC_UNVALIDATED.

## 6. Flight control

* **Hover law:** unchanged. It still runs below 400 Pa dynamic pressure, and in every A10-A configuration.
* **Wing-borne law:** blends in up to 2,000 Pa. It allocates pitch to the canards (15° per unit demand), stabilator (15°) and TVC (20°); yaw to the rudders (25°) and TVC (20°); roll to the ailerons. The fans' differential thrust stays in the loop whenever collective > 0.02.
* **Why the fans matter:** they're the decisive pitch effector (about ±14 kN·m), but they lag about 0.3–0.9 s. So the surfaces and TVC take the fast motion and the fans hold trim and lift. With the fans off, the fast effectors alone cannot hold the hull instability (section 2).

## 7. Test record (9 November 2026)

| Test | What it established |
|---|---|
| T1–T5 | A10-A take-off roll: the moment budget about the rear tyres; flaps retracting at 75 m/s; tail-strike angle 11.9°; the 7° incidence "lift-offs" were tyre hops. |
| Munk / VLM | Hull lift and Munk moment; CAD envelope within 3 % of the parameter file. |
| R1–R4 | Rolls with hull lift, suspension and drive limits. The hop artifact was traced to wheel overspin; speed tops out at 92–99 m/s. |
| R5 | As-drawn A10 with the 4 Nov campaign's take-off schedule: no lift-off inside the strip, with or without the drive limits. The 4 Nov "wheels off" results need re-checking against the drive limits. |
| U1, U2 | Static pitch and yaw derivatives with the hull term; the car could not turn on the road. |
| V1–V3 | Flight with the fans facing down: deceleration, the decelerating turn, and the fans-off wing-borne departure. |
| W1, W1g | Wing deployment from a standing start; the guard. |
| Images | 13 rendered frames with data panels (deployment, steering, VTOL, take-off roll, braking, turn) plus two A10-B model views. |

The regression tests are `tests/test_phantom_a10b.py` (default and identity, composition, mechanical steering, VTOL-centred steering, take-off lock, effector signs, control-law blend, deployment guard) and `tests/test_phantom_overlays.py`.

## 8. Known gaps and next steps

1. **Rolling take-off:** rotation needs about 3× the pitch moment available. Options: move the main gear toward the CG, raise the nose on its legs or suspension, or a short take-off on the fans.
2. **Wing-borne flight with the fans off:** needs more pitch control power or less forebody lift (shaping), not gain alone.
3. **Not modelled:**
   * ducted-fan crossflow moments and loads (duct lip lift and pitching moment), which in reality limit fan use at speed;
   * aerodynamic loads on the hatch, slide and pins during deployment;
   * ground effect on the hull;
   * density change with altitude;
   * flap auto-retraction above 75 m/s is still active;
   * the wing zero-lift angle is hard-coded at −2°.
4. **Visual model:** rudder surfaces and the TVC yaw deflection are not in the mesh yet.
5. **Hard cornering:** tyre-contact chatter at the 0.8 g limit (support count drops to 2 in one capture).
