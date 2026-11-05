# Unified airport: Phantom A10 spawn and climb check

On 5 November 2026, the unified-airport branch was exercised with the FX-A A10
at departure `[0, 0]`, the VTOL start configuration, and the P6 DRS and front
canards enabled. The test sent one manual `phantom-fbw-1` command: engine 1,
`attitude_vs`, collective 0.6, vertical speed +1 m/s and brakes released. Each
case ran 12 simulated seconds, using the same initial conditions. No pilot or
waypoint controller was used.

| Scenery collisions | Run | Start XYZ (m) | Maximum height gain (m) | Maximum horizontal drift (m) | Crash |
|---|---|---|---:|---:|---|
| Enabled | `20261105T185128-ab74b1` | `[0, 0, 0.23]` | 11.39 | 5.68 | No |
| Ignored | `20261105T185133-0eadc4` | `[0, 0, 0.23]` | 11.39 | 5.68 | No |

Ground height at the selected start was 0 m; spawn height is the aircraft
origin, not the height of its feet. Both cases remained airborne at the end,
with a final speed of approximately 1.05 m/s. The test confirms that this
specific start and command can lift off without a modeled collision in either
mode. It does not demonstrate a complete mission, stable hover, obstacle
avoidance, other spawn locations, or general A10 controllability. The observed
horizontal drift and prior P6 pitch-instability findings remain relevant to
flight testing.

Run evidence is retained locally in `a10-readiness-probe` beside the checkout,
under the corresponding `scenery_on` and `scenery_off` data roots. To repeat in
a new, separate data directory:

```text
$env:PYTHONPATH = 'src'
python -m tools.phantom.a10_spawn_probe --data-root <new-isolated-directory>
```

The command refuses to replace an unfinished flight found in the chosen test
data directory. It does not use or restart the user's existing flight server.
