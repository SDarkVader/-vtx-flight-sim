# Run-bound pilot supervisor

The optional supervisor attaches pilot adapter processes to an **existing**
Colin-controlled flight. It never starts a mission or changes the objective.
It is separate from both the browser and the server physics loop.

Start it with an existing run ID and a local JSON file, for example:

```json
{"providers": [
  {"id": "pilot-a", "command": ["python", "adapter_a.py"]},
  {"id": "pilot-b", "command": ["python", "adapter_b.py"]}
]}
```

```text
python tools/pilot_supervisor.py --base http://127.0.0.1:8774 --run-id RUN_ID --providers providers.json
```

Each command is an argument array, invoked directly without a shell. These are
protocol examples: no AI adapter, credentials or model provider are supplied
by this repository. The user must configure a compatible adapter before using
this supervisor with an actual conversational model.

Each adapter reads newline-delimited JSON state packets on standard input. A
packet contains `type: "state"`, `run_id`, the current `objective` (possibly
null), and a permitted instrument `observation`. The adapter writes newline-
delimited JSON on standard output with `type: "action"` and an `action` object
matching the existing R6 or Phantom action schema, including the observation
ID and decision reason. The supervisor attaches run, authority, pilot ID and
epoch itself. An adapter can also report a real provider error by writing `{"type":"failure",
"reason":"..."}`. Diagnostics belong on standard error. State packets are latest-
only; slow adapters do not build up an unlimited telemetry queue.

The server holds the most recent accepted control. A slow or silent provider is
not declared failed because of a deadline. On an actual child-process exit or a reported provider error, the
supervisor reports that failure to the server and tries the next provider. If
R6 hold is supported it continues until the replacement's first valid action;
if unavailable, the server reports that state and retains the previous controls.
A temporary server disconnection alone does not trigger failure or start a new
flight. If a different pilot or manual operator takes control, the supervisor
stops rather than reclaiming ownership.

The supervisor itself is a separate local process, not a redundant service. If
it or its host stops, it cannot report its own failure. The flight server still
retains the last applied controls and objective, but automatic fallback is not
guaranteed in that case. The R6 fallback has only been demonstrated in the
specific hover scenario recorded in `PERSISTENT_FLIGHT_INTERFACE.md`; Phantom
fallback currently reports unavailable. No claim of successful autonomous
flight follows from adapter or failover tests.
