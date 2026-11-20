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

## Manual review

1. Drive from **Meridian Arrivals · Shore Link**. Check the signed fork, hill, drop-off bays and marina turnaround.
2. Select the pinned **Phantom A10-D** and start the first manual flight at the west runway. Check the transition air-brake response during approach and retain the flight record.
3. At Lantern Marina, select the stock Ricochet. Run the Islet Trial and check the return to berth.
4. Review low-angle water shimmer, pier finishes and nearby tree silhouettes. Keep the recorded failures alongside successful runs as the world develops.

This branch captures the reviewed build at `44fef8cc49aec71d89c03c09976209c8ce8cb1fc`. The displayed world fingerprint is `067e9b189f8a4b0e2c3808d2e1be6af0c6f026018fb70e0d08fbd20d29809ec1`.
