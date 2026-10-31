# Independent power and stability review

This review uses the existing P0-V4A R5 geometry/allocation, the unchanged
synthetic axial BEMT polar and the recorded R5 flight. It does not change the
aircraft, issue controls or constitute a new flight. Numerical inputs/results
are in `power_independent_review.json`.

## Reduced fuel load

Reducing total fuel from 60 to 10 kg (equal fill of the four retained tanks)
changes allocated test mass from 1046.66895 to **996.66895 kg**. The 170 kg
occupant allowance is retained. Neutral CG changes by approximately
(-0.021, +4.120, +18.659) mm in source X/Y/Z coordinates. Removing low fuel
raises CG; the reduction in weight is not evidence of improved attitude
stability. Spring/damper hardware should remain unchanged between loads.

At the provisional maximum continuous rating and SFC, a two-minute fuel budget
is 469.8 kW × 0.4 kg/kWh × 2/60 h = **6.264 kg**. Adding a chosen 2 kg
planning reserve and rounding to 10 kg supplies a reasonable explicitly chosen
short-test loading. This is a planning calculation, not measured endurance,
usable-fuel qualification or a certified reserve policy.

## Static power calculation

For mass 996.66895 kg, weight is 9773.9835 N. Total disk area is 16.0000 m²
from the measured rotor radius. Ideal actuator-disk hover lower bound is
**154.335 kW**, before profile, installation and transmission losses.

The existing synthetic axial BEMT model gives the following equal-rotor static
solutions. These do not include the unequal thrust needed for CG trim, motion,
duct/rotor interactions, accessory loads or actual section measurements.

| Rotor speed | Hover collective | Rotor shaft power | Engine power before servos | Peak thrust / weight |
| --- | ---: | ---: | ---: | ---: |
| 800 rpm | No solution | — | — | 0.653 |
| 1000 rpm | 24.531° | 184.655 kW | 194.374 kW | 1.020 |
| 1050 rpm | 21.237° | 187.279 kW | 197.135 kW | 1.124 |
| 1100 rpm | 19.322° | 189.455 kW | 199.427 kW | 1.234 |
| 1150 rpm | 17.984° | 191.227 kW | 201.292 kW | 1.349 |
| 1200 rpm | 16.951° | 192.679 kW | 202.820 kW | 1.468 |

The 1000 rpm point is near the synthetic peak and reaches a modelled maximum
section incidence of 16.77°, beyond the assumed 16° stall onset. Minimizing the
table's power alone would therefore select a point with almost no lift margin.
At assumed CLmax 0.8, the 1200 rpm peak thrust/weight ratio is only **1.026**;
the nominal CLmax 1.2 value is not measured. Reducing fuel does not establish
adequate hover or manoeuvre margin across the uncertainty range.

## Why the current shaft speed droops

The previous governor applies common-coordinate torque
`Q = clip(180 (omega_reference - omega), 0, Q_limit)`. A sustained positive
load necessarily requires a sustained speed error. Solving the hover and
governor equations together at 10 kg fuel and a 1200 rpm reference gives:

- Actual speed **1113.574 rpm**, a droop of **86.426 rpm**.
- Collective **18.916°**, common drive torque **1629.091 Nm**.
- Engine output **199.972 kW** before accessories/servos.

The observed approximately 1100 rpm is therefore consistent with the control
law even when the engine is far from its maximum rating. Increasing the rated
power alone would not remove that proportional-governor steady-state error.

A bounded PI shaft-speed governor is a defensible disclosed mechanism change.
It must read shaft speed only, retain the existing torque/power/spool/fuel
limits, prevent integral windup at both zero and the upper torque limit, and
reset or unwind when the engine is commanded off or fuel is exhausted. It is
not a substitute for the pilot's attitude or navigation decisions.

For the root agent's proposed Kp = 180 and Ki = 90, the integral time Kp/Ki is
2 s. This does **not** imply a 2 s settling time. At neutral fixed-airframe
configuration the actual model mass matrix gives common-coordinate spin
inertia **13.90207 kg m²**, using `J_eq = v^T M v` with all four rotor signs
and the four 6016/1200 shaft ratios. Static BEMT torque scales approximately
with speed squared, giving a local torque-speed slope of 24.403 Nm/(rad/s).
The resulting fixed-geometry linearization is

`J_eq s² + (Kp + dQ_aero/domega) s + Ki = 0`.

Its poles are approximately **-14.249 and -0.454 s⁻¹**, giving roughly **8.8 s**
dominant 2% settling. This is conservatively overdamped in this narrow model.
Real turbine delays, transmission elasticity, governor sensing and actuator
hardware remain unqualified. The proposed Ki is a design hypothesis rather
than a recovered engine-controller value.

Regulating 1200 rpm does not itself lower hover consumption: the table gives
202.820 kW versus the drooped P-only equilibrium's 199.972 kW, about **1.4% more**
before servos, due to the operating-point change. It also increases rotor
angular momentum relative to the drooped speed. The benefit is predictable
shaft-speed response and restored thrust margin, not free power or guaranteed
attitude stability.

## What the actual flight shows

Run `20261031T071731-4e6434` contains 20 accepted decisions. In the airborne
window 37.4–46.1 simulated seconds, engine output was **193.45–223.83 kW**,
at most **47.64%** of the provisional 469.8 kW rating. Rotor speed was
1102.27–1116.62 rpm. The recorded mechanical tilt/cabin servo load was at most
37.95 W; individual pitch-servo power is not represented by that number.
The maximum observed X angular rate was 21.18°/s, while Y and Z rates reached
4.92 and 2.01°/s respectively in that window. Nacelle-angle feedback deviated
from neutral and showed coupled response after the small vector test.

Accepted observations were **0.1105–0.9075 simulated seconds old**, mean
**0.4202 s**, before the additional 20 ms control transport and actuator lag.
At a 20°/s body rate, this mean observation age alone corresponds to about
8.4° of attitude change before a decision is issued. The logged alternating
roll overshoots therefore cannot be diagnosed as a lack of engine rating.
Trim, delayed piloting and articulated/gyroscopic control response must be
addressed and tested separately. No successful landing follows from this review.

## Recommended verification

1. Compare old P-only and proposed PI responses on a supported/fixed-airframe
   shaft-load bench. Continue at least 12–15 simulated seconds after each load
   step to measure the predicted settling rather than stopping during recovery.
2. Assert drive torque and total engine power limits throughout spool-up,
   abrupt load increase, sustained impossible load and unloading. Check that
   the integrator stays bounded during saturation and that recovery does not
   require a long wind-down from accumulated impossible demand.
3. Verify engine-off, near-empty fuel, reverse/zero-speed and restart cases.
   The current instantaneous `Q*omega` accounting uses pre-step speed: the
   first finite integration step at zero speed has an expected left-Riemann
   energy discrepancy. Assess accumulated energy error quantitatively rather
   than treating a single zero-speed sample as evidence of free energy.
4. Retain the actual inertia, gravity and contact model during any later live
   attempt. Use only pilot instruments for decisions. A governor bench is not
   a flight and does not demonstrate attitude stability.
5. Keep collective-pitch bearing dynamics, pitch-dependent inertia/servo work,
   turbine/vertical-shaft/exhaust mechanics and structural qualification as
   explicit gaps until implemented or supported; a PI governor does not close
   those gaps.

Any exhaust reaction added later must use the actual outlet position and full
force/moment balance. Shaft power and residual exhaust momentum must share one
engine energy budget; a specified increase in exhaust thrust is not additional
free shaft power. Exhaust data and routing losses are a separate engineering
input, not a parameter to tune until a flight succeeds.
