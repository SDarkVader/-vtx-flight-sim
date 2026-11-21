# Ricochet hydrodynamics and aerodynamics

Source: `src/vtx/water/hydrodynamics.py` (`evaluate_mesh_hydrodynamics`), `src/vtx/water/datum.py` (`HydroCalibrationProfile`), `src/vtx/ricochet/plant.py` (`_evaluate_and_cache_hydro`, `_compute_aero_and_propulsion`) and `src/vtx/ricochet/spec_math.py` (`canopy_and_craft_cd0`).

## Water forces

Water forces are integrated over the closed triangle meshes of three bodies: the main hull and the two sponsons. Each is evaluated against the live water surface and applied to its own MuJoCo body. Each evaluation:

1. samples the water surface at every mesh vertex;
2. clips the triangles at the waterline;
3. samples the water again at the centre of every wetted triangle.

| Term | Model | Coefficient (profile `f03-provisional-v1`) |
| --- | --- | --- |
| Buoyancy | ρ g V_sub, at the centre of buoyancy of the clipped volume, scaled by local wet fraction near shores | n/a |
| Skin friction | ITTC-57: C_f = 0.075 / (log₁₀ Re − 2)², with Re floored at 2 × 10⁴, plus roughness allowance; multiplied by (1 + k) and a shallow-water factor; acts against tangential panel flow | ΔC_f 4.0 × 10⁻⁴; k 0.18 |
| Shallow-water resistance factor | 1 + 0.35 / max(h/T − 0.65, 0.45)², clipped to 1.0..3.2, where h/T is depth over draft | n/a |
| Normal pressure drag | ½ ρ C_d \|v_n\| v_n per panel: full C_d advancing into water, 35% of it retreating | C_d 1.05 |
| Planing (dynamic) lift | On downward-facing panels advancing into the water: ½ ρ C_L v_n \|v\| × deadrise factor | C_L 0.35 |
| Aft skeg lift (main hull) | Lateral lift at 28% of hull length aft, opposing sideslip; area = min(0.45 × wetted area, 0.65 × L × draft) | 0.15 |
| Wave excitation | Froude–Krylov dynamic pressure on wetted panels | Scale 1.0; diffraction damping 0.25 |
| Added mass, translation | Factor × displaced mass | Surge 0.08, sway 0.85, heave 0.65 |
| Added mass, rotation | Factor × displaced mass × arm² | Roll 0.25, pitch 0.55, yaw 0.45 |
| Shallow-keel added mass | Heave added mass × up to 2.5, pitch × up to 2.0, when keel clearance < 2 × draft | n/a |
| Radiation damping | Linear damping ratios on heave, roll and pitch; yaw = 0.35 × pitch | Heave 0.22, roll 0.36, pitch 0.28 |
| Quadratic roll damping | −440 \|p\| p | 440 N·m·s² |
| Munk moment | Kirchhoff–Munk moment −v × (Mₐ v), scaled by a viscous relief factor | 0.35 |
| Wet/dry blend | Smooth immersion band at the waterline | 0.03 m |

Water properties: ρ = 999.1 kg/m³ (fresh water, 15 °C), ν = 1.139 × 10⁻⁶ m²/s.

### Whole-vehicle added-mass coupling

Added mass is not applied per body in isolation. The plant combines the three bodies' added mass and added inertia about the vehicle centre of mass. It then solves the vehicle acceleration with (M + Mₐ) and (I + Iₐ), and gives each body its share of the added-mass reaction (`_evaluate_and_cache_hydro`). This avoids the instability of an explicit added-mass force on light bodies such as the 12 kg sponsons.

### Cadence

- **Standalone plant:** hydrodynamics are evaluated every 400 Hz step by default (`hydro_stride` 1).
- **Harbour fleet:** they are evaluated every fifth 100 Hz step (20 Hz). Between evaluations the force on each body is extrapolated to the middle of the current step from the two latest samples, using the causal Adams–Bashforth weights 3/2 and −1/2 (`causal-linear-midpoint-ab2-v1`). Each wrench component is clipped to ±8 × 10⁴.

### The wake the craft leaves

After each harbour step the craft also pushes momentum into the shared shallow-water field. The push is the reaction to its hull resistance, lift and damping, plus 25% of fan thrust as propwash. It is spread as a Gaussian over a radius of max(4.5 m, 0.75 × length), and cells are capped below their Froude limit. Analytical Kelvin wakes are drawn from the same state.

## Air forces

Air forces use body-frame airflow, v_air = v − wind. Dynamic pressure is q = ½ × 1.225 × V².

### Wing, hull and fuselage

| Term | Model |
| --- | --- |
| Wing lift | C_L = 0.25 + 4.2 α on S = 15.50 m²; cut to 20% when moving backwards (u < −0.2 m/s) |
| Wing drag | C_D = C_D0 + 0.048 C_L² |
| C_D0, Concept A | 0.0354: clean airframe 0.0325 plus canopy 0.0029 (24° windshield rake, fineness ratio 4.0) |
| C_D0, F03 | 0.0450: clean airframe 0.0325 plus canopy 0.0125 (82° rake, fineness ratio 2.2) |
| Hull axial drag area | Concept A 1.925 m²; F03 3.04 m² |
| Lateral drag area | 3.8 m² |
| Vertical drag area | 4.5 m² |
| Rotational damping | −(120 p, 180 q, 160 r) N·m |
| Air Munk moment | Added-mass diagonal (0.8, 3.8, 4.5) kg |
| Directional stiffness | Weathercock yaw moment = q_rudder × S × b × 0.095 sin β × 0.18 |

Angles of attack α and sideslip β use floors on the axial speed (0.8 m/s and 0.5 m/s) so they stay finite near rest.

### Control surfaces

Each surface sees its own local airflow, including the rotation of the craft. The elevator and rudder also get 55% of the fan slipstream speed.

| Surface | Area (m²) | Chord (m) | Force from deflection δ (rad) | Drag | Hinge-moment clip |
| --- | ---: | ---: | --- | --- | ---: |
| Aileron (each) | 0.72 | 0.42 | F_z = −2.2 q S δ | −0.18 q S δ² | ±45 N·m |
| Elevator | 1.15 | 0.36 | F_z = −2.35 q S δ | −0.22 q S δ² | ±55 N·m |
| Rudder | 1.15 | 0.44 | F_y = −2.45 q S δ, plus fin −0.725 q S sin β | −0.20 q S δ² | ±55 N·m |

Moments come from each surface's lever arm about the CG. Hinge moments, −C_h q S c (k_α α + k_δ δ), act on the surface joints, so the servos work against real loads.

The rudder's yaw coefficients (C_nβ 0.095, C_nr −0.18, C_nδr 0.14) are reported as the telemetry value `cn_yaw`.

## What this means at the helm

- **Slow speed:** the craft floats on the hull with the sponsons 0.20 m immersed at the 0.56 m design draft. Steering comes from fan slipstream over the rudder and from differential thrust. The wing does little.
- **Building speed:** planing lift on the forward bottom panels and wing lift both rise with the square of speed, so the hull lifts and wetted area and drag fall.
- **Roll:** the sponsons resist roll through buoyancy and radiation and quadratic damping; their struts flex up to ±0.06 m.
- **Stopping:** bring the reverse buckets past 64.5% (54.8°) and the net fan thrust reverses. At full deployment it reaches 55% of gross thrust astern.
