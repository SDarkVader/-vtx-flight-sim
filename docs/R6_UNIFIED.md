# Argon R6: one aircraft for model, physics and display

Every R6 in the game is the aircraft that flew the **3 November 2026 A-to-B sortie**
(run `20261103T125202-92636c`, software commit `0684b1a`).

| Part | Pin | Where |
|---|---|---|
| Physics | variant `r6-argon-20261103` in world `r6-valley-20261103`; MuJoCo model.xml `d5b83de4…` (byte-identical to the flight record), MuJoCo 3.17.0, 400 Hz | `src/vtx/aircraft.py`, `src/vtx/r6_historical_valley.py` |
| Ledger | `787b032b…` | `evidence/source/airframe_ledger_r6.json` |
| Display, piloted R6 | `/assets/airframe-r6.glb` `d001ae20…` | `aircraft.py` `render_asset` |
| Display, scenic R6 traffic | the same `/assets/airframe-r6.glb` `d001ae20…` | `public/vtx-env/vehicle-registry.js` (`r6`) |

`python tools/visual_r6/r6_unified.py` checks every pin and fails if any one breaks.
`tests/visual_r6/test_r6_unified.py` runs the same check in the test suite.

## Retired R6 display

`/assets/airframe-r6-blendstra-rig.glb` (`7325d0b3…`) and its source `r6-blendstra-reference.glb` (`58ff9950…`, Blendstra project
`dde793df…`, 5 Nov) are P0-V4 geometry. Their drive spindles stop about 0.45 m short of the rotor hubs, and their landing legs
stop short of their pads. The files are kept for the record, but no R6 entry may show them.

## Evidence (24 Nov 2026)

- **Physics replay** (`tools/visual_r6/r6_physics_replay.py`). The A-to-B controller (`argon_flight_test.py` gains and trims) runs
  in-process at 50 Hz with a 20 ms delay: spool, climb to 10 m, hover, transit to B (-50, 20), then land.
  - The frozen `0684b1a` code and this branch's `r6-argon-20261103` give the **same state trajectory hash**
    (`bf5361ec…`) over 65,441 steps. Both land 1.474 m from B after 163.6 s.
  - The current-world `r6` variant stays within 0.8 mm and 0.0075° of that path.
- **Blender pose check** (`tools/visual_r6/r6_pose_export.py` + `blender_pose_r6.py`). The physics body poses are applied to the
  display's 20 body containers. At rest they match to 1.2e-7 m. With the ducts tilted 20° in x, in y and diagonally, the
  column, gimbal, hub and braces stay joined.
