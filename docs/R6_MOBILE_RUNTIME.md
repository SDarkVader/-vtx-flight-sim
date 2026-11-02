# Isolated R6 mobile runtime

New missions default to R6, Stand 1 `(0, 0)`, 1,200 rpm, 300 kW, 10 kg fuel and the critical-damping gear proposal. The selected departure and destination remain independent of aircraft revision. Retry retains the prior revision and configuration unless the API caller explicitly overrides a field. A restored checkpoint is held paused at its saved state. An unreadable checkpoint blocks replacement instead of archiving it automatically.

## Cloud operation

Run a single stateful Uvicorn process behind HTTPS with `VTX_CLOUD_ACCESS_TOKEN` set to a unique, randomly generated secret of at least 32 characters and `VTX_DATA_ROOT` set to a dedicated persistent directory. A browser signs in at `/login` and receives a Secure, HttpOnly, SameSite=Strict cookie. API, WebSocket, evidence and static files are protected when the token is set. Unsafe browser requests require the matching HTTPS Origin. Keep the token private and rotate it by changing the environment and restarting the process. Set neither variable on existing PC installations to retain the existing LAN behavior.

The existing Colin pilot can connect to an isolated cloud instance explicitly with its simulator URL and `VTX_CLOUD_ACCESS_TOKEN` in its process environment; it sends the token as a bearer credential over HTTPS. Never reuse the PC data directory for the cloud instance. The cloud token authenticates users but does not provide individual operator accounts or a server-enforced exclusive manual-control lease. Only trusted operators should share it.

Vercel Sandbox sessions have a time limit. A persistent sandbox snapshots its filesystem when stopped, but the service and URL do not automatically restart: an operator must resume the sandbox and start Uvicorn again. It is a temporary test environment, not a continuously available production deployment. Never rely on Vercel Functions process memory as the flight session.

## Evidence and limitations

Stand 1 is a visual pad marking drawn about 2 cm above the physical terrain; the gear is supported by the terrain at elevation zero, rather than a separate pad collider. The real R6 physical model and R6 GLB remain in use; there are no scripted trajectories. The Argon reference is advisory and its loader currently accepts the baseline gear only, so it does not assert calibration of the critical-damping configuration. The documented near-90-degree yaw/world-to-body cross-coupling remains unresolved; no navigation or autonomous landing reliability is claimed. Ground-support tests are isolated simulation checks, not flight certification or a real-world structural assessment.
