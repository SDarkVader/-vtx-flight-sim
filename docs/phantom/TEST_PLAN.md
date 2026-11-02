# Phantom staged tests and acceptance — P0

**Definition of success:** the independent Phantom variant can be piloted through the same human/Colin live action boundary; forces, torque, energy and contact are integrated by MuJoCo, and flight outcomes follow those forces. A rendered transformation, static component drawing or a pre-scripted path **does not** count.

All tests below are **planned, not executed** unless supported by a retained test log. Existing VTX four-fan physics regressions must pass on the same commit and remain unchanged.

## Phase 0 — configuration and model isolation

- `phantom` is an explicit new selector; existing defaults, scene model, API, payload, checkpoints and evidence remain byte-for-byte or behaviourally equivalent.
- All mandatory Phantom mass, CG/inertia, geometry, power and finite actuator fields are populated from an identified source or **declared synthetic** values. Unknown values cause a clear configuration error, not implicit energy or mass.
- Validate local XYZ to MuJoCo transform, reverse it for render, and compare exact named joint axes.
- Assert positive-definite inertia, nonzero total mass, numerical finite values, 2 occupant mass centres, symmetric wing/bus wiring by default.
- Pin source `Blendstra A8` with immutable version, but log unresolved current wing clipping and unsafe root-load assumptions.

## Phase 1 — physical ground and hover bench

- **Zero power:** supported craft remains on gear; remove ground support in an isolated fixture and verify gravity-driven downward acceleration; no engine or rotor implies no fictional thrust.
- **Torque and power:** each pod must consume finite motor/generator/battery power to generate thrust; cap motor and bus and verify thrust drops below demand under supply restriction.
- **Kinematics:** move each wheel-pod axis, measure achieved vs command, gyro torque sign, thrust vector direction, angular momentum and reaction at body mount; no instant tilt.
- **Mass/energy:** change fuel/SOC and two-seat payload, recompute CG and inertia, log physical/thermal/source-to-sink energy residual.
- **Contact:** extend/retract landing legs, roll and brake, detect tyre/strut contact and collision without jumping/changing vehicle pose.
- **Hover flight:** manual pilot can command real lift, hover, yaw, drift and land or crash naturally; no altitude hold disguised as physics. One pod stopped must alter force/moment and may make failure inevitable.

## Phase 2 — control-surface and aerodynamics bench

- Separate left/right wing force sites, nose canards, left/right outboard ailerons, left/right inboard flaps.
- At zero relative wind, lifting/control surface aerodynamic force tends to zero. At 50/75/89.408/178.816 m/s, force scales with dynamic pressure given fixed aero coefficients **until physical stall/compressibility/deflection limits intervene**.
- Check aerodynamic angle of attack and force sign in normal/inverted flight; local wing and tail loads from `v+omega × r`. No aileron control magic at hover.
- Left/right differential aileron sign creates actual roll moment; symmetric flap deflection influences lift **and drag**; deployed canards generate correct pitch sign according to their calculated force location and local flow.
- Control actuators obey torque/speed, backdrive/jam and supply draw; log hinge moments at representative dynamic pressure.
- Check aeroelastic model level: rigid wing accepted only as a declared interim P2 hypothesis; full flutter/reversal and structural stress remain **unvalidated**. Never enable unrestricted 400 mph aileron deflection on a provisional model.

## Phase 3 — wing/wheel transition and two landing modes

- For each side: **hatch open → slide outward → rotate wing → engage independent positive flight locks → reseal fairing**. The retract sequence is reverse and is inhibited by known collision and load conflicts.
- Sample *every moving joint* throughout stow/deploy/retract, not only end frames. Validate wing self-intersection, wing-to-canopy/tyre, flap/aileron-to-shell, and available door aperture.
- Wing load-transferring structure is a real mass-bearing multibody approximation with bounded compliance: high load must cause finite response or failure/derating, **not** unsupported unlimited stiffness. Folding pivot bearings are not the full structural root lock.
- **VTOL take-off and landing:** leg support, thrust vector transition, rotor spool, low-speed control authority and real contact.
- **Rolling take-off/landing:** speed target is *not* a fixed 75m/s; use computed lift/weight margin from current wing `CL`, air density, fuel/occupant mass and propulsor support. The canard must control nose pitch while wheel pod thrust vector is deactivated/rotated. Rotor shutdown angular momentum, residual lift and gyro reactions persist and are logged.
- One wing half-stowed or one latch failed cannot be presented as normal successful transition.

## Phase 4 — speed envelope, aeroelastic and thermal

- Road 200 mph is a **minimum top-speed target**, flight 400 mph **maximum target**. No implication of cruise, required take-off speed, legal road use or safe structural envelope.
- Record drag, rolling resistance, tyre speed/centrifugal loads, thrust/power feasibility, lift/trim, engine and electrical duty, Mach effects, flutter/reversal, control response and thermal limits before granting each speed band.
- For a fixed 1300 kg notional vehicle, hover/accelerate/400mph flight power must be evaluated separately; do not sum maximum power curves as independently available from the same engine.
- At zero airspeed, ram cooling vanishes. Test powered radiator fan and inlet recirculation under wheel downwash; one fan loss eventually causes temperature derating.
- Test +g/−g, gust, rapid roll command, inertial body rotation, asymmetric failure, flutter precursor/reversal detection, over-torque lock failure and low-energy recovery.
- No claims of successful 400mph flight until actual high-speed instrumented run with bounded synthetic assumptions is recorded.

## Flight evidence contract

Every run retains: immutable variant config hash + source-status map; independent physics clock and pilot action timing; actual & commanded position of every effector; per-surface aerodynamic `F,M`, per-pod thrust/torque; mass, CG/inertia; generator/buffer/shaft/propulsor power and energy; thermal states; contact/impact; fault and protection decisions; outcome. Report planned vs actual and whether any known synthetic assumptions materially control success.

## Explicit go/no-go outcomes

- **GO P1:** physical hover, descent, limited electrical energy and contact test passes; not evidence of fully wingborne flight.
- **GO P2:** consistent aerodynamic control-force/moment signs and explicit stall, with bounded power/actuation.
- **GO P3:** collision-free wing/wheel transition throughout all swept poses, correct load transfer and non-scripted landing.
- **GO P4:** operating envelope validated by recorded simulation evidence; may still contain disclosed synthetic component parameters.

Reject: false claim of hardware rating; missing inertia; negative SOC with powered thrust; instantaneous movement; invisibly corrected attitude/height; disappearing crashes; pilot access to privileged physics state; any drift of the original flown quadrotor.
