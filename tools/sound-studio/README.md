# Sound Studio (development tools)

Local tools for designing Vaderland vehicle sound and the cockpit radio. **Development only: none of this is part of the game, and no sound in it is approved for the game.** No audio files or music are included; the pages load your own.

## What is here

| File | Purpose |
| --- | --- |
| `Radio.html` | Radio for any number of songs: search, shuffle, song knob, remembered folders |
| `Vehicle/Phantom A10-D/Vehicle Designer.html` | Several designs per vehicle sound, and a step-by-step flight replay |
| `Vehicle/Phantom A10-D/Sound Audition.html` | Loop, layer and mark takes |
| `Vehicle/Phantom A10-D/Sound map.md` | Which sounds the Phantom needs and what drives each |
| `Vehicle/Phantom A10-D/vehicle-tuning-2026-11-25.json` | Current settings for each part (work in progress) |
| `Vehicle/Phantom A10-D/Firefly prompts to try.txt` | Prompts for sounds with no take yet |
| `build-studio.js` | Joins the three pages into one |

## Build and open

```powershell
node tools\sound-studio\build-studio.js
```

This writes `VTX Sound Studio.html` next to the script. Open it in Edge or Chrome. Choose a sounds folder; songs go in a folder named `Radio`, and every other audio file is treated as a vehicle clip. Edit the three source pages, not the generated one, then rebuild.

## Settings in the tuning file

| Setting | Meaning |
| --- | --- |
| `name` | Starting design preset |
| `source` | Take file name; empty means a computer-made stand-in |
| `pitch` | Playback rate, or frequency multiplier for a stand-in |
| `weight` / `edge` | Low shelf at 220 Hz / high shelf at 2600 Hz, in dB |
| `clunk` | Strength of the added start and stop thump |
| `echo` | Send to a 1.4 s reverb |
| `layer` | Amount of a second source mixed in |
| `volume` | Linear gain |
| `length` | Movement length in seconds when played on its own |

## How flight data drives the sounds

The replay uses Phantom A10-D flight `20261119T194125-4656ed`, sampled at 10 Hz and built into the designer page. Each rule below is the designer's current behaviour, offered as a starting point for the PC game.

| Sound | Level | Pitch or trigger |
| --- | --- | --- |
| Fans | `r^1.7`, `r` = mean fan rpm / 4500 | rate `0.45 + 0.75 r` |
| Boosters | `j^0.8`, `j` = total thrust / 6000 N | rate `0.75 + 0.35 j` |
| Wind | `(speed / 80)^1.4` | rate `0.8 + 0.4 speed / 90` |
| Tyres | `speed / 50`, only with ground contact above 0.5 m/s | rate `0.7 + 0.6 speed / 80` |
| Cockpit hum | constant 0.25 | none |
| Wings | while the wing state is neither stowed nor locked | thump at start and stop |
| Pod tilt, flaps | while moving faster than 1.5 degrees per second | thump at start and stop |
| Legs | while moving faster than 0.04 m per second | thump at start and stop |
| Wing latch | wing state becomes locked | single hit |
| Touchdown | ground contact after being airborne | single hit |

Level and rate values are clamped to the 0 to 1 input range. The air brake is not in the replayed columns.

## Cockpit radio

The radio itself exists as two separate pieces on their own branches:

- **PC game (native Windows):** [`claude/native-cockpit-radio-20261125`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/native-cockpit-radio-20261125). The radio is the single commit `6e710bd`.
- **Browser cockpit (local development):** [`claude/cockpit-radio-20261125`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/cockpit-radio-20261125). The radio is the single commit `83bc5ae`.
