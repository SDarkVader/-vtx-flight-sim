# VTX airport flight school: verified source data and fictional design proposal

**Date**: 1 November 2026. **Purpose**: input to Gemini/Blender/flight simulation; *not* a chart for real-world flight.

## Reference airport

**Gloucestershire Airport, EGBJ**, is the strongest structural reference for the academy: two intersecting asphalt runways, curved connecting taxiways, hangars, maintenance stands, tower and flight training facilities. **Perth/Scone, EGPT**, is a good Scottish general-aviation secondary reference with three surfaces.

| Airport | Runway | Length | Width | Note |
|---|---|---:|---:|---|
| EGBJ | 08/26 | 1,432 m published | 30 m | active; real magnetic heading is not exactly 90 degrees |
| EGBJ | 03/21 | 980 m published | 23 m | active |
| EGBJ | 18/36 | 800 m old surface | 18 m | CLOSED in OurAirports; do not paint active markings |
| EGPT | 03/21 | 853 m | ~27 m (OurAirports) | asphalt |
| EGPT | 09/27 | 609 m | ~22 m (OurAirports) | asphalt |
| EGPT | 15/33 | 622 m | ~36 m (OurAirports) | grass |

**Important amendment:** In August 2026 EGBJ's runways were redesignated from 09/27 and 04/22 to 08/26 and 03/21. Many web photos and charts remain older. Verify current NATS AIP publication; local fiction need not use actual EGBJ runway names but must be internally consistent.

## Data files

- `real_airport_reference.json`: source-linked real locations, physical runway dimensions, true bearings and threshold coordinates where available.
- `EGBJ_runway_centerlines_WGS84.geojson`: real runway endpoint lines, including the retired 18/36 runway flagged `closed=true`.
- `VTX_fictional_airport_layout_proposal.json`: fictional local-metre layout with curved Bézier taxiway design candidates, apron, school, stand, roads and training scenario metadata. **Not real airport geospatial data.**

## Implementation contract

1. Drive navigation and minimap from a shared authoritative geometry graph. Do **not** treat a decorative texture or minimap image as a taxi route.
2. Generate pavement meshes and map lanes from sampled centreline curves, consistent widths and banks; ensure individual links have tangent/curvature continuity and physically feasible turn radii.
3. Validate max swept geometry including nacelles, rotor discs, gear and cabin through taxi turns. Test at actual steering/actuator limits. Initial example width 14 m and 25 m curve radius are proposal parameters **not real-world standards**.
4. No new airport building, vehicle, tree or security fence may physically intersect taxi, runway, hover or flight paths unless collision constraints model it. Ground-vehicle paths and aircraft taxi paths are distinct graphs with controlled crossings.
5. Maintain independent backend MuJoCo collider data for newly reachable solids. VTX existing `world.py` heightfield alone cannot make a hollow fly-through volcano: physical mesh and open passage clearance are required.
6. Keep physical aircraft geometry, transforms, centre of mass/inertia and control surfaces unchanged.
7. Fly training levels with measured data and deterministic replay; do not fake an aircraft's flight or taxi by animating a visual prop.
8. Minimap aircraft icon must use actual physical poses and yaw, not a fixed sprite; record and test map coordinate frame.
9. Distinguish verified public source dimensions, authored artistic plans, and unverified collision/operability claims in every report.

## Licence and primary source links

- OurAirports downloads — public domain, source CSV updated 31 Oct 2026: https://ourairports.com/data/
- EGBJ published UK AIP chart page: https://www.gloucestershireairport.co.uk/flying/information-for-pilots/uk-aip-aerodrome-chart
- Current UK NATS AIP: https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP
- Perth Airport official technical data: https://www.perthairport.co.uk/pilot-information/technical-data
- FAA airport design geometric references: https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.current/documentnumber/150_5300-13
- OSM licence (no OSM data included here): https://www.openstreetmap.org/copyright

## Visual art direction

Airside needs multiple properly sized hangars, academy buildings, tower, maintenance, rescue/fire, service roads, static and moving ground vehicles, stands, gates, curved taxiway junctions and holding lines. Surrounding this functional inner airport is the fantastical Vader's Nightmare world with a **hollow, flyable** volcano basement. These outer elements need physically validated limits if inside the flyable domain. Keep the airport readable and navigable before adding spectacle.
