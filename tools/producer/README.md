# VTX Producer

A sound studio for the phone: one self-contained page, no server, nothing uploaded. It is for building the game's atmosphere: music, vehicle sound and ambience, mixed and metered, then bounced to WAV. **Development only: none of it is part of the game, and no sound in it is approved for the game.** No audio is included; you load your own.

Open `VTX Producer.html` in a browser. On a phone the easiest route is to host the file (any static host) or open the published copy; a raw GitHub link shows source text, not the page.

## Benches

| Bench | What it does |
| --- | --- |
| Tracks | Multitrack timeline: import clips or stems (one track each), move, trim, split, chop, duplicate, reverse, fade, gain and pitch per clip; tempo, snap, loop and click; undo and redo; save points; bounce the song through the master, stems, or a seamless loop. Every track is a full channel strip. |
| Mix | Four channel strips (Music, Vehicle, SFX and takes, Ambience): fader with a dB taper, constant-power pan, mute and solo, trim, low cut, three-band tone, compressor, a room send and an echo send. Track strips too. Master suite: tone, glue compressor, width, limiter with a ceiling. Meters: momentary, short-term and integrated loudness (K-weighted and gated as in ITU-R BS.1770), peak, true peak (estimated), phase correlation, spectrum. Ducking on vehicle hits and marked takes. Project file. |
| Music | Radio deck (tuning and jog discs, shuffle, repeat, search, lock-screen controls) and a rack of 17 character dials plus volume with presets and an A/B bypass. |
| Vehicle | The Phantom A10-D parts, six designs each, your 25 Nov 2026 tuning, the 10 Hz flight replay, auto balance. Bounce a part, or all twelve, to WAV. |
| Scene | Looping beds and random one-shots with pitch, level and pan drift. Several scenes with crossfades between them. Bounce a scene through the Ambience strip and master; the same variation gives the same file. |
| Takes | Library (kept in the browser if you ask), waveform editor (trim, fades, normalise, gain, seamless loop points), audition, jobs, a notebook of Firefly prompts, bounce to WAV. Edits never change your files. |

Every control that has a range is a rotating disc with click-stop increments (touch, keyboard arrows, double-tap to reset). Fine increments make each stop smaller.

## Build

```
node tools/producer/build.js
```

writes `VTX Producer.html` next to the script. Edit the files under `src/`, not the generated page. `src/data/flight.js` is the flight record copied unchanged from the desktop Vehicle Designer; `src/data/vehicle-tuning-2026-11-25.json` is your tuning.

## Tests

```
node tools/producer/test/run.js
```

Needs Node 18 and Playwright. It makes synthetic audio (including a 997 Hz tone at -20 dBFS), plays it through the page in headless Chromium and checks what comes out: loudness against the BS.1770 reference, compressor and limiter response, pan law, dial increments, faders, mute and solo, take editing and bounce (WAV and zip are parsed), scenes, persistence, project file, touch gestures, and no sideways scroll from 320 to 430 px wide. 171 checks passed when this was written. `test/tracks.js` also runs on your own audio: set `USER_AUDIO` to a folder holding `Radio/` and `Sounds/`.

## What is not verified

- **Real phones.** The tests run in desktop Chromium. Safari on iPhone and Chrome on Android are untested. Known risks: iOS Safari mishandles `preservesPitch` on an element routed through Web Audio (WebKit bugs 240405 and 311000), so the speed dial and Keep pitch may misbehave there; background playback with the screen locked is not checked; the silent-switch fix uses `navigator.audioSession`, which only Safari has.
- **Hosted copy.** Saving files from a hosted page depends on the host. WAVs go out inside a zip because hosted pages may not save `.wav` directly. Not tried in that host.
- **Loudness and true peak** are measured in the page from the output. The tone check agrees with the reference to 0.01 LU, but this is not a certified meter, and the true peak is a 4x interpolated estimate. Check a final master elsewhere.
- **Compressor makeup.** Browsers add automatic makeup gain to their compressor; it is cancelled with the formula the Chromium implementation uses (checked in Chromium: unity below threshold). Safari and Firefox share the algorithm but are unchecked.
- **Plugins.** VST, VST3, AU and CLAP plugins are programs for a desktop operating system; a web page cannot install or run them. Use them in Ableton: bounce stems here, process them there, and import the results with Add, Import stems.
- **Not built:** time-stretch (warp), a clip launcher, automation lanes, recording, independent pitch shift (speed changes pitch, or pitch is held, nothing between), per-strip stems, full-mix bounce, MP3 or Ogg export, undo.
- Takes bounce at the device sample rate (44.1 or 48 kHz); parts and scenes at 48 kHz.
