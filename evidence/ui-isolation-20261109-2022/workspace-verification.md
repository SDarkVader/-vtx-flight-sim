# Isolated workspace verification — 2026-11-09

The test server ran on 127.0.0.1:18910 with a new temporary VTX_DATA_ROOT, separate from the existing simulator and its records.

- A new workspace selected Phantom A10-B with configuration SHA-256 `3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01`. Workspaces containing prior pilot memory, a checkpoint, flight evidence or experiments are not automatically switched; release-enforced R6 remains protected.
- An isolated A10-B sortie `20261109T204029-2aa1fc` ran for 13 simulated seconds; cockpit sensor readings updated, and its outcome was recorded as no takeoff. This is not evidence of a successful flight.
- A separate A10-B scheduled road experiment `ea86531f5bb04a92bd2ccf48d97ccdfe` completed 3 seconds and recorded no takeoff. Its request, parameters, mass properties and events are retained in `a10b-experiment-ea86531f.zip`.
- Cockpit, Flight test dashboard and Physics experiments were checked in all eight visibility combinations at desktop and 390x844 mobile sizes. The Mission, Controls and Airport views drawers were also opened together.
- Python: 21 checkpoint, release, dashboard and experiment-isolation tests passed. JavaScript: 9 telemetry, operator, airport and visual test cases passed.

Screenshots show the cockpit drawers and all three pages side by side. These checks do not demonstrate wingborne flight, complete R6 flight acceptance, or production deployment.
