# Voice pilot (Phantom, phantom-fbw-1)

Press **🎙 Voice** on the Phantom panel. It is push to talk and needs the Web Speech API, so use Chrome or Edge
(Android Chrome works). Speech is matched against a fixed grammar (`public/voice-pilot.js`). No language model sits
in the control loop.

Each command patches the panel's own `phantom-fbw-1` command, so it follows the same heartbeat, 5 s lease and
authority rules as the sliders. Every applied command is spoken back. The next action's `reason` records it for the
flight log, e.g. `Voice: "boost fifty percent" -> boost {...}`. For the console or tests,
`__phantomVoice('boost 50 percent')` takes typed input.

| Say | Effect |
|---|---|
| boost 50 percent / full boost / boosters off | booster **thrust** fraction. The plant's throttle commands rotor speed (thrust ∝ ω²), so 50% thrust sends throttle √0.5 = 0.71 |
| brakes off / stop / brakes on | brakes, plus drive zero on stop |
| drive 80 percent / reverse 20 / coast | wheel drive |
| take-off configuration | wings deploy, flaps 30, canards deployed at 0°, attitude hold |
| deploy the wings / flaps 30 / flaps up | high-lift system (flaps auto-retract above 75 m/s) |
| **downforce** / max downforce | canards deployed at −6° / −10° for road nose-rise control (`engineering/phantom/drs_flap.py`) |
| canards minus 8 / canards deploy | canard trim |
| nose up 8 / nose down 3 / level | attitude hold (1.0 = 10°) |
| climb 2 / descend 1.5 / hold altitude | vertical-speed hold (±3 m/s) |
| collective 60 / VTOL mode / legs down | hover configuration |
| status | airspeed, radar altitude, vertical speed, weight on wheels, wings, flaps, battery, warnings (pilot-visible sensors only) |

**These need "confirm"** (within 8 s; "cancel" drops them): stow wings, fold canards, retract legs, road mode,
engine off, stability off.

Tests: `tests/js/voice_pilot.test.mjs`, run by `tests/test_voice_pilot_js.py`. An end-to-end check against the live
server confirmed every command in the plant's command state, including the confirm flow.
