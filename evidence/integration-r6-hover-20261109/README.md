# R6 isolated hover integration check

Run `20261109T155749-05fcd0` used the integrated Python/MuJoCo laboratory, the canonical `P0-V4A-assembly-r6` model, `audit-fixes-20261103-r3` physics and `/assets/airframe-r6.glb`. The independent test laboratory used its own evidence and checkpoint directory. The test script is `tools/integration_r6_hover_check.py`; it requires a new output directory.

The rotors reached the scripted spool threshold at 2.027 s and the aircraft reached a maximum sensor-reported radar clearance of 1.523 m before the test stopped. Individual commands, observations, software identity and the final summary are retained in this directory. This is a short simulated hover check; it does not demonstrate navigation, autonomous landing or physical aircraft performance. The historical heading-dependent coupling finding remains an open engineering item.

The run metadata reports parent commit `a058c94ba346d7d48a396a75752ab1a0885f4f4f`; the worktree had additional uncommitted integration changes at execution, so that commit alone does not identify the complete runtime. Its captured runtime source SHA-256 is `9c40fab4b268aac535c7b05f8e4836e2d4d8f5e87a0ff37c42b072a0463915f8`.
