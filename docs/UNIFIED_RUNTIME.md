# One local cockpit for all VTX models

The active stateful simulator is the PC server on port **8765**. `scripts/launch_pc.py` opens a vehicle selector at `/`; its choices are R4, R5, R6, R6 variator, Phantom A9 as drawn, Phantom FX-A A9, Phantom A10 as drawn, and the current Phantom FX-A A10. Choosing a vehicle loads its physical inspection model and matching control panel without starting a sortie. Each new sortie records the selected variant in its metadata. An active sortie must be ended and retained before another vehicle is selected.

The launcher stores new records under `%LOCALAPPDATA%\VTX\unified-live`. Earlier R6 records, including the 3 November sortie that was ended and archived on 4 November, are preserved under `%LOCALAPPDATA%\VTX\r6-live`; the older PC backup is under `Documents\VTX-flight-logs-backup`. The [flight index](FLIGHT_INDEX.md) resolves the records across those archives. Run `tools/flight_index_builder.py` to regenerate the index after a session. Its local archive manifest contains absolute PC paths and is excluded from the online repository.

The launcher deliberately allows model selection instead of applying the old R6-only mission lock. `/api/release` reports the actually loaded model, whether the default R6 identity matches, and whether selection is allowed. `matches: false` after choosing Phantom means it differs from the R6 default; it is not an error by itself. The selected model's metadata and exact model hash are the flight's evidence.

Inspection switching uses `/api/model-preview` and creates no sortie or flight log. Phantom previews show the Phantom fly-by-wire panel; its controls become active only after a Phantom mission starts. R4–R6 drive settings are hidden for Phantom, and a Phantom mission uses the model's own default fuel and power configuration unless its separate Phantom options are supplied through the API.

The Vercel FastAPI deployment is a web preview. It has no persistent MuJoCo flight process, so a READY deployment is not a second live cockpit. Historic Vercel Sandbox sessions have stopped; their retained mobile A10 data is in the PC backup and the [mobile flight branch](https://github.com/SDarkVader/-vtx-flight-sim/tree/work/a10-airport-cockpit/evidence/phantom/mobile_flights_20261104).

Only stop processes whose command lines identify this VTX checkout and server. Ports used by Windows services, Google Drive, Ollama, peripherals, and other applications are unrelated to the simulator.
