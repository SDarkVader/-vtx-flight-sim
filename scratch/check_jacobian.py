import sys
from pathlib import Path
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vtx.aircraft import Aircraft

ac = Aircraft(airframe_variant="r6", rpm=1200.0, fuel_kg=10.0)
ac.spawn(0, 0, 0)
print("Total mass (10 kg fuel):", ac.mass_properties()["mass_kg"], "kg -> Weight:", ac.mass_properties()["mass_kg"] * 9.80665, "N")
print("CG world:", np.round(ac.mass_properties()["cg_world_m"], 4).tolist())

for i in range(1, 5):
    bid = ac.bids[f"rotor{i}"]
    print(f"Rotor {i} (index {i-1}): pos={ac.data.xpos[bid].round(3).tolist()}")

omega = 1200.0 * 2 * math.pi / 60.0
for deg in [15.0, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 20.0]:
    res = ac.aero.evaluate(omega, deg, 0.0)
    p_aero_kw = 4 * res["torque_nm"] * omega / 1000.0
    p_shaft_kw = p_aero_kw / 0.95
    print(
        f"pitch={deg:4.1f} deg | T_1={res['thrust_n']:7.1f} N | 4*T={4*res['thrust_n']:8.1f} N | "
        f"Q_1={res['torque_nm']:6.1f} Nm | P_shaft={p_shaft_kw:6.1f} kW | max_alpha={res['max_alpha_deg']:5.2f} deg"
    )

# Check what nacelle{i}_x and nacelle{i}_y joint angles do to thrust vector axis:
import mujoco as mj
for i in range(1, 5):
    for jname, idx in [(f"nacelle{i}_x", 0), (f"nacelle{i}_y", 1)]:
        jid = mj.mj_name2id(ac.model, mj.mjtObj.mjOBJ_JOINT, jname)
        qadr = ac.model.jnt_qposadr[jid]
        ac.data.qpos[qadr] = math.radians(5.0)
        mj.mj_forward(ac.model, ac.data)
        axis = ac.data.xmat[ac.bids[f"rotor{i}"]].reshape(3, 3)[:, 2]
        r_vec = ac.data.xpos[ac.bids[f"rotor{i}"]] - np.array(ac.mass_properties()["cg_world_m"])
        moment_per_unit_T = np.cross(r_vec, axis)
        ac.data.qpos[qadr] = 0.0
        mj.mj_forward(ac.model, ac.data)
        print(f"{jname} = +5 deg -> thrust_axis={axis.round(4).tolist()}, (r x axis)={moment_per_unit_T.round(4).tolist()}")
