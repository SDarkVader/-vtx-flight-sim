"""Fly the currently active live sortie to 10 m altitude and hold stable hover."""
from __future__ import annotations
import http.client
import json
import math
import time


class FastClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 18767):
        self.host = host
        self.port = port
        self.conn = http.client.HTTPConnection(host, port, timeout=5)

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "Connection": "keep-alive"} if body else {"Connection": "keep-alive"}
        try:
            self.conn.request(method, path, body=body, headers=headers)
            resp = self.conn.getresponse()
            data = resp.read()
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {data.decode(errors='ignore')}")
            return json.loads(data)
        except Exception:
            self.conn.close()
            self.conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
            self.conn.request(method, path, body=body, headers=headers)
            resp = self.conn.getresponse()
            data = resp.read()
            return json.loads(data)


def main():
    cli = FastClient()
    view = cli.request("GET", "/api/view")
    if not view.get("active") or view.get("authority") != "colin" or not view.get("paused"):
        raise RuntimeError("Expected the paused Argon-controlled flight")
    cli.request("POST", "/api/operator", {"time_scale":0.5, "paused":False})
    view = cli.request("GET", "/api/view")
    run_id = view.get("run_id")
    print(f"Connected to active sortie {run_id} (current t_s={view['observation']['t_s']:.2f}s)", flush=True)

    # Set authority to colin and time_scale to 0.25 so 50 Hz loop has 200 Hz sim-rate authority and user sees smooth real-time climb
    # Mission starts under Colin authority; do not take control from the operator.

    t0_sim = view["observation"]["t_s"]
    pos0 = list(view["observation"]["gnss_xy_m"])

    # Calibrated gains for R5/R6 diamond rotor configuration (E, N, W, S)
    kp_att = 0.62
    kd_rate = 0.32
    ki_att = 0.24
    kp_vel = 0.32
    kd_vel = 0.45

    trim_r2_r4 = 0.70
    trim_r3_r1 = 0.00

    int_roll = 0.0
    int_pitch = 0.0
    int_z = 0.0
    last_t_s = t0_sim
    spool_done_t_s = t0_sim
    destination = view["observation"]["mission"]["destination"]
    origin = list(pos0)
    distance = math.hypot(destination[0]-origin[0], destination[1]-origin[1])
    unit = [(destination[i]-origin[i])/distance for i in range(2)]
    arrived_at = None
    reached_10m_t_s = None

    step = 0
    while True:
        view = cli.request("GET", "/api/view")
        if not view.get("active"):
            print("Sortie ended by operator.", flush=True)
            break

        if view.get("authority") != "colin" or view.get("paused"):
            print("Operator took control or paused; pilot exiting.", flush=True)
            break
        obs = cli.request("GET", "/api/observe")
        if "IMPACT" in obs["warning_lamps"] or max(abs(x) for x in obs["attitude_xyz_deg"][:2]) > 15:
            print("Flight test paused: attitude or impact limit", obs["attitude_xyz_deg"], obs["warning_lamps"], flush=True)
            cli.request("POST", "/api/operator", {"paused":True})
            break
        t_s = obs["t_s"]
        dt = max(0.0, min(0.1, t_s - last_t_s))
        last_t_s = t_s

        clear = obs["radar_clearance_m"]
        baro = obs["baro_m"]
        rpm = obs["rotor_rpm"]
        mean_rpm = sum(rpm) / 4.0
        att = obs["attitude_xyz_deg"]
        rates = obs["gyro_world_deg_s"]
        vel = obs["gnss_velocity_mps"]
        pos = obs["gnss_xy_m"]
        tilt_fb = obs["tilt_feedback_deg"]
        max_tilt_fb = max(math.hypot(tx, ty) for tx, ty in tilt_fb)
        gear_comp = obs["gear_compression_m"]
        sup = sum(1 for g in gear_comp if g > 0.001)

        roll, pitch, yaw = att[0], att[1], att[2]
        wx, wy, wz = rates[0], rates[1], rates[2]
        vx, vy, vz = vel[0], vel[1], vel[2]

        # Phase 1: Zero collective & zero tilt until nacelles straighten (<1 deg) and rotors reach >=1180 RPM
        if spool_done_t_s is None:
            if mean_rpm >= 1180.0 and max_tilt_fb <= 1.2:
                spool_done_t_s = t_s
                pos0 = [pos[0], pos[1]]
                print(f"Spool-up & nacelle zeroing complete at t_s={t_s:.2f}s (RPM={mean_rpm:.1f}, max_tilt={max_tilt_fb:.2f} deg)", flush=True)
            coll = [0.0, 0.0, 0.0, 0.0]
            tilt = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
            stage = "1_spoolup_and_zero_tilt"
            reason = f"[1_spoolup] Centering nacelles (max_tilt={max_tilt_fb:.1f}deg) & spooling rotors ({mean_rpm:.0f}/1200 RPM)"
        else:
            t_flight = t_s - spool_done_t_s
            # Target radar clearance: climb smoothly from 0.76 m to 10.50 m (baro ~10.0 m, clearance ~10.5 m) at 1.15 m/s
            target_clear = 9.74
            vz_ff = 0.0

            if clear >= 9.0 and reached_10m_t_s is None:
                reached_10m_t_s = t_s
                print(f"Reached 10 m altitude band at t_s={t_s:.2f}s! Holding stable 10 m hover.", flush=True)

            stage = "2_climb_to_10m" if target_clear < 9.74 else "3_hover_hold_10m"

            if clear > 0.14:
                int_roll = max(-1.8, min(1.8, int_roll + roll * dt))
                int_pitch = max(-1.8, min(1.8, int_pitch + pitch * dt))
                int_z = max(-1.2, min(1.2, int_z + (target_clear - clear) * dt))

            # Outer loop position hold around departure pad
            travel = min(distance, 0.7 * t_flight)
            pos0 = [origin[i] + unit[i] * travel for i in range(2)]
            dx = pos[0] - pos0[0]
            dy = pos[1] - pos0[1]
            pitch_des = max(-2.5, min(2.5, -kp_vel * dx - kd_vel * vx)) if clear > 0.34 else 0.0
            roll_des = max(-2.5, min(2.5, kp_vel * dy + kd_vel * vy)) if clear > 0.34 else 0.0

            # Altitude & vertical speed loop (bounded so engine power stays within 300 kW and RPM stays ~1180-1200)
            ez = target_clear - clear
            evz = vz_ff - vz
            c_mean = 16.98 + 1.15 * ez + 1.65 * evz + 0.35 * int_z
            c_mean = max(14.5, min(18.65, c_mean))

            u_roll = -kp_att * (roll - roll_des) - kd_rate * wx - ki_att * int_roll
            u_pitch = -kp_att * (pitch - pitch_des) - kd_rate * wy - ki_att * int_pitch
            u_roll = max(-3.5, min(3.5, u_roll))
            u_pitch = max(-3.5, min(3.5, u_pitch))

            c1 = c_mean - trim_r3_r1 - u_pitch
            c2 = c_mean + trim_r2_r4 + u_roll
            c3 = c_mean + trim_r3_r1 + u_pitch
            c4 = c_mean - trim_r2_r4 - u_roll

            coll = [
                round(max(0.0, min(30.0, c1)), 2),
                round(max(0.0, min(30.0, c2)), 2),
                round(max(0.0, min(30.0, c3)), 2),
                round(max(0.0, min(30.0, c4)), 2),
            ]

            u_yaw = max(-4.0, min(4.0, -0.85 * yaw - 0.55 * wz))
            tilt = [
                [round(-u_yaw, 2), 0.0],
                [0.0, round(-u_yaw, 2)],
                [round(u_yaw, 2), 0.0],
                [0.0, round(u_yaw, 2)],
            ]
            reason = (
                f"[{stage}] clear={clear:.2f}m (baro={baro:.2f}m, target={target_clear:.2f}m), "
                f"vs={vz:+.2f}m/s, att=({roll:+.2f},{pitch:+.2f},{yaw:+.2f})deg, RPM={mean_rpm:.0f}"
            )

        cli.request(
            "POST",
            "/api/action",
            {
                "authority": "colin",
                "observation_id": obs["observation_id"],
                "reason": reason,
                "engine": 1.0,
                "collective_deg": coll,
                "tilt_deg": tilt,
                "cabin_deg": [0.0, 0.0, 0.0],
                "cabin_level": True,
            },
        )

        if step % 25 == 0:
            print(
                f"t={t_s:6.2f}s | {stage:23s} | clear={clear:6.2f}m | baro={baro:5.2f}m | vs={vz:+5.2f}m/s | "
                f"RPM={mean_rpm:6.1f} | pwr={obs['engine_shaft_kw']:5.1f}kW | pos=({pos[0]:+5.2f},{pos[1]:+5.2f}) | "
                f"att=({roll:+5.2f},{pitch:+5.2f},{yaw:+5.2f})",
                flush=True,
            )
        step += 1

        remaining = math.hypot(pos[0]-destination[0], pos[1]-destination[1])
        ground_speed = math.hypot(vx, vy)
        if remaining < 2.0 and ground_speed < .35:
            if arrived_at is None: arrived_at=t_s
            if t_s-arrived_at >= 2:
                print(f"Arrived over B: distance={remaining:.2f}m, clearance={clear:.2f}m", flush=True)
                cli.request("POST", "/api/operator", {"paused":True})
                break
        else:
            arrived_at=None
        if clear < 3:
            print("Paused due to low clearance",clear,flush=True)
            cli.request("POST", "/api/operator", {"paused":True})
            break

        time.sleep(0.02)


if __name__ == "__main__":
    main()
