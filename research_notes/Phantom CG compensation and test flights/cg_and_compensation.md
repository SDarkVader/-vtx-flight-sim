# VTX Phantom A9: independent CG envelope, pitch-balance compensation, wing-stagger requirements for A10, and feasibility proposals

*Research date: 2026-11-03. Scope: the VTX MuJoCo simulator design point only; no airworthiness claim is made.*

*Labels: MEASURED-K (measured from `assets/derived/phantom-a9-cassette.blend`, headless and read-only), DERIVED (computed here from labelled inputs), SYNTHETIC_UNVALIDATED (shortened to SYNTHETIC: an assumption), MANUFACTURER, REGULATORY_REFERENCE.*

*Frame: CAD X forward, Z up, metres. `evidence/phantom/phantom_geometry.json` says "+Y = CAD-RIGHT, physical left". Objects named R sit at +Y, and the driver seat is at −Y. Wing "R" (+Y) sits at z 1.00 and wing "L" (−Y) at z 0.88.*

*Method:* Blender ray-cast measurement (scratch `measure_cg.py`), ledger and Monte Carlo (`cg_study.py`), a horseshoe vortex-lattice model (`vlm_study.py`) and hover/proposal calculations (`extra.py`). All scripts are in the session scratchpad. No tracked file was edited.

*Inputs:*
- Masses from the sibling note `propulsion_and_energy_components.md` (same folder), cited as "sibling".
- A9 articulated bodies from `evidence/phantom/a9_handover.json`.
- The pod and leg masses in that handover are "A8 PLACEHOLDER" values, so they were **not** used.

*Build ledger:* `evidence/phantom/phantom_mass_ledger.json` and `cg_ledger_from_build.md` were still absent on the final check (2026-11-03), so no item-by-item comparison was possible.

## 1. Where is the CG, configuration by configuration?

### Takeaway
- **Baseline packaging:**
  - CG is at x = −0.56 m (5–95%: −0.60 to −0.50), y = 0, z = 0.53–0.55.
  - Mass is about 1,610 kg (1,490–1,680). That is 0.54 m aft of the four-pod thrust centroid at x −0.025.
- **Approved fix** (buffer battery and avionics in the nose; fuel in the vacated under-floor bay):
  - N1, battery centroid at x 1.60: CG x ≈ −0.29 (−0.33 to −0.23).
  - N2, battery against the front bulkhead at x 1.24, with the radiator moved forward into the nose: CG x ≈ −0.31 (−0.36 to −0.25).
- **Configuration and loading effects are small** (each change is at most ±0.016 m) because the cassette moves mass only sideways:
  - wing deploy or stow, and canard fold: Δx ≈ 0;
  - legs: Δz ≈ −0.011;
  - driver only: Δy ≈ −0.016;
  - reserve fuel: Δx about ±0.01.
- **The dominant uncertainty is the mass of what sits at each end:**
  - nose: battery, front pods, cooling;
  - tail: turbogenerator (TG), rear pods, boosters.

### Cited Findings
- **Measured geometry** (MEASURED-K, Blender, frame 240):
  - Hull: outer area 36.11 m², area centroid x −0.393, z 0.669; volume 4.614 m³; ∫w²dx = 17.71 m³.
  - Tub panels: 18.7 m² two-face area, centroid x −0.187.
  - Fender/fin group: 13.5 m², centroid x +0.11.
  - Nose free box: x 1.35–1.85, |y| ≤ 0.40, z 0.22–0.51, 0.136 m³.
  - Under-floor bay: x −0.96…0.84, |y| ≤ 0.27, z 0.21–0.31, about 0.097 m³ gross.
- **Ledger inputs:**
  - TG600-class: 270 kg (240–320) at x −1.85 (DERIVED, sibling).
  - Pods: 63 kg each (50–85) (DERIVED, sibling).
  - Boosters: 35 kg each (SYNTHETIC, sibling).
  - Buffer battery: 193 kg (180–225) (DERIVED, §6).
  - Hull skin: 2.6/3.2/4.0 kg/m² (SYNTHETIC).
  - Occupants: 80 kg each (SYNTHETIC; AC 120-27F uses 190–195 lb ≈ 86–88 kg, [FAA AC 120-27F](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_120-27F.pdf)).
  - Fuel: 90 kg full and 20 kg reserve (SYNTHETIC).
  - A9 articulated parts: 140.5 kg (repo).
- **Results** (DERIVED; `cg_study.py`):

| Config / load | Baseline M, CG (x, y, z) | N1 CG (x, y, z) | N2 x |
|---|---|---|---|
| Road, 2 occupants, full fuel | 1,614, (−0.564, 0, 0.545) | (−0.291, 0, 0.546) | −0.314 |
| Road, 1 occupant, reserve | 1,464, (−0.564, −0.016, 0.538) | (−0.303, −0.016, 0.546) | −0.329 |
| Hover (legs out), 2 occupants, full | (−0.564, 0, 0.534) | (−0.291, 0, 0.535) | −0.314 |
| Hover, 1 occupant, reserve | (−0.564, −0.016, 0.525) | (−0.303, −0.016, 0.533) | −0.329 |
| Wingborne, 2 occupants, full | (−0.564, 0, 0.545) | (−0.291, 0, 0.546) | −0.314 |
| 2 × 100 kg, full | 1,654, x −0.557 | x −0.290 | −0.313 |
| 1 × 60 kg, reserve | 1,444, x −0.568 | x −0.303 | −0.329 |
| Monte Carlo 5/50/95% (x) | −0.595 / −0.547 / −0.501 | −0.332 / −0.280 / −0.228 | −0.355 / −0.303 / −0.251 |

- **Inertia** (DERIVED; point masses, about the CG, kg·m²):
  - Baseline wingborne: Ixx 478, Iyy 1,850, Izz 2,211, Ixz −25.
  - N1 wingborne: Ixx 475, Iyy 2,694, Izz 3,058, Ixz −103.
  - Wing stow lowers Ixx by about 90. Distributed hull self-inertia adds about +250 to Iyy (SYNTHETIC, box approximation).
- **Tornado, N1** (Δx_cg from each item's low to high mass/position):

| Item | Δx_cg (m) |
|---|---|
| Battery mass | 0.052 |
| Front pods | 0.040 each |
| Rear pods | 0.028 each |
| Cooling | 0.030 |
| Boosters | 0.017 |
| Avionics | 0.015 |

### Inferences
- The nose packaging fix moves the CG about 0.27 m forward at a cost of +6 kg of harness. That is about half of the 0.54 m gap to the thrust centroid.
- With the fix, the TG is no longer the largest uncertainty (its tornado span is ±0.006). The nose-mass budget is.
- The fuel capacity of the under-floor bay is about 85 L, or 68 kg of Jet-A. Carrying a full 90 kg needs a second cell of about 22 kg in the under-sleeve bay at x ≈ −1.0. That moves the full-fuel N1 CG by about −0.013 m.

### Gaps
- No real TG600 mass has been published. The pod motor and fan masses, the hull laminate, the seat H-point and the full fuel load are all SYNTHETIC.
- No CAD build ledger exists to compare against.

## 2. Hover: thrust centroid vs CG, trim split, margin

### Takeaway
- The thrust centroid is at x −0.025, y 0, z 0.42 (MEASURED-K pivots at 1.54 / −1.59, ±1.04).
- **Rear-pod share:**
  - baseline: 67%;
  - N1: 58.5%;
  - N2: 59%.
- The sibling's thrust_max is 3,700 N per pod, so **no packaging configuration can hover at the ledger mass**:
  - the most-loaded pod needs 1.26–1.44 × T_max;
  - the hover-capable mass with all margin consumed is 1,122 kg (baseline) or 1,290 kg (N1);
  - with 25% of control reserve it is 842 kg or 968 kg.
- Pod tilt is about X, so it cannot give pitch. Pitch trim must come from front/rear thrust differential only.

### Cited Findings
DERIVED (`extra.py`; momentum theory, with power ∝ T^1.5):

- **Equal-pod requirement:** at a 25% reserve, equal pods need T_max = 7,093 N each (baseline, installed T/W 1.79) or 6,196 N (N1, T/W 1.56).
- **Unequal pods for N1:** front 4,396 N and rear 6,196 N.
- **Ideal power penalty from the unequal split:**

| Configuration | Rear share | Power penalty |
|---|---|---|
| N1 | 0.585 | +1.1% |
| Baseline | 0.672 | +4.5% |

- **Pod power:** the rear pods draw 1.32× (N1) and 1.55× (baseline) the equal-split power.
- **Roll trim, driver only:** y_cg −0.0155, giving a left/right thrust split of 50.7% / 49.3%. This is negligible.
- **Sibling finding:** a single TG600 cannot hover the vehicle at 1,300 kg (T/W 0.72) (sibling notes).

### Inferences
- The CG fix is necessary but not sufficient. Hover needs either more thrust per rear pod, aft lift (boosters), or a pod centroid closer to the CG (§8).
- Control margin should be defined as T_max − T_trim on the most-loaded pod. A minimum of 25% is proposed for simulator test cards.

### Gaps
- No pod fan map, ground-effect data or thrust lapse in tilt.
- 3,700 N per pod is the sibling's DERIVED value.

## 3. Wingborne: neutral point, static margin, canard-first stall, trim

### Takeaway
- **Neutral point (NP), canard plus wing, no body:**
  - x_np = −0.72 by VLM, more aft than the repo's −0.57 because the VLM includes canard downwash on the wing.
  - Wing height has no effect: −0.721 staggered vs −0.721 at a common height.
- **Body pitching moment dominates and is bounded:**

| Body model | NP x (m) |
|---|---|
| Munk on volume | −0.28 |
| Flat-plate planform (VLM) | +0.09 |
| Multhopp, with aft-body downwash at 0.6 | +0.22 |
| Multhopp, full | +0.84 |

- **Static margin at N1 (x −0.29):**

| Body model | Static margin |
|---|---|
| No body | +49% MAC |
| Munk | −1% |
| Flat plate | −43% |
| Multhopp, full | −130% |

- **Static margin at the baseline CG (−0.56):** +18% / −33% / −75% / −161%, in the same model order.
- **The vehicle is probably statically unstable in pitch.** Fly-by-wire (FBW) relaxed-stability augmentation is mandatory.
- **Canard sizing conflict:** with a canard CLmax of 1.0, canard-first stall needs the CG forward of about −0.54 (clean) or −0.60 (flapped). Moving the CG forward then raises the canard-limited minimum speed.
  - At 1,300 kg: 62.5 m/s at −0.55, 68 at −0.45, 81 at −0.30, 101 at −0.025, against a wing-only stall of 65 m/s.
  - So **the approved fix gives a hover-friendly CG but makes the present canard too small**: Vmin is about 81–90 m/s at N1.

### Cited Findings
- **VLM** (DERIVED; `vlm_study.py`, 30 mm vortex core):
  - Isolated wing: CLα 4.26 /rad vs Helmbold 4.67 (A 6.64).
  - Canard plus wing: CLα 4.39–4.47 /rad. The canard carries about 7% of the lift increment.
  - Repo geometry: S 4.055, MAC 0.872, canard 2 × 0.278 m² at z 0.95 (`a9_handover.json` aero_surfaces).
  - Canard area ×1.5 moves the NP to −0.63; ×2.0 moves it to −0.56.
- **Munk term** (repo method, `engineering/phantom/wing_loads.py`): 2 · 4.614 · 0.85 = 7.84 m³/rad, giving +0.44 m.
- **Multhopp term:** (π/2) · 17.71 = 27.8 m³/rad, giving +1.56 m.
- **Stall speeds,** wing only:

| Mass (kg) | Clean, CLmax 1.2 (m/s) | Flapped, CLmax 1.6 (m/s) |
|---|---|---|
| 1,100 | 60.2 | 52.1 |
| 1,300 | 65.4 | 56.6 |
| 1,400 | 67.9 | 58.8 |
| 1,550 | 71.4 | 61.8 |

- **Trimmed canard CL at clean wing stall** (1,300 kg):
  - 0.76 at −0.55, 1.10 at −0.45, 1.43 at −0.35;
  - canard loading 2.0 / 2.9 / 3.8 kPa vs wing loading 2.6–2.9 kPa;
  - same CLs at 1,100 and 1,400 kg (loadings scale with mass).
- **Canard-first-stall aft CG limit** (cm0 neglected):

| Wing CLmax | Canard CLmax 0.9 | 1.0 | 1.1 |
|---|---|---|---|
| 1.2 | −0.563 | −0.539 | −0.515 |
| 1.6 | −0.619 | −0.600 | −0.582 |

- **Time to double** (DERIVED; Cmq −5.7 and Iyy 2,950 SYNTHETIC):

| Instability (MAC) | 70 m/s | 120 m/s | 178.8 m/s |
|---|---|---|---|
| −10% | 0.71 s | 0.42 s | 0.28 s |
| −30% | 0.37 s | 0.21 s | 0.14 s |

- **X-29 reference:** −35% MAC with T2 of about 0.14–0.15 s, flown with triplex digital FBW ([NASA NTRS 19900002437](https://ntrs.nasa.gov/citations/19900002437)).

### Inferences
- The aft CG limit is min(NP − 5% MAC with FBW authority, canard-first-stall limit). The forward limit is the CG at which canard-limited Vmin becomes unacceptable.
- **With the present canard, the usable CG band is roughly −0.60 to −0.45.** Hover wants about −0.03. This is the core conflict.
- Resolve it with a larger canard or a canard flap (§8), not with CG movement.

### Gaps
- Body Cm is not known within a factor of about 4. Wind-tunnel or CFD data on the hull is required.
- Canard CLmax (NACA 0009, low Reynolds number), flap Cm (−0.10 used) and canard/wing interference at stall are all SYNTHETIC.

## 4. Lateral and vertical: driver-only seating, roll trim, wing stagger, A10 requirements

### Takeaway
- **Driver-only seating** shifts y by −0.016. Roll trim needs a 1.4% left/right pod differential in hover, or about 0.2° of aileron wingborne.
- **z_cg** is 0.53–0.56: 0.11–0.14 above the pod thrust line (z 0.42) and 0.39 below the wing.
- **Stagger, potential-flow results:**
  - No effect on the NP. The linear Clβ depends only on the *mean* wing height.
  - Zero-sideslip rolling moment: Cl ≈ −0.0003 to +0.0008 at α 6°, about 0.15–0.35° of aileron.
  - Left/right lift difference: −0.45% for the wing alone, −2.5% with body crossflow.
  - Mass products: Iyz +3.6 kg·m², which is negligible.
- **Incidence mismatch matters more than height:** a 0.1° left/right incidence difference gives Cl 0.00064, about twice the effect of the whole 0.12 m stagger.
- **Where the stagger really matters**, by inference (not computed in potential flow):
  - asymmetric viscous junction flow: the upper wing exits at the sleeve top and the lower one at mid-cell;
  - asymmetric stall onset;
  - different root stiffness in the upper and lower sleeve cells;
  - asymmetric aeroelastic twist.
- **The owner's A10 decision is supported**, chiefly for structural and stall symmetry.

### Cited Findings
DERIVED (`vlm_study.py`):

- **Clβ, cylinder crossflow** (R 0.79, axis z 0.62) — "+" means the windward (+Y) wing lifts, i.e. stabilising:

| Wing height | Clβ (/deg) |
|---|---|
| Staggered | +0.00178 |
| Common 0.94 | +0.00174 |
| Common 1.00 | +0.00195 |
| Common 0.88 | +0.00161 |

- **Stagger nonlinearity** (Cl(+5°) + Cl(−5°) − 2·Cl(0)): +0.00004.
- **Residual height difference Δz at α 6°, with the body:**

| Δz (m) | Cl |
|---|---|
| 0.01 | −0.00003 |
| 0.02 | −0.00007 |
| 0.05 | −0.00027 |
| 0.12 | −0.00031 |

- **Incidence difference:** 0.10° → 0.00064; 0.25° → 0.0016; 0.5° → 0.0032.
- **Aileron authority** Clδa ≈ 0.0022 /deg (strip theory, τ 0.64, repo aileron data).
- **Effect of a common height on CG:** z changes by at most +0.0015 m (wings at 1.00); x is unchanged.

### Inferences
**A10 requirements (proposed):**

| Requirement | Limit | Basis |
|---|---|---|
| Residual height difference | ≤ 10 mm | Cl < 1e-4, about 0.05° aileron |
| Left/right incidence match, including root fit | ≤ 0.05° | |
| Twist under 1 g | Matched within 0.05° | |
| Root bending stiffness | Matched within 5% | SYNTHETIC |
| Mass per side | Matched within 0.2 kg | Δy < 0.0003 m |
| Common wing height | 0.94–1.00 | Higher gives slightly more Clβ (+0.0002/deg) and a slightly higher CG |

- A common height leaves the NP and the CG effectively unchanged. Each wing should be modelled as its own MuJoCo body with mirrored inertia.

### Gaps
- Potential flow cannot show the viscous junction or stall asymmetry. A CFD or tunnel run of A9 vs A10 at α 10–16° and β ±10° is needed.
- The body crossflow is modelled as a cylinder, although the hull is flat and wide (2.45 m).

## 5. Transients

### Takeaway
None of the configuration transients needs CG compensation.

| Transient | Effect |
|---|---|
| Wing deploy/stow | Pure Y motion. Δx = Δz = 0; ΔIxx ≈ +90 kg·m². An asymmetric (one-wing) failure gives Δy 0.016–0.021 m: ~1.5% pod differential in hover, ~6° aileron if wingborne. |
| Canard fold | Δx ≈ +0.0002 m |
| Legs | Δz −0.011 m, Δx 0.000 m |
| Fuel burn, 90 → 20 kg (N1) | Δx −0.010 m (CG moves aft) |
| Fuel burn (baseline) | Δx +0.015 m |
| Occupant exit | Δx ≤ 0.013 m; Δy 0.016 m |

### Cited Findings
- DERIVED from the ledger tables in §1.
- Body COM poses from `evidence/phantom/a9_handover.json`: wing slide 20.74 kg, y ±1.292 deployed and ∓0.078 stowed.

### Inferences
- The FBW should schedule trim on configuration state (wing position, legs, fuel quantity) at a rate of about 1 Hz. No mechanical compensation is needed for transients.
- The one-wing-stuck case must be a tested failure mode.

### Gaps
- Deploy timing under load, and the aerodynamic transient during sliding, are not modelled.

## 6. Approved fix: sizing the parts and mounts

### Takeaway
**Battery:**
- Molicel P50B 21700 cells, 192s10p:
  - 1,920 cells × 71 g = 136 kg of cells;
  - 34.6 kWh; 691 V nominal / 806 V maximum (800 V bus);
  - 600 A continuous, ≈ 400 kW.
- Pack 193 kg (180–225). Volume 0.047 m³ of cells, or 0.09–0.11 m³ packed.
- Option N1 fits the 0.136 m³ nose box.
- Option N2 sits behind the front bulkhead in a 0.13 m³ box (x 0.96–1.52), with the radiator moved forward beside the ram inlets (x 1.8–2.1).

**Avionics:**
- 18 kg (14–25) at x 1.95, including triplex flight-control computers, e.g. Veronte Autopilot 4x at 750 g each.

**Fuel:**
- A bladder in the under-floor bay: about 85 L usable, centroid x −0.06.
- Plus a 22 kg cell in the under-sleeve bay.
- Boost pumps: Weldon 8150-B class.

**Recommendation:** N2. It costs 0.023 m of CG but gives about 1.1 m of crush length ahead of the pack, against about 0.6 m for N1. That matters because a road car's nose is its crush zone.

### Cited Findings
- **Cells:** P50B 60 A continuous, 260 Wh/kg, 714 Wh/L ([Molicel P50B datasheet](https://www.fsaeonline.com/content/Molicel-TDS--INR-21700-P50B-80122.pdf); MANUFACTURER). 71 g maximum (sibling notes). Pack factor 0.70 (SYNTHETIC).
- **Avionics:** Veronte 4x triple-redundant autopilot, 750 g ([NWUAV Autopilot 4x datasheet](https://www.NWUAV.com/media/veronte/Autopilot-4x-datasheet.pdf); MANUFACTURER).
- **Fuel cells:** ATL bladder cells ([ATL 33-gallon Sprint cell](https://atlinc.com/ATL-33-Gallon-Sprint-Fuel-Cell.html); MANUFACTURER; a 33 gal cell weighs about 11 lb).
- **Pumps:** Weldon 8150-B: 35 GPH, 24 V, 2 A, ≤ 2.6 lb (Aircraft Spruce listing; MANUFACTURER).
- **Crash loads** (REGULATORY_REFERENCE, unconfirmed):
  - ECE R100 mechanical shock: up to about 28 g for about 80 ms depending on vehicle class ([TÜV SÜD R100](https://www.tuvsud.com/en-us/industries/mobility-and-automotive/automotive-and-oem/automotive-testing-solutions/battery-testing/un-ece-r100)).
  - CS-23 emergency-landing factors: not verified.
- **Design mount load:** 193 kg × 28 g = 53 kN forward (DERIVED).

### Inferences
- Mount the pack on a CFRP or titanium cradle bolted to the front bulkhead, sized for 53 kN forward, 20 kN vertical and 15 kN lateral (SYNTHETIC split).
- Add an intumescent and thermal barrier and a vent path away from the radiator inlets.
- Relocating the radiator for N2 must keep the 45 kW zero-airspeed rejection capacity (sibling), so the fan-assisted inlet ducts need rerouting.

### Gaps
- Bracket allowables are not invented here; size the brackets from the certified allowables of the chosen alloy.
- Duct routing in the nose is unverified in CAD.
- R100 and CS-23 values still need primary-text confirmation.

## 7. Compensation options: products, effect, failure modes, MuJoCo representation

### Takeaway
Ranked by usefulness:

1. Packaging (approved).
2. FBW relaxed-stability augmentation plus configuration-scheduled trim (mandatory).
3. Front/rear pod thrust differential (already the hover pitch effector).
4. Booster thrust vectored down in hover (PROPOSAL).
5. Leg load-cell CG estimator as a take-off gate.
6. Removable ballast for simulator and early tests.

Active battery sleds, fuel transfer and seat rails move the CG by at most 0.07 m, so they are not worth their mass and complexity.

### Cited Findings
CG shift per kg·m moved is 1/M ≈ 0.00062 m per kg·m (DERIVED).

**Battery sled**
- Hardware: Thomson Electrak HD: 16 kN dynamic / 18 kN static, 100–1,000 mm stroke, ≤ 71 mm/s, 6.5–12.2 kg ([Thomson](https://thomsonlinear.com/en/products/linear-actuators/electrak-hd); MANUFACTURER).
- Effect: 193 kg × 0.3 m gives Δx 0.036 m in about 4 s; 0.6 m gives 0.071 m.
- Failure modes: jam or runaway; crash unlock.
- Mitigation: an irreversible screw, mechanical locks, position sensors and flight-phase gating.
- MuJoCo: a body with a slide joint (range ±0.15), a position actuator (forcerange ±16,000) and power P = |F·v|/0.8.

**Fuel transfer**
- Hardware: Weldon 8150-B, 35 GPH ≈ 0.037 L/s.
- Effect: moving 30 kg over 1 m gives 0.019 m in about 15 min, which is too slow and too small.
- Precedent: Concorde moved about 20 t to shift its CG about 2 m ([Heritage Concorde](https://www.heritageconcorde.com/fuel-transfer)).
- MuJoCo: per-tank mass updates via `model.body_mass` with mj_setConst.

**Seat rails**
- Effect: ±0.1 m × 160 kg gives ±0.010 m.

**Ballast**
- Effect: 20 kg in the nose at x 2.1 gives +0.03 m. It is dead mass.
- Precedents: the Switchblade used batteries as movable ballast ([Samson](https://www.samsonsky.com/?p=7551)); gliders specify a front-seat ballast minimum, e.g. 70 kg in the Twin Astir handbook.
- MuJoCo: a weld-fixed body whose mass is set per test card.

**FBW and canard augmentation**
- Precedents: YF-16 relaxed static stability ([NTRS 19760024050](https://ntrs.nasa.gov/citations/19760024050)); X-29 (§3).
- Requirements: actuator bandwidth well above 1/T2 (T2 ≥ 0.14 s, so ≥ 5–10 Hz). The canard pitch effectors (EMA) need about 60°/s (SYNTHETIC).
- MuJoCo: position actuators on the canard pitch joints (`A9_JOINT_CANARD_*_PITCH`) with kp and a velocity limit; the controller runs in Python.

**Pod thrust differential**
- Response: spool time 0.15–0.3 s (sibling, SYNTHETIC).
- MuJoCo: per-pod `site` motors with gear "0 0 1 0 0 0"; power from momentum theory.

**Booster vectoring**
- Hardware: the existing ceramic directional nozzles.
- MuJoCo: two site actuators per booster (axial and vertical components) with the constraint |T| ≤ 2,420 N.

**Weight and balance by leg load cells**
- Precedent: the Airbus A330/A340 weight-and-balance system, certified with < 1% weight error (SAWE paper 2450). Onboard weight-and-balance patents US7967244 and US8340892.
- MuJoCo: `force` sensors at the leg-foot sites; x_cg = Σ(F_i·x_i)/ΣF_i.

**Patented battery-shifting precedents**
- [US10543905](https://patents.google.com/patent/US10543905) (Kitty Hawk) and EP3594113. The latter claims up to 20% power saving.

### Inferences
- In hover, CG error appears directly as pod differential. A pre-flight estimate accurate to about 0.02 m (about 2% of pod load) is achievable and sufficient.

### Gaps
- No Exlar GSX weights.
- The FBW bandwidth requirement still needs a linear model.

## 8. Feasibility PROPOSALS beyond the approved fix (each needs owner approval)

### Takeaway
All figures are for N1 at 1,620 kg unless noted.

| Proposal | Hover split (rear share) | Pod T_max for 25% reserve | Wingborne effect | Cost / risk |
|---|---|---|---|---|
| P1 Unequal pods (up-rated rear fans) | 0.585 | Front 4.4 kN, rear 6.2 kN | None | Two pod variants; rear fans about 1.32× power |
| P2 Rear pods moved aft to x −2.12 | 0.50 | 4.0 kN each | Wheelbase changes; collides with the booster boxes (x −2.05…−1.48) | Major styling and packaging change |
| P3 Boosters vectored down, 2,000 N total | 0.49 | 4.7 kN each (T/W 1.18) | None | About 250 kW of booster power in hover (8 N/kW vs 10 N/kW for the pods); nozzle heat on the ground |
| P4 TG moved forward to x −1.40 (−1.00) | 0.56 (CG −0.22; −0.15) | 5.9 kN | Iyy −330 | Under-sleeve bay space and exhaust routing |
| P5 Canard area ×1.5 with plain flap (CLmax 1.5) | — | — | Vmin at 1,300 kg: 59 m/s at −0.30, 63 at −0.15, 69 at −0.025; NP −0.63 | Larger canard: identity and stowage |
| P5b Canard ×2.0 with flap | — | — | Vmin 57–60 down to CG −0.025; NP −0.56 | Stowage geometry |
| P6 Mass to 1,300 kg target (N1) | 0.585 | Rear 5.0 kN | Vmin −10% | Mass programme |

**Best feasible combination:**
- N2 packaging;
- P3 booster assist for hover;
- P5 enlarged canard with a flap;
- mass reduction toward 1,300–1,400 kg;
- uprated pods to at least 5 kN, with a second TG or a larger buffer per the sibling.

This keeps the Phantom shape (four pods, cassette, canards) and closes both hover and low-speed wingborne trim.

### Cited Findings
- DERIVED: `extra.py` and the `cg_study.py` proposal table.
- Booster data: 2,420 N at 300 kW (sibling; DERIVED).

### Inferences
- **P5 is the key aerodynamic enabler.** Without it, any CG that suits hover gives a minimum wingborne speed of 80–110 m/s.
- **P3 is the cheapest hover enabler** because the boosters and their directional nozzles already exist.

### Gaps
- Booster downward-thrust efficiency, ground erosion and heating.
- Canard stowage at ×1.5 area is unchecked in CAD.
- Pod up-rating mass penalty.

## 9. Precedents

### Takeaway
Every relevant precedent either solved CG with active FBW, or solved it with design-time packaging and ballast. None uses large in-flight mass movement, except Concorde (fuel at tonne scale).

### Cited Findings
- **Concorde:** about 20 t of fuel transfer, CG shift about 2 m ([Heritage Concorde](https://www.heritageconcorde.com/fuel-transfer)).
- **YF-16:** relaxed static stability with FBW ([NTRS](https://ntrs.nasa.gov/citations/19760024050)).
- **X-29:** −35% MAC ([NTRS](https://ntrs.nasa.gov/citations/19900002437)).
- **Beech Starship:** variable-sweep canard to offset flap pitching moment; a translating foreplane was rejected ([Wikipedia](https://en.wikipedia.org/wiki/Beechcraft_Starship)).
- **Piaggio P.180:** foreplane flaps deploy with the main flaps ([three-surface aircraft](https://en.wikipedia.org/wiki/Three-surface_aircraft)).
- **Lilium:** canard design narrows the CG range ([Leeham](https://leehamnews.com/2022/07/29/bjorns-corner-sustainable-air-transport-part-30-lilium-jet-vtol/)).
- **Samson Switchblade:** battery ballast ([samsonsky](https://www.samsonsky.com/?p=7551)).
- **Klein Vision AirCar:** extending tail, certificate of airworthiness ([GA News](https://generalaviationnews.com/2025/05/11/flying-car-production-prototype-unveiled)).
- **Terrafugia Transition:** mass growth to a 1,430 lb MTOW exemption ([Wikipedia](https://en.wikipedia.org/wiki/Terrafugia_Transition)).
- **AeroMobil 4.0:** central cradle holds the power unit and anchors the wings ([airport-technology](https://www.airport-technology.com/projects/aeromobil-4-0-flying-car/)).
- **PAL-V Liberty** ([airport-technology](https://www.airport-technology.com/projects/pal-v-liberty-flying-car/)).
- **Tandem eVTOL stability:** [TU Delft](https://research.tudelft.nl/files/144857449/6.2022_1029.pdf).

### Inferences
- The P.180 and Starship experience directly matches the Phantom's flap-plus-canard trim problem. It favours a canard flap (P5).

### Gaps
- Numeric F-16 static margin.
- Long-EZ ballast figures.
- Starship sweep angles.
- CG data for AeroMobil, PAL-V and Terrafugia.

## 10. Ranked recommendation

### Takeaway
1. **Implement N2** (nose battery behind the bulkhead, radiator forward, avionics in the nose, fuel cell under the floor plus a 22 kg under-sleeve cell). CG x −0.31 (−0.36 to −0.25).
2. **Treat the vehicle as statically unstable in pitch.** Build FBW relaxed-stability augmentation on the all-moving canards, with configuration-scheduled trim. Take the aft limit from body-Cm data once measured.
3. **Hover pitch trim via front/rear pod differential,** with a leg load-cell CG gate before every lift-off. Require a 25% reserve on the most-loaded pod.
4. **PROPOSALS for the owner:** P5 (canard ×1.5 with flap), P3 (booster assist), P1 or P6 (pod up-rating and mass reduction), P4 (TG forward).
5. **A10 common-height wing** to the §4 tolerances. Incidence matching is the tighter requirement.
6. **Do not use** a battery sled, fuel transfer or seat rails.

For the simulator `phantom-fx` variant: use the N2 masses and inertias from §1, the canard area as a parameter, and booster vectoring as an actuator.

### Cited Findings
- Sections 1–9.

### Inferences
- Hover and wingborne trim can both close within the Phantom identity, but only with P5 and a thrust increase. Packaging alone does not close them.

### Gaps
- Body Cm.
- Real TG and pod masses.
- Build ledger comparison (ledger absent).
