# Phantom mobile flight data — 4 November 2026 UTC

These files are copied from the retained `vtx-flight-lab` Vercel Sandbox snapshot. Each run has a readable `summary.json`, `key-events.jsonl`, and the complete original `events.jsonl.gz`. Decompress with `gzip -dc events.jsonl.gz` to inspect every recorded observation and event. `summary.json` includes the SHA-256 of the uncompressed original.

| Run | Maximum barometric altitude | Touchdown sink rate | Status |
| --- | ---: | ---: | --- |
| [Initial manual sortie](20261104T022405-070aa5/summary.json) | 17.20 m | 11.585 m/s at 20.2625 s; 12.668 m/s at 34.2525 s | Archived collision |
| [Colin retry](20261104T023710-072007/summary.json) | 74.96 m | **33.734 m/s at 122.1525 s** | Impact recorded; no formal server summary before Sandbox expiry |

The second run's command lease expired at simulation time 117.9675 s, before touchdown. Its last saved observation shows weight on wheels and near-zero velocity; this is not evidence of a controlled landing. The operator initially mentioned a 200 m target, then changed the target to 75 m. This run did not reach 200 m.

The **confirmed 200 m eastbound run** is already in the repository: run [`20261103T192918-14ade4`](../flight_campaign_20261103/evidence/flights/20261103T192918-14ade4/summary.json), with [analysis](../flight_campaign_20261103/analysis_20261103T192918-14ade4.json). It used Phantom FX-C / A9, so it must not be conflated with the FX-A A10 mobile climb above. Its raw record belongs to the existing PC flight campaign, separate from these mobile Sandbox logs.

No airframe, MuJoCo model, physics, or control code was changed to export this data.
