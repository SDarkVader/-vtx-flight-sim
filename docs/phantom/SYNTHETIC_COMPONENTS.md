# Synthetic component implementation contract — missing hardware without magic physics

**Purpose:** enable a functioning simulated Phantom before a manufacturer-specific wing hinge, actuator, turbogenerator or electric pod is selected. Every numerical limit must be inspectable and replaceable. `SYNTHETIC_UNVALIDATED` means a declared model hypothesis, **not** a datasheet or proof of flightworthiness.

## Component record

Each component instance has `id`, `kind`, `source_status`, `model_revision`, `mass_kg`, `r_body_m`, full component `inertia_kg_m2`, `limits`, `response`, `power`, `faults`, and `provenance`. Use named SI units in the schema, never implicit percentages for physical quantities. Refuse non-finite/negative mass, energy, power capacity, non-positive inertia or physically inconsistent limits.

Use six categories:

1. **Rotary or linear actuator:** target position/velocity; achieved angle/extension, rate, acceleration, applied torque or force; hard stops; compliance and friction; electrical work `P_mech = tau*omega` or `F*v` and explicit efficiency and regenerative treatment. Applied torque reacts against the structural body.
2. **Aero surface:** finite area/chord/centre, local dynamic pressure and alpha, bounded synthetic CL/CD/CM versus deflection and Mach. Interpolate tabulated coefficients, use stalls and residual drag, and include hinge moments; calculate torque about true CG.
3. **Rotating propulsor:** finite RPM, spool inertia, input torque, torque reaction, thrust map vs airspeed/pitch/RPM/density, consumed shaft/electric power; no thrust from a zero-powered stalled rotor except any explicitly modelled windmilling.
4. **Electrical source:** generator and/or finite-energy buffer with voltage, current, heat/efficiency, power caps and slew; total requested load allocated and any deficit affects motor output. No unlimited bus current or fictional minimum thrust.
5. **Aeromechanical joint:** wing hatch, slide and fold, positivity of lock state, independent structural fatigue/overload watch. A visual lock state cannot enable unlimited root bending capacity. Elastic wing modes must have physical stiffness/damping and modal inertia; hinges aren't floppy.
6. **Thermal component:** finite heat capacity and source/sink model, radiator airflow from ram + powered fan, temperature and high-temperature derating/faults.

## Minimal equations and protections

`I*omega_dot = tau_motor - tau_hinge - tau_damping - tau_friction`; clamp **motor torque** and available **power**, not the resulting external torque. Use hard contact/stop response in the actual physics engine. Mechanical output power `P_mech = tau_motor*omega`, electrical demand `P_elec >= P_mech / eta` when motoring. Regeneration must not recover more than negative mechanical work after losses.

`q = .5 * rho * |v_local - v_wind|^2`; `F_lift=q*S*CL`; `F_drag=q*S*CD`. Compute aerodynamic body force orientation using relative flow and surface attitude. `M_control = r_control × F + q*S*c*CM`. Loss of airflow must reduce forces continuously; avoid a constant-speed, always-effective aileron.

For a finite energy buffer `E(t+dt) = clamp(E(t) + (P_charge*eta_charge - P_discharge/eta_discharge)*dt, 0, E_max)`. Enforce current and power, temperature, generator delay and charge/discharge limits. When demand exceeds supply, derate loads by a documented arbitration policy and log unmet requests.

**Energy balance invariant:** fuel chemical input plus decreases in stored electrical/rotational energy must account for airframe kinetic/potential changes, propulsor aerodynamic work, drag, heat and dissipated losses within an appropriate integration tolerance. Internal joint reaction must not be counted as external energy.

## Numerical parameter sourcing policy

- `MEASURED`: independently measured on Phantom hardware or calibrated bench with timestamp and method.
- `MANUFACTURER_DOCUMENTED`: exact part number and original datasheet + conditions.
- `DERIVED`: calculated from explicitly identified inputs and equations.
- `SYNTHETIC_UNVALIDATED`: free parameter for simulator sensitivity; include lower/nominal/upper alternatives and uncertainties, never tune only until mission succeeds.

For early P1 and P2, **unknown numeric fields remain null** until a documented provisional value is explicitly selected. Never silently use a zero for missing lift, inertia, fuel burn or load when its physical contribution matters; a deliberately disabled component is a separately recorded fault/state.

## Input manifests and code integration

Use `inputs/phantom_simulation_manifest_v0.json` as a **contract/unknown-input register**, not a complete flight profile. A first P1 implementation must parse/check this manifest, require chosen provisional alternatives and fail clearly on unknown mandatory inputs. Do **not** load it into the existing aircraft.

Recommended new modules: `src/vtx/phantom/plant.py` for physical MuJoCo bodies; `surface_aero.py` for per-surface force and moments; `energy_bus.py` for generator/buffer/motors; `controls.py` for versioned action schema/actuators; `ledger.py` for mass/inertia and source status. Test each module separately before adding the API selector.

### Example failure behaviours (mandatory to test)

- Pod motor spool delay, tilt actuator blocked, asymmetrical thrust, failed rear propulsor.
- Wing hatch jam, incomplete slide, fold bearing seized, left lock fails, load exceedance.
- Aileron hard-over or detached, flap stuck, canard pitch saturation, servo loss of bus.
- Generator trip, buffer discharge limit, bus undervoltage, heat exchanger fan loss.
- Fuel exhaustion, external wind, low airspeed with little aerodynamic authority, wing flutter *flag* if coupled model isn't implemented.

## Boundary of synthetic modelling

Synthetic actuator force curves are legitimate *in the game* if they obey physics, mass/inertia and energy. A “synthetic strength limit” is also acceptable for structural failure events. But a physically impossible cap, inconsistent units, instant actuator, virtual altitude hold or fictitious generator energy defeats the purpose of the experiment. Keep model limits visible and record what changes between trials.
