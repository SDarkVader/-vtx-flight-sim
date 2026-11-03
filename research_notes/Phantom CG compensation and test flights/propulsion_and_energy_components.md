# Phantom VTOL propulsion and energy: real component data, hover feasibility and minimum wingborne speed (research notes, 2026-11-02)

Provenance labels on every number: **MEASURED-K** = measured in this study on the A8 CAD model (geometry only; not hardware; if "K" means something else in the project vocabulary, remap); **MANUFACTURER** = company datasheet, product page or press claim about a different machine; **REGULATORY_REFERENCE** = regulation text; **DERIVED** = calculated here from the stated inputs (values measured by third parties on other hardware and transferred here are marked **DERIVED-LIT**); **SYNTHETIC_UNVALIDATED** = free simulator parameter chosen here. SI units, ISA sea level (ρ = 1.225 kg/m³, g = 9.80665 m/s²), out of ground effect, unless stated. Nothing here is a hardware rating for the Phantom.

A8 measurement method (applies to every MEASURED-K value): `blender.exe -b --factory-startup --disable-autoexec assets/source/phantom-a8/phantom-a8.blend --python-expr <print-only script>` (Blender 5.2); nothing saved. Vertex radii computed in each `JOINT_WHEEL_POD_*` frame (axle = pod-local +Y). VTOL pose = frame 80 (pods at ±90° about X). Obstruction found with BVH ray casts from the disk mid-plane: 7 radii (0.07–0.25 m) × 24 azimuths = 168 rays per face per pod, 1 m range, ignoring the pod's own rotating parts. Projected areas from ray casts on a 20 mm grid. Limits: the scite literature tool required a paid plan and was unavailable, and the NASA concept-vehicle PDF could not be parsed, so some suggested sources are listed as gaps.

## 1. Fans: available disk and exit area, realistic figure of merit and duct augmentation, thrust/power per pod, rpm and tip speed

### Takeaway
As modelled, the A8 wheel pods have **no open flow path**. A solid Ø0.54 m structural disk fills each wheel, and in the VTOL pose the inlets sit under the fenders while the exits are partly blocked by the fixed tilt bracket, pin and pylon. The largest fan annulus that fits inside the tyre bore runs from r_hub 0.110 m to r_tip 0.245 m: **0.151 m² per pod, 0.602 m² total**, 23% less than the contract's 0.785 m². At 1,300 kg that is a disk loading of **21 kN/m²**, between Lilium-class fans and the F-35 LiftFan (≈70 kN/m²). With a realistic figure of merit (FM_open ≈ 0.8), hover needs about **370 kW of shaft power per pod**: 1.48 MW shaft and 1.59 MW electrical in total, rising to **≈1.96 MW electrical with a 15% thrust reserve**.

### Cited Findings
A8 geometry (MEASURED-K; from the Blender measurement described in the preamble):
- Pod pivot = disk centre: FL (1.54, −1.04, 0.42), FR (1.54, +1.04, 0.42), RL (−1.59, −1.04, 0.42), RR (−1.59, +1.04, 0.42) m (CAD X-forward, Y-lateral, Z-up). Pods tilt about X, 0 → ±90°, between frames 50 and 80 (30 frames at 24 fps = 1.25 s, i.e. 1.26 rad/s animation timing). The legs slide 0.52 m between frames 30 and 50 (0.83 s, 0.62 m/s). The scene runs frames 1–140.
- Tyre `WHEEL_*_CLOSED_TYRE`: a circular torus with outer radius 0.360 m (Ø0.720), **inner (bore) radius 0.254 m (Ø0.508)**, width 0.106 m, tube radius 0.053 m and major radius 0.307 m. Section points (r, |y|) in m: (0.254, 0), (0.280, 0.046), (0.307, 0.053), (0.333, 0.046), (0.360, 0).
- `WHEEL_*_STRUCTURAL_DISK`: a **closed, capped cylinder of r 0.270 m × 0.110 m** that fills the wheel. The modelled open flow area is therefore zero.
- `WHEEL_*_THRUST_INLET_OUTLET_PLACEHOLDER`: a flat disk of r 0.190 m (Ø0.380), 12 mm thick, on the outboard face only.
- `WHEEL_*_AMBER_RING`: r 0.234–0.258 m, on the outboard face.
- `PHANTOM_*_CFRP_THROTTLE_HUB`: a 0.13 m cube spanning r 0.057–0.081 m.
- `WHEEL_*_HINGE_SHAFT` (tilt pin, fixed to the body): Ø0.13 × 0.17 m along X through the disk centre. Its footprint in the disk plane reaches **r 0.107 m**.
- `WHEEL_*_TI_DOUBLE_SHEAR_HINGE_BRACKET` (fixed): 0.34 × 0.14 × 0.20 m. It enters the wheel 75 mm from the inboard side (pod-frame y −0.02…+0.12 m, against a tyre width of ±0.053 m) and covers about **0.068 m²** of the disk plane around the centre (r ≤ 0.19 m). The bracket also overlaps the solid structural disk volume, which is an A8 packaging conflict.
- `WHEEL_*_CLOSED_CFRP_REACTION_PYLON` (fixed): inboard of the wheel, pod-frame r 0.186–0.332 m, y 0.055–0.45 m.
- VTOL pose (frame 80): the outboard face, which carries the placeholder, faces **up**.
  - **Inlet side.** Front pods: 166 of 168 upward rays hit structure within 1 m (stowed canard blade 95, an A8 defect that the A9 re-design moves; front fender 22; tilt pin 18; pylon 12; brake-cooling duct 9). The nearest hit is 0.023 m above the disk face. Rear pods: 161 of 168 (rear fender 77, pylon 30, bracket 20, pin 18).
  - **Exit side.** 83–89 of 168 downward rays hit fixed structure within 1 m (pylon 24–34, bracket 20–22, pin 18, hull 7–15), at 0.010–0.016 m minimum distance.
- Contract assumption under test: four disks of 0.25 m radius, ideal induced hover power 1.04 MW, and 1.6 MW electrical at 65% aggregate efficiency — repo `docs/phantom/SYSTEMS_CONTRACT.md` §4.

Lift-fan and ducted-fan references:
- **F-35B LiftFan**: Ø50 in (1.27 m), two-stage counter-rotating fan, more than 20,000 lbf of cold thrust. The driveshaft/clutch upper limit is 29,000 shp. The three-bearing swivel module passes about 18,000 lbf and rotates 95° in 2.5 s; each roll post gives 1,950 lbf (MANUFACTURER) — [Rolls-Royce LiftSystem](https://www.rolls-royce.com/products-and-services/defence/aerospace/combat-jets/rolls-royce-liftsystem.aspx); [RR LiftSystem datasheet](https://www.mylearning.rolls-royce.com/~/media/Files/R/Rolls-Royce/documents/defence/VCOMB-4202-Rolls-Royce-LiftSystem-datasheet.pdf)
- **Lilium**: 36 ducted electric fans (one per flap), later reduced to 30. Lilium says hover power is about twice that of an equivalent open-rotor concept, cruise needs about one-tenth of hover power, and less blade-tip leakage gives about a 40% efficiency benefit (MANUFACTURER) — [evtol.news: Lilium's technology approach](https://evtol.news/news/liliums-technology-approach-explained); [AOPA (30 engines)](https://aopa.org/news-and-media/all-news/2023/june/flight-training-magazine/future-flight-lilium-jet)
- **Lilium motor** (Honeywell/Denso): 100 kW, "just over 4 kg", radial flux (MANUFACTURER) — [AIN 2022](https://backend.ainonline.com/news-article/2022-05-23/honeywell-and-denso-join-forces-make-electric-motors-lilium-jet)
- **Pereira (UMD, 2008)**: 17 shrouded-rotor models with nominal Ø16 cm rotors. Thrust rose by up to 94–95% over the open rotor at the same power, and maximum FM by up to 75%. Best values: lip radius 13% of D, diffuser included angle 10°, diffuser length 50–72% of D, and the smallest tip clearance tested (0.1% of D). A sharp lip can separate the flow in hover (DERIVED-LIT; micro-air-vehicle scale, low Reynolds number) — [DRUM dissertation record](https://drum.lib.umd.edu/handle/1903/8752); [Chopra lab summary](https://inderjitchopra.umd.edu/?p=127)
- **Aurora XV-24A LightningStrike** (turboelectric ducted-fan VTOL): one AE 1107C turboshaft (4,023 hp quoted) drives three Honeywell generators of about 1 MW each, feeding 24 variable-pitch ducted fans: 18 of about 30 in in the wings and 6 just under 2 ft in the canards. MTOW is quoted as about 12,000–13,000 lb, and sources disagree (MANUFACTURER/press) — [Wikipedia](https://en.wikipedia.org/wiki/Aurora_XV-24_LightningStrike); [evtol.news](https://evtol.news/aurora-flight-sciences)

### Inferences
Disk-area options (DERIVED from the MEASURED-K geometry). r_tip 0.245 m = tyre bore 0.254 m − about 8 mm duct liner − about 1 mm tip gap (SYNTHETIC). r_hub 0.110 m encloses the tilt-pin footprint (0.107 m, MEASURED-K).

| Case | r_hub → r_tip (m) | A per pod (m²) | A total (m²) | Disk loading at 1,300 kg (kN/m²) |
|---|---|---|---|---|
| D1 contract (no hub, inside tyre bore not checked) | 0 → 0.250 | 0.196 | 0.785 | 16.2 |
| **D2 recommended maximum inside tyre** | 0.110 → 0.245 | **0.151** | **0.602** | **21.2** |
| D2b (tilt pin moved out of hub) | 0.081 → 0.245 | 0.168 | 0.672 | 19.0 |
| D3 placeholder disk | 0.081 → 0.190 | 0.093 | 0.371 | 34.3 |
| D3b placeholder with pin hub | 0.110 → 0.190 | 0.075 | 0.302 | 42.3 |

- **D2 is only usable if all of the following change:**
  - the solid structural disk becomes an open duct;
  - the fixed Ti bracket, pin and pylon leave the disk plane (the bracket alone blocks ≈0.068 m², about 40% of the D2b annulus);
  - the fenders stop overhanging the inlet.

  Otherwise D3b is the honest upper bound. The contract's r = 0.25 m ignores the hub and liner and is larger than the tyre bore (0.254 m less the liner).
- **Duct quality.** The tyre torus works as a natural bellmouth with r_lip/D ≈ 0.053/0.49 = 0.11, close to Pereira's 0.13 optimum. The duct is short, though (L/D ≈ 0.106/0.49 = 0.22), and has no diffuser. The exit-area ratio σ_d is therefore about 1, and probably below 1 because the torus curves outward at the exit (DERIVED from MEASURED-K).
- **Ideal duct augmentation** (DERIVED, standard actuator-disk momentum theory):
  - P_ideal = T^1.5/√(4ρAσ_d) for a duct, against T^1.5/√(2ρA) for an open rotor. At σ_d = 1 that is 29% less ideal power, or 26% more thrust at equal power ((2σ_d)^(1/3)).
  - With σ_d = 1 the rotor carries 1/(2σ_d) = 50% of the thrust and the duct lip the rest.
  - A 10° diffuser giving σ_d ≈ 1.2 would cut another 9% (1/√1.2).
- **Benchmarks for FM_open** (FM against the open-rotor ideal on the fan annulus):
  - F-35 LiftFan: ≈ **0.70** at 70.2 kN/m², using the gross Ø1.27 m area and the 29,000 shp limit (equivalent to 0.49 against the σ_d = 1 duct ideal) (DERIVED from MANUFACTURER).
  - The contract's 65% aggregate implies FM_open ≈ 0.70 with η_motor·η_inverter = 0.93.
  - Shrouded rotors can exceed FM_open = 1 when they have a good lip and diffuser (DERIVED-LIT, Pereira).
  - For a short, diffuser-less tyre duct with obstructed inlet and exit, recommend **FM_open = 0.80 (0.65–1.00)**; realistic duct augmentation is 1.0–1.2× rather than the ideal 1.26× (SYNTHETIC_UNVALIDATED).
- **Hover power** (DERIVED; ISA sea level, out of ground effect, CG at the pod centroid, η_motor 0.95 × η_inverter 0.98; electrical excludes accessories; "peak" = +15% thrust, ×1.233 power). Each cell gives shaft / electrical / peak electrical in kW:

| Area | Mass (kg) | Ideal open-rotor (kW) | FM 0.65 | FM 0.80 | FM 1.00 |
|---|---|---|---|---|---|
| D1 0.785 m² | 1,100 | 808 | 1,243 / 1,335 / 1,646 | 1,010 / 1,084 / 1,337 | 808 / 868 / 1,070 |
| D1 | 1,300 | 1,038 | 1,596 / 1,715 / 2,115 | 1,297 / 1,393 / 1,718 | 1,038 / 1,115 / 1,375 |
| D1 | 1,400 | 1,160 | 1,784 / 1,916 / 2,363 | 1,450 / 1,557 / 1,920 | 1,160 / 1,246 / 1,536 |
| **D2 0.602 m²** | 1,100 | 922 | 1,419 / 1,524 / 1,880 | 1,153 / 1,238 / 1,527 | 922 / 991 / 1,222 |
| **D2** | **1,300** | **1,185** | 1,823 / 1,958 / 2,415 | **1,481 / 1,591 / 1,962** | 1,185 / 1,273 / 1,570 |
| D2 | 1,400 | 1,324 | 2,037 / 2,188 / 2,699 | 1,655 / 1,778 / 2,193 | 1,324 / 1,423 / 1,754 |
| D3b 0.302 m² | 1,100 | 1,303 | 2,005 / 2,154 / 2,656 | 1,629 / 1,750 / 2,158 | 1,303 / 1,400 / 1,727 |
| D3b | 1,300 | 1,675 | 2,576 / 2,767 / 3,413 | 2,093 / 2,248 / 2,773 | 1,675 / 1,799 / 2,218 |
| D3b | 1,400 | 1,871 | 2,879 / 3,093 / 3,814 | 2,339 / 2,513 / 3,099 | 1,871 / 2,010 / 2,479 |

- **Per pod at 1,300 kg** (D2, FM 0.8; DERIVED): T = 3,187 N; ideal exit velocity 131 m/s; mass flow 24 kg/s; ideal fan total-pressure rise ≈ 10.6 kPa; shaft power **370 kW in hover, 457 kW at +15% thrust**.
- **Tip speed and rpm** (DERIVED). A single-stage fan held to a mean-line work coefficient of ψ ≈ 0.32–0.47 (fan efficiency 0.85) needs U_tip ≈ 190–230 m/s (tip Mach 0.56–0.68), which is 7,400–9,000 rpm at r_tip 0.245 m. Hover torque is 394–478 N·m and peak torque 486–589 N·m. Recommend **210 m/s, 8,200 rpm, about 430 N·m in hover and 530 N·m peak**. A two-stage counter-rotating fan, like the LiftFan, could run slower.
- **Simulator coefficients at that point** (DERIVED): k_T ≈ 4.3e-3 N/(rad/s)² and k_Q ≈ 5.9e-4 N·m/(rad/s)² (ω_hover ≈ 857 rad/s). Thrust from power: T = (FM_open·P_shaft)^(2/3)·(2ρA)^(1/3).
- **Spool response** (DERIVED; inertia is SYNTHETIC). The small-signal thrust time constant is τ ≈ Iω/(2Q): 0.05 / 0.10 / 0.20 s for rotor inertia I = 0.05 / 0.10 / 0.20 kg·m², which covers a fan plus motor rotor. **If the fan is attached to the rotating tyre and rim (I ≈ 1.4 kg·m²), τ ≈ 1.4 s, too slow for hover attitude control.** The fan rotor must be decoupled from the tyre.
- **CG and control margin** (DERIVED from pod x-stations, MEASURED-K, and the CG estimate in repo `docs/phantom/WING_CASSETTE_STUDY.md` U2):

| CG x (m) | Front-pod share of W | Rear-pod share of W | Rear-pod overload |
|---|---|---|---|
| −0.025 (pod centroid) | 0.250 | 0.250 | 0% |
| −0.25 (repo estimate) | 0.214 | 0.286 | +14.4% |
| −0.50 | 0.174 | 0.326 | +30.4% |

  At CG −0.25 m a 15% reserve on the rear pods needs every pod sized for about 0.33 W, an installed T/W of about 1.32, with rear-pod power ×1.22. The alternative is to move the CG to x ≈ −0.025 m.
- **Control authority** with ±15% differential thrust (DERIVED; repo inertias 660 and 2,300 kg·m² from WING_CASSETTE_STUDY U10):
  - Roll: about 2.0 kN·m, ≈3.0 rad/s².
  - Pitch: about 3.0 kN·m, ≈1.3 rad/s².
  - Yaw from ±10° differential X-tilt (front vs rear): about 3.5 kN·m, ≈1.2 rad/s² with I_zz ≈ 2,800 kg·m² (SYNTHETIC), at a 1.5% loss of vertical thrust.

  With four pods there is no trimmed hover after a single pod failure (inference).
- **Lift-fan ram drag in crossflow.** D_ram = ṁV with ṁ ≈ √(ρ A T) per pod at σ_d = 1. For the full hover mass flow (97 kg/s) that is about **3–4 kN at 40 m/s**, which dominates transition drag (DERIVED).

### Gaps
- No fan has been designed. FM, σ_d, inlet distortion under the fenders, and the effect of exit blockage are all unquantified and need CFD or a rig test.
- Not retrieved: Akturk & Camci (tip clearance), Graf, Fleming & Ng (lip shapes), Leishman's text, and the NASA RVLT concept-vehicle technology factors. The scite tool needed a paid plan, and the NASA PDF ([Johnson et al. 2018](https://rotorcraft.arc.nasa.gov/Publications/files/Johnson_2018_TechMx.pdf)) could not be parsed.
- No sourced per-fan diameter, thrust or power for Lilium.
- Ground effect and suckdown (fan exit about 0.5–1 D above the ground) are not quantified. Jet-lift vehicles can *lose* lift near the ground.
- The A8 does not define whether the tyre rotates with the fan.

## 2. Electric motors and inverters: which units meet pod power and torque at that rpm; mass, continuous vs peak, inverter mass and efficiency

### Takeaway
Each pod needs about **370 kW continuous and 460 kW peak shaft power at 7,400–9,000 rpm (≈430–530 N·m)**. No single published, certified motor matches that. The closest published units are the H3X HPDM-250 (two per pod), YASA's 2025 prototype (an unverified claim), and Lilium-type 100 kW high-speed motors (four per pod). The EMRAX, YASA 750R and SP260D are low-speed, high-torque machines that would need a gearbox, and the certified ENGINeUS 100 is too heavy at 5 kW/kg. A realistic **motor plus inverter is 30–50 kg per pod (nominal 38 kg), or 120–200 kg for four pods**.

### Cited Findings
- **H3X HPDM-250** (integrated motor drive): about 15 kg; "12 kW/kg continuous" per H3X. Press reports conflict: 250 kW peak for 30 s with 200 kW continuous, against 250 kW continuous elsewhere. H3X calls its specs approximate, and the datasheet is gated (MANUFACTURER) — [H3X](https://www.h3x.tech); [CleanTechnica 2021](https://cleantechnica.com/2021/03/25/groundbreaking-h3x-motor-brings-electric-aircraft-one-step-closer-to-reality/); [FLYER](https://flyer.co.uk/h3x-super-light-electric-motor-with-3x-power/)
- **YASA prototype** (Oct 2025): 12.7 kg, 750 kW short-term peak (59 kW/kg), continuous output *estimated* at 350–400 kW. An earlier prototype gave 13.1 kg and 550 kW. The claims are not independently verified (MANUFACTURER) — [YASA](https://yasa.com/news/yasa-smashes-own-unofficial-power-density-world-record-pushing-state-of-the-art-electric-motor-to-staggering-new-59kw-kg-benchmark/); [electrive](https://www.electrive.com/2025/10/22/yasa-surpasses-its-own-record-in-motor-power-density)
- **YASA 750 R**: 200 kW peak; peak torque given as 790 or 700 N·m (conflicting); 0–3,250 rpm; up to 70 kW and 400 N·m continuous; mass not found (MANUFACTURER) — [YASA 750 R](https://yasa.com/yasa-750-r/)
- **EMRAX 268 HV** (datasheet v1.7): 210 kW peak (at 4,250 rpm), 101 kW continuous, 500 N·m peak and 226 N·m continuous, 4,500 rpm maximum, 100–830 V, 21.4–22.3 kg, Ø268 × 94 mm (MANUFACTURER) — [EMRAX 268 datasheet](https://emrax.com/wp-content/uploads/2025/08/EMRAX-268_datasheet_v1.7_version_C.pdf); [product page](https://emrax.com/e-motors/emrax-268/)
- **Safran ENGINeUS 100**: 125 kW maximum, "5 kW/kg", air-cooled with an embedded controller. EASA certified it in Feb 2025 under SC E-19 after 1,500 h of tests; serial production is planned for 2026 (MANUFACTURER / REGULATORY_REFERENCE) — [AIN](https://live.ainonline.com/aviation-news/air-transport/2025-02-04/easa-certifies-safrans-125-kilowatt-engineus-100-electric); [Safran PR](https://www.safran-group.com/pressroom/safran-obtains-easa-certification-first-electric-motor-new-air-mobility-2025-02-03)
- **Siemens SP260D**: about 260 kW and 50 kg (MANUFACTURER) — [Siemens PR](https://assets.new.siemens.com/siemens/assets/api/uuid:74280742-4044-4bc8-b67b-5b75d13921f5/pr20160704-maiden-flight.pdf). One article gives 2,500 rpm direct drive and 1,000 N·m (single source) — [engineering.com](https://mobile.engineering.com/amp/12805.html). This business went to Rolls-Royce Electrical, which RR closed (§3).
- **MAGicALL MAGiDRIVE** (integrated motor and controller; CityAirbus NextGen): torque density up to 50 N·m/kg, efficiency above 95% — [Aviation Today](https://www.aviationtoday.com/2022/05/11/airbus-magicall-cityairbus/). Product family spans 6–300 kW and 0.7–49.5 kg (MANUFACTURER) — [Sustainable Skies](https://sustainableskies.org/magicall-motorcontroller-vies-simplicity-lightness/)
- **Inverters.** GE/NASA are developing a 1 MW SiC inverter; GE's stated goals are 99% peak efficiency and 19 kW/kg (goals; achievement not confirmed) — [GE/NASA](https://www.geaerospace.com/news/press-releases/research/ge-nasa-partner-12mm-program-advance-future-electric-flight). Lab MW-class converters have reached 99% at 12 kVA/kg and 99.1% at more than 18 kVA/kg (DERIVED-LIT) — [UKY paper 1](https://scholars.uky.edu/en/publications/high-power-density-medium-voltage-megawatt-scale-power-converter-/); [UKY paper 2](https://scholars.uky.edu/en/publications/a-megawatt-scale-medium-voltage-high-efficiency-high-power-densit-2/)

### Inferences
- **Speed mismatch** (DERIVED). The EMRAX 268 (4,500 rpm), YASA 750R (3,250 rpm) and SP260D (2,500 rpm) are torque machines. Driving a 0.49 m fan at about 8,200 rpm would need roughly 2:1 to 3:1 gearing, and gearbox mass and loss are not sourced. The ENGINeUS 100 at 5 kW/kg would need four units, about 100 kg per pod, so it is excluded.
- **Candidate sets per pod** (DERIVED):
  - **A:** 2 × HPDM-250 class: about 30 kg including inverters, 400 kW continuous / 500 kW peak if the 200/250 kW figures hold. Speed rating is unknown.
  - **B:** 1 × YASA-prototype class (12.7 kg motor) plus a separate SiC inverter for 460 kW at 12–19 kVA/kg (24–38 kg): about 37–51 kg. The motor's continuous rating is an estimate.
  - **C:** 4 × Lilium-type 100 kW motors (about 4 kg each) plus inverters: needs a multi-fan pod, which is a geometry change.
  - Nominal for the simulator: **38 kg per pod** (12 kW/kg integrated × 460 kW).
- **Efficiencies** (SYNTHETIC_UNVALIDATED, anchored on the sources above): η_motor **0.95** (0.93–0.97; MAGicALL "above 95%"); η_inverter **0.98** (0.97–0.99; lab 99%). Overload: peak = 1.25 × continuous for ≤ 30 s, matching the HPDM-250 "250 kW / 30 s" pattern. Current or torque loop response 2–5 ms.
- **Heat** (DERIVED). In hover each pod motor dissipates about 370 × (1/0.95 − 1) ≈ **19.5 kW** and its inverter about 7.5 kW.
  - With a motor heat capacity of about 17.5 kJ/K (35 kg × 500 J/kg·K, SYNTHETIC), adiabatic heating is about 1.1 K/s, roughly **+67 K per minute**.
  - Active cooling is therefore mandatory even for short hovers. The natural sink is the pod's own fan stream (about 24 kg/s), if the motor sits in the hub.
- **Thermal limits** (SYNTHETIC_UNVALIDATED, no datasheet value retrieved): winding 150 °C (130–180), SiC junction 150 °C (125–175), coolant outlet 65 °C.

### Gaps
- No published rpm-torque map for the HPDM-250 (datasheet gated) or ENGINeUS 100; no rpm for the YASA prototype; no mass for the YASA 750R.
- No datasheet masses for flight inverters at 400–500 kW.
- No sourced gearbox mass or efficiency.
- Continuous ratings for 30–120 s duty need the manufacturers' thermal curves.

## 3. Turbo-generators: mass, power, efficiency, specific fuel consumption, spool/response time

### Takeaway
**The Safran TG600 is verified**: a 600 kW electrical turbogenerator built on the Arrano turboshaft with two GENeUS generators. Electra signed a development and production agreement in July 2026 with an initial order of 250 units, and Aura Aero's ERA uses two. **Its mass, SFC and transient data are not published.** A DERIVED estimate is **≈270 kg (240–320 kg)**. One TG600 covers only about 37% of the ≈1.6 MW hover demand. Honeywell's 1 MW generator (about 8 kW/kg, 97%) is the only other MW-class unit with test data. Rolls-Royce has exited electrical propulsion. Engine certification allows **≤5 s from ≤15% to 95% power**, so a buffer is mandatory for hover transients.

### Cited Findings
- **Safran TG600**:
  - A 600 kW turbogenerator from Safran Helicopter Engines: a gas turbine (Arrano) with two GENeUS generators from Safran Electrical & Power and a power-regulation system (MANUFACTURER) — [Safran TG600 product page](https://www.safran-group.com/products-services/tg600). The page returned HTTP 403 to fetch; content per search index.
  - Electra and Safran signed a development and production agreement on **15 July 2026**. The TG600 is central to the EL9 Ultra Short's hybrid-electric blown-lift propulsion. The agreement includes an initial order of 250 units and follows a 2023 MoU (MANUFACTURER) — [Safran PR 2026-07-15](https://www.safran-group.com/pressroom/electra-and-safran-reach-development-and-production-agreement-tg600-turbogenerator-power-el9-hybrid-2026-07-15)
  - eVTOL Insights adds: 600 kW of electricity, an "18% reduction in fuel consumption" against similar in-service engines, EL9 entry into service in 2030, first flight late 2027 or early 2028, take-off and landing in as little as 150 ft, and an FAA Part 23 application. Mass is not stated — [eVTOL Insights](https://evtolinsights.com/electra-and-safran-sign-production-agreement-for-tg600-turbogenerator/)
  - The search index also reports a first bench test of a flight-ready unit at Bordes in July 2026. That comes from the Safran PR, which I could not open (HTTP 403).
  - **Aura Aero ERA**: two TG600 units, 600 kW each, feed eight electric propulsion units using ENGINeUS motors (24 Aug 2026; MANUFACTURER) — [Evertiq](https://evertiq.com/design/2026-08-24-safran-aura-aero-expand-partnership-to-develop-turbogenerators). Safran's French press release is dated 27 July 2026, which is the date the repo source S06 cites — [Safran FR PR](https://www.safran-group.com/fr/espace-presse/safran-signe-accord-aura-aero-developper-turbogeneratrice-propulsion-avion-regional-hybride-2026-07-27-0)
- **Safran Arrano**: dry mass 175.1 kg (EASA data); 1,100–1,300 shp family, with the Arrano 1A rated up to 1,280 shp. Fuel burn is 10–15% better than legacy engines, but no absolute SFC is published (MANUFACTURER / REGULATORY_REFERENCE via secondary) — [Wikipedia: Safran Arrano](https://en.wikipedia.org/wiki/Safran_Arrano)
- **GENeUS 300**: 300 kW maximum, 550–800 VDC, 42,000 rpm maximum overspeed, "8 kW/kg" continuous — [Safran GENeUS](https://www.safran-group.com/products-services/geneustm-smart-generator). Ground tests confirmed **10 kW/kg and about 96% efficiency** — [Safran 2023-12-13](https://www.safran-group.com/news/safran-electrical-power-successfully-completes-first-geneus-300-ground-test-campaign-2023-12-13). The 2018 launch quoted more than 8 kW/kg for the whole pack, including the active rectifier and cooling (MANUFACTURER) — [Safran 2018](https://www.safran-group.com/news/safran-strengthens-its-electrical-offer-launch-its-ranges-electric-generators-and-motors-geneus-and-2018-07-16)
- **Honeywell 1 MW turbogenerator**: a 1 MW generator combined with the HGT1700 APU power core — [Honeywell](https://www.honeywellaerospace.com/us/en/products-and-services/product/hardware-and-systems/electric-power/the-honeywell-turbogenerator).
  - Ground test: 1.02 MVA, with a continuous run at 900 kW; "around 8 kW/kg"; about 97% efficiency, against 88–90% and 2–3 kW/kg for current generators — [AIN 2022](https://www.ainonline.com/news-article/2022-06-02/honeywell-reports-progress-one-mw-turbogenerator-tests)
  - Generator mass 280 lb (127 kg) — [Avweb](https://www.avweb.com/aviation-news/honeywell-develops-compact-generator-for-hybrid-aircraft/embed/)
  - The 2019 prototype paired an HTS900 with two 200 kW generators — [Honeywell 2019](https://www.honeywell.com/us/en/press/2019/02/honeywells-hybrid-electric-turbogenerator-debuts-at-heli-expo). The HTS900 weighs about 338 lb (153 kg), a partly uncited figure — [Wikipedia](https://en.wikipedia.org/wiki/Honeywell_HTS900) (MANUFACTURER)
- **Rolls-Royce**: a turbogenerator with a new small gas turbine, scalable from 500 to 1,200 kW, was announced in 2022, and the engine passed to test in 2023 — [Avweb](https://www.avweb.com/aviation-news/rolls-royce-developing-turbogenerator-tech-for-hybrid-electric-flight/). RR announced its exit from electrical propulsion in Nov 2023 and confirmed the closure on 7 Nov 2024; no source says what happened to the turbogenerator — [AIN 2024](https://www.ainonline.com/aviation-news/aerospace/2024-11-07/rolls-royce-confirms-closure-electric-propulsion-unit)
- **PBS TS100** turboshaft: 180 kW take-off (≤5 min), 160 kW maximum continuous, 140 kW cruise, 56.7 or 61.3 kg depending on variant (MANUFACTURER) — [PBS TS100](https://www.pbs.cz/en/aerospace/aircraft-engines/pbs-ts100); [PBS brochure](https://pbs.cz/getmedia/2479e5b0-bb94-48d9-8ced-067a88a63816/PBS-Brochure-Aerospace-Products.pdf.aspx?ext=.pdf)
- **Turbotech TG-R90**: 85 kW continuous (90 kW peak), 64 kg without equipment, 630–800 V DC, regenerative cycle, generator at turbine speed with no gearbox, 3,000 h TBO — [Turbotech](https://www.turbotech-aero.com/solutions/); [UST](https://ust-media.com/ust-magazine/UST031/75). Turbotech claims the TG-R55 plus 40 kg of Jet-A1 yields 130 kWh (MANUFACTURER) — [Mobility Engineering](https://www.mobilityengineeringtech.com/component/content/article/36603-bringing-turbine-power-to-small-aircraft)
- **14 CFR 33.73** (REGULATORY_REFERENCE) — [14 CFR 33.73](https://www.law.cornell.edu/cfr/text/14/33.73):
  - (a) moving the power lever from minimum to maximum in ≤1 s must not cause overtemperature, surge or stall;
  - (b) the engine must go from flight idle (or ≤15% of rated take-off power) to 95% in ≤5 s, from a stabilised static condition.

### Inferences
- **TG600 mass** (DERIVED; not published): Arrano 175 kg + 2 × GENeUS (600 kW at 8–10 kW/kg = 60–75 kg) + mounts, accessories, fuel control and ducting 20–50 kg (SYNTHETIC). That gives 255–300 kg. Recommend **270 kg (240–320 kg)**, about **2.2 kW/kg**.
  - 600 kW electrical needs about 625 kW of shaft power at 96%, about 840 shp. That is about 65% of the Arrano 1A's 1,280 shp rating (inference).
- **Specific power, other units** (DERIVED): Turbotech TG-R90 about 1.3–1.4 kW/kg; PBS TS100 about 2.9–3.2 kW/kg shaft-only; Honeywell generator alone about 8 kW/kg. The Honeywell turbogenerator's total mass is unknown; SYNTHETIC **300–450 kg**.
- **Fuel** (DERIVED): the Turbotech TG-R55 claim gives 40 kg / 130 kWh ≈ **0.31 kg/kWh_e**, a regenerative best case. Recommend **0.36 kg/kWh_e (0.31–0.42)** SYNTHETIC for a simple-cycle 600 kW unit.
- **Response** (SYNTHETIC_UNVALIDATED, bounded by REGULATORY_REFERENCE):
  - Model the generator as a first-order lag with **τ = 1.0 s (0.5–1.75 s)**, which takes 15% to 95% in 2.8 s (within the 33.73(b) 5 s limit), plus a ramp limit of 0.3 P_rated/s.
  - Cold start to power: 60 s (30–120 s).
  - A trip is a step to zero, with power-turbine run-down handled by the buffer.
  - A free-turbine machine like the Arrano droops in speed under a load step until the gas generator accelerates. The buffer must cover that gap (inference).
- **Packaging** (DERIVED with SYNTHETIC specific power). The A9 induction area is 0.0168 m² total — repo `docs/phantom/A9_WING_CASSETTE_REVISION.md` (U18). A 625 kW turboshaft needs about 2.1–2.5 kg/s of air (assuming 250–300 kW per kg/s), which at a 100 m/s inlet velocity means 0.017–0.021 m². The A9 duct is marginal for one TG600 and too small for two.
- **XV-24A comparison** (DERIVED from press dimensions): fan area ≈ 18 × 0.456 + 6 × ≈0.268 ≈ 9.8 m² for ≈5,700 kg, a disk loading of ≈5.7 kN/m² with about 3 MW installed (≈0.53 kW/kg). The Phantom's D2 configuration at 21 kN/m² needs ≈1.2 kW/kg electrical just to hover.

### Gaps
- TG600 mass, SFC map, dimensions, voltage and transient response are all unpublished, and the Safran pages returned 403.
- Total mass of the Honeywell 1 MW turbogenerator and the HGT1700 core is unknown.
- The status of the Rolls-Royce turbogenerator after 2024 is unknown.
- No load-step acceptance data were found for any turbogenerator.

## 4. Peak-power buffer: realistic pack kW/kg and Wh/kg, mass for N seconds of hover at the generator deficit, thermal limits

### Takeaway
The hover deficit is **power-limited, not energy-limited**. At 1,300 kg with one TG600, the peak deficit is about **1.39 MW**. That needs **360–705 kg of pack** at 3.9–2.0 kW/kg, which alone breaks the 1,300 kg budget, while the energy for 60 s is only about 17 kWh (≈116 kg). Even oversized packs reach their 60 °C discharge limit in about 1–2 min at continuous current. Supercapacitors are about 1–3 orders of magnitude short of the energy needed for anything beyond a few seconds.

### Cited Findings
- **Molicel P50B** (21700): continuous discharge 60 A at an 80 °C cut-off; 260 Wh/kg; 714 Wh/L; discharge ambient −40 to 60 °C, charge −20 to 60 °C (MANUFACTURER) — [P50B datasheet](https://www.fsaeonline.com/content/Molicel-TDS--INR-21700-P50B-80122.pdf). A reseller quotes 5,000 mAh / 18.0 Wh typical and 71 g maximum — [18650batterystore](https://www.18650batterystore.com/products/molicel-21700-p50b-5000mah-50a-battery)
- **Molicel P45B**: 4,500 mAh, 16.2 Wh, 242 Wh/kg — [P45B datasheet copy](https://www.imrbatteries.com/content/molicel_p45b.pdf). 45 A continuous at an 80 °C cut-off — [Battery Junction](https://batteryjunction.com/molicel-inr21700-p45b). 70 g maximum — [18650batterystore](https://18650batterystore.com/products/molicel-p45b). An independent bench tester recommends 35 A for like-for-like comparison — [endless-sphere](https://endless-sphere.com/sphere/threads/bench-test-results-molicel-p45b-50a-4500mah-21700-an-extraordinary-cell.116190/) (MANUFACTURER / independent test)
- **Amprius SiCore** high-power cell (Jan 2025): 370 Wh/kg, more than 3,000 W/kg, 10C without cooling, 15C with active cooling — [BusinessWire](https://www.businesswire.com/news/home/20250114667030/en/Amprius-Announces-Breakthrough-SiCore%E2%84%A2-Cell-Chemistry-to-Boost-Battery-Performance-for-Electric-Mobility-Applications). The product page lists 370 Wh/kg, 910 Wh/L, 10C continuous and 20C pulse (MANUFACTURER) — [Amprius SiCore](https://amprius.com/solutions/sicore/)
- **Kokam SLPB 80460330H**: 100 Ah, 3.7 V, 500 A continuous, 800 A peak; cell mass not captured (MANUFACTURER) — [Kokam datasheet](https://www.thierry-lequeu.fr/data/Kokam-SLPB-80460330H-100Ah.pdf)
- **Toshiba SCiB 20Ah-HP** (LTO): 2.3 V; 1,900 W input/output for 10 s at 50% SOC and 25 °C; 84 Wh/kg; 176 Wh/L; about 545 g (MANUFACTURER) — [Toshiba](https://news.toshiba.com/press-releases/press-release-details/2022/Toshiba-Launches-20Ah-HP-SCiBTM-Rechargeable-Lithium-ion-Battery-Cell-That-Delivers-Both-High-Energy-and-High-Power/default.aspx)
- **Skeleton SkelMod 54V 277F**: 13.8 kW/kg, 7.0 Wh/kg. The 51 V class gives 12.3 kW/kg and 4.0 Wh/kg; the power definition is not stated (MANUFACTURER) — [Skeleton 54V](https://www.skeletontech.com/skelmod-54v277f-ultracapacitor-module); [Skeleton 51V](https://www.skeletontech.com/skelmod-51v166f-ultracapacitor-module)
- **Lilium battery claims**: more than 300 Wh/kg and more than 3 kW/kg; silicon-anode cells at 330–350 Wh/kg; minimum SOC 10–15% (MANUFACTURER) — [evtol.news](https://evtol.news/news/liliums-technology-approach-explained)

### Inferences
- **Cell-level power** (DERIVED; ~3.3 V under load is SYNTHETIC): P50B 60 A × 3.3 V / 70.5 g ≈ **2.8 kW/kg**; P45B ≈ 2.1; Amprius 10C ≈ 3.7, 15C (cooled) ≈ 5.5, 20C pulse ≈ 7.4; SCiB 20Ah-HP ≈ 3.5 kW/kg for 10 s.
- **Pack level**: packaging factor **0.70 (0.60–0.80)** by mass (SYNTHETIC_UNVALIDATED; no sourced aviation pack data).
  - P50B-class pack: **2.0 kW/kg continuous, 182 Wh/kg**.
  - Amprius 10C: 2.6 kW/kg, 259 Wh/kg. Amprius 15C cooled: 3.9 kW/kg.
  - SCiB-HP: 2.4 kW/kg for 10 s, 59 Wh/kg.
  - Supercapacitor: if Skeleton's figure is matched-impedance maximum power, usable power at 95% efficiency is about 0.19 × 13.8 ≈ **2.6 kW/kg**, with ~5 Wh/kg usable.
- **Buffer mass for N seconds of hover** (DERIVED; 1,300 kg, D2, FM 0.8, 25 kW accessories). Hover needs 1,616 kW electrical and 1,987 kW peak with +15% thrust. Li cells use 80% depth of discharge. Mass = max(power-limited, energy-limited); P = power governs, E = energy governs:

| Source (deficit hover / peak) | P50B-class pack | Amprius 10C | Amprius 15C cooled | SCiB-HP (10 s rating) | Supercap 30 / 60 / 120 s |
|---|---|---|---|---|---|
| 1 × TG600, 600 kW (1,016 / 1,387 kW) | **705 kg (P)** | 536 (P) | 357 (P) | 568 (P); 720 at 120 s (E) | 1,613 / 3,226 / 6,451 kg (E) |
| Honeywell 1 MW (616 / 987 kW) | 502 (P) | 381 (P) | 254 (P) | 404 (P); 437 at 120 s | 978 / 1,956 / 3,912 (E) |
| 2 × TG600, 1.2 MW (416 / 787 kW) | 400 (P) | 304 (P) | 203 (P) | 322 (P) | 660 / 1,321 / 2,642 (E) |

  Energy alone for 60 s at the 1,016 kW deficit is 61 MJ (16.9 kWh), or ≈116 kg of P50B-class pack.
- **Hover endurance and achievable T/W** (DERIVED; P50B-class pack, 1.97 kW/kg, 182 Wh/kg, 80% depth of discharge):
  - **1 × TG600 + 100 / 200 / 300 / 400 kg**: available power 797 / 994 / 1,191 / 1,388 kW against 1,616 kW needed. **No hover is possible**; achievable T/W is 0.62 / 0.72 / 0.81 / 0.90.
  - **2 × TG600 + 300 / 400 kg**: 1,791 / 1,988 kW. Hover is possible at T/W 1.07 / 1.15, with energy-limited endurance of 378 / 504 s. With only 100–200 kg the T/W is 0.91–0.99.
- **Thermal** (DERIVED with SYNTHETIC ~0.5 V polarisation at full current and c_p 1.0 kJ/kg·K):
  - P50B at 60 A dissipates about 30 W per cell, about 0.43 K/s adiabatic: **+26 K in 60 s, +51 K in 120 s**. Starting at 25 °C, the 60 °C discharge limit (MANUFACTURER) is reached after about 80 s.
  - P45B at 45 A: +19 K in 60 s, +39 K in 120 s.
  - A power-sized pack running at about 70% of its continuous current heats at roughly half that rate (I²), so hover is thermally limited to about **2–3 min** without liquid cooling.
- **Supercapacitors** (DERIVED): bridging the generator lag (600 kW × 2 s = 1.2 MJ) needs about 64 kg at 5.25 Wh/kg usable. A Li pack already sized for MW-level power covers that transient, so **no supercapacitor is recommended** (SYNTHETIC decision).

### Gaps
- No pulse-power or mass data for the Kokam UHP cells.
- Amprius high-power figures are company claims; no independent test was found.
- No sourced cell-to-pack factor for high-power aviation packs.
- No P50B DC internal resistance or entropic heat data; the thermal estimates use an assumed polarisation.
- The power definition behind Skeleton's kW/kg is not stated.

## 5. Rear propulsors and cooling: mass and thrust; cooling power at zero airspeed

### Takeaway
The A8 rear nozzles (Ø0.35 m outer, Ø0.24 m exhaust liner) support two electric ducted fans that give about **2.4 kN static thrust each at 300 kW shaft**, falling to about 1.8 kN each at 62 m/s. At liftoff the rear fans need **≥600 kW** just to balance drag, so they, not the wing, set the wingborne limit. Hover rejects about **250 kW of waste heat**, while the A8 radiator and its two Ø0.25 m fans can reject only about **45 kW at zero airspeed**. The remainder must go to thermal storage or into the lift-fan streams.

### Cited Findings
MEASURED-K (A8 CAD):
- **Rear nozzles** `POWER_*_REAR_THRUST_NOZZLE`: centred at (−2.29, ±0.40, 0.51). Each is a solid cylinder Ø0.350 × 0.240 m spanning x −2.41…−2.17 m. The exhaust liner disk is Ø0.238 m at x −2.42, and the rim torus spans r 0.137–0.163 m.
- **Aft reaction boxes**: 0.57 × 0.40 × 0.30 m (0.0665 m³ each).
- **Radiator core**: 0.28 × 0.82 × 0.19 m (0.043 m³), a face of about 0.156 m² for flow along X.
- **Cooling-fan reservations**: two, each Ø0.25 × 0.033 m.
- **Under-floor battery/thermal bay**: 1.80 × 0.54 × 0.105 m (0.101 m³).
- **Hull**:
  - volume 4.35 m³ and wetted area 24.9 m²;
  - bounding box x −2.40…2.45 m, |y| ≤ 1.011 m, z 0.17–1.19 m;
  - **frontal area 2.04 m² in road pose** (hull alone 0.93) and 2.16 m² in VTOL pose;
  - planform 10.44 m² including the A8 wing envelopes (2 × 1.49 m²), so about **7.46 m² for the body alone**.
- **Repo context**: induction area 0.0168 m², and "the canards can't trim alone below about 70 m/s" — repo `docs/phantom/A9_WING_CASSETTE_REVISION.md`

### Inferences
- **Rear-fan geometry** (DERIVED, SYNTHETIC): fan tip r 0.165 m and hub r 0.05 m inside the nozzle give 0.0777 m² per fan. Exit area is taken as the liner, 0.0445 m² per fan.
- **Momentum thrust model** (DERIVED; fan efficiency 0.85, both fans together, exit area 0.089 m²):

| Total shaft power | 0 m/s | 40 m/s | 62 m/s | 90 m/s | 179 m/s |
|---|---|---|---|---|---|
| 300 kW | 3.05 kN | 2.42 kN | 2.15 kN | 1.87 kN | 1.25 kN |
| 600 kW | 4.84 kN | 4.03 kN | 3.66 kN | 3.25 kN | 2.32 kN |

  Using the full fan area (0.155 m²) instead raises thrust 10–20% (5.82 kN static at 600 kW).
- **Mass**: **35 kg per propulsor (25–45 kg)** for motor, inverter, fan, duct and nozzle (SYNTHETIC; motor at 12 kW/kg integrated).
- **Spool time**: τ 0.15 s (0.10–0.30 s) (SYNTHETIC).
- **400 mph is infeasible on this body** (DERIVED; body CdA 0.65 m² SYNTHETIC = 2.04 m² × Cd 0.32). At 178.8 m/s the drag is about 13.6 kN, thrust power about 2.4 MW, and shaft power about 5 MW through the A8 exit area. Reaching it would need CdA ≲ 0.2 m² and multi-MW propulsion.
- **Hover waste heat** (DERIVED/SYNTHETIC; 1,300 kg, D2, FM 0.8, 1 × TG600 plus battery):

| Source | Heat (kW) |
|---|---|
| Lift motors | ≈78 |
| Inverters | ≈32 |
| Battery (8–14% of ~1 MW) | ≈100 (80–140) |
| Generator (4%) | ≈25 |
| Turbine oil and gearbox | ≈15 |
| **Total** | **≈250 (190–310)** |

  Most of the turbine's heat leaves with its exhaust (inference).
- **Zero-airspeed heat rejection** (DERIVED): the A8 core at 8 m/s face velocity and 30 K air temperature rise rejects about **45 kW**, about 1.5 kg/s of air. Fan power is about **2 kW** (1.24 m³/s at 600 Pa, fan η 0.45).
  - Rejecting 125 kW (motors plus inverters) at steady state needs about 4.1 kg/s, a radiator face of ≥0.5 m² at about 7 m/s, and about **5–6 kW of fan power**. The A8 core and fans are about 3× undersized for steady hover.
  - Storing a 60 s hover (≈12 MJ) would take, for example, 100 kg of glycol-water at a 35 K rise, or battery cell thermal mass (about 0.49 MJ/K for 490 kg of cells).
  - The lift-fan streams (about 24 kg/s per pod) are the cheapest heat sink for the pod motors.

### Gaps
- No real large-EDF datasheet (thrust versus speed) was retrieved, so the rear-fan values are momentum theory only.
- No radiator core data.
- No inlet-recirculation or downwash data for the radiator in hover.
- No body drag CFD; CdA 0.65 m² is a guess.

## 6. Mass closure and hover feasibility at about 1,300 kg: T/W, power, endurance, control margin, sensitivities

### Takeaway
**Hover does not close at 1,300 kg with A8-sized wheel fans.**
- Even with every optimistic assumption at once (FM 1.0, a larger hub-free annulus, Amprius 15C cooled cells, minimum structure), the mass build-up is about **1,425 kg**. Feeding the higher hover power back in converges at **about 1,535 kg**.
- With nominal assumptions the loop **diverges**: the first pass is about 2.1–2.2 t, which needs even more power.
- The recommended baseline powertrain (one TG600 plus a 200 kg high-power buffer: 1.0 MW continuous, 1.2 MW for 10 s) gives **T/W ≈ 0.72 continuous and 0.82 peak**. It can hover with a 15% reserve only at **≤ about 924 kg**.

### Cited Findings
- **Repo mass and inertia context**: gross / minimum flying mass 1,300 / 1,050 kg (range 1,100–1,500); CG −0.25 m (range −0.75…−0.25); roll / pitch inertia 660 / 2,300 kg·m² ±30%; no mass ledger exists — repo `docs/phantom/WING_CASSETTE_STUDY.md` (U1, U2, U10)
- **A9 wing cassette mass**: 140.5 kg (63.0 kg articulated + 77.5 kg fixed) (DERIVED in repo) — repo `docs/phantom/A9_MUJOCO_HANDOVER.md`
- **Component data used**: §§1–5 above (TG600 / Arrano / GENeUS, HPDM-250 / YASA, Molicel / Amprius, 14 CFR 33.73).

### Inferences
**Mass build-up** (kg; nominal [range]; the label sits after each item):

| Item | Nominal [range] (kg) | Label |
|---|---|---|
| Primary structure (CFRP hull 24.9 m², tub, bulkheads, canopy frame) | 300 [200–400] | SYNTHETIC |
| A9 wing cassette (wings, flaps, ailerons, canards, sleeves, locks) | 140.5 | DERIVED (repo) |
| Landing legs ×4 | 50 [35–70] | SYNTHETIC |
| Wheel pods ×4 without motors (tyre, rim/duct, fan rotor, tilt actuator, pin) | 100 [80–140] | SYNTHETIC |
| Lift motors and inverters ×4 (460 kW peak each) | 150 [120–200] | DERIVED |
| Rear propulsors ×2 | 70 [50–90] | SYNTHETIC |
| HV distribution, protection, harness | 50 [30–70] | SYNTHETIC |
| Thermal system | 40 [25–60] | SYNTHETIC |
| Avionics, flight control, sensors, surface actuators | 30 [20–40] | SYNTHETIC |
| Interior, seats, restraints, glazing | 60 [40–80] | SYNTHETIC |
| Two occupants | 170 [160–200] | SYNTHETIC |
| **Subtotal without power source, buffer or fuel** | **≈1,160 [≈900–1,490]** | |
| Fuel (30 min at ≈550 kW_e × 0.36 kg/kWh_e ≈ 100 kg) | 80 [50–150] | DERIVED/SYNTHETIC |

Totals by configuration:
- **A. Baseline**: 1 × TG600 (270) + 200 kg buffer → **≈1,710 kg**. Still no hover (T/W 0.72).
- **B. Hover-capable**: 1 × TG600 + 705 kg P50B-class pack → ≈2,215 kg, and the loop diverges.
- **C. Hover-capable**: 2 × TG600 (540) + 304 kg Amprius 10C → ≈2,085 kg, and the loop diverges.
- **D. Optimistic**: low-end subtotal 900 + fuel 50 + TG600 240 + 235 kg Amprius 15C (D2b, FM 1.0) → ≈1,425 kg, converging to about 1,535 kg.

All DERIVED.

**Achievable T/W at 1,300 kg** with the baseline (1.0 MW continuous / 1.2 MW 10-s peak, 25 kW accessories) (DERIVED):

| Area | FM 0.65 (cont / peak) | FM 0.80 (cont / peak) | FM 1.00 (cont / peak) |
|---|---|---|---|
| D1 | 0.69 / 0.78 | 0.79 / 0.89 | 0.91 / 1.04 |
| D2 | 0.63 / 0.71 | **0.72 / 0.82** | 0.84 / 0.95 |
| D3b | 0.50 / 0.56 | 0.57 / 0.65 | 0.66 / 0.75 |

**Maximum mass that can hover with a 15% thrust reserve** (D2, FM 0.8) (DERIVED):

| Powertrain (peak electrical) | Maximum hover mass |
|---|---|
| Baseline (1.2 MW) | **924 kg** |
| 1 × TG600 + 400 kg P50B-class (1.39 MW) | 1,020 kg |
| Honeywell 1 MW + 400 kg P50B-class (1.79 MW) | 1,210 kg |
| 2 × TG600 + 300 kg Amprius 10C (1.98 MW) | 1,295 kg |

All of these exclude the CG offset penalty.

**Endurance where hover is possible** (DERIVED):
- 2 × TG600 + 300 kg P50B-class: 378 s energy-limited, about 2–3 min thermally limited.
- Baseline at 924 kg: the deficit of about 378 kW gives ≈277 s energy-limited, about 2 min thermally limited.

**Control margin** (DERIVED):
- Recommend **≥15% thrust reserve (10–20%) on the most heavily loaded pod**.
- At CG −0.25 m the rear pods already carry 14.4% above the mean, so the reserve is almost gone unless the pods are sized for about 0.33 W each or the CG moves to x ≈ −0.025 m.
- The power multiplier for a 10 / 15 / 20% reserve is 1.154 / 1.233 / 1.315.

**Sensitivities** (DERIVED):
- **Mass**: P_hover ∝ m^1.5, so +100 kg (+7.7%) means +11.8% (≈ +190 kW).
- **Disk area**: P ∝ A^−0.5. Going from D2 to D1 (+30% area) saves 12%; from D2 to D3b (−50%) costs 41% more.
- **Figure of merit**: P ∝ 1/FM. 0.8 → 0.65 costs 23% more; 0.8 → 1.0 saves 20%.
- **Density**: P ∝ ρ^−0.5. ISA+20 °C at sea level adds 3.4%; ISA at 1,500 m adds 7.6%; ISA+20 °C at 1,500 m adds 11.4%.
- **CG**: CG −0.25 m adds 22% power on each rear pod.
- **Buffer mass**: about +51 kg per +100 kW of deficit with P50B-class cells, about +26 kg with Amprius 15C (claim).

## 7. Minimal wingborne speeds: stall clean / flapped at 1,100–1,400 kg, power required vs speed, partial powered lift, rolling take-off distances

### Takeaway
Stall speeds (S 4.06 m², wing only) are **60–68 m/s clean (CLmax 1.2)** and **52–59 m/s flapped (CLmax 1.6)** over 1,100–1,400 kg, with wing loadings of 271–345 kg/m². In practice the minimum wingborne speed is about **62–65 m/s at 1,300 kg** (1.1 × V_s flapped). It is probably about **70 m/s** if the repo's canard-only trim limit holds. Two A8 constraints shape take-off and the flight band:
- **Partial powered lift is impossible during the ground roll.** The pods only tilt about X, so a wheel either rolls or lifts.
- **In the air, partial powered lift barely lowers the power needed below about 40 m/s.** Ram drag and lift-fan power keep it near 1.4–1.6 MW.

Rolling take-off on wheel drive to V_LOF takes **≈290 m in 8.6 s at 1,300 kg with 500 kW** (≈420 m to 70 m/s). One TG600's power to the rear fans holds level flight only between about **57 and 76 m/s at 1,300 kg**.

### Cited Findings
- **Owner-supplied wing data**: S 4.06 m², span 5.19 m, MAC 0.872 m, CLmax 1.2 clean / 1.6 flapped; two canards of 0.278 m² each (task brief).
- **Repo**: the canards can't trim alone below about 70 m/s, so the wheel-thrusters must keep pitch authority until then; neutral point −0.15 m against an estimated CG of −0.25 m — repo `docs/phantom/A9_WING_CASSETTE_REVISION.md`
- **A8 kinematics** (MEASURED-K): the pods rotate only about X, by 90° (road ↔ VTOL). The legs extend 0.52 m in VTOL mode and have shock feet, not wheels.
- **A8 frontal area** 2.04 m² and body planform about 7.46 m² (MEASURED-K, §5).

### Inferences
**Stall speeds** (DERIVED; V_s = √(2W/(ρ S CL))):

| Mass (kg) | Clean CL 1.2 | Flapped CL 1.6 | + canards (CL 1.0) | + body lift (7.46 m² × CL 0.2, SYNTHETIC) | W/S (kg/m²) |
|---|---|---|---|---|---|
| 1,100 | 60.1 m/s (117 kt) | 52.1 (101 kt) | 50.0 | 45.4 | 271 |
| 1,200 | 62.8 (122 kt) | 54.4 (106 kt) | 52.2 | 47.4 | 296 |
| 1,300 | 65.4 (127 kt) | 56.6 (110 kt) | 54.3 | 49.4 | 320 |
| 1,400 | 67.8 (132 kt) | 58.7 (114 kt) | 56.4 | 51.2 | 345 |

**Wingborne power required at 1,300 kg, wing only** (DERIVED). Drag model: body CdA 0.65 m², wing and canard CD0 0.008, AR 6.63, e 0.75, flap ΔCD 0.04 when CL > 1.2 (all SYNTHETIC); rear-fan shaft power from the momentum model in §5:

| Speed (m/s) | CL | Drag (kN) | Thrust power (kW) | Rear-fan shaft power (kW) |
|---|---|---|---|---|
| 62 | 1.32 | 3.1 | 193 | 482 |
| 70 | 1.05 | 2.9 | 204 | 467 |
| 80 | 0.80 | 3.3 | 268 | 590 |
| 100 | 0.51 | 4.6 | 463 | 985 |
| 130 | 0.30 | 7.4 | 957 | 2,003 |
| 160 | 0.20 | 10.9 | 1,749 | 3,645 |
| 178.8 | 0.16 | 13.6 | 2,428 | 5,052 |

The power curve bottoms out near 70 m/s; 1,100 and 1,400 kg are within ±10% below 80 m/s.

**Level-flight speed band**, wing only (DERIVED; lower bound = stall at CL 1.6):

| Mass (kg) | 535 kW rear shaft (≈1 TG600 after losses and accessories) | 1,000 kW rear shaft |
|---|---|---|
| 1,100 | 52.5–79 m/s | up to about 100 m/s |
| 1,300 | **57–76 m/s** | up to about 100 m/s |
| 1,400 | 59–73.5 m/s | up to about 100 m/s |

Climb margin with one TG600 is small; for example, 0.55 kN of excess thrust at 62 m/s is about a 4% climb gradient.

**Partial powered lift in the air** (transition corridor, 1,300 kg; DERIVED). Assumptions: D2 area, FM 0.8 with hover-like induced power (conservative, no forward-speed benefit), ram drag √(ρAT)V, wing at CL_op 1.3 flapped:

| Speed (m/s) | Wing share of weight | Pod vertical thrust (kN) | Lift-fan power (kW) | Ram drag (kN) | Aero drag (kN) | Rear power, electrical (kW) | **Total electrical (kW)** |
|---|---|---|---|---|---|---|---|
| 0 | 0% | 12.75 | 1,591 | 0 | 0 | 0 | **1,591** |
| 10 | 2.5% | 12.43 | 1,531 | 0.96 | 0.08 | 74 | **1,605** |
| 20 | 10% | 11.46 | 1,355 | 1.84 | 0.32 | 233 | **1,588** |
| 30 | 23% | 9.84 | 1,079 | 2.56 | 0.71 | 451 | **1,530** |
| 40 | 41% | 7.58 | 729 | 2.99 | 1.26 | 695 | **1,424** |
| 50 | 63% | 4.67 | 352 | 2.93 | 1.97 | 895 | **1,247** |
| 55 | 77% | 2.97 | 179 | 2.57 | 2.39 | 933 | **1,112** |
| 60 | 91% | 1.11 | 41 | 1.72 | 2.84 | 854 | **895** |
| 65 | 100% | 0 | 0 | 0 | 3.19 | 547 | **547** |

Minimum sustainable speed by total electrical power available (DERIVED):

| Total electrical power | Minimum speed |
|---|---|
| 600 kW | ≈64 m/s |
| 1.0 MW | ≈58 m/s |
| 1.2 MW | ≈52 m/s |
| ≥1.6 MW | down to hover |

**Rolling take-off** (DERIVED). Wing only, pods in road mode with 4WD wheel drive. Traction μ 0.9, rolling resistance 0.015, ground-roll CL 0.3 and take-off flap ΔCD 0.02 are all SYNTHETIC. Each cell gives distance and time.

To V_LOF = 1.1 × V_s(CL 1.6):

| Mass (V_LOF) | Wheels 300 kW | Wheels 500 kW | Wheels 500 + rear 500 kW | Rear only 600 kW | Rear only 1,000 kW |
|---|---|---|---|---|---|
| 1,100 kg (57.3 m/s) | 302 m / 9.0 s | 240 m / 7.8 s | 163 m / 5.3 s | 606 m / 18.6 s | 374 m / 11.9 s |
| 1,300 kg (62.3 m/s) | 472 m / 12.1 s | **292 m / 8.6 s** | 207 m / 6.2 s | 939 m / 25.8 s | 555 m / 16.0 s |
| 1,400 kg (64.6 m/s) | 587 m / 14.0 s | 337 m / 9.3 s | 239 m / 6.7 s | 1,154 m / 30.1 s | 665 m / 18.3 s |

To the trim-limited 70 m/s:

| Mass | Wheels 300 kW | Wheels 500 kW | Wheels 500 + rear 500 kW |
|---|---|---|---|
| 1,100 kg | 655 m / 14.5 s | 426 m / 10.7 s | 275 m / 7.1 s |
| 1,300 kg | 771 m / 16.5 s | **418 m / 10.5 s** | 286 m / 7.3 s |
| 1,400 kg | 830 m / 17.6 s | 438 m / 10.8 s | 301 m / 7.6 s |

- **Handover at liftoff** (1,300 kg, 62.3 m/s, CL 1.32 + flap): drag is 3.10 kN. Rear thrust is 3.18 kN at 500 kW (no climb), 3.65 kN at 600 kW (about 4% gradient) and 5.36 kN at 1,000 kW. **Rear-propulsor power of at least 600–800 kW at rotation is the binding requirement.**
- **Unresolved design conflict**: rolling take-off and landing happen at 57–65 m/s, below the about 70 m/s canard-only trim limit, but in the A8 the pods can't give pitch thrust while their wheels are rolling.

### Gaps
- No CFD for body CdA, body lift or pitching moment.
- No canard CLmax or trim polar.
- No flap ΔCL/ΔCD data.
- No tyre or road-surface data for μ and rolling resistance at 60–70 m/s.
- No model of lift-fan performance in crossflow (inlet momentum drag, pitching moment); ram drag is a simple estimate.

## 8. Recommended provisional simulator parameter set (with ranges), plus proposals that need owner approval

### Takeaway
Use a **physics-honest baseline**: D2 fans, one TG600-class source, a 200 kg high-power buffer. **At 1,300 kg the expected result is "no hover"** (T/W 0.72 continuous, 0.82 for 10 s), with wingborne flight between about 57 and 76 m/s and a rolling take-off of about 300–420 m. This is the correct physical result and should not be tuned away.
- **P1 hover bench tests** need a declared light test mass of **≤ about 900 kg**, or a separately labelled "VTOL-enabled synthetic variant" (2 × 600 kW + 300 kg Amprius-class buffer), which is **mass-inconsistent with 1,300 kg**, needs owner approval, and must be logged as such.
- All values are SYNTHETIC_UNVALIDATED unless another label is given.

### Cited Findings
- All sources are cited in §§1–7. The contract requirements are in repo `docs/phantom/SYSTEMS_CONTRACT.md` and `docs/phantom/SYNTHETIC_COMPONENTS.md`: unknowns stay null until a documented provisional value is chosen, every value gets lower / nominal / upper alternatives, and nothing is tuned until the mission succeeds.

### Inferences
**Recommended values** (fields follow `inputs/phantom_simulation_manifest_v0.json`; **bold = recommended**, [range]):

**Wheel pods** (each; layout identical, CW/CCW alternating):

| Parameter | Recommended [range] | Label |
|---|---|---|
| `position_body_m` (CAD frame) | FL (1.54, −1.04, 0.42), FR (1.54, 1.04, 0.42), RL (−1.59, −1.04, 0.42), RR (−1.59, 1.04, 0.42) | MEASURED-K |
| Fan annulus | **r_hub 0.110, r_tip 0.245 m → A 0.1506 m²** [0.075–0.196] | DERIVED from MEASURED-K |
| `effective_disc_radius_m` (equivalent area) | **0.219** [0.155–0.250] | DERIVED |
| Duct exit-area ratio σ_d | **1.0** [0.85–1.2] | SYNTHETIC |
| FM_open | **0.80** [0.65–1.00] | SYNTHETIC |
| `shaft_power_max_w` (≤30 s) | **460,000** [350,000–600,000] | DERIVED |
| Continuous shaft power | **370,000** [300,000–450,000] | DERIVED |
| `thrust_max_n` | **3,700** [3,000–4,400] | DERIVED = (0.8 × 460 kW)^(2/3)·(2ρA)^(1/3) |
| Hover rpm | **8,200** [7,400–9,000] (tip 210 m/s [190–230]) | DERIVED |
| Torque | **430 N·m hover / 530 N·m peak** [390–590] | DERIVED |
| k_T | **4.3e-3 N/(rad/s)²** | DERIVED |
| k_Q | **5.9e-4 N·m/(rad/s)²** | DERIVED |
| Rotating inertia | **0.10 kg·m²** [0.05–0.20], fan decoupled from tyre | SYNTHETIC |
| `spool_time_s` (first-order on ω) | **0.10** [0.05–0.20] | DERIVED |
| Motor torque headroom | 25% over hover torque for ≤30 s | SYNTHETIC |
| `tilt_rate_rad_s` | **1.26** [0.6–2.0] | MEASURED-K animation timing; not an actuator rating |
| η_motor / η_inverter | **0.95 / 0.98** [0.93–0.97 / 0.97–0.99] | SYNTHETIC |
| Motor + inverter mass | **38 kg** [30–50] | DERIVED |
| Pod mass without motor | **25 kg** [20–35] | SYNTHETIC |
| Motor heat in hover | ≈19.5 kW per pod; active fan-stream cooling required | DERIVED |
| Winding limit | **150 °C** [130–180] | SYNTHETIC |
| Ram drag in crossflow | **√(ρ A T)·V** per pod | DERIVED |

**Rear thrusters** (each):

| Parameter | Recommended [range] | Label |
|---|---|---|
| `position_body_m` | **(−2.29, ±0.40, 0.51)**; exit plane x −2.41 | MEASURED-K |
| Exit area | **0.0445 m²** [0.0445–0.0777] | MEASURED-K / DERIVED |
| `shaft_power_max_w` | **300,000** [200,000–400,000] | SYNTHETIC |
| `thrust_max_n` (static) | **2,420** [2,000–2,900] at 300 kW; momentum lapse with speed (≈1,830 at 62 m/s, ≈1,160 at 179 m/s per fan) | DERIVED |
| `spool_time_s` | **0.15** [0.10–0.30] | SYNTHETIC |
| Mass | **35 kg** [25–45] | SYNTHETIC |

**Electrical:**

| Parameter | Recommended [range] | Label |
|---|---|---|
| `architecture_selected` | **"A_series_turboelectric"** | per contract |
| `bus_voltage_v` | **800** [540–900] | consistent with GENeUS 550–800 VDC, Turbotech 630–800 V, EMRAX 100–830 V (MANUFACTURER) |
| `generator_power_cont_w` | **600,000** (one TG600-class unit) | MANUFACTURER rating of a different machine |
| Declared generator alternatives | 1,000,000 (Honeywell class); 1,200,000 (2 × TG600) | MANUFACTURER |
| Generator mass | **270 kg** per 600 kW [240–320] | DERIVED |
| Generator efficiency | **0.96** [0.95–0.97] | MANUFACTURER-anchored |
| SFC | **0.36 kg/kWh_e** [0.31–0.42] | SYNTHETIC |
| `generator_spool_time_s` (15→95%) | **3.0** [1.5–5.0]; τ ≈ 1.0 s, ramp limit 0.3 P_rated/s, cold start 60 s | ≤5 s REGULATORY_REFERENCE bound |
| Buffer | **200 kg** high-power Li-ion [100–400] | SYNTHETIC |
| `buffer_energy_j` | **1.31e8 total, 1.05e8 usable** (36.4 / 29.1 kWh at 182 Wh/kg, 80% DoD) [0.5e8–2.0e8] | DERIVED/SYNTHETIC |
| `buffer_power_discharge_cont_w` | **400,000** [300,000–780,000] | DERIVED |
| `buffer_power_discharge_peak_w` (10 s) | **600,000** [400,000–1,000,000] | DERIVED |
| Charge power | **200,000** [100,000–400,000] | SYNTHETIC |
| Round-trip efficiency | **0.90** [0.85–0.95] | SYNTHETIC |
| `buffer_soc_initial` | **0.90** [0.80–1.00]; minimum SOC 0.10–0.15 | Lilium practice, MANUFACTURER |
| `buffer_temperature_max_k` | **333.15** (60 °C ambient/discharge limit); cell cut-off 353.15 (80 °C) | MANUFACTURER, P50B family |
| Buffer heat capacity | **≈700 J/K per kg of pack** | SYNTHETIC |
| `radiator_heat_rejection_w` (zero airspeed, A8 core) | **45,000** [30,000–80,000] | DERIVED |
| `hover_cooling_fan_power_w` | **2,000** [1,500–6,000] | DERIVED |
| `actuator_power_reserved_w` plus avionics/accessories | **25,000 total in hover** [15,000–35,000] | SYNTHETIC |

**Mass:**

| Parameter | Recommended [range] | Label |
|---|---|---|
| `mass_kg` | **1,300** [1,100–1,400], owner target; log "mass closure not demonstrated: build-up 1,425–2,215 kg" | DERIVED |
| P1 hover test mass | **≤900 kg**, declared | SYNTHETIC |

**Aerodynamics** (for minimum speed):

| Parameter | Recommended [range] | Label |
|---|---|---|
| CL_op in transition | **1.3** | SYNTHETIC |
| Wing CD0 | **0.008** [0.006–0.012] | SYNTHETIC |
| Oswald e | **0.75** [0.70–0.85] | SYNTHETIC |
| Body CdA | **0.65 m²** [0.45–0.85], from 2.04 m² frontal area (MEASURED-K) × Cd 0.32 | SYNTHETIC |
| Flap ΔCD | **0.04** | SYNTHETIC |
| Minimum wingborne speed at 1,300 kg | **62 m/s** [57–70]; **70 m/s** if the canard-only trim limit holds | DERIVED |

**Expected outcomes with this set** (DERIVED; use as regression checks):
- At 1,300 kg: no hover (T/W 0.72 continuous, 0.82 for 10 s).
- Hover is possible at ≤924 kg with a 15% reserve, for about 2–5 min (thermal and energy limits).
- Wheel-drive rolling take-off of 292 m at 500 kW to 62 m/s (418 m to 70 m/s).
- Level flight between 57 and 76 m/s on one TG600.
- No 400 mph.

**What would make hover feasible or longer: PROPOSALS, each needs owner approval** (DERIVED numbers):
1. **Much larger lift-fan area.** Four fans of about Ø1.0 m (2.96 m², disk loading 4.3 kN/m²) cut hover to **718 kW electrical (885 kW peak)** at 1,300 kg (FM 0.8). That fits one TG600 plus about 150 kg of buffer. The fans would have to sit outside the wheels, in the body or wings like the XV-24A, which changes the design lock.
2. **Use the whole wheel as the fan** (r_tip 0.35 m, 1.39 m²): 1.05 MW electrical (1.29 MW peak). This needs a hubless or thin-tread wheel concept instead of a road tyre.
3. **Lower the gross mass.** Hover with a 15% reserve is possible at ≤924 kg with the baseline, or ≤1,020 kg with a 400 kg buffer. P ∝ m^1.5, so each −100 kg saves about 12%.
4. **Open and clean the pod flow path.** Remove the solid structural disk; move the Ti bracket, pin and pylon out of the disk plane (gains D2/D2b instead of D3b, −29% to −33% power); stop the fenders overhanging the inlets in VTOL pose; add a 10° diffuser of about 0.5 D length (σ_d ≈ 1.2, −9% ideal power); keep tip clearance small (0.1% D). Together these could push FM_open toward 1.0 (−20% power against FM 0.8).
5. **Move the CG to the pod centroid** (x ≈ −0.025 m). This recovers the 14% thrust margin the rear pods lose at CG −0.25 m.
6. **Add a second 600 kW source** (2 × TG600) **with a 300–400 kg buffer**. Hover becomes possible at 1,300 kg (T/W 1.07–1.15) for 6–8 min of energy, but the total mass rises to about 2.1 t, so it does not close.
7. **Cooled high-power cells** (the Amprius 15C claim, about 3.9 kW/kg pack). This halves buffer mass against P50B-class cells, but the buffer is still about 357 kg with one TG600.
8. **Make rolling take-off the primary mode** and use VTOL only at light weight (single occupant, low fuel) or as short emergency landings of ≤30–60 s.
9. **Add a central body lift fan** (F-35-style) or fans under the floor. This adds area without growing the wheels.
10. **Rear propulsors**: increase exit area to ≥0.15–0.25 m² total for better low-speed thrust, and budget ≥800 kW at rotation. The 400 mph target needs CdA ≲ 0.2 m² and multi-MW propulsion, a separate owner decision.
11. **Thermal**: put the pod motors in the fan streams, enlarge the radiator face to ≥0.5 m² with 5–6 kW of fans, or declare a thermal-storage hover limit of 60–120 s.

### Gaps
- No manufacturer operating maps for any selected component, so every pod, generator and buffer value is still SYNTHETIC, DERIVED or a MANUFACTURER value for a different machine.
- Ground effect and suckdown, inlet-distortion losses and crossflow lift-fan behaviour need CFD or a rig test before P1 results mean anything for real hardware.
- The mass ledger is the biggest single uncertainty, and it controls whether VTOL is even physically possible.
