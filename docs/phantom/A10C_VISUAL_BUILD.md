# Phantom A10-C visual assembly — isolated derived build (13 November 2026)

## Scope

This is a **development visual** for `phantom-a10c`. Keep the canonical A10-B visual, its GLB and its pinned configuration unchanged. The primary changes are four P7 TJ150-class turbojets and two front takeoff-stance linear actuators. This work does **not** implement the optional larger stabilator, improve the tyre model, add rear-pod downlocks, or change flight physics.

The master is made **outside the tracked source model directory** in `assets/derived/phantom-a10c-parts.blend`. A copy of the editable master is saved in the private Blendstra project at:

https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=51012152-29f9-478c-8551-6cae271a850f

## Build

Run from the repository root, using Blender and Python:

```bash
blender --background --python tools/phantom/build_a10c_parts_blend.py
python tools/phantom/build_a10c_visual.py --replace-exhaust
```

Inputs:
- `public/assets/phantom-a10b-visual.glb`: canonical original B visual; **read-only**.
- `assets/derived/phantom-a10c-parts.glb`: independent GLB exported by the Blender script.
- `assets/derived/phantom-a10c-parts.blend`: editable master exported by the Blender script.

Output:
- `public/assets/phantom-a10c-visual.glb`: derived A10-C composite visual (no changes to B).

The parts can also be viewed/edited in Blendstra, where the editable source was saved. The GLB inside the independent local package is a geometry preview made with trimesh; rebuilding the repo's derived asset using the Blender script above makes its export match the native Blender master. Do not assume the preview and native source have pixel-perfect correspondence.

## Dimensions and placement

Coordinate frame: original A10-B GLB/metres, +X forward, +Z up, Y lateral. The base airframe root is preserved.

| Part | Modelled envelope / mounting location | Basis |
|---|---|---|
| Four TJ150-class turbine housings | 0.636 m length, 0.272 m maximum diameter, nominal 1.5 kN each | Manufacturer/reference envelope, **not production CAD** |
| Jet locations | x -1.972; y ±0.40; z 0.355/0.665 m, two vertically stacked per side | **Provisional packaging**, not established jet mounting hardpoints |
| Two nose-lift actuator packages | approx. 0.12 × 0.12 × 0.50 m; nominal force 10 kN, 0.20 m stroke | Physics ledger nominal box and takeoff overlay; outer geometry is schematic |
| Front actuator visual mount | x +1.54, y ±0.78, z +0.75 m | **Provisional inboard placement**, selected to avoid the front tyre envelope |
| Front actuator ledger CG | x +1.54, y ±1.00, z +0.75 m | `inputs/phantom_overlays/takeoff_stance_v1.json`; **not** the visual mount location |

The inboard actuator offset must **not** be silently adopted as a physically validated mass location. Actual bearings, frame mounts, spring-seat load path, crash travel, tyre/wing clearances and thermal shielding need a sectioned fit review. The static placement does not mean nose-lift is already wired into the cockpit animation: `A10C_JOINT_NOSE_LIFT_FL` and `A10C_JOINT_NOSE_LIFT_FR` expose visual slide-joint metadata only.

## Merge invariants

The GLB merge script does not re-export the B asset through Blender. It copies the original B binary buffer intact, appends the C-only mesh buffers and material indices, and attaches one independent C component root under the canonical `airframe` node. It preserves original node names, transforms, joint hierarchy and links. The optional `--replace-exhaust` flag removes mesh **references** from original EDF-exhaust visual nodes *in the derived C output only*; those node identities remain.

The local GLB structure test on the uploaded A10-B visual and preview C parts found:
- B: 419 nodes, 362 meshes.
- C-only preview parts: 60 additional nodes, 50 meshes.
- Derived C: 479 nodes, 412 meshes.
- Exactly four new TJ150 mount nodes and two new nose-lift slide-joint nodes.
- B file SHA-256 unchanged and original B binary geometry bytes present in the derived C.

These are **structural tests**, not flight, assembly fit, motion-clearance or aerodynamic validation. Viewer screenshots show exposed booster/mount region; assess at matched cameras before approving geometry.

## Known limitations

- No independent interference sweep through pod rotation, landing-gear travel, wing deployment, or takeoff-stance extension.
- No simulation-to-visual control wiring for the new front slide joints.
- Turbojet housings are approximate external envelopes, with no verified fasteners, access panels, fire bulkheads or thermal safety standoff.
- The B-derived overall visual may still contain legacy elements not removed by `--replace-exhaust`; verify in the GLB viewer.
- The editable native Blender master currently lives in Blendstra. The checked-in generator creates a local `.blend`; binary deliverables are kept outside tracked source until explicitly checked in.
- For source-of-truth flight characteristics, see `docs/phantom/A10C_FANS_OFF_TAKEOFF.md` and `inputs/phantom_overlays/takeoff_stance_v1.json`.

## Operational note

Do **not** wire `phantom-a10c-visual.glb` as the default A10-B selector asset. A10-B remains pinned; A10-C should have its own selector identity and asset mapping after geometry and runtime checks.
