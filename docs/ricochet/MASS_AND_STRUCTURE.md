# Ricochet mass and structure

Source: `src/vtx/ricochet/mass_register.py` (register version `rc01-f03-lc-v2`), `src/vtx/ricochet/spec_math.py` and the built MuJoCo model. The harbour boats use load case LC-01.

## Mass register, LC-01

The 815.0 kg light ship plus an 85 kg passenger gives 900.0 kg. Centres of gravity are in the VTX body frame, in metres.

| Item | Mass (kg) | CG x | CG y | CG z | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| CFRP hull frame, bulkheads and cockpit tub | 332.0 | 0.62 | 0.00 | 0.44 | provisional_unverified |
| Canopy dome | 16.0 | 1.36 | 0.00 | 1.24 | derived_geometry |
| Seat, harness, stick and dual MFD console | 14.0 | 1.22 | 0.00 | 0.78 | derived_geometry |
| 9.6 m wing, winglets and carry-through spars | 155.0 | 0.18 | 0.00 | 0.96 | provisional_unverified |
| Sponson strut, port (titanium) | 5.0 | −0.26 | 3.55 | 0.78 | derived_geometry |
| Sponson strut, starboard (titanium) | 5.0 | −0.26 | −3.55 | 0.78 | derived_geometry |
| Tail pylon, T-tail and fan mounts | 38.0 | −2.05 | 0.00 | 1.72 | derived_geometry |
| Ducted fan unit, port (Ø0.90 m, 9-blade rotor, motor) | 28.0 | −2.05 | 0.78 | 1.56 | envelope_nominal |
| Ducted fan unit, starboard | 28.0 | −2.05 | −0.78 | 1.56 | envelope_nominal |
| Energy pack and drive wiring (forward bilge) | 170.0 | 1.62 | 0.00 | 0.40 | envelope_nominal |
| Sponson float, port | 12.0 | −0.34 | 3.80 | 0.48 | envelope_nominal |
| Sponson float, starboard | 12.0 | −0.34 | −3.80 | 0.48 | envelope_nominal |
| Passenger on the F02 seat track | 85.0 | 1.30 | 0.00 | 0.80 | envelope_nominal |
| **Total** | **900.0** | **0.506** | **0.000** | **0.704** | |

In the F03 variant the sponsons sit at z 0.42, so the total CG z is 0.702.

## Inertia (about the CG, VTX axes, kg·m²)

| | Concept A | F03 |
| --- | ---: | ---: |
| Ixx (roll) | 1,294.1 | 1,294.9 |
| Iyy (pitch) | 1,865.5 | 1,866.2 |
| Izz (yaw) | 2,747.0 | 2,747.0 |
| Ixz | 283.2 | 282.0 |

## How the mass is split in MuJoCo

The airframe body carries 854.59 kg. The articulated children carry the rest, so the vehicle total matches the register exactly (`_subtract_child_inertias`).

| Body | Mass (kg) | Local inertia (kg·m²) |
| --- | ---: | --- |
| Fan rotor, port and starboard | 4.2 each | (0.11, 0.06, 0.06) |
| Aileron, port and starboard | 2.2 each | (0.12, 0.03, 0.13) |
| Elevator | 2.8 | (0.20, 0.04, 0.22) |
| Rudder | 2.2 | (0.08, 0.09, 0.03) |
| Reverse bucket, port and starboard | 1.8 each | (0.04, 0.05, 0.05) |
| Sponson, port and starboard | 12.0 each | (0.8, 1.6, 1.6) |
| Cabin marker | 0.01 | (0.001, 0.001, 0.001) |

## Load cases (`rc01-f03-lc-v2`)

| Case | Description |
| --- | --- |
| LC-01 | Passenger aboard, underway. 85 kg passenger on the seat track at (1.30, 0, 0.80), nominal 900 kg manned trial. |
| LC-02 | Unoccupied and stowed on water, propulsion off, moved only by the water (815 kg). |
| LC-03 | Empty-payload flotation with a declared fuel state in the paired fuel-cell bays, lateral CG kept at y = 0 (815 kg dry plus fuel; provisional). |
| LC-04 | Propulsion installation comparison: baseline pack, paired fuel cells or alternate pack (provisional). |
| LC-MAX | Maximum payload: 85 kg passenger plus 150 kg payload, 1,050 kg. Aliases `LC-05`, `LC-05_MAX_PAYLOAD`. |

The legacy register `rc01-lc-v1` keeps the earlier definitions (LC-01 and LC-02 at 815 kg, LC-03 at 900 kg, LC-04 at 1,050 kg). The design study range is 750 to 1,050 kg.

Fuel states for LC-03: dry 0 kg, short test 5 kg, nominal 10 kg, full 20 kg (provisional).

The propulsion installations are mutually exclusive:

| Installation | Pack position |
| --- | --- |
| `baseline_pack` (default) | 170 kg at the forward bilge (1.62, 0, 0.40) |
| `fuel_cell_paired` | 85 kg + 85 kg at (−1.05, ±0.23, 0.55) plus fuel |
| `energy_pack_alternate` | 170 kg at (−1.02, 0, 0.69) |

## Buoyancy reserve

| | Concept A | F03 |
| --- | ---: | ---: |
| Enclosed volume (hull + 2 sponsons) | 3.167 m³ | 4.922 m³ |
| Maximum buoyancy | 3,164.5 kg | 4,917.4 kg |
| Reserve over 900 kg | 2,264.5 kg | 4,017.4 kg |
| Design minimum watertight volume | 1.80 m³ | 1.80 m³ |

## Structural rigidity (`spec_math.COMPONENT_RIGIDITY_SPECS`)

| Component | Material | Stiffness (N/m) | First mode (Hz) | Design limit load (N) | Safety factor | Rigid in sim? |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Hull girder | CFRP / Corecell M80 sandwich | 3.999 × 10⁷ | 45.9 | 35,304 | 51.3 | Yes |
| Main wing | CFRP T700/epoxy box | 128,412 | 6.4 | 16,769 | 3.0 | Rigid body in sim; flexibility reported in telemetry only |
| Sponson strut assembly | Ti-6Al-4V grade 5 | 51,790 | 5.1 | 1,800 | 5.6 | Modelled as a spring |
| Tail pylon and T-tail | CFRP HM laminate | 280,151 | 27.7 | 1,200 | 20.2 | Yes |
| Duct shroud and arm | CFRP HM laminate | 1.128 × 10⁶ | 32.0 | 2,200 | 15.2 | Yes |
| Canopy dome | Lexan MR10 polycarbonate | 392,727 | 24.9 | 3,752 | 10.6 | Yes |

## Sponson suspension

Each sponson hangs on a vertical slide joint with ±0.06 m of travel. The joints carry force and torque sensors, and `attachment_loads()` reports the loads on each hanger.

| | Concept A | F03 |
| --- | --- | --- |
| Stiffness | 51,790 N/m (strut spec) | 28,000 N/m |
| Damping | 950 N·s/m (spec 515, floored at 950) | 600 N·s/m |
| Mount | (−0.34, ±3.80, 0.48) | (−0.34, ±3.80, 0.42) |

## Flooding

The craft is waterproof by default (`waterproof = True`). If the seal is disabled, `HULL_BREACHED` is raised and water enters by Torricelli flow:

dm/dt = ρ × 0.095 × √(2g(h_seam + overtop))

- h_seam is the draft, at least 0.08 m.
- overtop = max(0, 0.14 − min freeboard) + 0.55 × max(0, |roll| − 10°)/30°, plus 0.45 inside a whirlpool core.

Flood water is capped at 92% of the enclosed volume. The mass is re-applied to MuJoCo every 8 kg of change, and at the cap.
