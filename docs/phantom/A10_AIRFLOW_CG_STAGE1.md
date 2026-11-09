# VTX Phantom A10 — Stage 1: airflow hardware and CG baseline

**Started:** 2026-11-04. **Engineering source:** repository A10 Blender file, existing mass ledger and its frozen parameter hash. This branch does not alter the source CAD, flight controls, physics plant or other aircraft.

## Gate 1 — establish mass and inertia truth

The current synthetic `phantom-fx` A10 configuration has an all-up mass of **1897.49 kg**, CG **x=-0.15156 m** at full fuel, two occupants, wings stowed and VTOL pose. Axes: +X forward, +Y left, +Z up. These are simulation model values, not measured aircraft specifications.

**Revision check.** Those figures are the **A10** cassette ledger as executed by the zero-change CLI below (`phantom-fx`, cassette revision A10). The earlier draft of this document quoted 1888.47 kg and x=-0.15084 m: those are the **A9** cassette ledger (`phantom-fx-a9`), which is 9.01 kg lighter. For reference, the first-moment examples are: an 8 kg add at x=+1.0 m shifts the A10 CG by **+4.83473 mm** (A9: +4.85465 mm); moving the existing 40 kg `hv_junction` forward by 0.4 m shifts it by **+8.43221 mm** (A9: +8.47246 mm), with no change in gross mass.

Use the existing `src/vtx/phantom/ledger.py` and `inputs/phantom_parameters_v1.json`. The new `tools/phantom/a10_cg_placement.py` independently calculates how proposed fixed hardware additions or relocations affect total mass, 3D CG and the complete 3x3 inertia tensor, without mutating the live plant.

**Run baseline:**

~~~bash
PYTHONPATH=src python tools/phantom/a10_cg_placement.py --variant phantom-fx --changes inputs/phantom_a10_cg_changes_stage1.json --output /tmp/a10-cg-baseline.json
PYTHONPATH=src python -m pytest -q tests/test_a10_cg_placement.py
~~~

The sample change list is **empty by design**: first verify exact identity against the source mass ledger. Add provisional components only after assigning explicit mass, mounting station and provenance. Each change is `SYNTHETIC_UNVALIDATED` until sourced.

### Example additional item

~~~json
{"operation":"add","id":"new_shutter_left","mass_kg":1.5,"position_m":[-1.3,0.7,0.7]}
~~~

This is **illustrative only**, not a selected part, verified position, duct fit or qualified mass. Mirrored hardware must be entered as separate left/right items. An existing fixed component may instead be moved with `{"operation":"relocate","id":"hv_junction","position_m":[x,y,z]}`; the numerical tuple must be replaced with an assessed location.

**Existing counted hardware:** each pod's `fan_motor_inverter` already includes inverter mass; `avionics_fcc`, `hv_junction`, `radiator` and both `cooling_fan_*` are already present. Prohibit duplicate bookkeeping. Neither a simple forward CG shift nor a smaller total mass guarantees better hover **and** wingborne trim.

## Gate 2 — inspect actual duct cross-sections

Source model: `assets/derived/phantom-a10-cassette.blend`. Relevant existing mesh objects include `A10_INDUCTION_DUCT_L/R`, `DUCT_RADIATOR_FRONT_RAM_INLET_*`, brake ducts, wheelhouse pressure exits, exhaust guides and wheel-pod fan placeholders. The Blendstra version is a **viewing derivative**, not an editable source; its bounds and shaded surfaces are inadequate to declare continuous, sealed, CFD-ready flow paths.

Measure at least: local throat areas, internal volumes, pressure-boundary locations, bend curvature/radii, diffuser expansion, hot-air exit paths, distance to rotors, all hatch/wing sweep clearances. Save CAD coordinate transformation and preserve A10 baseline. **Do not assume the 0.7 mm nominal CAD gap is a manufacturing tolerance.**

## Gate 3 — define two reversible airflow alternatives

Baseline A: current nominal fixed geometry.
Variant B: limited travel radiator bypass/shutters and duct inlets where tests show useful flow improvement.
Variant C: centrebody or inlet-lip adjustment only if B cannot meet mass-flow, drag or pressure recovery demand.

Each variant must include component mass, actuator load/torque, control law and fail-safe state. Prove packaging clearance before any mesh replacement. CFD test points: stationary/hover with powered cooling, road design points, transient road-to-flight conversion, wingborne approach and high-speed cases. Compare flow stability, mass flow, total-pressure recovery, drag, heat rejection and hot-air recirculation. **No CFD has yet been executed as part of this stage.**

## Electrical design boundary

Current FX-A simulator uses an **800 V nominal DC bus**, a `600 kW_e` continuous / `900 kW_e` takeoff turbogenerator baseline and a provisional energy buffer. Escalating ESC, ECU, radiator fan, pump, BMS or interconnect mass requires the same CG/inertia gate. Existing propulsion and coolant thermals are simplified; electrical fault and thermal models must be validated separately. Maintain functional separation between the flight controller and road-vehicle controller.

## Release gates

1. Zero-change sensitivity output matches the original ledger across configured mass and inertia.
2. Proposed components supply mass, position, inertia/provenance or explicitly bounded uncertainties; no double-counted inverter or HV distribution.
3. Road, hover, deployed wing, one/two occupant and depleted fuel configurations assessed; never approve a shift from hover trim alone.
4. Geometry alternatives preserve original A10 and are checked for physical fit, structural effect and moving collision.
5. CFD/thermal results and regression tests reproducible, parameter snapshots versioned, failures visible. No change to Colin's control schema until explicit review.

**References:** `docs/phantom/A10_WING_SYMMETRY_REVISION.md`, `docs/phantom/SYSTEMS_CONTRACT.md`, `docs/phantom/PHANTOM_FLIGHT_TEST_20261103.md` and `research_notes/Phantom CG compensation and test flights/cg_and_compensation.md`.
