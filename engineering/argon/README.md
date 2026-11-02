# VTX — Gemini Argon engineering workspace

**Base:** merged PR #4 (`67d170512877ff291f293bc63fe3537391c0f168`), 1 November 2026.
**Working branch:** `engineering/argon-stability-transmission-fuel-ecu-20261101`.
**Role:** Gemini Argon — engineering analysis, physical redesign and robotics.
**Status:** engineering instructions only. Nothing in this directory is evidence that an engineering modification is installed or validated.

## START HERE

Argon: use THIS DIRECTORY as your task root. Read the following in order:
1. [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) — exact historical and engineering references and evidence limits.
2. [01_TRANSMISSION_AND_TANKS.md](01_TRANSMISSION_AND_TANKS.md) — first scoped engineering job, deliverable and test gates.
3. [02_ROTORS_AND_ECU.md](02_ROTORS_AND_ECU.md) — dependent rotor and ECU research after the geometry work passes review.

Review the authoritative existing code and physics documents linked from these files. The existing VTX simulator is a **mass-bearing, real-time 6-DOF MuJoCo multibody system** operated with live fly-by-wire commands. Do not replace it with a game animation, fabricated physics, hidden altitude hold or replayed/synthetic flight.

**First implementation task:** derive an **isolated proposed airframe variant** that fixes gearbox/transmission positions and four fuel tanks together, with traceable source transforms and a complete before/after mass, CG, inertia, collision and propulsion-linkage audit. **STOP for engineering review** before replacing rotor coupling or enabling an active ECU.

## Branch and historical integrity

PR #4 was MERGED into `main` before creating this directory. It includes substantial visual/environment changes and three new 1 November flight record folders. Do not delete, rewrite, or reset these changes to the older main snapshot.

Earlier Argon handoff is preserved verbatim in commit `6a70bced4a31803c20355afb638248f8b627366f`'s message; this directory is the navigable implementation scope. The branch contains the merged PR #4 ancestry and these engineering instructions. `main` is not the engineering work branch.

Checkout and inspect:

```bash
git fetch origin
git switch engineering/argon-stability-transmission-fuel-ecu-20261101
git status --short
ls engineering/argon
```

Before proposing code, verify the current branch and read authoritative physics and evidence. If your checkout shows newer commits than those cited here, examine the diff; do not silently discard later work.

## Scope boundaries and working rules

- All part dimensions, current pivots, meshes and source hierarchy must come from the pinned CAD / ledger. Clearly tag measured source geometry vs. estimated mass allocations vs. hypothetical component performance vs. actual simulated observations.
- Preserve original R5 and 31 October/1 November run records; new variants may not mutate historical results.
- Mechanical clearance is a 360-degree **direction** of tilt inside a 20-degree **resultant tilt cone**, NOT continuous 360-degree end-over-end rotation of the nacelles.
- Existing common-shaft rotor constraints remain a useful control baseline; independent ring-motor transmissions are **concepts**, not fitted hardware or operational simulation.
- The current training-assistance and cowling ECU are **shadow/advisory** only. Do not engage unvalidated aircraft control.
- Original VTX source is proprietary. Use only permitted engineering research references; keep this repo private.
- Never infer stable flight, completed route or safety qualification from a static calculation, screenshot or sortie name.

## Deliverable at end of first scoped task

Provide a reviewable commit/PR with:
- old and proposed geometry placements, original part IDs and transformations;
- before/after mass ledger, CG and full symmetric 3×3 inertia for each fuel condition;
- shaft/input/output routing and torque/joint constraints;
- complete sampled clearance results plus stated untested swept tolerances;
- unchanged baseline regression and modified variant regression results;
- unresolved physical dimensions/strength/actuator/fuel slosh inputs.

Do not implement the entire ECU and geartrain in the same change. Ask for review of actual results, not design approval from unverified assumptions.
