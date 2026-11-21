# Vaderland 33 — Meridian Rooftop Quarter (offline candidate)

Status: offline candidate on `claude/vaderland-rooftop-quarter-20261121`, branched from the reviewed Vaderland 32 snapshot (`77d9d45`). Nothing here has run in a live cockpit or live harbour, been merged or been deployed. Vaderland 32 is unchanged and remains selectable.

## Direction

Vaderland is an experimental vehicle playground organised around events, progression, racing, AI-only races and building. **The zones are the environment, and vehicles arise from its challenges**: a course states what it demands (footprint, hover precision, jump size, corner radius), and vehicles are designed to meet it. Nothing is sized for one aircraft; the Phantom A10-D is one test pilot among future cars, bikes, booster vehicles and boats.

Influences: classic landing-target flight games, modern flight-simulator night light, rocket-sandbox engineering where failure is part of play, and neon arcade racing — in Vaderland's own style, with no copied names, layouts or art. The owner's reference images set the palette: amber and violet light against dark structure, a pink-orange sky, V banners and chevrons, saucer-topped towers, rooftop pads with ringed lights.

## What made Meridian grey (measured in v32)

- North-west and north-east wards: about 5% building footprint (148 and 106 solids over 6 m in about 5 km² each).
- The terrain shader painted one pale stone tint over the 2.1 km market square and a flat paving tint over the wards.
- Distant facades fade their window grid to a dim body tone close to the ground value, and haze pulls both together.
- No lighting grid, traffic, roof edges or beacons outlined the city at blue hour.

## 1. City light (render-only)

`public/vtx-env/vaderland/city-life.js` and `city-density.js`. Light follows where people are: a floor-area density of the surveyed architecture (footprint × storeys per 100 m cell, blurred over about 200 m; core ≈ 4.8, wards ≈ 0.2–0.3, airport terminal ≈ 1.2) sets lamp spacing and brightness, light pools and traffic volume. The core and its avenues are bright, the wards are dim, and open land stays dark. Colour is restrained: sodium amber, cool white on the core avenues, slow red obstruction beacons on towers of 60 m and more, and a few quiet air-taxi lanes over the core. The terrain shader draws urban ground as soft, low-contrast patches instead of one pale tint.

An earlier pass outlined about half of all roofs in coloured light and lit every street evenly; the owner found it too uniform, too square and too much like a nightclub, so both were removed.

## 2. Rooftop landing zones, missions and ward tracks (Vaderland 33)

Generator: `tools/vaderland/rooftop_quarter.py` → `inputs/vaderland/rooftop-quarter-33.json.gz`. District: `src/vtx/rooftop_quarter.py`. Client: `public/vtx-env/vaderland/neighbourhood.js`.

- **Rooftop landing zones**: 32 zones painted on existing Meridian roofs from about 15 m to 160 m, in four size classes stated as demands (S ≤ 8 m footprint, M ≤ 14 m, L ≤ 22 m, XL ≤ 34 m). Every zone passes the existing landing-support check (six-foot support, ≥ 4.5 m roof margin, clear vertical column). Markings are quiet (white and amber with small perimeter lights); a faint beacon shows only on the zone an active mission is heading to.
- **Missions**: 8 rooftop runs. Fly the hoops, brake into a hover and hold 3 s on the zone, hover down to the runway touchdown box and hold 2 s, then take off through the exit hoop. Contact anywhere else ends the attempt. Results keep splits, last, best and both landing errors, and checkpoint with the flight.
- **Ward Loops**: 14 mini tracks with kerbs, a tabletop and a kicker-and-landing in three sizes, timed as ground circuits. The 42 ramps are the only new solids.

**No buildings are added.** A box-house infill (terraces, cubes, round houses, low-poly trees, lanes and gardens; 6,501 solids) was built and rejected by the owner: it read as blocks and departed from the baseline Meridian architecture. It remains in the branch history (`0659dfc`) only. Any future infill must reuse the baseline building system (the ward, courtyard and market generators and the avenue facade material), not a new style.

### Measured cost of solid geometry

Offline on the review container, 8,000 extra static boxes raised `mj_step` from 0.317 ms to 0.441 ms and the plant checkpoint from 3.17 MB to 3.69 MB. Static geometry is carried in every checkpoint (`geom_xpos`/`geom_xmat`), so excluding constant world geoms from checkpoints would recover this and more; that is a separate change.

### Checks

`tests/test_rooftop_quarter.py`: the v32 world is a prefix of v33 and only ramps are added, ramps are closed convex hulls that do not intersect existing scenery, every zone validates as a landing surface, hoops are in clear air, a flown synthetic mission completes with two scored touchdowns, an off-zone touchdown ends the attempt, and the mission record survives checkpointing. Offline A10-D starts on S and XL roofs settled with zero speed.

The world fingerprint must be computed on the reference PC; this Linux environment already differs from the recorded v32 value (`525b017f…` against `067e9b18…`), and the existing v05/v08 fingerprint pins fail here on the unmodified tree for the same reason.

## 3. Atmosphere (render-only)

`public/vtx-env/vaderland/atmosphere.js`: a charcoal haze dome over Meridian lit from below by the same density field, so the core glows warm through the murk while the outskirts sink into ground fog; layered fog banks that are heavier over dark land and clear around the viewer; sparse motes that only show where there is light; wandering rain cells; rare distant flashes. Daylight haze is kept thin so the city does not turn grey.

## 4. The Lantern Race (Vaderland 33)

Generator: `tools/vaderland/lantern_race.py` (called by the rooftop generator). Physics: `src/vtx/water/rapids.py`, hooked into `HybridWaterField.evaluate`. Fleet: `src/vtx/harbour_trial.py`, `src/vtx/course_timing.py`, `src/vtx/harbour_session.py`. Client: `public/vtx-env/vaderland/lantern-race.js`, `lantern-marks.js`, the boat panel and the harbour map.

A tidal race through the natural narrows between Heron Island and Needle Island in Lantern Sound (about 96 m wide at the throat, 3.5–6 m deep). Nothing is built in the water except rocks, marks and three anchored ramps; the terrain is unchanged.

**Water physics.** The rapid is an analytical overlay on the existing hybrid water field, like the whirlpools, so every hull feels it through its ordinary hydrodynamics (relative flow, dynamic pressure, surface slope, vertical flow):

- a current jet along the surveyed centreline, about 4.1 m/s (8 kn) in the throat, 1.3 m/s at the start and slack at the finish, strongest mid-channel ((1 − q²)^0.7 across the half width);
- counter-current eddy lines along both banks (up to about 28% of the local current, reversed);
- a standing-wave train. A surface wave stands still in a current when its phase speed equals the current, which in deep water gives k = g/u² (λ ≈ 10 m at 4 m/s). The phase is integrated along the reach as the current changes, and elevation, slope, vertical flow and vertical acceleration are consistent (tested against a numerical derivative);
- rocks: a stagnation pillow of about 0.8·u²/2g upstream, flow parting around the rock and a slack, recirculating wake behind it;
- boils drifting downstream at about 0.8 u.

It is zero beyond the bank margin and tapers over 40 m beyond each end of the reach. `rapids_enabled` and `rapids_intensity` in the water configuration switch or scale it. Worlds without rapids are unchanged (Vaderland 32's harbour chart is identical).

**Courses.** Three lines share a start gate in slack water and a finish in the run-out pool, each marked by lantern piles in its own colour (amber Main Chute, violet Rock Garden, cyan Eddy Line):

| Line | Character | Gates |
|---|---|---|
| Main Chute | the fast water and the wave train, then the chute kicker before the finish | 18–26 m |
| Rock Garden | a slalom between boulders on the east side; two rocks just awash show only as boils | 12–14 m |
| Eddy Line | along the Heron bank through the eddies, finishing past the deep-water outlier ramp | 12–16 m |

Each line keeps its own water: no pile of one line stands within 6 m of another line's path. An offline run that steered a Ricochet down the Main Chute at full throttle found the first layout wrong — the hull's port wing clipped an Eddy Line pile 4 m off the chute line in the wave train — so the lines were separated and the check is now a test.

Lines are timed point to point on the fleet clock (`sprint` courses in `CourseTiming`). Crossing the start runs all three; the first line gate taken commits the boat to that line. Marker contact or an impact voids the run. Results, splits and fouls are checkpointed with the fleet (`lantern_races`, written only when a harbour has races). The boat panel stages the selected boat above the start for a chosen line.

**Ramps.** Three anchored floating ramps, sized from the Ricochet itself and tried offline with its full plant in the v33 fleet (900 kg; a 1.6 m centre hull that runs 0.61–0.71 m deep at 0–9 m/s; outrigger sponsons and struts to ±4.24 m; 9.8 m wing span):

- each deck starts at a sharp edge 1.05 m under water, below the running hull, so a hull meets the slope instead of a leading face;
- the decks are wet and waxed (friction 0.10, which governs the contact against any hull) and have some give (contact time constant 0.06 s). As a rigid wall the kicker struck the hull with 144 kN, about 16 g, and the fleet's impact rule called it a crash;
- the two ramps on the Ricochet's lines are 12 m wide, so the hull and both sponsons ride the deck. On a 7 m deck one sponson hung over the edge and the craft rolled over on the climb.

| Ramp | Size | Offline result with the Ricochet |
|---|---|---|
| Chute kicker (Main Chute) | 18 m, 1.35 m lip, 12 m wide | 42 kN peak; launches about 1.4 m above the water, lands about 10 m on, level again within 15 m |
| Deep-water outlier (Eddy Line) | 20 m, 2.2 m lip, 12 m wide | 49 kN peak; about 2.3 m above the water into 6 m of water; needs near top speed; lands with up to 35° of roll and pitch and recovers |
| Small-craft hop (Rock Garden) | 12 m, 0.8 m lip, 4.5 m wide | for narrower future hulls; a Ricochet steers round it |

A slipway at Needle Island's north tip takes amphibious vehicles between the island trail and the pool.

**Needle Island.** A 7 m gravel trail loop inset from the shore with a tabletop, for future wheeled vehicles; a basalt shelf above the throat that is also the landing zone of the **Low Line** air mission (five low hoops down the race past the Lantern Rock beacon, a held touchdown on the shelf, exit over the island).

**Scenery.** About 560 conifers on both islands (physical trunks, like the existing forests), the Lantern Rock with a breathing beacon, small hexagonal lanterns along both banks and the trail with light pools, and wet shingle and weed at the waterline instead of grass to the edge.

**Water surface.** Whitewater, spray and the surface relief come from the same rapid field the physics uses, sampled into a 1.25 m texture: foam carried by the current and stretched along it, foam collars and wakes at rocks, boils over the two rocks just awash, small cross-flow ripples (smooth directional wave trains, faded with distance so they never alias into contour lines), a lapping wash in the shallows, and warm lantern light on the water at night. Broken water scatters the reflected sky, so the wave train does not mirror the city-lit clouds at night. Near a boat the live harbour surface already displaces the mesh with the solver's own free surface, rapids included; elsewhere the standing waves are drawn by shading.

**Rocks.** Each rock is drawn as a sphere shrink-wrapped onto its collision hull (never outside it), with fractured relief, cavities, cracks, lichen on dry tops, and a dark glossy wet line that rises and falls with the water.

### Checks

`tests/test_lantern_race.py`: jet, eddies and compact support of the rapid; stationary standing waves with λ = 2πu²/g and a consistent slope; rock pillow, parting flow and wake; sprint timing; line commitment, finish and checkpoint round trip; race staging; the rapid current in the fleet's water field and switched off by configuration; the ramp friction and priority in the fleet's MuJoCo model; the v32 harbour unchanged; race solids limited to rocks, ramps, marks, trees, the shelf and poles; rocks seated on the bed; every line in open, deep water between its gates; trail on land and clear of trees; the slipway reaching from land into the pool; the shelf validating as a landing surface.

## Next

- A high-speed mountain circuit through valleys, cuttings and tunnels with tight street sections and real elevation change, widths and radii set for agile cars, bikes and booster vehicles (the A10-D is about the length of an open-wheel race car).
- Weather that affects physics (wind, rain grip) only with the owner's approval.
