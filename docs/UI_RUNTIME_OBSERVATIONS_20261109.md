# Running simulator UI observations — 2026-11-09

These observations concern the already-running simulator at http://127.0.0.1:8765/ on Steve_PC. Its process was launched from the dirty primary checkout using `scripts/launch_pc.py`, not from this integration worktree. They are not a validation of the integration branch.

- On opening the interface, the live state reported idle, manual authority, simulation time 0, revision `P0-V4A-assembly-r6`, physics revision `audit-fixes-20261103-r3` and asset `/assets/airframe-r6.glb`. The selector displayed R6. The owner explicitly identified the displayed aircraft as not being the correct R6; the labels do not prove model identity.
- Phantom A10-B was not the default. The displayed selector did not offer an explicitly named A10-B; the visible Phantom choices were labelled A10 and A9. No model was switched.
- The page displayed `Solver stopped: Flight checkpoint unavailable: Checkpoint model differs from current physics model`. Reproduction: open the existing page while this checkpoint and model state remain in place.
- Clicking **Flight records** showed `Cannot read properties of undefined (reading 'toFixed')` rather than opening records. Reproduction: open the existing page and click **Flight records**. No evidence was removed.
- Clicking **Cockpit** entered the cockpit view and exposed look controls; clicking **Look left** was accepted and the scene was displayed from the cockpit. This does not validate flight control inputs.
- At a 390 × 844 browser viewport, the scene and physical-controls section were visible in a vertical mobile layout. This is a visual smoke check, not a complete mobile usability or control test. The browser viewport override was reset afterward.
- Telemetry values were visible but static while no sortie was active. Wing deployment, flight controls, live telemetry changes, record retrieval, A10-B model and physics identity, and actual flight remain unverified in this running instance. No configuration, aircraft, flight, or physics setting was changed.
- Screenshots were captured in the computer-use session but no standalone screenshot files were retained; repeat the steps above to capture durable images.

## Owner-provided visual reference

The owner supplied `C:\Users\steve\Documents\Github\WhatsApp Image 2026-11-05 at 08.48.06.jpeg` and `C:\Users\steve\Documents\Github\WhatsApp Image 2026-11-048.06.jpeg`. Both show a Phase 2 aircraft in a visual-development report, with four roughly horizontal ducted fans, a central cabin and exposed frame. The owner states the aircraft currently displayed is not the correct R6. These images are visual references and do not by themselves establish a physics revision or identify a matching GLB.

The existing live checkout's `public/assets/airframe-r6.glb` has SHA-256 `8bd22777c41e193a523037396ba28e31acecee597500d1967d74f948152c0c95`. This integration worktree's file at the same relative path has SHA-256 `d001ae20ba7665cbdbb8e910e4006df07bc855cbcf85c58211ff81e04ac82034`. They are different files: investigate their appearance, rigging, and provenance against the reference before asserting that either is canonical. Neither was changed for this investigation.
