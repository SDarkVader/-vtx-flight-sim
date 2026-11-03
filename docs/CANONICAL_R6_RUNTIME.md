# Canonical VTX R6 cockpit

**Supported build:** P0-V4A-assembly-r6, physics `audit-fixes-20261103-r3`, render asset `/assets/airframe-r6.glb`.

**PC launch:** From a current checkout of `main`, run `.venv\\Scripts\\python.exe scripts\\launch_pc.py` on Windows. The canonical cockpit binds port **8765** and opens `http://127.0.0.1:8765/`. Only one instance may hold that port.

The launcher uses the persistent `%LOCALAPPDATA%\\VTX\\r6-live` flight-data directory (unless `VTX_DATA_ROOT` is explicitly provided) so an old R5 checkpoint in a Git worktree cannot silently replace R6. The old worktree flight records remain where they are; any migration must be a deliberate copy, never an overwrite. The server refuses to start if the loaded MuJoCo revision, physics revision, or render asset disagrees with `src/vtx/release.py`. Requests to start another airframe return HTTP 409 when the launcher sets `VTX_ENFORCE_RELEASE=1`. Query `/api/release` to verify the actual loaded identity and enforcement; do not infer it from a filename or UI screenshot.

**Vercel:** GitHub `main` supplies the current deployed source, and the deployment commit must be inspected independently of its READY status. Vercel's FastAPI deployment is not a continuously running stateful MuJoCo flight clock. For real remote flying, a single protected persistent backend must be exposed over HTTPS. Do not mistake a passing Vercel build or a snapshot/preview for a running cockpit. Temporary Vercel Sandbox sessions stop and need explicit resumption.

Before flights, confirm `/api/release` reports `matches: true` and `enforced: true`; check `/api/observe` shows the chosen departure and the R6 revision. Do not replace an active flight or any saved checkpoint without first retaining its evidence.
