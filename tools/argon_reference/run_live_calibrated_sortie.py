"""Execute calibrated live R6 hover & stability test sortie on http://127.0.0.1:8765."""
from __future__ import annotations
import json
import math
from pathlib import Path
import time
import urllib.request

BASE = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parents[1] / "evidence" / "argon_live_stability_calibration.json"


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
    if view.get("active"):
        post("/api/stop", {"reason": "Completed initial open-loop axis identification; starting calibrated closed-loop R6 hover run"})

    start = post(
        "/api/mission",
        {
            "departure": [0.0, 0.0],
            "destination": [-50.0, 20.0],
            "authority": "colin",
            "time_scale": 0.1,
            "stability_assist": 0.0,
            "reference_rpm": 1200.0,
            "gear_variant": "critical-damping-proposal",
            "airframe_variant": "r6",
            "fuel_kg": 10.0,
            "engine_power_limit_kw": 300.0,
            "label": "Argon R6 calibrated airborne hover, perturbation & landing test",
        },
    )
    run_id = start["run_id"]
    print(f"Started calibrated R6 live run: {run_id}", flush=True)

    kp_att = 0.58
    kd_rate = 0.30
    ki_att = 0.22
    kp_vel = 0.35
    kd_vel = 0.45
    trim_r2_r4 = 0.71
    trim_r3_r1 = 0.00

    int_roll = 0.0
    int_pitch = 0.0
    last_t_s = 0.0
    samples = []
    max_airborne_clear = 0.0
    max_airborne_att = 0.0

    start_wall = time.monotonic()
    while time.monotonic() - start_wall < 175.0:
        obs = get("/api/observe")
        if not obs.get("active") or "IMPACT" in obs.get("warning_lamps", []):
            print(f"Sortie ended at t_s={obs.get('t_s')}", flush=True)
            break

        t_s = float(obs["t_s"])
        dt = max(0.02, min(0.20, t_s - last_t_s)) if last_t_s > 0 else 0.05
        last_t_s = t_s

        att = obs["attitude_xyz_deg"]
        rates = obs["gyro_world_deg_s"]
        vel = obs["gnss_velocity_mps"]
        pos = obs["gnss_xy_m"]
        clear = float(obs["radar_clearance_m"])
        rpm = obs["rotor_rpm"]
        gear = obs["gear_compression_m"]
        support = sum(1 for g in gear if g > 0.002)

        roll, pitch, yaw = att[0], att[1], att[2]
        wx, wy, wz = rates[0], rates[1], rates[2]
        vx, vy, vz = vel[0], vel[1], vel[2]

        if t_s < 2.5:
            stage = "1_flat_pitch_spoolup"
            coll = [0.0, 0.0, 0.0, 0.0]
            tilt = [[0.0, 0.0]] * 4
            reason = f"[{stage} t={t_s:.2f}s] Spool to 1200 RPM at 0 deg pitch; RPM={rpm[0]:.1f}"
        else:
            if t_s < 7.0:
                stage = "2_trimmed_liftoff_climb"
                z_ref = 0.82 + min(0.85, (t_s - 2.5) * 0.35)
                pert_roll = 0.0
                pert_pitch = 0.0
            elif t_s < 9.0:
                stage = "3_airborne_hover_perturbation"
                z_ref = 1.65
                pert_roll = 0.35 if t_s < 8.0 else -0.35
                pert_pitch = 0.25 if 7.5 <= t_s < 8.5 else 0.0
            elif t_s < 11.0:
                stage = "4_airborne_hover_hold"
                z_ref = 1.60
                pert_roll = 0.0
                pert_pitch = 0.0
            else:
                stage = "5_controlled_landing_flare"
                z_ref = max(0.74, 1.60 - (t_s - 11.0) * 0.32)
                pert_roll = 0.0
                pert_pitch = 0.0

            z_err = z_ref - clear
            base_coll = 16.95 + 3.5 * z_err - 2.2 * vz
            base_coll = max(11.0, min(19.2, base_coll))

            roll_ref = max(-2.5, min(2.5, kp_vel * (0.0 - pos[1]) + kd_vel * (0.0 - vy)))
            pitch_ref = max(-2.5, min(2.5, -kp_vel * (0.0 - pos[0]) - kd_vel * (0.0 - vx)))

            roll_err = roll - roll_ref
            pitch_err = pitch - pitch_ref

            if support < 6:
                int_roll = max(-1.5, min(1.5, int_roll + roll_err * dt))
                int_pitch = max(-1.5, min(1.5, int_pitch + pitch_err * dt))

            u_roll = trim_r2_r4 - kp_att * roll_err - kd_rate * wx - ki_att * int_roll + pert_roll
            u_pitch = trim_r3_r1 - kp_att * pitch_err - kd_rate * wy - ki_att * int_pitch + pert_pitch

            u_roll = max(-3.5, min(3.5, u_roll))
            u_pitch = max(-3.5, min(3.5, u_pitch))

            c1 = base_coll - u_pitch
            c2 = base_coll + u_roll
            c3 = base_coll + u_pitch
            c4 = base_coll - u_roll
            coll = [
                round(max(0.0, min(30.0, c1)), 2),
                round(max(0.0, min(30.0, c2)), 2),
                round(max(0.0, min(30.0, c3)), 2),
                round(max(0.0, min(30.0, c4)), 2),
            ]

            u_yaw = max(-4.0, min(4.0, -0.8 * yaw - 0.5 * wz))
            tilt = [
                [round(-u_yaw, 2), 0.0],
                [0.0, round(-u_yaw, 2)],
                [round(u_yaw, 2), 0.0],
                [0.0, round(u_yaw, 2)],
            ]
            reason = (
                f"[{stage} t={t_s:.2f}s] z_ref={z_ref:.2f}m, clear={clear:.3f}m (sup={support}/6), "
                f"att=({roll:+.2f},{pitch:+.2f},{yaw:+.2f})deg, rates=({wx:+.2f},{wy:+.2f},{wz:+.2f})deg/s, "
                f"u_roll={u_roll:+.2f}, u_pitch={u_pitch:+.2f}, u_yaw={u_yaw:+.2f}"
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
        if support == 0:
            max_airborne_clear = max(max_airborne_clear, clear)
            max_airborne_att = max(max_airborne_att, abs(roll), abs(pitch))

        samples.append(
            {
                "stage": stage,
                "t_s": t_s,
                "support_contacts": support,
                "obs": obs,
                "command": {"collective_deg": coll, "tilt_deg": tilt},
                "ack": ack,
            }
        )
        if len(samples) % 4 == 1 or support == 0 and len(samples) % 2 == 0:
            print(
                f"t={t_s:5.2f}s | {stage:29s} | clear={clear:.3f}m (sup={support}/6) | RPM={rpm[0]:6.1f} | "
                f"pos=({pos[0]:+5.2f},{pos[1]:+5.2f}) | att=({roll:+5.2f},{pitch:+5.2f},{yaw:+5.2f}) | coll={coll}",
                flush=True,
            )

        OUT.write_text(
            json.dumps(
                {
                    "calibration_id": "ARGON-R6-LIVE-STABILITY-CALIBRATION-20261101",
                    "open_loop_identification_run_id": "20261101T223958-5d417d",
                    "calibrated_closed_loop_run_id": run_id,
                    "calibrated_parameters": {
                        "rotor_geometry_body_m": {
                            "rotor1_index0_east": [2.6, 0.0, 2.517],
                            "rotor2_index1_north": [0.0, 2.6, 2.517],
                            "rotor3_index2_west": [-2.6, 0.0, 2.517],
                            "rotor4_index3_south": [0.0, -2.6, 2.517],
                        },
                        "cg_10kg_fuel_m": [-0.0003, 0.0792, 1.4097],
                        "static_hover_trim_collective_deg": {
                            "mean_deg": 16.95,
                            "trim_r2_minus_r4_half_deg": trim_r2_r4,
                            "trim_r3_minus_r1_half_deg": trim_r3_r1,
                            "rotor_collectives_deg": [16.95, 17.66, 16.95, 16.24],
                        },
                        "gains": {
                            "kp_att_deg_per_deg": kp_att,
                            "kd_rate_deg_per_deg_s": kd_rate,
                            "ki_att_deg_per_deg_s": ki_att,
                            "kp_vel_deg_per_m": kp_vel,
                            "kd_vel_deg_per_mps": kd_vel,
                            "kp_yaw_tilt_deg_per_deg": 0.8,
                            "kd_yaw_tilt_deg_per_deg_s": 0.5,
                        },
                    },
                    "summary": {
                        "max_airborne_radar_clearance_m": round(max_airborne_clear, 3),
                        "max_airborne_roll_pitch_deg": round(max_airborne_att, 3),
                        "sample_count": len(samples),
                    },
                    "samples": samples,
                },
                indent=2,
            )
        )
        if t_s >= 14.0 and support == 6 and clear < 0.77:
            print(f"Touchdown and settled on 6 gear contacts at t_s={t_s:.2f}s!", flush=True)
            break
        time.sleep(0.45)


if __name__ == "__main__":
    main()
