# VTX integration ownership and evidence register

Snapshot: 2026-11-09. This is an audit ledger, not permission to delete branches or close pull requests. “In history” means commit ancestry only; it does not prove every file survives the integration. “Review unique” means the branch has commits outside the integration history and must be assessed before any closure.

## Aircraft and runtime ownership

- A10-B: PR #25 head `d6ba8f96405efd8c3979c6da9366b079d7633f74`; merged on GitHub as `3f88020c86f6b6bcb19e3b5bc8bac24ce20a52f2`. Preserve the B-specific GLB, effectors, suspension and overlay values. The trial merge at `1e922139c85f001616752b19dc1b033cae431052` is reference evidence; its notes and conflict resolutions are retained in `trial_a10b_20261109/`.
- A10-A: `phantom-fx` P6-on configuration `70089ccace22e4ce1cfd28104654257fe4d03771c4f6b1faa3c89fce253247dd`; P6-off `b835295b7b806fcb785f01a8776b6715d73790f48ac5134cb8d594e6d389ebde`. Both must remain reproducible. The 72-run register and later B data are retained under `reference/phantom_a10b_20261109/`.
- R6: canonical checkpoint `75aec5e1d6ab54d25bf366a3d1a88ce390e1003a`; revision `P0-V4A-assembly-r6`, physics `audit-fixes-20261103-r3`, visual `/assets/airframe-r6.glb`. The separate Blendstra rig remains as an additional asset and is not the canonical release target.
- Shared runtime: Python/MuJoCo `src/vtx/live_server.py`, Phantom implementation in `src/vtx/phantom/`, and one cockpit selector. The experiment service instantiates separate laboratory state and evidence paths; verify isolation and runtime tests before promotion.
- Identity caveat: the parameter hash does not encode source code or world revisions. New records additionally capture a Python-tree source hash and world metadata. Historical records retain their original meanings.
- Trial asset comparison: A10-B `phantom-a10b-visual.glb` has Git blob `3addb40a5fe7938e5a0509e06b4b61f4c03cec88` in both the trial and this integration; the A10-A Blendstra asset has blob `7da234c57c944fdbcb5d4ef2ec3267456a72aae9` in both. The trial's alternate `phantom-a10-visual.glb` is blob `ec17397a8db31b9376c66864784ec3b1a8c97f1b`, preserved on the trial ref; the integration's separate asset is `78dcd78264662e6e403bde7086a8fc9c76f45d5b`. R6 canonical asset is blob `9f9ece3ddc6755e0695f7cf03f55924906d65f38` in both this integration and the canonical R6 branch.

## Pull request disposition

| PR | Head | Provisional disposition |
|---|---|---|
| #25 | `d6ba8f9` | Already merged externally as `3f88020`; A10-B code is also integrated here. Reconcile current main ancestry before a PR. |
| #30 | `2cbe722` | Preserve visual-preview work; inspect its unique patch and tests against the integrated candidate before deciding. |
| #31 | `a1ce86f` | Preserve Vercel storage findings; documentation-only, review separately. |
| #32 | `54aad77` | Preserve objective and waypoint assessment contract; review alongside #33 and runtime evidence. |
| #33 | `db41288` | Preserve landing-assessment policy and tests; do not close based on similar behavior alone. |
| #34 | `0228a66` | Recovery reference; assess its two changed files and end-to-end acceptance before any disposition. |
| #35 | `5f58eb7` | Preserve separate Vaderland work; outside core physics integration until its unique changes are reviewed. |
| #36 | `143e153` | Preserve earlier Phantom documentation and flight history; compare its three changed files and target branch before closure. |

## Remote branches

| Branch | Tip | Commits outside integration history | Initial disposition |
|---|---|---:|---|
| `checkpoint/phantom-a10-live-20261106` | `9ff488dc0e3f6d8590dde4a1b4a2958b36bb51d1` | 0 | In history; verify current files before any closure |
| `claude/model-visual-improvement-h9j7ev` | `d6ba8f96405efd8c3979c6da9366b079d7633f74` | 0 | In history; verify current files before any closure |
| `claude/phantom-a10-sim` | `143e15346c163b0788f02624263271230d297a66` | 1 | Review unique commits and worktree data |
| `claude/pr-14-merge-conflicts-jdh85s` | `1c33985dd0b7bfcef04ab5ba6a65a75a7247b704` | 0 | In history; verify current files before any closure |
| `claude/vtx-phantom-retractable-wings-calcs` | `e5705c596c300c2415e3d8b3561ee5eb61dd03c3` | 0 | In history; verify current files before any closure |
| `colin/p0-v4-live-laboratory` | `11c38a1dc914a9308696ced7683d37a9254a98ac` | 0 | In history; verify current files before any closure |
| `docs/phantom-flight-systems-20261102` | `a9fa22a79320c7b093f70fece19b3718c73605ae` | 6 | Review unique commits and worktree data |
| `engineering/a10-airflow-cg-stage1` | `d387cba08a347c50938cf14d9de82fa9893a2bee` | 0 | In history; verify current files before any closure |
| `engineering/argon-stability-transmission-fuel-ecu-20261101` | `063ff3dc36451f2f735ad882ccb74beb7840b24a` | 1 | Review unique commits and worktree data |
| `feat/deterministic-airport-traffic-v1` | `93ecf006fcb1f3402ba34b1b19e0dc43cf214a79` | 0 | In history; verify current files before any closure |
| `feat/vaderland-rotating-office` | `5f58eb7c5936443a9028f9b3ef3f2f3bf9e06efb` | 1 | Review unique commits and worktree data |
| `feat/visual-air-traffic-preview` | `3d9ea031dc92df16fe4fc97030c0640b2378b40c` | 0 | In history; verify current files before any closure |
| `feature/openai-pilot-audit` | `e736cb1781a021d91e8c8c92e823e40a642a6420` | 0 | In history; verify current files before any closure |
| `feature/pilot-model-exchange-audit` | `31e535735d280a1cad56e8faacc04b8c89883488` | 0 | In history; verify current files before any closure |
| `fix/a10-exterior-visible` | `2cbe722d5c1acf403db030160cfccda84bc98554` | 0 | In history; verify current files before any closure |
| `fix/a10-smooth-circuit-cameras` | `cbce1a2f8dd9bd593b57bb562fe8b3f3f886d9d1` | 0 | In history; verify current files before any closure |
| `fix/a10-standalone-preview` | `e75b6f16c70a35be93f349dc7ea4cb56052b913e` | 0 | In history; verify current files before any closure |
| `fix/canonical-r6-launch-20261103` | `75aec5e1d6ab54d25bf366a3d1a88ce390e1003a` | 0 | In history; verify current files before any closure |
| `fix/live-rotor-visual-sync` | `713f1deca1071ccd13d06ba8915cf2559b4bf4f1` | 0 | In history; verify current files before any closure |
| `fix/mobile-flight-view-performance` | `8ecdaf150df21576e9a4c17ee2f2a9df6e312a85` | 0 | In history; verify current files before any closure |
| `fix/restore-three-pilot-modes` | `0228a66974eefe8b3df8b9fe2ccda7f236402b9e` | 1 | Review unique commits and worktree data |
| `integration/vtx-unified-20261107` | `e088a18f7803a3f3dd9091304532fdeb2f8dde76` | 0 | In history; verify current files before any closure |
| `main` | `3f88020c86f6b6bcb19e3b5bc8bac24ce20a52f2` | 1 | Current production base; reconcile merge ancestry |
| `ops/vercel-storage-policy-20261104` | `a1ce86f2770dedd2930f8687c8727a5d5776ad06` | 2 | Review unique commits and worktree data |
| `policy/waypoint-evaluation-contract-20261105` | `54aad77f684a4a0c587a183dae1a9e1044ed8767` | 1 | Review unique commits and worktree data |
| `policy/waypoint-landing-assessment` | `db412880b363ab105e65e5022657e2402d14079f` | 1 | Review unique commits and worktree data |
| `pr/25` | `d6ba8f96405efd8c3979c6da9366b079d7633f74` | 0 | In history; verify current files before any closure |
| `recovery/a10-local-20261106` | `f22e4efa8003cde644a42f9fd317c157d1853ee2` | 0 | In history; verify current files before any closure |
| `reference/phantom-a10b-20261109` | `2af24770c134ab2a466ef289f0b9d72654379b1b` | 0 | Reference evidence; integrated in history |
| `research/phantom-a9-cassette` | `aee8528f215e2dfe0f6679e2576f6ee9a0514ea1` | 0 | In history; verify current files before any closure |
| `sandbox/r6-flight-export-20261102` | `ca8755b1adcf1a3535b3918c057fe7c10e3b512f` | 2 | Review unique commits and worktree data |
| `trial/a10b-into-dashboard-cockpit-20261109` | `1e922139c85f001616752b19dc1b033cae431052` | 1 | Reference trial; notes retained; compare differences |
| `visual-dev/phase1-vaders-taxis` | `461bbe52922dc59b2461bb1d91246438e912b232` | 0 | In history; verify current files before any closure |
| `work/a10-airport-cockpit` | `acc18c32272ea47035522223234ddd92808479be` | 0 | In history; verify current files before any closure |
| `work/dashboard-cockpit-20261107` | `883fc4335db415492721ac4d279243ad52d890b2` | 0 | In history; verify current files before any closure |
| `work/flight-index-20261104` | `6cca85e27018caf6540221e0d580e6322434f1ba` | 2 | Review unique commits and worktree data |
| `work/mobile-pc-isolation-r6-retry` | `c7dc902ce405955f7f63243f40a2feba60de98cc` | 0 | In history; verify current files before any closure |
| `work/r6-mobile-isolated-runtime` | `038fba036f2812c36107305efc6cfef7409b1517` | 0 | In history; verify current files before any closure |
| `work/unified-airport-20261104` | `210272d928f26bfe1b331b5e8c8bc87814ad1d0c` | 0 | In history; verify current files before any closure |

## Local worktrees

Counts are Git status entries at audit time, including staged, unstaged and untracked paths. They are not a content-equivalence review; preserve all of them.

| Worktree | Branch or HEAD | Status entries | Unmerged |
|---|---|---:|---:|
| `C:/Users/steve/Documents/Github/-vtx-flight-sim` | `main` | 418 | 2 |
| `C:/Users/steve/Documents/Github/-vtx-flight-sim/.claude/worktrees/agent-ab30c2b8b057df1a2` | `worktree-agent-ab30c2b8b057df1a2` | 138 | 0 |
| `C:/Users/steve/Documents/Github/-vtx-flight-sim/.claude/worktrees/dreamy-khayyam-7059f0` | `research/phantom-a9-cassette` | 31 | 0 |
| `C:/Users/steve/Documents/Github/-vtx-flight-sim/.claude/worktrees/friendly-hamilton-2c334c` | `claude/phantom-a10-sim` | 30 | 0 |
| `C:/Users/steve/Documents/Github/-vtx-flight-sim/.claude/worktrees/hello-8d1b2f` | `claude/hello-8d1b2f` | 0 | 0 |
| `C:/Users/steve/Documents/Github/-vtx-flight-sim/.claude/worktrees/vtx-phantom-retractable-wings-da1842` | `claude/vtx-phantom-retractable-wings-da1842` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-a10-checkpoint-20261106` | `checkpoint/phantom-a10-live-20261106` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-a10-exterior-fix-20261104` | `fix/a10-exterior-visible` | 26 | 0 |
| `C:/Users/steve/Documents/Github/vtx-canonical-r6-20261103` | `fix/canonical-r6-launch-20261103` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-dashboard-cockpit-20261107` | `work/dashboard-cockpit-20261107` | 1 | 0 |
| `C:/Users/steve/Documents/Github/vtx-flight-index-20261104` | `work/qa-flight-index-20261104` | 4 | 0 |
| `C:/Users/steve/Documents/Github/vtx-integrated-candidate-20261105` | `integration/a10-unified-pilot-20261105` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-integration-20261109` | `integration/workspace-verified-20261109` | 12 | 0 |
| `C:/Users/steve/Documents/Github/vtx-three-mode-recovery` | `fix/restore-three-pilot-modes` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-unified-integration-20261107` | `integration/vtx-unified-20261107` | 0 | 0 |
| `C:/Users/steve/Documents/Github/vtx-visual-traffic-review-20261104` | `detached` | 29 | 0 |
| `C:/Users/steve/OneDrive/Documents/ChatGPT/VTX/sim-audit-fixes` | `fix/simulator-audit-20261103` | 0 | 0 |
| `C:/Users/steve/OneDrive/Documents/ChatGPT/VTX/unified-airport` | `work/unified-airport-20261104` | 15 | 0 |

## Outstanding reconciliation

- Compare the dirty main checkout, especially unmerged `public/app.js` and `src/vtx/live_server.py`, and its untracked flight checkpoints, with the integration. Do not overwrite or move them.
- Compare the dirty OneDrive unified-airport worktree, flight-index worktree and visual worktrees file by file; their status counts do not establish equivalence.
- Review the 6 November A10 checkpoint and R6 engineering/checkpoint branches against the integrated runtime and archived telemetry.
- Test actual live and experiment behavior, PC/mobile controls and reconnect handling. A Vercel build alone does not prove a stateful physics runtime.
- Determine the correct VTX Vercel account/project and production target; the currently connected account lists a different project.

## Engineering records inspected

- [A10-A stable-flight engineering plan](https://docs.google.com/document/d/1frzJSjImLMfn7ygvi0RnO6ESG-yRckhJqZkg-irZxt0/edit): separates measured simulation, synthetic coefficients and unverified engineering hypotheses; requests trim and control-authority testing rather than assuming a completed wingborne envelope. This predates the A10-B reference results.
- [Independent Phantom investigation](https://docs.google.com/document/d/1yQllp_hdkOsKB1FwCb0k3yqMJ-_vruTPRavtop4IqAo/edit): documents hypotheses about hull moment, actuation and transition. Its numerical conclusions are not automatically treated as verified design inputs; later A10-B work supplies opt-in overlays and test evidence.
- [Argon calibration reference](https://drive.google.com/file/d/1-4x9mr9MkmJ6Q2FWM5q-NXrovBbVjolW/view): identifies the R6 diamond rotor ordering and recorded hover calibration; its listed flight results are historical simulation evidence, not a new integration acceptance run.
- [R6 mobile runtime record](https://drive.google.com/file/d/1wtopfxloYPMesFEkCc1j-AlFDE3qoErV/view): describes paused checkpoint recovery, isolated persistent storage, a single stateful service and the unresolved yaw/world-to-body navigation coupling.
- Remote Desktop Commander reports Steve_PC online; its process inventory was inspected without stopping or changing existing processes.
