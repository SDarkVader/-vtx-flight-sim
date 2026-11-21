# Ricochet in the harbour

Source: `src/vtx/harbour_fleet.py`, `src/vtx/harbour_session.py`, `src/vtx/harbour_water.py` and `src/vtx/harbour_trial.py`.

## The fleet

| Boat | Name | Variant | Home berth |
| --- | --- | --- | --- |
| `ricochet-airport` | Ricochet · Airport Landing | `ricochet-concept-a` | `airport-landing-ricochet` |
| `ricochet-marina` | Ricochet · Lantern Marina | `ricochet-concept-a` | `lantern-marina-ricochet` |

A fleet holds one to four boats, each with a unique id, an explicit variant and a compatible berth. Only `ricochet-concept-a` (hull `concept_a`) and `ricochet-rc01-f03` (hull `f03_baseline`) are accepted, and no variant is ever substituted. Both boats use load case LC-01 and share one MuJoCo scene, so they can collide with each other and with the harbour scenery. Aircraft are not coupled to the boats by collision.

The fleet runs in its own worker process. Only that process changes the fleet, and commands and snapshots are handled between solver steps.

## Solver cadence

| Part | Rate | Notes |
| --- | --- | --- |
| Rigid bodies (MuJoCo) | 100 Hz (Δt 0.01 s) | The fleet recompiles each craft at 100 Hz; the standalone plant stays at 400 Hz |
| Hull hydrodynamics | 20 Hz (every 5 steps) | Forces between samples extrapolated to the step midpoint |
| Shallow water | 10 Hz | Shared across the harbour basin; only changed cells are recomputed |

The fleet aims to hold 1× real time. Achieved rate is measured as harbour Δt_s over wall-clock Δt, and `physics.scheduler_backlog_s` in the status reports how far the worker is behind.

## Water environment

The harbour water starts with:

- still water at the harbour water level, with no wind or current;
- vessel wakes on and whirlpools off.

Water forces and the wake are covered in [Hydrodynamics and aerodynamics](HYDRO_AND_AERO.md).

## Mooring

A moored boat is held to its mooring point by a spring:

| | Stiffness | Damping | Limit |
| --- | --- | --- | --- |
| Position (horizontal) | 1,200 N/m | 1,400 N·s/m | ±2,500 N |
| Heading | 1,500 N·m/rad | 1,300 N·m·s/rad | ±1,800 N·m |

Throttle above 0.02 is refused while moored.

**Release** (`undock`) frees the berth and removes the spring.

**Mooring** (`dock`) succeeds only when all of these hold:

- the berth exists, is compatible with the variant, and is free or already reserved by this boat;
- the boat is not already moored;
- the boat is within 2 m of the berth centre;
- horizontal speed is below 0.5 m/s;
- heading is within 15° of the berth approach heading;
- throttle is at or below 0.02.

Each refusal returns a plain reason, such as "Slow below 0.5 m/s before mooring".

## Restart and staging

`restart` respawns the selected boat. The fleet and the water keep their clock, and the other boat keeps its wake.

| Option | Where the boat starts |
| --- | --- |
| None | Its home berth, moored, if the berth is free |
| `position: [x, y]` | Open water at those world coordinates, keeping its current heading; refused on land |
| `timeTrial: true` | At the harbour time-trial start, at the trial heading |
| `raceId` | At a Lantern Race start (Vaderland 33) |

A restart is refused if the boat would overlap scenery at the chosen position. The fleet state before a restart is saved under `harbour-history/`.

## Flags and crashes

| Flag | Raised when |
| --- | --- |
| `IMPACT` | Any contact touching the boat exceeds 100,000 N. The boat is then marked `crashed` and an `impact` event is logged. |
| `FUEL_EXHAUSTED` | The fuel reserve reaches zero. Servos and fans go passive. |
| `HULL_BREACHED` | The hull seal is disabled (standalone plant); flooding begins |
| `SERVO_SATURATED` | A surface servo reaches 98% of its force limit (standalone plant) |

`max_impact_n` keeps the largest contact force seen. The physics continues after an impact; there is no automatic rescue.

## Telemetry

`GET /api/harbour` returns the schema `vtx-harbour-fleet-public-v1`.

**Per boat:**
- id, name, variant;
- position, heading and horizontal speed;
- the accepted command (not the achieved deflection);
- the berth it is moored at;
- world pose of every body (airframe, cabin, sponsons, rotors, surfaces and buckets);
- hull variant, hull geometry SHA-256 and model XML SHA-256;
- `crashed`, flags and fuel.

**Fleet-wide:**
- berths with world position, heading and occupancy;
- the last 16 events, structures and water level;
- a physics block: rates, `dynamics_id`, water grid identity and `scheduler_backlog_s`;
- water surface patches near the boats, for drawing.

The standalone plant's `physical_snapshot()` adds more:
- commanded, target and achieved surface angles;
- per-fan rpm, torque, thrust and shaft power;
- the hydrodynamic breakdown by term and by body;
- sponson attachment loads;
- structural deflection and margin estimates;
- mass properties and energy state.

## Checkpoints

The worker publishes the fleet to `airport-harbour-current.json.gz` atomically every 2 s and after every ownership change. The saved state includes the shallow-water arrays (float64, base64).

A checkpoint restores only when the world, model, cadence and dependency fingerprints match. A checkpoint from a known exact-equivalent earlier dependency set is accepted as well: `PREVIOUS_`, `SINGLE_PASS_`, `ARRAY_CAPTURE_` and `SAMPLE_REUSE_FLEET_DEPENDENCIES` in `harbour_session.py`.

## Performance notes

Measured offline on one underway Ricochet run with two boats:

- **Before the sparse water kernel:** shallow-water steps took about 50 ms and harbour steps about 12.5 ms.
- **After:** about 15 ms and 8.8 ms.
- **Remaining cost:** hull hydrodynamics, mainly the 3,138-vertex hull water queries.

Absolute times depend on the machine; these figures are from the development container, not the reference PC.
