# Argon Live Flight Stability & Telemetry Calibration Reference

**Baseline Commit / Revision**: `P0-V4A-assembly-r6` (`R6`) & `P0-V4A-assembly-r5` (`R5`)  
**Machine-Readable Telemetry Ledger**: [`evidence/argon_live_stability_calibration.json`](./argon_live_stability_calibration.json)  
**Task 01 Engineering Ledger**: [`evidence/argon_task01_transmission_tanks.json`](./argon_task01_transmission_tanks.json)  
**3D BVH Clearance Ledger**: [`evidence/r6_clearance_audit.json`](./r6_clearance_audit.json)

---

## 1. Retain-All Sortie Summary

| Sortie ID | Airframe | Fuel | Objective | Peak Radar Clearance | Peak Baro Alt | Outcome & Key Finding |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `20261101T223958-5d417d` | `R6` (pre-fix) | `10 kg` | Open-loop rotor & axis identification | `2.283 m` | `1.643 m` | Identified diamond `(E, N, W, S)` rotor indexing, `+0.0792 m` Y-CG offset, and `shaft2` skewed hinge axis (`aircraft.py` fixed). |
| `20261101T231152-3ab37e` | `R6` (fixed) | `10 kg` | Closed-loop hover, doublet perturbation & landing | `1.760 m` | `1.150 m` | **0 structural impacts** (`warning_lamps: []`). Airborne hover (`0/6` ground contact) with roll/pitch `<= 1.44°`; smooth 6-gear touchdown (`56.1 mm` equal strut compression). |
| `20261101T232353-c7b594` | `R5` / `R6` | `10 kg` | `10 m` altitude climb, `18 s` hover hold & destination translation | `10.770 m` | `10.170 m` | Climbed smoothly at `+1.15 m/s` (`252 kW`, `1,188 RPM`) and held `10.5–10.77 m` clearance for `17.9 s` with roll/pitch `<= 0.42°` (`202.5 kW`, `1,199.3 RPM`) until yaw drift past `90°` exposed world-vs-body frame cross-coupling during translation. |

---

## 2. Calibrated Rotor Indexing & Control Allocation Matrix

In `src/vtx/aircraft.py` and `evidence/source/airframe_ledger_r6.json`, the four rotors are arranged in a **cardinal diamond (`+` configuration)** rather than an `X` quadrotor:

| Index | Body / Actuator Name | Rotor Hub Position $(x, y, z)$ [m] | Gimbal Pivot $(x, y, z)$ [m] | Primary Moment Axis |
| :--- | :--- | :--- | :--- | :--- |
| `0` (`F1`) | `rotor1` / `nacelle1` | `(+2.600,  0.000, 2.517)` (**East, `+X`**) | `(+2.600,  0.000, 1.980)` | Pitch (`-tau_y` when `T_1` increases) |
| `1` (`F2`) | `rotor2` / `nacelle2` | `( 0.000, +2.600, 2.517)` (**North, `+Y`**) | `( 0.000, +2.600, 1.980)` | Roll (`+tau_x` when `T_2` increases) |
| `2` (`F3`) | `rotor3` / `nacelle3` | `(-2.600,  0.000, 2.517)` (**West, `-X`**) | `(-2.600,  0.000, 1.980)` | Pitch (`+tau_y` when `T_3` increases) |
| `3` (`F4`) | `rotor4` / `nacelle4` | `( 0.000, -2.600, 2.517)` (**South, `-Y`**) | `( 0.000, -2.600, 1.980)` | Roll (`-tau_x` when `T_4` increases) |

### Body-Frame Collective Mixing Law
For a mean hover/climb collective command $c_{\text{mean}}$ and body-frame roll/pitch collective differentials $(u_{\text{roll,body}}, u_{\text{pitch,body}})$:

$$
\begin{aligned}
c_1 \text{ (East, } +X\text{)} &= c_{\text{mean}} - \Delta c_{\text{pitch,trim}} - u_{\text{pitch,body}} \\
c_2 \text{ (North, } +Y\text{)} &= c_{\text{mean}} + \Delta c_{\text{roll,trim}} + u_{\text{roll,body}} \\
c_3 \text{ (West, } -X\text{)} &= c_{\text{mean}} + \Delta c_{\text{pitch,trim}} + u_{\text{pitch,body}} \\
c_4 \text{ (South, } -Y\text{)} &= c_{\text{mean}} - \Delta c_{\text{roll,trim}} - u_{\text{roll,body}}
\end{aligned}
$$

---

## 3. Calibrated Mass, CG & Static Hover Trim Table (`R6`, `1,200 RPM`)

Because the M250-C30P turboshaft (`132 kg` in `P01`) is mounted forward of the origin (`+Y`), the whole-aircraft center of gravity has a positive $y_{\text{CG}}$ offset that must be trimmed by biasing `Rotor 2 (+Y)` collective above `Rotor 4 (-Y)`:

| Fuel State | Total Mass [kg] | Whole-Aircraft CG $(x, y, z)$ [m] | Hover Thrust / Rotor [N] | Mean Hover Collective $c_{\text{mean}}$ [deg] | Roll CG Trim $\Delta c_{\text{roll,trim}}$ [deg] | Hover Trim Collectives $[c_1, c_2, c_3, c_4]$ [deg] | Hover Shaft Power [kW] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Empty (`0 kg`)** | `986.67` | `(-0.0003, +0.0800, 1.4143)` | `2,418.98` | `16.88°` | `+0.71°` | `[16.88°, 17.59°, 16.88°, 16.17°]` | `200.4 kW` |
| **Short Test (`10 kg`)** | `996.67` | `(-0.0003, +0.0792, 1.4097)` | `2,443.50` | `16.95°` | `+0.71°` | `[16.95°, 17.66°, 16.95°, 16.24°]` | `202.5 kW` |
| **Half Fuel (`30 kg`)** | `1,016.67` | `(-0.0003, +0.0777, 1.4005)` | `2,492.53` | `17.12°` | `+0.70°` | `[17.12°, 17.82°, 17.12°, 16.42°]` | `207.8 kW` |
| **Baseline (`60 kg`)** | `1,046.67` | `(-0.0003, +0.0754, 1.3875)` | `2,566.08` | `17.38°` | `+0.69°` | `[17.38°, 18.07°, 17.38°, 16.69°]` | `216.1 kW` |
| **Max Cap (`110 kg`)** | `1,096.67` | `(-0.0003, +0.0720, 1.3673)` | `2,688.66` | `17.81°` | `+0.67°` | `[17.81°, 18.48°, 17.81°, 17.14°]` | `230.5 kW` |

- **Rotor Sensitivity at Hover (`1,200 RPM`)**:
  - $\partial T / \partial c \approx 268\,\text{N/deg}$ per rotor (`1,072 N/deg` total vertical thrust sensitivity).
  - Roll/pitch moment sensitivity: $\partial \tau_x / \partial u_{\text{roll}} = \partial \tau_y / \partial u_{\text{pitch}} = 2 \times 2.60\,\text{m} \times 268\,\text{N/deg} \approx 1,394\,\text{N}\cdot\text{m/deg}$.
  -Climb collective ceiling at `300 kW` shaft power limit: cap $c_{\text{mean}} \le 18.65^\circ$ (`~252–285 kW`) so `rotor_rpm` remains regulated at `1,185–1,200 RPM` without governor droop during sustained `+1.15 m/s` climbs.

---

## 4. Essential Calibration Findings for Next Run / Task 02 (`02_ROTORS_AND_ECU.md`)

1. **Mandatory World-to-Body Heading Transformation (`R_z(-\psi)`)**:
   - Sensor observations `attitude_xyz_deg = [phi_w, theta_w, psi]` and `gyro_world_deg_s = [wx_w, wy_w, wz_w]` are reported in the **world East-North-Up frame**.
   - Before computing body-frame rotor commands $(u_{\text{roll,body}}, u_{\text{pitch,body}})$ and nacelle vectoring $(t_{x,\text{body}}, t_{y,\text{body}})$, world errors and rates **must** be rotated by heading $\psi = \text{yaw}$:
     $$
     \begin{bmatrix} \phi_{\text{body}} \\ \theta_{\text{body}} \end{bmatrix} =
     \begin{bmatrix} \cos\psi & \sin\psi \\ -\sin\psi & \cos\psi \end{bmatrix}
     \begin{bmatrix} \phi_w \\ \theta_w \end{bmatrix}, \qquad
     \begin{bmatrix} \omega_{x,\text{body}} \\ \omega_{y,\text{body}} \end{bmatrix} =
     \begin{bmatrix} \cos\psi & \sin\psi \\ -\sin\psi & \cos\psi \end{bmatrix}
     \begin{bmatrix} \omega_{x,w} \\ \omega_{y,w} \end{bmatrix}
     $$
   - In run `20261101T232353-c7b594`, omitting this rotation worked while $|\psi| < 35^\circ$, but as $\psi \to 90^\circ$ at `t = 172.8 s`, world roll and pitch swapped axes relative to the airframe (`cos(90°) = 0`), causing immediate cross-axis positive feedback during translation.

2. **Flat-Pitch Nacelle Zeroing Gate Before Liftoff**:
   - If a sortie begins with non-zero residual nacelle tilt (`tilt_feedback_deg`), holding `collective_deg = [0, 0, 0, 0]` and `tilt_deg = [[0,0],[0,0],[0,0],[0,0]]` until `mean_rpm >= 1180` and `max(|tilt_feedback|) <= 1.0°` eliminates ground tip-over moments during spool-up.

3. **Yaw Lead Compensation & Reaction-Torque Decoupling**:
   - Tangential nacelle tilt yaw control (`[-u_yaw, 0]` on `F1`, `[0, -u_yaw]` on `F2`, `[+u_yaw, 0]` on `F3`, `[0, +u_yaw]` on `F4`) acts through the nacelle tilt actuator (`tau = 0.08 s`) + `20 ms` command delay, which produced a `~6.5 s` period lightly-damped yaw oscillation at `10 m` altitude (`t = 160..172 s`).
   - Increasing yaw rate damping ratio (`kd_yaw >= 1.2 * kp_yaw`) and decoupling differential collective reaction torque in Task 02 (`02_ROTORS_AND_ECU.md`) suppresses heading drift during hover and cruise.

---

## 5. Calibrated Baseline Gains (Ready for Next Sortie)

```json
{
  "hover_trim_10kg_fuel": {
    "c_mean_deg": 16.95,
    "c_max_climb_deg": 18.65,
    "trim_r2_r4_deg": 0.71,
    "trim_r3_r1_deg": 0.00
  },
  "attitude_loop_body_frame": {
    "kp_att_deg_per_deg": 0.62,
    "kd_rate_deg_per_deg_s": 0.32,
    "ki_att_deg_per_deg_s": 0.24,
    "max_u_att_deg": 3.50
  },
  "altitude_loop": {
    "kp_z_deg_per_m": 1.15,
    "kd_vz_deg_per_mps": 1.65,
    "ki_z_deg_per_m_s": 0.35
  },
  "position_and_yaw_loop": {
    "kp_pos_deg_per_m": 0.32,
    "kd_vel_deg_per_mps": 0.45,
    "kp_yaw_tilt_deg_per_deg": 0.45,
    "kd_yaw_tilt_deg_per_deg_s": 0.85
  }
}
```
