# Vehicle selection, cameras and Windows launch — 17 November 2026

The development Argon R6 and Phantom A10-C are explicit choices in Main Aircraft and Choose vehicle. The inaccurate “visual match pending” text is removed. Existing R6 assets, physical variants, control channels and avionics are retained. Historical aircraft remain under the earlier/experimental group. An active aircraft flight must be saved or ended before changing its physical variant.

The right controls panel now follows the selected seat. Aircraft shows the physical aircraft's own controls; Ricochet shows its helm and harbour controls; scenic passenger seats show a passenger notice. Switching away clears pending aircraft panel input without sending a control command, stopping a flight or changing its authority. The Phantom voice command path and legacy keyboard input cannot operate the aircraft from the boat/passenger panel.

Selecting either Ricochet opens a cockpit camera. Its render datum is above the authored bucket seat, behind the two instrument displays and inside the canopy. The camera uses the same interpolated airframe transform as the hull, so rotation and translation stay attached to the boat. Cockpit mouse look, chase and top views remain available. Boat and passenger cameras do not overwrite the physical aircraft's remembered camera. R6 passenger views use the existing cabin eye datum and its -Y forward axis.

Current physical and scenic aircraft assets have explicit SHA-256 render pins. Pinned bytes are verified before GLTF parsing; a mismatch reports an unavailable visual instead of displaying a substitute. This is visual identity verification, not a change to physics configuration, aircraft acceptance or promotion. Ricochet rendering retains the existing physics-derived geometry identity checks.

The Windows launcher preserves a frontend-incompatible idle selection in the existing recovery archive. An occupied port must match the airport/harbour runtime and every frontend text file before it is identified as this build. Launcher-served static files use cache revalidation, including conditional responses; this wrapper does not alter API responses or the Python runtime fingerprint. A browser with an older document already open still needs a deliberate reload after an approved update.

## Verification

- Full local Python mathematics/regression suite: **519 passed** with an isolated data root and test-output directory.
- Final JavaScript suite: **77 passed**, including the camera follow-up.
- Runtime review guard passed with the same recursive Python fingerprint as main; `src/vtx` and physics inputs are unchanged.
- Offline browser fixture: Main Aircraft selected `r6`, the R6 rotor controls appeared, the Phantom controls were hidden, and the visual pin verified. Selecting Airport Landing Ricochet opened cockpit mode, displayed the harbour helm and hid R6 controls. This fixture did not run a physics clock or forward controls to the live game.
- Browser pixel capture was unavailable, and a later browser click timed out. A final visual check of the Ricochet eye position and the second boat in the owner's cockpit remains outstanding. Headless tests cover rotated/translated camera poses, invalid telemetry, switching panel focus and rejecting changed visual bytes.

The live Phantom sortie and its evidence were not restarted, paused, replaced or refreshed during this work. The primary checkout and the prior isolated worktree retain their original uncommitted changes.

## Outstanding work

The conversational AI pilot's voice handoff latency and the browser speech-recognition network error are unresolved. This update adds no flight script, automatic pilot or navigation-map access. The AI pilot continues to require live instrument observations and individual control commands. Cloud persistence and full flight acceptance of development aircraft remain separate work.
