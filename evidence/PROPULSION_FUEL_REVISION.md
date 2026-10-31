# Fuel, regulated shaft power and downward-exhaust study

31 October 2026. This extends `EXPERIMENT_REPORT.md`; prior flights and their
physical configurations remain unchanged. No stable-flight result is inferred
from these calculations or shaft tests.

## Reduced test loading

New missions default to **10 kg total fuel, 2.5 kg per protected cell**, retaining
the 170 kg occupant ballast. The allocated R5 test mass falls from 1046.66895 kg to
**996.66895 kg**. This removes 490.3325 N of weight and reduces ideal induced hover
power 7.08% at the same 16 m² disk area. It raises the neutral CG18.66 mm because
the removed fuel was low in the frame; reduced mass does not establish improved
attitude stability. Full mass tensors and CG are recomputed by the live plant.

The planning choice is a 120 s test plus 2 kg fuel allowance. At the provisional
469.8 kW maximum continuous shaft output and 0.4 kg/kWh SFC,120 s uses 6.264 kg;
8.264 kg including that allowance rounds to 10 kg. This is not a qualified reserve
or endurance statement. Custom 1–110 kg loads and 10/20/60 kg suggestions are
available before a new sortie. Retrying preserves old loading unless explicitly
changed; the browser sends the operator's current selection. Active aircraft
fuel cannot be edited to shed mass in flight.

## Shaft power and RPM

The old P-only governor needs speed error to supply load torque. The independent
synthetic-polar hover calculation predicts about 86 rpm droop at 1200 rpm command.
Actual prior-flight logs show 1102–1117 rpm while shaft output remained below 48%
of the 469.8 kW reference rating. The observed instability therefore is not
explained by rated power exhaustion. Trim, pilot delay and mechanical coupling
remain open control problems.

The proposed local PI shaft regulator retains Kp 180 Nm/(rad/s), adds a 2 s integral
time (Ki 90), conditional anti-windup, and a drive fuel-cut at 101% of commanded
RPM. The threshold is a proposed governor setting, not a blade structural
rating. No speed, angular momentum or position is clipped; overspeed coasts
under actual aerodynamic loading. The controller reads only common shaft
speed and engine command. It cannot hold altitude, attitude or navigate.

New test missions default to a **300 kW shaft-output ceiling** with the previously
documented **1200 rpm experimental gearset**. The ceiling can be selected from
10–469.8 kW before a sortie. The existing torque, spool and fuel limits remain;
actuator supply is charged before drive power and fuel burn follows actual
shaft output under the unchanged SFC assumption. This does not consume 300 kW
continuously. The nominal static hover calculation at 10 kg fuel is approximately
**202.82 kW before actuator loads**,16.951° collective. Weak-polar sensitivity
(CLmax 0.8) leaves only 2.6% peak thrust margin; neither the polar nor rotor/gear
rating is qualified.800 rpm still cannot support this test mass.

The articulated, clamped dynamometer compared a 20° collective load at the same
1200 rpm command. The prior regulator settled at 1107.02 rpm/213.88 kW; PI at
1199.64 rpm/272.21 kW. These are different achieved speeds and thrusts, not an
efficiency comparison. PI peak speed on unloading was 1212 rpm under its fuel
cut; stored rotational energy was not erased. All samples remain below the
300 kW test ceiling. Thus improved RPM regulation can increase consumption at
the same blade pitch. Load reduction and selecting an appropriate pitch are
what reduce the required hover power. This bench is not a piloted flight.

## Downward exhaust: sizing, not assumed lift

The official Rolls-Royce reference lists C30P exhaust ports as **Up**. The
schematic P0-V4 engine has no dimensioned exhaust outlets. Downward exhaust
would require a new installation: ducts, supports, heat shielding, pressure-loss
assessment and plume/ground-clearance evaluation. The available engine SFC and
MGT values do not provide nozzle mass flow, total pressure or temperature.

For an entire engine/duct control volume, the static reaction includes outlet
momentum and pressure, with the inlet terms also included in moving flight:

`F = mdot_exhaust * V_exit + (p_exit - p_ambient) * A_exit`

`P_jet = 0.5 * mdot_exhaust * V_exit²` for the pressure-matched static example.

Exhaust flow includes engine airflow plus fuel. Fuel flow alone cannot supply
it. The force acts along the aircraft's outlet axes and about their real moment
arms, not always vertically in world coordinates. Duct bend and final outlet
reactions must not be counted twice. Residual exhaust energy cannot also be
counted as shaft output. Added backpressure may reduce available shaft power
and change SFC; added duct mass removes some lift benefit.

One explicitly hypothetical sizing case assumes 2 kg/s exhaust,100m/s exit speed,
700 K static outlet temperature,101325 Pa pressure and R =287J/(kg K). Two equal
downward circular outlets would each be **158.89 mm diameter**; total area
0.03965 m², ideal reaction 200 N and jet kinetic power 10 kW. One metre total straight
thin-wall tubing at assumed 1 mm wall and 8000 kg/m³ density weighs about 4 kg,
excluding bends, mounts and shielding. These assumptions are not C30P data or
released hot-duct material choices. Installed net benefit remains unknown.

To equal the 490.33 N weight benefit of the fuel reduction at a hypothetical 2 kg/s
would require 245.17m/s exit speed and 60.11 kW jet kinetic power. Removing that
weight saves 11.76 kW of ideal rotor induced power. Diverting new shaft power into
such a jet is therefore unattractive in this comparison. Recovering an existing
residual jet is a different calculation and requires its measured exhaust state
and the installation penalty map.

**No positive exhaust force was added to the flight plant.** Without those
inputs, doing so would invent lift. The calculator, sensitivity cases and
unknown-input register are saved for a concrete installation review.

## Evidence

- `power_fuel_exhaust_study.json`: full CG/inertia, fuel plan, conditional two-outlet sizes and dynamometer samples.
- `wolfram_power_fuel_exhaust.json`: independent Wolfram arithmetic query/result.
- `exhaust_independent_review.md`: Rolls-Royce and NASA primary-source links and installation blockers.
- `power_independent_review.md` / `.json`: separate power, hover sensitivity and prior-flight latency analysis.
- `tools/power_fuel_study.py --dynamometer`: reproducible calculation and clamped bench, never flight controls.

The keyboard guide starts closed on load and on browser-history restoration.
Only the Keyboard controls button opens it; Close/Escape dismiss it.
