# Phantom physical systems and controls contract (P0)

**Applies to the isolated Phantom variant only.** The A8 model is a reference for geometry and articulation, not a mass/inertia measurement. All units SI. Derived calculations from assumptions must be labelled **SYNTHETIC_UNVALIDATED** until supported by measurements, manufacturer operating maps or testing.

## 1. Physical architecture

In the existing VTX repository:
- `src/vtx/aircraft.py`: current live MuJoCo airframe builder and step. Add a new `phantom` model variant; do not replace the common-shaft existing aircraft or override defaults.
- `src/vtx/aero.py`: **rotor** blade element model only. Add a separate module for wing/canard/control-surface polars and local force integration.
- `src/vtx/live_server.py`: current `Action` accepts engine, four collectives, four 2D tilts, cabin controls. Make any Phantom-specific action a **versioned, opt-in schema** and never silently change the old parser.
- `src/vtx/physics_model.py`: reduced rigid-body validation harness; not a substitute for a coupled live multibody physical state.

Source CAD axes X-forward/Y-lateral/Z-up must be explicitly transformed into the MuJoCo body frame; do not infer signs from rendered camera poses. Full mass and CG, 3x3 positive-definite inertia and moving wing/pod mass distributions must be represented. At minimum `F=ma` and `tau = I*omega_dot + omega × I*omega`, including externally applied aerodynamic/propulsive/contact moments. Let MuJoCo carry internal actuator joint constraint forces to avoid double-counting.

## 2. Effectors, independent commands and achieved telemetry

| Distinct command group | Physically required output | Minimum feedback |
| --- | --- | --- |
| `pod_[FL,FR,RL,RR]` thrust | Local axial force at actual pod location and vector axis, rotor torque and angular momentum | `commanded_thrust_N`, `actual_thrust_N`, rpm, tilt, shaft torque, power, thermal/fault |
| `pod_[...]` road drive | Contact wheel spin torque, friction, rolling and tyre losses | wheel spin, angular acceleration, ground contact, electrical draw |
| `rear_prop_[L,R]` | Rear force at real mounting sites; independent response and failure | throttle, achieved thrust, spool, power, exhaust/generator balance |
| `wing_[L,R]` | Hatch position, lateral carriage extension, fold angle, positive flight-lock state, moving mass | angle, slide position, lock verified, motor torque, sweep collision flag |
| `aileron_[L,R]` | Separate outboard hinged trailing-edge force/moment at real hinge location | deflection, rate, hinge torque, power, saturation |
| `flap_[L,R]` | Separate inboard control, lift/drag changes and hinge torque | deflection, rate, high-dynamic-pressure inhibit, power |
| `canard_[L,R]` | Positive/negative pitch-trim authority from local relative airspeed, particularly while converting wheel thrust for rolling landing | deflection, calculated lift and pitch moment, rate, torque |
| `gear_leg_[FL,FR,RL,RR]` | Landing-leg extension, spring/damper response, contact forces and stroke | state, compression, normal impulse, fault |
| `cooling` | Engine/generator/motor/inverter heat source, fan power, radiator flow | temperature, rejected heat, operating state |

Every actuator implements travel, hard stop, maximum angular or linear speed, acceleration, continuous and peak torque, inertia, power draw, efficiency, response delay, position sensor and jam/disconnect failure. Do not equate a target deflection with actual deflection.

## 3. Wings and aerofoils

At each lifting/control surface, evaluate **local** velocity relative to surrounding air: `v_local = v_CG + omega × r_surface - v_wind` (in a consistent body/world frame). Dynamic pressure `q = .5*rho*|v_local|²`, and `F_lift = q*S*CL(alpha,deflection,Mach,Reynolds,pose)`. Drag, pitching moment and sign of moment about the current CG must be computed from the correct application centre. Start with declared bounded synthetic coefficient tables and explicit stall, not unrestricted `CL`. No lift when relative speed approaches zero.

- **Wings**: loaded bending/torsion/structural envelope and centre-of-pressure movement; separately modelled left/right.
- **Ailerons**: independent outboard, differential roll; include possible aileron reversal and flutter risk as unvalidated until aeroelastic model/test exists. Barrel-roll capability is a control-system test, not guaranteed by root bearing C rating.
- **Flaps**: independent inboard, symmetric lift/drag scheduled for slow flight. Rate and max-q restrictions; *not* deployable at arbitrary 400 mph.
- **Nose canards**: pitch compensation during transition when wheel thrust vectors stop providing nose-up/vertical authority. Account for forward location, local flow, lift, drag and control moment. The previous “75 m/s” wing-only calculation was conditional on 4.5 m² and CL=0.8; it is not a guaranteed takeoff threshold.
- **Hatch and wing cassette**: hatch opens first; wing slides outward; then rotates; lock engages. Folding/translation during loaded high-q flight needs a validated operating envelope. Wing flex under load may be modelled with elastic modes, **not uncontrolled joint play**. The outer shell is not the wing root.

Provisional static root screen (NOT final design): 1300 kg, +12g ultimate, 1.2 m wing lift-resultant arm, half the total load per wing -> **91.8 kN·m** root bending. If load spread vertically between two lines, opposing force magnitudes at separation of 0.35/0.16/0.12 m are **262/574/765 kN** respectively. The existing ~160 mm exterior fairing has not demonstrated 350 mm effective load separation. Load carrying locks and inner spar/tub must be designed first; the folding bearing must not carry a bending moment by itself.

## 4. Electrical architecture and energy

Two permissible competing synthetic plant architectures; choose explicitly before running tests:

**A. Series turboelectric:** turbine/engine -> shaft generator -> DC bus and buffer -> 4 pod electric motors, 2 aft electric propulsors, wing/control actuators, cooling. Shaft mechanical, generator electric, inverter DC/AC and motor shaft powers are individually accounted; no free rear jet exhaust thrust.

**B. Shaft + rear exhaust hybrid:** gas path produces turbine shaft power **and** aft exhaust thrust, both constrained by a common fuel/thermodynamic budget and separate spool response; cannot claim generator power and full nozzle thrust independently from the same fuel.

For either architecture keep `P_generator_elec + P_buffer_discharge = P_pods_elec + P_rear_elec + P_actuators + P_cooling + P_aux + P_buffer_charge + P_loss` with explicit voltage/current limits and energy `E_buffer_dot = -P_buffer_discharge + eta_charge*P_buffer_charge`. Fuel consumption reduces fuel mass and changes CG/inertia. Buffer state-of-charge and thermal envelope must constrain peak power. Do not model “unlimited budget” as unlimited in-flight energy.

At 1300 kg and radius .25 m for each of four effective rotor disks, momentum-theory ideal induced hover lower bound is roughly **1.04 MW** (sea level, independent noninterfering disks). If a *synthetic illustration* assumes 65% aggregate effective efficiency, electrical hover is roughly **1.6 MW** before independent accessory loads. This is a **demand estimate**, not a motor/aircraft rating. Effective rotor disk area cannot be inferred from tyre diameter.

Turbine-generator example for comparison only: Safran TG600 **600 kW per unit**; a 1.2 MW nominal installed generation is two such units, not one, and still may be inadequate for the proposed compact disks without a peak-power buffer. Aft thrust at 400 mph needs its own drag and propulsion calculation. Hover, rolling and maximum-speed power/thermal loads are distinct conditions.

## 5. Cooling and airflow

The A8 CAD has *nominal* paired engine induction, radiator, brake inlet and wheelhouse pressure-relief geometry; duct terminations and pressure-flow maps are not yet engineered. Model actual engine/generator heat, HV inverter/motor heat and thermal capacitance; calculate cooling mass flow and radiator differential pressure. Ram-air cooling cannot operate at zero airspeed: **powered cooling is mandatory for VTOL if waste heat exists**. Side vents may affect yaw/drag, not automatically improve stability. Test crosswind and wing/pod transformation airflow.

## 6. Live pilot boundary and instrumentation

Keep the existing human/Colin **same-control** rule and independent physics clock. Add new Phantom commands only after a versioned opt-in action schema, input validation, fault rejects and logging. Pilot-visible instruments include airspeed, attitude, rate, lift margin estimate, actuator status, power/SOC/fuel and faults. Audit truth is recorded separately and is **not** a privileged Colin observation. No code may teleport, freeze height, suppress collisions, force a successful landing or inject free corrective forces.

Log at physics and action cadence: `mission_id`, variant, config hash, deterministic seed, timestamp, requested/actual effectors, local airspeed, `F/M` breakdown, total mass/inertia, engine/generator/buffer state, energy balance residual, contact and all protection events. Synthetic assumptions are logged as such.
