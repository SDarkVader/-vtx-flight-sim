# Persistent VTX pilot station (experimental)

The station maintains a connection to the real MuJoCo simulator, preserves
instrument/action evidence, and retries an **actually crashed** Colin sortie.
It does not fabricate a flight, navigate a route, or replay successful inputs.
All actuator setpoints are explicitly supplied in `tools/pilot_controls.json`.

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
An operator hold always takes precedence over retries. The version committed
to Git is disabled and disarmed. Re-enable only when explicitly instructed.

## Run-bound commands

When ready to permit commands, set `enabled: true`, `armed: true`,
`arm_run_id` to the exact current `/api/view.run_id`, increase integer
`serial`, and supply the reason, engine, collective and nacelle targets.
Write the complete JSON atomically. No run ID match means neutral idle command
instead of flight; the same command is **never** re-armed on a retry. The pilot
fetches a fresh `/api/observe` for each action.

Cabin levelling is forced off. Selecting that UI control while Colin is
piloting will not seize manual authority. To take over, use the explicit
**Take manual authority** button.

The temporary experimental assist wire is opt-in per flight and is applied to
actual collective targets only when enabled. It is not certified or established
as beneficial, and does not control yaw. Its application is reported by
`observation.assistance_applied`.

## Recovery boundaries

- A recorded crash permits up to five automatic restarts by default, with
  a cooldown. Each retries the retained mission at departure in neutral idle.
- A server restart cannot resume mid-air physics. If a previous sortie has
  metadata but no summary, it is recorded as **interrupted**. A Colin-owned
  interrupted attempt may be retried from departure; a manual-owned one may not.
- Server and pilot processes reconnect independently. Pauses and manual control
  are respected, and a safety guard latches until the control serial changes.
- All simulator evidence stays under `evidence/flights/<run-id>/`.
  Pilot events: `pilot/pilot_events.jsonl`; latest state:
  `pilot/pilot_status.json`; station logs: `pilot/station-*.log`.
  These local data files are not committed to the repository.

## Verification

```powershell
$env:PYTHONPATH='src;.'
.\.venv\Scripts\python.exe -m pytest -q tests
node --check public\app.js
```

These checks test API boundaries, physical mechanics and pilot recovery logic,
not actual stable hover. Flightworthiness claims require separate evidence.
