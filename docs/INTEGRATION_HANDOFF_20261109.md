# VTX integration handoff — 9 November 2026

This branch is a draft integration candidate. It combines the A10-B model, the dashboard/cockpit candidate, the A10-B reference evidence and a separate scheduled experiment runner. It is not approved for production promotion. The source checkout and other worktrees retain their own changes and evidence.

## Local launch

Use a **new, dedicated** data directory and an unused port. From this integration worktree in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
$env:VTX_DATA_ROOT = 'C:\Users\steve\Documents\VTX-integration-data'
& 'C:\Users\steve\Documents\GitHub\-vtx-flight-sim\.venv\Scripts\python.exe' -m uvicorn vtx.dashboard_site:app --host 127.0.0.1 --port 18909
```

Open `http://127.0.0.1:18909/` for the live cockpit and `http://127.0.0.1:18909/experiments/` for isolated tests. Check the chosen data directory and port before launch; do not point the test instance at an existing live-flight data directory. The dashboard is at `/dashboard/` and its legacy assessment store still depends on a separate Site. For remote/mobile access, use a stateful Python service with persistent storage and authenticated HTTPS; no Vercel production target has been verified for this branch.

## Identity and retained evidence

- A10-B: `3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01`.
- A10-A, P6 enabled: `70089ccace22e4ce1cfd28104654257fe4d03771c4f6b1faa3c89fce253247dd`.
- A10-A, P6 disabled: `b835295b7b806fcb785f01a8776b6715d73790f48ac5134cb8d594e6d389ebde`.
- R6: `P0-V4A-assembly-r6`, `audit-fixes-20261103-r3`, `/assets/airframe-r6.glb`.

The 72-row A10-A register and later B evidence are in `reference/phantom_a10b_20261109/`; the supplied trial merge notes are in `trial_a10b_20261109/`. The recorded fan-assisted turn rerun is in `evidence/integration-turn-20261109/`. An isolated R6 hover run is in `evidence/integration-r6-hover-20261109/`; its notes state that its recorded parent commit did not include all then-uncommitted source changes. The isolated HTTP and pilot-handover checks are in `evidence/integration-http-20261109/`.

Parameter hashes alone do not identify the controller or world. New runs also record a runtime source fingerprint and world version. A new checkpoint with a different runtime fingerprint or Phantom configuration is blocked rather than silently resumed; old checkpoints without a source fingerprint show an unverified-source notice.

## Verification and remaining work

- The A10-B fan-assisted decelerating turn was rerun on the MuJoCo plant and completed 90 degrees. This is not a demonstration of conventional runway rotation or fans-off sustained flight.
- The R6 isolated hover check reached 1.523 m sensor-reported radar clearance. It is not a navigation or landing acceptance test; the historical heading-dependent coupling still requires work.
- Local HTTP checks exercised A10-B manual and AI-pilot action routing, stale-epoch rejection, model-switch rejection during flight, a concurrent isolated A10-A P6-off experiment and evidence ZIP export. The experiment run did not change the active A10-B sortie.
- The JavaScript tests passed 24 cases. A full Python run is in progress at handoff; verify its final result and CI on the pushed commit. Earlier focused physics, checkpoint, preview concurrency and experiment-isolation tests passed.
- The experiment page supports timed commands, separate run history, manual and measured-attitude abort, comparison, selected Phantom parameter overrides and evidence export. It is not yet a complete interface for every geometry, inertia, aerodynamic or actuator parameter. Its bounded overrides are labelled synthetic and generate a new configuration fingerprint.
- Browser automation was disabled in the current Work settings, so PC/mobile visual and accessibility acceptance remains outstanding. The local HTTP tests do not substitute for those checks.
- An actual external AI provider, conversation persistence across a real disconnect, hosted persistent service and production Vercel project have not been validated. The AI-pilot check used a synthetic test pilot and did not call an external model.
- Review the still-dirty worktrees and the preliminary branch/PR register in `docs/INTEGRATION_RESOLUTION_20261109.md` and `docs/LOCAL_WORKTREE_AUDIT_20261109.md`. Do not close PRs with unique work. Production deployment, destructive cleanup and branch deletion require the owner's explicit approval.
