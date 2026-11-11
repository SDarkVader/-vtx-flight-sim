# Phantom in the VTX simulator (opt-in variants `phantom`, `phantom-fx`)

Status: TEST_PLAN Phases 0-1 plus the Phase 2 low-speed aero subset.

Every number is in `inputs/phantom_parameters_v1.json` as `{v, u, l, s}`. The label `l` must be one of:
- MEASURED-K
- DERIVED
- SYNTHETIC_UNVALIDATED
- MANUFACTURER
- REGULATORY_REFERENCE

Any other label is rejected. These are **not validated aircraft performance figures**. Nothing in the physics was tuned to make hover succeed.

## Variants

### `phantom`

The A10 as drawn (the A9 is kept as `phantom-a9` and `phantom-fx-a9` for comparison):
- 0.49 m fans inside 0.72 m wheels;
- 2 x 600 kW turbogenerators;
- CG taken from the ledger.

### `phantom-fx` (FX-A)

A feasibility **design proposal** from propulsion research section 9:
- 1.10 m fan-wheels with 0.90 m fans;
- figure of merit 0.90 with a 10 deg diffuser;
- one turbogenerator, 900 kW_e for 5 min and 600 kW_e continuous;
- 311 kg nose battery at x 1.80 m;
- avionics at x 1.70 m;
- 129 kg fuel at x -0.06 m;
- pods at y +/-1.25 m.

FX-C (one occupant, 60 kg fuel) is a selectable load state.

### Proposals carried in the parameter file

- The CG study's N2 battery (193 kg at x 1.24 m) and its 68 kg fuel bladder are recorded as non-active alternatives. The propulsion-sized FX-A ledger supersedes them.
- P3 (boosters vectored down) and P5 (1.5x canard with flap) are off by default, under `proposals.*`.

## What is modelled (`src/vtx/phantom/`)

### `params.py`
- Deep merge: base, then variant overlay, then overrides.
- Checks labels and manifest coverage; a failure raises `PhantomConfigError`.
- Produces a hashed parameter snapshot.
- A10 is a swap of `geometry_sources.wing_cassette_revision`.

### `ledger.py`
- Component build-up gives mass, CG and inertia per configuration.
- Fuel burns per tank.
- Ledger mass equals MuJoCo mass (tested).

### `plant.py`
The MuJoCo 3.17 model uses the CAD frame: X forward, +Y = physical left, Z up. It runs implicitfast at 400 Hz.

Joints:
- pod tilt (hinge with an electromechanical actuator), fan spin, wheel spin;
- leg screw slide with an oleo;
- A9 wing slides, lock pins, flaps, ailerons, canards and hatches;
- wing-lock equality constraint;
- booster rotors.

Other features:
- actuators are rate-limited and force-capped;
- brakes are modelled as joint friction loss;
- radar altimeter by ray cast;
- per-step CSV log;
- 20 s crash ring buffer.

Tyre contact fix: MuJoCo's negative `solref` is an acceleration gain, not a force stiffness. Passing the physical N/m directly made contacts explode. The tyre stiffness (N/m) and damping (N s/m) are now converted to a MuJoCo time constant and damping ratio for a quarter-mass corner.

### `propulsion.py`
Ducted-fan momentum theory:
- power P = T^1.5 / (FM * sqrt(2 * rho * A));
- tip-speed limit;
- thrust-coefficient lapse with advance ratio;
- descent inflow;
- ram drag;
- capped Cheeseman-Bennett ground effect.

### `energy_bus.py`
- Generators: spool lag, ramp limit, take-off rating timer, specific fuel consumption.
- Buffer battery: state of charge, continuous and peak power, peak credit, thermal limit.
- Load arbitration by priority; propulsion is derated when supply runs short, and unmet power is logged.
- Energy balance residual is logged.
- Discharge is clamped so the buffer never goes below `soc_min` within a step.

### `surface_aero.py`
Quasi-steady, per surface:
- local flow is v + w x r - wind;
- attached-flow coefficients blended into flat-plate post-stall;
- flap and aileron strips only act when the wing is locked;
- canards only act when deployed;
- fins;
- body drag area from the measured projected areas;
- no Munk moment.

### `controls.py`
`PhantomAction`, schema `phantom-fbw-1`: extra fields forbidden, every field bounded, no pose or force fields.

Stability modes:
- `off`;
- `rate_damping` (the default);
- `attitude`;
- `attitude_vs`: attitude hold plus vertical-speed hold. There is no position, velocity or altitude hold.

Allocation:
- Hover pitch trim comes only from the front/rear thrust differential.
- Yaw uses the reaction-torque split plus diagonal pod tilt.

Pilot test inputs (PTI):
- types: step, doublet, 3-2-1-1, sweep, on any axis;
- armed by the pilot, executed by the FBW, logged.

Lease failsafe after 5 s of sim time without an accepted action:
- collective, boosters and wheel drive go to 0, brakes go on;
- logged as an `ABORT` event plus `lease_abort_ring.npz`;
- no rescue.

### `live.py` and `live_server.py` (additive)
- `Mission.airframe_variant` accepts `phantom` and `phantom-fx`, with an optional `phantom` options block. Legacy metadata stays byte-identical when that block is unset.
- `/api/action` dispatches on `schema`. A schema/airframe mismatch returns 409; validation errors keep the `body` location.
- `/api/validate?variant=phantom` uses the Phantom footprint.
- Checkpoints use schema `phantom-1`.
- A leg load-cell CG gate (GO / NO_GO, 0.25 m) is logged at start.
- `time_scale` and timing are logged with every action.
- Run-folder evidence: `phantom_parameters.json`, `phantom_ledger.json`, `phantom_steps.csv.gz`, `crash_ring.npz`.

### Browser
- `public/assets/phantom-a10.glb` (and `phantom-a9.glb` for the A9 variants), built by `tools/phantom/export_phantom_glb.py`: frame 1, Z-up, no animations, joint extras.
- `public/assets/phantom-a10-visual.glb`: the render-only refinement of the A10 export, loaded by default (`?cad=1` loads the raw export). Built by `tools/phantom/refine_phantom_visual.py`; see `A10_VISUAL_PASS.md`.
- `public/vtx-env/phantom-look.js` drives the joints from `rendering_truth.phantom.joints`.
- `public/phantom-controls.js` is the operator panel.
- `public/app.js` has about 5 one-line hooks; `index.html` has 2 new `<option>`s.

## CG table

Base configuration: VTOL, wings stowed, canards folded, full fuel, 2 occupants. The pod share is the fraction of weight each pod carries.

| Variant / load | Mass (kg) | CG x (m) | Front / rear pod share, each |
|---|---|---|---|
| phantom | 1906.1 (+606 vs the notional 1,300) | -0.732 | 0.137 / 0.363 |
| phantom-fx, FX-A | 1897.5 | -0.152 | 0.230 / 0.270 |
| phantom-fx, FX-C | 1743.5 | -0.157 | about 0.23 / 0.27 |

These are the A10 cassette ledger. The A9 variants are 9.0 kg lighter (1897.1, 1888.5 and 1734.5 kg for the same three rows).

Full tables:
- `evidence/phantom/phantom_mass_ledger.json`
- `research_notes/Phantom CG compensation and test flights/cg_ledger_from_build.md`

## Hover feasibility

Bench run: `attitude_vs` mode for 10 s. Results are in `evidence/phantom/phantom_bench_results.json`.

| Variant | Result | Collective margin | Worst-pod margin | Power |
|---|---|---|---|---|
| phantom | **No lift-off**; rear pods saturate | -0.208 | -0.455 | generator 1.2 MW |
| phantom-fx, FX-A | Climbs 9.4 m | +0.415 | +0.31 | generator 900 kW + buffer 400 kW |
| phantom-fx, FX-C | Climbs 9.7 m | +0.541 | +0.422 | generator 900 kW + buffer 248 kW |

Feasibility sweep (`tools/phantom/phantom_feasibility.py`):
- 22 of 67 design points close.
- FX-A closes at 1885 kg, thrust-to-weight 1.40 collective and 1.30 for the worst pod, about 1.28 MW_e.
- The as-drawn aircraft with resized motors diverges to about 2.5 t.

All other benches pass for both variants:
- zero power on the gear, VTOL and road stance;
- fixture freefall;
- joint travel no faster than the rate limits, including the wing deploy/stow sequence;
- thrust direction;
- gyro sign;
- power-limited thrust;
- mass update on fuel burn;
- contact without pose jumps;
- energy residual.

## Commands

Server: use port 8766 only.

```
PY=C:/Users/steve/Documents/Github/-vtx-flight-sim/.venv/Scripts/python.exe
PYTHONPATH=src $PY -m vtx.phantom.ledger
PYTHONPATH=src $PY tools/phantom/phantom_bench.py          # about 65 s
PYTHONPATH=src $PY tools/phantom/phantom_feasibility.py
PYTHONPATH=src $PY tools/phantom/export_phantom_glb.py     # Blender -b, never saves
PYTHONPATH=src $PY -m pytest -q tests && git checkout evidence/flights/
VTX_DATA_ROOT=<scratch dir> PYTHONPATH=src $PY -m uvicorn vtx.live_server:app --host 127.0.0.1 --port 8766
```

## Starting a sortie through the API

Humans and AI pilots use the same endpoint.

```
POST /api/mission {"departure":[13.7,-28.4],"destination":[-45,18],"authority":"manual",
                   "airframe_variant":"phantom-fx","time_scale":0.2,"phantom":{"load_state":"FX-C"}}
POST /api/mission {"departure":[13.7,-28.4],"destination":[-45,18],"airframe_variant":"phantom","time_scale":0.2}
GET  /api/observe
POST /api/action {"schema":"phantom-fbw-1","authority":"manual","observation_id":12,"reason":"Lift-off, VS hold",
                  "stability_mode":"attitude_vs","collective":0.55,"vertical_speed_m_s":0.5,"brake":[0,0,0,0]}
POST /api/action {..., "pti":{"axis":"pitch","type":"doublet","amplitude":0.1,"pulse_s":1.0}}
```

`GET /api/observe` returns the `observation_id`, `lease_remaining_s` and the sensors; it never returns simulator truth.

Timing: at `time_scale` 0.2, one action per second of wall time gives a decision at least every 0.2 s of sim time. If no action arrives within 5 s of sim time, the lease ABORT fires.

CLI helpers (default host 127.0.0.1:8766):
- `tools/phantom/phantom_pilot_client.py` with `start`, `observe` or `action`.
- `tools/phantom/phantom_persistent_pilot.py`, a keep-alive. It only re-sends the command in `tools/phantom/phantom_pilot_controls.json`, and only while that file is armed and bound to the active run.

## Known gaps

- Packaging conflicts: the turbogenerator and boosters share the rear bay, and the fx fuel volume exceeds the bay.
- Windmilling is not modelled.
- No Munk moment.
- No structural or aeroelastic model.
- Fan/booster interaction is not modelled.
- Wingborne flight is pitch-unstable, so canard augmentation is required. Only the low-speed FBW subset is implemented.
- The GLB shows A9 geometry, not the FX-A wheels and fans.
- The leg actuator is a position servo, which droops about 2 cm under the fx load.
- The N2 option is not active.
- An A10 swap needs `a10_handover.json` registered under `geometry_sources.revisions`.
- The cockpit camera's `cabin` pose is a render-only seat offset.
