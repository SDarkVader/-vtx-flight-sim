# Vaderland 32

Vaderland links airport arrivals, mountain roads, urban air trials and coastal boat racing in one world. The routes let the existing vehicles explore, race and test their limits. Aircraft and boats use their ordinary controls and recorded physics.

## Development

| Work | Current state |
| --- | --- |
| Roads and terrain | The surveyed airport, linked mountain and tunnel routes, Meridian Handling Yard and Cathedral proving circuits share collision geometry with the rendered world. |
| Road and air challenges | Cathedral has a speed circuit, quarry route and vertical loops. Meridian has the High Line and Parallax air trials. Stock Phantom runs completed the Meridian trials. The two recorded A10-C Grand Loop attempts ended in DNFs. |
| City and replay | Meridian gained a lit streetscape and Crest Gardens. The v30 animation uses archived sorties and native-physics runs, including the takeoffs, hangar strike, spin and fall, and Grand Loop attempts. The animation and editing clips are separate media deliverables. |
| Airport to marina | Vaderland 32 adds the 1.28 km Lantern Shore Link from Meridian Arrivals to the existing Lantern Marina. The 14 m road has a signed fork, drop-off bays and a turnaround. A stairway and gangway connect it to the berths and the eight-gate Islet Trial. |

## Recorded checks

- The pinned Phantom A10-D completed the offline outbound drive and turnaround in 121.5 seconds and the return in 94.2 seconds. Both runs used ordinary road inputs and recorded zero collisions. The link's steepest surveyed grade was 8.57%.
- A stock Ricochet completed the Islet Trial in 167.361 seconds with zero fouls. Mid-lap checkpoint restore reproduced the boat state.
- The shore work matched 46,366 existing road-height probes and 14,065 wet height probes exactly. Native rays checked 81 stair, landing and gangway surfaces. Eight offline WebGL views rendered on the target GPU.
- The owner's packaged Windows build loaded Vaderland 32 and verified the A10-D aircraft and visual pins while parked at Lantern Marina. The air-brake result in the handover comes from a separate v31 offline test.

## Manual A10-D flight on 20 November 2026

Run `20261120T192930-9fad97` verifies the v32 runway departure, airborne traversal towards Meridian and physical terrain contact on the west side of the city. The pilot lifted vertically from Runway 08 and reached 1,698 m above the world datum. On the northwest approach to the Crest, the aircraft slowed to 4.6 m/s across the ground while still climbing at 3.1 m/s. The pitch excursion began while the attitude demand was steady at 0.8° nose-up. The pitch reached 37.6° as the climb began to reverse, and later corrections repeatedly reached the control limits. The right canard struck terrain at 370.13 s. The retained package includes the original flight, audit, control and impact records.

The flown build's desktop view was limited to one WebGL draw per 50 ms. A manual sample at the 1× setting advanced at about 0.66×, with solver backlog increasing independently of the display. Keep both measurements with the flight result.

## Frame pacing follow-up

The renderer now targets 60 FPS on desktop and 15 FPS in the lightweight view. The live view displays rendered FPS separately from telemetry age. The frame clock does not change the telemetry cadence or the recorded pose used to draw the aircraft.

In an offline WebGL comparison using the flight's recorded telemetry and the same High settings on the local RTX 4070 Ti SUPER, the runway chase, Meridian approach and Crest approach rose from 18.3–18.5 to about 60 FPS. Each view was sampled for five seconds. The 95th-percentile draw intervals in the candidate were 18.5–18.7 ms. Native 1× solver throughput and a full manual flight with the new renderer remain open.

## Manual review

1. Drive from **Meridian Arrivals · Shore Link**. Check the signed fork, hill, drop-off bays and marina turnaround.
2. Select the pinned **Phantom A10-D** and repeat the west-runway flight. Check the transition air-brake response during approach and retain the flight record. The recorded 20 November flight used attitude mode with the air brake off.
3. At Lantern Marina, select the stock Ricochet. Run the Islet Trial and check the return to berth.
4. Review low-angle water shimmer, pier finishes and nearby tree silhouettes. Keep the recorded failures alongside successful runs as the world develops.

This branch captures the reviewed build at `44fef8cc49aec71d89c03c09976209c8ce8cb1fc`. The displayed world fingerprint is `067e9b189f8a4b0e2c3808d2e1be6af0c6f026018fb70e0d08fbd20d29809ec1`.
