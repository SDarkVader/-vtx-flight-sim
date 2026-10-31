# VTX independent fan transmissions: preliminary component and structural screen

2026-10-31. **Disposition: no installed component has passed.** This is a traceable preliminary screen, not a strength, fatigue, stability, resonance, fit, or aircraft qualification. The current live simulator retains the original coupled shaft. The earlier separate Blendstra illustration is schematic and has no working or strength-verified gears.

## Source model and loads

The R5 allocation ledger defines four fan axes at a 2.60 m radius, gimbal pivots near z=2.03 m, rotors near z=2.31 m, four blades per fan and approximately 3.333 kg m² rotor spin inertia per fan. These inertias come from an allocated mass model, not measured components. The illustrative radial shaft bounding box is about 76 mm across and bearings are depicted at radii 1.19 and 2.15 m (0.96 m spacing). Neither the bounds nor the approximate ledger mass establishes a round shaft's actual wall thickness, material, load path or bearing stiffness. The locally modeled nacelle gearbox envelope is about 310 mm diameter × 150 mm high; actual mounting and shaft routing remain to be verified. The rotor gimbal and any coupling must accommodate the requested full azimuth of tilt up to 20°.

Under the previous assumed **300 kW total mechanical input, equal load and 95% overall transfer efficiency**, output is 71.25 kW and 567 N m per fan at 1,200 rpm. The common 6,016 rpm turbine shaft would be about 476 N m total or 119 N m per branch if split equally *at that speed*. This is neither a peak torque requirement nor an approved operating condition. Unequal branches, acceleration, overspeed, thermal losses, accessories and transient gusts require separate limits. For scale, spinning the modeled 3.333 kg m² fan up at 100 rpm/s needs about 34.9 N m of additional ideal rotor torque before drag, gearbox inertia and efficiency. At 1,200 rpm and an assumed 5°/s gimbal slew, ideal rotor gyroscopic torque magnitude is about 36.5 N m; bearing/housing reactions and higher transient rates are additional. These are not design load factors.

## Planetary geometry and excitation check

The prior 20-tooth sun / 60-tooth ring example permits a 20-tooth planet for an ideal, standard unshifted equal-module spur set. **Correction:** its earlier three equally spaced planet illustration cannot satisfy the conventional equal-spacing assembly condition: (20+60)/3 is not an integer. Four equally spaced planets satisfy (20+60)/4=20. The simplified adjacent tip-clearance expression has +6.28 modules of nominal clearance with four planets, before deflection, pins, carrier and lubrication. It is not a gear-mesh or manufacturability verification. The local illustration source has been revised to four planets, but the remote model update failed and the earlier saved model still shows three. Its circles do not represent meshing involute teeth. A 20/20/60 tooth selection repeats tooth contacts and needs gear-life/hunting-tooth analysis.

For the proposed hypothetical 4:1 first stage, sun speed is 1,504 rpm at a 6,016 rpm engine shaft. With a 20:60 sun/ring, ring speed is `(4*fan_rpm - sun_rpm)/3`. This corrects an earlier erroneous rearrangement and its numerical speeds. The carrier-relative sun/planet mesh frequency is `20*abs(sun_rpm - fan_rpm)/60`:

| Fan rpm | Ring rpm | Sun mesh frequency | Four-blade passing frequency |
|---:|---:|---:|---:|
| 1,100 | 965.33 | 134.67 Hz | 73.33 Hz |
| 1,200 | 1,098.67 | 101.33 Hz | 80.00 Hz |
| 1,300 | 1,232 | 68.00 Hz | 86.67 Hz |

The 1,100–1,300 rpm range is **only a calculation sweep**, not an established permissible range. The turbine reference shaft is 100.27 Hz. At the illustrative 1,200 rpm point the mesh excitation at 101.33 Hz is near the turbine shaft's rotational frequency; proximity of two excitations alone is **not evidence of a resonance**. Near 1,253 rpm the two illustrative mesh and blade-passing curves cross; the crossing alone also does not establish resonance. Natural frequencies, mode shapes, damping, bearing and mount stiffness, load sharing and dynamic responses are unknown. Evaluate the full operating and transient range using a coupled Campbell diagram, flexible-body/gear/contact analysis, and instrumented run-up. NASA's [planetary-gear dynamics study](https://ntrs.nasa.gov/citations/20010070088) explains that mesh harmonics may excite particular natural modes and that mode response depends on configuration and torque.

## Shaft torsion scenarios — not margins

The following are **hypothetical uniform steel-like cylinders** with 76 mm outside diameter, G=79.3 GPa and 0.96 m between idealized ends. The 119 N m and 567 N m cases are distinct hypothetical locations; they cannot be superimposed or assigned to an existing shaft without the final speed/gear topology. Results exclude bending, stress concentrations, bore/spline geometry, joints, bearing loads, thermal effects and fatigue.

| Hypothetical section and torque | Peak elastic shear stress | Surface shear strain | Total twist |
|---|---:|---:|---:|
| Solid 76 mm, 119 N m | 1.38 MPa | 17 microstrain | 0.025° |
| Solid 76 mm, 567 N m | 6.58 MPa | 83 microstrain | 0.120° |
| 76/66 mm tube, 119 N m | 3.20 MPa | 40 microstrain | 0.058° |
| 76/66 mm tube, 567 N m | 15.25 MPa | 192 microstrain | 0.278° |

The difference between the two assumed sections shows why geometry and material are needed. Comparing these numbers to yield strength would still not establish suitability. As an explicitly artificial illustration, a 0.96 m fixed-base torsional spring driving only the allocated 3.333 kg m² rotor gives 45.3 Hz for the solid section and 29.8 Hz for the tube. These are **not VTX natural frequencies**: actual transmission ratios, multiple rotating inertias, shafts, mount flexibility and gyroscopic effects are omitted. They must not be used as a resonance clearance.

## Motor-generator candidates for the ring

For the fixed 567 N m carrier torque example, ideal planetary torque balance gives about 425 N m on the ring. This is a steady illustrative point, not a rating; motor speed and torque change with the chosen interface ratio and load. A proposed motor-to-ring 3:1 speed reduction with assumed 95% transfer efficiency would require approximately 149.2 N m motor torque when motoring at this point, with motor speed three times ring speed: 2,896, 3,296, and 3,696 rpm at the three illustrative fan speeds. At nominal speed ring mechanical input is 48.93 kW per branch, or 195.7 kW for four. The motor would supply approximately 51.5 kW per branch before inverter losses. The required generator and electrical source, losses and cooling must be included within the assumed total engine power; the simple 95% allocation is not a complete power balance. This high power throughput and its mass make the architecture questionable until redesigned. Regeneration uses a different loss direction; transient and unequal-load cases are unbounded. This is a proposed additional stage, not shown as a proven part in the model.

| Candidate | Published data | Screening result |
|---|---|---|
| [EMRAX 348](https://emrax.com/e-motors/emrax-348/) | Up to 396 N m continuous; 43.9 kg liquid-cooled dry; 348 mm diameter | **Fails the direct-ring nominal continuous comparison:** 425 N m exceeds the listed 396 N m. Four motors alone weigh 175.6 kg before cooling/electronics. Earlier datasheet revisions differ; use a confirmed configuration and current supplier curve. |
| [EMRAX 268](https://emrax.com/e-motors/emrax-268/) | Up to 226 N m continuous; 22.3 kg liquid-cooled dry; 268 mm diameter, 94 mm axial | At the **hypothetical 3:1/95% motoring** point, 149.2 N m is about 66% of the published maximum continuous torque. **Shortlist for investigation only**: torque-speed and cooling curves, thermal derating, four-quadrant controller, bearing loads, shock, vibration and aircraft use are not verified. Four motors weigh 89.2 kg before their 3:1 stages, inverters, coolant and mounts. |
| [YASA P400 R](https://yasa.com/media/2021/05/yasa-p400rdatasheet-rev-14.pdf) | Up to 200 N m continuous; 28.2 kg dry, 305 mm diameter; rated cooling conditions specified | 149.2 N m is about 75% of the stated maximum continuous torque for the hypothetical 3:1 motoring case. **Research comparison only**: datasheet is automotive/off-road/marine oriented; application, thermal curves, bidirectional system and aviation qualification must be confirmed. |

Four liquid-cooled EMRAX 268 motors alone are approximately 89.2 kg, almost the entire existing **91 kg P03 system allocation**. The design cannot assume those motors are incremental without a full remove/replace mass ledger; equally, it cannot assume the existing gearbox, shafts and bearings disappear. Full assembly mass, center of gravity, inertia and performance must be recomputed. No supplier has confirmed this architecture or operating duty.

## Required evidence before selecting an installed component

* Actual drawings/sections and materials of shafts, bearings, joints, attachments, gear teeth, and gimbal; ±20° swept fit of each unit and adjacent fans at all azimuths. Verify whether the variable drive is above, at, or below the gimbal, and how torque crosses it.
* Full load spectrum and four-branch transient torque/power budget, load sharing and safety factors; FEA of gears/carriers, bearing housings and frame under combined thrust, torque, vibration, thermal and landing loads. Independently assess gear contact stress and tooth root fatigue with appropriate standards and supplier data.
* Coupled torsional/lateral modal and forced-response analysis over rotor and turbine ranges, harmonics, critical-speed crossings, nonlinear backlash, and controller delay; instrumented test to validate model. Do not use the toy fixed-base frequencies above as acceptance thresholds.
* Electronic variator closed-loop stability, loss of inverter, motor or bus, common-cause failures, energy sinking, overspeed/underspeed, mechanical disconnection, and confirmed rotorcraft autorotation behaviour. No claim of fault-tolerance is made by having four branches.
* Supplier-specific continuous and peak torque-speed-temperature curves, thermal model, exact controller and DC-bus specs, mounting, aviation design/qualification documentation, service life and total mass. Bench-test one instrumented branch with independent speed feedback and complete energy balance before simulating four or asserting flight capability.

## Reproduce

Run `python tools/transmission_candidate_screen.py`. It uses only the standard library and `evidence/source/airframe_ledger.json`; it asserts the basic equal-spacing and tip-adjacency arithmetic and outputs all assumptions. Manufacturer numbers above were checked 2026-10-31 and may change; the current 348 product page differs from older PDFs, so confirm configuration with the supplier. The gear assembly condition is described in [this JSME planetary design paper](https://www.jstage.jst.go.jp/article/jamdsm/17/6/17_2023jamdsm0079/_pdf); standard tooth and carrier checks are still required for this application.
