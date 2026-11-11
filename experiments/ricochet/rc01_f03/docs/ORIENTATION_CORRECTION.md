# RC01 F03 visual orientation correction (2026-11-11)

**Supersedes the original F03 animation only. Physics and telemetry files remain unchanged.**

## Root cause
In `ricochet_water_solver.py`, yaw is integrated in world coordinates and initialized at `pi/2` radians so body +X points along the lake +Y axis. The CSV exports `yaw_deg = degrees(world_yaw - pi/2)` as a **relative** heading. The original `render_animation.py` treated this relative yaw as absolute yaw when rotating the aircraft mesh, omitting the +90° offset. Thus the old image depicts sideways motion.

## Fix
The visualization now applies yaw `yaw_deg + 90°` (world heading), while retaining the source frame roll, pitch, position, and hydrodynamic data. Added in-frame cyan body +X and green velocity vector arrows, plus heading and forward/side speed telemetry. This is a render-only correction and does not change physical trajectories, lake coordinates, force histories, mass assumptions, or claims of hydrodynamic validity.

## Verification
- 15.0 s: world Y velocity +2.8525 m/s, world X -0.0012 m/s. Relative yaw +0.03°, world heading 90.03°, hence body-forward velocity 2.8525 m/s, lateral approx zero.
- Late steering: body-forward and velocity vectors separate modestly as the hull rotates; this is now visible.
- Numerical model: reduced-order low-speed buoyancy and drag only; no joint deformation simulation, planing pressure, water turbulence, CFD or full VTX MuJoCo run.

**Original animation: INVALID as visual proof of motion orientation.** The numerical trajectory remains separately checkable.

## Reproducibility
Inputs: `RC01_F03_nominal_timeseries.csv`, `RC01_F03_results.json`; renderer: `render_animation_orientation_fix_v2.py`. Audit CSV: `RC01_F03_body_velocity_orientation_audit.csv`.

SHA-256 source MP4: `9956972885a2de8a4bed6f3f7cf0bed53780628535a22bc96d7fa159ced4e18a`

SHA-256 corrected MP4: `e8a27b636a0f11eaab2c1c1d37d38862fe1be270f0390cbbd2dd0923546b3f9d`
