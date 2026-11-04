# Phantom A10 — visual pass (render only)

![A10 visual pass](img/a10-visual-pass.jpg)

**What this is:** a render-only refinement of the A10 CAD export. Physics, the mass ledger, colliders, joint
definitions and `provenance.render_asset` are unchanged. The browser loads the refined sibling GLB instead of
the raw export; `?cad=1` loads the raw CAD GLB.

| File | Role |
|---|---|
| `tools/phantom/refine_phantom_visual.py` | shell smoothing, finishes, wing-bay window, wing-cassette cowls, alloy wheels |
| `tools/phantom/phantom_livery.py` | Vader's Taxis artwork, door swoops, LED lamps, rivets, amber-strip snapping (called by the script above) |
| `engineering/phantom/drs_flap.py` | DRS/airbrake geometry (single source) + road pitch-balance analysis -> `evidence/phantom/drs_balance.json` |
| `public/vtx-env/phantom-look.js` | runtime: drives joints and the visual-pass systems from the plant state |
| `public/assets/phantom-a10-visual.glb` | live sim asset (from `public/assets/phantom-a10.glb`) |
| `assets/derived/phantom-a10-cassette-visual.glb` | animated preview (from the cassette GLB; all 28 animations kept) |

Regenerate after any CAD re-export:

```
python tools/phantom/refine_phantom_visual.py public/assets/phantom-a10.glb public/assets/phantom-a10-visual.glb
python tools/phantom/refine_phantom_visual.py assets/derived/phantom-a10-cassette.glb assets/derived/phantom-a10-cassette-visual.glb
```

Needs `numpy pygltflib trimesh scipy pillow`. No Blender required.

## What changes

- **Smooth shell.** Crease-aware Phong tessellation of the exterior shell. Every original CAD vertex stays
  exactly where it was; only the new in-between vertices are lifted onto the smooth surface, at most 35 mm.
  Edges with a dihedral angle above 58° stay sharp.
- **Wing-cassette cowls.** One continuous body-side profile. It starts tangent to the roof, rolls over a
  shoulder into a near-vertical reveal panel that carries the wing slot, then tucks into the fender. Each end
  blends back into the haunch with a swept leading edge. The slot stays open, with a short tunnel back to the
  real mouth flange so the wing still deploys through it.
- **Wing-bay window.** A compact rounded window (about 0.58 × 1.12 m) is cut into the deck over both ball screws.
  The deck faces are clipped exactly to the window outline. The bay lid underneath is removed and the sleeve top
  plate is rendered as glazing. The window has a low-crown translucent panel, a slim Ti frame, an amber LED edge
  and two service lights. The lights are switched off on the `low` (phone) quality tier.
- **Finishes.** Clearcoat gunmetal and carbon, gold-amber light lines (emissive), smoked canopy, brushed Ti.
- **Livery.** Original angular V emblem: flat on each fin's outboard plane, ray-projected onto the bonnet.
  A slanted VADER'S TAXIS wordmark sits at the top of each door. Two curved amber swoops are ray-projected point
  by point onto each door and kept below the door's Z-line so they never cross a body line. The car also has a red
  LED tail chevron, white LED headlight blades, and about 4,400 dark dome rivets along the panel creases.
- **Wheels.** Forged-alloy faces with a V-T-X monogram spoke pattern (T crossbar, V arms, centre stem,
  X diagonals) and a centre cap. The lip ring is polished alloy instead of amber, and a mild red ember glow sits
  behind the spokes.

Every added node carries the extras `visual_only: true` and `mass_kg: 0`. The original node order, names, poses
and extras are preserved, so `phantom-look.js` drives the same joints.

- **DRS / airbrake flap (render-only articulation).** A split inverted NACA 4412 blade in 2×2 twill carbon, spanning
  between the fins with 0.24 m chord and 0.219 m² of blade. Its rest incidence is 6° trailing edge up. Both halves sit
  on one hinge axis, joined and driven by a central coaxial Ti rotary EMA on a carbon aerofoil pylon. It has Ti root
  and tip ribs, flanged Ti fin bearings, a Gurney lip and a red LED brake strip. Airbrake travel is +55°.
- **Rear boosters: conical vectoring cowl (render-only articulation).** Twelve overlapping Ti petals with ceramic inner
  faces, each hinged at its root on a tangential axis, plus a Ti sync ring and four actuators. All petals inward gives
  partial closing; deflection as cos(θ − θᵥ) tilts the cone (directional).
- **Tail lamps.** Compact swept units on the flat rear panel only: gloss-black bevelled bezel, recessed lens with
  LED-segment texture.

## Runtime (all finite-rate, driven by the plant state)

| System | Driven by |
|---|---|
| booster liner colour, blue plume and light | `boosters[j].thrust_n / phantom.booster_thrust_max_n`: a shallow indigo glow at low boost, rising to a radiant cyan-blue jet |
| cone petals | closed (10°) at idle, open (−4°) at full boost, 60°/s; tilted by `phantom.booster_vector_deg` (plant p3 angle) |
| DRS airbrake | brake command > 0.3 above 12 m/s ground speed, 140°/s |
| brake lamps (tail lenses, DRS strip) | brake command |
| wheel-hub ember glow | `phantom.fan_rpm / phantom.fan_rpm_max` per pod (CAD L/R mirroring resolved through the pod joints) |

`plant.physical_snapshot()` gained three render-only keys (`booster_thrust_max_n`, `booster_vector_deg`,
`fan_rpm_max`). Physics is unchanged.

An end-to-end check against the live server confirmed every system. Parked: plume off, petals closed, brake lamps
bright. Full boost: 1,289 of 2,418 N, plume on, petals opening. Braking at 19.6 m/s: DRS at 55°, lamps bright.

## Road pitch balance (drs_flap.py, plant aero + hull Munk moment)

All forces scale with q, so the canard trim angle does not depend on speed. These are values at 200 mph:

| Case | ΔN front | ΔN rear |
|---|---|---|
| level, no devices (drag couple only; the plant has no body lift) | −674 N | +674 N |
| + DRS flap at rest (830 N downforce) | −823 N | +1,655 N |
| + canards −5.4° (front unloading cancelled) | 0 | +1,598 N |
| + canards −9.6° (aero split = static split; constant attitude) | +593 N | +1,568 N |
| as-drawn 2.9° nose-up stance (Munk ×0.85), no devices | −1,757 N | +1,202 N |

The rear flap alone *raises* the nose. Front downforce from the canards is what stops it. With the as-drawn stance, the
static-share trim is unreachable before the canards stall. The airbrake adds 1.29 kN of drag at 200 mph (0.069 g) and
offsets about 15% of 1 g brake dive. Its hinge moment is 56 N·m.

## Known limits

- Below the front of each cowl, the original CAD haunch nose still shows as a small sharp edge. Removing it needs
  a hull edit in the CAD source (`build_a10_cassette.py`), not a render pass.
- With the wings stowed, the window mostly shows the stowed wing panels, which fill the panel level. The screws and
  rails show fully once the wings deploy.
- The size of `phantom-a10-visual.glb` is about 11 MB, against 2.8 MB for the raw export.
- The DRS and the booster cowls are articulated in the render only. Their forces are not in the MuJoCo plant.
- The live map has no boundary: a sustained road run leaves the 1 km world and falls off it.
