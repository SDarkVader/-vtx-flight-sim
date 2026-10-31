# Two-stage learning experiment

**Stage 1:** Colin constructs the VTX physical digital aircraft and a navigable first test world. Colin begins inexperienced, pilots through actual fly-by-wire commands and live observations (see [LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md](LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md)), attempts takeoffs, flight and landings from map-selected valid locations, crashes when physics dictates and updates its controller/policy from observed experience. Save every meaningful attempt, outcome and versioned learning checkpoint. Preserve physics/model revisions separately from learned policy changes.

**Stage 2:** The proprietor later introduces a different environment. Do not generate, load, inspect, pretrain, tune against or anticipate it now. Carry forward Colin's Stage 1 learned piloting state, with the same live observation/fly-by-wire action interface and physical aircraft; new learning must arise from observed events in Stage 2.

Report learning transfer versus a true cold start under controlled, reproducible conditions. Evaluate generalisation, failure, crash frequency, adaptation and physical feasibility. Do not silently reset, use privileged access to scene truth, or fabricate successful transfer.

The experiment is intended to expose the aircraft's and pilot's limitations, not to ensure success.
