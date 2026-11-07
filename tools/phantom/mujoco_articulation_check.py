"""Load the generated A9 MJCF fragment in MuJoCo and drive every joint through its range.

Run:  python tools/phantom/mujoco_articulation_check.py
Reads:  evidence/phantom/a9_mujoco_fragment.xml, evidence/phantom/a9_handover.json
Writes: evidence/phantom/a9_mujoco_check.json

The chassis is welded to the world (gravity on, no aerodynamics): this checks that the handover
compiles, inertias are valid, joint axes/limits are consistent and the declared actuator authority
(force/torque caps, rate-ramped position targets) can move each joint under gravity. It is an
articulation check only, not a flight or structural test.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
import sys
_REV = (sys.argv[sys.argv.index("--rev") + 1] if "--rev" in sys.argv else "a9").lower()   # default A9 unchanged
FRAG = ROOT / "evidence" / "phantom" / f"{_REV}_mujoco_fragment.xml"
HAND = ROOT / "evidence" / "phantom" / f"{_REV}_handover.json"
OUT = ROOT / "evidence" / "phantom" / f"{_REV}_mujoco_check.json"

# actuator caps (N or N m) and rates (m/s or deg/s) from the handover control limits
CAPS = {
    "WING_._SLIDE": (2500.0, 0.30), "LOCK": (1500.0, 0.14), "AILERON": (72.0, 80.0), "FLAP": (60.0, 15.0),
    "CANARD_._PITCH": (420.0, 40.0), "CANARD_._FOLD": (150.0, 60.0), "HATCH": (25.0, 180.0),
}


def cap_for(name):
    import re
    for pat, v in CAPS.items():
        if re.search(pat, name):
            return v
    raise KeyError(name)


def build_model():
    frag = FRAG.read_text()
    xml = f"""<mujoco model="phantom_{_REV}_articulation_check">
  <compiler angle="degree" inertiafromgeom="false"/>
  <option timestep="0.001" gravity="0 0 -9.81" integrator="implicitfast"/>
  <worldbody>
    <body name="chassis" pos="0 0 0">
      <inertial pos="-0.3 0 0.6" mass="1100" diaginertia="600 2300 2600"/>
{frag}
    </body>
  </worldbody>
</mujoco>"""
    return mujoco.MjModel.from_xml_string(xml), xml


def main():
    hand = json.loads(HAND.read_text())
    model, xml = build_model()
    # add position actuators programmatically via a second compile with <actuator>
    names = [model.joint(i).name for i in range(model.njnt)]
    acts = []
    for n in names:
        force, _ = cap_for(n)
        jt = model.joint(n).type
        kp = 2.0e5 if jt == mujoco.mjtJoint.mjJNT_SLIDE else 2.0e3
        if "AILERON" in n or "FLAP" in n or "HATCH" in n:
            kp = 400.0
        acts.append(f'<position name="act_{n}" joint="{n}" kp="{kp}" kv="{kp * 0.05}" forcerange="{-force} {force}" forcelimited="true"/>')
    xml2 = xml.replace("</mujoco>", "  <actuator>\n    " + "\n    ".join(acts) + "\n  </actuator>\n</mujoco>")
    model = mujoco.MjModel.from_xml_string(xml2)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    total = float(sum(model.body_mass[1:]))
    results = dict(compiled=True, nbody=model.nbody, njnt=model.njnt, nu=model.nu, articulated_mass_kg=total - 1100.0,
                   chassis_placeholder_mass_kg=1100.0, joints={})
    for n in names:
        jid = model.joint(n).id
        aid = model.actuator(f"act_{n}").id
        lo, hi = model.jnt_range[jid]
        force, rate = cap_for(n)
        is_slide = model.joint(n).type == mujoco.mjtJoint.mjJNT_SLIDE
        rate_si = rate if is_slide else math.radians(rate)
        rec = dict(range=[float(lo), float(hi)], units="m" if is_slide else "rad", cap=force, rate=rate)
        for tag, target in (("to_hi", hi), ("to_lo", lo)):
            mujoco.mj_resetData(model, data)
            mujoco.mj_forward(model, data)
            q0 = float(data.qpos[model.jnt_qposadr[jid]])
            T = abs(target - q0) / rate_si + 1.5
            steps = int(T / model.opt.timestep)
            peak, t95 = 0.0, None
            for k in range(steps):
                t = k * model.opt.timestep
                cmd = q0 + np.clip(t * rate_si, 0, abs(target - q0)) * np.sign(target - q0)
                data.ctrl[aid] = cmd
                mujoco.mj_step(model, data)
                peak = max(peak, abs(float(data.actuator_force[aid])))
                q = float(data.qpos[model.jnt_qposadr[jid]])
                if t95 is None and abs(target - q0) > 0 and abs(q - q0) >= 0.95 * abs(target - q0):
                    t95 = t
            q_end = float(data.qpos[model.jnt_qposadr[jid]])
            rec[tag] = dict(target=float(target), achieved=q_end, error=q_end - float(target), t95_s=t95,
                            peak_actuator_force=peak, saturated=peak >= 0.999 * force)
        results["joints"][n] = rec
    ok = all(abs(r["to_hi"]["error"]) < 0.02 * max(1e-3, r["range"][1] - r["range"][0]) + 1e-3 and
             abs(r["to_lo"]["error"]) < 0.02 * max(1e-3, r["range"][1] - r["range"][0]) + 1e-3 for r in results["joints"].values())
    results["all_joints_reach_both_limits"] = ok
    OUT.write_text(json.dumps(results, indent=1))
    print(f"compiled: {model.nbody} bodies, {model.njnt} joints, {model.nu} actuators; articulated mass {results['articulated_mass_kg']:.1f} kg")
    for n, r in results["joints"].items():
        u = r["units"]
        f = (lambda v: f"{v:.3f}") if u == "m" else (lambda v: f"{math.degrees(v):.1f}")
        print(f"  {n:34s} range [{f(r['range'][0])}, {f(r['range'][1])}] {('m' if u == 'm' else 'deg')}: "
              f"hi {f(r['to_hi']['achieved'])} lo {f(r['to_lo']['achieved'])}  peak {max(r['to_hi']['peak_actuator_force'], r['to_lo']['peak_actuator_force']):.1f}"
              f"/{r['cap']:.0f}  t95 {r['to_hi']['t95_s']}")
    print("ALL_JOINTS_REACH_BOTH_LIMITS", ok)


if __name__ == "__main__":
    main()
