# Control input timing — live experiment

The 2026-10-31 retry `20261031T151225-52aea6` exposed overlapping pilot commands: collective split and fan direction were changed again while previous targets were still moving. Consequently the measured response cannot be assigned to any single command. The aircraft is paused at simulation time 27.343 s, at 6.491 m clearance, descending at 0.82 m/s, with horizontal velocity approximately [-1.594, 8.893] m/s and roll -15.629 degrees. This is not a stabilized hover.

The physical model limits collective motion to 4 degrees per second and fan target motion to 5 degrees per second per coordinate. These are **target slew rates**, not measured aircraft response times; physical gimbal tracking and attitude response can lag and overshoot. For example a 6-degree change in a collective target takes at least 1.5 simulated seconds to traverse, and a 10-degree fan target step takes at least 2 simulated seconds. One second of simulated time at 0.02x takes about 50 seconds of wall time.

## Operating method

* Use the current observed state and actuator feedback, and check who has authority before every command.
* For a controlled identification step, change one input group at a time: common collective, differential collective, or a fan-vector direction. Record all commanded values, the actual feedback, attitude and angular rate, vertical and horizontal velocity, clearance, fuel, and simulation time.
* Keep an unchanged command alive if needed for the five-simulated-second lease; a heartbeat must not change a target. Wait for feedback to approach the target and then observe its effect for a measured interval before the next identification step. Do not infer settling merely from the nominal slew time.
* Emergency corrections and user takeover override the identification sequence. A rigid wait while attitude, altitude, or position deteriorates would be unsafe and would make the experiment less useful.
* In a coupled airborne recovery, vertical lift and attitude may both require correction. Label concurrent changes explicitly and do not use that interval to claim isolated gains.
* Derive gain estimates only from comparable conditions and sufficiently isolated input/response intervals; identify delay and uncertainty and retain failed observations.

## Measurements from this run

At t=15.070 s, roll rate was -0.866 degrees/s; a commanded increase in differential collective produced 2.576 degrees of actual side-to-side difference at t=15.437, when roll rate was +0.058 degrees/s. Gear contact was also changing, so this is not an isolated gain. At t=16.915–17.265 s, roll rate changed from -15.116 to -2.127 degrees/s, an average +37.1 degrees/s², while actuator feedback and other forces were changing. At t=18.615–20.085 s, +Y speed increased from 2.206 to 4.381 m/s, averaging +1.48 m/s². Subsequent changes in bank and tilt coincided with +Y speed reducing from 6.024 m/s at t=21.100 to 1.452 m/s at t=22.150. None of these aggregate observations by itself establishes a controller gain.

The live session contains the complete audit and pilot decisions up to the pause; it is temporary. Archive the full log and pilot notes before its expiry and push them to GitHub, as requested by the user.
