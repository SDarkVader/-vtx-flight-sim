"""Stage 6-8 live airborne liftoff, perturbation calibration, and controlled settle."""
from __future__ import annotations
import json
import math
from pathlib import Path
import time
import urllib.request

BASE = "http://127.0.0.1:8765"
TELEM_IN = Path(__file__).resolve().parent / "live_calibration_telemetry.json"
TELEM_OUT = Path(__file__).resolve().parents[1] / "evidence" / "argon_live_stability_calibration.json"


def get(path: str):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=5).read())


def post(path: str, payload: dict):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def main():
    prev = json.loads(TELEM_IN.read_text()) if TELEM_IN.exists() else {"samples": []}
    samples = prev.get("samples", [])
    print(f"Loaded {len(samples)} prior samples from {prev.get('run_id')}", flush=True)
    for s in samples[::8]:
        o = s["obs"]
        print(
            f"  [prior] t={s['t_s']:5.2f}s | {s['stage']:26s} | RPM={o['rotor_rpm'][0]:6.1f} | "
            f"P={o['engine_shaft_kw']:5.1f}kW | coll_fb={o['collective_feedback_deg'][0]:5.2f} | "
            f"gear_max={max(o['gear_compression_m']):.4f}m | clear={o['radar_clearance_m']:.3f}m",
            flush=True,
        )

    view = get("/api/view")
    run_id = view.get("run_id")
    print(f"Continuing live calibration on run_id={run_id}, active={view.get('active')}", flush=True)

    # First, check why 300 kW power limit drooped RPM at 17.1 deg collective:
    # At 1200 RPM and 17.1 deg collective, 4 rotors require ~310-335 kW shaft power!
    # Let's check what happens as collective increases from 17.2 to 18.8 deg under the 300 kW limit vs
    # equilibrium RPM, and measure liftoff & closed-loop attitude stability.
    t0_sim = float(view["observation"]["t_s"])
    start_wall = time.monotonic()

    while time.monotonic() - start_wall < 120.0:
        obs = get("/api/observe")
        if not obs.get("active") or "IMPACT" in obs.get("warning_lamps", []):
            print(f"Sortie ended or impacted at t_s={obs.get('t_s')}", flush=True)
            samples.append({"obs": obs, "stage": "ended"})
            break

        t_s = float(obs["t_s"])
        dt_stage = t_s - t0_sim
        att = obs["attitude_xyz_deg"]
        rates = obs["gyro_world_deg_s"]
        vel = obs["gnss_velocity_mps"]
        rpm = obs["rotor_rpm"]
        coll_fb = obs["collective_feedback_deg"]
        tilt_fb = obs["tilt_feedback_deg"]
        gear = obs["gear_compression_m"]
        alt = obs["radar_clearance_m"]

        roll_deg, pitch_deg, yaw_deg = att[0], att[1], att[2]
        wx_deg_s, wy_deg_s, wz_deg_s = rates[0], rates[1], rates[2]
        vx, vy, vz = vel[0], vel[1], vel[2]

        # Calibrated PD attitude + rate + horizontal velocity damping:
        # Rotor 1 (-X, +Y), Rotor 2 (-X, -Y), Rotor 3 (+X, +Y), Rotor 4 (+X, -Y)
        # +d_roll increases R1, R3 (+Y) and decreases R2, R4 (-Y) -> positive roll moment (+tau_x)
        # +d_pitch increases R1, R2 (-X) and decreases R3, R4 (+X) -> positive pitch moment (+tau_y)
        d_roll = max(-2.2, min(2.2, -0.35 * roll_deg - 0.18 * wx_deg_s))
        d_pitch = max(-2.2, min(2.2, -0.35 * pitch_deg - 0.18 * wy_deg_s))

        # Nacelle tilt damping for yaw rate + horizontal drift:
        yaw_tilt = max(-4.0, min(4.0, -0.25 * yaw_deg - 0.15 * wz_deg_s))
        vx_tilt = max(-3.0, min(3.0, -1.2 * vx))
        vy_tilt = max(-3.0, min(3.0, -1.2 * vy))

        if dt_stage < 2.0:
            stage = "6a_respool_1200rpm"
            base_coll = 14.5
            pert_roll = 0.0
            pert_pitch = 0.0
        elif dt_stage < 5.5:
            stage = "6b_liftoff_power_sweep"
            # Sweep collective from 17.2 to 18.6 deg to calibrate power-limited thrust & liftoff clearance
            frac = min(1.0, (dt_stage - 2.0) / 3.0)
            base_coll = 17.2 + 1.4 * frac
            pert_roll = 0.0
            pert_pitch = 0.0
        elif dt_stage < 7.0:
            stage = "7a_roll_doublet_calibration"
            base_coll = 17.8
            pert_roll = 0.45 if dt_stage < 6.25 else -0.45
            pert_pitch = 0.0
        elif dt_stage < 8.5:
            stage = "7b_pitch_doublet_calibration"
            base_coll = 17.8
            pert_roll = 0.0
            pert_pitch = 0.45 if dt_stage < 7.75 else -0.45
        elif dt_stage < 10.5:
            stage = "8a_damped_settle"
            frac = min(1.0, (dt_stage - 8.5) / 2.0)
            base_coll = 17.4 - 4.4 * frac
            pert_roll = 0.0
            pert_pitch = 0.0
        else:
            stage = "8b_ground_idle_hold"
            base_coll = 10.0
            pert_roll = 0.0
            pert_pitch = 0.0

        u_roll = d_roll + pert_roll
        u_pitch = d_pitch + pert_pitch

        coll = [
            round(max(0.0, min(30.0, base_coll + u_roll + u_pitch)), 2),
            round(max(0.0, min(30.0, base_coll - u_roll + u_pitch)), 2),
            round(max(0.0, min(30.0, base_coll + u_roll - u_pitch)), 2),
            round(max(0.0, min(30.0, base_coll - u_roll - u_pitch)), 2),
        ]
        tilt = [
            [round(vx_tilt, 2), round(vy_tilt - yaw_tilt, 2)],
            [round(vx_tilt, 2), round(vy_tilt + yaw_tilt, 2)],
            [round(vx_tilt, 2), round(vy_tilt - yaw_tilt, 2)],
            [round(vx_tilt, 2), round(vy_tilt + yaw_tilt, 2)],
        ]
        reason = (
            f"[{stage} t={t_s:.2f}s] base_coll={base_coll:.2f}, PD=({d_roll:+.2f},{d_pitch:+.2f}), "
            f"pert=({pert_roll:+.2f},{pert_pitch:+.2f}); RPM={rpm[0]:.1f}, P={obs['engine_shaft_kw']:.1f}kW, "
            f"clear={alt:.3f}m, gear_max={max(gear):.4f}m, att=({roll_deg:+.2f},{pitch_deg:+.2f},{yaw_deg:+.2f}) deg"
        )
        ack = post(
            "/api/action",
            {
                "authority": "colin",
                "observation_id": obs["observation_id"],
                "reason": reason,
                "engine": 1.0,
                "collective_deg": coll,
                "tilt_deg": tilt,
                "cabin_deg": [0.0, 0.0, 0.0],
                "cabin_level": False,
            },
        )
        samples.append(
            {
                "stage": stage,
                "t_s": t_s,
                "obs": obs,
                "command": {"collective_deg": coll, "tilt_deg": tilt},
                "ack": ack,
            }
        )
        TELEM_IN.write_text(json.dumps({"run_id": run_id, "samples": samples}, indent=2))
        support = sum(1 for g in gear if g > 0.002)
        print(
            f"t={t_s:5.2f}s | {stage:28s} | RPM={rpm[0]:6.1f} | P={obs['engine_shaft_kw']:5.1f}kW | "
            f"clear={alt:.3f}m (sup={support}/6) | att=({roll_deg:+5.2f},{pitch_deg:+5.2f},{yaw_deg:+5.2f}) | coll={coll}",
            flush=True,
        )
        if dt_stage >= 11.0:
            print("Completed Stage 6-8 calibration sequence.", flush=True)
            break
        time.sleep(0.8)


if __name__ == "__main__":
    main()
