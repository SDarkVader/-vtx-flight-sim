# Phantom A10-C: take-off and flight without the lift fans (11 November 2026)

This is a preserved **11 November study**. Its schedules and figures describe
that study and must not be substituted for the later recorded pilot flights.
Current defaults and promotion decisions are described in the
[README](../../README.md); A10-B is a pinned reference, not a promoted Main
Aircraft default in the continuity integration.

`phantom-a10c` is a **development** variant: A10-B plus two changes. A10-B (`phantom-a10b`, config `3ecae1a9`) is unchanged
and was the pinned default for this study. Every figure in the original study below is from the MuJoCo plant with scripted test inputs, not a piloted
flight or a measurement.

## What stopped A10-B

| Finding | Evidence |
|---|---|
| **Thrust, not stability, ended fans-off flight.** At its best lift-to-drag ratio (about 4.4 at 6 deg) level flight needs about 4.3 kN. The two EDF boosters give 3.1 to 3.4 kN, so the aircraft slows, the angle of attack rises and it departs. | Cruise run, EDF boosters, started in trim at 80 m/s: slows 79 to 70 m/s in 13 s, then pitches up past 45 deg. |
| **It flies in trim.** With enough thrust the existing wing-borne law holds it, with the existing 0.219 m2 stabilator. The earlier fans-off departure started out of trim (90 m/s, 4 deg: 2.4 kN m nose-down). | Cruise run, turbojets: 40 s, pitch 3.0 to 6.2 deg, pitch demand at most 0.25 of full. |
| **It is statically unstable but trims near 6 to 7 deg.** Free pitching moment at 95 m/s: 7.2 kN m nose-down at 0 deg, zero near 6.8 deg, nose-up above. | Static sweep of the surface model about the CG. |
| **It cannot rotate on the ground.** Level, the wing and hull make too little lift below about 100 m/s, and the stabilator cannot lift the nose about the rear tyres. | Take-off roll, turbojets, level stance: wheels leave at 101 m/s after 3.8 km. |

## The two changes

1. **Turbojet boosters** (proposal P7, already in the parameter file): four PBS TJ150, 1,500 N each. The manufacturer's
   page gives 1,500 N and 18.1 kg; the parameter file carries 18.9 kg from an earlier revision of that page.
2. **Take-off stance nose strut** (`inputs/phantom_overlays/takeoff_stance_v1.json`): each front wheel's spring seat moves
   down 0.20 m on a rate-limited actuator while the wings are out in road stance, and retracts otherwise. That is
   3.7 deg nose-up over the 3.13 m wheelbase. The load path stays spring, damper and tyre. Sized on the Thomson
   Electrak HD: 10 kN dynamic, 58 mm/s at full load; the static corner load is about 4.3 kN. The 9 kg actuator mass is
   an estimate.

## Results

| Run | Lift-off | Ground roll | After lift-off |
|---|---|---|---|
| A10-B + turbojets, level stance | 101 m/s | 3.8 km | climbs |
| + nose lift 0.20 m | 78 m/s | 1.0 km | climbs about 2.3 m/s at 83 m/s |
| + nose lift 0.20 m + 1.0 m2 stabilator | 74 m/s | 0.87 km | climbs about 2.3 m/s |
| + nose lift 0.30 m + 1.0 m2 stabilator | 68 m/s | 0.64 km | pitch peaks 13.2 deg (tail-strike angle 11.9 deg) |
| **`phantom-a10c`** (turbojets, 0.20 m, actuated strut) | 79 m/s, 23.7 s | 1.1 km | climbs to 55 m in 25 s, pitch at most 8.5 deg |
| `phantom-a10c` through the live simulator, airport runway 08/26 | wheels off at 79 m/s, 22.8 s | about 1.0 km of the 1.43 km runway | 41 m radar height at 42 s, lift fans at 0 rpm |

Schedule used: brakes off, full wheel drive and boosters, wings and canards out, flaps 30, attitude hold; pitch target
7 deg from 55 m/s; wheel drive off once airborne.

## Checks asked for

* **Centre of gravity.** Compiled model and ledger agree: 1,933.1 kg, CG x -0.174 m, lateral offset 0.04 mm (A10-B).
  A10-C is 1,969 kg with CG x -0.176 m.
* **Pinned axes.** None. The airframe has one free joint with six unconstrained degrees of freedom, no damping,
  armature or friction on it. The model's only two equality constraints are the wing locks, inactive until the wings lock.
* **Visual model.** `phantom-a10b-visual.glb` has 28 joints, no cameras and no instruction nodes; it has no nose strut,
  turbojet or larger stabilator geometry. A10-C reuses that mesh until those parts are modelled.

## Not done

* A larger all-moving stabilator (about 1.0 m2, body width) shortens the roll and adds control margin. It is a geometry
  change, so it is left as an option.
* Landing with the fans off, cruise endurance on turbojet fuel burn, crosswind and engine-out cases are untested.
* Flaps still retract automatically above 75 m/s; ducted-fan crossflow and ground effect on the hull are not modelled.
* A bug found on the way: `/api/view` failed with turbojet boosters selected (the engine name could not be converted
  to a number). Fixed in `plant.py`.

## Recovered recorded flights and current integration (15 November 2026)

The owner has numerous successful takeoffs. The recorded 12 November flights
are independent evidence of that behavior; a later outcome does not erase an
earlier demonstrated takeoff. The integrated revisions remain separate and
unpromoted while the owner tests both.

| Integrated candidate | Recorded parent runtime | Original evidence and environment |
| --- | --- | --- |
| `phantom-a10c-runway-20261112` | `26ec2aa2…`, commit `b38d5f1b…` | Runway takeoffs `20261112T132734-215fcf` (airport) and `20261112T135625-df0959` (sandbox) |
| `phantom-a10c-vtol-20261112` | `3b30e763…`, commit `eb855817…` | Vertical takeoffs and sustained flight `20261112T204732-17cc37` and `20261112T211016-e9d0ab` (airport) |

Exact parent/configuration/asset hashes and original run associations are in
[the registry](../../inputs/flight_revisions.json). Original flight folders are
retained in the local data archive; the repository does not duplicate those
large logs. Read the project's continuity record before selecting a live
runtime or data directory.

The recorded runway flight established the 0.20 m spring-seat setting before
acceleration: full extension by 5.67 s, drive/booster command at 12.255 s, and
the final continuous no-wheel-support interval near 35.02 s at about 78.9 m/s.
It climbed before its later collision. These timings differ from the original
study schedule above. The flap command remained held while the airspeed
interlock retracted the actual flaps near 75 m/s; that did not prevent the
recorded takeoff. Do not attribute the later collision to a tail strike or one
control mechanism without contact evidence.

The current integrated Python tree is pinned by the registry to
`94e13085e9d7b6d5c1c4e87547d621fbd3655f0fd2764f862b8e37bbddc70cc0`.
Offline recorded-control reproductions used the original manual patch semantics,
recorded issue times, 20 ms transport, 400 Hz integration, airport model and
129 kg initial fuel. The first 42 s / 4,200 samples of the runway run and
45 s / 4,500 samples of the VTOL run match all 16 compared channels at stored
CSV precision. The reproducible harness is
[`tools/reproduce_recorded_phantom.py`](../../tools/reproduce_recorded_phantom.py).
The local `final14` comparison/evidence paths are recorded in the continuity
record. These results establish the requested takeoff reproductions, not a
complete flight envelope or owner acceptance.

The newer dashboard/instruments/controls are retained. The cockpit now uses
the original authored B wheel sizes/mounts, measured articulation, and an
[optional measured-suspension schematic](A10C_SUSPENSION_SCHEMATIC.md).
Ground cockpit checks verified deployed wings/canards and nose-up attitude.
Format-3 calibrated save → inspect VTOL → restore-paused returned identical
checkpoint bytes/state and retained the 0.11 m radar reference. Owner flight
tests and Main Aircraft promotion remain outstanding.
