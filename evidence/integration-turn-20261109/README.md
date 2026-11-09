# Integrated A10-B fan-assisted turn

Executed `reference/phantom_a10b_20261109/scripts/v3_a10b.py evidence/integration-turn-20261109 turn_fan` with MuJoCo 3.17.0 on the integration worktree. The copied `camp_repo.py` is the unmodified reference helper. Output `v3_turn_fan.json` is new telemetry; the reference records remain under `reference/phantom_a10b_20261109/telemetry/`.

Configuration SHA-256: `3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01`; mass 1933.1 kg. The scripted test started airborne after deployment, and completed a 90 degree heading change in 29.4 seconds while decelerating from 59.7 to -1.2 m/s; altitude changed -0.1 m. This is a simulated fan-assisted test, not evidence of conventional runway rotation or fans-off sustained flight.
