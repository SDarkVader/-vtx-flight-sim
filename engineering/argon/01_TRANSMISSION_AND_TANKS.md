# Task 01 — Transmission position and four fuel tanks (FIRST CHANGE)

**Only implement this bounded task until the user reviews a before/after diff.**

## Problem and known evidence

The original source includes misplaced mechanical parts. Verified R2 repair candidates in `evidence/source/assembly_repairs.json` move an F1 example vertical torque shaft from a zero-world transform to the fan station near x=2.60 m, spanning approximately z=0.42–2.07 m, and propose a vectoring output extension near z=2.16–2.31 m. Equivalent work is documented for other branches. These are geometric repair *proposals*, not proven transmission joints.

The new independent planetary arrangement is a separate concept model. It must not be treated as fitting the present R5 airframe by default. The source may show incorrect shaft axis, gearbox orientation, centerline spacing and bearings. The live simulator currently uses ideal common-drive equality constraints.

Four protected diagonal fuel tanks occupy the lower structure; their centroids and orientation are recoverable from the assembly ledger. The plant uses equal tank quantities and provisional fixed-cylinder inertia estimates; no slosh model, asymmetric draw management, validated pressure or actual installation has been established.

**Changing gearbox and tanks affects fuel feed, CG, full inertia, yaw/roll coupling, fan moment arms, shaft supports and collision geometry. Resolve them together.**

## Investigation

1. Pin baseline R5 plus PR #4 exact commit, inventory all P03 shafts/gears/bearings/output stubs, P06 gimbal supports/actuators, P07 fuel tanks, primary rings/braces and cabin. Read `tools/build_airframe.py` and `evidence/source/assembly_repairs.json`; map every candidate by stable source object ID, local/world matrix and parent hierarchy. Verify P0-V4/R5 and latest undercarriage, without accidentally using a schematic transmission as the aircraft master.
2. Build a branch-wise mechanical chain for F1–F4: common turbine shaft -> distribution -> reduction/gearbox -> reversing stages -> radial shafts -> local vertical shaft -> upper nacelle pivot -> rotor spin shaft. Include whether each joint moves during tilt, and show torque crossing the gimbal with bearings, flex coupling/CV or another **explicit** feasible interface. Do not allow a shaft to clip its support.
3. Build a spatial envelope for transmission replacement: motor-generator, planetary ring, fixed reduction, wiring, DC bus, brake if hypothesised, cooling/lubrication and service clearance. Locate these objects as **proposed** components; cost and size must come from actual candidate data or declared uncertainty.
4. Extract each tank's exact source mesh, centroid, orientation, gross and usable volume hypothesis, point attachments, plumbing, exposed thermal areas and clearances. Evaluate multiple physically viable layouts around drive shafts and movable fans. Recheck six undercarriage stroke envelopes and cockpit.
5. Sweep each cowling through all 360 degrees of *tilt direction* and up to 20 degrees *resultant tilt angle*. Start with sampled collision tests, then finer/adaptive sweep or continuous collision bound, including blade tips, ducts, structure, tank bodies, transmission housing, wiring, adjacent units and cabin. Explicitly distinguish visual clearance, tolerance, load deflection and failure-critical clearance.
6. Recalculate actual mass allocation, 3-D CG and **full symmetric 3×3 inertia** after each move. Include all gearbox/drive/motor-generator/cooling additions, removal and substitutions; do not duplicate mass in an assembly and its replacement.
7. Recalculate at least at 10 / 20 / 60 / 110 kg total fuel plus deliberately asymmetric load examples. Determine effect on available thrust and rotor wrench controllability at each condition, but do not retune the controller yet. Fuel slosh and lines must either be modelled at justified fidelity or reported as missing.
8. Preserve candidate variants for comparison; use the same physics solver, loading, starting height, world and pilot-control sequences. Do not alter historical records or suppress collisions, tip-over or insufficient lift.

## Required calculations

CG from source mass allocations:
```
r_CG = sum(m_i * r_i) / sum(m_i)
I_CG = sum(I_i + m_i * ((d_i·d_i)*Identity - d_i*d_i^T))
d_i = r_i - r_CG
```
Reject zero/negative masses, non-positive-definite inertia, broken shaft connectivity, discontinuous load paths and control channels that can produce unavailable thrust.

Check static force at test mass 996.66895 kg:
```
W = m*g ~= 9773.98 N
W/4 ~= 2443.50 N per fan before control reserves
```
These figures are **for pre-change low-fuel allocated R5**, not automatically valid after new mass or gearbox installation.

## First task output and stop rule

Create a derived model/variant name (e.g., `P0-V4A-R6-placement-study`, but choose an unoccupied revision). Include:
- source-ID annotated gearbox/tank transform table (old vs proposed), assembly visuals or geometry inspection;
- four complete mechanical power and joint paths;
- physical clearance/collision matrices at allowable tilt cone;
- pre/post fuel volume, tank protection/routing and CG/inertia matrices;
- comprehensive mass ledger delta and potential new engine/rotor power demand;
- baseline physics/contact tests plus reproducible variant tests and explicit failures;
- open blockers for gear tooth design, shaft strength, mount stiffness, motor curve, insulation, fuel slosh, certified component data and real measurement.

**Stop and return evidence and diff. Do NOT silently install variable drive, change pilot command semantics, tune airframe damping, invent lift or activate ECU.**
