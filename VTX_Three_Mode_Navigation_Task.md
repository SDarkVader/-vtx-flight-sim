# VTX Live Flight â€” Shared Cockpit, Selectable World
Date: 2026-11-10
Agent: Antigravity Main Agent, Gemini 4 Argon Medium
This task supersedes earlier descriptions of three separate interactive interfaces, an Airport On/Off toggle, or an independent sandbox simulator.

## Working location and safety
Use ONLY C:\Users\steve\Documents\Github\vtx-three-panel-20261110, branch work/three-panel-ui-20261110, based on merged commit ed6da13f2bc087b5cc3252c467002c0dd89b61ab.
The original checkout C:\Users\steve\Documents\Github\-vtx-flight-sim has hundreds of local changes and unresolved conflicts: DO NOT modify/reset/clean/merge it. Leave ports 8765 and 8766 and all historical flight data alone. The isolated development launcher is RUN_THREE_PANEL_DEV.ps1 (port 18911). Do not push, merge or deploy.

## Exact UI behavior
ONE shared live flight cockpit/screen. Keep the existing surrounding screen, panels, buttons, AI pilot controls, manual controls, aircraft/model selector, actuators, physics settings, telemetry, experiments, cameras, and records unchanged and functional.
Provide environment selection: MAIN AIRPORT or TEST SANDBOX.
- Airport selection: central live 3D view displays the main airport, with aircraft placed at its appropriate start position.
- Test Sandbox selection: the SAME central live 3D view displays the user's own sandbox environment, with aircraft placed at its appropriate start position.
- Only the central live world/scene and the aircraft's environment-specific starting placement change. The surrounding UI does not change or get duplicated. Both selections are LIVE flight, with the same AI pilot, manual controls, physics engine, models, experiments and telemetry.
- Both environments support live experimentation and AI control. Never turn sandbox into a passive preview, dashboard, headless runner, or separate flight application.
- Change actual world geometry/collisions as well as rendering; do not merely hide airport graphics while airport physics remains.
- Handle environment switching safely: do not silently reset an active sortie or corrupt telemetry; if a reset/reposition is needed, expose that clearly and require deliberate action. Preserve flight records and tag runs with environment identity.

## Physics experiments
Keep existing scheduled/headless MuJoCo experiment runner at /experiments/ available as a tool/workflow, but it is NOT a replacement for live experiments in either world. Do not create a second cockpit or a separate main navigation system solely for the sandbox.

## Implementation and verification
Inspect public/workspace-panels.js, public/workspace-theme.css, public/index.html, public/app.js, src/vtx/live_server.py, src/vtx/world.py, src/vtx/dashboard_site.py, src/vtx/experiments.py and relevant tests.
Make the smallest coherent change for selectable live environments in the existing cockpit. Reuse scene/world loading and flight controls. No physics retuning, aircraft model changes, fabricated telemetry, duplicated event handlers, or new physics engine.
Verify the same cockpit/panels and AI/manual controls are present in both selections; actual scene and collision identity changes; aircraft placement correct; live telemetry works in both; no unintended loss of sorties, session data or authority. Run focused tests and git diff --check, report results and any precise blocker, then STOP. No push/merge/deploy.

