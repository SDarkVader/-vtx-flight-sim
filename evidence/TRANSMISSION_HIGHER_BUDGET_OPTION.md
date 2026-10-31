# Independent fan drives: higher component budget and ratio alternative

The user permits increased budget for specific components during early development. Treat component cost and the existing P03 mass allocation as adjustable design inputs, not evidence of available aircraft payload or installed power. No purchase or flight qualification is implied.

## Alternative ratio screen

Keep the hypothetical 20:60 planetary, fan on carrier, and sun driven from a common 6,016 rpm engine shaft. Instead of the previous 4:1 reduction, choose an ideal fixed reduction of 6,016/4,800 = 1.2533:1 so sun speed is 4,800 rpm at the chosen nominal engine condition. Willis' relation gives ring rpm = (4 × carrier rpm − 4,800)/3. This puts the ring at zero speed at 1,200 rpm nominal, while requiring approximately the same ring reaction torque. Assume the same illustrative fixed carrier torque of 566.99 N m and an ideal 3:1 motor-to-ring speed reduction, with 95% motoring efficiency for the torque estimate:

| Fan rpm | Ring rpm | Ideal signed ring power per fan | Motor rpm | Sun mesh frequency |
| ---: | ---: | ---: | ---: | ---: |
| 1,100 | −133.33 | −5.94 kW | −400 | 1,233.33 Hz |
| 1,200 | 0 | 0 kW | 0 | 1,200 Hz |
| 1,300 | +133.33 | +5.94 kW | +400 | 1,166.67 Hz |

At nominal, ideal sun input is 71.25 kW per branch, with ring reaction torque magnitude 425.24 N m. Approximately 149.2 N m motor torque is required in the assumed motoring case, though zero-speed and regenerating torque and losses depend on the actual gear and inverter. With four fans all at the same endpoint and torque, total signed ideal ring power magnitude is about 23.75 kW, before loss and transients. Opposite branch commands may exchange power through the bus; net supply, battery buffering and dissipative braking need explicit design.

This is a **kinematic thought experiment**, not a selected or proven gearbox. The engine speed, total torque and power budgets, rotor aerodynamic loads, and gearing efficiencies vary in operation. Near zero motor rpm, power at the shaft is zero while electrical current, heating and holding torque remain; the motor and controller need continuous zero-speed thermal ratings, not just a generic peak or maximum continuous torque. The 3:1 stage must tolerate continuous reaction torque, reversals, backlash, failure and torsional loads. A separate mechanical brake or lock cannot be assumed to provide continuous safe operation or a smooth transfer. The changed ratio substantially shifts mesh excitation and demands new coupled modal, bearing, and gear fatigue checks. Verify packaging, common-shaft load split, gearing direction for counter-rotating fans, failure isolation, overspeed protection and gimbal articulation.

The [EMRAX 268](https://emrax.com/e-motors/emrax-268/) remains a **supplier investigation candidate**: published figures include up to 226 N m continuous and 22.3 kg for the liquid-cooled unit, subject to drive cycle, thermal conditions and controller. The actual continuous torque near zero speed, bidirectional operation, cooling, vibration and aircraft duty require supplier confirmation. Four dry motors weigh 89.2 kg; gearbox stages, shafts, electronics, mounts and coolant add weight. A 348 direct-drive option remains below the illustrative 425 N m ring torque on its current published maximum continuous figure. Do not equate extra financial budget with extra lift, torque capacity or thermal capacity.
