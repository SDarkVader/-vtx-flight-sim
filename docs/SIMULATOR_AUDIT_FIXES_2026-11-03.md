# Simulator audit fixes — 2026-11-03

Physics revision: `audit-fixes-20261103-r1`. This branch is based on the A9
research branch; it does not replace the prior branch, CAD file or Blendstra
preview. Its evidence is simulator regression testing, not real flight data.

## Implemented

- Compute assist rates in body axes rather than the principal-inertia frame.
- Conserve fuel draw across non-empty tanks. When a timestep requests more fuel
  than remains, scale the powered torques and energy to the available fuel;
  report exhaustion and remove drive on subsequent steps.
- Retain world-frame observation fields and add body-frame angular rate and
  velocity, derived from the same noisy samples.
- Estimate ground clearance with downward rays from gear foot locations and
  the airframe centre, restricted to world geometry. A no-hit result is null
  and raises `CLEARANCE_UNAVAILABLE`; the UI displays an unavailable value.
  These rays do not cover the full footprint or guarantee obstacle clearance.
- Use MuJoCo's implicit integrator and preserve the governor integrator during
  a temporary overspeed fuel cut.
- Initialize the live laboratory at application startup rather than import, so
  an import alone cannot restore checkpoints or write flight evidence.
- Record requested commands and slew-limited targets in physics snapshots, and
  record gear and non-gear contact loads separately. The old maximum contact
  field remains available for compatibility.

These changes affect the model and invalidate comparisons that assume the old
physics or clearance semantics. Existing historical logs are not rewritten.

## Outstanding

The audit also identifies cockpit keyboard and horizon axes, legacy retry
defaults, actuator saturation telemetry, atmosphere and wind, and the
ducted-fan, sideflow and descent models. Those are not corrected by this revision.
In particular, the existing open-rotor model is not a validated Phantom ducted
fan; do not use this revision as evidence of real-aircraft performance.

The untracked Phantom implementation and parameter files in the research
worktree were not copied into this isolated branch. These changes therefore
apply to the tracked R6/shared simulator code and have not been verified on a
running Phantom variant. The A10-named Blender file examined separately contains
an A9-labelled scene; no new A10 geometry is claimed by this revision.
