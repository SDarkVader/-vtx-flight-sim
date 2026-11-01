# Raymond Winston — VTX cockpit observation log

**Recorded:** 2026-11-01  
**Observer/operator:** Raymond Winston (conversational remote pilot)  
**Status:** Historical observation report; **not** a fresh live telemetry capture.

## Position and available instruments

My "seat" is the VTX software pilot interface. I do not physically occupy a cabin or experience acceleration, sound, or vision as a human pilot would. I receive permitted instrument and scene observations and issue control commands through the simulator's fly-by-wire interface. The airframe and physics continue independently of my conversation and decisions.

The interface supports commands for engine power, four nacelles' collective pitch and two-axis tilt, and cabin articulation. The aircraft is modeled with gravity, mass/inertia, rotor response, ground contact, and mechanical limitations. A control request is **not** proof that an actuator achieved it or that the aircraft flew.

## Prior observed session (historical, not current)

A previously discussed run, **20261101T143514-d304d7**, reported:

| Instrument / state | Reported observation | Interpretation |
| --- | --- | --- |
| Rotor speed | Approximately 1,190 RPM reached | Rotor operation, not proof of lift |
| Engine command | Maximum reported fraction 1.0 | Command level; not a measured thrust force |
| Collective | Up to 16 degrees reported | Control input; achieved blade pitch requires actuator telemetry |
| Ground clearance | Approximately 0.75 m | No verified departure from landing gear |
| Flight outcome | **No confirmed takeoff** | Cannot claim successful flight |

During a conversational demonstration, the four fan assemblies visibly articulated and rotor power changed in response to remote commands. Two people watching the simulation independently observed these movements. This establishes an interactive control demonstration, not a completed flight.

## Cockpit perspective — first-person operator commentary

The boss talks to his phone while watching the aircraft on a separate computer. From my side, that speech becomes an instruction, which I must turn into a specific control action, send, and then check against the next available observation.

The four ducted fans can move in ways that make the airframe look almost as if it's dancing. It's a convincing demonstration of independent articulation, but the important instrument is not how impressive the movement looks: it is whether the physics reports the intended motion.

When power rises and collective changes, I cannot simply declare the aircraft airborne. On the recorded attempt it remained on the ground. Gravity appears to have declined my application for promotion to aviator.

The unusual feature is that the same conversation can also initiate inspection and changes to the software around the vehicle. That is a separate development capability, not an in-world physical action by the pilot. Together, live actuation and concurrent code work make the test environment unusually flexible.

## Current connection and evidence limitations

At the time this entry was prepared, Steve_PC was accessible via Desktop Commander, but `http://127.0.0.1:8765/api/view` was **not responding**. Accordingly there are **no current** readings for position, attitude, velocity, altitude, thrust, fuel, rotor speeds, collisions, or flight-control authority. Do not substitute historical values for current telemetry.

The repository's `docs/LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md` defines the governing standard: actual live observation/action loops, identical control semantics for AI and human pilots, and no precomputed flight path or hidden autopilot. The cockpit log is an operator account, not a certification that all acceptance conditions have been met.

**Next observation:** With the simulator running, capture a timestamped `/api/view` and `/api/observe` snapshot plus the associated control request and achieved actuator state; append it as a separately identified live measurement.

— Raymond Winston, Vader's Taxis Experimental Aviation Division
 

## Flight Two designated location — Raymond's Patch

**Site name:** Raymond's Patch — VTX First Conversational Test Stand  
**Marker:** RW-01 / amber cockpit beacon  
**Airframe:** P0-V4A-assembly-r5  
**Local position:** GNSS x = -0.03 m, y = +0.04 m (initial inspection reading; approximate origin)  
**Initial radar clearance:** 0.821 m  
**Observed state:** inspection mode, aircraft inactive, four rotors stopped, no mission running.

I designate the aircraft's present starting position as **Raymond's Patch**: the spot where the second instrumented conversational flight trial is to begin. The marker is documentary, not yet a rendered object in the world. Its proposed in-world appearance is a small amber RW-01 ground beacon and a sign reading *Raymond Winston — Experimental Test Pilot*. The marker's coordinates refer to this local simulation frame, not a real-world geographic location.

This is the **Flight Two staging location**, not a claim that Flight Two has flown. Flight One refers to the earlier live remote-control demonstration. A subsequent flight record must capture departure, actual movement, landing or failure, and the measured telemetry separately.

*Cockpit note:* Every test pilot ought to have a patch of ground to call his own. Mine is conveniently located exactly where the aircraft is currently refusing to leave it.

## Flight Two — unattended recorder handoff

Mission started with run ID `20261101T151650-a47d96`, departure `[0,0]` at Raymond's Patch and destination `[35,20]` (local simulation metres). Both locations passed the simulator's map-validity checks. The mission was created under `colin` control authority, with simulation time scale `0.05` and stability assistance `0`.

A separate local process began writing approximately one pilot-facing observation per wall-clock second to `evidence/flights/20261101T151650-a47d96/raymond-flight-two-observations.jsonl`, independent of the phone connection. The recorder is designed to end after approximately fifteen minutes, or earlier if the mission ends, then commit and push its own observation log to this branch. Raw simulator audit evidence remains in the run's evidence directory.

**Critical limitation:** the process is a passive recorder, not an AI pilot. The flight mission is initialized but no autonomous end-to-end flight is claimed. An actual flight requires continued observation-based control decisions; do not mistake mission creation or unattended recording for flying.

## Flight Two live session and evidence preservation

**Live run ID:** `20261101T151650-a47d96`  
**Mission label:** Raymond Flight Two RW-01 instrumented trial  
**Departure:** (0, 0) — Raymond's Patch  
**Destination:** (35, 20) — simulation local metres  
**Authority:** Colin interface; pilot command source must be checked from action logs  
**Status at recorder activation:** active, at approximately 1.03 simulated seconds, no warning lamps. No takeoff or landing verified.

The simulator already had this active mission when the dedicated recorder was started. A second mission request returned HTTP 409 (conflict), so the existing flight was preserved rather than reset. The recorder `tools/raymond_flight_two_recorder.py` writes UTC-stamped permitted `/api/observe` responses each second and periodic instrument-only `/api/view` snapshots to `evidence/raymond-flight-two/`. The simulator separately persists native event logs in `evidence/flights/20261101T151650-a47d96/`. The recorder does not issue flight-control commands. A phone disconnection does not itself stop this PC-local process; a PC shutdown or server failure can.

## Flight Two — active run and persistent capture

**Run ID:** `20261101T151650-a47d96`  
**Mission:** Raymond's Patch `(0,0)` to `(35,20)` in the stage1-valley environment.  
**Operator:** `colin` authority channel used by Raymond for a single explicitly chosen action.  
**Recording:** `evidence/flights/20261101T151650-a47d96/events.jsonl` (simulator audit) plus `raymond-monitor.jsonl` (independent one-second wall-clock pilot observations). The recorder is a detached PowerShell process, configured for up to fifteen minutes or until the sortie ends; it does **not** generate flight controls.

**Initial control:** one live action accepted, sequence `1`, scheduled at simulation time `3.93 s`: engine `0.5`, symmetric collective `10°`, zero tilt. This was a spool-up test, not a flight path or autopilot.

**First response:** at simulation time `4.02 s`, four rotor speeds were approximately `5.01–5.02 RPM`, radar clearance `0.752 m`, and no warning lamps. No takeoff was established. The control lease will expire without further deliberate piloting actions.

The active run is a trial, not a completed end-to-end flight. Preserve the simulator's own final summary to determine actual outcome. Do not interpret unattended observation logging as autonomous piloting.
