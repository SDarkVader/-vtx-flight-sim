# Ricochet propulsion and energy

Source: `src/vtx/ricochet/plant.py` (`_apply_actuator_controls`, `_compute_aero_and_propulsion`, `step`) and `src/vtx/harbour_fleet.py` (`step`).

## Ducted fans

Two Ø0.90 m ducted fans sit on the tail pylon at (−2.05, ±0.78, 1.56). Each has a 9-blade rotor and an electric direct-drive motor. The rotors are real MuJoCo bodies (4.2 kg each) on unlimited hinges along ±X, and the starboard fan counter-rotates. Their speed is integrated by MuJoCo from motor torque minus blade drag; nothing sets it directly.

| Quantity | Value |
| --- | --- |
| Rotor diameter D | 0.90 m |
| Thrust coefficient Cₜ | 0.24 |
| Maximum thrust per fan | 1,450 N (2,900 N total) |
| Maximum rotor speed ω_max | 544.8 rad/s (5,202 rpm) |
| Blade drag torque | k_q ω\|ω\| + 0.04 ω, with k_q = 95 / ω_max² (116.8 N·m at ω_max: 95 from the quadratic term, 21.8 from the linear term) |
| Motor torque limit | ±200 N·m |
| Motor power limit | 68 kW per fan: torque ≤ 68,000 / max(\|ω\|, 120) |
| Idle floor with throttle above 1% | 94.25 rad/s (900 rpm) |
| Spool fraction (telemetry) | \|ω\| / 545 |

## Speed governor

For each fan, every rigid step:

1. Work out the fan's share of the throttle:
   - port: throttle × max(0, 1 − 0.5 × differential)
   - starboard: throttle × max(0, 1 + 0.5 × differential)
2. Apply inflow lapse with forward airspeed u: lapse = clamp(1 − 0.18 × u/45, 0.55, 1.05).
3. Reference speed: ω_ref = ω_max × √(share × lapse), raised to the 900 rpm idle floor when throttle > 0.01.
4. Motor torque = feed-forward blade drag at ω_ref + 2.2 × (ω_ref − ω), limited by the torque and power limits.
5. With throttle ≤ 0.01: light regenerative coast-down, torque = −0.45 ω, clipped to ±45 N·m.
6. With no fuel, or propulsion switched off in the mass register: zero torque.

## Thrust

Gross thrust per fan: T = Cₜ ρ_air n\|n\| D⁴, where n = ω / 2π is in rev/s.

Net axial thrust per fan: T_net = T × (1 − 1.55 f), where f is the reverse-bucket fraction (achieved angle / 85°).

| Bucket | Net thrust factor |
| --- | --- |
| Stowed (0°) | +1.00 |
| Half (42.5°) | +0.23 |
| 64.5% (54.8°) | 0 (neutral) |
| Full (85°) | −0.55 (reverse) |

The deflected jet also lifts the tail: +0.06 × \|T\| × f per fan, along body +Z.

Propulsion forces and moments are applied at the airframe:

| Component | Value |
| --- | --- |
| Force, body X | T_net,port + T_net,stbd |
| Force, body Z | Bucket lift (above) |
| Pitch moment | (1.56 − CG z) × total net thrust (thrust line above the CG) |
| Yaw moment | (T_net,stbd − T_net,port) × 0.78 m |

Rotor reaction torque is not added separately. It reaches the airframe through the rotor hinges in MuJoCo.

## Fan slipstream

The fans wash the tail. Slipstream speed is √((T_port + T_stbd) / (2 ρ π 0.45²)), and 55% of it is added to the local airflow at the elevator and rudder. So the rudder keeps steering authority at low boat speed whenever the fans are running. See [Hydrodynamics and aerodynamics](HYDRO_AND_AERO.md#control-surfaces).

## Power, fuel and energy

| Quantity | Model |
| --- | --- |
| Propulsion power | \|ω_port τ_port\| + \|ω_stbd τ_stbd\| |
| Servo power | Σ (\|actuator force × joint rate\| + 0.06 \|actuator force\|) |
| Fuel at start | 10 kg energy-reserve proxy (`fuel_initial`) |
| Fuel burn | 1.15 × 10⁻⁷ kg/s per watt of total power |
| Energy budget | 20 kWh; consumed and remaining are reported |

At full throttle with no forward speed, each fan settles at ω_max. Blade drag there is 116.8 N·m, just under the 125 N·m that the 68 kW limit allows at that speed. That is about 64 kW per fan, or roughly 127 kW in total, which burns about 0.015 kg/s. At that rate the 10 kg reserve lasts about 11 minutes and the 20 kWh budget reads empty after about 9.5 minutes. Only the fuel reserve gates power: at zero, `FUEL_EXHAUSTED` is raised and the servos and motors go passive.

These are model values derived from the code above, not measured figures. The propulsion installation's motor, gearbox, cooling, controllers and thrust, torque and power map are marked unverified in the mass register.
