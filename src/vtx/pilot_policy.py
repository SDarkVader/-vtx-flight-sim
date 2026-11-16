"""Fresh telemetry requirements for new pilot decisions, never held controls.

This validates the command envelope. It cannot establish whether an external
client used a learned model or how that client reached its decision.
"""

import math


def observation_error(
    observation,
    now,
    run_id,
    expected_run_id,
    pilot_run_id,
    observation_id=None,
    previous_observation_id=None,
):
    if not run_id or (expected_run_id or pilot_run_id) != run_id:
        return "Colin action must identify the current run"
    if not isinstance(observation, dict):
        return "Colin action requires an actual permitted observation ID"
    observed_t = observation.get("t_s")
    if (
        isinstance(observed_t, bool)
        or not isinstance(observed_t, (int, float))
        or not math.isfinite(observed_t)
    ):
        return "Colin action requires a valid observation time"
    # Pilot packets round simulation time to milliseconds.
    if observed_t > float(now) + 0.001:
        return "Pilot observation is from the future; observe again before deciding"
    # Slow model decisions are permitted. A later decision must observe again
    # instead of replaying a packet already consumed in this pilot epoch.
    if (
        previous_observation_id is not None
        and observation_id <= previous_observation_id
    ):
        return "Pilot observation was superseded by a prior decision; observe again before deciding"
    return None
