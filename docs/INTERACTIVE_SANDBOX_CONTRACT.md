# Interactive 3D sandbox acceptance

A single coherent VTX-P0-V4 aircraft must be rendered from its true integrated 6-DOF physics state. Never replace flight dynamics with scripted trajectories, keyed animation or invisible attitude corrections. Show separate F1–F4 ducted fan thrust, tilt actuators, saturation and latency.

Implement a deterministic headless solver, quaternion rotation, rigid-body inertia, coupled force/moment integration, rotor gyroscopic/reaction moments, physical contact/collisions, power and aerodynamic terms with clearly stated synthetic assumptions and separate VTX calibration blockers. Use fixed timesteps, stable numerical integration and exact logged initial conditions.

Browser view: live 3D aircraft/map, camera, map-click A-to-B mission selection and all takeoff/flight/landing phases, telemetry, controls to fly/pause/abort/replay, failures and crash visualisation. Geometry and render pose shall agree with logged state.

Test deterministic nominal flights and physically meaningful failures (rotor asymmetry, loss of control authority, changing CG, actuator delays, gusts, sensor faults, collisions, infeasible landings); report precisely why each run succeeded or failed.

The actual P0-V4 performance remains CALIBRATION_BLOCKED without real mass/CG/inertia, rotor maps, airloads and actuator validation. Synthetic test results are not evidence of physical airworthiness. Keep source artwork separate from measured geometry.
