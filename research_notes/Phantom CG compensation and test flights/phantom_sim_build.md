# Phantom sim build: summary

The full note is in `docs/phantom/PHANTOM_SIM_INTEGRATION.md`.

## Hover results

| Variant | Mass | CG x | Hover result |
|---|---|---|---|
| As drawn (`phantom`) | 1897 kg | -0.73 m | **Not feasible.** Collective margin -21%, worst pod -46%. |
| FX-A (`phantom-fx`) | 1888 kg | -0.15 m | **Feasible on the bench.** Collective margin +42%, worst pod +31%. |
| FX-C load | 1734 kg | -0.16 m | Margins +54% / +42%. |

For the as-drawn aircraft, the CG is 0.58 m behind the pod centroid and the rear fans saturate.

## How the flight-test method items map to the sim

- **Stability modes:** off, rate_damping, attitude and attitude_vs. Vertical-speed hold is the only outer loop. Each mode's contribution is logged.
- **Time scale:** `time_scale` (at most 1) is logged in the run keys, in every action's timing block and in the summary.
- **PTI:** step, doublet, 3-2-1-1 and sweep inputs on any axis. The pilot arms them and the FBW executes them. They are logged as `pti_event`.
- **Lease expiry:** recorded as a `command_lease_expired` event with `ABORT`, plus `lease_abort_ring.npz`.
- **Leg load-cell CG gate:** recorded in `phantom_run_keys.cg_gate`.
- **Section 3 logging table:** covered by `phantom_steps.csv.gz` (100 Hz), `physics_audit` (20 Hz), and the observations and actions, which carry both sim time and wall time.

## Commands

```
PYTHONPATH=src .venv/Scripts/python.exe tools/phantom/phantom_bench.py
VTX_DATA_ROOT=<scratch> PYTHONPATH=src .venv/Scripts/python.exe -m uvicorn vtx.live_server:app --port 8766
python tools/phantom/phantom_pilot_client.py start --variant phantom-fx --load-state FX-C --time-scale 0.2
python tools/phantom/phantom_pilot_client.py start --variant phantom --time-scale 0.2
python tools/phantom/phantom_pilot_client.py observe
python tools/phantom/phantom_pilot_client.py action --observation N --mode attitude_vs --collective 0.55 --vs 0.5 --brake 0 --reason "..."
```

No missions were flown. The benches are physics tests with canned inputs.
