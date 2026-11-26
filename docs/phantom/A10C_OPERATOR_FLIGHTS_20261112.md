# Phantom A10-C — manual flight record (12 November 2026)

The Phantom FX-A A10-C was flown manually in the VTX simulator on 12 November 2026. Cockpit screenshots and a screen recording document climbing flight, high-altitude manoeuvring, descent, low horizontal groundspeed during ascent, and an impact at the end of a recorded run.

## Recorded flight measurements

| Recording | Captured telemetry | Flight behaviour |
| --- | --- | --- |
| Cockpit capture `70382.dng` | Clearance **1,456.98 m**; vertical speed **+14.31 m/s**; ground speed **5.09 m/s** | High-altitude climbing flight |
| Cockpit capture `70392.png` | Clearance **921.75 m**; vertical speed **−14.19 m/s**; ground speed **15.82 m/s** | Descending flight with forward motion |
| Cockpit capture `70394.png` | Clearance **19.76 m**; vertical speed **+7.90 m/s**; ground speed **0.18 m/s** | Ascent with near-stationary horizontal movement |
| Seven-minute screen recording (`Recording 2026-11-12 212038 … .mp4`) | Example frame: clearance **1,048.81 m**; vertical speed **+0.38 m/s**; ground speed **19.85 m/s** | High-altitude forward flight |
| Same recording, final seconds | At approximately **7:03**: clearance **7.61 m**; vertical speed **−15.75 m/s**; subsequent simulator statuses **IMPACT**, **HARD_LANDING**, **POWER_LIMITED** | High-rate descent and recorded impact |

The operator exercised canards, yaw/rudder, bank, collective and forward thrust during flight. The flight recordings capture the aircraft responding to control inputs, manoeuvring and changing speed and altitude. Impacts and unsuccessful landings remain part of the flight-test history alongside the preceding successful manoeuvres.

## Earlier A10-C runway departure — 11 November

The [A10-C fans-off takeoff study](A10C_FANS_OFF_TAKEOFF.md) records a separate scripted live-simulator runway test with lift fans at **zero rpm**: approximately **79 m/s** at wheel-off, approximately **one kilometre** ground roll, and **41 m** radar height at forty-two seconds.

These are separate test sessions, retained as separate records to preserve their configurations and telemetry.

## Engineering record and source material

The flight evidence was supplied as cockpit captures and a screen recording during the README update. The original media and full-resolution flight telemetry remain outside this documentation commit; this record transcribes the supplied measurements and links the earlier runway test. Source media can be added to the repository or flight index without altering the reported results.

A10-C cockpit development is tracked in [PR #45](https://github.com/SDarkVader/-vtx-flight-sim/pull/45) and [PR #46](https://github.com/SDarkVader/-vtx-flight-sim/pull/46). The simulator's existing A10-B default remains unchanged by this documentation update.
