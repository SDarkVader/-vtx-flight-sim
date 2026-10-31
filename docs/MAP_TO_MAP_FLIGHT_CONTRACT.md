# Map-selected ground-to-ground missions

The proprietor chooses any valid departure position and any valid destination on the current map. No fixed pads or scripted routes.

A validity check must consider terrain support and slope, complete aircraft/rotor footprint, surface obstruction, rotor clearance, no-go volumes and configured synthetic safety thresholds. Show rejection reasons. On mission start, the aircraft begins physically supported by landing contacts at the chosen origin; there is no teleportation during flight.

Execute the actual physics-driven phases: stationary preflight, rotor spool/liftoff, hover, navigation, turn and obstacle handling, approach, controlled descent, touchdown and stationary settling. Resolve all ground reactions, collisions, rotor saturation and physical limits through a single authoritative 6-DOF state. Only classify LANDED if supported and stationary under measured criteria; otherwise report ABORTED, BLOCKED, COLLIDED, CRASHED, UNSTABLE or INFEASIBLE with evidence.

UI: pan/zoom map; clickable departure and destination markers; validation feedback; Fly, Abort, Pause and Replay; live pose, velocity, route, telemetry and independent per-rotor controls.

Save map and environment version, A/B coordinates, weather, random seeds, solver configuration, physical parameter fixture, commands, sensor observations, contacts and results to replay exactly. Test at least five seeded valid A/B pairs, including turns; reject invalid terrain/clearance; reproduce success and genuine failure.

Stage 2 must accept the proprietor's previously unseen map with the same mission interface, while the controller retains Stage 1 learned state and is limited to specified observations. It must not read the underlying simulator's omniscient world state.

This is a **required future implementation**, not a claim that the map simulator exists.
