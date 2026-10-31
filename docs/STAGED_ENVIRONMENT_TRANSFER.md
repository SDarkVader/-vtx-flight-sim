# Staged environment transfer and experiential learning

**Stage 1:** Colin builds a deterministic interactive environment and trains/tests a physically bounded controller and estimator using observable flight experience. Record wind, disturbances, missions, failures and adaptations; save a versioned learning checkpoint and frozen initial controller.

**Stage 2:** The proprietor supplies a different environment later. Do not create, inspect, preload, pretrain on, infer private layout of or tune for Stage 2 before its actual introduction. At first exposure, load the frozen Stage 1 checkpoint. Retain the learned state, but give the controller only sensor/environment observations it is permitted to obtain, never the full simulator truth or proprietor's privileged map view.

Keep immutable ground truth physics separate from mutable controller/adaptation state. Adaptive parameters cannot rewrite mass, gravity, collision response or safety outcomes. Never suppress a crash to make the learner appear successful.

Evaluate transfer against (a) the transferred checkpoint, (b) an identical cold-start learner and (c) a fixed non-learning baseline under the same initial conditions, environment version and seeds. Record all observations and updates, including setbacks. Measure flight completion, collision/crash, path/attitude error, energy, jerk and actuator saturation. Replays with matching software/solver/seed must agree.

Save complete checkpoint hashes and audit first exposure. An online learning method and persistence must actually be implemented, not merely claimed. User decides when and what Stage 2 is.
