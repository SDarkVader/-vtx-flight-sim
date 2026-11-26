# Vaderland development log

## Origin — 20 November 2026

Vaderland began with a conversation about Elon Musk's flying-car idea and what a realistic flying car might look like. A 2D concept image was selected, engineering calculations followed, and the design became the Argon R6 simulation. The Phantom and Ricochet followed the same approach: each began as 2D concept art and was developed into a 3D simulated vehicle with engineering models, controls and physics testing. As the vehicles developed, the airfield, city, roads, marina and trial courses grew around them, forming the connected world of Vaderland.

## Vaderland 32 · Manual-flight replay

The field check followed a manual Phantom A10-D from vertical takeoff at Runway 08 to the northwest side of Meridian. The replay reel shows the hover attempt, loss of control and recorded terrain impact. The world showcase also retains the Grand Loop DNFs, the Argon transports and the Ricochet runs. [See the current media](VADERLAND_MEDIA.md).

## Conversational AI piloting

Alongside manual flying and driving, VTX has been developed around AI models taking live control of simulated vehicles. The owner can give conversational instructions; an AI pilot receives limited, permitted telemetry and view information, decides what control inputs to issue, and adjusts after observing the results. The aim is genuine piloting through the vehicle's controls, not following a prerecorded trajectory or hiding an autopilot behind an AI voice. AI-piloted flight attempts and manoeuvres are already part of the project's history. Dedicated AI-only time trials are a planned competition format, not a claim that the mode is finished.

## Cockpit radio and vehicle sound · 25 November 2026

Work began on how the Phantom A10-D sounds and on a radio for the cockpit. **All of it is in development. None of it is part of the game yet, and no vehicle sound has been approved for it.** The owner listens and approves before sound goes in.

**Vehicle sound.** The owner is making takes in Adobe Firefly and chose a mix of grounded and heightened sound, because this is a video game. So far the takes cover moving parts: wing deployment, flaps, a geared motor and the thruster pods. Fans, boosters, air brake, wing latch, touchdown, tyres, wind and cockpit hum are still computer-made stand-ins.

**Sound Studio.** A set of local tools on [`claude/sound-studio-dev-20261125`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/sound-studio-dev-20261125/tools/sound-studio) offers several designs for each part and replays recorded flight `20261119T194125-4656ed` step by step: vertical takeoff and landing, then a runway takeoff and transition to hover. Starting volumes were set by measurement and then tuned by the owner. The flight replay has only been partly tested.

**Cockpit radio.** It plays the player's own music, with a song knob. There are two separate versions:

- **PC game:** native Windows, on [`claude/native-cockpit-radio-20261125`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/native-cockpit-radio-20261125). [How to add it to a Windows build](https://github.com/SDarkVader/-vtx-flight-sim/blob/claude/native-cockpit-radio-20261125/native/radio/README.md). Its headless radio checks (13) and the injected flight-input test (131 checks) passed.
- **Local development:** the browser cockpit, on [`claude/cockpit-radio-20261125`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/cockpit-radio-20261125). Its unit test passed, and the panel was tried on a blank test page.

Neither radio had been launched inside its full application, or checked by ear there, when this was written. The branches were pushed with hosted CI skipped, to avoid creating Vercel previews, so the hosted tests have not run on them. No music or sound takes are in the repository.

Claude also wrote lyrics and a production prompt for an original radio song, *One Sixty and Climbing*, drawn from the AI pilot's aborted transition in that flight record. It has not been produced.
