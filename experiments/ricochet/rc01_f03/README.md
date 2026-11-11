# VTX Ricochet RC-01 — F03 isolated hydro-model development checkpoint

**Status:** isolated **development branch**, not merged; not a new aircraft available in the live game.  
**Date:** 2026-11-11. **Main branch base:** `b9cdbe8f9898d77169e720ad564848c0de5b08e8`.  
**Authoritative editable model:** [Blendstra RC-01 F03 exact version](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=5e68818b-0922-4239-8a57-c35d7e72ec68&version=version_c5b32f472bc4616bc00025706062fff2ab7a8e9ac5890c07fa8f4c1b2b7c1d8f).  
**Full recovery evidence / corrected MP4:** [Google Drive F03 checkpoint](https://drive.google.com/drive/folders/19Muw51jKaPYrsbp8GSraPO8xeKzIP6Xt).

## Contents

- `model/blendstra_rebuild.py` — exact editable F01→F02→F03 construction script from the saved model revision (all assemblies, bulkhead web panels, keep-outs, hull loft and two float candidates). Use in Blender with its original scripting dependencies; **not a native `.blend` export**.
- `model/RC01_F03_closed_hull_reference.glb` — measured *hull reference geometry only* (48 vertices / 92 triangular faces), not the full model or collision-ready aircraft. Full original assembly stays pinned on Blendstra.
- `model/RC01_F03_cad_stations.npz` — six station geometry data.
- `physics/ricochet_water_solver.py` — deterministic reduced-order exploratory 6-DOF hydrostatics/drag/thrust probe. **Not CFD, planing dynamics, joint FEA, or the MuJoCo runtime.**
- `physics/vtx_runtime_contract.py` — fail-closed model/world frame conversion and future lake integration contract. Does not inject forces into game.
- `tests/test_vtx_runtime_contract.py` — six regression tests, including frame parity and original animation orientation correction.
- `render/` — corrected renderer and visualization driver. The *original* animation incorrectly omitted 90° from world heading; its visual evidence is superseded.
- `data/` — raw 24 s time series, results, CG/mass sensitivity, timestep comparison and corrected heading audit.
- `docs/` — canonical state, development workflow, integration gates and evidence limitations.

## Current isolated baseline

| Quantity | F03 exploratory result / assumption |
|---|---|
| Design mass | 900 kg (not weighed) |
| Hull outer envelope | 6.80 m overall length, 1.60 m max hull beam, 9.60 m wing span |
| Geometrically closed loft | 4.807485 m³ (not leak-tested construction volume) |
| Calm freshwater | 999.1 kg/m³, 15°C, 101325 Pa, g=9.80665 m/s² |
| Reference lake | centre X−265 m Y+30 m, 56×160 m; assumed virtual bottom −3 m |
| F03 displacement trial | 900 kg, 24 s, 50.676 m along lake axis, peak 2.853 m/s |
| Numerical sensitivity | 0.02→0.01 s: 0.00808 m final distance difference |
| Dynamic / mechanical | no physically qualified joints, no slamming, no measured fan map or planing lift |

The test does **not** demonstrate water takeoff, high-speed performance, verified joint reactions or physical support in `world.py`.

## Reproduce isolated tests

From repository root, with Python 3.11+, `numpy`, `scipy`, `trimesh`:

```bash
python -m unittest discover -v -s experiments/ricochet/rc01_f03/tests
python experiments/ricochet/rc01_f03/physics/ricochet_water_solver.py --help
```

The raw recorded data and solver source are included. Re-run the solver using the saved parameter/configuration options and compare the generated CSV/JSON to this checkpoint rather than silently retuning coefficients. For animation renderer dependencies, see `render/render_animation_orientation_fix_v2.py` (`opencv-python`, `ffmpeg`, `numpy`, `scipy`).

## Before real-environment trials

The live `src/vtx/world.py` visual water does not have the required physical bathymetry or buoyancy model; `world.validate` currently rejects its water. The new `vtx_runtime_contract.py` explicitly refuses to treat it as integrated. Use this branch as a **staging area** for an opt-in model variant and lake fixture, not as a simulator patch. Full rules: [integration gates](docs/INTEGRATION_GATES.md) and [workflow](docs/DESIGN_WORKFLOW.md).

## Data provenance and recovery

- `docs/CANONICAL_STATE.json` captures the exact repo base, Blendstra model revision and F03 test identity.
- F01/F02 structural registers and the original four-page F03 engineering report are retained in the Drive recovery archive. Native Blendstra `.blend` source remains hosted by the pinned Blendstra project; **not** mirrored into this branch.
- No files under active `src/vtx/`, `public/`, `inputs/` or game runtime are altered in this branch.
