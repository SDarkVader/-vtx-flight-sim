# Arbitrary-location map missions

The proprietor chooses any **valid** departure position and destination from the current test map, rather than preselected pads or scripted routes. Validate terrain support, stability and footprint, rotor/obstacle clearance and physically permissible landing area, with clear reasons for refusal.

The aircraft begins at rest on its gear at the selected departure. **Colin must actively fly** through the real-time fly-by-wire control interface, receiving only permitted pilot observations and choosing control inputs repeatedly based on what happens. A and B describe only the desired ground start and destination; neither point authorizes an autopilot to compute and execute a predetermined path. Colin attempts takeoff, navigation and landing using the modelled actuators and forces. Follow [the live piloting contract](LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md). It may fail at any phase. No teleportation, trajectory override, hidden lift, forced stabilisation, environment peeking or scripted successful touchdown.

Real ground reaction, impacts, loss of control, energy limits and rotor constraints determine what happens. Touchdown is not success unless supported and settled. Record actual flown routes, successive live observations, Colin's individual fly-by-wire commands, learning updates, flight/impact telemetry and physical outcomes. Replay only for later inspection.

The exact same mission interface must work when the proprietor later supplies the unseen Stage 2 environment; do not grant advance knowledge of that world.
