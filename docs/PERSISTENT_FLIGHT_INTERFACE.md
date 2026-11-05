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
or send zero controls when unarmed. Its status reports when no fallback pilot is
available. There is no integrated natural-language model, provider-failure
detector or autonomous R6 stabilisation fallback yet. Stored goals and the
handover interface provide continuity for a pilot implementation; they do not
claim the aircraft is being flown or stabilised.

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
