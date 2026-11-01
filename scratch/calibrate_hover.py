import sys
from pathlib import Path
import math
import numpy as np
import mujoco as mj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vtx.aircraft import Aircraft, DT
from vtx._rotation import Rotation


def run_sim(kp_att, kd_rate, kp_vel, kd_vel, ki_att=0.2, trim_r2_r4=0.71, trim_r3_r1=0.0):
    ac = Aircraft(None, "critical-damping-proposal", 1200.0, fuel_kg=10.0, airframe_variant="r6")
    ac.spawn(0, 0, 0)

    int_roll = 0.0
    int_pitch = 0.0
    max_alt = 0.0
    max_att = 0.0

    # Simulate 20 Hz sensor/control loop (every 20 physics steps = 0.05 s)
    for step in range(4000):  # 10.0 simulated seconds
        t_s = ac.data.time
        if step % 20 == 0:
            bid = ac.bids["airframe"]
            q = ac.data.xquat[bid]
            euler = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_euler("xyz", degrees=True)
            vel = np.zeros(6)
            mj.mj_objectVelocity(ac.model, ac.data, mj.mjtObj.mjOBJ_BODY, bid, vel, 0)
            rates = np.degrees(vel[:3])
            v_xyz = vel[3:]
            pos = ac.data.xpos[bid]
            clear = float(pos[2] + 1.56 - 0.95)
            rpm = abs(ac.joint("rotor1_spin")[1]) * 60.0 / (2 * math.pi)
            support = sum(1 for i in range(1, 7) if ac.joint(f"gear{i}_stroke")[0] > 0.002)

            roll, pitch, yaw = euler
            wx, wy, wz = rates
            vx, vy, vz = v_xyz

            if t_s < 2.5:
                # Stage 1: Spool to 1200 RPM with blades flat (0 deg) so no ground-contact tip-over moment builds during spool-up
                coll = [0.0, 0.0, 0.0, 0.0]
                tilt = [[0.0, 0.0]] * 4
            else:
                # Stage 2: Smoothly ramp collective to target altitude z_ref = 1.60 m (radar clearance)
                z_ref = 0.82 + min(0.80, (t_s - 2.5) * 0.35)
                if t_s > 7.5:
                    z_ref = max(0.76, 1.62 - (t_s - 7.5) * 0.40)

                z_err = z_ref - clear
                base_coll = 16.95 + 3.5 * z_err - 2.2 * vz
                base_coll = max(12.0, min(19.2, base_coll))

                # Desired roll/pitch from horizontal position/velocity hold around (0,0)
                # Note: +pitch (nose up around Y) tilts thrust toward -X; -pitch tilts thrust toward +X
                # +roll (around X) tilts thrust toward -Y; -roll tilts thrust toward +Y
                roll_ref = max(-3.0, min(3.0, kp_vel * (0.0 - pos[1]) + kd_vel * (0.0 - vy)))
                pitch_ref = max(-3.0, min(3.0, -kp_vel * (0.0 - pos[0]) - kd_vel * (0.0 - vx)))

                roll_err = roll - roll_ref
                pitch_err = pitch - pitch_ref

                if support < 6:
                    int_roll = max(-1.5, min(1.5, int_roll + roll_err * 0.05))
                    int_pitch = max(-1.5, min(1.5, int_pitch + pitch_err * 0.05))

                # u_roll > 0 means we want +tau_x (increase Rotor 2 at +Y, decrease Rotor 4 at -Y)
                u_roll = trim_r2_r4 - kp_att * roll_err - kd_rate * wx - ki_att * int_roll
                # u_pitch > 0 means we want +tau_y (increase Rotor 3 at -X, decrease Rotor 1 at +X)
                u_pitch = trim_r3_r1 - kp_att * pitch_err - kd_rate * wy - ki_att * int_pitch

                u_roll = max(-3.5, min(3.5, u_roll))
                u_pitch = max(-3.5, min(3.5, u_pitch))

                # Rotor 0 = R1 (+X), Rotor 1 = R2 (+Y), Rotor 2 = R3 (-X), Rotor 3 = R4 (-Y)
                c1 = base_coll - u_pitch
                c2 = base_coll + u_roll
                c3 = base_coll + u_pitch
                c4 = base_coll - u_roll
                coll = [
                    round(max(0.0, min(30.0, c1)), 3),
                    round(max(0.0, min(30.0, c2)), 3),
                    round(max(0.0, min(30.0, c3)), 3),
                    round(max(0.0, min(30.0, c4)), 3),
                ]

                # Yaw damping via tangential nacelle tilts:
                # From check_jacobian: +tau_z produced by (-nacelle1_x, -nacelle2_y, +nacelle3_x, +nacelle4_y)
                u_yaw = max(-4.0, min(4.0, -0.8 * yaw - 0.5 * wz))
                tilt = [
                    [round(-u_yaw, 2), 0.0],
                    [0.0, round(-u_yaw, 2)],
                    [round(u_yaw, 2), 0.0],
                    [0.0, round(u_yaw, 2)],
                ]

            ac.set_command(
                {
                    "engine": 1.0,
                    "collective_deg": coll,
                    "tilt_deg": tilt,
                    "cabin_deg": [0.0, 0.0, 0.0],
                    "cabin_level": False,
                }
            )
            if step % 200 == 0:
                print(
                    f"t={t_s:4.2f}s | clear={clear:.3f}m (sup={support}/6) | RPM={rpm:6.1f} | "
                    f"pos=({pos[0]:+5.2f},{pos[1]:+5.2f}) | att=({roll:+5.2f},{pitch:+5.2f},{yaw:+5.2f}) | "
                    f"rates=({wx:+5.2f},{wy:+5.2f},{wz:+5.2f}) | coll={coll}"
                )
            if support == 0:
                max_alt = max(max_alt, clear)
                max_att = max(max_att, abs(roll), abs(pitch))
        ac.step()
        if ac.crashed:
            print(f"CRASHED at t={ac.data.time:.3f}s")
            break
    print(f"Summary: max_airborne_clear={max_alt:.3f}m, max_airborne_att={max_att:.3f} deg, crashed={ac.crashed}")


if __name__ == "__main__":
    run_sim(kp_att=0.55, kd_rate=0.28, kp_vel=0.0, kd_vel=0.0)
