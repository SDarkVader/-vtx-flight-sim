"""Offline round-trip through the native gear action, pinned solver and imported Godot rig.

Run with the bundled Python, --godot pointing at the matching editor and --output
pointing at a new results directory. No cockpit, listener or physical pad is used.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CORNERS = ("FL", "FR", "RL", "RR")


def encode(value, path):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def probe_rig(godot, project, output, label, view):
    frame = output / (label + "-view.json")
    result = output / (label + "-rig.json")
    encode(view, frame)
    subprocess.run([
        godot, "--headless", "--path", project, "--script", "res://gear_rig_probe.gd",
        "--log-file", output / (label + "-godot.log"), "--", frame, result,
    ], timeout=45, check=True)
    return json.loads(result.read_text(encoding="utf-8"))


async def submit(server, body):
    from starlette.requests import Request

    async def receive():
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}

    # Call the same route handler as the bridge, in-process, with no network listener.
    return await server.action(Request({"type": "http", "method": "POST", "path": "/api/action"}, receive))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    godot = args.godot.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(output)
    os.environ.update(VTX_DATA_ROOT=str(output / "data"), VTX_DEFAULT_ENVIRONMENT="vaderland-33",
                      APPDATA=str(output / "appdata"), LOCALAPPDATA=str(output / "localappdata"))
    sys.path.insert(0, str(ROOT / "src"))
    import mujoco
    import numpy as np
    from vtx import live_server as server

    project = output / "rig-project"
    project.mkdir()
    # A script-only project has no cockpit scene or backend launcher.
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="VTX gear bench"\n')
    shutil.copytree(ROOT / "native/flight", project / "flight")
    shutil.copy2(Path(__file__).with_name("gear_rig_probe.gd"), project)
    subprocess.run([godot, "--headless", "--editor", "--import", "--path", project,
                    "--log-file", output / "rig-import.log"], timeout=120, check=True)

    lab = server.lab = server.Laboratory()
    lab.start(server.Mission(airframe_variant="phantom-a10d", environment="vaderland-33",
                             authority="manual", phantom={"start_configuration": "vtol"},
                             departure=lab.world.default_departure, destination=lab.world.default_destination,
                             departure_heading_deg=90.0, label="Offline airborne leg travel fixture"))
    try:
        aircraft = lab.aircraft
        # Unload the feet at fixture initialization. Normal gravity, contacts and actuators
        # remain enabled during both strokes. Only test commands affect the sliders.
        aircraft.data.qpos[2] += 200
        mujoco.mj_forward(aircraft.model, aircraft.data)
        rows = []
        receipts = []

        def sample(label):
            view = lab.view()
            truth = view["rendering_truth"]
            observed = view["observation"]
            assert view["active"] and observed["configuration"]["identity"]["verified"]
            assert truth["variant"] == "phantom-a10d" and view["environment"]["version"] == "33.1"
            rig = probe_rig(godot, project, output, label, view)
            measured = [float(aircraft.joint("leg_" + k)[0]) for k in CORNERS]
            compression = [float(aircraft.joint("leg_" + k + "_oleo")[0]) for k in CORNERS]
            np.testing.assert_allclose(rig["rendered_slider_plus_oleo_m"], np.add(measured, compression),
                                       atol=0.000003, rtol=0)
            rows.append(dict(stage=label, physics_t_s=truth["t_s"], sensor_t_s=observed["t_s"],
                             command_m=truth["command"]["leg_extension_m"].copy(),
                             observation_m=observed["leg_extension_m"], slider_extension_m=np.negative(measured).tolist(),
                             compression_m=compression, rendered_signed_m=rig["rendered_slider_plus_oleo_m"]))
            return rig["patch"]

        patch = sample("extended")
        for action, target in (("retract", 0.0), ("deploy", 0.52)):
            assert patch == {"leg_extension_m": [target] * 4}, (action, patch)
            ack = asyncio.run(submit(server, dict(patch, schema="phantom-fbw-1", authority="manual",
                                                  expected_run_id=lab.run_id, reason="Native landing leg bench")))
            assert ack["accepted"]
            receipts.append(ack)
            for _ in range(400):
                lab.integrate()
            sample(action + "-moving")
            moving = rows[-1]
            assert moving["command_m"] == [target] * 4
            assert all(0.15 < extension < 0.37 for extension in moving["slider_extension_m"])
            for _ in range(500):
                lab.integrate()
            patch = sample(action + "-complete")
            for field in ("observation_m", "slider_extension_m"):
                np.testing.assert_allclose(rows[-1][field], [target] * 4, atol=0.001, rtol=0)

        identity = lab.view()["observation"]["configuration"]["identity"]
        encode(dict(passed=True, variant=aircraft.variant, config_sha256=aircraft.P.config_sha256,
                    verified_identity=identity, corners=CORNERS, steps_per_second=400, receipts=receipts,
                    samples=rows), output / "gear-receipt.json")
    finally:
        lab.stop("Offline leg travel fixture finished")


if __name__ == "__main__":
    main()
