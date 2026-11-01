"""Seamlessly transition active 10 m hover sortie into cruise to Mission Destination B and hold over B."""
from __future__ import annotations
import http.client
import json
import math
import time


class FastClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
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
    if not view.get("active"):
        raise RuntimeError("No active sortie found on live server")

    obs0 = view["observation"]
    run_id = view.get("run_id")
    dest = list(obs0["mission"]["destination"])
    start_xy = list(obs0["gnss_xy_m"])
    t0_sim = obs0["t_s"]

    dx_tot = dest[0] - start_xy[0]
    dy_tot = dest[1] - start_xy[1]
    dist_tot = math.hypot(dx_tot, dy_tot)
    ux = dx_tot / max(1e-6, dist_tot)
    uy = dy_tot / max(1e-6, dist_tot)

    # Cruise speed 4.0 m/s with smooth minimum-jerk / cosine velocity profile
    v_cruise = 4.0
    T_cruise = max(4.0, dist_tot / v_cruise)

    print(
        f"Active sortie {run_id}: translating from ({start_xy[0]:+.2f}, {start_xy[1]:+.2f}) "
        f"to Destination B ({dest[0]:+.1f}, {dest[1]:+.1f}), dist={dist_tot:.1f}m at ~10m altitude",
        flush=True,
    )

    # Set time_scale to 0.35 so user sees brisk, smooth real-time progress across the map & 3D view
    cli.request("POST", "/api/operator", {"authority": "colin", "time_scale": 0.35, "paused": False})

    kp_att = 0.62
    kd_rate = 0.32
    ki_att = 0.24
    kp_pos = 0.36
    kd_vel = 0.52

    trim_r2_r4 = 0.70
    trim_r3_r1 = 0.00

    int_roll = 0.0
    int_pitch = 0.0
    int_z = 0.0
    last_t_s = t0_sim
    arrived_t_s = None

    step = 0
    while True:
        view = cli.request("GET", "/api/view")
        if not view.get("active"):
            print("Sortie ended by operator.", flush=True)
            break

        obs = view["observation"]
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

        roll, pitch, yaw = att[0], att[1], att[2]
        wx, wy, wz = rates[0], rates[1], rates[2]
        vx, vy, vz = vel[0], vel[1], vel[2]

        # Smooth trajectory generator from start_xy to dest
        tau = min(1.0, max(0.0, (t_s - t0_sim) / T_cruise))
        # Smoothstep s(tau) = 3*tau^2 - 2*tau^3, ds/dtau = 6*tau*(1 - tau)
        s = tau * tau * (3.0 - 2.0 * tau)
        ds_dt = (6.0 * tau * (1.0 - tau)) / T_cruise if tau < 1.0 else 0.0

        ref_x = start_xy[0] + s * dx_tot
        ref_y = start_xy[1] + s * dy_tot
        vx_ref = ds_dt * dx_tot
        vy_ref = ds_dt * dy_tot

        dist_rem = math.hypot(dest[0] - pos[0], dest[1] - pos[1])
        v_ground = math.hypot(vx, vy)

        if dist_rem < 1.5 and v_ground < 0.6 and arrived_t_s is None:
            arrived_t_s = t_s
            print(
                f"Arrived over Destination B ({dest[0]:+.1f}, {dest[1]:+.1f}) at t_s={t_s:.2f}s! "
                f"pos=({pos[0]:+.2f}, {pos[1]:+.2f}), clear={clear:.2f}m, baro={baro:.2f}m",
                flush=True,
            )

        stage = "4_cruise_to_dest_B" if arrived_t_s is None else "5_stationkeep_over_B_10m"

        target_clear = 10.50
        int_roll = max(-1.8, min(1.8, int_roll + roll * dt))
        int_pitch = max(-1.8, min(1.8, int_pitch + pitch * dt))
        int_z = max(-1.5, min(1.5, int_z + (target_clear - clear) * dt))

        # Position + velocity tracking loop
        ex = pos[0] - ref_x
        ey = pos[1] - ref_y
        evx = vx - vx_ref
        evy = vy - vy_ref

        pitch_des = max(-4.0, min(4.0, -kp_pos * ex - kd_vel * evx))
        roll_des = max(-4.0, min(4.0, kp_pos * ey + kd_vel * evy))

        # Coordinated thrust vectoring assist (tilts fans gently in direction of desired acceleration)
        tx_vec = max(-3.5, min(3.5, -0.45 * vy_ref + 0.25 * ey + 0.20 * evy))
        ty_vec = max(-3.5, min(3.5, +0.45 * vx_ref - 0.25 * ex - 0.20 * evx))

        # Altitude hold at 10.5 m radar clearance (~10.0 m baro)
        ez = target_clear - clear
        evz = 0.0 - vz
        c_mean = 16.98 + 1.25 * ez + 1.70 * evz + 0.35 * int_z
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
            [round(tx_vec - u_yaw, 2), round(ty_vec, 2)],
            [round(tx_vec, 2), round(ty_vec - u_yaw, 2)],
            [round(tx_vec + u_yaw, 2), round(ty_vec, 2)],
            [round(tx_vec, 2), round(ty_vec + u_yaw, 2)],
        ]

        reason = (
            f"[{stage}] pos=({pos[0]:+.1f},{pos[1]:+.1f})->B({dest[0]:+.0f},{dest[1]:+.0f}) rem={dist_rem:.1f}m, "
            f"spd={v_ground:.2f}m/s, clear={clear:.2f}m, att=({roll:+.2f},{pitch:+.2f},{yaw:+.2f})deg"
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
                f"t={t_s:6.2f}s | {stage:24s} | pos=({pos[0]:+6.2f},{pos[1]:+6.2f}) | rem={dist_rem:5.2f}m | "
                f"spd={v_ground:4.2f}m/s | clear={clear:5.2f}m | baro={baro:5.2f}m | "
                f"att=({roll:+5.2f},{pitch:+5.2f},{yaw:+5.2f})",
                flush=True,
            )
        step += 1

        if arrived_t_s is not None and (t_s - arrived_t_s) >= 30.0:
            print(f"Completed 30s station-keeping over Destination B ({pos[0]:+.2f}, {pos[1]:+.2f}) at 10 m.", flush=True)
            break

        time.sleep(0.02)


if __name__ == "__main__":
    main()
