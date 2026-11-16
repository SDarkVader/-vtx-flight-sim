# Persistent VTX pilot station (experimental)

## Scope and current cockpit boundary

This page describes the older experimental Colin supervisor. It is **not the
launcher for the current single cockpit** and must not be started alongside
it: the supervisor can create a server on port 8765 with another data root.
Use the [README's current local launch procedure](../README.md) and the
runtime/data locations in the authoritative record named by `AGENTS.md`.
The current Phantom candidates await owner flight tests and promotion.

The station maintains a connection to the simulator and records instrument readings and
commands. Each control decision supplies individual actuator setpoints in `tools/pilot_controls.json`.

## Start / stop

From the simulator repository on the authorized Windows PC:

```powershell
.\.venv\Scripts\python.exe -u scripts\pilot_station.py
```

The station adopts an existing server at `192.168.55.121:8765`, or starts
`vtx.live_server:app` when it cannot reach one. It launches and supervises
`tools/persistent_pilot.py`. Keep the station terminal open; Ctrl+C stops
processes it owns (not a server it merely adopted). It is **not** a Windows
startup service.

To **hold**, set `enabled: false`, `armed: false` in
`tools/pilot_controls.json`; then set `paused: true` via `/api/operator`.
The committed control file starts disarmed.

## Run-bound commands

To enable commands, set `enabled: true` and `armed: true`.
Read `/api/observe` and use that sample to choose the settings. Put its `run_id` in
`arm_run_id` and its `observation_id` in the control file. Increase `serial` and supply
the reason, engine, collective and nacelle targets. Write the complete JSON atomically.
The server records the cited instrument sample with the command. The station keeps
monitoring while a run or observation is missing.

The `cabin_level` setting defaults to on. To take over from Colin, use the cockpit’s
**Take manual authority** button.

The temporary experimental assist wire is opt-in per flight and is applied to
actual collective targets only when enabled. It is not certified or established
as beneficial, and does not control yaw. Its application is reported by
`observation.assistance_applied`.

## Recovery boundaries

- A recorded crash stops pilot commands. The operator can start a new attempt from the cockpit.
  Current cockpit checkpoint recovery is separate: supported R6 state and
  Phantom inner format 3 retain the integration, controller/actuator,
  fuel/energy, environment, identity and sensor calibration required by the
  implementation. Compatible interrupted flights restore paused and require
  explicit takeover/resume. Legacy or incompatible checkpoints remain retained
  for inspection; a reset must never be called a resume.
- Server and pilot processes reconnect independently. Pauses and manual control
  are respected, and a safety guard latches until the control serial changes.
- All simulator evidence stays under `evidence/flights/<run-id>/`.
  Pilot events: `pilot/pilot_events.jsonl`; latest state:
  `pilot/pilot_status.json`; station logs: `pilot/station-*.log`.
  These local data files are not committed to the repository.

## Current explicit save and switch

In the current cockpit, use **Save flight & switch** to park an unfinished
flight. It writes `pilot/saved-flights/<run_id>.json` under the configured data
root without inventing an end summary. In **Flight records**, choose
**Restore paused flight**, confirm the run/variant/environment/time, then take
control and use **Resume existing mission**. **New mission** and **Retry**
create new run identities; they do not continue the saved sortie.

Source, registry, environment, asset and frontend mismatches block exact
recovery while retaining the checkpoint. Older Phantom inner format 2 omits
radar ground calibration and is not accepted as an exact calibrated restore
by format 3. Do not edit a checkpoint's hashes to make it load. Camera settings
are stored separately in the browser profile/origin, not in solver state.

The 15 November cockpit check saved a calibrated runway state, switched to the
distinct VTOL candidate and restored the same runway run paused at 55.0175 s.
Its checkpoint bytes and physical/held state matched exactly, including the
0.11 m radar reference. That is a continuity check on the ground, not owner
flight acceptance or proof of the legacy supervisor's behavior.

## Verification

```powershell
$env:PYTHONPATH='src;.'
.\.venv\Scripts\python.exe -m pytest -q tests
node --check public\app.js
```

These checks test API boundaries, physical mechanics and pilot recovery logic,
not actual stable hover. Flightworthiness claims require separate evidence.
