# RC-01 game-environment integration gates (development branch only)

**Canonical existing code remains unchanged.** This branch adds an isolated candidate and a fail-closed import contract, not water simulation inside the game.

## 0. Canonical source check
- GitHub base `b9cdbe8f9898d77169e720ad564848c0de5b08e8` (2026-11-10), `main` at branch creation.
- VTX source: `src/vtx/world.py` and `src/vtx/atmosphere.py`, geometry and world gravity conventions.
- F03 model: exact pinned Blendstra source version, separately tracked from GitHub main. Model builder script in `model/`.

## 1. Define physically valid water fixture
- Keep existing airport lake centre (−265,+30), nominal 56×160m reference; preserve airport scenery/obstacles outside fixture.
- Add actual bathymetry and collision/surface support. F03 `bottom_z=-3m` is a hypothetical isolated value and **must not** be assumed present in VTX terrain.
- Share exact water surface/bed geometry between renderer, collision, validator and hydrodynamic solver. Explicit depth/edge transitions; fail on unsupported dry/shore intersections.
- Standard gravity 9.80665m/s²; ISA 288.15K/101325Pa at sea level, freshwater density 999.1kg/m³ at 15°C, zero wind and waves baseline.

## 2. Separate model variant
- Add selectable `ricochet-rc01-dev` behind an explicit development-only flag. Never replace existing R6/Phantom selection.
- Build whole rigid-body/multibody mass ledger and moment arms from actual geometry. Rotor axes and physical joints must be mapped, articulated and collision/sweep checked.
- Convert F03 +Y-starboard design labels to existing VTX +Y-left body basis. **Polar vectors** `(x,y,z)->(x,-y,z)`; **axial vectors** `(x,y,z)->(-x,y,-z)`; inertia `I'=S I S^T`. This is a *basis reflection*, not an ordinary quaternion rotation. Validate body-vs-world axes and momentum signs before simulation.
- F03 animation's CSV `yaw_deg` was *relative to +90° initial lake heading*, not absolute. Do not repeat the renderer bug.

## 3. Water force model
- Map submerged sample/mesh elements to current MuJoCo body poses, calculate fluid reactions and apply at actual contact/centre-of-pressure locations via the engine's force interface, logging equal/external forces. Avoid double-counting added mass or existing vehicle weight.
- Keep Munk-like destabilizing yaw/pitch effects explicitly separate from gravity, CG changes and fluid added-mass state; calibrate derivatives with independent reference or experiments. F03 coefficients are **not** accepted calibration.
- Include hydrodynamic pressure, drag and planing transition at higher Froude numbers before high-speed tests. Slamming, waves, spray and porpoising remain future work.

## 4. Verification tests (must pass before enabling in gameplay)

1. zero-thrust gravity, float equilibrium and minimum displacement across 750/900/1050kg;
2. hydrostatic restoring force/torque vs ±5° roll/pitch; both floats active, absent, asymmetric;
3. diagonal mass movement, fuel draw, control surface travel, rotor gyros, true full inertia, and joint hard-stop collision;
4. forward thrust maps to *nose direction* independent of world heading, yaw torque sign verified from actual fan lever arms;
5. time-step convergence, energy and momentum residual logging, geometry watertightness and collision overlap check;
6. lake edge, water depth, shore transition, aircraft-select isolation, persistence, telemetry export, recovery to F03 pinned state;
7. differential thrust manoeuvres and pitch–heave/porpoising cases, then launch tests only after physical lift and shaft power models are justified.

`physics/vtx_runtime_contract.py` intentionally rejects running against visual-only lake metadata. CI should keep it that way until a vetted `water_physics_revision` plus bathymetry exists.

## 5. Branch merging policy

Keep this package on the development branch; do not merge directly. Use a draft pull request, compare source hashes, require independent flight/physics test review and owner decision for live runtime changes. Tests in this branch are evidence only for the isolated fixture and conversion logic.
