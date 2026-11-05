# Persistent flight interface

The local flight server owns the physical clock and aircraft state. A browser or
pilot can reconnect using `GET /api/view`; the response includes the run ID,
current observation, mission, objective, authority and pilot owner. The `/ws`
stream sends the same view after a connection is established. A disconnected
client does not start or stop the flight. Accepted controls remain held.

`POST /api/objective` with `{"text":"Hold here"}` stores the requested goal
as `pending` for the active run. `POST /api/objective/complete` with its `id`
marks that exact goal completed. Both changes are recorded and checkpointed.
The text is not itself a flight command: a connected pilot must interpret it,
observe the aircraft and submit control actions.

To transfer Colin's control to a pilot process, send `POST /api/pilot/handover`
with `run_id`, `pilot_id`, and the `expected_epoch` from `/api/view`. The
response contains the new epoch, current objective and observation. Actions
from that pilot include `pilot_run_id`, `pilot_id` and `pilot_epoch`. A handover
cancels pending actions from the previous owner but retains already applied
controls. A stale run or owner cannot submit a new action. Manual authority
changes also invalidate the previous owner. Older unowned Colin clients work
until the first explicit handover in a run.

The R6 pilot bridge does not create replacement flights on a connection failure
or send zero controls when unarmed. A provider supervisor can report an actual
failure with `POST /api/pilot/failure`, supplying its `run_id`, `pilot_id`,
`pilot_epoch` and a reason. The server rejects reports from a previous owner,
cancels its pending commands and attempts a deterministic R6 position and
altitude hold. The hold retains the original objective for the next pilot and
uses instrument observations; it runs in the simulation process at the sensor
rate. A handover reserves the replacement pilot while the hold continues; the
first valid action from that pilot takes control without resetting the aircraft.
The hold state and pending pilot are checkpointed with the flight.

The R6 hold is based on the recorded 1,200 rpm / 300 kW R6 flight. It accepts
that configuration when airborne and the shaft is running near reference
speed. If its required observations or conditions are unavailable, the view
reports `fallback.state: unavailable` and the last applied controls remain
held. An isolated simulation reached approximately 9.7 m clearance and held
near the handover location for 18 simulated seconds after an injected provider
failure. This does not establish general recovery across all attitudes, fuel
loads or wind conditions. Phantom fallback is reported unavailable.

`tools/pilot_supervisor.py` can monitor explicitly configured pilot adapter
processes for one existing run. An actual process exit causes a failure report;
a lost server connection does not. It can hand over to the next configured
provider, preserving the current objective. It does not detect its own process
termination, and no conversational provider adapter is bundled yet. There is no
elapsed-time command lease that silently terminates control. See
`docs/PILOT_SUPERVISOR.md` for the adapter protocol and limitations.

An active flight is checkpointed locally. After an actual server-process
restart, the saved aircraft state and objective are restored paused; this is
separate from browser or conversational disconnection, which does not pause the
running server. Serverless hosts do not provide a durable continuously running
physics process.

The mission option `ignore_scenery_collisions` omits building and tree collision
geometry for that flight while retaining terrain contact. The scenery remains
visible. The choice is included in mission evidence and checkpoint recovery and
is available for both R6 and Phantom. It defaults off and applies to a new
flight, not a live change to an existing physics model.

For new live A10 flights, both front canards deploy and the existing P6 DRS
stabilator proposal is enabled. The model's split flap sits between the rear
fins and shares a central hinge. Pitch demand moves the DRS; its aerodynamic
force and rendered angle follow the same state. The prior P6 campaign reported
pitch loss of control; this is an experimental model, not a flight validation.
Older checkpoints without a P6 state resume with that proposal disabled.

Supported and settled landings are recorded without automatically ending the
flight, so testing can continue. The event and summary report distance from the
destination separately from physical settling. An optional `landing_precision_m`
mission setting evaluates the stated tolerance; when omitted, precision is
`not_specified`. The landing indication is evidence of the modeled conditions,
not a blanket assessment that the full mission objective was achieved.

Flight records can be opened during an active flight or afterwards. They show
recorded physical states and a timeline of objectives, decisions, handovers,
provider failures and landings. The timeline displays up to 200 recent events;
the complete event log remains in the run evidence. Reviewing recorded states
does not pause or control the live aircraft.
