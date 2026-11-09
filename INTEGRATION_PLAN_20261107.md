# VTX unified integration — 7 November 2026

## Sources of truth

- A10 reference: `checkpoint/phantom-a10-live-20261106` at `9ff488dc0e3f6d8590dde4a1b4a2958b36bb51d1`. User independently identifies run `20261106T125337-b1e1a0`, configuration SHA `70089ccace22e4ce1cfd28104654257fe4d03771c4f6b1faa3c89fce253247dd`; paused, manual, 0.5x. This is a configuration/telemetry checkpoint, not a resumable MuJoCo state.
- Airport: `work/unified-airport-20261104` at `210272d928f26bfe1b331b5e8c8bc87814ad1d0c` on the PC. Retains airport operations, separate visual traffic and physical integration changes.
- Recovery: `origin/recovery/a10-local-20261106` at `f22e4efa8003cde644a42f9fd317c157d1853ee2`. Incorporates airport work and A10 engineering/camera changes. It differs substantially from the A10 checkpoint.
- PR #34: head `0228a66974eefe8b3df8b9fe2ccda7f236402b9e` on airport base; physical flight default and explicit scripted traffic. Open, not accepted or promoted. Two changed files; cannot assume end-to-end recovery from its checks.
- Additional candidate `74f4c3a`: physical sortie selector and pilot work; reconcile feature-by-feature with recovery and checkpoint.
- Dirty live working tree: preserved as `C:\Users\steve\Documents\GitHub\vtx-preserved-pre-integration-20261107.zip`; archive CRC verified; includes 418 changed/untracked file contents, SHA-256 manifest, index and merge metadata. The live checkout and process were not modified by the merge.

## Plan and acceptance

1. Reconcile the checkpoint with recovery in this isolated worktree; resolve each of the identified conflicts against the feature intent and compare configuration and asset hashes. Preserve checkpoint assets and physical model behavior; reconcile rather than select whole files indiscriminately. Reconcile PR #34 and the later `74f4c3a` selector independently.
2. Run a separate Python/MuJoCo runtime on a verified free port and a new data root, never port 8765 or the production evidence/archive roots. Compare identity and instrument response against the checkpoint. Do not claim a paused state is resumable without a full physics snapshot.
3. Bring existing airport, cameras, models, manual flight, actor separation and animations into one physical cockpit. Check both aircraft, correct asset and matching physics identity, controls, mechanisms, telemetry, collisions and persisted evidence on desktop and mobile.
4. Connect actual experiment execution and provenance to that same runtime. Preserve implementation, measured-simulation, derived and hypothesized inputs. Results require run identifiers, model/config/asset hashes, conditions and separately recorded assessment criteria. Do not invent results.
5. Integrate run-scoped pilot authority, handover, disconnect and reconnect, voice/session persistence and fallback. Verify only one active controller and continuous observations/actions. Conversational voice requires an actual provider and tested session, not just the deterministic voice grammar.
6. Provide authenticated PC/mobile access to the authoritative stateful runtime, with persistence and secured connectivity. Test end-to-end through the actual access path. A static Site or Vercel READY status does not prove physics connectivity.
7. Promotion and duplicate-service removal only after all acceptance tests and preservation of the existing flight. No changes to port 8765 before acceptance.

## Current worktree state

The recovery merge was started without committing. Conflicts are intentionally left for explicit reconciliation; no blanket ours/theirs resolution. Do not run the candidate until conflicts are resolved and the isolated runtime is configured.

## Reconciliation progress

- `src/vtx/phantom/controls.py`: retained checkpoint flight-control code and added recovery's optional pilot/run identity fields. Enforcement must be checked with the unresolved server.
- `public/vtx-env/quality.js`: kept the checkpoint's 0.8 low-tier pixel ratio; performance/visual quality still needs mobile profiling.
- `public/vtx-env/traffic-path.js`: retained existing paths and the additive kinematic ground-traffic helpers. The latter are not physical aircraft control. Ground/path suite: 4 passed.
- `src/vtx/phantom/plant.py`: retained checkpoint P6/P7 and road-start folded canards; incorporated recovery's A10 asset provenance and articulated-geometry CG input to the controller. This is a candidate change to physics/control behavior, not proof of identity with the paused runtime.
- `src/vtx/world.py`: integrated recovery's extended terrain/runway with a distinct world id/version because it changes the checkpoint terrain. Requires full visual/physics alignment and performance validation.
- `tests/test_phantom_ledger.py`: retained the additive snapshot/body-origin and articulated-CG tests. Both targeted tests passed.
- `test_phantom_p6_p7.py`, `test_phantom_plant.py`, `test_takeoff_strip.py`, `test_verify_artifact_identity.py`: 15 passed. These do not establish full model equivalence, end-to-end flight, graphics or production readiness.
- Twelve files remain conflicted, notably the live server, phantom session handling, cockpit/pilot controls, appearance and associated tests. Do not launch until resolved. Preserve checkpoint voice functionality while reconciling the recovery branch's run-bound control and command semantics. Check lease/fallback behavior as a complete system rather than choosing a file in isolation.
- Port 8765 was observed after work: run `20261106T125337-b1e1a0`, active, paused, manual, 0.5x. Only read endpoints were used.

## Continued reconciliation

- `phantom-look.js`: combined the checkpoint's joint/effects implementation with recovery's A10 appearance/deck additions; syntactic check passed. Needs visual verification.
- `phantom-controls.js`: retained checkpoint voice and heartbeat, added recovery's front-surface controls and expected run ID. Voice grammar and operator-heartbeat checks passed; browser and handover checks remain.
- `src/vtx/live_server.py` and `src/vtx/phantom/live.py`: working files have no conflict markers, but remain Git-unmerged pending behavior review and tests. Added recovery pilot ownership, landing records and run-scoped operations while retaining checkpoint lease. Fixed checkpoint restoration to preserve recorded options and compare actual model hashes. Fixed stale-run destination rejection.
- 42 live-interface, checkpoint and landing tests passed; one recovery test (`test_accepted_command_survives_pilot_delay`) is intentionally unresolved because its hold-without-lease behavior conflicts with the checkpoint's five-simulated-second lease and stale observation check. Do not remove or silently alter this test without resolving full reconnect/fallback semantics.
- The isolated backend was started on 127.0.0.1:18879 with `VTX_DATA_ROOT` under `integration-test-data-20261107` (ignored by Git). Initial test discovered P6 default config mismatch; after restoring the reference P6 setting, isolated run `20261107T140058-a9a060` matched reference configuration SHA, model XML SHA and render-asset path. On-disk Phantom GLB SHA-256 also matched the live checkout (`315fd09c2dc33d27c4954c3440a9eac4db9917c593eb289b637118e81844cfed`). This is identity evidence, not a full dynamic equivalence or resumable snapshot claim. Test sortie ended without takeoff.
- Vercel list reports READY previews for the checkpoint, recovery and airport branches. READY is deployment status, not evidence of a persistent physics connection. Nothing was deployed or promoted.
- `public/app.js`, `public/index.html`, pilot bridge and related tests remain conflicted. The isolated server's UI is not usable until those are reconciled. Do not promote or use for actual flight.

## Command persistence correction

`docs/PERSISTENT_FLIGHT_INTERFACE.md` explicitly specifies held accepted controls without an elapsed-time lease, run-bound handovers, and Phantom fallback reported unavailable. The temporary choice to retain the old five-second lease was incorrect for this design. Candidate server and Phantom runtime now hold accepted controls; the Phantom panel transmits changed controls and retains voice and run identity. Focused live/checkpoint/landing tests: 43 passed, including the previous held-command conflict. Phantom live boundary and handover tests: 6 passed. Voice and operator tests: 4 passed. These are isolated tests, not end-to-end mobile or real conversational pilot validation. Working server files still require conflict staging and full review. The isolated running server at 18879 predates this correction and must be restarted before using it to test the new policy. Port 8765 remains untouched.

## Failure and reset instruction

User specified failed tests should be recorded with a pilot summary and engineering findings and reset; the long pause applies only to the protected reference flight. Candidate now preserves `summary.json`, events and Phantom crash ring, generates `pilot_summary.json` and `engineering_findings.json` with measured-simulation data and an explicitly unassessed cause, and starts a distinct new run. A confirmed run-bound pilot provider failure or modeled crash triggers this path; an ordinary connection interruption does not. The replacement starts with manual authority and inherits the prior mission/configuration through retry; no automatic pilot is claimed. The record is saved before retry, and an evidence write failure prevents retry. 52 focused tests passed, including retained-run crash/retry, pilot failure, crash ring capture, stale failure fencing, flight checkpoint and landing tests. This is an isolated candidate change, not production; server/UI/pilot reconciliation and end-to-end tests remain. The 18879 process predates this change.

## Isolated cockpit test candidate

All Git conflict markers have been resolved in the isolated worktree; source is still uncommitted and has not been promoted. The cockpit combines physical vehicle selector, airport rendering, pilot objective, flight records, telemetry, and experimental options. Physical motion renders the MuJoCo body pose, and the physical chase camera tracks the simulated world CG; `rideCgLocal` remains confined to the explicitly scripted visual traffic path. The fixed scripted path is not the physics aircraft's pivot or CG. Camera/physical visual and current articulated CG checks passed; this is not yet a visual/in-flight acceptance.

The isolated server is listening on PC localhost 18879 with `integration-test-data-20261107` as its data root. An HTTP test started Phantom, handed control to a test pilot, injected provider failure and verified a fresh unpaused manual run with matching reference config SHA; both test attempts were ended and retained. Browser rendering and PC/mobile interaction have not yet been independently verified. The candidate is not accessible from another device through PC localhost. Existing production port 8765 was not modified.

A broad regression run stalled and was stopped; the previous selector expectation was reconciled and 10 Phantom A10 tests passed. Some legacy pilot supervisor/simulation tests may require updates for the user-requested automatic reset semantics; do not claim all regressions or acceptance complete.

## PC test access, historical evidence and start modes

PC test server remains 127.0.0.1:18879, with separate integration data. A headless Edge smoke check observed a Three.js canvas, Phantom panel and required controls; this is not a visual flight or mobile acceptance. The live API lists 12 existing summary records (3 r6-live, 9 unified-live), read-only and labelled by original outcome; these are not asserted to be all retained flights, and paths/raw replay and the Documents backup are not indexed. Failure summaries/findings are exposed in Flight records for candidate runs; causes stay not assessed unless evidence supports them.

Phantom start selection now passes `start_configuration=vtol` or `road` to the actual plant. Isolated checks report VTOL pods 90 degrees/legs 0.52 m and road pods 0 degrees/legs 0 m; they share reference config SHA. The panel exposes separate pod and leg commands so transitions can be sequenced; command-independence was tested, but full ground-contact transition and end-to-end manual operation still need visual verification. A `Set A: runway 08 start` button uses (-700,0), 15 m inside the rendered threshold at (-715,0), and both map and Phantom footprint validators reported clear; this is an operator-selected starting point, not a new physical constraint.

The matching Phantom GLB includes the DRS hinge, booster petal nodes and both ceramic exhaust liners. The retained effects implementation reads booster thrust and fan rpm; no thrust/glow visual acceptance has been performed. The paused run 20261106T125337-b1e1a0 on port 8765 was checked unchanged.
