"""Live observer/action boundary, independent physics clock and durable evidence.

There is no pilot policy here. Colin must read /api/observe, reason, and send
individual /api/action requests while the physical clock keeps running. Manual
controls use that same endpoint. /api/view is renderer/audit truth, NOT a sensor.
"""
from __future__ import annotations
import asyncio
import copy
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import hashlib
import hmac
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
from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect,Request
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator,ConfigDict
from ._rotation import Rotation
from .aircraft import Aircraft,DT,ROOT
from .mission_selection import MapPoint,select_mission
from .world import TestWorld
from .r6_hold import R6HoldController
from .phantom import live as phantom_live
from .phantom.controls import PhantomAction
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from .release import EXPECTED_RELEASE, actual_release, assert_expected_release

class Action(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    authority:str
    observation_id:int|None=None
    pilot_id:str|None=None
    pilot_epoch:int|None=None
    pilot_run_id:str|None=None
    reason:str=Field(min_length=3,max_length=2000)
    engine:float=Field(ge=0,le=1)
    collective_deg:list[float]
    tilt_deg:list[list[float]]
    cabin_deg:list[float]=[0.,0.,0.]
    cabin_level:bool=True
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
    departure:list[float]=Field(default_factory=lambda:[0.,0.])
    destination:list[float]=Field(default_factory=lambda:[-50.,20.])
    authority:str='manual'
    time_scale:float=Field(default=1.,ge=.01,le=1)
    stability_assist:float=Field(default=0.,ge=0,le=1,allow_inf_nan=False)
    reference_rpm:float=1200.
    gear_variant:str='critical-damping-proposal'
    airframe_variant:str='r6'
    fuel_kg:float=Field(default=10.,ge=1.,le=110.)
    engine_power_limit_kw:float=Field(default=300.,ge=10.,le=469.8)
    atmosphere_model:str='constant'
    wind_world_mps:list[float]=Field(default_factory=lambda:[0.,0.,0.])
    ignore_scenery_collisions:bool=False
    label:str='user selected mission'
    phantom:phantom_live.PhantomOptions|None=None
    @field_validator('departure','destination')
    @classmethod
    def xy(cls,v):
        if len(v)!=2:raise ValueError('Expected map X/Y')
        return v
    @field_validator('wind_world_mps')
    @classmethod
    def wind_vector(cls,v):
        if len(v)!=3 or not all(math.isfinite(x) for x in v):raise ValueError('Expected three finite wind components in world axes (m/s)')
        return v
    @field_validator('atmosphere_model')
    @classmethod
    def atmosphere(cls,v):
        if v not in ('constant','isa'):raise ValueError('Atmosphere must be constant or isa')
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
        if v not in ['baseline','light','r6','r6_variator','phantom','phantom-fx','phantom-a9','phantom-fx-a9']:raise ValueError('Unknown airframe revision')
        return v


def mission_dump(request):
    """Legacy metadata stays byte-identical: the optional phantom block is omitted when unset.

    Phantom requests also record whether the top-level fuel_kg was set by the
    operator; an unset value is the four-fan default and is not Phantom fuel."""
    d=request.model_dump()
    if d.get('phantom') is None:d.pop('phantom',None)
    if phantom_live.is_phantom_variant(d.get('airframe_variant')):d['fuel_kg_explicit']='fuel_kg' in request.model_fields_set
    return d

def foot_clearance_m(p):
    """Radar clearance: ray straight down from just below the lowest gear foot.

    Replaces the former fixed cabin-sphere point (read 0.75 m on the gear and
    ignored trees, audit F4). The ray uses the MuJoCo scene, so terrain, boxes
    and trees are all seen."""
    m,d=p.model,p.data
    gids=getattr(p,'_foot_gids',None)
    if gids is None:
        gids=[g for g in range(m.ngeom) if (mj.mj_id2name(m,mj.mjtObj.mjOBJ_BODY,int(m.geom_bodyid[g])) or '').startswith('gear')]
        p._foot_gids=gids
    def lowest(g):
        R=d.geom_xmat[g].reshape(3,3)
        if m.geom_type[g]==mj.mjtGeom.mjGEOM_BOX:return float(d.geom_xpos[g][2]-np.abs(R[2])@m.geom_size[g])
        return float(d.geom_xpos[g][2]-m.geom_rbound[g])
    low=min(lowest(g) for g in gids)
    x,y=d.xpos[p.bids['airframe']][:2]
    gid=np.zeros(1,np.int32)
    # Start 5 cm above the foot plane under the airframe centre (clear of the airframe, which
    # sits well above its feet) so a compressed foot never puts the origin inside the terrain.
    dist=mj.mj_ray(m,d,np.array([x,y,low+.05]),np.array([0.,0.,-1.]),None,1,-1,gid)
    return max(0.,(dist if dist>=0 else low+.05)-.05)

class Laboratory:
    def __init__(self):
        self.world=TestWorld();self.flight_world=self.world;self.aircraft=Aircraft(self.world,gear_variant='critical-damping-proposal',rpm=1200.,fuel_kg=10.,airframe_variant='r6',engine_power_limit_kw=300.);self.aircraft.spawn(0,0,self.world.surface_z(0,0))
        self.active=False;self.paused=False;self.time_scale=1.;self.authority='manual';self.run_id=None
        self.mission=None;self.objective=None;self.pilot_owner=None;self.pending_pilot=None;self.pilot_epoch=0;self.fallback_controller=None;self.fallback_status=None;self.action_log=[];self.action_sequence=0;self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.obs_id=0;self.last_obs=None;self.observations={};self.last_sensor_t=-1.;self.sensor_rng=np.random.default_rng(41031)
        self.audit_file=None;self.log_path=None;self.last_audit_t=-1.;self.settled_s=0.;self.left_ground=False
        self.error=None;self.clock_lag_s=0.;self.wall_started=None;self.end_summary=None;self.clock_epoch=0
        self.retry_hint=None
        self.data_root=Path(os.environ.get('VTX_DATA_ROOT',str(ROOT))).resolve()
        self.checkpoint_path=self.data_root/'pilot/live-flight-checkpoint.json'
        self.last_checkpoint_t=-1.
        self.memory_path=self.data_root/'pilot/colin-memory.json'
        self.memory_path.parent.mkdir(parents=True,exist_ok=True)
        if not self.memory_path.exists():self.memory_path.write_text(json.dumps(dict(schema_version=1,pilot='Colin',experience_count=0,lessons=[],aircraft_familiarity='cold start; no VTX-specific solution',stage2_accessed=False,history=[]),indent=2))
        restored=self.restore_checkpoint()
        # Never replace or classify a saved sortie merely because its checkpoint
        # cannot be decoded by this build. It remains available for recovery.
        self.recovery_blocked=self.checkpoint_path.exists() and not restored
        completed=sorted((self.data_root/'evidence/flights').glob('*/summary.json'))
        if completed and not restored:
            last=json.loads(completed[-1].read_text())
            meta_path=completed[-1].parent/'metadata.json'
            if meta_path.exists():
                self.retry_hint=dict(run_id=last['run_id'],mission=last['mission'],request=json.loads(meta_path.read_text())['request'])
                self.end_summary={k:v for k,v in last.items() if k!='final'}
        # If the process died without stop(), the latest metadata is still
        # enough to retry at the departure point. Never reconstruct mid-flight
        # physics from a render frame or claim the interrupted flight landed.
        unfinished=sorted(p for p in (self.data_root/'evidence/flights').glob('*/metadata.json')
                          if not (p.parent/'summary.json').exists())
        if not restored and not self.recovery_blocked and unfinished and (not completed or unfinished[-1].parent.name>completed[-1].parent.name):
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
        if getattr(p,'is_phantom',False):
            state=dict(schema='phantom-1',run_id=self.run_id,model_xml_sha256=p.provenance['model_xml_sha256'],mission=self.mission,objective=self.objective,pilot_owner=self.pilot_owner,pending_pilot=self.pending_pilot,pilot_epoch=self.pilot_epoch,fallback_status=self.fallback_status,authority=self.authority,
                       time_scale=self.time_scale,paused=self.paused,plant=p.checkpoint_state(),
                       session=dict(action_log=self.action_log,action_sequence=self.action_sequence,next_pending_action=self.next_pending_action,last_command_time=self.last_command_time,
                                    lease_expired=self.lease_expired,obs_id=self.obs_id,settled_s=self.settled_s,left_ground=self.left_ground,
                                    last_audit_t=self.last_audit_t,sensor_rng_state=self.sensor_rng.bit_generator.state,
                                    phantom_cg_gate=getattr(self,'phantom_cg_gate',None)))
            return self._write_checkpoint(state)
        state=dict(schema=1,run_id=self.run_id,
                   model_xml_sha256=p.provenance['model_xml_sha256'],
                   mission=self.mission,objective=self.objective,pilot_owner=self.pilot_owner,pending_pilot=self.pending_pilot,pilot_epoch=self.pilot_epoch,
                   fallback_status=self.fallback_status,fallback_controller=self.fallback_controller.snapshot() if self.fallback_controller else None,authority=self.authority,
                   time_scale=self.time_scale,paused=self.paused,
                   physics=dict(time=float(d.time),qpos=d.qpos.tolist(),
                                qvel=d.qvel.tolist(),act=d.act.tolist(),
                                ctrl=d.ctrl.tolist(),
                                qacc_warmstart=d.qacc_warmstart.tolist()),
                   plant=dict(command=p.command,pitch=p.pitch.tolist(),
                              target_angles=p.target_angles.tolist(),
                              actuator_telemetry=p.actuator_telemetry,
                              cabin_target=p.cabin_target.tolist(),
                              engine_spool=p.engine_spool,fuel=p.fuel.tolist(),
                              wind=p.wind.tolist(),rotors=p.rotors,
                              integrity=p.integrity.tolist(),power=p.power,
                              energy=p.energy,events=p.events,flags=list(p.flags),
                              crashed=p.crashed,max_alt=p.max_alt,
                              max_impact_n=p.max_impact_n,
                              max_gear_load_n=getattr(p,'max_gear_load_n',None),max_nongear_impact_n=getattr(p,'max_nongear_impact_n',None),
                              step_count=p.step_count,last_mass_update=p.last_mass_update,
                              last_collision=p.last_collision,
                              stability_assist=p.stability_assist,
                              assisted_collective_deg=p.assisted_collective_deg,
                              experimental_assist=p._bench_apply_experimental_assist,
                              governor_integral_nm=p.governor.integral_nm,
                              governor_telemetry=p.governor.telemetry),
                   session=dict(action_log=self.action_log,action_sequence=self.action_sequence,
                                next_pending_action=self.next_pending_action,
                                last_command_time=self.last_command_time,
                                lease_expired=self.lease_expired,obs_id=self.obs_id,
                                settled_s=self.settled_s,left_ground=self.left_ground,
                                last_audit_t=self.last_audit_t,
                                sensor_rng_state=self.sensor_rng.bit_generator.state))
        return self._write_checkpoint(state)

    def _write_checkpoint(self,state):
        d=self.aircraft.data
        payload=json.dumps(state,allow_nan=False,separators=(',',':'),default=float)
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
            if state['schema']=='phantom-1':
                return self._restore_phantom(state)
            if state['schema']!=1:
                raise ValueError('Unsupported checkpoint schema')
            run_id=state['run_id']
            evidence=self.data_root/'evidence/flights'/run_id
            metadata=json.loads((evidence/'metadata.json').read_text())
            if (metadata['run_id']!=run_id or
                    (evidence/'summary.json').exists()):
                raise ValueError('Checkpoint does not identify an unfinished sortie')
            saved_request=dict(metadata['request'])
            # Older checkpoints omitted these fields and used the former defaults.
            saved_request.setdefault('airframe_variant','light')
            saved_request.setdefault('gear_variant','baseline')
            request=Mission(**saved_request)
            flight_world=self.world_for(request.ignore_scenery_collisions)
            candidate=Aircraft(flight_world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw,
                               atmosphere_model=request.atmosphere_model,wind_world_mps=request.wind_world_mps)
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
            candidate.actuator_telemetry=plant.get('actuator_telemetry',candidate.actuator_telemetry)
            candidate.cabin_target[:]=plant['cabin_target']
            candidate.engine_spool=float(plant['engine_spool'])
            candidate.fuel[:]=plant['fuel']
            candidate.set_wind(plant['wind'])
            candidate.rotors=plant['rotors']
            candidate.integrity[:]=plant['integrity']
            candidate.power=plant['power']
            candidate.energy=plant['energy']
            candidate.events=plant['events']
            candidate.flags=set(plant['flags'])
            candidate.crashed=plant['crashed']
            candidate.max_alt=plant['max_alt']
            candidate.max_impact_n=plant['max_impact_n']
            candidate.max_gear_load_n=plant.get('max_gear_load_n',0.)
            candidate.max_nongear_impact_n=plant.get('max_nongear_impact_n',0.)
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
            self.flight_world=flight_world
            self.run_id=run_id
            self.log_path=evidence
            self.audit_file=(evidence/'events.jsonl').open('a',encoding='utf-8')
            self.mission=state['mission']
            self.objective=state.get('objective')
            self.pilot_owner=state.get('pilot_owner');self.pending_pilot=state.get('pending_pilot');self.pilot_epoch=state.get('pilot_epoch',0)
            self.fallback_status=state.get('fallback_status')
            self.fallback_controller=R6HoldController.restore(state['fallback_controller']) if state.get('fallback_controller') else None
            self.authority=state['authority']
            self.time_scale=state['time_scale']
            self.active=True
            self.paused=True
            self.wall_started=time.monotonic()
            self.action_log=session['action_log']
            self.action_sequence=session.get('action_sequence',max((a['sequence'] for a in self.action_log),default=0))
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

    def _restore_phantom(self,state):
        run_id=state['run_id'];evidence=self.data_root/'evidence/flights'/run_id
        metadata=json.loads((evidence/'metadata.json').read_text())
        if metadata['run_id']!=run_id or (evidence/'summary.json').exists():raise ValueError('Checkpoint does not identify an unfinished sortie')
        saved=dict(metadata['request'])
        if saved.pop('fuel_kg_explicit',True) is False:saved.pop('fuel_kg',None)
        request=Mission(**saved)
        flight_world=self.world_for(request.ignore_scenery_collisions)
        candidate=phantom_live.make_aircraft(flight_world,request,enable_a10_surfaces='stab_te_up' in state['plant'])
        if candidate.provenance['model_xml_sha256']!=state['model_xml_sha256']:raise ValueError('Checkpoint model differs from current physics model')
        candidate.restore_state(state['plant'])
        session=state['session'];self.sensor_rng.bit_generator.state=session['sensor_rng_state']
        self.aircraft=candidate;self.flight_world=flight_world;self.run_id=run_id;self.log_path=evidence
        self.audit_file=(evidence/'events.jsonl').open('a',encoding='utf-8')
        import gzip as _gz
        candidate.step_log=_gz.open(evidence/'phantom_steps.csv.gz','at');candidate.STEP_COLS=None
        self.mission=state['mission'];self.objective=state.get('objective');self.pilot_owner=state.get('pilot_owner');self.pending_pilot=state.get('pending_pilot');self.pilot_epoch=state.get('pilot_epoch',0);self.fallback_status=state.get('fallback_status');self.authority=state['authority'];self.time_scale=state['time_scale']
        self.active=True;self.paused=True;self.wall_started=time.monotonic()
        self.action_log=session['action_log'];self.action_sequence=session.get('action_sequence',max((a['sequence'] for a in self.action_log),default=0));self.next_pending_action=session['next_pending_action']
        for action in self.action_log[self.next_pending_action:]:action['cancelled']=True
        self.next_pending_action=len(self.action_log)
        self.last_command_time=session['last_command_time'];self.lease_expired=session['lease_expired'];self.obs_id=session['obs_id']
        self.last_obs=None;self.observations={};self.last_sensor_t=-1.;self.last_audit_t=session['last_audit_t']
        self.settled_s=session['settled_s'];self.left_ground=session['left_ground'];self.last_checkpoint_t=float(candidate.data.time);self.end_summary=None
        self.phantom_cg_gate=session.get('phantom_cg_gate');self.phantom_landing_site=None
        self.log('flight_checkpoint_restored',dict(checkpoint_t_s=candidate.data.time,paused=True,pending_actions_cancelled=True,variant=candidate.variant,
                 reason='Explicit operator resume required; physics position and velocity retained'))
        return True

    def log(self,kind,payload):
        if self.audit_file:
            row=dict(kind=kind,wall_utc=datetime.now(timezone.utc).isoformat(),t_s=round(float(self.aircraft.data.time),9),payload=payload)
            self.audit_file.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n');self.audit_file.flush()

    def sensor_observation(self):
        p=self.aircraft;d=p.data;m=p.model
        if self.last_obs is not None and d.time-self.last_sensor_t<.05:return self.last_obs
        self.last_sensor_t=float(d.time);self.obs_id+=1
        if getattr(p,'is_phantom',False):
            obs=phantom_live.sensor_observation(self)
            self.last_obs=obs;self.observations[self.obs_id]=obs
            if len(self.observations)>3000:del self.observations[min(self.observations)]
            self.log('observation',obs)
            return obs
        bid=p.bids['airframe'];q=d.xquat[bid]
        euler=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_euler('xyz',degrees=True)
        velocity=np.zeros(6);mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_BODY,bid,velocity,0)
        pos=d.xpos[bid];clearance=p.ground_clearance()
        # Quantized independent instruments, not privileged accelerations, thrust,
        # inertia, future trajectory, contact manifold or optimizer state.
        noise=self.sensor_rng.normal
        obs=dict(observation_id=self.obs_id,t_s=round(float(d.time),3),
            gnss_xy_m=np.round(pos[:2]+noise(0,.015,2),2).tolist(),
            baro_m=round(float(pos[2]+noise(0,.01)),2),
            radar_clearance_m=round(float(clearance+noise(0,.005)),3) if clearance is not None else None,
            attitude_xyz_deg=np.round(euler+noise(0,.008,3),3).tolist(),
            gyro_world_deg_s=np.round(np.degrees(velocity[:3])+noise(0,.008,3),3).tolist(),
            gnss_velocity_mps=np.round(velocity[3:]+noise(0,.005,3),3).tolist(),
            rotor_rpm=[round(float(abs(p.joint(f'rotor{i}_spin')[1])*60/(2*math.pi)),2) for i in range(1,5)],
            shaft_torque_nm=[round(v['torque_nm'],1) for v in p.rotors],
            collective_feedback_deg=np.round(p.pitch,3).tolist(),
            stability_assist=p.stability_assist,assistance_applied=bool(p.stability_assist and p._bench_apply_experimental_assist),assisted_collective_deg=p.assisted_collective_deg,
            tilt_feedback_deg=[[round(math.degrees(p.joint(f'nacelle{i}_{a}')[0]),3) for a in 'xy'] for i in range(1,5)],
            cabin_feedback_deg=[round(math.degrees(p.joint(f'cabin_{a}')[0]),3) for a in 'xyz'],
            cabin_level_enabled=bool(p.command['cabin_level']),
            cabin_level_powered=bool(p.command['cabin_level'] and p.engine_spool>0 and p.fuel.sum()>1e-12),
            cabin_level_limited=bool(p.cabin_level_limited),
            gear_compression_m=[round(float(p.joint(f'gear{i}_stroke')[0]),4) for i in range(1,7)],
            fuel_kg=np.round(p.fuel,4).tolist(),engine_shaft_kw=round(p.power['engine_w']/1000,2),
            warning_lamps=(['IMPACT'] if p.crashed else [])+(['COMMAND_LEASE_EXPIRED'] if self.lease_expired else [])+(['FUEL_EXHAUSTED'] if p.fuel.sum()<=1e-12 else [])+(['CLEARANCE_UNAVAILABLE'] if clearance is None else [])+(['CABIN_LEVEL_TRAVEL_LIMIT'] if p.cabin_level_limited else []),
            configuration=dict(airframe_revision=p.provenance['revision'],airframe_variant=p.airframe_variant,
                               engine_power_limit_kw=p.engine_power_limit_w/1000.,reference_rpm=p.reference_rpm,gear_variant=p.gear_variant,
                               initial_fuel_kg=float(p.fuel_initial.sum()),atmosphere_model=p.atmosphere_model,wind_world_mps=p.wind.tolist()),
            scheduler_backlog_s=round(self.clock_lag_s,3),
            mission=self.mission,authority=self.authority,active=self.active,paused=self.paused,
            time_scale=self.time_scale,
            sensor_status='Provisional sensor models: GNSS/baro/IMU/shaft/angle/fuel/gear transducers; no certified sensor integration')
        # Body-axis channels derived from the already-noised world channels:
        # no extra RNG draws, so the legacy noise sequence is unchanged (audit F2).
        body_from_world=d.xmat[bid].reshape(3,3).T
        obs['gyro_body_deg_s']=np.round(body_from_world@np.asarray(obs['gyro_world_deg_s']),3).tolist()
        obs['velocity_body_mps']=np.round(body_from_world@np.asarray(obs['gnss_velocity_mps']),3).tolist()
        cabin_rotation=d.xmat[p.bids['cabin']].reshape(3,3)
        cabin_forward=body_from_world@(-cabin_rotation[:,1])
        obs['cabin_heading_body_deg']=round(math.degrees(math.atan2(cabin_forward[0],-cabin_forward[1])),3)
        cabin_euler=Rotation.from_matrix(cabin_rotation).as_euler('xyz',degrees=True)
        # Reuse the existing attitude sensor error; no extra RNG samples.
        obs['cabin_attitude_xyz_deg']=np.round(cabin_euler+(np.asarray(obs['attitude_xyz_deg'])-euler),3).tolist()
        obs['frame_labels']=dict(attitude_xyz_deg='extrinsic xyz (= ZYX yaw-pitch-roll); roll/pitch already heading-relative',
            gyro_world_deg_s='world axes',gyro_body_deg_s='airframe body axes',gnss_velocity_mps='world axes',velocity_body_mps='airframe body axes',
            radar_clearance_m='min of downward rays from each gear foot and the airframe centre to terrain, buildings or trees; ~0 on the gear; null if no return',
            cabin_heading_body_deg='cabin forward in airframe body axes',cabin_attitude_xyz_deg='cabin extrinsic xyz, sharing the attitude sensor error')
        self.last_obs=obs;self.observations[self.obs_id]=obs
        if len(self.observations)>3000:del self.observations[min(self.observations)]
        self.log('observation',obs)
        return obs

    def world_for(self,ignore_scenery):
        if not ignore_scenery:return self.world
        world=copy.copy(self.world);world.obstacles=[]
        return world

    def start(self,request:Mission):
        if os.environ.get('VTX_ENFORCE_RELEASE')=='1' and request.airframe_variant!='r6':
            raise HTTPException(409,'This cockpit is pinned to R6; use a separate experimental runtime for other airframes')
        self.phantom_landing_site=None;self.phantom_cg_gate=None
        if self.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before starting another mission')
        flight_world=self.world_for(request.ignore_scenery_collisions)
        mission=select_mission(flight_world.id,flight_world.version,MapPoint(*request.departure),MapPoint(*request.destination),flight_world)
        if phantom_live.is_phantom_variant(request.airframe_variant):
            next_aircraft=phantom_live.make_aircraft(flight_world,request)
        else:
            next_aircraft=Aircraft(flight_world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw,
                               atmosphere_model=request.atmosphere_model,wind_world_mps=request.wind_world_mps)
        next_aircraft.spawn(*request.departure,mission.departure_surface_z_m)
        if self.active:self.stop('Operator started a new flight test; previous attempt retained')
        self.aircraft=next_aircraft
        self.flight_world=flight_world
        self.aircraft.stability_assist=request.stability_assist
        self.active=True;self.paused=False;self.time_scale=request.time_scale;self.authority=request.authority
        self.run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.mission=dict(departure=request.departure,destination=request.destination,
                          departure_z_m=mission.departure_surface_z_m,destination_z_m=mission.destination_surface_z_m,
                          environment=self.world.id,environment_version=self.world.version,label=request.label,
                          ignore_scenery_collisions=request.ignore_scenery_collisions)
        self.objective=None
        self.pilot_owner=None;self.pending_pilot=None;self.pilot_epoch=0
        self.fallback_controller=None;self.fallback_status=None
        self.log_path=self.data_root/'evidence/flights'/self.run_id;self.log_path.mkdir(parents=True)
        self.audit_file=(self.log_path/'events.jsonl').open('w')
        self.wall_started=time.monotonic();self.action_log=[];self.action_sequence=0;self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.last_obs=None;self.obs_id=0;self.last_sensor_t=-1.;self.last_audit_t=-1.;self.observations={}
        self.settled_s=0.;self.left_ground=False;self.error=None;self.end_summary=None
        self.sensor_rng=np.random.default_rng(self.world.seed)
        try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        except (subprocess.CalledProcessError,FileNotFoundError):
            pin=ROOT/'BUILD_COMMIT'
            commit=pin.read_text().strip() if pin.exists() else 'UNKNOWN_BUILD_COMMIT'
        meta=dict(run_id=self.run_id,mission=self.mission,operator=request.authority,request=mission_dump(request),
                  airframe=self.aircraft.provenance,software_commit=commit,
                  runtime_source_sha256=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'src/vtx').glob('*.py')))).hexdigest(),
                  learning_checkpoint_sha256=hashlib.sha256(self.memory_path.read_bytes()).hexdigest(),
                  clocks='400 Hz physics, 100 Hz aero, 20 Hz sensors; independent wall clock at displayed time scale',
                  controls='20 ms simulated transport; accepted targets remain held until changed, authority transfers, or the flight test ends')
        (self.log_path/'metadata.json').write_text(json.dumps(meta,indent=2))
        (self.log_path/'model.xml').write_text(self.aircraft.xml)
        (self.log_path/'pilot-before.json').write_bytes(self.memory_path.read_bytes())
        self.log('mission_start',meta)
        if getattr(self.aircraft,'is_phantom',False):phantom_live.after_start(self,request)
        self.checkpoint(force=True)
        return dict(run_id=self.run_id,observation=self.sensor_observation())

    def accept_action(self,a):
        if not self.active:raise HTTPException(409,'No active sortie')
        if isinstance(a,PhantomAction)!=bool(getattr(self.aircraft,'is_phantom',False)):
            raise HTTPException(409,'Action schema does not match the active airframe (Phantom requires schema phantom-fbw-1)')
        if a.authority!=self.authority:raise HTTPException(409,'This operator does not hold control authority')
        if self.authority=='colin' and a.observation_id not in self.observations:raise HTTPException(409,'Colin action requires an actual permitted observation ID')
        takeover=(a.authority=='colin' and self.pending_pilot is not None and a.pilot_id==self.pending_pilot
                  and a.pilot_epoch==self.pilot_epoch and a.pilot_run_id==self.run_id)
        if takeover:
            for pending in self.action_log[self.next_pending_action:]:
                if not pending.get('cancelled'):
                    pending['cancelled']=True
                    self.log('control_cancelled',dict(sequence=pending['sequence'],reason='Replacement pilot action accepted'))
            previous=self.pilot_owner;self.pilot_owner=self.pending_pilot;self.pending_pilot=None
            self.fallback_controller=None;self.fallback_status=None
            self.log('pilot_takeover_applied',dict(previous=previous,pilot_id=self.pilot_owner,pilot_epoch=self.pilot_epoch))
        if a.authority=='colin' and (self.pilot_epoch>0 or a.pilot_id is not None or a.pilot_epoch is not None or a.pilot_run_id is not None) and (self.pilot_owner is None or a.pilot_id!=self.pilot_owner or a.pilot_epoch!=self.pilot_epoch or a.pilot_run_id!=self.run_id):
            raise HTTPException(409,'Pilot ownership has changed; reconnect to the current session')
        obs=self.observations.get(a.observation_id)
        self.action_sequence+=1
        row=dict(sequence=self.action_sequence,issued_t_s=float(self.aircraft.data.time),
                 apply_t_s=float(self.aircraft.data.time)+.02,observation=obs,decision=a.reason,
                 issued=a.model_dump(by_alias=True,exclude_none=True) if isinstance(a,PhantomAction) else a.model_dump())
        if isinstance(a,PhantomAction):phantom_live.accept_timing(self,row)
        self.action_log.append(row);self.last_command_time=float(self.aircraft.data.time);self.lease_expired=False
        self.log('pilot_decision',row)
        if takeover:self.checkpoint(force=True)
        return dict(accepted=True,sequence=row['sequence'],apply_t_s=row['apply_t_s'])

    def compact_actions(self):
        # The append-only event log remains the full history. Keep recent
        # decisions and every pending action in memory and in checkpoints.
        if self.next_pending_action>64:
            count=self.next_pending_action-32
            del self.action_log[:count]
            self.next_pending_action-=count

    def integrate(self):
        p=self.aircraft
        if getattr(p,'is_phantom',False):
            phantom_live.integrate(self);self.compact_actions();return
        if self.fallback_controller and p.data.time-self.fallback_controller.last_time>=.05:
            try:
                obs=self.sensor_observation()
                command=self.fallback_controller.decide(obs)
                self.accept_action(Action(authority='colin',pilot_id=self.pilot_owner,
                    pilot_epoch=self.pilot_epoch,pilot_run_id=self.run_id,
                    observation_id=obs['observation_id'],**command))
            except (ValueError,KeyError,TypeError,HTTPException) as exc:
                self.fallback_controller=None
                self.fallback_status=dict(state='unavailable',reason=str(exc))
                self.log('fallback_unavailable',self.fallback_status)
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
        self.compact_actions()
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
        if self.fallback_controller:
            self.fallback_controller=None;self.fallback_status=dict(state='inactive',reason='Flight ended')
        self.checkpoint_path.unlink(missing_ok=True)
        outcome=('landed_at_departure' if getattr(self,'phantom_landing_site',None)=='departure' else 'landed') if self.settled_s>=2 else ('collision' if p.crashed else ('airborne attempt ended' if self.left_ground else 'no takeoff'))
        summary=dict(run_id=self.run_id,outcome=outcome,reason=reason,simulated_seconds=float(p.data.time),
                     wall_seconds=time.monotonic()-self.wall_started,decisions=self.action_sequence,
                     left_ground=self.left_ground,max_airframe_origin_altitude_m=p.max_alt,
                     max_contact_force_n=p.max_impact_n,fuel_used_kg=float((p.fuel_initial-p.fuel).sum()),
                     max_gear_load_n=getattr(p,'max_gear_load_n',None),max_nongear_impact_n=getattr(p,'max_nongear_impact_n',None),
                     final=p.physical_snapshot(),mission=self.mission,
                     claim='Conditional experimental model; not validated VTX performance')
        if getattr(p,'is_phantom',False):summary['phantom']=phantom_live.summary_extras(self)
        self.log('sortie_end',summary)
        (self.log_path/'summary.json').write_text(json.dumps(summary,indent=2,default=float));self.audit_file.close();self.audit_file=None
        self.end_summary={k:v for k,v in summary.items() if k!='final'}
        self.retry_hint=dict(run_id=self.run_id,mission=self.mission,request=json.loads((self.log_path/'metadata.json').read_text())['request'])
        return self.end_summary

    def retry(self,request):
        """Explicit new sortie. Preserve the failed run and the learned state."""
        if self.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before retrying a mission')
        if self.active:self.stop('Operator restarted flight test; previous attempt retained')
        hint=self.retry_hint
        if not hint:raise HTTPException(409,'No retained mission to retry')
        old=hint['request']
        variant=request.get('airframe_variant',old.get('airframe_variant','light'))
        # Phantom fuel comes from its own options/load state; never inherit the
        # legacy four-fan fuel default through a retry (flight campaign D-2).
        fuel_kw={}
        if not phantom_live.is_phantom_variant(variant):fuel_kw['fuel_kg']=request.get('fuel_kg',old.get('fuel_kg',60.))
        elif 'fuel_kg' in request:fuel_kw['fuel_kg']=request['fuel_kg']
        elif old.get('fuel_kg') is not None and old.get('fuel_kg_explicit'):fuel_kw['fuel_kg']=old['fuel_kg']
        m=Mission(departure=hint['mission']['departure'],destination=hint['mission']['destination'],
                  authority=request.get('authority','manual'),time_scale=request.get('time_scale',old.get('time_scale',Mission.model_fields['time_scale'].default)),
                  stability_assist=request.get('stability_assist',old.get('stability_assist',0.)),
                  reference_rpm=old.get('reference_rpm',800.),gear_variant=old.get('gear_variant','baseline'),
                  airframe_variant=variant,**fuel_kw,
                  engine_power_limit_kw=request.get('engine_power_limit_kw',old.get('engine_power_limit_kw',469.8)),
                  atmosphere_model=request.get('atmosphere_model',old.get('atmosphere_model','constant')),
                  wind_world_mps=request.get('wind_world_mps',old.get('wind_world_mps',[0.,0.,0.])),
                  ignore_scenery_collisions=request.get('ignore_scenery_collisions',old.get('ignore_scenery_collisions',False)),
                  label='Explicit retry of '+hint['run_id'],
                  **({'phantom':request.get('phantom',old.get('phantom'))} if (request.get('phantom') or old.get('phantom')) else {}))
        result=self.start(m)
        self.log('retry_lineage',dict(previous_run_id=hint['run_id'],checkpoint_preserved=True,new_airframe_variant=m.airframe_variant,
                                      previous_fuel_kg=old.get('fuel_kg',60.),new_fuel_kg=m.fuel_kg if not phantom_live.is_phantom_variant(variant) else float(self.aircraft.fuel_initial.sum()),
                                      previous_power_limit_kw=old.get('engine_power_limit_kw',469.8),new_power_limit_kw=m.engine_power_limit_kw))
        return result

    def view(self):
        return dict(mode='live' if self.active else 'inspection',run_id=self.run_id,authority=self.authority,
                    active=self.active,paused=self.paused,time_scale=self.time_scale,error=self.error,
                    clock_lag_s=self.clock_lag_s,observation=self.sensor_observation(),
                    rendering_truth=self.aircraft.physical_snapshot(),mission=self.mission,objective=self.objective,
                    pilot_owner=self.pilot_owner,pending_pilot=self.pending_pilot,pilot_epoch=self.pilot_epoch,fallback=self.fallback_status,
                    recent_decisions=[{k:v for k,v in a.items() if k!='observation'} for a in self.action_log[-8:]],
                    end_summary=self.end_summary,retry_available=bool(self.retry_hint or self.aircraft.crashed))

# Laboratory initialization restores checkpoints and may write evidence; it
# belongs at server startup rather than at module import (audit F16).
lab=None

def get_lab():
    """Create the Laboratory on first use."""
    global lab
    if lab is None:lab=Laboratory()
    return lab

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
    get_lab()
    if os.environ.get('VTX_ENFORCE_RELEASE')=='1':
        assert_expected_release(lab.aircraft.provenance)
    task=asyncio.create_task(physical_clock())
    yield
    if lab.active:
        lab.checkpoint(force=True)
        if lab.audit_file:
            lab.audit_file.close();lab.audit_file=None
    task.cancel()

app=FastAPI(title='VTX live engineering laboratory',lifespan=lifespan)

# Authentication is opt-in for the existing PC/LAN installation. Public cloud
# instances must set a unique high-entropy token and run behind HTTPS.
_access_token=os.environ.get('VTX_CLOUD_ACCESS_TOKEN','')
if _access_token and len(_access_token)<32:
    raise RuntimeError('VTX_CLOUD_ACCESS_TOKEN must contain at least 32 characters')
def _authorized(headers,cookies):
    if not _access_token:return True
    bearer=headers.get('authorization','')
    cookie=cookies.get('vtx_session','')
    expected=hmac.new(_access_token.encode(),b'vtx-browser-session',hashlib.sha256).hexdigest()
    return hmac.compare_digest(bearer,'Bearer '+_access_token) or hmac.compare_digest(cookie,expected)

@app.middleware('http')
async def cloud_access(request:Request,call_next):
    if _access_token and request.url.path!='/login' and not _authorized(request.headers,request.cookies):
        if request.url.path=='/':return RedirectResponse('/login',status_code=303)
        return JSONResponse({'detail':'Authentication required'},status_code=401)
    valid_bearer=bool(_access_token) and hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+_access_token)
    if _access_token and request.method not in ('GET','HEAD','OPTIONS') and request.url.path!='/login' and not valid_bearer:
        origin=request.headers.get('origin','')
        if origin!='https://'+request.headers.get('host',''):
            return JSONResponse({'detail':'Invalid origin'},status_code=403)
    return await call_next(request)

@app.get('/login',response_class=HTMLResponse)
async def login_page():
    return '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>VTX access</title><body style="background:#101d25;color:white;font:18px sans-serif;padding:2em"><h1>VTX simulator</h1><form method="post"><label>Access token <input name="token" type="password" autocomplete="current-password" required></label><button>Sign in</button></form></body>'

@app.post('/login')
async def login(request:Request):
    from urllib.parse import parse_qs
    token=parse_qs((await request.body()).decode(errors='replace')).get('token',[''])[0]
    if not _access_token or not hmac.compare_digest(token,_access_token):
        return HTMLResponse('Invalid access token',status_code=401)
    response=RedirectResponse('/',status_code=303)
    response.set_cookie('vtx_session',hmac.new(_access_token.encode(),b'vtx-browser-session',hashlib.sha256).hexdigest(),secure=True,httponly=True,samesite='strict')
    return response
@app.get('/api/world')
async def world():return lab.world.public()
@app.get('/api/observe')
async def observe():return lab.sensor_observation()
@app.get('/api/release')
async def release_identity():
    loaded=actual_release(lab.aircraft.provenance)
    return dict(expected=EXPECTED_RELEASE,loaded=loaded,matches=(loaded==EXPECTED_RELEASE),
                enforced=os.environ.get('VTX_ENFORCE_RELEASE')=='1')
@app.get('/api/view')
async def view():return lab.view()
@app.post('/api/objective')
async def set_objective(request:dict):
    if not lab.active:raise HTTPException(409,'No active flight')
    text=request.get('text')
    if not isinstance(text,str) or not 1<=len(text.strip())<=1000:
        raise HTTPException(422,'Objective must contain 1 to 1000 characters')
    previous=lab.objective
    lab.objective=dict(id=uuid.uuid4().hex,text=text.strip(),status='pending',run_id=lab.run_id)
    lab.log('objective_changed',dict(previous=previous,objective=lab.objective))
    lab.checkpoint(force=True)
    return lab.objective
@app.post('/api/objective/complete')
async def complete_objective(request:dict):
    if not lab.active:raise HTTPException(409,'No active flight')
    if not lab.objective or request.get('id')!=lab.objective['id']:
        raise HTTPException(409,'Objective no longer current')
    lab.objective={**lab.objective,'status':'completed'}
    lab.log('objective_completed',dict(objective=lab.objective))
    lab.checkpoint(force=True)
    return lab.objective
@app.post('/api/pilot/handover')
async def pilot_handover(request:dict):
    if not lab.active or lab.authority!='colin':raise HTTPException(409,'Colin must hold authority in an active flight')
    pilot=request.get('pilot_id');epoch=request.get('expected_epoch')
    if not isinstance(pilot,str) or not 1<=len(pilot.strip())<=100 or type(epoch) is not int:
        raise HTTPException(422,'Pilot ID and current epoch required')
    if request.get('run_id')!=lab.run_id:raise HTTPException(409,'Flight changed; refresh current state')
    if epoch!=lab.pilot_epoch:raise HTTPException(409,'Pilot ownership changed; refresh current state')
    if lab.fallback_controller:
        lab.pending_pilot=pilot.strip();lab.pilot_epoch+=1
        lab.log('pilot_takeover_pending',dict(pilot_id=lab.pending_pilot,pilot_epoch=lab.pilot_epoch,objective=lab.objective))
        lab.checkpoint(force=True)
        return dict(run_id=lab.run_id,pilot_id=lab.pending_pilot,pilot_epoch=lab.pilot_epoch,
                    objective=lab.objective,observation=lab.sensor_observation(),pending=True)
    for row in lab.action_log[lab.next_pending_action:]:
        if not row.get('cancelled'):
            row['cancelled']=True
            lab.log('control_cancelled',dict(sequence=row['sequence'],reason='Pilot handover'))
    previous=lab.pilot_owner
    lab.fallback_controller=None
    lab.fallback_status=None
    lab.pilot_owner=pilot.strip();lab.pending_pilot=None;lab.pilot_epoch+=1
    lab.log('pilot_handover',dict(previous=previous,pilot_id=lab.pilot_owner,pilot_epoch=lab.pilot_epoch,objective=lab.objective))
    lab.checkpoint(force=True)
    return dict(run_id=lab.run_id,pilot_id=lab.pilot_owner,pilot_epoch=lab.pilot_epoch,objective=lab.objective,observation=lab.sensor_observation())
@app.post('/api/pilot/failure')
async def pilot_failure(request:dict):
    if not lab.active or lab.authority!='colin':raise HTTPException(409,'No active Colin-controlled flight')
    reason=request.get('reason','Pilot provider unavailable')
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:
        raise HTTPException(422,'Failure reason must contain 1 to 500 characters')
    if (lab.fallback_controller and lab.pending_pilot is not None and request.get('run_id')==lab.run_id and request.get('pilot_id')==lab.pending_pilot
            and request.get('pilot_epoch')==lab.pilot_epoch):
        lab.log('pending_pilot_failed',dict(pilot_id=lab.pending_pilot,reason=reason.strip()))
        lab.pending_pilot=None;lab.pilot_epoch+=1;lab.checkpoint(force=True)
        return dict(run_id=lab.run_id,pilot_owner=lab.pilot_owner,pilot_epoch=lab.pilot_epoch,
                    objective=lab.objective,fallback=lab.fallback_status)
    if (request.get('run_id')!=lab.run_id or request.get('pilot_id')!=lab.pilot_owner
            or request.get('pilot_epoch')!=lab.pilot_epoch or lab.pilot_owner is None):
        raise HTTPException(409,'Pilot ownership changed; refresh current state')
    for row in lab.action_log[lab.next_pending_action:]:
        if not row.get('cancelled'):
            row['cancelled']=True
            lab.log('control_cancelled',dict(sequence=row['sequence'],reason='Pilot provider failed'))
    previous=lab.pilot_owner;lab.pending_pilot=None
    lab.pilot_epoch+=1
    try:
        lab.fallback_controller=R6HoldController(lab.sensor_observation())
        lab.pilot_owner='r6-deterministic-hold'
        lab.fallback_status=dict(state='active',controller='r6-deterministic-hold',reason=reason.strip())
    except (ValueError,KeyError,TypeError) as exc:
        lab.fallback_controller=None;lab.pilot_owner=None
        lab.fallback_status=dict(state='unavailable',reason=str(exc),provider_failure=reason.strip())
    lab.log('pilot_provider_failed',dict(previous=previous,pilot_epoch=lab.pilot_epoch,
                                         objective=lab.objective,fallback=lab.fallback_status))
    lab.checkpoint(force=True)
    return dict(run_id=lab.run_id,pilot_owner=lab.pilot_owner,pilot_epoch=lab.pilot_epoch,
                objective=lab.objective,fallback=lab.fallback_status)
@app.get('/api/validate')
async def validate(x:float,y:float,variant:str|None=None,ignore_scenery_collisions:bool=False):
    from dataclasses import asdict
    world=lab.world_for(ignore_scenery_collisions)
    if phantom_live.is_phantom_variant(variant):
        from .phantom.mission import validate_phantom
        return validate_phantom(world,MapPoint(x,y),variant)
    return asdict(world.validate(MapPoint(x,y),'mission'))
@app.post('/api/destination')
async def destination(request:dict):
    if not lab.active:raise HTTPException(409,'Start a flight test before changing its destination')
    try:
        point=MapPoint(*request['destination'])
    except (KeyError,TypeError,ValueError) as e:
        raise HTTPException(422,'Destination requires two finite coordinates') from e
    decision=lab.flight_world.validate(point,'destination')
    if not decision.valid:raise HTTPException(422,decision.reason)
    before=lab.mission['destination']
    lab.mission['destination']=[point.x_m,point.y_m]
    lab.mission['destination_z_m']=decision.terrain_z_m
    lab.settled_s=0.
    lab.last_obs=None
    lab.log('destination_change',dict(before=before,after=lab.mission['destination']))
    lab.checkpoint(force=True)
    return dict(destination=lab.mission['destination'],landing_valid=True)
@app.post('/api/mission')
async def mission(request:Mission):
    try:return lab.start(request)
    except ValueError as e:raise HTTPException(422,str(e))
def parse_action(body):
    """One endpoint, two schemas: 'phantom-fbw-1' -> PhantomAction, anything else -> the unchanged legacy Action."""
    model=PhantomAction if isinstance(body,dict) and body.get('schema')=='phantom-fbw-1' else Action
    try:return model.model_validate(body)
    except ValidationError as e:
        raise RequestValidationError([{**err,'loc':('body',*err['loc'])} for err in e.errors()])
@app.post('/api/action')
async def action(request:Request):
    try:body=await request.json()
    except ValueError:raise RequestValidationError([{'type':'json_invalid','loc':('body',),'msg':'JSON decode error','input':None}])
    a=parse_action(body)
    try:return lab.accept_action(a)
    except HTTPException as e:
        lab.log('rejected_pilot_action',dict(request=a.model_dump(by_alias=True),reason=e.detail))
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
        if not getattr(lab.aircraft,'is_phantom',False):lab.aircraft._bench_apply_experimental_assist=enabled
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
            if lab.pilot_owner is not None:
                lab.pilot_owner=None;lab.pilot_epoch+=1
            lab.fallback_controller=None;lab.fallback_status=None;lab.pending_pilot=None
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
    return dict(authority=lab.authority,paused=lab.paused,time_scale=lab.time_scale,stability_assist=lab.aircraft.stability_assist,experimental_assist_wire=getattr(lab.aircraft,'_bench_apply_experimental_assist',False))
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
    for path in sorted((lab.data_root/'evidence/flights').glob('*/summary.json'),reverse=True):
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
    path=lab.data_root/'evidence/flights'/run_id/'events.jsonl'
    compressed=path.with_suffix('.jsonl.gz')
    if not path.exists() and not compressed.exists():raise HTTPException(404,'Run not found')
    # Large historical logs must not block the event loop and live physics.
    return await asyncio.to_thread(read_replay_frames,path if path.exists() else compressed)
@app.websocket('/ws')
async def stream(ws:WebSocket):
    if not _authorized(ws.headers,ws.cookies):
        await ws.close(code=1008);return
    await ws.accept()
    try:
        while True:
            # Paused/inspection states do not need 20 full snapshots per second.
            await ws.send_json(lab.view());await asyncio.sleep(.25 if lab.paused or not lab.active else .1)
    except (WebSocketDisconnect,RuntimeError):pass
app.mount('/evidence',StaticFiles(directory=ROOT/'evidence'),name='evidence')
app.mount('/',StaticFiles(directory=ROOT/'public',html=True),name='frontend')
