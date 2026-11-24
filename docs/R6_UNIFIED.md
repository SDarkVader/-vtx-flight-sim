# Argon R6: one aircraft for model, physics and display

Every R6 in the game flies the physics of the **3 November 2026 A-to-B sortie** (run `20261103T125202-92636c`,
commit `0684b1a`) and shows the **owner-confirmed connected assembly**.

| Part | Pin | Where |
|---|---|---|
| Physics | Variant `r6-argon-20261103` in world `r6-valley-20261103`. MuJoCo model.xml `d5b83de4…` is byte-identical to the flight record (MuJoCo 3.17.0, 400 Hz). | `src/vtx/aircraft.py`, `src/vtx/r6_historical_valley.py` |
| Ledger | `787b032b…` | `evidence/source/airframe_ledger_r6.json` |
| Flight-record render name | `/assets/airframe-r6.glb`. Kept in the physics provenance so the flight's identity is unchanged. | `aircraft.py` `render_asset` |
| Display, piloted R6 | `/assets/airframe-r6-blendstra-rig.glb` `7325d0b3…` | `public/app.js` `R6_DISPLAY`, an explicit and pinned map from the record name |
| Display, scenic R6 traffic | the same rig `7325d0b3…` | `public/vtx-env/vehicle-registry.js` (`r6`) |
| Connected reference | `assets/reference/r6-blendstra-reference.glb` `58ff9950…`, Blendstra project `dde793df…`, version `version_c94fd5e0…` | the rig matches it at rest for all 691 meshes |

The rig's 20 body containers sit on the physics body frames (worst 5.7e-8 m, 0°). `python tools/visual_r6/r6_unified.py`
checks every row of the table above, and `tests/visual_r6/test_r6_unified.py` runs it.

## Not the R6 display

`/assets/airframe-r6.glb` (`d001ae20…`) is a disconnected assembly: a thin rod ends in mid-air, and an actuator and a cable end
float free near each duct. The owner reported it as disconnected in live play and in Blender. The file is kept because the flight
record names it, but it is never displayed.

## Evidence (24 Nov 2026)

- **Physics replay** (`tools/visual_r6/r6_physics_replay.py`). The A-to-B controller runs in-process at 50 Hz with a 20 ms delay:
  climb to 10 m, hover, transit to B (-50, 20), then land.
  - Frozen `0684b1a` and `r6-argon-20261103` give the same state-trajectory hash `bf5361ec…` over 65,441 steps.
    Both land 1.474 m from B after 163.6 s.
  - The current-world `r6` stays within 0.8 mm and 0.0075° of that path.
- **Blender pose check** (`tools/visual_r6/r6_pose_export.py` + `blender_pose_r6.py`). Physics body poses are applied to the rig.
  At rest they match to 1.2e-7 m. With the ducts tilted 20° (x, y and diagonal), the ducts stay on their braces and mounts.
