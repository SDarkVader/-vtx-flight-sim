# Running the live laboratory

From the repository root, Python 3.11 or later:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m uvicorn vtx.live_server:app --host 0.0.0.0 --port 8765
```

Open `http://localhost:8765`. Click Set A / Set B on the map or enter arbitrary
east/north coordinates in metres. Roofs, terrain, footprint and immediate
vertical approach are validated. Route clearance remains the pilot's job.
Begin a sortie, then use engine, collective and independent X/Y tilt controls.
Manual takeover uses exactly the same action interface as Colin. Every attempt
is retained. Pause is an explicit operator action, recorded as such.

Physics advances independently at 400 Hz, aero updates at 100 Hz and sensor
observations at 20 Hz. The displayed clock scale is actual simulated seconds per
wall second. Agent mode uses a slower clock to accommodate reasoning latency;
physics continues while the agent thinks. There is no action-driven stepping.
Commands incur 20 ms simulated transport. Five simulated seconds without a
command feathers collective and shuts the engine down (spool to 0; `engine=0` is not a ground idle); it does not rescue flight.

`GET /api/observe` is the only instrument interface for piloting. It provides
quantized/noisy GNSS, barometric and radar height, IMU attitude/rates, shaft
RPM/torque, pitch/tilt/gear/fuel transducers and warning lamps. Sensor integration
is provisional. It does not disclose forces, CG, inertia, contacts, future
states or solver variables. `POST /api/action` accepts engine, four collectives,
four two-axis tilts and cabin gimbal commands; a Colin action must cite an actual
observation and give its decision reason. There is no pose or velocity command.

```sh
python tools/pilot_client.py observe
python tools/pilot_client.py action --observation ID --engine 1 \
  --collective 10,10,10,10 --tilt '0,0;0,0;0,0;0,0' \
  --reason 'A deliberate decision from the observation just inspected'
```

The client issues one action and exits. It contains no flight policy, route
tracking, time schedule or replay mechanism. Colin's explicit observations,
decisions and retained lessons are the learned state. Local EMA position servos
operate measured/proposed mechanical anchors; a shaft-speed governor supplies
torque. Neither receives aircraft attitude, navigation or altitude targets.

`/api/view` and `/ws` supply renderer/forensic state, clearly separated from
instruments. They are not pilot sensors. Engineering and replay are post-flight
inspection. Playback changes rendered states only; it cannot apply controls to
the live plant. Landing requires departure from gear, destination proximity,
at least three compressed gear contacts, near-level attitude, speed <0.15 m/s
and two seconds settled. Merely reaching B never awards a landing.

Each run saves metadata, model XML, initial checkpoint, observation/decision/
control/physics events, energy and collisions, and a final outcome. The model
XML and ledger hashes identify the physical revision. Checkpoint lessons are
stored separately in `pilot/colin-memory.json`; no Stage 2 world is created.

# Mechanical scope and unresolved evidence

The original exact-version `.blend` and GLB remain immutable local source
artifacts. `tools/build_airframe.py` derives the current editable scene at
`assets/derived/p0-v4-live.blend`, live GLB and component ledger together.
Historical exact R1 code is retained at commit `288d53b`. The current builder
also exposes `-- --baseline`, `-- --r2`, `-- --r3` and `-- --r4` repair-stage modes; those
use the current interface specification and are not byte-identical historical
reproductions. R3 requires `r2_gear_area.json`, retained with the source evidence.
Source object IDs are retained. Browser batching preserves triangles and keeps
the ledger's part mapping. It does not change mechanics.

Full mass tensors come from exact surface triangle moments with uniform areal
density within each subsystem's allocation. This is a disclosed **distribution
hypothesis**, not measured material mass. Occupants are two 85 kg ellipsoid
ballasts at the source seats. Fuel occupies four fixed diagonal cylinders with
no slosh; mass and inertia are updated as fuel leaves with local velocity.
The retained R4 revision lowers the gimbal bearing stack by 0.28 m, separates
stationary rings from the blade plane, refits the load braces and assigns moving
EMA heads to their nacelles. The sampled triangle audit checks 6,912 blade/pose
configurations with no intersections; continuous elastic clearance is unverified.
It retains the original 843 kg reference and separately adds
the longer gear's material allowance. See `assembly_repairs.json` and both
preserved ground-fault records. Actual laminate, hardware and human inertias
remain unmeasured.

R5 is the default experimental lighter underside: 32 legacy P06 box-spar
components are retired while the newer primary triangulated frame remains.
Retained part masses and landing-gear hardware constants are unchanged. This
removes 32.7202 allocated kg; test mass is 1046.6689 kg. Select R4 to compare.
The exact removed IDs, Wolfram CG/inertia cross-check and unverified structural
consequences are in `evidence/EXPERIMENT_REPORT.md` and `underside_trade.json`.
Rebuild with Blender and `tools/build_airframe.py`; `-- --r4` builds the older
configuration. R5 requires the preserved R4 mass ledger as an input.

MuJoCo integrates a free airframe, independently articulated nacelles, rotor
spin, high-speed radial shafts, occupied two-axis cabin and six spring/damper
gear sliders. It accounts for variable inertias and the internal reaction of
motors, bearings and common-drive constraints. Aerodynamic rotor forces and
torques act externally. Gyroscopic torque is not added a second time.
Engine output is capped by reference torque, power and spool state; stored rotor
energy can supply transient aero power. Fuel energy, mechanical output, servo
power, transmission losses and aero absorption are recorded separately.

The source's drivetrain contains placeholder envelopes. The implemented common
ratio is an ideal kinematic gear constraint, not modeled gear teeth, flexible
CV joints, lubrication or a substantiated gear rating. High-speed radial shaft
inertias are geometry-derived under the allocation hypothesis. Unmodeled
engine-internal and vertical-shaft rotation, driveline flexibility and bearing
compliance remain blockers. The 1200 rpm option explicitly proposes changing
the overall reduction from 7.52:1 to 5.0133:1 at the same 6016 rpm input; it
does not assume the engine can overspeed. Tooth design/mass/rating are unverified.

Rotor radius/chord come from blade mesh sections. Axial BEMT uses an explicit
synthetic polar (2π lift slope, CLmax1.2, nominal 16° stall, CD0.012+0.02CL²),
zero twist and neutral duct gain. No efficiency is fitted to weight. Edgewise
flow, descending wake, rotor interactions, duct pressure and ground effect are
not qualified; out-of-model flow is flagged. Blade collective changes its
aerodynamic incidence and its displayed pose, not a prescribed thrust.

Collective pitch currently uses a rate/lag-limited state rather than separate
mass-bearing blade-pitch joints. Pitch-dependent blade inertia, pitch bearing
torques and pitch-servo power are unresolved; recorded servo power covers
nacelle and cabin actuation. These are mechanical-model gaps, in addition to
missing calibration, and prevent a claim of a complete physical aircraft.

EMA anchors and torque/power/rate limits are proposed mechanisms, with tendon
forces acting through actual lever arms. Rod inertia is lumped into the source
body partition, not a full telescoping-rod mass model. The neutral cabin servo
does not implement resultant-acceleration coordination. Contact shapes are
explicit source-derived OBBs, open-ring capsules and swept rotor envelopes.
All-part self-contact and elastic deformation/laminate failure are not modeled.
Rigid world impacts persist; a rotor strike invalidates that rotor's intact
aerodynamic contribution. This is not a material damage or injury prediction.

No component strength/rating, installed power, mass or rotor performance has
been qualified. These remain `CALIBRATION_BLOCKED`, even after tests pass or
a conditional model lifts off. The experiment can expose failures and compare
hypotheses; it cannot establish real VTX flightworthiness.

Current new-sortie defaults:10kg total fuel,300kW shaft ceiling and1200rpm proposed gearset. The bounded PI RPM regulator replaces steady P-only droop; it is not an attitude controller. See `evidence/PROPULSION_FUEL_REVISION.md` for exact assumptions, tests and the exhaust-lift calibration block. Fuel and power configuration are locked during a sortie.
