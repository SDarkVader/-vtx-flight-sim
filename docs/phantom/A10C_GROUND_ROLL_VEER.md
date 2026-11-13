# Phantom A10-C: why it veers on a slow ground roll (13 November 2026)

Findings only. Nothing in the model, parameters or control software was changed for this note. Every figure is from
the MuJoCo plant on the `work/a10c-cockpit-controls-20261112` code (commit `eb85581`), Main Airport runway, scripted
inputs, run headlessly. Scripts and raw outputs: `engineering/phantom/a10c_ground_roll/`.

## What was seen

On 12 November the AI-piloted "runway centreline retest" flights (half wheel drive, boosters off, rate-damping mode)
left the centreline at 33 to 40 m/s with the yaw stick at zero. The afternoon's take-offs (full drive, both boosters,
attitude mode) and the pilot's own flights did not. The question was what happens in the aircraft between 20 and
45 m/s with the wheels on the ground.

## The runs

Take-off stance means wings out and locked, canards deployed, flaps 30, nose strut extended (3.7 deg nose-up). All runs
start from rest at the runway 08 threshold; the chart stops at 46 m/s or at the crash.

| Case | Result |
|---|---|
| Take-off stance, drive 0.5, boosters off, rate damping | Rear pods lift to 6.9 deg from 20 m/s; rear tyres at 4.5 to 5.0 kN sideways, fighting each other; one rear wheel off the ground 5 to 7 % of the time; yaw diverges from 34 m/s; spins at 39 m/s; crash. |
| Same, attitude mode | Same. Diverges from 34 m/s, opposite direction. The mode is not the cause. |
| Same, full drive and both boosters (the documented take-off schedule) | 46 m/s in 11 s with 1.2 deg of yaw. The same fight is present (rear pods 5.9 deg, rear tyres 4.3 kN at 34 m/s) but the aircraft is through the band before the yaw grows. |
| Road stance (wings stowed, strut retracted, pitch 0) | Straight to 46 m/s. Rear pods within 0.06 deg. |
| Wings, canards and flaps out but **no nose lift** (pitch 0) | Straight to 46 m/s. Rear pods within 0.06 deg. |
| Take-off stance with the pod tilt joints **pinned at 0** (a mechanical down-lock, diagnostic only) | Straight to 46 m/s, 0.6 m off the centreline. Rear tyres still reach 3.4 kN sideways by 46 m/s from 0.015 deg of toe. |

## The mechanism

1. **The pod hinge is at the wheel centre.** The tilt hinge (body X axis) and the wheel axle share the same anchor, so
   the tyre contact patch is one tyre radius, 0.55 m, below the hinge. Any sideways tyre force puts that force times
   0.55 m on the tilt joint, in the direction that lifts the pod toward VTOL.
2. **Nothing holds a pod down except its servo.** The tilt joint has a hard stop at 0 deg on the road side only. Toward
   VTOL it is held by a position servo: 20,000 N m/rad, 3,000 N m stall (`pods.tilt_*`). 2,600 N m of tyre moment
   therefore means about 7 deg of pod lift. There is no down-lock or latch in the model.
3. **In the take-off stance pod tilt becomes toe.** With the body pitched 3.7 deg nose-up the tilt axis is no longer
   horizontal, so a pod lifted by angle d turns its wheel by d x sin(3.7 deg) about the vertical. Both rear pods lift
   outward, so the two rear wheels toe in against each other: 6.9 deg of lift gives 0.43 deg of toe each. Measured toe in
   the runs matches this to three decimals. At pitch 0 the coupling is zero, which is why the road-stance and
   no-nose-lift runs are clean.
4. **The simulated tyre has no cornering stiffness.** The tyre is a rigid Coulomb contact (`friction 1.0`, soft
   constraint, no slip-angle law). Measured at 31 to 35 m/s on the front wheels (`tyre.py`):

   | Toe per wheel | Sideways force / normal load |
   |---|---|
   | 0.00 deg (steering servo compliance only) | 0.14 |
   | 0.01 to 0.02 deg | 0.13 |
   | 0.05 deg | 1.00 (friction limit) |
   | 0.1 to 2 deg | 1.00 |

   The force saturates at the friction limit by 0.05 deg of slip, an effective stiffness of about 2.6 MN/rad per
   tyre. A road tyre of this load has about 60 to 90 kN/rad and saturates near 6 to 8 deg. The modelled tyre is roughly
   thirty to forty times too stiff sideways, and that is what makes the loop below diverge.
5. **The loop.** Sideways force lifts the pod; pod lift becomes toe (only when pitched); toe makes sideways force. With
   the modelled tyre the gain is far above one, so the rear pods go to the servo's limit and both rear tyres sit at the
   friction limit, pushing against each other with no net force on the aircraft. With a slip-angle tyre of 60 kN/rad the
   same loop has a gain of about 0.15 and settles at a fraction of a degree.
6. **Why it then yaws.** Rear tyres at their friction limit have no reserve for a real cornering force, and they hop
   (5 to 7 % airborne). The rear axle cannot react any yaw disturbance, so the aircraft is directionally unstable on its
   wheels. The seed is the front steering's own compliance (about 0.05 deg, through the 3.5 cm of mechanical trail the
   pitch creates), aero asymmetry and the hopping. Nothing in the flight computer resists it: on the ground the yaw
   loop drives only the rudders and booster vectoring, the nosewheels follow the yaw stick alone, and in every mode.

   Aerodynamic yaw authority on the ground, from the surface model (`aero_auth.py`), against the 7,000 N m one rear
   tyre at its limit exerts about the CG:

   | Speed | Rudders at 25 deg, yaw | Canards +10 / -10 deg, roll | Canards +10 / -10 deg, yaw | Canards +10 / +10 deg, lift |
   |---|---|---|---|---|
   | 30 m/s | 263 N m | 220 N m | 2 N m | 125 N |
   | 40 m/s | 468 N m | 391 N m | 3 N m | 222 N |
   | 60 m/s | 1,052 N m | 881 N m | 8 N m | 499 N |
   | 80 m/s | 1,870 N m | 1,566 N m | 14 N m | 888 N |

   Below 60 m/s no aerodynamic surface in the model comes within an order of magnitude of the tyre forces.

7. **Why the full-thrust take-off works.** The fight needs about 15 s in the 20 to 40 m/s band to build and let the
   yaw grow. At full drive and boost the aircraft spends 5 s there. Whether that margin matters is a judgement for the
   operator: in the model, a rejected take-off, a slow roll with the wings out, or a bump that unloads a rear wheel
   between 20 and 40 m/s would meet the same mechanism.

## What this does not say

* It does not say the aircraft cannot fly. Flown by the schedule in `A10C_FANS_OFF_TAKEOFF.md` it reaches rotation speed
  straight, and the pilot has flown it from a standing start to flight by hand, repeatedly, without a veer. The veer
  appeared only in the AI-piloted slow rolls.
* It does not identify the pod tilt servo as "the" fault. Three things combine: hinge at the wheel centre with no
  down-lock, the pitched stance, and a tyre with no slip-angle compliance. Removing any one of them stops the
  divergence in simulation; only the first two exist on a real aircraft.
* The pilot's observation that the canards keep the aircraft straight on take-off is reproduced. Same full-thrust
  schedule, four canard conditions (`takeoff.py`):

  | Canards | Track at lift-off | Lift-off |
  |---|---|---|
  | Deployed, under the attitude loop (as flown) | 4.7 m off the centreline, 0.1 deg yaw | 80 m/s, 1,156 m |
  | Folded | 16.7 m off, drifting through the roll | 88 m/s, 1,597 m |
  | Held full nose-up (+25 deg) | 3.4 m off | 74 m/s, 952 m |
  | Held full nose-down (-20 deg) | 7 to 16 m off | none: still rolling at 96 m/s |

  In the model they do it through pitch, not side force: the canards carry the nose as the wing loads up, so the
  aircraft leaves its wheels before the rear-pod fight has time to swing it. Nose-down canard, which keeps the
  nosewheels loaded, is the worst case here because it keeps the aircraft on the ground longest. The flight computer
  commands the canards symmetrically; the 0.2 / -2.8 deg readout in the 12 November screenshots is the two trim
  sliders set differently (the aero hinge moment at those speeds is under 1 N m against an 8,000 N m/rad servo).

## Decisions this leaves open (not taken)

1. **Pod retention on the road.** A mechanical down-lock in the model (engaged when the pod is within a degree of 0 and
   the wheels are loaded), or the ECU preload that the 12 November session wrote into `plant.py` on the local machine
   (`POD_DOWN_PRELOAD_FRACTION = 0.8`, uncommitted, not on any branch on GitHub), or a stiffer tilt servo parameter.
   These are different claims about the real aircraft.
2. **Tyre model.** A slip-angle law (cornering stiffness proportional to load, saturating at the friction limit) would
   make every ground result, A10-B included, more faithful and would remove the divergence on its own. It changes the
   pinned A10-B configuration hash, so it would have to go in as an overlay or a new revision.
3. **Ground directional control in the ECU.** Today the wheels receive no feedback in any mode. A yaw-rate or heading
   loop to the nosewheels whenever the wheels are loaded, and the automatic per-phase mode selection asked for on
   13 November (no pilot-selected default), are design changes to the flight computer, not the airframe.
4. **The canards.** They already do in the model what the pilot reports: deployed, the take-off tracks straight and
   lifts off 440 m earlier than folded. Whether the take-off procedure should state canards out and nose-up as the
   directional-control step, and whether the slow-roll case (wings out below rotation speed for longer than a
   full-thrust take-off needs) is one the aircraft must survive, are operational calls.
