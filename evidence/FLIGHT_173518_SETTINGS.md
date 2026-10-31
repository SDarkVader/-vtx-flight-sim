# Mobile run 20261031T173518-46b6e2: settings and response

Times are simulated seconds from the start of the run. Commands and subsequent observations are distinct: blade pitch and nacelle servos have lag. These observations are from one provisional simulation and do not establish repeatable or real-aircraft safe settings.

| Time (s) | Setting / request | Observed response |
| --- | --- | --- |
| 13.32–15.68 | One-degree individual nacelle axis tests, then distinct individual collective requests of 0.5 / 1 / 1.5 / 2° | Both axes on all four nacelles responded; collective feedback was 0.50 / 0.99 / 1.49 / 1.97°. Aircraft remained supported. These were small checks, not full-range tests. |
| 21.70 | Engine reference 100%, all collective approximately 15°, nacelles centered | Roll approximately −0.10° and gear still supporting the aircraft. Stable on the ground, not an airborne hover. |
| 24.49 request, 25.25 observation | F1–F4 collective 16.5 / 16.7 / 16.5 / 16.3°, centered nacelles | Roll improved from approximately −0.18° to −0.09° and measured roll rate became positive, while at least part of the gear was still loaded. This is a promising ground trim point, not proof it will stabilize liftoff. |
| 25.60–27.35 | Collective 17° evenly, then 17 / 18 / 17 / 16° as an opposing roll correction | Roll worsened to approximately −7.4° despite the correction, with very low clearance. This was not a successful liftoff setting. |
| 27.81–30.80 | Reduce collective, then request 14 / 13.8 / 14 / 14.2° and 1.5° X tilt on each nacelle | During the recovery, measured horizontal Y velocity fell from around +1.94 to −0.02 m/s and roll improved from −9° to about −0.7° by 29.65 s; gear contact and other changing forces also contributed, so this is not an isolated actuator-effectiveness measurement. |
| 36.83–37.72 | 16.5 / 16.7 / 16.5 / 16.3°, followed by 17 / 17.2 / 17 / 16.8° | The craft stayed close to level while partially supported, approximately −0.10° to −0.16° roll. |
| 38.13–40.29 | Raise mean to 17.5° with small trim, reverse differential at 39.11, request +8° X fan tilt at 40.12 | Roll grew from −1.5° at 38.67 to −13.3° at 39.67; an impact was recorded by approximately 40.29 s. Neither correction stopped the roll. Requested tilt was rate limited and had not reached 8° at impact. |

The simulator's shadow assistance was off during this run and never controlled the aircraft. The controller candidate remains shadow-only; changing its percentage records suggestions, not flight corrections. The model ties the four rotor speeds together, even though collective and cowling targets are separate.

The recorded rotor forces around 38.67 s were approximately 2,469 / 2,522 / 2,469 / 2,416 N for F1–F4. At 39.67 s they were 2,458 / 2,246 / 2,458 / 2,658 N. Thus the recorded data does not establish the earlier suggestion that an 18° command simply reduced thrust through blade stall. Contact, gyroscopic and nacelle dynamics, inflow and actuator delays need to be separated in controlled comparisons.
