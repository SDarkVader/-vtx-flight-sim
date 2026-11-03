# Simulator audit follow-up — 3 November 2026

This isolated branch extends `22023f8`; the original worktree and model files are retained. The preview uses the R6 experimental simulator, not a verified Phantom A10 aircraft. Its geometry, dynamics, controller and operating limits are conditional and cannot demonstrate real-world airworthiness.

## Changes

- Cabin gimbal joints include passive damping and the powered level controller uses measured cabin world angular rates projected into cabin axes. Torque, power and travel limits remain in force; level mode is the default and can be disabled. The gains are provisional. Isolated disturbance tests are not flight validation.
- Cockpit camera controls and horizon follow the cabin orientation. Legacy panels are hidden in both views; nearby seat and harness surfaces are suppressed inside the cockpit. A small cabin-mounted 3D panel displays actual simulator sensor values, with inactive, paused and stale indications. Decorative seat yokes that projected into the seats are removed from this rendered version; physical controls and source model files remain unchanged.
- Steady wind and an opt-in standard-atmosphere density model affect the existing rotor and body force calculations. The default constant density preserves prior cases. This is not a weather or turbulence model.
- A standalone hover-only ducted-fan screening calculation distinguishes an open-rotor equivalent from an ideal duct bound. It is not an integrated Phantom simulation or validated forward-flight or descent model. Vortex ring state and duct aerodynamics require further modeling and evidence.
- Actuator limit and cabin status telemetry support inspection. The modified MuJoCo model has a different model hash; existing checkpoints must not be resumed as if they came from the new model. Preserve prior evidence separately.

Reference context: [NASA standard atmosphere](https://ntrs.nasa.gov/api/citations/20120003268/downloads/20120003268.pdf), [NASA rotor vortex-ring-state study](https://rotorcraft.arc.nasa.gov/Publications/files/77-2021-0193_Veismann.pdf), and [NASA stabilized-gimbal work](https://ntrs.nasa.gov/api/citations/20230005922/downloads/20230005922.pdf).

The actual A10 handover geometry has not been verified. The R6 flight test is not a test of a Phantom A10 configuration.
