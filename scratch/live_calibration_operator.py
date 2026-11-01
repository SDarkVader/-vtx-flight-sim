"""Live telemetry calibration and stability test operator on active run."""
from __future__ import annotations
import json
import math
from pathlib import Path
import time
import urllib.request

BASE = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parent / "live_calibration_telemetry.json"


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
    view = get("/api/view")
    run_id = view.get("run_id")
    print(f"Operating live calibration on run_id={run_id}", flush=True)
    samples = []

    # Calibration stages indexed by simulated time t_s (at time_scale=0.1, 12 s sim = 120 s wall)
    # Every step reads fresh /api/observe, computes calibrated trim adjustment from measured attitude/rates,
    # and issues /api/action with explicit telemetry reasoning.
    start_wall = time.monotonic()
    while time.monotonic() - start_wall < 150.0:
        obs = get("/api/observe")
        if not obs.get("active") or "IMPACT" in obs.get("warning_lamps", []):
            print(f"Sortie ended or impacted at t_s={obs.get('t_s')}", flush=True)
            samples.append({"obs": obs, "stage": "ended"})
            break

        t_s = float(obs["t_s"])
        att = obs["attitude_xyz_deg"]  # [roll_x, pitch_y, yaw_z]
        rates = obs["gyro_world_deg_s"]  # [wx, wy, wz]
        rpm = obs["rotor_rpm"]
        coll_fb = obs["collective_feedback_deg"]
        tilt_fb = obs["tilt_feedback_deg"]
        gear = obs["gear_compression_m"]
        alt = obs["radar_clearance_m"]

        # Closed-loop calibration trim around measured roll (X) and pitch (Y)
        # Rotor layout in body frame:
        # Rotor 1: (+X, +Y) front-left  | Rotor 2: (+X, -Y) front-right
        # Rotor 3: (-X, +Y) rear-left   | Rotor 4: (-X, -Y) rear-right
        # Wait: let's check rotor coordinates from Task 01:
        # Rotor 1: (-1.45, +1.50), Rotor 2: (-1.45, -1.50), Rotor 3: (+1.45, +1.50), Rotor 4: (+1.45, -1.50)
        # Roll about X (+roll = +Y side goes up, -Y side goes down):
        #   Wait: R x F for F=(0,0,T) at (x,y,z):
        #   tau_x = y * T, tau_y = -x * T
        #   So positive y (Rotors 1 & 3, y=+1.50) produces +tau_x (positive roll moment).
        #   Negative y (Rotors 2 & 4, y=-1.50) produces -tau_x (negative roll moment).
        #   Positive x (Rotors 3 & 4, x=+1.45) produces -tau_y (negative pitch moment).
        #   Negative x (Rotors 1 & 2, x=-1.45) produces +tau_y (positive pitch moment).
        roll_deg, pitch_deg, yaw_deg = att[0], att[1], att[2]
        wx_deg_s, wy_deg_s, wz_deg_s = rates[0], rates[1], rates[2]

        # Calibrated PD feedback on collective (bounded to +/- 1.5 deg) to measure closed-loop vs open-loop stability
        d_roll = -0.18 * roll_deg - 0.12 * wx_deg_s
        d_pitch = -0.18 * pitch_deg - 0.12 * wy_deg_s
        d_roll = max(-1.5, min(1.5, d_roll))
        d_pitch = max(-1.5, min(1.5, d_pitch))

        if t_s < 2.5:
            stage = "1_spool_baseline"
            base_coll = 0.0
            coll = [0.0, 0.0, 0.0, 0.0]
            tilt = [[0.0, 0.0]] * 4
            reason = (
                f"[Calib Stage 1 t={t_s:.2f}s] Spooling 1200 RPM baseline at 0 deg collective; "
                f"RPM={rpm[0]:.0f}, P={obs['engine_shaft_kw']:.1f} kW, gear_stroke={max(gear):.4f} m"
            )
        elif t_s < 4.5:
            stage = "2_collective_axis_id"
            # Step individual collectives slightly on ground to verify torque & gear unloading per rotor
            coll = [6.0, 8.0, 10.0, 12.0]
            tilt = [[1.0, -1.0], [-1.0, 1.0], [1.0, 1.0], [-1.0, -1.0]]
            reason = (
                f"[Calib Stage 2 t={t_s:.2f}s] Actuator lag & individual rotor load calibration: "
                f"cmd coll={coll} vs fb={coll_fb}, tilt_fb[0]={tilt_fb[0]}, torque={obs['shaft_torque_nm']}"
            )
        elif t_s < 6.5:
            stage = "3_ground_light_trim"
            # Bring to 15.5 deg near-liftoff ground trim and zero nacelle tilts
            base_coll = 15.5
            coll = [
                round(base_coll + d_roll + d_pitch, 2),
                round(base_coll - d_roll + d_pitch, 2),
                round(base_coll + d_roll - d_pitch, 2),
                round(base_coll - d_roll - d_pitch, 2),
            ]
            tilt = [[0.0, 0.0]] * 4
            reason = (
                f"[Calib Stage 3 t={t_s:.2f}s] Pre-liftoff ground trim at {base_coll} deg + PD ({d_roll:+.2f},{d_pitch:+.2f}); "
                f"att=({roll_deg:+.2f},{pitch_deg:+.2f},{yaw_deg:+.2f}) deg, gear={gear}"
            )
        elif t_s < 10.5:
            stage = "4_hover_liftoff_stability"
            # Smooth ramp from 16.6 to 17.2 deg collective with calibrated attitude/rate damping and yaw nacelle trim
            frac = min(1.0, (t_s - 6.5) / 2.0)
            base_coll = 16.6 + 0.5 * frac
            coll = [
                round(max(0.0, min(30.0, base_coll + d_roll + d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll - d_roll + d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll + d_roll - d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll - d_roll - d_pitch)), 2),
            ]
            # Small yaw damping via differential X-tilt on left (+Y: rotors 1,3) vs right (-Y: rotors 2,4)
            yaw_tilt = max(-3.0, min(3.0, -0.15 * yaw_deg - 0.10 * wz_deg_s))
            tilt = [
                [0.0, round(-yaw_tilt, 2)],
                [0.0, round(yaw_tilt, 2)],
                [0.0, round(-yaw_tilt, 2)],
                [0.0, round(yaw_tilt, 2)],
            ]
            reason = (
                f"[Calib Stage 4 t={t_s:.2f}s] Hover liftoff & stability test: radar={alt:.3f}m, "
                f"att=({roll_deg:+.2f},{pitch_deg:+.2f},{yaw_deg:+.2f}) deg, rates=({wx_deg_s:+.2f},{wy_deg_s:+.2f},{wz_deg_s:+.2f}) deg/s"
            )
        else:
            stage = "5_controlled_settle"
            # Controlled descent back to ground support
            base_coll = max(12.0, 16.5 - (t_s - 10.5) * 1.5)
            coll = [
                round(max(0.0, min(30.0, base_coll + d_roll + d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll - d_roll + d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll + d_roll - d_pitch)), 2),
                round(max(0.0, min(30.0, base_coll - d_roll - d_pitch)), 2),
            ]
            tilt = [[0.0, 0.0]] * 4
            reason = (
                f"[Calib Stage 5 t={t_s:.2f}s] Controlled settle: coll={base_coll:.2f} deg, radar={alt:.3f}m, "
                f"att=({roll_deg:+.2f},{pitch_deg:+.2f},{yaw_deg:+.2f}) deg"
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
        OUT.write_text(json.dumps({"run_id": run_id, "samples": samples}, indent=2))
        print(
            f"t={t_s:5.2f}s | {stage:26s} | RPM={rpm[0]:6.1f} | clear={alt:.3f}m | "
            f"att=({roll_deg:+5.2f},{pitch_deg:+5.2f},{yaw_deg:+5.2f}) | coll={coll}",
            flush=True,
        )
        if t_s >= 13.5:
            print("Completed 13.5 s simulated calibration sequence.", flush=True)
            break
        time.sleep(1.0)


if __name__ == "__main__":
    main()
