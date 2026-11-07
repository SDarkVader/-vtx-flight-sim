# World graphics changes (visual only, physics untouched)

This file was meant to go to `dreamy-khayyam-7059f0/research_notes/Phantom CG compensation and test flights/graphics_changes.md`, but the worktree sandbox blocked writing outside this worktree, so it lives here. Copy it there if needed.

Worktree: `C:\Users\steve\Documents\Github\-vtx-flight-sim\.claude\worktrees\agent-ab30c2b8b057df1a2` (from research/phantom-a9-cassette @ bce9339). Nothing is committed.

## What changed
Only `public/` changed. Nothing changed under src/, tools/, scripts/, inputs/ or tests/*.py, and no JSON changed. Aircraft visuals were not touched.

- **Tiers: new `vtx-env/quality.js`**
  - Defaults: phone gets `low`, desktop `?lite` gets `lite`, desktop gets `high`.
  - `?quality=low|lite|medium|high` overrides the tier. `?tm=aces|agx|neutral` overrides tone mapping, for comparison only.
  - Tone mapping: I compared ACES, AgX and Neutral. AgX washed out the golden-hour palette, so ACES stays, at exposure 1.05.

  | | low | lite | medium | high |
  |---|---|---|---|---|
  | Antialiasing | off | on | on | on |
  | Pixel-ratio cap | 0.8 | 1.2 | 1.2 | 1.5 |
  | Shadows | none | none | 2048 view-fitted | 4096 view-fitted |
  | Far forest | 350 | 700 | 1700 | 2600 |
  | Facade/airfield ppm | 14/7 | 14/7 | 24/11 | 24/11 |
  | Local-light slots | 0 | 2 | 3 | 4 |
  | Fog | stock linear | sun-aware | sun-aware height | sun-aware height |
  | Paint drape | flat floor only | full | full | full |
  | Clouds | 16 | 26 | 26 | 40 |

- **`sky.js`**
  - New analytic sky: zenith blend, Mie glow and sun disc.
  - The fog colour uses the same haze function as the sky horizon.
  - The fog chunks are patched globally (lite and above): sun-aware aerial perspective, exponential height fog (scale 260 m), and fog that is tone-mapped and sRGB-encoded like the sky. three applies fog after tone mapping, so the old fog never matched the sky. The patch is guarded and falls back to the stock chunks.
  - The PMREM environment gets a dark ground disc.
  - The sun shadow is fitted to the view every frame: centred on the aircraft when the camera is near, otherwise on the ground ahead. Its size follows camera distance, it is texel-snapped, and normal bias scales with texel size.
  - Cloud count follows the tier; hemisphere light and sun were retuned.
- **New `vtx-env/ground.js`: exact drape**
  - Inside ±500 m it uses the physics heightfield: same samples and the same diagonal as `world.terrain_z`. Outside ±500 m it uses the distant-hills mesh triangles.
  - Paint triangles are clipped with Sutherland–Hodgman against the flat floor (|x|,|y| ≤ 220, one polygon), then each sloped terrain-cell triangle, then the hills triangles. UVs and normals are interpolated.
- **New `vtx-env/world-dressing.js`, run once after the world is built**
  - DP1: airfield paint is draped and depth-tested with polygon offset. It was z = 0.02 with depthTest off, which painted through the hills.
  - Inset light discs are put on the ground, aligned to its normal and depth-tested; on lite and above they get one additive glow `Points` draw.
  - Service-road paint and the water are draped too.
  - On `low`, paint is clipped to the flat floor, because a full drape made the phone triangle count higher. The water is draped on every tier.
  - Light LOD (new `light-pool.js`): every decorative point light (volcano, windsock lamp) is hidden and served by a fixed pool of 0/2/3/4 lights. Volcano interior lights only switch on when the camera is in the cavern, which stops the orange light leaking onto the outside grass. The hangar spot light is off on low.
  - sRGB colour space is set on canvas textures that lacked it: signs, stencils and the A/B markers.
  - Medium and high get world-space macro colour variation on the terrain. No geometry changed.
- **DP2: trees (`vegetation.js`)**
  - Three columnar species: spruce, cypress and fastigiate broadleaf.
  - Each is built in unit space (radius ≤ 0.96, z in [0, 1]) and scaled by its own collider's radius and height, so every tree lies inside its cylinder.
  - Per-instance colour variety is kept. The colliders are unchanged.
- **DP3: props**
  - Removed the weather vane on the landable dispatch roof (`buildings.js`), and the GPU cart and ladder near Stand 1 (`airfield.js`).
  - Windsock pole is upright, and the sock now streams away from the pole.
  - The follow-me cab runs on the north service road, (20,34)→(20,93)→(100,93) and back.
- **`app.js`.** Changes are confined to the scene-setup block: tier and module imports, renderer options per tier, sky, light pool and `scene.onBeforeRender`, tier options passed to the builders, and `groundZ` for the vehicles. `animate`, `loadAirframe` and the top import lines are untouched.
- **`index.html`.** Import-map cache-bust remaps for the changed modules, and the `app.js?v=` bump.

## Not done
- 2-cascade shadows (high uses a single 4096 view-fitted map instead).
- Procedural normal/roughness detail maps.
- Facade window repaint and PBR retune.
- Far-forest species variety.

## Report only: visible objects without colliders (unchanged)
- The volcano at (-30,220): radius about 88 m, height 64 m.
- The tower cab and mast.
- Hold signs at (30 ± 8.2, 16) and at the taxiway holdpoints.
- The PAPI units at x = ±416. They and the holdpoint signs at about (-450,110) and (-250,110) sit at z = 0, so they are buried under the slope. This predates my changes.
- The crossing posts and beacons.

## Physics-coincidence check
Harness: `harness/sample.mjs` plus `harness/coincidence_check.py` (against `TestWorld`). Output files are in `coincidence/`: `before_*`, `after_*_high`, `after_*_low`.

| Check | Before | After (high and low) |
|---|---|---|
| Terrain mesh vs heights and `terrain_z` (10,201 vertices, 22,000 interior samples, diagonals) | max 2.4e-6 m, 0 wrong | identical |
| Downward rays at mission points (stand-1, the (13.7,-28.4) spawn, pad-b, (-45,18), (30,20), (100,100), 7 landable roofs, apron stands, taxi/road points), 4.1 m footprint | +0.02 m paint, but the dispatch roof was **+2.04 m (vane)** | +0.02 m paint; every roof 0.00 m |
| Trees | 29 of 58 instances outside their collider (up to 2.9× the radius, +3.4 m above the top) | **0 outside**: max 0.96× radius, top excess 5e-7 m |
| Water vs ground | −5.3 to +3.6 m | +0.040 to +0.041 m |
| Airfield paint | depthTest off, up to 50 m under the slopes | draped and depth-tested; the remaining "buried" samples are the PAPI and hold-sign props above |
| Vehicles vs boxes and water (600 samples each, all five vehicles) | — | 0 conflicts |
| `validate()` verdicts | — | unchanged, since physics was not edited |

Caveat: the sampler's paint filter also picks up small props. I have not checked the service-road drape numerically; it is only visible in the screenshots.

## Performance
Sums over 10 views. Headless Edge 156, ANGLE D3D11, RTX 4070 Ti SUPER. Full tables are in `perf_tables.md` and `perf_phone.md`. Noise is about ±10–20%.

| Config | Draw calls | Triangles | Median ms |
|---|---|---|---|
| Desktop before → high | 5023 → 5004 | 4.35M → 5.07M | 68.3 → 80.6 |
| Desktop before → medium | 5023 → 4974 | 4.35M → 4.50M | 68.3 → 69.4 |
| ?lite before → lite | 5024 → 4979 | 3.72M → 3.87M | 59.4 → 70.9 |
| Phone before → low (390×844, DPR 3) | 4074 → 3889 | 3.403M → 3.419M (+0.5%) | 48.9 → 61–67 (two runs) |

On the phone, draw calls fall 5% and local lights fall from 9 to 0, but triangles rise 0.5% and the headless frame time came out higher. This is not verified on a real device. If it needs tightening: flat-clip the water on low, or revert the tree mesh on low.

## Screenshots
- Before: `before/before-{desktop,phone,lite}_<view>.jpg`
- After: `after/after-{desktop,phone,lite,low,medium}_<view>.jpg`
- Views: chase-stand1, apron-hangar, runway-grazing-east, overview-sw, pad-b, dispatch-tower, trees-south, top-stand1, stands-north, water-west.

## Tests
- Node tests: 5/5 pass.
- pytest without `VTX_DATA_ROOT`: 133 passed, 1 warning, which matches the baseline.
- `evidence/flights/.../summary.json` was not modified.
- The preview server on 8767 has been stopped.
