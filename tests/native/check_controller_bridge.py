"""Exercise native controller input and the shipping HTTP bridge against a stepped Phantom bench.

Run with the packaged Python runtime and pass --godot (pinned editor) and --output (fresh folder).
Only the ephemeral test receiver listens. No cockpit, simulator service or real input device is opened.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from math import isclose
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from threading import Thread


ROOT = Path(__file__).resolve().parents[2]
CONFIG = "58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3"
STAGES = (
    "combined", "release", "reverse", "disconnect", "keyboard", "key_release",
    "airbrake", "manual_collective", "deploy_wings", "stow_wings", "pods_forward", "pods_vertical", "brakes",
    "power_after_airbrake",
    "before_pause", "recovered_pause", "before_stale", "recovered_stale",
)


@contextmanager
def receiver(lab, token, records):
    from vtx.live_server import parse_action

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                assert self.path == "/api/action" and self.headers["Authorization"] == f"Bearer {token}"
                action = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert action["schema"] == "phantom-fbw-1" and action["authority"] == "manual"
                assert action["expected_run_id"] == lab.run_id
                accepted = lab.accept_action(parse_action(action))
                assert accepted["accepted"]
                for _ in range(80):
                    lab.integrate()
                assert lab.action_log[-1].get("applied") and lab.active
                truth = lab.aircraft.physical_snapshot()
                records.append(dict(
                    stage=STAGES[len(records)], action=action, accepted=accepted, t_s=truth["t_s"],
                    issued_t_s=lab.action_log[-1]["issued_t_s"],
                    held=deepcopy(truth["command"]), mixer=deepcopy(truth["fcc"]),
                    measured_rudder_deg=truth["phantom"]["rudder_deg"],
                    measured_booster_yaw_deg=truth["phantom"]["booster_vector_yaw_deg"],
                    fan_rpm=truth["phantom"]["fan_rpm"],
                    booster_thrust_n=[b["thrust_n"] for b in truth["boosters"]],
                ))
                status = 200
                response = dict(accepted, bench_truth={
                    "t_s": truth["t_s"], "command": truth["command"],
                    "phantom": {"transition_ecu": truth["phantom"]["transition_ecu"]},
                })
            except Exception as exc:
                status, response = 500, {"detail": repr(exc)}
            data = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    with HTTPServer(("127.0.0.1", 0), Handler) as http:
        thread = Thread(target=http.serve_forever)
        thread.start()
        try:
            yield http.server_port
        finally:
            http.shutdown()
            thread.join()


def check(records):
    assert len(records) == len(STAGES)
    combined, release, reverse, disconnect, keys = records[:5]
    for record, sign in ((combined, 1), (reverse, -1)):
        cmd, mixer = record["held"], record["mixer"]
        assert all(k in record["action"] for k in ("pitch", "roll", "yaw", "collective", "booster_throttle"))
        for axis in ("pitch", "roll", "yaw"):
            assert 0.1 < sign * cmd[axis] < 0.95, (axis, cmd)
        assert all(x * sign > 0 for x in mixer["attitude_cmd_deg"])
        assert sign * mixer["yaw_rate_cmd_deg_s"] > 0
        assert sign * record["measured_rudder_deg"] > 0
        assert sign * record["measured_booster_yaw_deg"] > 0
        assert min(record["fan_rpm"]) > 0 and min(record["booster_thrust_n"]) > 0
        assert 0 < cmd["collective"] < 1 and 0 < cmd["booster_throttle"][0] < 1
        assert cmd["booster_throttle"][0] == cmd["booster_throttle"][1]
    assert combined["held"]["collective"] > reverse["held"]["collective"]
    assert combined["held"]["booster_throttle"][0] > reverse["held"]["booster_throttle"][0]
    for record, previous in ((release, combined), (disconnect, reverse)):
        cmd = record["held"]
        assert all(cmd[axis] == 0 for axis in ("pitch", "roll", "yaw"))
        assert cmd["collective"] == previous["held"]["collective"]
        assert cmd["booster_throttle"] == previous["held"]["booster_throttle"]
    cmd = keys["held"]
    assert all(isclose(cmd[key], value) for key, value in (("pitch", 0.34), ("roll", -0.46), ("yaw", 0.40)))
    assert cmd["collective"] > disconnect["held"]["collective"]
    assert cmd["booster_throttle"][0] < disconnect["held"]["booster_throttle"][0]
    held = {r["stage"]: r["held"] for r in records}
    assert held["airbrake"]["airbrake"] == "on" and held["airbrake"]["stability_mode"] == "attitude_vs"
    assert held["airbrake"]["booster_throttle"] == [0, 0] and held["airbrake"]["collective"] >= 0.5
    assert held["manual_collective"]["stability_mode"] == "attitude" and held["manual_collective"]["airbrake"] == "off"
    assert held["deploy_wings"]["wing"] == "deploy" and held["deploy_wings"]["canard_fold"] == "deployed"
    assert held["stow_wings"]["wing"] == "stow" and held["stow_wings"]["canard_fold"] == "folded"
    assert held["pods_forward"]["pod_tilt_deg"] == [0] * 4 and held["pods_vertical"]["pod_tilt_deg"] == [90] * 4
    assert held["brakes"]["brake"] == [0] * 4
    assert isclose(held["power_after_airbrake"]["collective"], 0.416)
    assert held["power_after_airbrake"]["booster_throttle"] == [0.08, 0.08]
    for before, recovered in (("before_pause", "recovered_pause"), ("before_stale", "recovered_stale")):
        assert all(abs(held[before][axis]) > 0.1 and held[recovered][axis] == 0 for axis in ("pitch", "roll", "yaw"))
        assert held[recovered]["collective"] == held[before]["collective"]
        assert held[recovered]["booster_throttle"] == held[before]["booster_throttle"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    godot = args.godot.resolve(strict=True)
    os.chdir(output)
    sys.path.insert(0, str(ROOT / "src"))
    os.environ["VTX_DATA_ROOT"] = str(output / "data")
    os.environ["VTX_DEFAULT_ENVIRONMENT"] = "vaderland-33"

    from vtx.live_server import Laboratory, Mission

    lab = Laboratory(data_root=output / "data")
    lab.start(Mission(
        airframe_variant="phantom-a10d", environment="vaderland-33", authority="manual",
        departure=list(lab.world.default_departure), destination=list(lab.world.default_destination),
        departure_heading_deg=90.0, phantom={"start_configuration": "vtol"},
    ))
    try:
        identity = json.loads((lab.log_path / "aircraft_identity.json").read_text())
        assert identity["verified"] and identity["config_sha256"] == CONFIG
        project = output / "project"
        shutil.copytree(ROOT / "native", project, ignore=shutil.ignore_patterns(".godot", "__pycache__"))
        godot_env = dict(os.environ, APPDATA=str(output / "appdata"))
        command = [str(godot), "--headless", "--path", str(project)]
        with (output / "import.log").open("wb") as log:
            subprocess.run([*command, "--editor", "--import"], env=godot_env, check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=90)
        fixture = project / "controller_bridge_fixture.gd"
        shutil.copyfile(Path(__file__).with_name(fixture.name), fixture)
        records = []
        token = secrets.token_urlsafe(32)
        with receiver(lab, token, records) as port:
            result = subprocess.run(
                [*command, "--log-file", str(output / "godot.log"), "--script", str(fixture)],
                env=dict(godot_env, BENCH_PORT=str(port), BENCH_RUN=lab.run_id, BENCH_TOKEN=token),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
            )
        (output / "controller.log").write_text(result.stdout, encoding="utf-8")
        (output / "commands-and-feedback.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        result.check_returncode()
        check(records)
        dispatch = next(json.loads(line)["sample_to_post_ms"] for line in result.stdout.splitlines()
                        if line.startswith('{"sample_to_post_ms":'))
        assert len(dispatch) == len(records)
        lab.audit_file.flush()
        events = [json.loads(line) for line in (lab.log_path / "events.jsonl").read_text().splitlines()]
        applied = {e["payload"]["sequence"]: e["payload"]["applied_sim_t_s"] for e in events
                   if e["kind"] == "control_applied"}
        for record, delay in zip(records, dispatch):
            record["sample_to_post_wall_ms"] = delay
            record["solver_queue_sim_ms"] = 1000 * (applied[record["accepted"]["sequence"]] - record["issued_t_s"])
            assert 19.999 <= record["solver_queue_sim_ms"] <= 22.501
        (output / "commands-and-feedback.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"Verified {len(records)} native HTTP actions against {identity['variant']} ({CONFIG})")
    finally:
        lab.stop("Offline native controller check complete")


if __name__ == "__main__":
    main()
