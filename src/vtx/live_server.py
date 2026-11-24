"""Live observer/action boundary, independent physics clock and durable evidence.

There is no pilot policy here. Colin must read /api/observe, reason, and send
individual /api/action requests while the physical clock keeps running. Manual
controls use that same endpoint. /api/view is renderer/audit truth, NOT a sensor.
"""
from __future__ import annotations
import asyncio
import copy
import csv
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import hashlib
import hmac
import gzip
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Literal
import mujoco as mj
import numpy as np
from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect,Request
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator,ConfigDict
from ._rotation import Rotation
from .aircraft import Aircraft,DT,ROOT
from .mission_selection import MapPoint,SurfaceDecision,select_mission
from .harbour_session import HarbourSession
from .world import TestWorld,SandboxWorld,make_world,resolve_environment_key
from .r6_historical_valley import R6_HISTORICAL_VARIANT
from .r6_hold import R6HoldController
from .phantom import live as phantom_live
from .phantom.controls import PhantomAction
from .phantom.identity import asset_sha256
from .frontend_identity import server_frontend_manifest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from .release import EXPECTED_RELEASE, actual_release, assert_expected_release
from .pilot_api_recorder import get_recorder, record_decision, openai_transport, close_recorders

def publish_new_evidence(path, content):
    """Publish a fully written same-directory evidence file without replacement."""
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    created=False
    try:
        with temporary.open('xb') as stream:
            created=True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link publishes atomically and fails if the evidence exists.
        # Unlike os.replace, it cannot overwrite an existing flight record.
        os.link(temporary,path)
    finally:
        if created:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass  # A complete published summary remains valid.

def runtime_source_sha256(source_root=None):
    """Identify the actual Python runtime, including the nested Phantom plant."""
    root = Path(source_root) if source_root is not None else Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*.py'), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode('utf-8')
        contents = path.read_bytes()
        digest.update(len(relative).to_bytes(4, 'big'))
        digest.update(relative)
        digest.update(len(contents).to_bytes(8, 'big'))
        digest.update(contents)
    return digest.hexdigest()


# Captured at import, before operators can change files under a running server.
RUNTIME_SOURCE_SHA256 = runtime_source_sha256()
R6_CHECKPOINT_DERIVED = ('xpos','xquat','xmat','xipos','ximat','xanchor','xaxis',
                         'cdof','cdof_dot','geom_xpos','geom_xmat','site_xpos','site_xmat',
                         'subtree_com','cvel','actuator_force','actuator_velocity',
                         'ten_length','ten_velocity','ten_J')

def world_fingerprint(world):
    """Hash the actual terrain and world definition, not just its version label."""
    heights=np.ascontiguousarray(world.heights,dtype='<f8')
    metadata=dict(key=world.environment_key,id=world.id,version=world.version,seed=world.seed,
        n=world.n,half=world.half,label=world.label,shape=list(heights.shape),
        obstacles=world.obstacles,water=world.water,default_departure=world.default_departure,
        default_destination=world.default_destination)
    if hasattr(world, 'runway'):
        metadata.update(runway=world.runway, approach_corridor=world.approach_corridor)
    if hasattr(world, 'harbour'):
        metadata['harbour']=world.harbour
    if hasattr(world, 'vaderland'):
        metadata['vaderland']=world.vaderland
    raw=json.dumps(metadata,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    digest=hashlib.sha256(b'vtx-world-v1\0')
    digest.update(len(raw).to_bytes(8,'big'));digest.update(raw);digest.update(heights.tobytes())
    return digest.hexdigest()

def environment_identity(world,flight_world,aircraft):
    hfield=np.ascontiguousarray(aircraft.model.hfield_data,dtype='<f4')
    return dict(scheme='vtx-world-v1',seed=world.seed,displayed_world_sha256=world_fingerprint(world),
                physics_world_sha256=world_fingerprint(flight_world),
                mujoco_hfield_sha256=hashlib.sha256(hfield.tobytes()).hexdigest())


def landing_support(world,point,purpose,variant):
    if getattr(world,'harbour',None) and phantom_live.is_phantom_variant(variant):
        from .phantom.mission import footprint
        if world.harbour_overlaps(point.x_m,point.y_m,footprint(variant)['swept_radius_m']):
            return SurfaceDecision(False,'Harbour water overlaps the aircraft footprint')
    if purpose == 'departure' and phantom_live.is_phantom_variant(variant):
        purpose = 'phantom-departure'
    return world.validate(point,purpose)


def place_at_departure(aircraft, request, terrain_z):
    if phantom_live.is_phantom_variant(request.airframe_variant):
        heading = 90.0 if request.departure_heading_deg is None else request.departure_heading_deg
        aircraft.spawn_on_surface(*request.departure, terrain_z, heading_deg=90.0 - heading)
        aircraft.departure_heading_deg = heading % 360.0
    else:
        aircraft.spawn(*request.departure, terrain_z)


class Action(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    authority:str
    observation_id:int|None=None
    pilot_id:str|None=None
    pilot_epoch:int|None=None
    pilot_run_id:str|None=None
    expected_run_id:str|None=None
    reason:str=Field(min_length=3,max_length=2000)
    engine:float=Field(ge=0,le=1)
    collective_deg:list[float]
    tilt_deg:list[list[float]]
    cabin_deg:list[float]=[0.,0.,0.]
    cabin_level:bool=True
    @field_validator('collective_deg')
    @classmethod
    def pitch(cls,v):
        if len(v)!=4 or any(not 0<=x<=30 for x in v):raise ValueError('Four collective controls, each 0â€“30 degrees')
        return v
    @field_validator('tilt_deg')
    @classmethod
    def tilt(cls,v):
        if len(v)!=4 or any(len(t)!=2 or math.hypot(*t)>20.000001 for t in v):raise ValueError('Four X/Y tilt commands, each with a combined magnitude no greater than 20 degrees')
        return v
    @field_validator('cabin_deg')
    @classmethod
    def cabin(cls,v):
        if len(v) not in (2,3) or any(abs(x)>15 for x in v[:2]) or (len(v)==3 and abs(v[2])>180):raise ValueError('Cabin X/Y Â±15 degrees and yaw Â±180 degrees')
        return v if len(v)==3 else [*v,0.]

class Mission(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    departure:list[float]=Field(default_factory=lambda:[0.,0.])
    departure_heading_deg:float|None=Field(default=None, allow_inf_nan=False)
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
    landing_precision_m:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    label:str='user selected mission'
    landing_requested:bool=False
    environment:str|None=None
    phantom:phantom_live.PhantomOptions|None=None
    @field_validator('environment')
    @classmethod
    def env(cls,v):
        return None if v is None else resolve_environment_key(v)
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
        if v not in ('baseline','light','r6','r6_variator',R6_HISTORICAL_VARIANT,*phantom_live.VARIANTS):raise ValueError('Unknown airframe revision')
        return v


def mission_dump(request):
    """Legacy metadata stays byte-identical: the optional phantom block is omitted when unset.

    Phantom requests also record whether the top-level fuel_kg was set by the
    operator; an unset value is the four-fan default and is not Phantom fuel."""
    d=request.model_dump()
    if d.get('phantom') is None:d.pop('phantom',None)
    if d.get('departure_heading_deg') is None:d.pop('departure_heading_deg',None)
    if phantom_live.is_phantom_variant(d.get('airframe_variant')):d['fuel_kg_explicit']='fuel_kg' in request.model_fields_set
    return d

def normalize_saved_mission_request(raw: dict) -> dict:
    """Retain recorded mission options when restoring a flight."""
    return dict(raw)

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
    @property
    def world(self):
        return self._world

    @world.setter
    def world(self, world):
        # Display worlds are built before selection and are not mutated afterwards.
        # Compute on selection, never in the telemetry/400 Hz integration loop.
        fingerprint=world_fingerprint(world)
        if hasattr(self,'_harbours') and self.harbour_key(self.world.environment_key)!=self.harbour_key(world.environment_key):
            self.harbour_session.set_rate(0.)
        self._world=world
        self._displayed_world_sha256=fingerprint

    def world_snapshot(self):
        snapshot=self.world.public()
        snapshot['displayed_world_sha256']=self._displayed_world_sha256
        return snapshot

    def airport_harbour_world(self):
        if getattr(self.world,'harbour',None):
            return self.world
        airport = getattr(self, '_harbour_airport', None)
        if airport is None or airport.seed != self.world.seed:
            self._harbour_airport = make_world('airport', seed=self.world.seed)
        return self._harbour_airport

    @staticmethod
    def harbour_key(environment):
        # The historical sandbox/valley boat menu explicitly opens Main Airport.
        return environment if environment.startswith('vaderland-') else 'airport'

    def harbour_for(self, environment):
        key=self.harbour_key(resolve_environment_key(environment))
        if key not in self._harbours:
            self._harbours[key]=HarbourSession(self.data_root/'worlds'/key, environment=key)
        return self._harbours[key]

    @property
    def harbour_session(self):
        return self.harbour_for(self.world.environment_key)

    def __init__(self, data_root=None):
        # VTX_DEFAULT_ENVIRONMENT picks the world a fresh server opens on (unset: the Main Airport, as before).
        # A restored checkpoint or saved selection still takes precedence.
        default_env=os.environ.get('VTX_DEFAULT_ENVIRONMENT')
        self.world=make_world(default_env) if default_env else TestWorld();self.flight_world=self.world;self.aircraft=Aircraft(self.world,gear_variant='critical-damping-proposal',rpm=1200.,fuel_kg=10.,airframe_variant='r6',engine_power_limit_kw=300.);self.aircraft.spawn(0,0,self.world.surface_z(0,0))
        self.active=False;self.paused=False;self.time_scale=1.;self.authority='manual';self.run_id=None
        self.mission=None;self.objective=None;self.pilot_owner=None;self.pending_pilot=None;self.pilot_epoch=0;self.fallback_controller=None;self.fallback_status=None;self.action_log=[];self.action_sequence=0;self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.obs_id=0;self.last_obs=None;self.observations={};self.last_sensor_t=-1.;self.sensor_rng=np.random.default_rng(41031)
        self.audit_file=None;self.log_path=None;self.last_audit_t=-1.;self.settled_s=0.;self.left_ground=False;self.landing_recorded=False;self.last_landing=None
        self.error=None;self.recovery_notice=None;self.preview_generation=0;self.clock_lag_s=0.;self.wall_started=None;self.end_summary=None;self.clock_epoch=0
        self.retry_hint=None
        self.inspection_clock=None
        self.data_root=Path(data_root if data_root is not None else os.environ.get('VTX_DATA_ROOT',str(ROOT))).resolve()
        self._harbours={'airport':HarbourSession(self.data_root)}
        self.harbour_helm_outside_airport=False
        self.checkpoint_path=self.data_root/'pilot/live-flight-checkpoint.json'
        self.saved_flights_path=self.data_root/'pilot/saved-flights'
        self.inspection_path=self.data_root/'pilot/inspection-selection.json'
        self.inspection_selection_known=False
        self.server_frontend_identity=None
        self.last_checkpoint_t=-1.
        self.memory_path=self.data_root/'pilot/colin-memory.json'
        self.memory_path.parent.mkdir(parents=True,exist_ok=True)
        if not self.memory_path.exists():self.memory_path.write_text(json.dumps(dict(schema_version=1,pilot='Colin',experience_count=0,lessons=[],aircraft_familiarity='cold start; no VTX-specific solution',stage2_accessed=False,history=[]),indent=2))
        self.checkpoint_set_aside=None
        restored=self.restore_checkpoint()
        # Never replace or classify a saved sortie merely because its checkpoint
        # cannot be decoded by this build. It remains available for recovery.
        self.recovery_blocked=self.checkpoint_path.exists() and not restored
        inspection_request=None
        if restored:self.inspection_selection_known=True
        elif not self.recovery_blocked and self.inspection_path.exists():
            try:inspection_request=self._restore_inspection_selection()
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.error='Saved aircraft selection unavailable: '+str(exc)
                self.recovery_blocked=True
        completed=sorted((self.data_root/'evidence/flights').glob('*/summary.json'))
        if completed and not restored:
            try:
                last=json.loads(completed[-1].read_text(encoding='utf-8'))
                meta_path=completed[-1].parent/'metadata.json'
                if meta_path.exists():
                    self.retry_hint=dict(run_id=last['run_id'],mission=last['mission'],request=json.loads(meta_path.read_text(encoding='utf-8'))['request'])
                    self.end_summary={k:v for k,v in last.items() if k!='final'}
            except (OSError,ValueError,KeyError,TypeError) as exc:
                # Retain suspect evidence; do not use it as a retry source or
                # infer that a checkpoint can safely resume over this summary.
                detail=f'Flight summary {completed[-1]} is unreadable; retained for inspection: {exc}'
                self.error=(self.error+'; '+detail) if self.error else detail
        # If the process died without stop(), the latest metadata is still
        # enough to retry at the departure point. Never reconstruct mid-flight
        # physics from a render frame or claim the interrupted flight landed.
        unfinished=sorted(p for p in (self.data_root/'evidence/flights').glob('*/metadata.json')
                          if not (p.parent/'summary.json').exists()
                          and not (self.saved_flights_path/(p.parent.name+'.json')).exists())
        if not restored and not self.recovery_blocked and unfinished and (not completed or unfinished[-1].parent.name>completed[-1].parent.name):
            path=unfinished[-1]
            try:
                meta=json.loads(path.read_text())
                aside=self.checkpoint_set_aside if self.checkpoint_set_aside and self.checkpoint_set_aside.get('run_id')==meta['run_id'] else None
                interrupted=dict(run_id=meta['run_id'],mission=meta['mission'],
                                 outcome='interrupted',authority=meta.get('operator'),
                                 reason=('Checkpoint written by a different software build was set aside; physical state not resumed'
                                         if aside else 'Server exited before the sortie ended; physical state not recoverable'),
                                 previous_evidence=path.parent.name,**({'checkpoint_set_aside':aside} if aside else {}))
                self.retry_hint=dict(run_id=meta['run_id'],mission=meta['mission'],
                                     request=meta['request'])
                self.end_summary=interrupted
            except (ValueError,KeyError,OSError):
                pass
        if inspection_request and self.retry_hint and inspection_request!=self.retry_hint['request']:
            self.retry_hint=None;self.end_summary=None

    def _remember_inspection_selection(self,request,aircraft,world):
        """Persist an explicit selection, independently of a flight checkpoint."""
        uri=aircraft.provenance.get('render_asset')
        visual_hash=asset_sha256(uri) if uri else None
        if not visual_hash:raise ValueError('Selected aircraft visual asset is missing')
        frontend=server_frontend_manifest()
        state=dict(schema=1,request=mission_dump(request),runtime_source_sha256=RUNTIME_SOURCE_SHA256,
                   environment=dict(key=world.environment_key,id=world.id,version=world.version,seed=world.seed),
                   environment_identity=environment_identity(world,aircraft.world,aircraft),
                   model_xml_sha256=aircraft.provenance['model_xml_sha256'],
                   config_sha256=aircraft.provenance.get('config_sha256'),
                   visual_identity=dict(uri=uri,sha256=visual_hash),server_frontend_identity=frontend)
        self.inspection_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.inspection_path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as f:
            json.dump(state,f,separators=(',',':'));f.flush();os.fsync(f.fileno())
        os.replace(temporary,self.inspection_path)
        self.server_frontend_identity=frontend
        self.inspection_selection_known=True

    def _restore_inspection_selection(self):
        state=json.loads(self.inspection_path.read_text(encoding='utf-8'))
        if state.get('schema')!=1:raise ValueError('Unsupported aircraft selection record')
        if state.get('runtime_source_sha256')!=RUNTIME_SOURCE_SHA256:
            raise ValueError('Selected aircraft requires runtime '+str(state.get('runtime_source_sha256'))+'; record retained')
        frontend=self._verify_server_frontend(state)
        saved=dict(state['request'])
        if saved.pop('fuel_kg_explicit',True) is False:saved.pop('fuel_kg',None)
        request=Mission(**saved)
        env=state['environment'];world=make_world(env['key'],seed=env['seed'])
        if world.id!=env['id'] or world.version!=env['version']:
            raise ValueError('Selected environment definition differs; record retained')
        flight_world=copy.copy(world) if request.ignore_scenery_collisions else world
        if request.ignore_scenery_collisions:flight_world.obstacles=[]
        if phantom_live.is_phantom_variant(request.airframe_variant):
            aircraft=phantom_live.make_aircraft(flight_world,request)
            from .phantom import identity as aircraft_identity_pins
            check=aircraft_identity_pins.verify(aircraft,experimental=bool(aircraft.experimental_overrides),runtime_source_sha256=RUNTIME_SOURCE_SHA256)
            if check['pinned'] and check['mismatches']:raise ValueError('Selected aircraft identity differs; record retained')
            aircraft._identity=check
        else:
            aircraft=Aircraft(flight_world,request.gear_variant,request.reference_rpm,fuel_kg=request.fuel_kg,
                airframe_variant=request.airframe_variant,engine_power_limit_kw=request.engine_power_limit_kw,
                atmosphere_model=request.atmosphere_model,wind_world_mps=request.wind_world_mps)
        place_at_departure(aircraft, request, flight_world.surface_z(*request.departure))
        if aircraft.provenance['model_xml_sha256']!=state['model_xml_sha256'] or aircraft.provenance.get('config_sha256')!=state.get('config_sha256'):
            raise ValueError('Selected aircraft model or configuration differs; record retained')
        if state.get('environment_identity')!=environment_identity(world,flight_world,aircraft):
            raise ValueError('Selected environment data or heightfield differs; record retained')
        self._verify_checkpoint_visual(state,aircraft)
        self.world=world;self.flight_world=flight_world;self.aircraft=aircraft
        self.server_frontend_identity=frontend
        self.inspection_selection_known=True
        return state['request']

    def checkpoint(self, force=False):
        """Crash-consistent physics checkpoint, never a flight-control decision."""
        if not self.active or not self.run_id or not self.log_path:
            return
        p=self.aircraft
        if not force and p.data.time-self.last_checkpoint_t < .5:
            return
        d=p.data
        asset=p.provenance.get('render_asset')
        visual_identity=dict(uri=asset,sha256=asset_sha256(asset) if asset else None)
        # Reuse the selection/start snapshot: hashing 150 MB of assets inside
        # the 400 Hz physics loop would perturb live flight. Restore rehashes.
        frontend=self.server_frontend_identity
        if not frontend:raise ValueError('Current flight has no server frontend asset snapshot')
        if getattr(p,'is_phantom',False):
            state=dict(schema='phantom-2',run_id=self.run_id,model_xml_sha256=p.provenance['model_xml_sha256'],config_sha256=p.P.config_sha256,runtime_source_sha256=RUNTIME_SOURCE_SHA256,visual_identity=visual_identity,server_frontend_identity=frontend,mission=self.mission,objective=self.objective,pilot_owner=self.pilot_owner,pending_pilot=self.pending_pilot,pilot_epoch=self.pilot_epoch,fallback_status=self.fallback_status,authority=self.authority,
                       time_scale=self.time_scale,paused=self.paused,plant=p.checkpoint_state(),
                       session=dict(action_log=self.action_log,action_sequence=self.action_sequence,next_pending_action=self.next_pending_action,last_command_time=self.last_command_time,
                                    lease_expired=self.lease_expired,obs_id=self.obs_id,settled_s=self.settled_s,left_ground=self.left_ground,
                                    landing_recorded=self.landing_recorded,last_landing=self.last_landing,
                                    last_audit_t=self.last_audit_t,sensor_rng_state=self.sensor_rng.bit_generator.state,
                                    phantom_cg_gate=getattr(self,'phantom_cg_gate',None)))
            revision=p.provenance.get('flight_revision')
            if revision:state['flight_revision_registry_sha256']=revision['registry_sha256']
            return self._write_checkpoint(state,force=force)
        spec=mj.mjtState.mjSTATE_INTEGRATION
        integration=np.empty(mj.mj_stateSize(p.model,spec))
        mj.mj_getState(p.model,d,integration,spec)
        state=dict(schema=2,run_id=self.run_id, runtime_source_sha256=RUNTIME_SOURCE_SHA256,
                   model_xml_sha256=p.provenance['model_xml_sha256'],
                   visual_identity=visual_identity,
                   server_frontend_identity=frontend,
                   dependency_versions=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,mujoco=mj.__version__),
                   integration_spec=int(spec),integration_state=integration.tolist(),
                   model_state={name:getattr(p.model,name).tolist() for name in ('body_mass','body_inertia')},
                   derived_state={name:getattr(d,name).tolist() for name in R6_CHECKPOINT_DERIVED},
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
                                landing_recorded=self.landing_recorded,last_landing=self.last_landing,
                                last_audit_t=self.last_audit_t,
                                sensor_rng_state=self.sensor_rng.bit_generator.state))
        return self._write_checkpoint(state,force=force)

    def _write_checkpoint(self,state,force=False):
        d=self.aircraft.data
        if getattr(self.world,'timing',None):state['course_timing']=self.world.timing.save()
        state['harbour_fleet']=self.harbour_session.flight_snapshot(force=force)
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

    def save_flight_for_switching(self,expected_run_id):
        """Park an unfinished flight without ending it or discarding its checkpoint."""
        if not self.active or not self.run_id:raise HTTPException(409,'No active flight to save')
        if expected_run_id!=self.run_id:raise HTTPException(409,'Flight changed; refresh before saving')
        saved=self.saved_flights_path/(self.run_id+'.json')
        if saved.exists():raise HTTPException(409,'A saved checkpoint for this flight already exists')
        if getattr(self.aircraft,'is_phantom',False) and self.aircraft.step_log:
            self.aircraft.step_log.flush()
        self.checkpoint(force=True)
        payload=self.checkpoint_path.read_bytes()
        self.saved_flights_path.mkdir(parents=True,exist_ok=True)
        try:
            with saved.open('xb') as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
        except FileExistsError:
            raise HTTPException(409,'A saved checkpoint for this flight already exists')
        except OSError:
            saved.unlink(missing_ok=True)
            raise
        self.log('flight_saved_for_switching',dict(run_id=self.run_id,checkpoint_t_s=float(self.aircraft.data.time)))
        if getattr(self.aircraft,'is_phantom',False) and self.aircraft.step_log:
            self.aircraft.step_log.close();self.aircraft.step_log=None
        if self.audit_file:self.audit_file.close();self.audit_file=None
        self.checkpoint_path.unlink()
        self.active=False;self.paused=True;self.last_obs=None
        return dict(run_id=self.run_id,environment=(self.mission or {}).get('environment_key'),saved=True)

    def saved_flights(self):
        result=[]
        for path in sorted(self.saved_flights_path.glob('*.json')):
            try:
                state=json.loads(path.read_text(encoding='utf-8'))
                if state['run_id']!=path.stem:raise ValueError('Run ID does not match saved checkpoint')
                evidence=self.data_root/'evidence/flights'/path.stem
                meta=json.loads((evidence/'metadata.json').read_text(encoding='utf-8'))
                physics=state.get('plant',{}) if state.get('schema')=='phantom-2' else state.get('physics',{})
                result.append(dict(run_id=path.stem,variant=meta.get('request',{}).get('airframe_variant'),
                    environment=(state.get('mission') or {}).get('environment_key'),t_s=physics.get('time'),
                    available=not (evidence/'summary.json').exists()))
            except (OSError,ValueError,KeyError,TypeError):
                result.append(dict(run_id=path.stem,available=False))
        return result

    def restore_saved_flight(self,run_id):
        """Resume a parked flight paused; leave incompatible checkpoints intact."""
        if self.active:raise HTTPException(409,'End or save the current flight before restoring another')
        if self.recovery_blocked or self.checkpoint_path.exists():raise HTTPException(409,'An existing checkpoint needs recovery first')
        if not isinstance(run_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise HTTPException(422,'Invalid saved flight ID')
        saved=self.saved_flights_path/(run_id+'.json')
        if not saved.is_file():raise HTTPException(404,'Saved flight not found')
        payload=saved.read_bytes()
        try:
            state=json.loads(payload)
            if state.get('run_id')!=run_id:raise ValueError('Saved flight identity differs from its filename')
        except (ValueError,TypeError) as exc:
            raise HTTPException(409,'Saved checkpoint is invalid and remains available for inspection') from exc
        self.checkpoint_path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with self.checkpoint_path.open('xb') as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
        except FileExistsError:
            raise HTTPException(409,'An existing checkpoint needs recovery first')
        if not self.restore_checkpoint():
            # The saved source is untouched; remove only the copy made above.
            self.checkpoint_path.unlink(missing_ok=True)
            raise HTTPException(409,self.error or 'Saved checkpoint is incompatible')
        # Restore has already attached the paused physical state and opened its
        # evidence. Later I/O errors must not falsely report that restoration
        # failed: the active checkpoint and the saved source remain intact.
        warnings=[]
        try:
            archive=self.data_root/'pilot/checkpoint-history'
            archive.mkdir(parents=True,exist_ok=True)
            saved.rename(archive/(run_id+'-'+uuid.uuid4().hex+'.json'))
        except OSError as exc:
            warnings.append('Saved checkpoint could not be archived; it remains in Saved flights: '+str(exc))
        try:
            meta=json.loads((self.log_path/'metadata.json').read_text(encoding='utf-8'))
            saved_request=dict(meta['request'])
            if saved_request.pop('fuel_kg_explicit',True) is False:saved_request.pop('fuel_kg',None)
            self._remember_inspection_selection(Mission(**saved_request),self.aircraft,self.world)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            warnings.append('Aircraft selection could not be saved for the next idle restart: '+str(exc))
        self.recovery_blocked=False;self.error=None
        self.recovery_notice=' '.join(warnings) if warnings else None
        return dict(run_id=self.run_id,restored=True,paused=True,environment=(self.mission or {}).get('environment_key'),
                    **({'warning':self.recovery_notice} if warnings else {}))

    def fork_checkpoint_continuation(self,expected_run_id,expected_sha256):
        """Explicitly branch a diverged checkpoint into a new evidence directory.

        The parent evidence is never opened for writing; the checkpoint is saved
        byte-for-byte before the active checkpoint is changed to the new run.
        """
        if self.active:raise HTTPException(409,'End or save the current flight before continuing another')
        if not self.checkpoint_path.is_file():raise HTTPException(404,'No retained active checkpoint')
        payload=self.checkpoint_path.read_bytes();digest=hashlib.sha256(payload).hexdigest()
        if digest!=expected_sha256:raise HTTPException(409,'Checkpoint changed; refresh before continuing')
        transaction=self.data_root/'pilot/fork-transactions'/(digest+'.json')
        if transaction.exists():raise HTTPException(409,'A continuation transaction for this checkpoint already exists; inspect its recorded state before retrying')
        def file_digest(path):
            h=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            return h.hexdigest()
        def durable_new(path,data):
            with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        try:
            state=json.loads(payload);parent=state['run_id'];schema=state['schema']
            if not isinstance(parent,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',parent):raise ValueError('Invalid checkpoint run ID')
            if parent!=expected_run_id:raise ValueError('Checkpoint identifies a different run')
            if schema not in (2,'phantom-2'):raise ValueError('Checkpoint format does not support verified continuation')
            if state.get('runtime_source_sha256')!=RUNTIME_SOURCE_SHA256:raise ValueError('Checkpoint runtime differs from this build')
            self._verify_server_frontend(state)
            checkpoint_time=float(state['plant']['time'] if schema=='phantom-2' else state['physics']['time'])
            source=self.data_root/'evidence/flights'/parent
            meta=json.loads((source/'metadata.json').read_text(encoding='utf-8'))
            if meta['run_id']!=parent or (source/'summary.json').exists():raise ValueError('Checkpoint does not identify an unfinished sortie')
            try:self._verify_evidence_tail(source,checkpoint_time,phantom=schema=='phantom-2')
            except json.JSONDecodeError:
                tail_reason='Parent event log is incomplete or malformed; retained unchanged'
            except ValueError as exc:
                if not any(part in str(exc) for part in ('extends beyond the checkpoint','incomplete or unreadable')):raise
                tail_reason=str(exc)
            else:raise ValueError('Evidence does not require a separate continuation')
            required=['metadata.json','model.xml','events.jsonl']
            if schema=='phantom-2':required+=['aircraft_identity.json','phantom_parameters.json','phantom_ledger.json','phantom_steps.csv.gz']
            get_recorder(self.data_root).drain()
            filenames=sorted(p.name for p in source.iterdir() if p.is_file())
            if any(name not in filenames for name in required):raise ValueError('Required parent evidence is missing')
            original_hashes={name:file_digest(source/name) for name in filenames}
            small={name:(source/name).read_bytes() for name in required if name not in ('events.jsonl','phantom_steps.csv.gz')}
            if original_hashes['model.xml']!=state['model_xml_sha256']:
                raise ValueError('Recorded model XML differs from the checkpoint')
            if schema=='phantom-2':
                with gzip.open(source/'phantom_steps.csv.gz','rt',encoding='utf-8') as f:header=f.readline()
                if not header.startswith('t,') or not header.endswith('\n'):raise ValueError('Original telemetry header is unavailable')
        except (OSError,EOFError,ValueError,KeyError,TypeError) as exc:
            raise HTTPException(409,'Checkpoint continuation unavailable: '+str(exc)) from exc

        child=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
        stage=self.data_root/'pilot'/'fork-staging'/uuid.uuid4().hex
        staged_evidence=stage/'evidence/flights'/child;staged_evidence.mkdir(parents=True)
        lineage=dict(parent_run_id=parent,checkpoint_time_s=checkpoint_time,checkpoint_sha256=digest,
                     parent_evidence_sha256=original_hashes,
                     reason=tail_reason,relationship='explicit continuation from checkpoint; parent retains later evidence')
        meta=dict(meta);meta['run_id']=child;meta['continuation']=lineage
        # The new segment begins at the checkpoint, whose server assets can
        # differ from those present when the original run first started.
        meta['server_frontend_identity']=state['server_frontend_identity']
        durable_new(staged_evidence/'metadata.json',json.dumps(meta,indent=2).encode('utf-8'))
        for name,data in small.items():
            if name!='metadata.json':durable_new(staged_evidence/name,data)
        durable_new(staged_evidence/'events.jsonl',b'')
        if schema=='phantom-2':
            durable_new(staged_evidence/'phantom_steps.csv.gz',gzip.compress(header.encode('utf-8')))
        state['run_id']=child;state['continuation']=lineage
        staged_checkpoint=stage/'pilot/live-flight-checkpoint.json';staged_checkpoint.parent.mkdir(parents=True)
        durable_new(staged_checkpoint,json.dumps(state,separators=(',',':'),allow_nan=False).encode('utf-8'))
        candidate=Laboratory(data_root=stage)
        if not candidate.active or not candidate.paused:
            raise HTTPException(409,'Checkpoint continuation validation failed: '+str(candidate.error))
        if getattr(candidate.aircraft,'is_phantom',False) and candidate.aircraft.step_log:
            candidate.aircraft.step_log.close();candidate.aircraft.step_log=None
        candidate.audit_file.close();candidate.audit_file=None
        for name in ('events.jsonl',*(['phantom_steps.csv.gz'] if schema=='phantom-2' else [])):
            with (staged_evidence/name).open('ab') as f:f.flush();os.fsync(f.fileno())
        # Ensure neither the checkpoint nor the evidence changed during staging.
        get_recorder(self.data_root).drain()
        if (self.checkpoint_path.read_bytes()!=payload or
                sorted(p.name for p in source.iterdir() if p.is_file())!=filenames or
                any(file_digest(source/name)!=value for name,value in original_hashes.items())):
            raise HTTPException(409,'Parent checkpoint or evidence changed during continuation validation')
        transaction.parent.mkdir(parents=True,exist_ok=True)
        try:
            with transaction.open('x',encoding='utf-8') as f:
                json.dump(dict(parent_run_id=parent,child_run_id=child,checkpoint_sha256=digest,
                               staged_root=str(stage),state='publish_started'),f)
                f.flush();os.fsync(f.fileno())
        except FileExistsError:
            raise HTTPException(409,'A continuation transaction for this checkpoint already exists')
        archive=self.data_root/'pilot/checkpoint-history';archive.mkdir(parents=True,exist_ok=True)
        preserved=archive/(parent+'-fork-'+uuid.uuid4().hex+'.json')
        with preserved.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
        target=self.data_root/'evidence/flights'/child;target.parent.mkdir(parents=True,exist_ok=True)
        staged_evidence.rename(target)
        # Original checkpoint is already durable in checkpoint-history.
        os.replace(staged_checkpoint,self.checkpoint_path)
        transaction_update=transaction.with_suffix('.tmp')
        durable_new(transaction_update,json.dumps(dict(parent_run_id=parent,child_run_id=child,
            checkpoint_sha256=digest,staged_root=str(stage),state='committed')).encode('utf-8'))
        os.replace(transaction_update,transaction)
        candidate.data_root=self.data_root;candidate.checkpoint_path=self.checkpoint_path
        candidate.saved_flights_path=self.saved_flights_path;candidate.inspection_path=self.inspection_path
        candidate.memory_path=self.memory_path;candidate.log_path=target
        candidate.audit_file=(target/'events.jsonl').open('a',encoding='utf-8')
        if schema=='phantom-2':candidate.aircraft.step_log=gzip.open(target/'phantom_steps.csv.gz','at',encoding='utf-8')
        candidate.recovery_blocked=False;candidate.error=None;candidate.inspection_selection_known=True
        self.harbour_for(candidate.world.environment_key).take_over(candidate.harbour_session)
        self.harbour_session.set_rate(0.)
        candidate._harbours=self._harbours
        self.__dict__.update(candidate.__dict__)
        self.log('checkpoint_continuation',lineage)
        return dict(run_id=child,parent_run_id=parent,checkpoint_time_s=checkpoint_time,paused=True,continuation=lineage)

    def restore_checkpoint(self):
        """Restore exact persisted plant state, held until explicit operator resume."""
        path=self.checkpoint_path
        if not path.exists():
            return False
        fleet=None
        try:
            state=json.loads(path.read_text(encoding='utf-8'))
            saved_source=state.get('runtime_source_sha256')
            if saved_source and saved_source != RUNTIME_SOURCE_SHA256:
                raise ValueError(f"Saved flight {state.get('run_id')} requires runtime {saved_source}; "
                                 f"this runtime is {RUNTIME_SOURCE_SHA256}. Checkpoint retained at {path}")
            if not saved_source:
                raise ValueError(f'Checkpoint has no runtime source fingerprint; source equivalence is unverified. Checkpoint retained at {path}')
            frontend=self._verify_server_frontend(state)
            if state.get('harbour_fleet') is not None:
                mission=state['mission']
                harbour=self.harbour_for(mission.get('environment_key') or mission.get('environment'))
                fleet=harbour.stage(mission['environment_identity']['seed'],state['harbour_fleet'],harbour.environment)
            if state['schema']=='phantom-1':
                raise ValueError('Legacy Phantom checkpoint lacks actuator and controller state required for verified continuation; retained for inspection')
            if state['schema']=='phantom-2':
                restored=self._restore_phantom(state,fleet)
                if restored:self.server_frontend_identity=frontend
                return restored
            if state['schema']==1:
                raise ValueError('Legacy R6 checkpoint lacks solver and actuator state required for verified continuation; retained for inspection')
            if state['schema']!=2:
                raise ValueError('Unsupported checkpoint schema')
            run_id=state['run_id']
            evidence=self.data_root/'evidence/flights'/run_id
            metadata=json.loads((evidence/'metadata.json').read_text())
            if (metadata['run_id']!=run_id or
                    (evidence/'summary.json').exists()):
                raise ValueError('Checkpoint does not identify an unfinished sortie')
            self._verify_evidence_tail(evidence,state['physics']['time'],phantom=False)
            saved_request=normalize_saved_mission_request(metadata['request'])
            if not saved_request.get('airframe_variant') or not saved_request.get('gear_variant'):
                raise ValueError('Checkpoint lacks the recorded aircraft or gear variant; identity cannot be reconstructed')
            request=Mission(**saved_request)
            saved_env=request.environment or (state.get('mission') or {}).get('environment_key') or (state.get('mission') or {}).get('environment')
            if not saved_env:raise ValueError('Checkpoint lacks its recorded environment; environment cannot be reconstructed')
            environment=state.get('mission',{}).get('environment_identity')
            if not environment or 'seed' not in environment:raise ValueError('Checkpoint lacks its environment fingerprint or seed')
            restored_world=make_world(saved_env,seed=environment['seed'])
            flight_world=copy.copy(restored_world) if request.ignore_scenery_collisions else restored_world
            if request.ignore_scenery_collisions:flight_world.obstacles=[]
            candidate=Aircraft(flight_world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw,
                               atmosphere_model=request.atmosphere_model,wind_world_mps=request.wind_world_mps)
            if candidate.provenance['model_xml_sha256']!=state['model_xml_sha256']:
                raise ValueError('Checkpoint model differs from current physics model')
            if environment!=environment_identity(restored_world,flight_world,candidate):
                raise ValueError('Checkpoint environment data or heightfield differs from its recording')
            self._verify_checkpoint_visual(state,candidate)
            versions=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,mujoco=mj.__version__)
            if state.get('dependency_versions')!=versions:raise ValueError('Checkpoint Python, NumPy or MuJoCo version differs from this runtime')
            d=candidate.data;m=candidate.model;spec=mj.mjtState.mjSTATE_INTEGRATION
            if state.get('integration_spec')!=int(spec):raise ValueError('Unsupported MuJoCo integration state')
            integration=np.asarray(state['integration_state'],dtype=float)
            if integration.shape!=(mj.mj_stateSize(m,spec),) or not np.all(np.isfinite(integration)):
                raise ValueError('Invalid checkpoint integration state')
            for name in ('body_mass','body_inertia'):
                arr=np.asarray(state['model_state'][name],dtype=float);target=getattr(m,name)
                if arr.shape!=target.shape or not np.all(np.isfinite(arr)):raise ValueError('Invalid checkpoint model array: '+name)
                target[:]=arr
            mj.mj_setConst(m,mj.MjData(m));mj.mj_setState(m,d,integration,spec)
            warmstart=d.qacc_warmstart.copy();mj.mj_forward(m,d);d.qacc_warmstart[:]=warmstart
            for name in R6_CHECKPOINT_DERIVED:
                arr=np.asarray(state['derived_state'][name],dtype=float);target=getattr(d,name)
                if arr.shape!=target.shape or not np.all(np.isfinite(arr)):raise ValueError('Invalid checkpoint derived array: '+name)
                target[:]=arr
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
            session=state['session']
            self.sensor_rng.bit_generator.state=session['sensor_rng_state']
            self.harbour_for(restored_world.environment_key).restore_flight(state,fleet)
            if 'course_timing' in state:restored_world.timing.restore(state['course_timing'])
            self.world=restored_world
            self.aircraft=candidate
            self.server_frontend_identity=frontend
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
            self.last_command_time=session['last_command_time']
            self.lease_expired=session['lease_expired']
            self.obs_id=session['obs_id']
            self.last_obs=None
            self.observations={}
            self.last_sensor_t=-1.
            self.last_audit_t=session['last_audit_t']
            self.settled_s=session['settled_s']
            self.left_ground=session['left_ground']
            self.landing_recorded=session.get('landing_recorded',False);self.last_landing=session.get('last_landing')
            self.last_checkpoint_t=float(d.time)
            self.end_summary=None
            self.log('flight_checkpoint_restored',
                     dict(checkpoint_t_s=d.time,paused=True,
                          pending_actions_retained=True,
                          reason='Explicit operator resume required; physics position and velocity retained'))
            return True
        except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
            self.error='Flight checkpoint unavailable: '+str(exc)
            return False
        finally:
            if fleet is not None and self.harbour_session.worker is not fleet:
                fleet.close()

    def _restore_phantom(self,state,fleet=None):
        run_id=state['run_id'];evidence=self.data_root/'evidence/flights'/run_id
        metadata=json.loads((evidence/'metadata.json').read_text())
        if metadata['run_id']!=run_id or (evidence/'summary.json').exists():raise ValueError('Checkpoint does not identify an unfinished sortie')
        self._verify_evidence_tail(evidence,state['plant']['time'],phantom=True)
        saved=dict(metadata['request'])
        if saved.pop('fuel_kg_explicit',True) is False:saved.pop('fuel_kg',None)
        if not saved.get('airframe_variant'):
            raise ValueError('Checkpoint lacks the recorded aircraft variant; identity cannot be reconstructed')
        request=Mission(**saved)
        from .phantom.flight_revisions import REGISTRY_PATH, flight_revision
        if flight_revision(request.airframe_variant):
            expected_registry=state.get('flight_revision_registry_sha256')
            actual_registry=hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
            if not expected_registry or expected_registry!=actual_registry:
                raise ValueError('Checkpoint flight revision registry is missing or differs from this build')
        saved_env=request.environment or (state.get('mission') or {}).get('environment_key') or (state.get('mission') or {}).get('environment')
        if not saved_env:raise ValueError('Checkpoint lacks its recorded environment; environment cannot be reconstructed')
        environment=state.get('mission',{}).get('environment_identity')
        if not environment or 'seed' not in environment:raise ValueError('Checkpoint lacks its environment fingerprint or seed')
        restored_world=make_world(saved_env,seed=environment['seed'])
        flight_world=copy.copy(restored_world) if request.ignore_scenery_collisions else restored_world
        if request.ignore_scenery_collisions:flight_world.obstacles=[]
        expected_config=state.get('config_sha256') or metadata.get('airframe',{}).get('config_sha256')
        if not expected_config:
            snapshot=evidence/'phantom_parameters.json'
            if snapshot.exists():
                expected_config=json.loads(snapshot.read_text(encoding='utf-8')).get('config_sha256')
        if not expected_config:
            raise ValueError('Checkpoint has no Phantom configuration fingerprint')
        candidate=None
        for enable_surfaces in (False, True):
            attempt=phantom_live.make_aircraft(flight_world,request,enable_a10_surfaces=enable_surfaces)
            if (attempt.provenance['model_xml_sha256']==state['model_xml_sha256'] and
                    attempt.P.config_sha256==expected_config):
                candidate=attempt
                break
        if candidate is None:
            raise ValueError('Checkpoint model or Phantom configuration differs from current physics')
        from .phantom import identity as aircraft_identity_pins
        check = aircraft_identity_pins.verify(candidate, experimental=bool(candidate.experimental_overrides),
                                              runtime_source_sha256=RUNTIME_SOURCE_SHA256)
        if check['mismatches']:
            raise ValueError('Checkpoint aircraft differs from its pinned identity: ' + check['status'])
        candidate._identity = check
        if environment!=environment_identity(restored_world,flight_world,candidate):
            raise ValueError('Checkpoint environment data or heightfield differs from its recording')
        self._verify_checkpoint_visual(state,candidate)
        candidate.restore_state(state['plant'])
        import gzip as _gz
        try:
            with _gz.open(evidence/'phantom_steps.csv.gz','rt',encoding='utf-8') as stream:
                header=stream.readline().strip()
                step_columns=header.split(',') if header else None
        except (OSError,EOFError) as exc:
            raise ValueError('Original Phantom telemetry cannot be opened for continuation') from exc
        if step_columns is not None and step_columns!=list(candidate.step_row()):
            raise ValueError('Original Phantom telemetry columns differ from this runtime')
        session=state['session'];self.sensor_rng.bit_generator.state=session['sensor_rng_state']
        self.harbour_for(restored_world.environment_key).restore_flight(state,fleet)
        if 'course_timing' in state:restored_world.timing.restore(state['course_timing'])
        self.world=restored_world;self.aircraft=candidate;self.flight_world=flight_world;self.run_id=run_id;self.log_path=evidence
        self.audit_file=(evidence/'events.jsonl').open('a',encoding='utf-8')
        candidate.step_log=_gz.open(evidence/'phantom_steps.csv.gz','at');candidate.STEP_COLS=step_columns
        self.mission=state['mission'];self.objective=state.get('objective');self.pilot_owner=state.get('pilot_owner');self.pending_pilot=state.get('pending_pilot');self.pilot_epoch=state.get('pilot_epoch',0);self.fallback_status=state.get('fallback_status');self.authority=state['authority'];self.time_scale=state['time_scale']
        self.active=True;self.paused=True;self.wall_started=time.monotonic()
        self.action_log=session['action_log'];self.action_sequence=session.get('action_sequence',max((a['sequence'] for a in self.action_log),default=0));self.next_pending_action=session['next_pending_action']
        self.last_command_time=session['last_command_time'];self.lease_expired=session['lease_expired'];self.obs_id=session['obs_id']
        self.last_obs=None;self.observations={};self.last_sensor_t=-1.;self.last_audit_t=session['last_audit_t']
        self.settled_s=session['settled_s'];self.left_ground=session['left_ground'];self.landing_recorded=session.get('landing_recorded',False);self.last_landing=session.get('last_landing');self.last_checkpoint_t=float(candidate.data.time);self.end_summary=None
        self.phantom_cg_gate=session.get('phantom_cg_gate');self.phantom_landing_site=(self.last_landing or {}).get('closest_reference')
        self.log('flight_checkpoint_restored',dict(checkpoint_t_s=candidate.data.time,paused=True,pending_actions_retained=True,variant=candidate.variant,
                 reason='Explicit operator resume required; physics position and velocity retained'))
        return True

    @staticmethod
    def _verify_evidence_tail(evidence,checkpoint_time,phantom):
        """Never append resumed state behind newer, already recorded evidence."""
        t=float(checkpoint_time)
        if not math.isfinite(t):raise ValueError('Invalid checkpoint time')
        try:
            with (evidence/'events.jsonl').open(encoding='utf-8') as stream:
                for line in stream:
                    row=json.loads(line)
                    if float(row.get('t_s',0))>t+1e-6:
                        raise ValueError('Flight evidence extends beyond the checkpoint; a separate continuation segment is required')
            if phantom:
                with gzip.open(evidence/'phantom_steps.csv.gz','rt',encoding='utf-8',newline='') as stream:
                    for row in csv.DictReader(stream):
                        if float(row['t'])>t+1e-6:
                            raise ValueError('Flight telemetry extends beyond the checkpoint; a separate continuation segment is required')
        except (OSError,EOFError,KeyError,TypeError) as exc:
            raise ValueError('Flight evidence is incomplete or unreadable; checkpoint retained') from exc

    @staticmethod
    def _verify_server_frontend(state):
        recorded=state.get('server_frontend_identity')
        if not isinstance(recorded,dict) or not isinstance(recorded.get('files'),dict):
            raise ValueError('Saved state has no server frontend asset fingerprint; retained for inspection')
        actual=server_frontend_manifest()
        if actual!=recorded:
            before=recorded['files'];after=actual['files']
            changes=[f'missing {name}' for name in sorted(before.keys()-after.keys())]
            changes += [f'added {name}' for name in sorted(after.keys()-before.keys())]
            changes += [f'changed {name}' for name in sorted(before.keys() & after.keys()) if before[name]!=after[name]]
            detail=', '.join(changes[:5]) or 'manifest format or metadata changed'
            if len(changes)>5:detail+=f' and {len(changes)-5} more'
            raise ValueError('Server frontend assets differ from the saved state: '+detail+'; retained for inspection')
        return actual

    @staticmethod
    def _verify_checkpoint_visual(state,candidate):
        recorded=state.get('visual_identity') or {}
        uri=candidate.provenance.get('render_asset')
        if not recorded.get('uri') or not recorded.get('sha256'):
            raise ValueError('Checkpoint has no verified visual asset fingerprint')
        if recorded['uri']!=uri or asset_sha256(uri)!=recorded['sha256']:
            raise ValueError('Checkpoint visual asset is missing or differs from the recorded asset')

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
        if self.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before starting another mission')
        if self.active:raise HTTPException(409,'End the current sortie explicitly before a new mission')
        target_world=self.world
        if request.environment is not None:
            target_env=resolve_environment_key(request.environment)
            if getattr(self.world,'environment_key','airport')!=target_env:
                target_world=make_world(target_env,seed=self.world.seed)
        flight_world=copy.copy(target_world) if request.ignore_scenery_collisions else target_world
        if request.ignore_scenery_collisions:flight_world.obstacles=[]
        self.preview_generation+=1
        departure_check=landing_support(flight_world,MapPoint(*request.departure),'departure',request.airframe_variant)
        if not departure_check.valid:raise ValueError('INVALID_DEPARTURE: '+departure_check.reason)
        target=MapPoint(*request.destination)
        if max(abs(target.x_m),abs(target.y_m))>flight_world.half-8:
            raise ValueError('Destination outside surveyed map boundary')
        arrival_check=landing_support(flight_world,target,'destination',request.airframe_variant)
        target_z=flight_world.surface_z(*request.destination)
        if phantom_live.is_phantom_variant(request.airframe_variant):
            candidate=phantom_live.make_aircraft(flight_world,request)
            # A pinned aircraft flies only as itself: physics configuration, parameter file and visual asset must match the pin.
            from .phantom import identity as aircraft_identity_pins
            check=aircraft_identity_pins.verify(candidate,experimental=bool(candidate.experimental_overrides),runtime_source_sha256=RUNTIME_SOURCE_SHA256)
            if check['pinned'] and check['mismatches']:
                self.log('flight_refused_identity_mismatch',check) if getattr(self,'log_path',None) else None
                raise HTTPException(409,'Flight refused: '+check['name']+' does not match its pinned identity. '+check['status'])
            candidate._identity=check
        else:
            candidate=Aircraft(flight_world,request.gear_variant,request.reference_rpm,
                               fuel_kg=request.fuel_kg,airframe_variant=request.airframe_variant,
                               engine_power_limit_kw=request.engine_power_limit_kw,
                               atmosphere_model=request.atmosphere_model,wind_world_mps=request.wind_world_mps)
        place_at_departure(candidate, request, departure_check.terrain_z_m)
        self._remember_inspection_selection(request,candidate,target_world)
        self.world=target_world;self.aircraft=candidate
        self.phantom_landing_site=None;self.phantom_cg_gate=None
        # Bench engine is ready after launch; collective remains zero until commanded.
        if not getattr(self.aircraft, 'is_phantom', False):
            self.aircraft.set_command(dict(engine=1.0))
        self.flight_world=flight_world
        self.aircraft.stability_assist=request.stability_assist
        self.active=True;self.paused=False;self.time_scale=request.time_scale;self.authority=request.authority
        self.run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.mission=dict(departure=request.departure,destination=request.destination,
                          departure_z_m=departure_check.terrain_z_m,destination_z_m=target_z,
                          destination_landing_valid=arrival_check.valid,destination_advisory=arrival_check.reason,landing_requested=request.landing_requested,
                          environment=self.world.id,environment_version=self.world.version,
                          environment_identity=environment_identity(self.world,flight_world,self.aircraft),
                          environment_key=getattr(self.world,'environment_key','airport'),
                          environment_label=getattr(self.world,'label','Main Airport'),
                          label=request.label,
                          ignore_scenery_collisions=request.ignore_scenery_collisions,landing_precision_m=request.landing_precision_m)
        if request.departure_heading_deg is not None and phantom_live.is_phantom_variant(request.airframe_variant):
            self.mission['departure_heading_deg'] = candidate.departure_heading_deg
        self.objective=None
        self.pilot_owner=None;self.pending_pilot=None;self.pilot_epoch=0
        self.fallback_controller=None;self.fallback_status=None
        self.log_path=self.data_root/'evidence/flights'/self.run_id;self.log_path.mkdir(parents=True)
        self.audit_file=(self.log_path/'events.jsonl').open('w')
        self.wall_started=time.monotonic();self.action_log=[];self.action_sequence=0;self.next_pending_action=0;self.last_command_time=0.;self.lease_expired=False
        self.last_obs=None;self.obs_id=0;self.last_sensor_t=-1.;self.last_audit_t=-1.;self.observations={}
        self.settled_s=0.;self.left_ground=False;self.landing_recorded=False;self.last_landing=None;self.error=None;self.end_summary=None
        self.sensor_rng=np.random.default_rng(self.world.seed)
        try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        except (subprocess.CalledProcessError,FileNotFoundError):
            pin=ROOT/'BUILD_COMMIT'
            commit=pin.read_text().strip() if pin.exists() else 'UNKNOWN_BUILD_COMMIT'
        meta=dict(run_id=self.run_id,mission=self.mission,operator=request.authority,request=mission_dump(request),
                  airframe=self.aircraft.provenance,software_commit=commit,
                  server_frontend_identity=self.server_frontend_identity,
                  runtime_source_sha256=RUNTIME_SOURCE_SHA256, runtime_hash_scheme='vtx-python-tree-at-import-v1',
                  learning_checkpoint_sha256=hashlib.sha256(self.memory_path.read_bytes()).hexdigest(),
                  clocks='400 Hz physics, 100 Hz aero, 20 Hz sensors; independent wall clock at displayed time scale',
                  controls=('20 ms simulated transport; Phantom commands held until changed' if getattr(self.aircraft,'is_phantom',False) else '20 ms simulated transport; 5 simulated seconds lease then feather collective while engine remains available; experimental rate damping is shadow-only'))
        (self.log_path/'metadata.json').write_text(json.dumps(meta,indent=2))
        (self.log_path/'model.xml').write_text(self.aircraft.xml)
        (self.log_path/'pilot-before.json').write_bytes(self.memory_path.read_bytes())
        self.log('mission_start',meta)
        if getattr(self.aircraft,'is_phantom',False):phantom_live.after_start(self,request)
        self.checkpoint(force=True)
        return dict(run_id=self.run_id,observation=self.sensor_observation())

    def update_destination(self, destination):
        """Retarget the current sortie without altering the aircraft or pilot authority."""
        if not self.active:
            raise HTTPException(409, 'Start a sortie before changing its live destination')
        if not isinstance(destination, list) or len(destination) != 2 or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
            for x in destination
        ):
            raise HTTPException(422, 'Destination must be two finite map coordinates')
        point = MapPoint(*destination)
        if max(abs(point.x_m), abs(point.y_m)) > self.world.half - 8:
            raise HTTPException(422, 'Destination outside surveyed map boundary')
        variant=getattr(self.aircraft,'variant',None) or getattr(self.aircraft,'airframe_variant',None)
        arrival_check = landing_support(self.world,point,'destination',variant)
        previous = list(self.mission['destination'])
        self.mission['destination'] = list(destination)
        self.mission['destination_z_m'] = self.world.surface_z(*destination)
        self.mission['destination_landing_valid'] = arrival_check.valid
        self.mission['destination_advisory'] = arrival_check.reason
        self.mission['landing_requested'] = False
        self.settled_s = 0.
        self.log('destination_changed', dict(previous=previous, destination=destination,
                 destination_z_m=self.mission['destination_z_m'],landing_valid=arrival_check.valid,
                 advisory=arrival_check.reason,t_s=float(self.aircraft.data.time)))
        self.checkpoint(force=True)
        return dict(run_id=self.run_id, destination=self.mission['destination'],
                    destination_z_m=self.mission['destination_z_m'],
                    landing_valid=arrival_check.valid, advisory=arrival_check.reason)
    def accept_action(self,a):
        if not self.active:raise HTTPException(409,'No active sortie')
        if a.expected_run_id is not None and a.expected_run_id!=self.run_id:
            raise HTTPException(409,'Flight changed; refresh before sending controls')
        if isinstance(a,PhantomAction)!=bool(getattr(self.aircraft,'is_phantom',False)):
            raise HTTPException(409,'Action schema does not match the active airframe (Phantom requires schema phantom-fbw-1)')
        if a.authority!=self.authority:raise HTTPException(409,'This operator does not hold control authority')
        if a.authority=='colin' and getattr(a,'pti',None) is not None and a.pti.command!='abort':
            raise HTTPException(409,'Timed test excitation is offline only; pilot decisions must be individual telemetry-based commands')
        if self.authority=='colin':
            from .pilot_policy import observation_error
            prior=None
            # The existing feedback hold is a server-owned connection hold,
            # not a new external pilot decision or waypoint navigator.
            feedback_hold=(self.fallback_controller is not None and self.pilot_owner=='r6-deterministic-hold'
                           and a.pilot_id==self.pilot_owner)
            if not feedback_hold:
                prior=next((row['issued'].get('observation_id') for row in reversed(self.action_log)
                            if not row.get('cancelled') and row['issued'].get('authority')=='colin'
                            and row['issued'].get('pilot_id')==a.pilot_id
                            and row['issued'].get('pilot_epoch')==a.pilot_epoch),None)
            error=observation_error(self.observations.get(a.observation_id),self.aircraft.data.time,
                                    self.run_id,a.expected_run_id,a.pilot_run_id,a.observation_id,prior)
            if error:raise HTTPException(409,error)
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
        if not self.active:
            return
        p=self.aircraft
        if timing:=getattr(self.world,'timing',None):
            if getattr(timing,'air',None):
                timing.sample(p.data.time,p.data.qpos[:3],air_allowed=self.flight_world is self.world,
                              contact=bool(p.data.ncon) or p.crashed)
            else:
                timing.sample(p.data.time,p.data.qpos[:3])
        if getattr(p,'is_phantom',False):
            phantom_live.integrate(self);self.compact_actions()
            if p.crashed:self.reset_after_failure('Physical crash detected')
            return
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
        if p.data.time-self.last_command_time>5 and not self.lease_expired:
            p.set_command(dict(engine=p.command['engine'],collective_deg=[0.]*4,tilt_deg=p.command['tilt_deg'],cabin_deg=p.command['cabin_deg']))
            self.lease_expired=True;self.log('command_lease_expired',dict(behavior='feather collective; keep bench engine and servos powered; no flight rescue'))
        self.compact_actions()
        p.step()
        if p.crashed:
            self.reset_after_failure('Physical crash detected')
            return
        if p.data.time-self.last_audit_t>=.05:
            self.last_audit_t=float(p.data.time)
            self.log('physics_audit',p.physical_snapshot())
            self.sensor_observation()
            self.checkpoint()
            support=sum(1 for i in range(1,7) if p.joint(f'gear{i}_stroke')[0]>.002)
            speed=float(np.linalg.norm(p.data.qvel[:3]))
            level=float(p.data.xmat[p.bids['airframe']].reshape(3,3)[2,2])>.98
            self.update_landing_evidence(support=support,level=level,speed=speed,loaded=True)

    def update_landing_evidence(self, *, support, level, speed, loaded):
        """Record supported settling independently of waypoint precision; keep physics running."""
        p=self.aircraft
        if support==0 and p.data.time>1:
            self.left_ground=True;self.landing_recorded=False
        if self.left_ground and support>=3 and loaded and level and speed<.15 and not p.crashed:
            self.settled_s+=.05
        else:
            self.settled_s=0.
        if self.settled_s>=2 and not self.landing_recorded:
            xy=np.asarray(p.data.qpos[:2],dtype=float)
            distance=float(np.linalg.norm(xy-np.asarray(self.mission['destination'],dtype=float)))
            departure_distance=float(np.linalg.norm(xy-np.asarray(self.mission['departure'],dtype=float)))
            precision=self.mission.get('landing_precision_m')
            self.last_landing=dict(t_s=float(p.data.time),position_m=xy.tolist(),support_count=support,
                settled_s=self.settled_s,speed_m_s=speed,level=bool(level),collision=bool(p.crashed),
                destination_distance_m=distance,departure_distance_m=departure_distance,
                closest_reference='departure' if departure_distance<distance else 'destination',
                physical='supported_stable',precision_tolerance_m=precision,
                precision='not_specified' if precision is None else ('met' if distance<=precision else 'missed'))
            self.landing_recorded=True
            self.phantom_landing_site=self.last_landing['closest_reference'] if getattr(p,'is_phantom',False) else None
            self.log('supported_landing_observed',self.last_landing)
            self.checkpoint(force=True)

    def stop(self,reason):
        if not self.active:return self.end_summary or dict(status='No active sortie')
        # Keep the checkpoint and leave the flight paused if recording the
        # outcome fails; an I/O error must not silently discard recoverable state.
        self.paused=True;p=self.aircraft
        if self.fallback_controller:
            self.fallback_controller=None;self.fallback_status=dict(state='inactive',reason='Flight ended')
        outcome=('landed_at_departure' if self.last_landing and self.last_landing['closest_reference']=='departure' else 'landed') if self.settled_s>=2 and self.last_landing and not p.crashed else ('collision' if p.crashed else ('airborne attempt ended' if self.left_ground else 'no takeoff'))
        summary=dict(run_id=self.run_id,outcome=outcome,reason=reason,simulated_seconds=float(p.data.time),
                     wall_seconds=time.monotonic()-self.wall_started,decisions=self.action_sequence,
                     left_ground=self.left_ground,max_airframe_origin_altitude_m=p.max_alt,
                     max_contact_force_n=p.max_impact_n,fuel_used_kg=float((p.fuel_initial-p.fuel).sum()),
                     max_gear_load_n=getattr(p,'max_gear_load_n',None),max_nongear_impact_n=getattr(p,'max_nongear_impact_n',None),
                     final=p.physical_snapshot(),mission=self.mission,landing_assessment=self.last_landing,
                     claim='Conditional experimental model; not validated VTX performance')
        if getattr(p,'is_phantom',False):summary['phantom']=phantom_live.summary_extras(self)
        publish_new_evidence(self.log_path/'summary.json',json.dumps(summary,indent=2,default=float).encode('utf-8'))
        self.log('sortie_end',summary)
        self.audit_file.close();self.audit_file=None
        self.checkpoint_path.unlink(missing_ok=True)
        self.active=False;self.last_obs=None
        self.end_summary={k:v for k,v in summary.items() if k!='final'}
        self.retry_hint=dict(run_id=self.run_id,mission=self.mission,request=json.loads((self.log_path/'metadata.json').read_text())['request'])
        return self.end_summary

    def reset_after_failure(self, reason):
        """Retain a failed run and its evidence before starting a new test."""
        if not self.active:
            raise HTTPException(409, 'No active flight to reset')
        run_id = self.run_id
        run_path = self.log_path
        objective = self.objective
        pilot = self.pilot_owner
        config = dict(getattr(self.aircraft, 'provenance', {}))
        result = self.stop(reason)
        pilot_summary = dict(run_id=run_id, reason=reason, outcome=result['outcome'],
                             objective=objective, pilot_id=pilot,
                             decision_count=result['decisions'],
                             simulated_seconds=result['simulated_seconds'],
                             evidence=['summary.json', 'events.jsonl'])
        findings = dict(run_id=run_id, evidence_state='measured_simulation',
                        configuration=config, outcome=result['outcome'],
                        max_airframe_origin_altitude_m=result['max_airframe_origin_altitude_m'],
                        max_contact_force_n=result['max_contact_force_n'],
                        max_gear_load_n=result['max_gear_load_n'],
                        max_nongear_impact_n=result['max_nongear_impact_n'],
                        fuel_used_kg=result['fuel_used_kg'],
                        causal_analysis='Not assessed',
                        next_action='Review telemetry and identify the failure mechanism.')
        (run_path/'pilot_summary.json').write_text(json.dumps(pilot_summary,indent=2,default=float),encoding='utf-8')
        (run_path/'engineering_findings.json').write_text(json.dumps(findings,indent=2,default=float),encoding='utf-8')
        return dict(previous_run_id=run_id, pilot_summary='pilot_summary.json',
                    engineering_findings='engineering_findings.json')

    def retry(self,request):
        """Explicit new sortie. Preserve the failed run and the learned state."""
        if self.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before retrying a mission')
        if self.active:raise HTTPException(409,'End and retain the current sortie before retrying')
        hint=self.retry_hint
        if not hint:raise HTTPException(409,'No retained mission to retry')
        if 'expected_previous_run_id' in request and request['expected_previous_run_id']!=hint['run_id']:
            raise HTTPException(409,'Retained mission changed; refresh before retrying')
        old=hint['request']
        def retained(name):
            if name in request:return request[name]
            if name in old:return old[name]
            raise HTTPException(409,'Retained mission lacks '+name+'; specify it or start a new mission')
        variant=request.get('airframe_variant') or old.get('airframe_variant')
        if not variant:raise HTTPException(409,'Retained mission has no aircraft variant; select a new mission explicitly')
        # Phantom fuel comes from its own options/load state; never inherit the
        # legacy four-fan fuel default through a retry (flight campaign D-2).
        fuel_kw={}
        if not phantom_live.is_phantom_variant(variant):
            fuel=request.get('fuel_kg',old.get('fuel_kg'))
            if fuel is None:raise HTTPException(409,'Retained mission has no fuel loading; specify fuel or start a new mission')
            fuel_kw['fuel_kg']=fuel
        elif 'fuel_kg' in request:fuel_kw['fuel_kg']=request['fuel_kg']
        elif old.get('fuel_kg') is not None and old.get('fuel_kg_explicit'):fuel_kw['fuel_kg']=old['fuel_kg']
        retry_env=request.get('environment',old.get('environment') or hint.get('mission',{}).get('environment_key') or hint.get('mission',{}).get('environment'))
        if not retry_env:raise HTTPException(409,'Retained mission has no environment; choose one explicitly')
        m=Mission(departure=hint['mission']['departure'],destination=hint['mission']['destination'],
                  departure_heading_deg=old.get('departure_heading_deg'),
                  authority=request.get('authority','manual'),time_scale=retained('time_scale'),
                  stability_assist=retained('stability_assist'),
                  reference_rpm=retained('reference_rpm'),gear_variant=retained('gear_variant'),
                  airframe_variant=variant,**fuel_kw,
                  engine_power_limit_kw=retained('engine_power_limit_kw'),
                  atmosphere_model=retained('atmosphere_model'),wind_world_mps=retained('wind_world_mps'),
                  ignore_scenery_collisions=retained('ignore_scenery_collisions'),
                  landing_requested=retained('landing_requested'),landing_precision_m=retained('landing_precision_m'),
                  label='Explicit retry of '+hint['run_id'],
                  **({'environment':retry_env} if retry_env else {}),
                  **({'phantom':request.get('phantom',old.get('phantom'))} if (request.get('phantom') or old.get('phantom')) else {}))
        result=self.start(m)
        self.log('retry_lineage',dict(previous_run_id=hint['run_id'],checkpoint_preserved=True,new_airframe_variant=m.airframe_variant,
                                      previous_fuel_kg=old.get('fuel_kg'),new_fuel_kg=m.fuel_kg if not phantom_live.is_phantom_variant(variant) else float(self.aircraft.fuel_initial.sum()),
                                      previous_power_limit_kw=old.get('engine_power_limit_kw'),new_power_limit_kw=m.engine_power_limit_kw))
        return result

    def pilot_status(self):
        observation = self.sensor_observation()
        return dict(run_id=self.run_id, active=self.active, paused=self.paused, authority=self.authority,
                    pilot_owner=self.pilot_owner, pending_pilot=self.pending_pilot, pilot_epoch=self.pilot_epoch,
                    objective=self.objective, airframe_variant=observation['configuration']['airframe_variant'],
                    warning_lamps=observation['warning_lamps'], outcome=(self.end_summary or {}).get('outcome'))

    def scenery_snapshot(self):
        plant=self.aircraft
        if not getattr(plant,'scenery',None):return {}
        t=float(plant.data.time)
        if self.active or self.run_id:
            self.inspection_clock=None
        else:
            now=time.monotonic()
            if self.inspection_clock is None or self.inspection_clock[0] is not plant:
                self.inspection_clock=(plant,now)
            t=now-self.inspection_clock[1]
            plant.scenery.apply(plant.data,scene_time=t)
            import mujoco as mj
            mj.mj_kinematics(plant.model,plant.data)
        return dict(iris=plant.scenery.doors(plant.data),course_timing=self.world.timing.runs,scenery_time_s=t)

    def view(self):
        return dict(mode='live' if self.active else 'inspection',run_id=self.run_id,authority=self.authority,
                    start_configuration=getattr(self.aircraft,'start_configuration',None),
                    departure_heading_deg=(self.mission or {}).get('departure_heading_deg',getattr(self.aircraft,'departure_heading_deg',None)),
                    runtime_source_sha256=RUNTIME_SOURCE_SHA256, runtime_hash_scheme='vtx-python-tree-at-import-v1',
                    server_frontend_last_capture_sha256=(self.server_frontend_identity or {}).get('sha256'),
                    browser_frontend_verified=False,
                    environment=dict(key=getattr(self.world,'environment_key','airport'),
                                     id=self.world.id,version=self.world.version,seed=self.world.seed,
                                     displayed_world_sha256=self._displayed_world_sha256,
                                     label=getattr(self.world,'label','Main Airport'),
                                     half_m=self.world.half,
                                     default_departure=list(getattr(self.world,'default_departure',[-700.,0.])),
                                     default_destination=list(getattr(self.world,'default_destination',[-50.,20.]))),
                    active=self.active,paused=self.paused,time_scale=self.time_scale,error=self.error,recovery_notice=self.recovery_notice,landing_assessment=self.last_landing,inspection_selection_known=self.inspection_selection_known,
                    **self.scenery_snapshot(),
                    clock_lag_s=self.clock_lag_s,observation=self.sensor_observation(),
                    rendering_truth=self.aircraft.physical_snapshot(),mission=self.mission,objective=self.objective,
                    pilot_owner=self.pilot_owner,pending_pilot=self.pending_pilot,pilot_epoch=self.pilot_epoch,fallback=self.fallback_status,
                    recent_decisions=[{k:v for k,v in a.items() if k!='observation'} for a in self.action_log[-8:]],
                    end_summary=self.end_summary,retry_available=bool(self.retry_hint))

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
        # Yield to other requests even while catching up, without adding a
        # timed wait between batches when complete physics steps are owed.
        await asyncio.sleep(0 if accum >= DT and lab.active and not lab.paused else .005)
        now=time.monotonic();delta=now-last;last=now
        harbour_rate = lab.time_scale if lab.active else 1.
        if not getattr(lab.world,'harbour',None) and lab.harbour_helm_outside_airport:
            harbour_rate = 1.
        elif (lab.active and lab.paused) or not getattr(lab.world,'harbour',None):
            harbour_rate = 0.
        lab.harbour_session.set_rate(harbour_rate)
        if not lab.active or lab.paused:accum=0.;continue
        if seen_epoch!=lab.clock_epoch:
            lab.log('scheduler_clock_rebase',dict(unintegrated_backlog_s=accum,time_scale=lab.time_scale,reason='Explicit operator clock change; no physical state reset'))
            seen_epoch=lab.clock_epoch;accum=0.;continue
        if seen_run!=lab.run_id:
            seen_run=lab.run_id;accum=0.;continue
        accum+=delta*lab.time_scale
        # A short batch lets cockpit I/O run between groups of solver steps.
        n=min(int(accum/DT),4)
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
    for harbour in lab._harbours.values():
        await asyncio.to_thread(harbour.close)
    await asyncio.to_thread(close_recorders)

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
async def world():return lab.world_snapshot()

@app.post('/api/scenery/iris')
async def set_iris(request:dict):
    import mujoco as mj
    plant=lab.aircraft
    if request.get('environment')!=lab.world.environment_key or not getattr(plant,'scenery',None):
        raise HTTPException(409,'The selected environment has no matching iris doors')
    door=request.get('door');opened=request.get('open')
    if door not in ('west','east') or type(opened) is not bool:raise HTTPException(422,'Choose a portal and its open state')
    if not opened and lab.active:
        cfg=next(d for d in lab.world.vaderland['operations']['annex']['doors'] if d['id']==door)
        x,y,z=plant.data.qpos[:3]-cfg['center']
        if abs(x)<16. and math.hypot(y,z)<21.:raise HTTPException(409,'Aircraft occupies the iris clearance zone')
    instant=not lab.active or lab.paused
    lab.harbour_session.set_iris(door,opened,instant)
    plant.scenery.command(plant.data,door,opened,instant)
    mj.mj_forward(plant.model,plant.data)
    if lab.active:
        lab.log('environment_iris',dict(portal=door,open=opened));lab.checkpoint(force=True)
    return dict(iris=plant.scenery.doors(plant.data),door=door,open=opened)

@app.get('/api/harbour/world')
async def harbour_world():
    airport = lab.airport_harbour_world()
    return dict(airport.public(), displayed_world_sha256=world_fingerprint(airport))

@app.get('/api/harbour')
async def harbour_status(airport:bool=False):
    try:
        return await asyncio.to_thread(lab.harbour_session.status,lab.airport_harbour_world() if airport else lab.world)
    except (OSError,ValueError) as exc:
        raise HTTPException(409,str(exc)) from exc

@app.get('/api/harbour/model')
async def harbour_model(boatId:str,airport:bool=False):
    try:
        return await asyncio.to_thread(lab.harbour_session.model,lab.airport_harbour_world() if airport else lab.world,boatId)
    except (OSError,ValueError,KeyError) as exc:
        raise HTTPException(409,str(exc)) from exc

@app.post('/api/harbour/action')
async def harbour_action(request:dict,airport:bool=False):
    action=request.get('action')
    if action not in ('activate','select','command','dock','undock','save','restore','restart'):
        raise HTTPException(422,'Unknown harbour action')
    if action in ('select','command','dock','undock','restart') and not isinstance(request.get('boatId'),str):
        raise HTTPException(422,'Select the boat explicitly')
    if action=='dock' and not isinstance(request.get('berthId'),str):
        raise HTTPException(422,'Select the berth explicitly')
    if action=='command' and not isinstance(request.get('command'),dict):
        raise HTTPException(422,'Expected a boat command')
    try:
        result=await asyncio.to_thread(lab.harbour_session.act,lab.airport_harbour_world() if airport else lab.world,action,request)
        if airport and action in ('activate','select','command','undock','restart'):
            lab.harbour_helm_outside_airport=not bool(getattr(lab.world,'harbour',None))
        return result
    except (OSError,ValueError,KeyError) as exc:
        raise HTTPException(409,str(exc)) from exc
@app.get('/api/observe')
async def observe():
    observation=lab.sensor_observation()
    if lab.active and lab.run_id:
        get_recorder(lab.data_root).emit(dict(schema_version=1,run_id=lab.run_id,
            decision_id=None,wall_utc=datetime.now(timezone.utc).isoformat(),
            kind='pilot_observation_served',payload=observation))
    return {**observation, 'run_id': lab.run_id}

@app.get('/api/pilot/status')
async def pilot_status():
    return lab.pilot_status()

class PilotPrompt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instruction:str=Field(min_length=1,max_length=2000)
    model:str=Field(default='gpt-5.1',min_length=1,max_length=100)

@app.post('/api/pilot/openai-decision')
async def pilot_openai_decision(prompt:PilotPrompt):
    """Opt-in model request; records response but NEVER commands the aircraft."""
    if not lab.active or lab.authority!='colin':
        raise HTTPException(409,'Active Colin-authority sortie required')
    observation=lab.sensor_observation()
    try:
        return await asyncio.to_thread(record_decision,run_id=lab.run_id,
            instruction=prompt.instruction,observation=observation,
            model=prompt.model,transport=openai_transport,data_root=lab.data_root)
    except Exception:
        raise HTTPException(502,'OpenAI pilot request failed; aircraft control unchanged')

@app.get('/api/release')
async def release_identity():
    loaded=actual_release(lab.aircraft.provenance)
    return dict(expected=EXPECTED_RELEASE,loaded=loaded,matches=(loaded==EXPECTED_RELEASE),
                enforced=os.environ.get('VTX_ENFORCE_RELEASE')=='1',
                selection_allowed=os.environ.get('VTX_ENFORCE_RELEASE')!='1',
                supported_variants=['r6','r6_variator',R6_HISTORICAL_VARIANT,'light','baseline',*phantom_live.VARIANTS])
@app.get('/api/view')
async def view():return lab.view()
@app.get('/api/identity')
async def identity():
    """Effective aircraft, physics, visual and software identity of the loaded aircraft, checked against its pin."""
    p=lab.aircraft
    if getattr(p,'is_phantom',False):out=dict(phantom_live.aircraft_identity(lab))
    else:
        from .phantom import identity as pins
        out=dict(variant=p.provenance.get('airframe_variant'),revision=p.provenance.get('revision'),render_asset=p.provenance.get('render_asset'),
                 git_commit=pins.git_commit(),pinned=False,verified=None,mismatches=[],status='not pinned (historical or reference variant)')
    out.update(runtime_source_sha256=RUNTIME_SOURCE_SHA256,run_id=lab.run_id,active=lab.active)
    out.update(server_frontend_last_capture_sha256=(lab.server_frontend_identity or {}).get('sha256'),browser_frontend_verified=False)
    return out

@app.get('/api/frontend-identity')
async def frontend_identity():
    """Current server files, not an attestation of an open browser or its cache."""
    try:return await asyncio.to_thread(server_frontend_manifest)
    except (OSError,ValueError) as exc:raise HTTPException(409,'Frontend identity unavailable: '+str(exc))

@app.get('/api/runs/{run_id}/frontend-identity')
async def recorded_frontend_identity(run_id:str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise HTTPException(422,'Invalid run ID')
    path=lab.data_root/'evidence/flights'/run_id/'metadata.json'
    if not path.is_file():raise HTTPException(404,'Run not found')
    try:meta=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:raise HTTPException(409,'Run metadata cannot be read') from exc
    if meta.get('run_id')!=run_id:raise HTTPException(409,'Run metadata identity differs')
    recorded=meta.get('server_frontend_identity')
    return dict(captured=bool(recorded),identity=recorded,
                note='Server public files captured at mission start; browser-loaded content is not verified')

class PilotCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(min_length=1,max_length=500)
    confirm:bool=False
    source:Literal['voice','text','ai']='text'
    heard_wall_ms:float|None=None

@app.post('/api/pilot/command')
async def pilot_command(c:PilotCommand):
    """A spoken or typed instruction -> one validated action through accept_action -> confirmation from the plant.

    'executed' is true only when the physics loop holds the commanded values; understanding alone is never reported as execution."""
    from . import pilot_command as pc
    t0=time.perf_counter()
    base=dict(heard=c.text,source=c.source,understood=False,accepted=False,executed=False,run_id=lab.run_id,authority=lab.authority)
    def done(**kw):
        out={**base,**kw,'latency_ms':round((time.perf_counter()-t0)*1000,1)}
        if lab.active and lab.run_id==base['run_id']:lab.log('pilot_command',out)
        return out
    if not getattr(lab.aircraft,'is_phantom',False):
        return done(intent='refused',say='Voice and text commands fly the Phantom only. Choose a Phantom first.')
    before=lab.sensor_observation()
    r=pc.parse(c.text,before)
    if r['intent']=='status':return done(understood=True,intent='status',say=pc.status_readback(before),telemetry=pc.telemetry_excerpt(before))
    if c.source=='ai':
        return done(intent='refused',rejected='AI text macros are disabled',
                    say='Observe the aircraft and send an explicit telemetry-based pilot action. Plain-language AI instructions do not execute built-in flight commands.')
    if r['intent'] in ('unknown','refused','confirm','cancel') or not r['patch']:
        return done(understood=r['intent'] in ('refused','confirm','cancel'),intent=r['intent'],say=r['say'])
    base.update(understood=True,intent=r['intent'],patch=r['patch'])
    if not lab.active:return done(say='No flight is running. Start a mission first.',rejected='No active sortie')
    if r['risky'] and not c.confirm:return done(needs_confirmation=True,say=r['say']+' Say confirm or cancel.')
    if r['risky']:r['say']='Confirmed. '+r['say'].rstrip('?')+'.'
    try:
        a=PhantomAction(schema='phantom-fbw-1',authority=lab.authority,observation_id=before['observation_id'],expected_run_id=lab.run_id,
                        reason=f'Pilot command ({c.source}): "{c.text}" -> {r["intent"]}',**r['patch'])
        result=lab.accept_action(a)
    except HTTPException as e:
        lab.log('rejected_pilot_action',dict(request=dict(text=c.text,patch=r['patch']),reason=e.detail))
        return done(rejected=str(e.detail),say='Command rejected: '+str(e.detail))
    except ValidationError as e:
        return done(rejected=str(e),say='Command rejected: it is outside the control limits.')
    base.update(accepted=True,sequence=result['sequence'],apply_t_s=result['apply_t_s'],observation_id=before['observation_id'])
    get_recorder(lab.data_root).emit(dict(schema_version=1,run_id=lab.run_id,decision_id=None,wall_utc=datetime.now(timezone.utc).isoformat(),
        kind='pilot_action_accepted',payload=dict(action=a.model_dump(by_alias=True,exclude_none=True),result=result)))
    run=lab.run_id;deadline=time.perf_counter()+2.0;applied_ms=None;cancelled=False
    while time.perf_counter()<deadline and lab.active and lab.run_id==run and not lab.paused:
        queued=next((row for row in lab.action_log if row.get('sequence')==result['sequence']),None)
        if queued and queued.get('cancelled'):
            cancelled=True;break
        if queued and queued.get('applied') and float(lab.aircraft.data.time)>=result['apply_t_s'] and pc.held(lab.aircraft.fcc.cmd,r['patch']):
            applied_ms=round((time.perf_counter()-t0)*1000,1);break
        await asyncio.sleep(.005)
    if applied_ms is None:
        why='the command was cancelled before application' if cancelled else 'the simulation is paused' if lab.paused else 'the flight ended' if not lab.active or lab.run_id!=run else 'the physics loop did not apply it within 2 seconds'
        return done(say=f'Command accepted but not yet applied: {why}.',not_applied=why,telemetry_before=pc.telemetry_excerpt(before))
    await asyncio.sleep(.25)   # let the plant respond so the reply quotes telemetry from after the command
    if lab.run_id!=run:
        return done(executed=True,applied_latency_ms=applied_ms,say='Command applied; the flight changed before telemetry readback.',telemetry_before=pc.telemetry_excerpt(before))
    lab.last_obs=None;after=lab.sensor_observation()
    return done(executed=True,applied_latency_ms=applied_ms,say=r['say'],telemetry_before=pc.telemetry_excerpt(before),telemetry_after=pc.telemetry_excerpt(after))

@app.get('/api/phantom/physics')
async def phantom_physics(variant:str='phantom-a10b'):
    from .phantom.params import Params, VARIANTS
    if variant not in VARIANTS:
        raise HTTPException(422, f'Unknown Phantom variant {variant!r}')
    return Params(variant).snapshot()
@app.post('/api/model-preview')
async def model_preview(request:dict):
    """Validate the replacement before parking the explicitly named flight."""
    save_run = request.get('save_run_id')
    if (lab.run_id if lab.active else None) != save_run:
        raise HTTPException(409,'Flight changed; refresh before switching vehicles')
    if lab.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before changing vehicles')
    if os.environ.get('VTX_ENFORCE_RELEASE')=='1' and request.get('airframe_variant')!='r6':
        raise HTTPException(409,'This cockpit is pinned to R6')
    target_world=lab.world
    if request.get('environment') is not None:
        try:env_key=resolve_environment_key(request.get('environment'))
        except ValueError as e:raise HTTPException(422,str(e))
        if getattr(lab.world,'environment_key','airport')!=env_key:
            target_world=make_world(env_key,seed=lab.world.seed)
    dep_default=list(getattr(target_world,'default_departure',[0,0])) if request.get('environment') is not None else [0,0]
    variant=request.get('airframe_variant')
    options={}
    if lab.inspection_selection_known and lab.inspection_path.is_file():
        previous=json.loads(lab.inspection_path.read_text(encoding='utf-8'))['request']
        if previous.get('airframe_variant')==variant:
            options=previous
            if not options.pop('fuel_kg_explicit',True):options.pop('fuel_kg',None)
    phantom={**(options.get('phantom') or {}),'start_configuration':request.get('start_configuration','vtol')}
    options.update(environment=request.get('environment'),airframe_variant=variant,departure=request.get('departure',dep_default),phantom=phantom)
    if 'departure_heading_deg' in request:options['departure_heading_deg']=request['departure_heading_deg']
    try:selection=Mission(**options)
    except ValidationError as e:raise HTTPException(422,str(e))
    flight_world=copy.copy(target_world) if selection.ignore_scenery_collisions else target_world
    if selection.ignore_scenery_collisions:flight_world.obstacles=[]
    point=MapPoint(*selection.departure)
    verdict = landing_support(flight_world, point, 'departure', selection.airframe_variant)
    if not verdict.valid:raise HTTPException(422,verdict.reason)
    lab.preview_generation+=1
    generation=lab.preview_generation
    def build():
        if phantom_live.is_phantom_variant(selection.airframe_variant):
            aircraft=phantom_live.make_aircraft(flight_world,selection)
        else:
            aircraft=Aircraft(flight_world,selection.gear_variant,selection.reference_rpm,
                              fuel_kg=selection.fuel_kg,airframe_variant=selection.airframe_variant,
                              engine_power_limit_kw=selection.engine_power_limit_kw,
                              atmosphere_model=selection.atmosphere_model,wind_world_mps=selection.wind_world_mps)
        place_at_departure(aircraft, selection, verdict.terrain_z_m)
        return aircraft
    try:aircraft=await asyncio.to_thread(build)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    if (lab.run_id if lab.active else None) != save_run or generation!=lab.preview_generation:
        raise HTTPException(409,'The flight or model selection changed while the inspection model was loading')
    if getattr(aircraft,'is_phantom',False):
        from .phantom import identity as aircraft_identity_pins
        check=aircraft_identity_pins.verify(aircraft,experimental=bool(aircraft.experimental_overrides),runtime_source_sha256=RUNTIME_SOURCE_SHA256)
        if check['pinned'] and check['mismatches']:
            raise HTTPException(409,'Aircraft identity mismatch: '+check['status'])
        aircraft._identity=check
    if save_run:
        lab.save_flight_for_switching(save_run)
    try:lab._remember_inspection_selection(selection,aircraft,target_world)
    except ValueError as e:raise HTTPException(409,str(e))
    lab.world=target_world;lab.flight_world=flight_world;lab.aircraft=aircraft;lab.last_obs=None;lab.last_sensor_t=-1.;lab.obs_id=0;lab.observations={}
    lab.action_log=[];lab.run_id=None;lab.mission=None;lab.error=None;lab.paused=False
    lab.retry_hint=None;lab.end_summary=None;lab.objective=None;lab.last_landing=None
    lab.pilot_owner=None;lab.pending_pilot=None;lab.fallback_status=None;lab.fallback_controller=None
    return lab.view()
@app.post('/api/environment')
async def set_environment(request:dict):
    """Switch the live world between Main Airport and Test Sandbox when no sortie is active."""
    if lab.active:raise HTTPException(409,'End and retain the current sortie before switching environments')
    if lab.recovery_blocked:raise HTTPException(409,'Saved checkpoint requires recovery before switching environments')
    if not lab.inspection_selection_known:raise HTTPException(409,'Select an aircraft explicitly before switching environments')
    try:env_key=resolve_environment_key(request.get('environment'))
    except ValueError as e:raise HTTPException(422,str(e))
    current_variant=getattr(lab.aircraft,'variant',None) or getattr(lab.aircraft,'airframe_variant',None)
    if not current_variant:
        raise HTTPException(409,'Loaded aircraft identity is unavailable; environment was not changed')
    requested_variant=request.get('airframe_variant')
    if requested_variant is not None and requested_variant!=current_variant:
        raise HTTPException(409,'Environment change cannot replace the loaded aircraft; select the aircraft separately')
    if os.environ.get('VTX_ENFORCE_RELEASE')=='1' and current_variant!='r6':
        raise HTTPException(409,'Loaded aircraft does not match the enforced release; environment was not changed')
    target_world=lab.world if getattr(lab.world,'environment_key','airport')==env_key else make_world(env_key,seed=lab.world.seed)
    start_cfg=request.get('start_configuration') or getattr(lab.aircraft,'start_configuration','vtol')
    dep=request.get('departure') if request.get('departure') is not None else list(target_world.default_departure)
    dest=request.get('destination') if request.get('destination') is not None else list(target_world.default_destination)
    try:selection=Mission(environment=env_key,airframe_variant=current_variant,departure=dep,destination=dest,departure_heading_deg=request.get('departure_heading_deg'),phantom={'start_configuration':start_cfg})
    except ValidationError as e:raise HTTPException(422,str(e))
    point=MapPoint(*selection.departure)
    verdict = landing_support(target_world, point, 'departure', selection.airframe_variant)
    if not verdict.valid:raise HTTPException(422,verdict.reason)
    lab.preview_generation+=1
    generation=lab.preview_generation
    def build():
        if phantom_live.is_phantom_variant(selection.airframe_variant):
            aircraft=phantom_live.make_aircraft(target_world,selection)
        else:
            aircraft=Aircraft(target_world,selection.gear_variant,selection.reference_rpm,
                              fuel_kg=selection.fuel_kg,airframe_variant=selection.airframe_variant,
                              engine_power_limit_kw=selection.engine_power_limit_kw,
                              atmosphere_model=selection.atmosphere_model,wind_world_mps=selection.wind_world_mps)
        place_at_departure(aircraft, selection, verdict.terrain_z_m)
        return aircraft
    try:aircraft=await asyncio.to_thread(build)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    if lab.active or generation!=lab.preview_generation:
        raise HTTPException(409,'The flight or model selection changed while the environment was loading')
    if getattr(aircraft,'is_phantom',False):
        from .phantom import identity as aircraft_identity_pins
        check=aircraft_identity_pins.verify(aircraft,experimental=bool(aircraft.experimental_overrides),runtime_source_sha256=RUNTIME_SOURCE_SHA256)
        if check['pinned'] and check['mismatches']:
            raise HTTPException(409,'Aircraft identity mismatch: '+check['status'])
        aircraft._identity=check
    try:lab._remember_inspection_selection(selection,aircraft,target_world)
    except ValueError as e:raise HTTPException(409,str(e))
    lab.world=target_world;lab.flight_world=target_world;lab.aircraft=aircraft
    lab.last_obs=None;lab.last_sensor_t=-1.;lab.obs_id=0;lab.observations={}
    lab.action_log=[];lab.run_id=None;lab.mission=None;lab.error=None;lab.paused=False
    return dict(ok=True,environment=env_key,world=lab.world_snapshot(),view=lab.view())
@app.post('/api/objective')
async def set_objective(request:dict):
    if not lab.active:raise HTTPException(409,'No active flight')
    if request.get('run_id') is not None and request['run_id']!=lab.run_id:
        raise HTTPException(409,'Flight changed; refresh before setting an objective')
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
    lab.log('pilot_provider_failed',dict(pilot_id=lab.pilot_owner,reason=reason.strip(),pilot_epoch=lab.pilot_epoch))
    lab.pilot_epoch += 1
    lab.pilot_owner = None
    lab.pending_pilot = None
    try:
        lab.fallback_controller = R6HoldController(lab.sensor_observation())
        lab.pilot_owner = 'r6-deterministic-hold'
        lab.fallback_status = dict(state='active', reason=reason.strip())
    except (ValueError, KeyError, TypeError) as exc:
        lab.fallback_controller = None
        lab.fallback_status = dict(state='unavailable', reason=str(exc))
    lab.log('pilot_fallback', lab.fallback_status)
    lab.checkpoint(force=True)
    return dict(run_id=lab.run_id, pilot_epoch=lab.pilot_epoch,
                pilot_owner=lab.pilot_owner, objective=lab.objective, fallback=lab.fallback_status)
@app.get('/api/validate')
async def validate(x:float,y:float,variant:str|None=None,ignore_scenery_collisions:bool=False,purpose:str='mission'):
    from dataclasses import asdict
    world=lab.world_for(ignore_scenery_collisions)
    if purpose == 'departure':
        return asdict(landing_support(world,MapPoint(x,y),purpose,variant))
    if phantom_live.is_phantom_variant(variant):
        from .phantom.mission import validate_phantom
        return validate_phantom(world,MapPoint(x,y),variant)
    return asdict(world.validate(MapPoint(x,y),'mission'))
@app.post('/api/mission')
async def mission(request:Mission):
    if 'airframe_variant' not in request.model_fields_set:
        raise HTTPException(409,'Select an aircraft explicitly before starting a mission')
    try:return lab.start(request)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/destination')
async def destination(request:dict):
    if request.get('run_id') is not None and request['run_id'] != lab.run_id:
        raise HTTPException(409, 'Flight changed; refresh before changing its destination')
    try:
        return lab.update_destination(request.get('destination'))
    except ValueError as e:
        raise HTTPException(422,str(e))

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
    try:
        result=lab.accept_action(a)
        if lab.run_id:
            get_recorder(lab.data_root).emit(dict(schema_version=1,run_id=lab.run_id,
                decision_id=None,wall_utc=datetime.now(timezone.utc).isoformat(),
                kind='pilot_action_accepted',payload=dict(action=body,result=result)))
        return result
    except HTTPException as e:
        lab.log('rejected_pilot_action',dict(request=a.model_dump(by_alias=True),reason=e.detail))
        raise
@app.post('/api/stop')
async def stop(request:dict):return lab.stop(str(request.get('reason','Operator ended sortie')))
@app.post('/api/save-flight')
async def save_flight(request:dict):return lab.save_flight_for_switching(request.get('run_id'))

@app.post('/api/restart-flight')
async def restart_flight(request:dict):
    if not lab.active or not lab.run_id or request.get('run_id') != lab.run_id:
        raise HTTPException(409,'Flight changed; refresh before restarting')
    saved = json.loads((lab.log_path/'metadata.json').read_text(encoding='utf-8'))['request']
    if not saved.pop('fuel_kg_explicit', True):
        saved.pop('fuel_kg', None)
    selection = Mission(**{**saved, 'destination':lab.mission['destination'],
                           'time_scale':lab.time_scale, 'authority':lab.authority})
    lab.save_flight_for_switching(lab.run_id)
    return lab.start(selection)
@app.get('/api/saved-flights')
async def saved_flights():return lab.saved_flights()
@app.post('/api/restore-flight')
async def restore_flight(request:dict):return lab.restore_saved_flight(request.get('run_id'))
@app.get('/api/checkpoint-recovery')
async def checkpoint_recovery():
    path=lab.checkpoint_path
    if not lab.recovery_blocked or not path.is_file():return dict(available=False)
    try:
        data=path.read_bytes();state=json.loads(data)
        digest=hashlib.sha256(data).hexdigest();txn=lab.data_root/'pilot/fork-transactions'/(digest+'.json')
        transaction=json.loads(txn.read_text(encoding='utf-8')) if txn.is_file() else None
        physics=state.get('plant',{}) if state.get('schema')=='phantom-2' else state.get('physics',{})
        reason=lab.error or ''
        fork_available=transaction is None and any(s in reason for s in ('extends beyond the checkpoint','evidence is incomplete or unreadable'))
        if not fork_available and transaction is None and state.get('schema') in (2,'phantom-2'):
            def malformed_evidence():
                try:lab._verify_evidence_tail(lab.data_root/'evidence/flights'/state['run_id'],physics['time'],state['schema']=='phantom-2')
                except json.JSONDecodeError:return True
                except (ValueError,KeyError,OSError,TypeError):return False
                return False
            fork_available=await asyncio.to_thread(malformed_evidence)
        return dict(available=True,run_id=state.get('run_id'),checkpoint_sha256=digest,
                    checkpoint_time_s=physics.get('time'),reason=lab.error,transaction=transaction,fork_available=fork_available)
    except (OSError,ValueError):return dict(available=False,reason='Checkpoint cannot be read; retained for inspection')
@app.post('/api/fork-checkpoint')
async def fork_checkpoint(request:dict):return lab.fork_checkpoint_continuation(request.get('run_id'),request.get('checkpoint_sha256'))
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
        if not math.isfinite(value) or not 0<=value<=1:raise HTTPException(422,'Stability assistance must be 0â€“1')
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
        if not .01<=value<=1 or not math.isfinite(value):raise HTTPException(422,'Time scale must be .01â€“1')
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
        try:
            s=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(s,dict) or s.get('run_id')!=path.parent.name:
                raise ValueError('Summary does not identify its flight')
            row={k:v for k,v in s.items() if k!='final'}
        except (OSError,ValueError,TypeError):
            row=dict(run_id=path.parent.name,outcome='summary unreadable; evidence retained',
                     simulated_seconds=None,decisions=None,active=False)
        try:
            meta=json.loads((path.parent/'metadata.json').read_text(encoding='utf-8'))
            if meta.get('run_id')==path.parent.name:
                if meta.get('continuation'):row['continuation']=meta['continuation']
                if not row.get('mission') and isinstance(meta.get('mission'),dict):row['mission']=meta['mission']
        except (OSError,ValueError,TypeError,AttributeError):
            pass  # Summary remains independently available for inspection.
        m=row.get('mission')
        if not isinstance(m,dict):m={}
        if m.get('environment') and 'environment' not in row:
            row['environment']=m.get('environment')
            row['environment_key']=m.get('environment_key')
            row['environment_label']=m.get('environment_label')
        result.append(row)
    # A retained parent of a checkpoint continuation has no summary. Keep it
    # discoverable without inventing an outcome or writing to its evidence.
    for path in sorted((lab.data_root/'evidence/flights').glob('*/metadata.json'),reverse=True):
        run_id=path.parent.name
        if (path.parent/'summary.json').exists() or (lab.active and lab.run_id==run_id):continue
        try:
            meta=json.loads(path.read_text(encoding='utf-8'))
            if meta.get('run_id')!=run_id:continue
            mission=meta.get('mission') or {}
            row=dict(run_id=run_id,outcome='unfinished; evidence retained',simulated_seconds=None,
                     decisions=None,active=False,mission=mission,
                     environment=mission.get('environment'),environment_key=mission.get('environment_key'),
                     environment_label=mission.get('environment_label'))
            if meta.get('continuation'):row['continuation']=meta['continuation']
            result.append(row)
        except (OSError,ValueError,TypeError):
            continue
    if lab.active and lab.run_id:
        m=lab.mission or {}
        row=dict(run_id=lab.run_id,outcome='in progress',simulated_seconds=float(lab.aircraft.data.time),
                             decisions=lab.action_sequence,active=True,mission=lab.mission,
                             environment=m.get('environment'),environment_key=m.get('environment_key'),
                             environment_label=m.get('environment_label'))
        meta_path=lab.log_path/'metadata.json'
        if meta_path.exists():
            meta=json.loads(meta_path.read_text(encoding='utf-8'))
            if meta.get('continuation'):row['continuation']=meta['continuation']
        result.insert(0,row)
    return result


@app.get('/api/archive/runs')
async def archive_runs():
    """Read legacy PC summary records without writing to their archives."""
    local=os.environ.get('LOCALAPPDATA')
    if not local:
        return dict(records=[],available=False)
    records=[]
    for source in ('r6-live','unified-live'):
        folder=Path(local)/'VTX'/source/'evidence'/'flights'
        for path in sorted(folder.glob('*/summary.json'),reverse=True)[:200]:
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
                records.append(dict(source=source,run_id=data.get('run_id',path.parent.name),
                    recorded_outcome=data.get('outcome'),simulated_seconds=data.get('simulated_seconds'),
                    mission=data.get('mission'),record_status='historical summary; original assessment'))
            except (OSError,ValueError,TypeError):
                continue
    return dict(records=records,available=True)

@app.get('/api/archive/r6-pilot-record')
async def r6_historical_pilot_record():
    """Expose the retained pilot record without serving the whole pilot directory."""
    path=ROOT/'pilot/flight_records/20261103T125202-92636c/PILOT_RECORD.md'
    if not path.is_file():raise HTTPException(404,'Historical R6 pilot record is unavailable')
    return FileResponse(path,media_type='text/plain; charset=utf-8')

@app.get('/api/runs/{run_id}/findings')
async def run_findings(run_id: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):
        raise HTTPException(400,'Invalid run ID')
    folder=lab.data_root/'evidence'/'flights'/run_id
    result={}
    for key,filename in (('pilot_summary','pilot_summary.json'),('engineering_findings','engineering_findings.json')):
        path=folder/filename
        if path.is_file():
            result[key]=json.loads(path.read_text(encoding='utf-8'))
    if not result:
        raise HTTPException(404,'No failure summaries recorded for this run')
    return result


def read_decision_timeline(path, limit=200):
    """Return recent significant events with bounded memory; the full log remains intact."""
    from collections import deque
    events=deque(maxlen=limit);count=0
    kinds={'objective_changed','objective_completed','pilot_decision','pilot_handover',
           'pilot_takeover_pending','pilot_takeover_applied','pilot_provider_failed',
           'pending_pilot_failed','authority_change','supported_landing_observed','sortie_end'}
    with (gzip.open(path,'rt',encoding='utf-8') if path.suffix=='.gz' else path.open(encoding='utf-8')) as stream:
        for line in stream:
            try: row=json.loads(line)
            except json.JSONDecodeError:
                if not line.endswith('\n'):continue  # live writer may be partway through its last line
                raise
            kind=row.get('kind')
            if kind not in kinds:continue
            payload=row.get('payload') or {}
            if kind=='pilot_decision':
                issued=payload.get('issued') or {}
                detail=dict(decision=payload.get('decision'),sequence=payload.get('sequence'),
                            pilot_id=issued.get('pilot_id'),authority=issued.get('authority'))
            elif kind=='sortie_end':
                detail={k:payload.get(k) for k in ('outcome','reason','landing_assessment')}
            else: detail=payload
            events.append(dict(kind=kind,t_s=row.get('t_s'),detail=detail));count+=1
    return dict(events=list(events),total_events=count,truncated=count>len(events))

@app.get('/api/timeline/{run_id}')
async def timeline(run_id:str):
    if not run_id.replace('-','').isalnum():raise HTTPException(422,'Invalid run ID')
    path=lab.data_root/'evidence/flights'/run_id/'events.jsonl'
    compressed=path.with_suffix('.jsonl.gz')
    if not path.exists() and not compressed.exists():raise HTTPException(404,'Run not found')
    return await asyncio.to_thread(read_decision_timeline,path if path.exists() else compressed)

def recorded_phantom_wheel_geometry(run_dir):
    """Read only explicitly described, identity-matched historical tyre cylinders.

    Do not compile a historical model, resolve includes or use the currently
    selected aircraft. Unsupported or incomplete evidence stays unavailable.
    """
    unavailable=dict(status='unavailable')
    try:
        metadata=json.loads((run_dir/'metadata.json').read_text(encoding='utf-8'))
        airframe=metadata['airframe']
        revision=airframe['airframe_variant']
        expected=airframe['model_xml_sha256']
        if (metadata['run_id']!=run_dir.name or not isinstance(revision,str) or
                not revision.startswith('phantom-') or not isinstance(expected,str) or
                not re.fullmatch(r'[0-9a-f]{64}',expected)):
            return unavailable
        xml=(run_dir/'model.xml').read_bytes()
        if len(xml)>16_000_000 or hashlib.sha256(xml).hexdigest()!=expected:
            return unavailable
        # Includes/default-defined geometry cannot safely be inferred by this
        # deliberately narrow reader, nor should this audit parse entities.
        if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b',xml,re.IGNORECASE):
            return unavailable
        root=ET.fromstring(xml)
        if root.tag!='mujoco' or any(e.tag=='include' for e in root.iter()):
            return unavailable
        geom_pose_attrs=('type','size','pos','fromto','quat','euler','axisangle','xyaxes','zaxis')
        for default in root.iter('default'):
            if any(any(g.get(a) is not None for a in geom_pose_attrs) for g in default.findall('geom')):
                return unavailable
        parents={child:parent for parent in root.iter() for child in parent}
        geometry={}
        for pod in ('FL','FR','RL','RR'):
            matches=[e for e in root.iter('geom') if e.get('name')==f'tyre_{pod}']
            if len(matches)!=1:return unavailable
            geom=matches[0];body=parents.get(geom)
            if (body is None or body.tag!='body' or body.get('name')!=f'pod_{pod}_wheel' or
                    not any(j.get('name')==f'pod_{pod}_wheel' for j in body.findall('joint')) or
                    parents.get(body) is None or parents[body].get('name')!=f'pod_{pod}' or
                    parents.get(parents[body]) is None or parents[parents[body]].get('name')!='airframe' or
                    any(body.get(a) is not None for a in ('quat','euler','axisangle','xyaxes','zaxis')) or
                    geom.get('class') is not None or body.get('childclass') is not None or
                    geom.get('type')!='cylinder' or any(geom.get(a) is not None for a in
                        ('fromto','quat','euler','axisangle','xyaxes'))):
                return unavailable
            size=[float(v) for v in geom.attrib['size'].split()]
            axis=[float(v) for v in geom.attrib['zaxis'].split()]
            pos=[float(v) for v in geom.get('pos','0 0 0').split()]
            body_pos=[float(v) for v in body.get('pos','0 0 0').split()]
            if (len(size)!=2 or not all(math.isfinite(v) and v>0 for v in size) or
                    len(axis)!=3 or not all(math.isfinite(v) for v in axis) or
                    abs(axis[0])>1e-9 or abs(axis[2])>1e-9 or abs(axis[1])<1e-9 or
                    len(pos)!=3 or not all(math.isfinite(v) and abs(v)<1e-9 for v in pos) or
                    len(body_pos)!=3 or not all(math.isfinite(v) and abs(v)<1e-9 for v in body_pos)):
                return unavailable
            geometry[pod]=dict(radius_m=size[0],half_width_m=size[1])
        return dict(status='recorded-model-verified',model_xml_sha256=expected,
                    airframe_variant=revision,wheels=geometry)
    except (OSError,ValueError,TypeError,KeyError,ET.ParseError):
        return unavailable


def recorded_replay_context(run_dir):
    """Read replay identity without changing the selected aircraft or world.

    An absent historical fingerprint is not evidence that the current terrain
    or a similarly named visual is the one originally recorded.
    """
    context=dict(environment=None,visual=None)
    try:
        meta=json.loads((run_dir/'metadata.json').read_text(encoding='utf-8'))
        if meta.get('run_id')!=run_dir.name:return context
        mission=meta.get('mission') or {}
        env=mission.get('environment_identity') or {}
        fingerprint=env.get('displayed_world_sha256')
        if (env.get('scheme')=='vtx-world-v1' and isinstance(env.get('seed'),int) and
                not isinstance(env.get('seed'),bool) and
                all(isinstance(mission.get(k),str) and mission[k] for k in
                    ('environment_key','environment','environment_version')) and
                isinstance(fingerprint,str) and re.fullmatch(r'[0-9a-f]{64}',fingerprint)):
            context['environment']=dict(key=mission['environment_key'],id=mission['environment'],
                version=mission['environment_version'],seed=env['seed'],displayed_world_sha256=fingerprint)
        airframe=meta.get('airframe') or {}
        variant=airframe.get('airframe_variant');model=airframe.get('model_xml_sha256')
        config=airframe.get('config_sha256');asset=airframe.get('render_asset')
        if (not isinstance(variant,str) or not variant or not isinstance(model,str) or
                not re.fullmatch(r'[0-9a-f]{64}',model) or
                (config is not None and (not isinstance(config,str) or not re.fullmatch(r'[0-9a-f]{64}',config))) or
                not isinstance(asset,str) or not re.fullmatch(r'/assets/[A-Za-z0-9_.-]+\.glb',asset)):
            return context
        xml=(run_dir/'model.xml').read_bytes()
        if len(xml)>16_000_000 or hashlib.sha256(xml).hexdigest()!=model:return context
        identity_path=run_dir/'aircraft_identity.json'
        if identity_path.exists():
            identity=json.loads(identity_path.read_text(encoding='utf-8'))
            if (identity.get('variant')!=variant or identity.get('model_xml_sha256')!=model or
                    identity.get('render_asset')!=asset or identity.get('config_sha256')!=config):
                return context
            digest=identity.get('render_asset_sha256');identity_source='aircraft_identity.json'
        else:
            # R6 runs have no Phantom aircraft_identity.json; new runs record
            # their actual public asset in the mission-start server snapshot.
            manifest=meta.get('server_frontend_identity') or {}
            files=manifest.get('files') or {}
            entry=files.get(asset.lstrip('/')) or {}
            if manifest.get('scheme')!='vtx-server-public-tree-v1':return context
            digest=entry.get('sha256');identity_source='server-frontend-snapshot'
        if (isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest) and
                asset_sha256(asset)==digest):
            context['visual']=dict(variant=variant,model_xml_sha256=model,config_sha256=config,render_asset=asset,
                render_asset_sha256=digest,identity_source=identity_source,
                status='server-asset-matches-record',browser_loaded_verified=False)
    except (OSError,ValueError,TypeError,AttributeError):
        pass
    return context


def read_replay_frames(path, limit=1200):
    """Bound replay memory while retaining the first and last physical states."""
    frames=[]; stride=1; count=0; last=None
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:
        for line in stream:
            try:row=json.loads(line)
            except json.JSONDecodeError:
                if not line.endswith('\n'):continue
                raise
            if row['kind']!='physics_audit':continue
            last=row['payload']
            if count % stride == 0:frames.append((count,last))
            count+=1
            if len(frames)>limit:
                frames=frames[::2];stride*=2
    if count and frames[-1][0]!=count-1:
        if len(frames)>=limit:frames.pop()
        frames.append((count-1,last))
    wheel_source=recorded_phantom_wheel_geometry(path.parent)
    output=[v for _,v in frames]
    if wheel_source['status']=='recorded-model-verified':
        for frame in output:
            if not isinstance(frame,dict):continue
            provenance=frame.get('provenance') or {}
            phantom=frame.get('phantom')
            if (isinstance(phantom,dict) and isinstance(provenance,dict) and
                    provenance.get('model_xml_sha256')==wheel_source['model_xml_sha256'] and
                    provenance.get('airframe_variant')==wheel_source['airframe_variant'] and
                    frame.get('variant')==wheel_source['airframe_variant'] and
                    'wheel_collision_geometry' not in phantom):
                phantom['wheel_collision_geometry']=wheel_source['wheels']
                phantom['wheel_collision_geometry_source']='recorded-model-verified'
    return dict(mode='POST_FLIGHT_AUDIT_ONLY',frames=output,
                recorded_context=recorded_replay_context(path.parent),recorded_wheel_geometry=wheel_source,
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
    loop=asyncio.get_running_loop()
    next_send=loop.time()
    interval=None
    try:
        while True:
            delay=next_send-loop.time()
            if delay>0:
                await asyncio.sleep(delay)
            try:
                snapshot=lab.view()
            except Exception:
                next_send=loop.time()+.05
                interval=None
                continue
            await ws.send_json(snapshot)
            period=.25 if lab.paused or not lab.active else .1
            sent_at=loop.time()
            if period!=interval:
                next_send=sent_at+period
            else:
                # Skip missed slots and avoid sending a second frame immediately after a stall.
                slots=max(1,math.ceil((sent_at+period/2-next_send)/period))
                next_send+=slots*period
            interval=period
    except (WebSocketDisconnect,RuntimeError):pass
from .experiments import install_experiment_routes
install_experiment_routes(app, get_lab, Laboratory, Mission, parse_action, DT)

app.mount('/docs/phantom',StaticFiles(directory=ROOT/'docs/phantom'),name='phantom_docs')
app.mount('/evidence',StaticFiles(directory=ROOT/'evidence'),name='evidence')
# Vercel serves public/ as CDN assets and omits it from the function bundle.
if not os.environ.get('VERCEL') or (ROOT/'public/index.html').is_file():
    app.mount('/',StaticFiles(directory=ROOT/'public',html=True),name='frontend')
