# Flight-test objectives and waypoint evaluation contract

## Authority and scope
This policy governs flight-test planning, pilot assessment, automated outcome labels, and reporting for all VTX simulator vehicles, including R6 and Phantom A10. The proprietor's stated objective takes precedence over inferred precision targets. A waypoint is a navigational reference, **not** a required exact touchdown coordinate.

## Mandatory rules
1. Record the actual test objective before a sortie (e.g. first horizontal translation, A-to-B navigation, hover, attitude control, controlled landing). Do not invent additional acceptance criteria.
2. Treat waypoint coordinates as guidance for navigation unless the proprietor explicitly defines a landing zone or numerical precision tolerance. Record final distance from each waypoint as a measurement, never an implicit failure.
3. Evaluate physical outcomes separately: takeoff, controlled translation, navigation, recovery from overshoot, descent, gear-supported settling, collisions, attitude, impact loads, and remaining control authority. Never let a positional tolerance override the physical landing assessment.
4. Distinguish **flight objective demonstrated**, **controlled landing observed**, **precision target met/not met (only if specified)**, and **incomplete/unknown**. An unsafe or uncontrolled landing must not be called safe merely because it is near a waypoint.
5. Do not call a sortie failed solely for missing an arbitrary waypoint radius. If an existing software condition prevents a `landed` label, report that as a *software classification mismatch* and retain the observed physical outcome.
6. Preserve raw telemetry, original automated labels, model revision, and pilot narrative. Corrections are additive annotations, never silent rewrites of historical evidence.
7. For early development flights, prioritise demonstrated controllability, translation, navigation, overshoot correction, and controlled landing. Track accuracy as a metric to improve, not a gate, unless explicitly requested.
8. No automatic certification or real-world airworthiness claims follow from simulator outcomes.

## Required reporting
Each sortie report must state: **user-specified objective**; **observed capabilities**; **physical landing outcome** (including evidence and uncertainty); **distance to waypoint** (if applicable); **explicit precision requirement** (or `none specified`); **automated classification**; and **engineering assessment**. Keep these fields separate.

## Regression example: R6 Argon A-to-B, 20261103T125202-92636c
The recorded flight traversed from A toward B, overshot, corrected, descended, and eventually settled with six-gear support, approximately 2.58 m from waypoint B. The software's 2.00 m radius produced `airborne attempt ended`. No proprietor-authorised 2 m landing requirement is established in the flight record. Retain the original label as historical data, annotate **controlled A-to-B navigation and supported landing observed; waypoint offset 2.58 m; precision criterion not specified**, and flag the automatic label as a classification mismatch. Also preserve the recorded initial near-hover thrust and ground-level drift before final settling.

## Implementation acceptance tests
- Safe, supported landing 2.58 m from an A-to-B waypoint with no specified radius: navigation/landing observations retained; no precision-based failure.
- Same landing with an explicitly requested 2.00 m tolerance: physical landing remains recorded; precision objective marked not met.
- Landing directly on the waypoint with unsafe impact or overturned aircraft: precision alone cannot establish a successful landing.
- Uncertain ground contact or incomplete telemetry: label physical landing as unverified, not automatically successful.
- Historical R6 source summary and event evidence remain unchanged.

Update the outcome evaluator and its tests to enforce this policy; a documentation change alone does not alter runtime behaviour.
