# Live interface and keyboard controls

## Current local cockpit

The continuity integration uses **http://127.0.0.1:8770/** and one authoritative
server. Follow the [README launch instructions](../README.md) and read the
single live project record named by `AGENTS.md` before changing its source,
data directory or selected aircraft. Do not launch a second cockpit to inspect
another candidate. Main Aircraft promotion is pending; explicitly select a
named test candidate in Experiments, or intentionally restore its own saved
flight.

**Save flight & switch** parks an unfinished flight. **Flight records → Restore
paused flight** restores a compatible state; takeover and **Resume existing
mission** are explicit. Starting or retrying while a sortie is active is
rejected: save or end it first. New mission/retry and resume are different
operations and retain different evidence. See
[checkpoint and pilot-station boundaries](PERSISTENT_PILOT_STATION.md).

The following hosted-session notes are historical. Their URLs, ports, expiry
times and older recovery behavior do not identify the current local runtime.

## Historical hosted session and R6 controls

Live sandbox: https://sb-6iqplfebw 9l 2.vercel.run

The browser and Colin connect to one authoritative Python/MuJoCo process.
This URL is a temporary exposed Vercel Sandbox session, not a permanent
production deployment. The named sandbox retains its filesystem when stopped.
Sessions are time-limited and the named sandbox can be resumed from its retained snapshot. The first session expired after the recorded crash; resumption preserved all logs and pilot lessons.
Runtime project: `prj_elJEQpC8KCD9BFprF5mWeCoHfoLH`; sandbox `vtx-flight-lab`;
initial session `sbx_voOi 8kyJVrhGjVMGMQZfXKAzzFcD`, port 8765.
This is an isolated sandbox; no production deployment in that project was edited.

Click **Take manual authority** to use the same raw controls as Colin. It copies
the current actuator settings. Press **C** for cockpit/chase view.

The raw mixes below describe the R6 control path. Use the Phantom-specific
panel's **Take control**, sliders and deployment buttons for the current
Phantom candidates; do not assume another airframe's keyboard mix or fuel/drive
settings apply to Phantom.

| Input | Raw fly-by-wire effect |
| --- | --- |
| R / F | Increase / decrease common collective |
| Arrows | Increment common vector tilt, relative to the cabin's forward/right axes |
| W / S | Differential collective for pitch torque |
| A / D | Differential collective for roll torque |
| Q / E | Tangential vector mix for yaw torque |
| X | Engine command on / idle |
| Space | Feather collective and idle the engine |

Keyboard mixes are fixed mappings. They do not read attitude, velocity or
position and do not hold the aircraft stable. Released keys stop changing the
raw targets; current actuator targets remain held. Sliders show individual
channels. **Keyboard controls** opens a guide that closes with Close or Escape.
The guide starts closed and can be reopened at any time. Physics continues
while the guide is open. Select any valid A/B with the map or coordinate fields; local support
validation does not guarantee an obstacle-free route.

The displayed clock scale applies to the independent physics clock. 0.01× and
0.02× accommodate Colin's reasoning latency; 0.05×, 0.1× and 1× are also
available. All changes are explicit and logged. The last accepted command
remains in effect until the operator or pilot changes it, authority transfers,
or the flight test ends. Explicit Pause freezes physics and is logged.

**Retry · manual** and **Retry · Colin** start another attempt from the retained
departure and destination. In the current integration a new mission or retry
refuses an active test; save or end it explicitly first. The lower
frame selector chooses the full R4 or experimental R5 variant for a fresh sortie;
an active aircraft cannot be lightened by changing a menu.

Flight records provide post-flight state inspection. They cannot operate the
live plant. Camera views and instruments follow solver state, not animations.

The commands below describe the historical hosted client. For the current
local run, use the README procedure on port 8770 rather than these old URLs or
the earlier port-8765 launch recipe.

```sh
VTX_LAB_URL=https://sb-6iqplfebw 9l 2.vercel.run python tools/pilot_client.py observe
```

To resume hosting through the connected Vercel Sandbox tools, resume the named
sandbox in the same project, then run from `/vercel`:

```sh
PYTHONPATH=/vercel/src MUJOCO_GL=disable /vercel/.venv/bin/python -m uvicorn \
  vtx.live_server:app --host 0.0.0.0 --port 8765 --no-access-log
```

Use the returned current route; do not assume an expired session URL is live.
Resuming starts a new physical sortie only when explicitly requested; retained
logs and Colin's checkpoint are on disk. No Stage 2 environment has been created.

The session renewed at 08:10 UTC on 31 October 2026 expires around 08:55 UTC.
An attempted extension exceeded the account's 45-minute maximum. Durable
always-on hosting remains unavailable with the current project permissions;
the same experiment can run continuously on a local machine with the commands
above. Session expiry is not a landing, a crash reset or successful flight.

New test defaults are 10 kg total fuel, a 300 kW shaft-power ceiling and the 1200 rpm proposed gearset. Choose fuel/power before starting or retrying; their values are locked for an active sortie. The Keyboard controls dialog starts closed and closes again when returning through browser history. See `evidence/PROPULSION_FUEL_REVISION.md` for calculations and unresolved exhaust-lift inputs.
