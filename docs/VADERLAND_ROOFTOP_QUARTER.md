# Meridian Rooftop Quarter — design note

Status: offline candidate on `claude/vaderland-rooftop-quarter-20261121`, branched from the reviewed Vaderland 32 snapshot (`77d9d45`). Nothing here has run in a live cockpit, been merged or been deployed.

## Brief

The owner's direction for Meridian: speed, fun, lighting and contrast. The city must feel alive for every kind of vehicle and must not read as grey. Influences are the playful landing targets of classic flight games, the night light of modern flight simulators, the engineer-and-fail-forward spirit of rocket sandboxes, and the neon speed of arcade racers — in Vaderland's own style, with no copied names, layouts or art.

The reference images set the palette: amber and violet light against dark structure, a pink-orange sky, V banners and chevrons, saucer-topped towers, rooftop taxi pads with yellow rings and edge lights, wet reflective decks and drones with light cones.

## What made the city grey (measured in v32)

- The north-west and north-east wards have about 5% building footprint coverage (148 and 106 solids over 6 m in about 5 km² each). Dense real districts are 25–50%.
- Under the market district the terrain shader painted one light stone tint over a 2.1 km square. In the wards a flat pale paving tint did the same.
- Distant facades fade their window grid to a dim body tone close to the ground value. Haze then pulls both towards one colour and silhouettes dissolve.
- Nothing outlined the city at blue hour: no street lighting grid, traffic, roof edges or beacons.

## Step 1 — city life (render-only, this branch)

`public/vtx-env/vaderland/city-life.js` adds, from the surveyed road polylines and building boxes:

- street lamps every 30–38 m with small light pools (sodium side streets, white avenues);
- traffic light streams on every city road segment (white towards the viewer, red away);
- amber, violet, magenta and cyan roof-edge lines on about half of the buildings, so blocks read as shapes from the air;
- slow red obstruction beacons on towers over 45 m;
- Vader's Taxis air lanes: warm body lights with red and green navigation lights on six elliptical lanes over the city.

The terrain shader now draws lots as pocket parks, warm plazas and dark service courts instead of one stone or paving tint.

None of this is a collider or part of the world data, so the world fingerprint, aircraft and physics are unchanged. It is all deterministic in the presentation clock and costs five extra draw calls.

## Step 2 — Rooftop Quarter (physical, proposed as Vaderland 33)

- Mid-rise infill and perimeter blocks in the north-west wards, the stretch the A10-D crossed on its approach.
- Saucer-topped taxi-rank towers and a Vader's Taxis dispatch tower as the district landmark.
- The **Taxi Rooftop Ladder**: six physically landable pads, graded from large and low to small and high, with edge lights and wet-look decks. It trains the open acceptance items, sustained hover and controlled landing. Fares (pick up at one pad, deliver to another against the clock) can follow for manual and AI pilots.
- Only building masses and pads get colliders. Small detail stays render-only so the physics checkpoint does not grow.

Each physical change needs the established checks: support and intrusion survey, clear High Line and Parallax envelopes, unchanged routes, native ray agreement, and a world fingerprint computed on the owner's PC (this Linux environment computes `525b017f…` for the v32 tree against the recorded `067e9b18…`, so physical fingerprints must come from the reference machine).
