# Trial: Phantom A10-B merged into the unified dashboard-cockpit candidate (9 November 2026)

This is a trial integration, kept for reference. It is not a promotion and not a proposal to merge.

| | Commit |
|---|---|
| Base | `work/dashboard-cockpit-20261107` at `883fc43` (the unified environment: airport, cockpit, flight-test dashboard) |
| Merged in | PR #25 head `27c89ae` (Phantom A10-B). The later #25 commit, `d6ba8f9`, changed only the main README and is not in this trial. |
| Result | the merge commit on this branch |

## How the conflicts were resolved

The merge conflicted in 11 files and 54 hunks. Merging `main` alone into the same base conflicts in 9 of those files (45 hunks). #25 added `tests/test_operator_controls.mjs`, `tests/test_phantom_a10.py` and more hunks in `src/vtx/phantom/plant.py`.

- **`src/vtx/phantom/plant.py`**: both sides were kept.
  - From the candidate:
    - the FCC uses the CG from the measured joint positions;
    - the road start sets the canard fold;
    - `fan_thrust_max_n` is in the snapshot.
  - From A10-B:
    - the effectors, air data (`qdyn`, `beta`) and suspension;
    - the steering joints and the effector snapshot fields.
  - Render asset:
    - `phantom-a10b-visual.glb` for `phantom-a10b`;
    - the Blendstra `phantom-a10-blendstra-81c823e2.glb` for the other A10 variants;
    - the cassette GLB otherwise.
  - The exact text used is in `resolution/p2.txt`, `p3.txt`, `p4.txt` and `p8.txt`.
- **`src/vtx/live_server.py`**: the candidate's side, plus `phantom-a10b` in `supported_variants`.
- **Interface files** (`README.md`, `public/app.js`, `public/index.html`, `public/model-selector.js`, `public/phantom-controls.js`, `public/vtx-env/phantom-look.js`): the candidate's side, then the A10-B additions applied by hand:
  - `index.html`: the airframe list gets `phantom-a10b` (selected), and `phantom-fx` is relabelled "A10-A · previous prototype";
  - `phantom-look.js`: the front pods steer from `pod_F*_steer`. The lookup is guarded with `q?.[...]` because the candidate's `updatePhantom` can run while parked with no joints;
  - `app.js`: the `phantom-look.js` cache key is bumped.
- **`public/assets/phantom-a10-visual.glb`**: the candidate's version.
- **Tests:**
  - `test_operator_controls.mjs`: the candidate's version, which carries its new heartbeat semantics;
  - `test_phantom_a10.py`: the A10-B assertions.
- `resolution/resolve.py` is the helper that applied a choice to each conflict hunk in turn.

## Two integration fixes in this trial (not on `main`)

1. **`src/vtx/phantom/live.py`**: `make_aircraft` forces P6 on only when the variant's own P6 is off. Without this, A10-B gets config `71bb4a67` instead of its canonical `3ecae1a9`, with identical physics. Checked: A10-B becomes `3ecae1a9` again and A10-A stays `70089cca`.
2. **`src/vtx/dashboard_site.py`**: the dashboard's start-up preview uses `DEFAULT_VARIANT` (A10-B) instead of `phantom-fx`.

## Test status when stopped

- Candidate CI step 1, `node tests/visual-air-traffic.test.mjs`: **passed**.
- JS tests: **all 17 files pass**. `far-forest-boundary.test.mjs` needs `--loader ./tests/vendor-three-loader.mjs`, as it does on the candidate alone.
- pytest: **incomplete**. The runs were stopped on request, so the names of the failures were not captured.
  - The trial run reached about 87% (`logs/pytest_trial_partial.log`).
  - The candidate alone, with no A10-B, timed out at about 70% (`logs/pytest_dashboard_cockpit_alone_partial.log`).
  - Both runs show the same failure pattern at the same points in the suite. That suggests the failures already exist on the candidate, but it is not confirmed.
- The candidate alone cannot collect `tests/test_a10_cg_placement.py`: it imports `tools/phantom/a10_cg_placement.py`, which is not on that branch. `main` has the file, so this trial does too.

## Observed on the candidate, independent of A10-B

- `public/model-selector.js` has mis-encoded characters (`Â·`, `â€¦`). The title split on ` · ` fails, so the start button reads "New Phantom FX-A A10 · CURRENT PROTOTYPE (opt-in, SYNTHETIC) mission".
- The config ID covers only the parameter tree. Two things changed since the A10-A register without changing it:
  - the FCC now uses the measured-joint CG;
  - the world is now `stage1-extended-airfield-recovery` v4 (previously `stage1-valley` v2).

  Runs on the same config ID from before and after these changes are not strictly comparable. This matters for dashboard gate 01 (evidence integrity audit).
