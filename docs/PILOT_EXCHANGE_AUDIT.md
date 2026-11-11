# External AI-pilot input/output audit (opt-in)

The simulator already records observations, accepted/rejected controls and physical outcomes in `evidence/flights/<run_id>/events.jsonl`. It does **not** call Colin's external language model and therefore cannot capture the prompt or raw response on its own.

`vtx.pilot_exchange.record_exchange` is an optional helper for the **external model caller**. Invoke it after each model response with the actual API request and response objects, the current simulator run ID, unique decision ID and observation ID. It creates `evidence/flights/<run_id>/pilot-exchanges/<decision_id>.json` without overwriting existing decisions.

Example (inside the external model client, not the simulator):

```python
from vtx.pilot_exchange import record_exchange, sha256_bytes

record_exchange(data_root, flight_id=run_id, decision_id=decision_id,
                observation_id=observation_id, sim_time_s=sim_time,
                request_payload=model_request, response_payload=model_response)
```

This is **not automatically active** until the actual model caller invokes it. It does not alter the physics clock, control interface or pilot decisions. Capture at the API boundary; do not reconstruct prompts from observation logs.

Object fields resembling credentials are redacted. Nested free-text may still contain sensitive material, so keep logs private, exclude them from commits, and use controlled retention. Stored JSON is not byte-identical to the API exchange after redaction. Optional SHA-256 hashes can be computed on the original serialized request/response bytes before redaction.

Tests: `pytest -q tests/test_pilot_exchange.py`. A passing unit test does not validate a live external AI integration; verify a real sortie separately after instrumenting the model caller.
