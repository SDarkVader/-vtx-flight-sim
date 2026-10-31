# Live interface and keyboard controls

Live sandbox: https://sb-6iqplfebw9l2.vercel.run

The browser and Colin connect to one authoritative Python/MuJoCo process.
This URL is a temporary exposed Vercel Sandbox session, not a permanent
production deployment. The named sandbox retains its filesystem when stopped.
Sessions are time-limited and the named sandbox can be resumed from its retained snapshot. The first session expired after the recorded crash; resumption preserved all logs and pilot lessons.
Runtime project: `prj_elJEQpC8KCD9BFprF5mWeCoHfoLH`; sandbox `vtx-flight-lab`;
initial session `sbx_voOi8kyJVrhGjVMGMQZfXKAzzFcD`, port 8765.
This is an isolated sandbox; no production deployment in that project was edited.

Click **Take manual authority** to use the same raw controls as Colin. It copies
the current actuator settings. Press **C** for cockpit/chase view.

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

The displayed clock scale applies to the independent physics clock. 0.02× is
used for Colin's reasoning latency; manual users can choose 0.1× or 1×. A
5-simulated-second command lease feathers/ idles if inputs cease. That event is
logged and may cause a crash. Explicit Pause freezes physics and is logged.

**Retry · manual** and **Retry · Colin** appear after a crash or completed
sortie. Retry archives an active crash, preserves the pilot checkpoint and
starts a fresh aircraft at the retained mission A, with the same B. The lower
frame selector chooses the full R4 or experimental R5 variant for a fresh sortie;
an active aircraft cannot be lightened by changing a menu.

Flight records provide post-flight state inspection. They cannot operate the
live plant. Camera views and instruments follow solver state, not animations.

For a local, durable run, follow `LIVE_LAB_IMPLEMENTATION.md` and open
http://localhost:8765. For a hosted pilot client:

```sh
VTX_LAB_URL=https://sb-6iqplfebw9l2.vercel.run python tools/pilot_client.py observe
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
