# Independent review: downward exhaust lift

31 October 2026. Analysis only; no aircraft, fuel, UI or control files were
changed for this review. No flight was performed by the reviewer. Values below
are calculations or explicitly hypothetical sensitivities, not measured VTX
performance.

## What the available sources establish

The current P01 mass ledger contains the compressor shell, a generic M250-class
engine schematic, two mounts and heat shielding. It contains **no dimensioned
exhaust outlets**. The supplied P0-V1 PDFs and Blendstra engineering records
identify an M250-C30P reference, but give no installed exhaust airflow, nozzle
area/velocity, exit/total pressure, nozzle total temperature, duct pressure loss
or shaft-power-versus-backpressure map.

The [Rolls-Royce M250 product page](https://www.rolls-royce.com/products-and-services/civil-aerospace/helicopters/m250-turboshaft.aspx)
describes exhaust leaving the engine's middle. Its linked official
[2024 FIRST Network Directory](https://www.rolls-royce.com/~/media/Files/R/Rolls-Royce/documents/civil-aerospace-downloads/helicopters/2024-m250-rr300-first-network-directory.pdf),
printed pp. 84–85, lists C30P exhaust configuration **Up**, 650 shp reference
takeoff output and 6016 rpm output-shaft speed. Pointing the installed exhaust
downward is therefore an installation redesign with duct/mount/shield mass and
pressure loss, not a recovered existing P0-V4 mechanism. The directory's
SFC/MGT cells include 0.592/0.599 and 1414/1320°F. The accessible heading does not
explicitly state SFC units; the customary lb/(shp·h) interpretation should be
confirmed before conversion/use. MGT is not a calibrated nozzle flow state.
Those cells cannot replace an installed part-load map or establish exhaust
reaction. No exhaust airflow/exit-pressure map was found in the directory.

## Required force and energy accounting

[NASA Glenn's thrust equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/thrust-force/)
gives the momentum-flow and exit-pressure contributions. For the entire engine
plus attached duct control volume, use the incoming-air momentum and all final
outlet momentum/pressure terms. With a static, ideally expanded, downward jet,
negligible inlet velocity and positive thrust magnitude F:

```
mdot_exhaust = mdot_air + mdot_fuel
F = mdot_exhaust * V_exit             (only if p_exit = p_ambient)
P_jet = 0.5 * mdot_exhaust * V_exit^2
      = F^2 / (2 * mdot_exhaust)
```

With nonambient exit pressure retain `(p_exit-p_ambient)*A_exit`. In motion,
retain inlet momentum and evaluate the actual body/world vectors. Nozzle
direction fixed to the aircraft rotates with the aircraft; it must not supply
world-up force independent of bank. Apply the reaction at the actual mounting
line, with moment `(r_outlet-r_CG) cross F`. Do not add the full outlet reaction
and a second full internal bend-turning reaction to the same whole-aircraft
force sum.

The [NASA turboprop explanation](https://www.grc.nasa.gov/WWW/K-12/BGP/turbprp.html)
distinguishes shaft extraction from the smaller residual core contribution.
Recovering residual exhaust energy need not incur a one-for-one shaft debit,
but cannot be assumed lossless. Extracting more jet energy by reducing power
turbine expansion competes with shaft power. Added duct backpressure changes
the engine operating point; the penalty requires a supplier/bench map.
The [NASA nozzle design equations](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/nozzle-design/)
require the actual flow/pressure/temperature conditions. A small outlet alone
does not establish thrust or available pressure.

At the current **provisional** 469.8 kW shaft cap and 0.4 kg/kWh SFC:

```
fuel flow = 469.8 * 0.4 / 3600 = 0.0522 kg/s
fuel chemical power at assumed 43 MJ/kg = 2.2446 MW
shaft / chemical = 0.20930
chemical - shaft = 1.7748 MW
```

**0.0522 kg/s is fuel flow, not total exhaust flow.** The 1.7748 MW difference
includes exhaust enthalpy, heat transfer and other losses. It is not available
nozzle kinetic power. Converting that entire difference into thrust would be
an unjustified and extremely loose energy ceiling, not an exhaust model.

## Quantitative sensitivities: fuel removal versus jet lift

The existing R5 test case is 1046.66895 kg with 60 kg fuel, giving 10264.316 N
weight at 9.80665 m/s². With the model's 16 m² rotor disk area and rho=1.225,
ideal induced velocity is 16.1816 m/s and ideal hover induced power is
166.093 kW. These are ideal lower bounds; blade/profile/duct/transmission losses
remain additional. Removing fuel and keeping the four tank masses symmetric
changes actual modeled CG/inertia; it must not merely change displayed weight.

| Comparison | Remove 40 kg fuel | Remove 50 kg fuel |
| --- | ---: | ---: |
| Static force reduction, N | 392.266 | 490.333 |
| Ideal fan induced-power reduction, kW | 9.430 | 11.758 |
| Equal jet thrust kinetic power at hypothetical 1 kg/s, kW | 76.936 | 120.213 |
| Equal jet thrust kinetic power at hypothetical 2 kg/s, kW | 38.468 | 60.106 |
| Equal jet thrust kinetic power at hypothetical 4 kg/s, kW | 19.234 | 30.053 |

The exhaust flows in the table are deliberately selected sensitivity variables,
**not C30P or VTX estimates**. The comparison shows why deliberately diverting
shaft power to a small high-speed jet can lose more fan lift than it gains.
Residual energy recovery can still be beneficial if actual exhaust state and
installation loss allow it. The table cannot decide that unknown trade.

For scale, at hypothetical exhaust flow 2 kg/s, 100/250/500 N thrust requires
2.50/15.625/62.50 kW jet kinetic power. A 0.20 m lateral lever arm makes these
20/50/100 N·m steady moments. Extra lift alone does not provide roll/pitch-rate
damping. Fixed outlet imbalance or CG offset may worsen trim. Added duct mass
subtracts its own `m_duct*g` from the lift benefit, before shaft derating.

## Recommendation for this implementation

1. Reduce the selected test fuel explicitly and derive operating mass/CG/tensor
   and a short test-duration/reserve budget using the declared SFC. Keep the
   earlier 60 kg configuration available for comparison. Tank-shell mass stays.
2. Do not add a positive exhaust-flight force from engine power or fuel flow
   alone. Keep an unknown exhaust calibration gated off in actual flight. A
   parameterized, labelled sensitivity/bench model can test the equations.
3. Before enabling a physical exhaust revision, obtain exhaust airflow and
   total pressure/temperature versus shaft load and ambient conditions, outlet
   areas, allowable backpressure and installed shaft/SFC penalty maps. Dimension
   the ducts and add their mass, inertia, colliders and mounting reactions.
4. Include duct losses, heat shielding, fuel-cell clearance, hot-gas ingestion,
   rotor inflow interference and ground impingement. Gas that strikes another
   aircraft part returns momentum to the same aircraft; gross outlet thrust
   cannot then be counted as wholly free external lift.
5. Compare power-limited trim and measured rate response after the mass change.
   Adjust the disclosed shaft governor/control behaviour if justified by tests;
   do not change gravity, rotor polars or arbitrary efficiency to force stability.

Stable flight is not established by this calculation. The previous trials
already had conditional lift but poor rate-control timing and coupled actuator
response. Lower fuel helps the force/power budget; it does not resolve those
stability issues by itself.
