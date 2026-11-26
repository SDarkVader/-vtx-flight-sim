# R6 fan drive through the tilt pivot: Wolfram engineering check (24 Nov 2026)

These results were computed with the Wolfram Language evaluator. They check the candidate `r6-r3-drive-candidate.glb`.

## Inputs

**Measured from the candidate model (F1):**
- Spindle: 86 mm across, running from z 0.60 to 1.99 m, a span of 1.39 m.
- Pivot: (2.6, 0, 1.98).
- CV ball: 160 mm. CV race: 182 mm across, top at +20 mm.
- Gearbox underside: +90 mm above the pivot, 310 mm wide.

**From the flight record and package:**
- Rotor reference speed: 1200 rpm.
- Overall ratio: 5.0133, so the radial shafts turn at 6016 rpm.
- Nacelle gearbox: 7.5:1, so the spindle and stub turn at 9000 rpm.
- Engine: 469.8 kW continuous, with a 300 kW flight limit.
- Transmission efficiency: 0.95.
- Power is assumed to split evenly across the four fans.
- Tilt limit: ±20° about each axis.

**Assumed:**
- Tube wall: 3 mm.
- Steel: E 200 GPa, 7850 kg/m³.
- High-modulus CFRP: E 135 GPa, 1600 kg/m³.
- The spindle is pinned at both ends, at the bevel gearhead and at the CV.

## Results

| Check | Result |
|---|---|
| Worst joint angle, 20° on both axes | **28.0°** |
| A single Cardan (U-joint) at that angle | Output speed swings 0.883–1.132 × input, twice per turn. This rules a U-joint out; a CV joint is needed |
| Torque per fan at 9000 rpm | 75.6 N·m at the 300 kW limit; 118.4 N·m continuous |
| Shear in an 86 mm tube with a 3 mm wall, continuous | 3.8 MPa, which is negligible |
| First whirl (critical) speed, steel tube | **7,230 rpm**: *below* the 9000 rpm operating speed |
| First whirl speed, solid steel bar | 5,294 rpm |
| First whirl speed, HM-CFRP tube | 13,157 rpm, giving a margin of 1.46 |
| Gearbox underside to CV race, worst tilt | 33.6 mm clear |

## Findings

1. **The connection holds geometrically.** The tilting gearbox stays 33.6 mm clear of the joint race even at the worst tilt.
2. **The spindle's material and supports must be specified.**
   - A 1.39 m steel spindle would run above its first critical (whirl) speed.
   - Options:
     - a CFRP tube, with a margin of 1.46;
     - a mid-span steady bearing, which halves the span and raises the critical speed about 4×;
     - a lower spindle speed.
   - This is an owner decision.
3. **The CV joint must be rated for 28° at 9000 rpm.** High-speed CV joints are usually rated for smaller angles. Confirm against a supplier datasheet, or limit the combined tilt.
4. **The physics model does not define a spindle speed.** It uses an ideal equivalent ratio, and CV and tooth compliance are not modelled. The 7.5:1 figure comes from the gearbox part name.
