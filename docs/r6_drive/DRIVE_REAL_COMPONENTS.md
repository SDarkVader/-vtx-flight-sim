# R6 fan drive: real components and stability check (24 Nov 2026)

**Status:** engineering study for the owner. Nothing in r2, `model.xml` or the live simulator has changed. Every flight below is an isolated, offline replay.

## 1. The duty, taken from the physics model

| Item | Value | Source |
|---|---|---|
| Engine output | 6,016 rpm. Installed limit 769.4 N·m (484.7 kW, 650 shp class). Continuous 469.8 kW. Flight limit 300 kW | R6 flight record `hypotheses`: M250-C30P class. The engine TCDS (EASA/FAA) could not be retrieved |
| Engine to fan ratio | 5.0133, fan at 1,200 rpm | same |
| Fan torque | 567 N·m at the 300 kW limit; 888 N·m continuous; 916 N·m installed peak | Wolfram, η 0.95, 4 fans |
| Nacelle tilt | Model stops at 20° (cone). The recorded A-to-B flight used ≤ 4°, on one axis, for yaw only | `aircraft.py:288`, `argon_fly_to_b.py:166-172` |

## 2. The CV joint on the tilt pivot

Source: NTN catalogue *Constant Velocity Joints for Industrial Machines* (5603E), https://www.ntnglobal.com/en/products/catalog/pdf/5603E.pdf.

- **Fixed cup type, the high-angle type:**
  - With a boot it is rated for 25° under load and 38° static (p. 7). The joint alone is rated for 42°.
  - Allowable speed falls as the angle rises (Fig. 12, p. 18). At 25°, BJ75 is rated to about 890 rpm, and larger sizes to less.
- **Fixed disc type, the high-speed type:**
  - It is rated for 14–18° under load (p. 6).
  - Fig. 9 (p. 17) shows that at 6,000 rpm only about 0–4° is usable, and at about 1,200 rpm about 13°.
- **Conclusion:** no catalogue CV joint can carry this drive at 28° or 20° at any of its shaft speeds. The joint must run at fan speed (1,200 rpm), and the tilt has to be limited to about 13°.

**Selection: NTN BJ150 fixed disc type**, sized by NTN's method (p. 12–14), with Wolfram arithmetic:

| Check | Value |
|---|---|
| Life torque Te = K1·K2·Ta/K3 | K1 1.5 (blower duty), K2 0.78 (4 h/day), K3 0.915 (4° normal angle), giving **725 N·m** (916 N·m if run continuously at 13°) |
| BJ150 capacity at 1,200 rpm | about 900 N·m (Fig. 8-1(A), p. 14): passes |
| Peak strength, TD1 (Table 2, p. 16) | 4,710 N·m against 916 N·m peak: 5.1× |
| Allowable angle under load / static | 16° / 18° (p. 25). Fig. 9 at 1,200 rpm gives about 13° |
| Mass | 16.3 kg per joint, derived from DFB L = 500 mm at 40.2 kg minus 5 × 1.54 kg of tube (p. 26) |

## 3. Speed reduction

Source: Tandler spiral bevel catalogue (DieQua), https://diequa.com/wp-content/uploads/2023/02/tandler-spiralbevel-full-RevA3-web-singles.pdf.

- The ratings charts (p. 10–11) stop at **3,000 rpm input**, half the 6,016 rpm needed.
- At 5:1, a size that carries the fan torque is E1, about 1,150 N·m at 3,000 rpm, and it weighs **250 kg** (weights table, p. 46). D1 carries about 450 N·m and weighs 124 kg.
- **Conclusion:** no industrial catalogue gearbox is usable. The 5:1 stage has to be an aerospace-class spiral bevel gearbox, which is custom. It should sit at the bottom bevel gearhead so the spindle and CV turn at fan speed.
- This study keeps the ledger's gearbox mass allocations. They are **unverified**.

## 4. Shafts, from Wolfram

| Shaft | Speed | Peak shear | First whirl speed | Margin |
|---|---|---|---|---|
| Spindle, 86 × 3 steel tube; bearings at 0.60, 1.10 and 1.98 m | 1,200 rpm | 29 MPa | 18,039 rpm | 15× |
| Radial shaft, 76 × 3 steel tube, 0.96 m span | 6,016 rpm | 7.6 MPa | 13,334 rpm | 2.2× |

If the reduction moves to the bottom gearhead, the spindle no longer whirls; it did at 9,000 rpm.

## 5. Stability: re-flying the recorded sortie offline

Tool: `tools/visual_r6/r6_drive_mass_study.py`. It edits the in-memory model, then runs the unmodified `r6_physics_replay.py`, which uses the pilot gains as flown on 3 Nov. The flight is 300 s long, from A to B in the historical valley world.

| | Baseline r6 | NTN BJ150 CVs fitted | Industrial (BJ150 + Tandler E1) |
|---|---|---|---|
| Mass | 996.7 kg | 1,057.7 kg (+61.0) | 2,043.5 kg |
| CG (x, y, z) | −0.000, 0.079, 1.203 | −0.000, 0.074, 1.248 | −0.000, 0.038, 0.902 |
| Roll / pitch / yaw inertia | 1,817 / 1,784 / 2,542 | 2,059 / 2,025 / 2,954 (+13% / +14% / +16%) | 5,644 / 5,607 / 9,625 |
| Outcome | landed at B, 1.47 m off, at 163.6 s | landed at B, 1.20 m off, at 159.2 s | **never left the ground** |
| Max roll/pitch | 2.72° | 2.66° | — |
| RMS roll / pitch in transit | 0.82° / 1.46° | 0.85° / 1.49° | — |
| Mean hover power / peak | 202.3 / 235.9 kW | 220.0 / 240.1 kW | — |
| Margin to the 300 kW limit in hover | 98 kW | 80 kW | — |
| Max gear load | 4,164 N | 4,016 N | — |

**Result.** With real NTN CV joints the aircraft stays stable on the same controller and lands at B. The cost is 61 kg and 18 kW more hover power, and the CG rises 45 mm.

## 6. Owner decisions before any adoption

1. Move the 5:1 reduction to the bottom bevel gearhead. The spindle and CV then turn at 1,200 rpm, and the nacelle gearbox becomes a direct drive.
2. Lower the nacelle tilt cone from 20° to about 13°, at `aircraft.py:288` and `:549`. The recorded flight used ≤ 4°.
3. Accept +61 kg and +18 kW hover power for steel industrial CV joints, or commission a lighter aerospace CV joint with the same angle and speed limits.
4. The 5:1 spiral bevel stage needs an aerospace supplier and a verified mass.
5. Any change to physics is a new variant, not the frozen r6-argon-20261103. The validation ladder applies.
