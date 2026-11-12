# Flight-test assessment authority and waypoint policy

Status: proposed policy for review. Applies to VTX simulated flight-test reporting and future evaluation logic once implemented.

## Governing principle

A waypoint is a navigational reference. It is **not** a mandatory touchdown coordinate, and proximity to a waypoint alone must not determine whether a flight or landing succeeded.

Only the proprietor's explicitly stated test objectives and acceptance criteria govern mission success. A software default, pilot script, UI marker, or report template must not silently add a stricter requirement.

## Assessment rules

1. Record separately: (a) demonstrated flight capabilities and objective completion, (b) physical touchdown and settling evidence, (c) navigation error or distance from target, and (d) any explicitly authorised precision objective.
2. Assess a controlled landing using recorded contact/support, attitude, velocities, impact/collision conditions, and stable settling. A momentary ground touch or near-zero radar clearance alone does not establish a completed landing.
3. Report waypoint distance as a measurement. Do not turn it into a failure threshold without a preflight requirement specifying the tolerance, reference point, and scope.
4. When no positional tolerance was authorised, label positional precision **not specified**, not failed. A safe landing near the intended destination may satisfy a general A-to-B navigation demonstration.
5. Distinguish observed pilot corrections, overshoot, drift, control limitations, and faults from the overall test outcome. Preserve these as engineering findings even when the primary objective succeeds.
6. Do not invent requirements retrospectively, silently reclassify historical telemetry, or treat an automated evaluator's outcome as the proprietor's assessment.
7. Preserve original run IDs, raw telemetry, simulator-generated outcomes, and original reports. Corrections or reinterpretations must be separately dated and attributed, with the original retained.
8. When an existing automated rule conflicts with this policy, flag the mismatch explicitly until code and tests are updated. Documentation alone does not change runtime behaviour.

## Regression case: R6 A-to-B navigation demonstration

Run `20261103T125202-92636c`: the recorded flight reached B's vicinity, overshot and corrected, descended, and eventually settled on six gear legs. Final recorded distance to B was 2.58 m, versus the simulator's 2.00 m automatic landing radius. The simulator outcome was `airborne attempt ended`.

Required interpretation: **controlled A-to-B navigation and supported landing demonstrated; final waypoint error 2.58 m; positional tolerance not specified by the proprietor**. Retain the simulator's original classification as a historical software output, not as proof that the landing was physically unsuccessful.

## Implementation acceptance tests

- A stable, supported landing 2.58 m from B with no specified positional tolerance must not fail solely because of distance.
- The same landing with an explicitly configured preflight 2.00 m precision requirement must report the precision objective as missed, without automatically erasing the supported landing.
- An upside-down, high-impact, unstable, or unsupported touchdown must not be marked safe merely because it occurs exactly on the waypoint.
- A waypoint flyover or hover without touchdown must not be reported as a landing.
- Existing telemetry and original reports must remain byte-for-byte unchanged by evaluation-policy updates.

Implement and test changes to runtime scoring separately before claiming the simulator enforces this policy.
