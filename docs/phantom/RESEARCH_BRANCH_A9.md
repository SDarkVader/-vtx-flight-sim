# Research branch: Phantom A9 wing cassette

Branch `research/phantom-a9-cassette` = `main` plus the files `main` leaves out: the A8 source, the A9 model and the render evidence. SHA-256 pins are in `assets/derived/phantom-a9-SHA256.txt`.

| Item | Path |
| --- | --- |
| A8 source (unchanged, read-only) | `assets/source/phantom-a8/phantom-a8.blend` |
| A9 model (Blender 5.2.3) and glTF | `assets/derived/phantom-a9-cassette.blend`, `.glb` |
| Stills and motion video | `evidence/phantom/media/` |
| Build, sweep, handover tools | `tools/phantom/` |
| Loads and flutter screening | `engineering/phantom/wing_loads.py` |
| Sweep, handover, MuJoCo check | `evidence/phantom/a9_*` |
| Reports | `docs/phantom/A9_WING_CASSETTE_REVISION.md`, `A9_MUJOCO_HANDOVER.md` |

## Reproduce

```bash
blender -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend --python tools/phantom/build_a9_cassette.py -- assets/derived/phantom-a9-cassette.blend
blender -b --disable-autoexec assets/derived/phantom-a9-cassette.blend --python tools/phantom/sweep_clearance.py -- --step 3 --out evidence/phantom/a9_sweep.json
python tools/phantom/mujoco_articulation_check.py
python engineering/phantom/wing_loads.py
```

Check the flags against each script's header. A full sweep takes about 15 minutes. Blendstra runs Blender 4.5.3, so results from there need re-verification.

## Status
Kinematic and clearance results only: 0 moving collisions over 178 frames. Not validated: FEA, CFD, aeroelasticity, pitch balance, induction flow. Static residuals: the right canard root pod against the A8 nose panel, and the duct against the booster fairings.
