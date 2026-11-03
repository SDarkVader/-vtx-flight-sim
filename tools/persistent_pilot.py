"""Persistent, run-aware VTX pilot link. Never invents flight setpoints.

Pilot commands come exclusively from tools/pilot_controls.json, bound to a run
and serial. Retries start DISARMED and preserve the simulator's flight evidence.
The /api/view endpoint is used only for session/crash status; flight controls
depend on /api/observe. Cabin level control defaults on and remains configurable.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__:
    from .argon_calibration import from_instrument_observation
else:
    from argon_calibration import from_instrument_observation

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "tools" / "pilot_controls.json"
STATUS = Path(os.environ.get("LOCALAPPDATA", str(ROOT / "pilot"))) / "VTX" / "r6-live" / "pilot_status.json"
EVENTS = STATUS.with_name("pilot_events.jsonl")
BASE = "http://192.168.55.121:8765"
SAFE = dict(engine=0.0, collective_deg=[0.0]*4,
            tilt_deg=[[0.0,0.0] for _ in range(4)],
            cabin_deg=[0.0,0.0,0.0], cabin_level=True)
DEFAULT = dict(enabled=True, auto_retry=True, max_auto_retries=5,
               retry_cooldown_s=3.0, time_scale=0.05,
               stability_assist=1.0, experimental_assist_wire=True,
               armed=False, arm_run_id="", serial=0, reason="Ground idle",
               max_attitude_deg=12.0, max_rate_deg_s=15.0, **SAFE)


def load_config(path=CONTROLS):
    if not path.exists():
        raise FileNotFoundError("Missing pilot controls: " + str(path))
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("Pilot control file must contain an object")
    for k in DEFAULT:
        if k not in cfg:
            raise ValueError("Missing pilot field: " + k)
    if type(cfg["armed"]) is not bool or type(cfg["enabled"]) is not bool:
        raise ValueError("Pilot armed/enabled must be boolean")
    if type(cfg["auto_retry"]) is not bool or type(cfg["experimental_assist_wire"]) is not bool:
        raise ValueError("Retry and experimental wire must be boolean")
    if type(cfg["serial"]) is not int or cfg["serial"] < 0:
        raise ValueError("Serial must be a nonnegative integer")
    if not isinstance(cfg["arm_run_id"], str):
        raise ValueError("arm_run_id must be a string")
    def number(v, lower, upper):
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not lower<=v<=upper:
            raise ValueError("Invalid numeric control or guard")
        return float(v)
    number(cfg["engine"],0,1)
    for v in cfg["collective_deg"]:
        number(v,0,30)
    if len(cfg["collective_deg"]) != 4:
        raise ValueError("Exactly four collectives required")
    if len(cfg["tilt_deg"]) != 4 or any(len(t)!=2 for t in cfg["tilt_deg"]):
        raise ValueError("Exactly four paired nacelle tilts required")
    for t in cfg["tilt_deg"]:
        for v in t: number(v,-20,20)
        if math.hypot(*t)>20: raise ValueError("Nacelle vector exceeds 20 degrees")
    if len(cfg["cabin_deg"])!=3: raise ValueError("Three cabin angles required")
    for i,v in enumerate(cfg["cabin_deg"]):
        number(v,-180 if i==2 else -15,180 if i==2 else 15)
    number(cfg["stability_assist"],0,1)
    number(cfg["time_scale"],0.01,1)
    number(cfg["max_attitude_deg"],1,90)
    number(cfg["max_rate_deg_s"],1,360)
    number(cfg["retry_cooldown_s"],0.1,600)
    if type(cfg["max_auto_retries"]) is not int or not 0<=cfg["max_auto_retries"]<=100:
        raise ValueError("Retry limit must be integer 0..100")
    if not isinstance(cfg["reason"],str) or not 3<=len(cfg["reason"])<=2000:
        raise ValueError("Reason must contain 3..2000 characters")
    if type(cfg.get("cabin_level")) is not bool:
        raise ValueError("Cabin leveling must be boolean")
    return cfg


def request(base, path, payload=None):
    body=None if payload is None else json.dumps(payload,allow_nan=False).encode()
    headers={"Content-Type":"application/json"}
    # The existing PC/LAN path remains unchanged. Cloud use is explicit and
    # the token is never put in a URL or the pilot controls file.
    token=os.environ.get("VTX_CLOUD_ACCESS_TOKEN")
    if token:
        if not base.startswith("https://"):
            raise ValueError("Cloud token requires an HTTPS simulator URL")
        headers["Authorization"]="Bearer "+token
    req=Request(base+path, data=body, headers=headers)
    with urlopen(req,timeout=4) as response:
        return json.load(response)


class Pilot:
    def __init__(self, base=BASE, controls=CONTROLS, status=STATUS, events=EVENTS):
        self.base=base
        self.controls=controls
        self.status=status
        self.events=events
        self.run_id=None
        self.settings_run=None
        self.last_sent=0.0
        self.last_report=0.0
        self.last_retry=0.0
        self.retries=0
        self.expected_retry_run=None
        self.blocked_serial=None
        self.last_state=None
        self.connected=False
        self.calibration=None
        self.calibration_error="Not verified against live aircraft revision and fuel state"

    def event(self, kind, **details):
        row={"utc":datetime.now(timezone.utc).isoformat(),"kind":kind, **details}
        self.events.parent.mkdir(parents=True,exist_ok=True)
        with self.events.open("a",encoding="utf-8") as f:
            f.write(json.dumps(row,allow_nan=False)+"\n")
        if kind not in ("telemetry","pilot_action"):
            print(kind,details,flush=True)

    def status_update(self, **details):
        self.status.parent.mkdir(parents=True,exist_ok=True)
        body={"utc":datetime.now(timezone.utc).isoformat(),"run_id":self.run_id,
              "retries":self.retries, **details}
        temp=self.status.with_suffix(".tmp")
        temp.write_text(json.dumps(body,indent=2,allow_nan=False),encoding="utf-8")
        temp.replace(self.status)

    def refresh_calibration(self, observation):
        """Expose Argon's measured/estimated R6 reference from permitted instruments."""
        try:
            self.calibration=from_instrument_observation(observation)
            self.calibration_error=None
        except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            self.calibration=None
            self.calibration_error=str(exc)

    def tick(self, now=None):
        now=time.monotonic() if now is None else now
        cfg=load_config(self.controls)
        if not cfg["enabled"]:
            self.status_update(state="disabled",calibration=self.calibration,calibration_error=self.calibration_error)
            return
        view=request(self.base,"/api/view")
        if not self.connected:
            self.connected=True
            self.event("server_connected",run_id=view.get("run_id"))
        run=view.get("run_id")
        if run!=self.run_id:
            self.event("session_changed",previous=self.run_id,new=run)
            if run and run!=self.expected_retry_run:
                self.retries=0  # A separately initiated mission starts a fresh retry budget.
            self.expected_retry_run=None
            self.run_id=run
            self.settings_run=None
            self.blocked_serial=None
            self.last_sent=0
        crashed=bool(view.get("rendering_truth",{}).get("crashed") or
                     "IMPACT" in view.get("observation",{}).get("warning_lamps",[]))
        outcome=(view.get("end_summary") or {}).get("outcome")
        if crashed or (not view.get("active") and outcome in ("collision","interrupted")):
            self.status_update(state="interrupted" if outcome=="interrupted" else "crashed",crashed=crashed,authority=view.get("authority"))
            if not cfg["auto_retry"] or self.retries>=cfg["max_auto_retries"]:
                if self.retries>=cfg["max_auto_retries"] and self.last_state!="retry_limit":
                    self.event("retry_limit",limit=cfg["max_auto_retries"])
                    self.last_state="retry_limit"
                return
            if now-self.last_retry < cfg["retry_cooldown_s"]:
                return
            # Server restarts default to manual; only recover sorties whose
            # retained metadata proves Colin previously held authority.
            if outcome=="interrupted":
                if (view.get("end_summary") or {}).get("authority")!="colin":return
            elif view.get("authority")!="colin":
                return
            self.last_retry=now
            result=request(self.base,"/api/retry",{"authority":"colin",
                     "time_scale":cfg["time_scale"],"stability_assist":cfg["stability_assist"]})
            self.retries+=1
            self.expected_retry_run=result["run_id"]
            self.event("auto_retry",previous=run,new=result["run_id"],attempt=self.retries)
            self.run_id=None  # The next tick must detect a fresh run, disarmed.
            return
        if not view.get("active"):
            self.status_update(state="inactive",authority=view.get("authority"))
            return
        if view.get("authority")!="colin":
            if cfg["armed"]:
                self.blocked_serial=cfg["serial"]  # Never resume an old command after manual takeover.
            self.status_update(state="manual_authority",authority=view.get("authority"))
            if self.last_state!="manual_authority":
                self.event("manual_authority",run_id=run)
                self.last_state="manual_authority"
            return
        if view.get("paused"):
            # Read-only instrument inspection is permitted while flight remains paused.
            self.refresh_calibration(request(self.base,"/api/observe"))
            self.status_update(state="paused",authority="colin",calibration=self.calibration,calibration_error=self.calibration_error)
            return
        if self.settings_run!=run and cfg["armed"] and cfg["arm_run_id"]==run:
            result=request(self.base,"/api/operator",{
                "experimental_assist_wire":cfg["experimental_assist_wire"],
                "stability_assist":cfg["stability_assist"]})
            self.event("assistance_config",run_id=run,
                       enabled=result["experimental_assist_wire"],
                       level=result["stability_assist"])
            self.settings_run=run
        # Only this permitted sensor packet may support control decisions.
        obs=request(self.base,"/api/observe")
        self.refresh_calibration(obs)
        attitude=obs.get("attitude_xyz_deg",[0,0,0])
        rates=obs.get("gyro_world_deg_s",[0,0,0])
        guard=(max(abs(attitude[0]),abs(attitude[1]))>cfg["max_attitude_deg"] or
               max(abs(r) for r in rates)>cfg["max_rate_deg_s"] or
               "IMPACT" in obs.get("warning_lamps",[]))
        matched=bool(cfg["armed"] and cfg["arm_run_id"]==run and cfg["serial"]>0)
        if guard and matched and self.blocked_serial!=cfg["serial"]:
            self.blocked_serial=cfg["serial"]
            self.event("guard_triggered",run_id=run,serial=cfg["serial"],
                       attitude=attitude,rates=rates)
        armed=matched and self.blocked_serial!=cfg["serial"] and not guard
        setpoints={k:cfg[k] for k in SAFE} if armed else dict(SAFE)
        if armed and now-self.last_sent>=0.55:
            action={**setpoints,"authority":"colin","observation_id":obs["observation_id"],
                    "reason":cfg["reason"] if armed else "Persistent pilot safe idle / disarmed heartbeat"}
            ack=request(self.base,"/api/action",action)
            self.last_sent=now
            self.event("pilot_action",run_id=run,serial=cfg["serial"] if armed else 0,
                       armed=armed,sequence=ack["sequence"],observation_id=obs["observation_id"],
                       setpoints=setpoints)
        if now-self.last_report>=2:
            self.event("telemetry",run_id=run,obs=obs,armed=armed)
            self.last_report=now
        state="armed" if armed else ("guarded" if guard else "idle")
        self.status_update(state=state,authority="colin",armed=armed,
                           control_serial=cfg["serial"],assistance_applied=obs.get("assistance_applied"),
                           observation=obs,calibration=self.calibration,
                           calibration_error=self.calibration_error)
        self.last_state=state


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base",default=BASE)
    parser.add_argument("--once",action="store_true",help="Single monitoring step")
    args=parser.parse_args()
    pilot=Pilot(base=args.base)
    print("VTX PERSISTENT PILOT",args.base,"disarmed unless explicitly authorized",flush=True)
    while True:
        try:
            pilot.tick()
        except KeyboardInterrupt:
            pilot.event("pilot_stopped",reason="Keyboard interrupt")
            break
        except (URLError,HTTPError,OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
            if pilot.connected:
                pilot.event("link_error",error=str(exc))
            pilot.connected=False
            pilot.status_update(state="link_error",error=str(exc))
        if args.once:break
        time.sleep(0.5)


if __name__=="__main__":
    main()
