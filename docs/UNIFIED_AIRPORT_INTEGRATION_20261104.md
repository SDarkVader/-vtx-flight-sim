# Unified airport integration — 4 November 2026

This branch adds one airport traffic layer to the existing VTX scene. It does not replace Colin's MuJoCo plant or pilot authority. The static preview uses the bundled terrain when `/api/world` is unavailable; physical missions require the live Python backend.

## Aircraft and routes

- Nine aircraft and four service vehicles share the scene clock, registry, camera target, and terrain coordinates. Density is adjustable; mobile defaults to six visible actors.
- The primary A10 is Blendstra version `81c823e2-71aa-4da1-b924-1c1cb030664f`. Its GLB retains transparent inspection glazing, 28 clips and the 28 named control joints. The joint extras were restored from the matching authored A10 and their axes converted from Blender Z-up to glTF Y-up.
- The Argon R6 traffic model is the repository's `p0-v4-r6.blend` / `airframe-r6.glb` assembly (revision `P0-V4A-assembly-r6`), not a substitute lightweight mesh. Its visual pivot uses the Argon 10 kg calibration CG `(-0.0003, 0.0792, 1.4097) m`. Its four rotor groups animate during scripted operations. The physical mission form defaults to Argon R6 at `(0, 0)`.
- All seven defined flight procedures are assigned to flights. Traffic uses open runways 08/26 and 03/21, with 18/36 closed. The 03/21 visual strip follows the same physical heightfield as the route sampler. Operations stay within the ±500 m physical world and reserve runway occupancy with a wake gap. The current schedule reaches four simultaneous airborne aircraft.
- The A10 visual rig opens the hatches, extends and locks the wings, moves canards, flaps and ailerons, turns the wheel pods toward the ground after takeoff, restores them for landing, and retracts the wing mechanism after arrival. Amber wheel and nozzle glow is render only.

## Verification

- Node regression tests check fleet size, route assignments, GLB contents, staged joints, wheel and canard motion, deterministic sampling, full cycle swept clearance and runway reservations.
- The existing Python suite passed: 219 tests. The physical equations and pilot command files were not modified.
- Local browser inspection confirmed the A10 loads with 28 active joints and a moving wing slide, Argon R6 is selectable and rendered, the compact mobile controls, and trajectory based speed and clearance values. The preview should be checked again after deployment.

## Physical limits

Scripted traffic is kinematic and has no collision response. The live physical aircraft has authority over its own actuators; traffic is held while a physical flight is active. Latest A10 geometry has no validated corresponding mass, aerodynamics or actuator model, so the physical mission form continues to use explicit older experimental variants. Argon R6 calibration is conditional; the documented yaw/world-to-body cross coupling during translation remains unresolved. A static Vercel preview cannot run the persistent MuJoCo backend; use the local live server for physical sorties.
