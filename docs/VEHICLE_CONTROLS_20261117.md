# Vehicle selection, cameras and Windows launch — 17 November 2026

The development Argon R6 and Phantom A10-C are explicit choices in Main Aircraft and Choose vehicle. The inaccurate “visual match pending” text is removed. Existing R6 assets, physical variants, control channels and avionics are retained. Historical aircraft remain under the earlier/experimental group. An active aircraft flight must be saved or ended before changing its physical variant.

The right controls panel now follows the selected seat. Aircraft shows the physical aircraft's own controls; Ricochet shows its helm and harbour controls; scenic passenger seats show a passenger notice. Switching away clears pending aircraft panel input without sending a control command, stopping a flight or changing its authority. The Phantom voice command path and legacy keyboard input cannot operate the aircraft from the boat/passenger panel.

Selecting either Ricochet opens a cockpit camera. Its eye stays inside the canopy above the authored bucket seat. A single compact display sits below the water sightline, with sharp speed, heading, fuel and helm readings. The oversized source dashboard surround and source display panes are hidden only in the pilot view; original geometry and exterior visibility are retained. Clear reflective glass retains sun glare, while a cabin lamp and two exterior lamps provide real illumination at night without adding physical mass. The camera and instruments use the same interpolated airframe transform as the hull. Mouse look, chase and top views remain available.

The Phantom has a cabin-mounted rectangular flight display with a live attitude horizon, heading ribbon, speed/height tapes and system readouts. Its forward and side visibility treatments affect rendering only. Argon keeps its fixed eye and cabin, with a near-camera rotor-housing cutaway; blades remain articulated and exterior materials restore on exit. Housing meshes remain separate from render batching so the cutaway remains reversible. VTX flank lettering is parented to its render body and fitted against the existing skin. Wheel exhaust now opposes the physical fan force axis, including when the pods deploy downward for lift.

Both maps draw a scale bar from their projection and support bounded button, mouse-wheel and pinch zoom. Airport views offers 0–10 scheduled scenery actors, mixing Argons and Phantoms, with passenger seats for all ten. The additional traffic reserves apron movement and uses routes checked for obstacle and fleet clearance. No scenery or map data enters the AI pilot's instrument packets.

Current physical and scenic aircraft assets have explicit SHA-256 render pins. Pinned bytes are verified before GLTF parsing; a mismatch reports an unavailable visual instead of displaying a substitute. This is visual identity verification, not a change to physics configuration, aircraft acceptance or promotion. Ricochet rendering retains the existing physics-derived geometry identity checks.

The Windows launcher preserves a frontend-incompatible idle selection in the existing recovery archive. An occupied port must match the airport/harbour runtime and every frontend text file before it is identified as this build. Launcher-served static files use cache revalidation, including conditional responses; this wrapper does not alter API responses or the Python runtime fingerprint. A browser with an older document already open still needs a deliberate reload after an approved update.

## Verification

- Full local Python mathematics/regression suite: **519 passed** with an isolated data root and test-output directory.
- Final JavaScript suite: **84 passed**, including actual-GLB visibility/lettering, physical fan-axis comparisons, traffic clearance and map scale/zoom checks.
- Runtime review guard passed with the same recursive Python fingerprint as main; `src/vtx` and physics inputs are unchanged.
- Offline browser pixel checks completed for both Ricochets, including distinct headings, one compact screen, clear water view and night lighting. Phantom front/side views and the sharp flight deck were checked; Argon retained its cabin eye and showed the rotor cutaway and its own controls. Both map sizes showed the scale bar; zoom and the 0–10 traffic choice were exercised. The frozen fixture could not actuate the live simulator.
- `Test-VTX-Vehicles.bat` passed installation validation, actual startup on 8781, and occupied-port frontend identification. In its isolated save folder, two real boats were initialized, saved and restored; a server restart retained exact positions, held commands, fuel, selected boat and berth ownership. Save before closing: Windows Ctrl+C can interrupt the marine child process before the final shutdown snapshot, even though the explicit save/restart test passed. The launcher never replaces an occupied different build.

The live Phantom sortie and its evidence were not restarted, paused, replaced or refreshed during this work. The primary checkout and the prior isolated worktree retain their original uncommitted changes.

## Outstanding work

The conversational AI pilot's voice handoff latency and browser speech-recognition network error are unresolved. The original live data root also reported a Windows access error replacing its harbour snapshot; the isolated launch/save/restart checks did not reproduce it and this PR does not claim to repair that old session. This update adds no pilot flight script or navigation-map access. Cloud persistence and full manual flight acceptance remain separate work.
