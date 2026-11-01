"""Tests the live link without moving the MuJoCo aircraft or calling the LAN API."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.persistent_pilot import DEFAULT, Pilot, load_config


class FakeServer:
    def __init__(self):
        self.run="run-a"
        self.authority="colin"
        self.active=True
        self.paused=False
        self.crashed=False
        self.actions=[]
        self.operators=[]
        self.retry_calls=[]
        self.end_summary=None
        self.obs=dict(observation_id=1,t_s=0,attitude_xyz_deg=[0,0,0],
                      gyro_world_deg_s=[0,0,0],warning_lamps=[],
                      assistance_applied=False)
    def __call__(self, base, path, payload=None):
        if path=="/api/view":
            return dict(run_id=self.run,active=self.active,paused=self.paused,
                        authority=self.authority,rendering_truth=dict(crashed=self.crashed),
                        observation=self.obs,end_summary=self.end_summary)
        if path=="/api/observe":
            self.obs["observation_id"]+=1
            return dict(self.obs)
        if path=="/api/operator":
            self.operators.append(payload)
            self.obs["assistance_applied"]=bool(payload["experimental_assist_wire"])
            return dict(experimental_assist_wire=payload["experimental_assist_wire"],
                        stability_assist=payload["stability_assist"])
        if path=="/api/action":
            self.actions.append(payload)
            return dict(accepted=True,sequence=len(self.actions))
        if path=="/api/retry":
            self.retry_calls.append(payload)
            self.run="run-b"
            self.active=True
            self.authority="colin"
            self.crashed=False
            return dict(run_id=self.run)
        raise AssertionError(path)


def test_link_requires_session_binding_and_no_cabin_level():
    with TemporaryDirectory() as tmp:
        directory=Path(tmp)
        controls=directory/"controls.json"
        cfg=dict(DEFAULT,armed=True,arm_run_id="wrong-run",serial=1,
                 engine=0.4,reason="Forty percent ground spool")
        controls.write_text(json.dumps(cfg))
        pilot=Pilot(controls=controls,status=directory/"status.json",
                    events=directory/"events.jsonl")
        fake=FakeServer()
        with patch("tools.persistent_pilot.request",side_effect=fake):
            pilot.tick(now=100)
            assert fake.actions[-1]["engine"]==0
            assert fake.actions[-1]["cabin_level"] is False
            cfg["arm_run_id"]="run-a"
            controls.write_text(json.dumps(cfg))
            pilot.tick(now=101)
            assert fake.actions[-1]["engine"]==0.4
            assert fake.actions[-1]["cabin_level"] is False


def test_crash_retries_disarmed_and_keeps_lineage():
    with TemporaryDirectory() as tmp:
        directory=Path(tmp)
        controls=directory/"controls.json"
        cfg=dict(DEFAULT,armed=True,arm_run_id="run-a",serial=3,
                 engine=0.4,reason="Initial test spool")
        controls.write_text(json.dumps(cfg))
        pilot=Pilot(controls=controls,status=directory/"status.json",
                    events=directory/"events.jsonl")
        fake=FakeServer()
        with patch("tools.persistent_pilot.request",side_effect=fake):
            pilot.tick(now=100)
            assert fake.actions[-1]["engine"]==0.4
            fake.crashed=True
            pilot.tick(now=105)
            assert fake.retry_calls[0]["authority"]=="colin"
            assert fake.retry_calls[0]["stability_assist"]==1
            pilot.tick(now=106)
            assert fake.actions[-1]["engine"]==0
            assert fake.actions[-1]["cabin_level"] is False
            assert len(fake.operators)==2


def test_manual_pause_and_guard_disallow_control():
    with TemporaryDirectory() as tmp:
        directory=Path(tmp)
        controls=directory/"controls.json"
        cfg=dict(DEFAULT,armed=True,arm_run_id="run-a",serial=4,
                 engine=0.7,reason="Testing engine")
        controls.write_text(json.dumps(cfg))
        pilot=Pilot(controls=controls,status=directory/"status.json",
                    events=directory/"events.jsonl")
        fake=FakeServer()
        with patch("tools.persistent_pilot.request",side_effect=fake):
            fake.authority="manual"
            pilot.tick(now=100)
            assert fake.actions==[]
            fake.authority="colin"
            fake.paused=True
            pilot.tick(now=101)
            assert fake.actions==[]
            fake.paused=False
            fake.obs["gyro_world_deg_s"]=[20,0,0]
            pilot.tick(now=102)
            assert fake.actions[-1]["engine"]==0
            fake.obs["gyro_world_deg_s"]=[0,0,0]
            pilot.tick(now=103)
            assert fake.actions[-1]["engine"]==0  # latched until new serial
            cfg["serial"]=5
            controls.write_text(json.dumps(cfg))
            pilot.tick(now=104)
            assert fake.actions[-1]["engine"]==0.7


def test_rejects_cabin_level_and_excessive_tilt():
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/"controls.json"
        cfg=dict(DEFAULT,cabin_level=True)
        path.write_text(json.dumps(cfg))
        try:
            load_config(path)
            assert False
        except ValueError:
            pass
        cfg["cabin_level"]=False
        cfg["tilt_deg"]=[[20,20],[0,0],[0,0],[0,0]]
        path.write_text(json.dumps(cfg))
        try:
            load_config(path)
            assert False
        except ValueError:
            pass


def test_interrupted_colin_sortie_restarts_from_metadata_not_airborne_state():
    with TemporaryDirectory() as tmp:
        directory=Path(tmp)
        controls=directory/"controls.json"
        controls.write_text(json.dumps(DEFAULT))
        pilot=Pilot(controls=controls,status=directory/"status.json",
                    events=directory/"events.jsonl")
        fake=FakeServer()
        fake.active=False
        fake.run=None
        fake.authority="manual"  # A freshly restarted server defaults to manual.
        fake.end_summary=dict(outcome="interrupted",authority="colin",run_id="lost-run")
        with patch("tools.persistent_pilot.request",side_effect=fake):
            pilot.tick(now=100)
            assert len(fake.retry_calls)==1
            assert fake.retry_calls[0]["authority"]=="colin"
            pilot.tick(now=101)
            assert fake.actions[-1]["engine"]==0
            assert fake.actions[-1]["cabin_level"] is False


def test_does_not_recover_interrupted_manual_sortie():
    with TemporaryDirectory() as tmp:
        directory=Path(tmp)
        controls=directory/"controls.json"
        controls.write_text(json.dumps(DEFAULT))
        pilot=Pilot(controls=controls,status=directory/"status.json",
                    events=directory/"events.jsonl")
        fake=FakeServer()
        fake.active=False
        fake.run=None
        fake.authority="manual"
        fake.end_summary=dict(outcome="interrupted",authority="manual")
        with patch("tools.persistent_pilot.request",side_effect=fake):
            pilot.tick(now=100)
            assert fake.retry_calls==[]
