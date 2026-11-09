# Isolated UI test, 2026-11-09

This is a browser-operated test of integration commit `5886afd6355747b96d379d2c03e184ee3bae87ba`, using `vtx.dashboard_site:app` on `127.0.0.1:18909` and a new, separate `VTX_DATA_ROOT`. The pre-existing simulator on port 8765 and its checkpoint were not changed. The archive contains the complete isolated runtime data, including raw events, model XML, parameters, ledger, telemetry, experiment requests and summaries. It contains no screenshots.

## Findings

- A clean page loaded R6 initially. A10-B is present in the selector and can be selected, but it is **not the default game vehicle**.
- After selecting A10-B, the interface showed configuration prefix `3ecae1a925a6`; `/api/view` returned full SHA-256 `3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01`, model XML SHA-256 `8ddcb5f0f217b957fa316a0f50a0c10273a39c9304dddae6aefd8450d2e28329`, and render asset `/assets/phantom-a10b-visual.glb`. That GLB's file SHA-256 was `45364301f2950ca57e5b34ac73d29b0abe11471dd82f0fe0e5068da70418a93e`. These identify the loaded files; they do not independently establish visual correctness against an approved A10-B reference.
- Started manual sortie `20261109T201818-c9041e`. Clicking **Wing deploy** showed both sides progressing through `hatch_opening`, `sliding_out` and `locked`; clicking **Canards deploy** changed the button to **Canards fold**. Increasing **Front left surface** to 1 degree produced an accepted `canard_pitch_deg: [1, 0]` command. All three manual commands are in `pilot-api.jsonl`. No takeoff was attempted.
- Cockpit view and look button responded. The cockpit instrument overlay showed dashes for altitude, vertical speed, speed and fuel during the active sortie, while the main telemetry displayed values. The Phantom control panel displayed `radar undefined`. These are reproducible UI defects; no physics conclusions follow from them.
- **End & retain evidence** produced the no-takeoff summary. **Flight records** displayed the sortie, historical PC summaries and a timeline listing all three manual decisions. This isolated instance does not reproduce the `toFixed` flight-record failure observed separately in the existing port-8765 simulator.
- From **Physics experiments**, a 3-second A10-B run `a0d18a9fec534ffd993e6d5270acac76` completed and displayed `3ecae1a925a6`. An A10-A P6-disabled run `f96ec9c3bae545cbb4d38531ed3d8166` completed and displayed `b835295b7b80`. The comparison showed both rows. Clicking **Download evidence ZIP** saved the A10-B export to the user's Downloads folder. This is a short ground test, not flight acceptance.
- At 390 × 844, the experiment form and cockpit rendered with a vertical layout and scrollable navigation; this was a smoke check, not a complete touch/accessibility test. Returning from experiments to cockpit preserved the A10-B selection in this instance.
- Browser screenshots were captured for inspection but the computer-use tool did not provide a retained local screenshot path; standalone screenshots remain outstanding.

## Reproduce

Launch the integration worktree with `PYTHONPATH=src`, an unused port and a new `VTX_DATA_ROOT` as described in `docs/INTEGRATION_HANDOFF_20261109.md`. Open the cockpit, select A10-B, start a manual mission, open Controls, deploy wings and canards, and inspect cockpit instruments. End the sortie and open Flight records. Open Physics experiments, run the default A10-B 3-second schedule, then select A10-A without P6 and repeat to inspect the comparison and evidence export.

Do not overwrite the owner’s existing runtime, data, or checkpoints when reproducing.
