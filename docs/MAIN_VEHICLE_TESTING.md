# Main vehicle testing

Double-click `Test-VTX-Vehicles.bat` in this checkout. It opens this PR build at **http://127.0.0.1:8781/** and uses **%LOCALAPPDATA%/VTX/vehicle-tests/pr61** for its own records. The existing game on 8770 and its save folder remain separate. The launcher verifies the reviewed runtime; if 8781 is occupied, it checks the running frontend against this checkout and refuses a different version. `--check` validates the installation without starting a server; `--no-browser` is available for startup checks.

Choose vehicles explicitly; no flight or aircraft is selected automatically. Save or end the current aircraft flight before changing its physical variant. Boats continue independently of that aircraft. Earlier and experimental revisions stay in their separate group.

| Main vehicle | Select | Visibility and controls | Manual acceptance to record |
| --- | --- | --- | --- |
| Phantom A10-C | Main Aircraft → Phantom A10-C | Physical Phantom panel; cockpit shows the live flight deck; forward, left and right sightlines clear; exterior restores on exit | Start at the west threshold; deploy wings/canards and inspect actual readbacks; controlled manual flight; save, restart this test server and restore paused |
| Argon R6 | Main Aircraft → Argon R6 | R6 rotor, collective and cabin controls; fixed eye/cabin position; nearby rotor housing cutaway in cockpit; original exterior on exit | Spool, collective/tilt response, takeoff/hover/landing; save and restore; verify the selected visual against the owner's reference |
| Ricochet at Airport Landing | Choose vehicle → Ricochet · Airport Landing | Single compact helm, clear reflective glass, night cabin/exterior lamps; left/right, chase and top views | Release mooring, use low throttle/rudder, return and dock; save harbour |
| Ricochet at Lantern Marina | Choose vehicle → Ricochet · Lantern Marina | Same cockpit/helm bound to the second boat's own pose and readings | Move and dock independently; switch boats and restart; both positions, controls and berth ownership must persist |

Before moving a vehicle, confirm its name, displayed controls and camera. The current visual asset must show its verified pin. Missing readings must display a dash, never a fabricated measurement. Observe display updates and stale warnings; the instruments do not supply commands or fly a route.

Check the Phantom's side views with the cockpit Look controls or mouse drag. Cockpit-only visibility treatments must return to the original appearance in chase/free view. Avionics and Ricochet lamp fixtures are presentation objects only; collision geometry, mass, forces, actuators and physics inputs remain unchanged. Verify that deployed wheel-fan exhaust points toward the ground and VTX artwork stays against the skin as the vehicle moves.

Verify the scale bar on both maps at several zoom levels, using buttons, mouse wheel and pinch where available. It must represent the same distance as the projected world coordinates and stop at the whole-world/100 m limits. Under Airport views, select traffic counts 0, 2, 5 and 10; check mixed aircraft and the additional passenger seats. This changes scenery only.

For every attempt, retain the run ID, selected vehicle, starting point, control inputs, visible result and saved-flight or harbour result. Scripted flights are not part of the game. This checklist is for manual acceptance; offline tests and Mathematics passing do not replace the owner's flight evaluation.
