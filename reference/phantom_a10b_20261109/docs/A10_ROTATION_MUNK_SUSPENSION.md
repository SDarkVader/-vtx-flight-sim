# Phantom A10: take-off rotation, hull Munk moment and road suspension

Build examined: `phantom-fx` (FX-A A10) with the P6 DRS stabilator, config `70089cca`, the configuration of 66 of
the 72 A10-A register runs (4-7 Nov). Config `b835295b` (4 runs) is the same build with P6 off. Both SHAs were
reproduced from the parameter tree. Tests are canned schedules on the MuJoCo plant (flat 8 km strip), not piloted
flights; each test was chosen from the telemetry of the one before.

## 1. Why the take-off roll does not rotate

| Test | What it showed |
|---|---|
| T1 instrumented roll (attitude mode, rotate command at 70 m/s) | CG is 1.438 m ahead of the rear tyre contact: weight moment 26.8 kN m nose-down. Front tyres still carry 5.3 kN at 118 m/s. Pitch demand saturates at 0.209 (attitude gain 1.2/rad x 10 deg cap): canards +3.1 deg, stabilator 9.1 deg. |
| T2 per-surface aero | Wing CL 0.14 at zero incidence (2.2 kN per side at 115 m/s). Flaps retract automatically above 75 m/s (`control_limits.flap.max_speed_m_s`). Stabilator at its 6 deg rest makes 1.37 kN downforce, only 0.46 m behind the rear contact. |
| T3 static authority about the rear contact | Nose-up available at 120 m/s: 11.0 kN m (attitude law), 18.9 kN m (full stick / full deflection) vs 26.8 kN m needed: no rotation at any reachable speed. 7 deg wing incidence + full stick rotates at about 100-120 m/s. Tail-strike angle 11.9 deg (hull 0.81 m aft of the rear contact). |
| T4 dynamic rolls, full stick | As flown: pitch 0.07 deg max to 115 m/s. 7 deg incidence: rotates at 93.9 m/s, wheels leave at 93.8 m/s, then tumbles. 7 deg + battery at x +0.5: wheels off 92.7 m/s, collision. |
| T5 contact log of the 7 deg run | No hull-ground contact. Lift 14.4 kN < 18.6 kN weight at 94 m/s: the "lift-off" is tyre hopping (spikes to 76 kN). Road load path has no suspension: tyre only, 3.7 Hz, damping ratio 0.18, 18.6 mm static deflection. |

Model items that work against the take-off, independent of the airframe design:
1. flaps auto-retract above 75 m/s, before any rotation speed;
2. attitude mode caps the pitch demand at 0.209;
3. no road suspension (tyre on a pod servo; the oleo legs are only in the VTOL load path);
4. wing zero-lift angle hard-coded at -2 deg in `surface_aero.py` (the handover `cm0` term is multiplied by 0);
5. no hull lift / Munk moment; constant air density with altitude.

Sensitivities (live build): moving the 311 kg nose buffer from x +1.80 to -0.06 cuts the rotation moment to
21.1 kN m but raises the hover rear-pod load from 5.0 to 5.9 kN of 6.55 kN.

## 2. Hull lift and Munk moment

`tools/phantom/hull_lift_vlm.py` takes exact plane sections of the body-only CAD envelope
(`public/assets/phantom-a10.glb`; plan 10.38 m2 vs the parameter file's 10.14 m2, side 4.07 vs 3.96 m2) and solves a
horseshoe vortex lattice. Free air, thin surface, no ground effect. Results in `evidence/phantom/hull_lift_vlm.json`.

| Estimate | dCm/dalpha (/rad, S 3.934 m2, c 0.872 m) |
|---|---|
| Closed-body slender-body potential (upper bound) | +10.1 |
| Multhopp forebody, no upwash credit | +5.7 |
| Vortex lattice, forebody (used) | +5.3 (K 9.28 m2 at x +1.81 m) |
| Vortex lattice, whole planform (check) | +5.2 |

The plant's stability with P6 is Cm_a = -2.67/rad; with the hull term it is about +2.6/rad (statically unstable).
Yaw counterpart: side profile ahead of the fins K = 1.66 m2 at x +1.30 m, destabilising, against fins of about
1.06 m2 at 1.91 m behind the CG.

## 3. Overlays (opt-in, base configs unchanged)

`inputs/phantom_overlays/*.json`, merged as Params overrides with `vtx.phantom.overlays.load(...)`. Without them the
base config SHAs (`70089cca`, `b835295b`) and every register grouping are unchanged.

* `hull_lift_v1`: forebody normal force N = q K sin(a) cos(a) at x +1.81 m (pitch) and the side-profile term at
  x +1.30 m (yaw), written bilinearly so it vanishes at 0 and 90 deg and is exact in any direction. The wing already
  spans the body (screening basis), so only the forebody is added. Crossflow drag stays in the existing body drag.
* `road_suspension_v1`: a slide joint between each pod and wheel along the pod z axis (vertical in road stance).
  Spring 42.1 kN/m front / 49.9 kN/m rear (1.6 Hz on the sprung corner mass), damping ratio 0.35, preloaded to keep
  the design ride height, travel -0.12 / +0.08 m. The tyre `solref` is converted on the 19 kg unsprung wheel, because
  MuJoCo's solref is mass-normalised (on the 474 kg corner mass the tyre would come out ~25x too soft).

* `wheel_drive_limits_v1`: the hub motor's rated power (`pods.hub_motor_power_w`, 60 kW, present in the parameter
  file but not used by the base plant) caps the drive torque at P/omega, and a slip limiter fades the torque to zero
  between 1x and 2x a 0.15 slip ratio. Found by the reruns below: see R2/R3.

Tests: `tests/test_phantom_overlays.py`.

## 4. Roll series rerun

Same schedule as T4 (full stick in rate_damping from 70 m/s; 0.5 s after wheels-off, attitude hold at 5 deg).

**R1, hull lift + suspension.**

| Run | Result |
|---|---|
| As flown + suspension only | No rotation (0.82 deg max to 114 m/s). The suspension alone does not change the moment balance. |
| As flown + hull + suspension | The front springs extend as the nose unloads; the body sits ~1 deg nose-up, the hull lift adds to it and the nose comes up at 106-107 m/s (rotation). Then it departs: pitch 2 -> 4 -> 12 -> 42 deg in ~0.9 s with the controls saturated. That is the static instability from the hull term. |
| 7 deg incidence + hull + suspension | Pitch held within +/-1.3 deg; skimming touchdowns. |
| 7 deg + battery at x +0.5 + hull + suspension | Rotates from 81 m/s, wheels off at 82 m/s, then a 508 deg/s pitch-rate spike and a tumble. |

**R2/R3, the spike.** At 100 Hz, then per physics step: the front-left wheel was unloaded at full droop while the full
wheel-drive command was still applied. Nothing limited the hub motor (no power limit, no traction control), so it
overspun to 452 rad/s, a 248 m/s tyre surface speed at 82 m/s road speed. On touchdown MuJoCo's soft contact
produced 208 kN in one 2.5 ms step to remove that slip, kicking the wheel up at 20 m/s. The 76 kN single-tyre spikes in
the rigid-wheel T5 hops are probably the same mechanism. Hence the `wheel_drive_limits_v1` overlay.

**R4, hull lift + suspension + wheel drive limits.**

| Run | 0-90 m/s | Speed at strip end (7.4 km) | Wheels off | Last 10 s |
|---|---|---|---|---|
| As flown + all three | 33.6 s, 1.94 km | 99.4 m/s | never | pitch 0.76 deg (suspension), lift 0.36 W |
| 7 deg incidence + all three | 37.1 s, 2.22 km | 96.3 m/s | never | front tyres 1.3-2.4 kN, lift 0.79 W |
| 7 deg + battery at x +0.5 + all three | 38.2 s, 2.32 km | 92.1 m/s | never | front tyres at zero load, springs near full droop, lift 0.81 W |
| 7 deg incidence + drive limits only (rigid wheels) | 37.3 s, 2.24 km | 96.0 m/s | never | no hops at all |

What R4 shows:
* With the drive limited to its rated power, the roll flattens out at 92-99 m/s: the 60 kW per wheel cap (plus the
  boosters) meets the drag. Without the cap the base plant ran 600 N m per wheel at any speed, about 104 kW per wheel
  at 95 m/s, so its acceleration figures and the R1 rotation at 106 m/s were optimistic.
* The hops and "lift-offs" of T4/T5 and R1 do not occur once the wheels cannot overspin: they were the drive artifact,
  not lift.
* The 7 deg + battery-aft case reaches the rotation threshold (front tyres unloaded) at about 92 m/s, which is close
  to the speed the drive can reach.
* Wherever the nose does come up with the hull term on (R1), the airframe departs in pitch within about a second:
  the hull lift makes it statically unstable and the FBW's pitch authority is already saturated at rotation.
