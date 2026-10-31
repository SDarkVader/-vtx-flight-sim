# Import of complete local starter is still outstanding

The initial GitHub files are an execution contract, **not** the complete pre-existing starter harness.

Use the ChatGPT-provided `vtx-flight-sim-map-missions.zip` or `vtx-flight-sim-map-missions.bundle` (local commit `e768250`), which contains 31 passing local mathematical and map-selection tests, Python source, numerical inputs, legacy engineering studies and a concept image. The GitHub repository created here is independent and currently does not yet contain those full files or source history.

The Git bundle represents a full local history; import carefully, preserving the existing remote branch, and verify the resulting tree before pushing to the private GitHub repository. Alternatively extract the ZIP and commit the contents, updating the README only after verifying actual file presence.

Run `pip install -r requirements.txt` then `PYTHONPATH=src pytest -q`. Confirm 31 tests before proceeding with the flight simulation. Build browser-based 3D physics, map missions and two-stage learning as specified in the contracts. Do not mistake the starter numerical checks for implemented 3D flight.

IMPORTANT: The remote repository is currently named `-vtx-flight-sim` (leading hyphen); use that exact URL unless renamed.
