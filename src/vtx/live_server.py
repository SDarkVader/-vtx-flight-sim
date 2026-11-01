"""Live observer/action boundary, independent physics clock and durable evidence.

There is no pilot policy here. Colin must read /api/observe, reason, and send
individual /api/action requests while the physical clock keeps running. Manual
controls use that same endpoint. /api/view is renderer/audit truth, NOT a sensor.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import hashlib
import gzip
import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid
import mujoco as mj
import numpy as np
from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator,ConfigDict
from ._rotation import Rotation
from .aircraft import Aircraft,DT,ROOT
from .mission_selection import MapPoint,select_mission
from .world import TestWorld

class Action(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    authority:str
    observation_id:int|None=None
    reason:str=Field(min_length=3,max_length=2000)
    engine:float=Field(ge=0,le=1)
    collective_deg:list[float]
    tilt_deg:list[list[float]]
    cabin_deg:list[float]=[0.,0.,0.]
    cabin_level:bool=False
    @field_validator('collective_deg')
    @classmethod
    def pitch(cls,v):
        if len(v)!=4 or any(not 0<=x<=30 for x in v):raise ValueError('Four collective controls, each 0–30 degrees')
        return v
    @field_validator('tilt_deg')
    @classmethod
    def tilt(cls,v):
        if len(v)!=4 or any(len(t)!=2 or math.hypot(*t)>20.000001 for t in v):raise ValueError('Four X/Y tilt commands, each with a combined magnitude no greater than 20 degrees')
        return v
    @field_validator('cabin_deg')
    @classmethod
    def cabin(cls,v):
        if len(v) not in (2,3) or any(abs(x)>15 for x in v[:2]) or (len(v)==3 and abs(v[2])>180):raise ValueError('Cabin X/Y ±15 degrees and yaw ±180 degrees')
        return v if len(v)==3 else [*v,0.]

class Mission(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    departure:list[float]
    destination:list[float]
    authority:str='manual'
    time_scale:float=Field(default=1.,ge=.01,le=1)
    stability_assist:float=Field(default=0.,ge=0,le=1,allow_inf_nan=False)
    reference_rpm:float=1200.
    gear_variant:str='baseline'
    airframe_variant:str='light'
    fuel_kg:float=Field(default=10.,ge=1.,le=110.)
    engine_power_limit_kw:float=Field(default=300.,ge=10.,le=469.8)
    label:str='user selected mission'
    @field_validator('departure','destination')
    @classmethod
    def xy(cls,v):
        if len(v)!=2:raise ValueError('Expected map X/Y')
        return v
    @field_validator('authority')
    @classmethod
    def auth(cls,v):
        if v not in ['colin','manual']:raise ValueError('Authority must be colin or manual')
        return v
    @field_validator('reference_rpm')
    @classmethod
    def rpm(cls,v):
        if v not in [800.,1200.]:raise ValueError('Only the documented 800 rpm baseline / 1200 rpm gearset proposal')
        return v
    @field_validator('gear_variant')
    @classmethod
    def gear(cls,v):
        if v not in ['baseline','critical-damping-proposal']:raise ValueError('Unknown reviewed gear model')
        return v
    @field_validator('airframe_variant')
    @classmethod
    def airframe(cls,v):
        if v not in ['baseline','light']:raise ValueError('Unknown airframe revision')
        return v


class Laboratory:
    def __init__(self):
        self.world=TestWorld();self.aircraft=Aircraft(self.world,rpm=1200.,fuel_kg=10.,engine_power_limit_kw=300.);self.aircraft.spawn(0,0,0)
        self.active=False;self.paused=False;self.time_scale=1.;self.authority='manual';self.run_id=None
        self.mission=None;self.action_log=[];self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.obs_id=0;self.last_obs=None;self.observations={};self.last_sensor_t=-1.;self.sensor_rng=np.random.default_rng(41031)
        self.audit_file=None;self.log_path=None;self.last_audit_t=-1.;self.settled_s=0.;self.left_ground=False
        self.error=None;self.clock_lag_s=0.;self.wall_started=None;self.end_summary=None;self.clock_epoch=0
        self.retry_hint=None
        self.checkpoint_path=ROOT/'pilot/live-flight-checkpoint.json'
        self.last_checkpoint_t=-1.
        self.memory_path=ROOT/'pilot/colin-memory.json'
        self.memory_path.parent.mkdir(exist_ok=True)
        if not self.memory_path.exists():self.memory_path.write_text(json.dumps(dict(schema_version=1,pilot='Colin',experience_count=0,lessons=[],aircraft_familiarity='cold start; no VTX-specific solution',stage2_accessed=False,history=[]),indent=2))
        restored=self.restore_checkpoint()
        completed=sorted((ROOT/'evidence/flights').glob('*/summary.json'))
        if completed and not restored:
            last=json.loads(completed[-1].read_text())
            meta_path=completed[-1].parent/'metadata.json'
            if meta_path.exists():
                self.retry_hint=dict(run_id=last['run_id'],mission=last['mission'],request=json.loads(meta_path.read_text())['request'])
                self.end_summary={k:v for k,v in last.items() if k!='final'}
        # If the process died without stop(), the latest metadata is still
        # enough to retry at the departure point. Never reconstruct mid-flight
        # physics from a render frame or claim the interrupted flight landed.
        unfinished=sorted(p for p in (ROOT/'evidence/flights').glob('*/metadata.json')
                          if not (p.parent/'summary.json').exists())
        if not restored and unfinished and (not completed or unfinished[-1].parent.name>completed[-1].parent.name):
            path=unfinished[-1]
            try:
                meta=json.loads(path.read_text())
                interrupted=dict(run_id=meta['run_id'],mission=meta['mission'],
                                 outcome='interrupted',authority=meta.get('operator'),
                                 reason='Server exited before the sortie ended; physical state not recoverable',
                                 previous_evidence=path.parent.name)
                (path.parent/'summary.json').write_text(json.dumps(interrupted,indent=2))
                self.retry_hint=dict(run_id=meta['run_id'],mission=meta['mission'],
                                     request=meta['request'])
                self.end_summary=interrupted
            except (ValueError,KeyError,OSError):
                pass

    def checkpoint(self, force=False):
        """Crash-consistent physics checkpoint, never a flight-control decision."""
        if not self.active or not self.run_id or not self.log_path:
            return
        p=self.aircraft
        if not force and p.data.time-self.last_checkpoint_t < .5:
            return
        d=p.data
        state=dict(schema=1,run_id=self.run_id,
                   model_xml_sha256=p.provenance['model_xml_sha256'],
                   mission=self.mission,authority=self.authority,
                   time_scale=self.time_scale,paused=self.paused,
                   physics=dict(time=float(d.time),qpos=d.qpos.tolist(),
                                qvel=d.qvel.tolist(),act=d.act.tolist(),
                                ctrl=d.ctrl.tolist(),
                                qacc_warmstart=d.qacc_warmstart.tolist()),
                   plant=dict(command=p.command,pitch=p.pitch.tolist(),
                              target_angles=p.target_angles.tolist(),
                              cabin_target=p.cabin_target.tolist(),
                              engine_spool=p.engine_spool,fuel=p.fuel.tolist(),
                              wind=p.wind.tolist(),rotors=p.rotors,
                              integrity=p.integrity.tolist(),power=p.power,
                              energy=p.energy,events=p.events,flags=list(p.flags),
                              crashed=p.crashed,max_alt=p.max_alt,
                              max_impact_n=p.max_impact_n,
                              step_count=p.step_count,last_mass_update=p.last_mass_update,
                              last_collision=p.last_collision,
                              stability_assist=p.stability_assist,
                              assisted_collective_deg=p.assisted_collective_deg,
                              experimental_assist=p._bench_apply_experimental_assist,
                              governor_integral_nm=p.governor.integral_nm,
                              governor_telemetry=p.governor.telemetry),
                   session=dict(action_log=self.action_log,
                                next_pending_action=self.next_pending_action,
                                last_command_time=self.last_command_time,
                                lease_expired=self.lease_expired,obs_id=self.obs_id,
                                settled_s=self.settled_s,left_ground=self.left_ground,
                                last_audit_t=self.last_audit_t,
                                sensor_rng_state=self.sensor_rng.bit_generator.state))
        payload=json.dumps(state,allow_nan=False,separators=(',',':'))
        target=self.checkpoint_path
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary,target)
        self.last_checkpoint_t=float(d.time)

    def restore_checkpoint(self):
        """Restore exact persisted plant state, held until explicit operator resume."""
        path=self.checkpoint_path
        if not path.exists():
            return False
        try:
            state=json.loads(path.read_text(encoding='utf-8'))
            if state['schema']!=1:
                raise ValueError('Unsupported checkpoint schema')
            run_id=state['run_id']
            evidence=ROOT/'evidence/flights'/run_id
            metadata=json.loads((evidence/'metadata.json').read_text())
            if (metadata['run_id']!=run_id or
                    (evidence/'summary.json').exists()):
                raise ValueError('Checkpoint does not identify an unfinished sortie')
            request=Mission(**metadata['request'])
            candidate=Aircraft(self.world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw)
            if candidate.provenance['model_xml_sha256']!=state['model_xml_sha256']:
                raise ValueError('Checkpoint model differs from current physics model')
            d=candidate.data
            physics=state['physics']
            for name in ('qpos','qvel','act','ctrl','qacc_warmstart'):
                arr=np.asarray(physics[name],dtype=float)
                target=getattr(d,name)
                if arr.shape!=target.shape or not np.all(np.isfinite(arr)):
                    raise ValueError('Invalid checkpoint physics array: '+name)
                target[:]=arr
            d.time=float(physics['time'])
            if not math.isfinite(d.time) or d.time<0:
                raise ValueError('Invalid checkpoint physics time')
            plant=state['plant']
            candidate.command=plant['command']
            candidate.pitch[:]=plant['pitch']
            candidate.target_angles[:]=plant['target_angles']
            candidate.cabin_target[:]=plant['cabin_target']
            candidate.engine_spool=float(plant['engine_spool'])
            candidate.fuel[:]=plant['fuel']
            candidate.wind[:]=plant['wind']
            candidate.rotors=plant['rotors']
            candidate.integrity[:]=plant['integrity']
            candidate.power=plant['power']
            candidate.energy=plant['energy']
            candidate.events=plant['events']
            candidate.flags=set(plant['flags'])
            candidate.crashed=plant['crashed']
            candidate.max_alt=plant['max_alt']
            candidate.max_impact_n=plant['max_impact_n']
            candidate.step_count=plant['step_count']
            candidate.last_mass_update=plant['last_mass_update']
            candidate.last_collision=plant['last_collision']
            candidate.stability_assist=plant['stability_assist']
            candidate.assisted_collective_deg=plant['assisted_collective_deg']
            candidate._bench_apply_experimental_assist=plant['experimental_assist']
            candidate.governor.integral_nm=plant['governor_integral_nm']
            candidate.governor.telemetry=plant['governor_telemetry']
            for i,bid in enumerate(candidate.fuel_bids):
                candidate.model.body_mass[bid]=max(float(candidate.fuel[i]),1e-9)
                candidate.model.body_inertia[bid]=(candidate.initial_fuel_inertia[i]*
                    max(float(candidate.fuel[i]/candidate.fuel_initial[i]),1e-9))
            mj.mj_setConst(candidate.model,mj.MjData(candidate.model))
            mj.mj_forward(candidate.model,d)
            session=state['session']
            self.sensor_rng.bit_generator.state=session['sensor_rng_state']
            self.aircraft=candidate
            self.run_id=run_id
            self.log_path=evidence
            self.audit_file=(evidence/'events.jsonl').open('a',encoding='utf-8')
            self.mission=state['mission']
            self.authority=state['authority']
            self.time_scale=state['time_scale']
            self.active=True
            self.paused=True
            self.wall_started=time.monotonic()
            self.action_log=session['action_log']
            self.next_pending_action=session['next_pending_action']
            for action in self.action_log[self.next_pending_action:]:
                action['cancelled']=True
            self.next_pending_action=len(self.action_log)
            self.last_command_time=session['last_command_time']
            self.lease_expired=session['lease_expired']
            self.obs_id=session['obs_id']
            self.last_obs=None
            self.observations={}
            self.last_sensor_t=-1.
            self.last_audit_t=session['last_audit_t']
            self.settled_s=session['settled_s']
            self.left_ground=session['left_ground']
            self.last_checkpoint_t=float(d.time)
            self.end_summary=None
            self.log('flight_checkpoint_restored',
                     dict(checkpoint_t_s=d.time,paused=True,
                          pending_actions_cancelled=True,
                          reason='Explicit operator resume required; physics position and velocity retained'))
            return True
        except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
            self.error='Flight checkpoint unavailable: '+str(exc)
            return False

    def log(self,kind,payload):
        if self.audit_file:
            row=dict(kind=kind,wall_utc=datetime.now(timezone.utc).isoformat(),t_s=round(float(self.aircraft.data.time),9),payload=payload)
            self.audit_file.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n');self.audit_file.flush()

    def sensor_observation(self):
        p=self.aircraft;d=p.data;m=p.model
        if self.last_obs is not None and d.time-self.last_sensor_t<.05:return self.last_obs
        self.last_sensor_t=float(d.time);self.obs_id+=1
        bid=p.bids['airframe'];q=d.xquat[bid]
        euler=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_euler('xyz',degrees=True)
        velocity=np.zeros(6);mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_BODY,bid,velocity,0)
        pos=d.xpos[bid];surface=self.world.surface_z(float(pos[0]),float(pos[1]))
        # Quantized independent instruments, not privileged accelerations, thrust,
        # inertia, future trajectory, contact manifold or optimizer state.
        noise=self.sensor_rng.normal
        obs=dict(observation_id=self.obs_id,t_s=round(float(d.time),3),
            gnss_xy_m=np.round(pos[:2]+noise(0,.015,2),2).tolist(),
            baro_m=round(float(pos[2]+noise(0,.01)),2),
            radar_clearance_m=round(float(pos[2]+1.56-.95-surface+noise(0,.005)),3),
            attitude_xyz_deg=np.round(euler+noise(0,.008,3),3).tolist(),
            gyro_world_deg_s=np.round(np.degrees(velocity[:3])+noise(0,.008,3),3).tolist(),
            gnss_velocity_mps=np.round(velocity[3:]+noise(0,.005,3),3).tolist(),
            rotor_rpm=[round(float(abs(p.joint(f'rotor{i}_spin')[1])*60/(2*math.pi)),2) for i in range(1,5)],
            shaft_torque_nm=[round(v['torque_nm'],1) for v in p.rotors],
            collective_feedback_deg=np.round(p.pitch,3).tolist(),
            stability_assist=p.stability_assist,assistance_applied=bool(p.stability_assist and p._bench_apply_experimental_assist),assisted_collective_deg=p.assisted_collective_deg,
            tilt_feedback_deg=[[round(math.degrees(p.joint(f'nacelle{i}_{a}')[0]),3) for a in 'xy'] for i in range(1,5)],
            cabin_feedback_deg=[round(math.degrees(p.joint(f'cabin_{a}')[0]),3) for a in 'xyz'],
            gear_compression_m=[round(float(p.joint(f'gear{i}_stroke')[0]),4) for i in range(1,7)],
            fuel_kg=np.round(p.fuel,4).tolist(),engine_shaft_kw=round(p.power['engine_w']/1000,2),
            warning_lamps=(['IMPACT'] if p.crashed else [])+(['COMMAND_LEASE_EXPIRED'] if self.lease_expired else [])+(['FUEL_EXHAUSTED'] if p.fuel.sum()<=.001 else []),
            configuration=dict(airframe_revision=p.ledger['revision'],reference_rpm=p.reference_rpm,gear_variant=p.gear_variant,
                               initial_fuel_kg=float(p.fuel_initial.sum())),
            scheduler_backlog_s=round(self.clock_lag_s,3),
            mission=self.mission,authority=self.authority,active=self.active,paused=self.paused,
            time_scale=self.time_scale,
            sensor_status='Provisional sensor models: GNSS/baro/IMU/shaft/angle/fuel/gear transducers; no certified sensor integration')
        self.last_obs=obs;self.observations[self.obs_id]=obs
        if len(self.observations)>3000:del self.observations[min(self.observations)]
        self.log('observation',obs)
        return obs

    def start(self,request:Mission):
        if self.active:raise HTTPException(409,'End the current sortie explicitly before a new mission')
        mission=select_mission(self.world.id,self.world.version,MapPoint(*request.departure),MapPoint(*request.destination),self.world)
        self.aircraft=Aircraft(self.world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw)
        self.aircraft.spawn(*request.departure,mission.departure_surface_z_m)
        self.aircraft.stability_assist=request.stability_assist
        self.active=True;self.paused=False;self.time_scale=request.time_scale;self.authority=request.authority
        self.run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.mission=dict(departure=request.departure,destination=request.destination,
                          departure_z_m=mission.departure_surface_z_m,destination_z_m=mission.destination_surface_z_m,
                          environment=self.world.id,environment_version=self.world.version,label=request.label)
        self.log_path=ROOT/'evidence/flights'/self.run_id;self.log_path.mkdir(parents=True)
        self.audit_file=(self.log_path/'events.jsonl').open('w')
        self.wall_started=time.monotonic();self.action_log=[];self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.last_obs=None;self.obs_id=0;self.last_sensor_t=-1.;self.last_audit_t=-1.;self.observations={}
        self.settled_s=0.;self.left_ground=False;self.error=None;self.end_summary=None
        self.sensor_rng=np.random.default_rng(self.world.seed)
        try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        except (subprocess.CalledProcessError,FileNotFoundError):
            pin=ROOT/'BUILD_COMMIT'
            commit=pin.read_text().strip() if pin.exists() else 'UNKNOWN_BUILD_COMMIT'
        meta=dict(run_id=self.run_id,mission=self.mission,operator=request.authority,request=request.model_dump(),
                  airframe=self.aircraft.provenance,software_commit=commit,
                  runtime_source_sha256=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'src/vtx').glob('*.py')))).hexdigest(),
                  learning_checkpoint_sha256=hashlib.sha256(self.memory_path.read_bytes()).hexdigest(),
                  clocks='400 Hz physics, 100 Hz aero, 20 Hz sensors; independent wall clock at displayed time scale',
                  controls='20 ms simulated transport, held targets; 5 simulated seconds lease then feather/idle; experimental rate damping is shadow-only and does not control aircraft')
        (self.log_path/'metadata.json').write_text(json.dumps(meta,indent=2))
        (self.log_path/'model.xml').write_text(self.aircraft.xml)
        (self.log_path/'pilot-before.json').write_bytes(self.memory_path.read_bytes())
        self.log('mission_start',meta)
        self.checkpoint(force=True)
        return dict(run_id=self.run_id,observation=self.sensor_observation())

    def accept_action(self,a:Action):
        if not self.active:raise HTTPException(409,'No active sortie')
        if a.authority!=self.authority:raise HTTPException(409,'This operator does not hold control authority')
        if self.authority=='colin' and a.observation_id not in self.observations:raise HTTPException(409,'Colin action requires an actual permitted observation ID')
        obs=self.observations.get(a.observation_id)
        if obs and self.aircraft.data.time-obs['t_s']>1.:raise HTTPException(409,'Observation is more than one simulated second old; observe again')
        row=dict(sequence=len(self.action_log)+1,issued_t_s=float(self.aircraft.data.time),
                 apply_t_s=float(self.aircraft.data.time)+.02,observation=obs,decision=a.reason,issued=a.model_dump())
        self.action_log.append(row);self.last_command_time=float(self.aircraft.data.time);self.lease_expired=False
        self.log('pilot_decision',row)
        return dict(accepted=True,sequence=row['sequence'],apply_t_s=row['apply_t_s'])

    def integrate(self):
        p=self.aircraft
        while self.next_pending_action<len(self.action_log):
            row=self.action_log[self.next_pending_action]
            if row.get('cancelled'):
                self.next_pending_action+=1
                continue
            if p.data.time<row['apply_t_s']:break
            self.next_pending_action+=1
            if row['issued']['authority']!=self.authority:
                row['cancelled']=True
                self.log('control_cancelled',dict(sequence=row['sequence'],reason='Control authority changed before application'))
                continue
            cmd={k:row['issued'][k] for k in p.command}
            p.set_command(cmd);row['applied']=True
            self.log('control_applied',dict(sequence=row['sequence'],requested=cmd))
        if p.data.time-self.last_command_time>5 and not self.lease_expired:
            p.set_command(dict(engine=0.,collective_deg=[0.]*4,tilt_deg=p.command['tilt_deg'],cabin_deg=p.command['cabin_deg']))
            self.lease_expired=True;self.log('command_lease_expired',dict(behavior='feather collective, engine idle; no flight rescue'))
        p.step()
        if p.data.time-self.last_audit_t>=.05:
            self.last_audit_t=float(p.data.time)
            self.log('physics_audit',p.physical_snapshot())
            self.sensor_observation()
            self.checkpoint()
            support=sum(1 for i in range(1,7) if p.joint(f'gear{i}_stroke')[0]>.002)
            if support==0 and p.data.time>1:self.left_ground=True
            dest=np.array(self.mission['destination'])
            speed=float(np.linalg.norm(p.data.qvel[:3]))
            level=float(p.data.xmat[p.bids['airframe']].reshape(3,3)[2,2])>.98
            near=float(np.linalg.norm(p.data.qpos[:2]-dest))<2.
            if self.left_ground and support>=3 and near and level and speed<.15 and not p.crashed:self.settled_s+=.05
            else:self.settled_s=0.
            if self.settled_s>=2:self.stop('supported stationary landing at destination')

    def stop(self,reason):
        if not self.active:return self.end_summary or dict(status='No active sortie')
        self.active=False;self.last_obs=None;p=self.aircraft
        self.checkpoint_path.unlink(missing_ok=True)
        outcome='landed' if self.settled_s>=2 else ('collision' if p.crashed else ('airborne attempt ended' if self.left_ground else 'no takeoff'))
        summary=dict(run_id=self.run_id,outcome=outcome,reason=reason,simulated_seconds=float(p.data.time),
                     wall_seconds=time.monotonic()-self.wall_started,decisions=len(self.action_log),
                     left_ground=self.left_ground,max_airframe_origin_altitude_m=p.max_alt,
                     max_contact_force_n=p.max_impact_n,fuel_used_kg=float((p.fuel_initial-p.fuel).sum()),
                     final=p.physical_snapshot(),mission=self.mission,
                     claim='Conditional experimental model; not validated VTX performance')
        self.log('sortie_end',summary)
        (self.log_path/'summary.json').write_text(json.dumps(summary,indent=2));self.audit_file.close();self.audit_file=None
        self.end_summary={k:v for k,v in summary.items() if k!='final'}
        self.retry_hint=dict(run_id=self.run_id,mission=self.mission,request=json.loads((self.log_path/'metadata.json').read_text())['request'])
        return self.end_summary

    def retry(self,request):
        """Explicit new sortie. Preserve the failed run and the learned state."""
        if self.active:
            if not self.aircraft.crashed:raise HTTPException(409,'Current sortie has no recorded crash; end it before starting another')
            self.stop('User requested retry after crash; failed sortie archived')
        hint=self.retry_hint
        if not hint:raise HTTPException(409,'No retained mission to retry')
        old=hint['request']
        m=Mission(departure=hint['mission']['departure'],destination=hint['mission']['destination'],
                  authority=request.get('authority','manual'),time_scale=request.get('time_scale',.1),
                  stability_assist=request.get('stability_assist',old.get('stability_assist',0.)),
                  reference_rpm=old.get('reference_rpm',800.),gear_variant=old.get('gear_variant','baseline'),
                  airframe_variant=request.get('airframe_variant','light'),
                  fuel_kg=request.get('fuel_kg',old.get('fuel_kg',60.)),
                  engine_power_limit_kw=request.get('engine_power_limit_kw',old.get('engine_power_limit_kw',469.8)),
                  label='Explicit retry of '+hint['run_id'])
        result=self.start(m)
        self.log('retry_lineage',dict(previous_run_id=hint['run_id'],checkpoint_preserved=True,new_airframe_variant=m.airframe_variant,
                                      previous_fuel_kg=old.get('fuel_kg',60.),new_fuel_kg=m.fuel_kg,
                                      previous_power_limit_kw=old.get('engine_power_limit_kw',469.8),new_power_limit_kw=m.engine_power_limit_kw))
        return result

    def view(self):
        return dict(mode='live' if self.active else 'inspection',run_id=self.run_id,authority=self.authority,
                    active=self.active,paused=self.paused,time_scale=self.time_scale,error=self.error,
                    clock_lag_s=self.clock_lag_s,observation=self.sensor_observation(),
                    rendering_truth=self.aircraft.physical_snapshot(),mission=self.mission,
                    recent_decisions=[{k:v for k,v in a.items() if k!='observation'} for a in self.action_log[-8:]],
                    end_summary=self.end_summary,retry_available=bool(self.retry_hint or self.aircraft.crashed))

lab=Laboratory()

async def physical_clock():
    last=time.monotonic();accum=0.;seen_run=None;seen_epoch=lab.clock_epoch
    while True:
        await asyncio.sleep(.005)
        now=time.monotonic();delta=now-last;last=now
        if not lab.active or lab.paused:accum=0.;continue
        if seen_epoch!=lab.clock_epoch:
            lab.log('scheduler_clock_rebase',dict(unintegrated_backlog_s=accum,time_scale=lab.time_scale,reason='Explicit operator clock change; no physical state reset'))
            seen_epoch=lab.clock_epoch;accum=0.;continue
        if seen_run!=lab.run_id:
            seen_run=lab.run_id;accum=0.;continue
        accum+=delta*lab.time_scale
        n=min(int(accum/DT),40)
        try:
            for _ in range(n):
                if lab.active:lab.integrate()
                accum-=DT
            lab.clock_lag_s=accum
        except Exception as e:
            lab.error=str(e);lab.log('solver_error',dict(error=str(e)))
            lab.stop('solver error; evidence retained')

@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(physical_clock())
    yield
    if lab.active:
        lab.checkpoint(force=True)
        if lab.audit_file:
            lab.audit_file.close();lab.audit_file=None
    task.cancel()

app=FastAPI(title='VTX live engineering laboratory',lifespan=lifespan)
@app.get('/api/world')
async def world():return lab.world.public()
@app.get('/api/observe')
async def observe():return lab.sensor_observation()
@app.get('/api/view')
async def view():return lab.view()
@app.get('/api/validate')
async def validate(x:float,y:float):
    from dataclasses import asdict
    return asdict(lab.world.validate(MapPoint(x,y),'mission'))
@app.post('/api/mission')
async def mission(request:Mission):
    try:return lab.start(request)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/action')
async def action(a:Action):
    try:return lab.accept_action(a)
    except HTTPException as e:
        lab.log('rejected_pilot_action',dict(request=a.model_dump(),reason=e.detail))
        raise
@app.post('/api/stop')
async def stop(request:dict):return lab.stop(str(request.get('reason','Operator ended sortie')))
@app.post('/api/retry')
async def retry(request:dict):
    try:return lab.retry(request)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/operator')
async def operator(request:dict):
    if 'experimental_assist_wire' in request:
        enabled=request['experimental_assist_wire']
        if not isinstance(enabled,bool):raise HTTPException(422,'Experimental assist wire requires boolean')
        lab.aircraft._bench_apply_experimental_assist=enabled
        lab.log('experimental_assist_wire_change',dict(enabled=enabled))
        lab.last_obs=None
    if 'stability_assist' in request:
        value=float(request['stability_assist'])
        if not math.isfinite(value) or not 0<=value<=1:raise HTTPException(422,'Stability assistance must be 0–1')
        lab.log('stability_assist_change',dict(before=lab.aircraft.stability_assist,after=value))
        lab.aircraft.stability_assist=value
    if 'authority' in request:
        if request['authority'] not in ['manual','colin']:raise HTTPException(422,'Unknown authority')
        if request['authority']!=lab.authority:
            for row in lab.action_log[lab.next_pending_action:]:
                if not row.get('cancelled'):
                    row['cancelled']=True
                    lab.log('control_cancelled',dict(sequence=row['sequence'],reason='Control authority changed before application'))
        lab.log('authority_change',dict(before=lab.authority,after=request['authority']));lab.authority=request['authority']
    if 'paused' in request:
        lab.paused=bool(request['paused']);lab.clock_epoch+=1;lab.log('explicit_operator_pause',dict(paused=lab.paused))
        if lab.active:lab.checkpoint(force=True)
    if 'time_scale' in request:
        value=float(request['time_scale'])
        if not .01<=value<=1 or not math.isfinite(value):raise HTTPException(422,'Time scale must be .01–1')
        lab.time_scale=value;lab.clock_epoch+=1;lab.log('clock_scale',dict(time_scale=value))
    if lab.active:lab.checkpoint(force=True)
    lab.last_obs=None  # Operator status must update even when the physical clock is paused.
    return dict(authority=lab.authority,paused=lab.paused,time_scale=lab.time_scale,stability_assist=lab.aircraft.stability_assist,experimental_assist_wire=lab.aircraft._bench_apply_experimental_assist)
@app.get('/api/memory')
async def memory():return json.loads(lab.memory_path.read_text())
@app.post('/api/lesson')
async def lesson(request:dict):
    text=str(request.get('lesson','')).strip()
    if len(text)<10 or len(text)>4000:raise HTTPException(422,'A concrete observed lesson is required')
    mem=json.loads(lab.memory_path.read_text())
    record=dict(run_id=lab.run_id,lesson=text,wall_utc=datetime.now(timezone.utc).isoformat(),basis=request.get('basis',[]))
    mem['lessons'].append(record);mem['experience_count']=len(mem['lessons']);mem['history'].append(dict(run_id=lab.run_id,checkpoint=mem['experience_count']))
    mem['aircraft_familiarity']='Explicit lessons from logged live decisions; no automatic policy or environment map'
    lab.memory_path.write_text(json.dumps(mem,indent=2));lab.log('learned_state_update',record)
    if lab.log_path:(lab.log_path/'pilot-after.json').write_bytes(lab.memory_path.read_bytes())
    return mem
@app.get('/api/runs')
async def runs():
    result=[]
    for path in sorted((ROOT/'evidence/flights').glob('*/summary.json'),reverse=True):
        s=json.loads(path.read_text());result.append({k:v for k,v in s.items() if k!='final'})
    return result
def read_replay_frames(path, limit=1200):
    """Bound replay memory while retaining the first and last physical states."""
    frames=[]; stride=1; count=0; last=None
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:
        for line in stream:
            row=json.loads(line)
            if row['kind']!='physics_audit':continue
            last=row['payload']
            if count % stride == 0:frames.append((count,last))
            count+=1
            if len(frames)>limit:
                frames=frames[::2];stride*=2
    if count and frames[-1][0]!=count-1:
        if len(frames)>=limit:frames.pop()
        frames.append((count-1,last))
    return dict(mode='POST_FLIGHT_AUDIT_ONLY',frames=[v for _,v in frames],
                total_frames=count,sampling_stride=stride,downsampled=count>len(frames))

@app.get('/api/replay/{run_id}')
async def replay(run_id:str):
    if not run_id.replace('-','').isalnum():raise HTTPException(422,'Invalid run ID')
    path=ROOT/'evidence/flights'/run_id/'events.jsonl'
    compressed=path.with_suffix('.jsonl.gz')
    if not path.exists() and not compressed.exists():raise HTTPException(404,'Run not found')
    # Large historical logs must not block the event loop and live physics.
    return await asyncio.to_thread(read_replay_frames,path if path.exists() else compressed)
@app.websocket('/ws')
async def stream(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            # Paused/inspection states do not need 20 full snapshots per second.
            await ws.send_json(lab.view());await asyncio.sleep(.25 if lab.paused or not lab.active else .1)
    except (WebSocketDisconnect,RuntimeError):pass
app.mount('/evidence',StaticFiles(directory=ROOT/'evidence'),name='evidence')
app.mount('/',StaticFiles(directory=ROOT/'public',html=True),name='frontend')
