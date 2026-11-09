# OpenAI pilot recorder (experimental)

The recorder is opt-in and separate from the aircraft's physics clock. It uses a bounded in-memory queue and background writer. An I/O failure increments `write_errors`; queue overflow increments `dropped`. Neither failure stops flight, but **the audit is then incomplete**. This is not lossless recording or durable delivery.

## Configuration

Set `OPENAI_API_KEY` on the trusted Python server, **never in the browser, a prompt, or GitHub**. Set `VTX_DATA_ROOT` to a persistent private directory. On a public deployment also configure `VTX_CLOUD_ACCESS_TOKEN` and HTTPS. The local server has opt-in authentication; do not expose it to the public internet without configuring access controls.

Start a real sortie with `authority: "colin"`. Then POST to `/api/pilot/openai-decision` with JSON:

```json
{"instruction":"Climb to ten metres","model":"gpt-5.1"}
```

The endpoint uses the current permitted sensor observation and sends the instruction and observation to OpenAI's Responses API. It records the exact JSON request, returned JSON response or error type, with flight and decision IDs in `VTX_DATA_ROOT/evidence/flights/<run_id>/pilot-api.jsonl`. The request runs in a worker thread, not the physics event loop.

**The model response is informational only.** It is not parsed into control commands. Colin must still use `/api/action` to fly. The same audit file also receives observations served by `/api/observe` and accepted `/api/action` submissions for both R6 and Phantom. The action and observation events have no model decision ID until the external pilot provides a reliable association; use timestamps and observation IDs for partial correlation. Existing `events.jsonl` continues to record physical consequences. No physics, authority, control or aircraft dynamics were changed.

## Offline test

`pytest -q tests/test_pilot_api_recorder.py`

The test uses a simulated “Climb to ten metres” request and mock response. It does **not** establish an airborne flight or test the live OpenAI account. No key or API credit is needed.

## Limitations

The OpenAI API returns model outputs and any available reasoning summaries, **not private internal chain-of-thought**. Full payloads can contain sensitive user content; protect the private data directory. This first version does not implement log rotation, guaranteed delivery, model-driven automatic control, or end-to-end decision-to-actuator linking. Do not merge as flight-tested until CI and an R6 smoke test have passed.
