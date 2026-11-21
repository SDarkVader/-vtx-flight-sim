import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {mergeGeometries} from './vendor/BufferGeometryUtils.js';
import {tiltFromDirection} from './tilt-direction.js?v=fan-direction-6';
import {zoomDistance} from './camera-zoom.js?v=1';
import {rotorVisualOffset} from './rotor-visual.js?v=1';
import {createPoseInterpolator} from './vtx-env/pose-interpolation.js?v=1';
const poseInterpolator=createPoseInterpolator();
import {physicalCameraTarget,physicalAircraftPosition} from './physical-camera-target.js?v=2';
import {cockpitAxes} from './cockpit-axes.js?v=1';
import {renderAttitudeIndicator} from './attitude-display.js?v=1';
import {createViewPreferenceStore} from './view-preferences.js?v=1';
import {createWorldSynchronizer,worldMatches} from './world-sync.js?v=1';
import {replayFrameAsset,replayCockpitReadings} from './replay-presentation.js?v=1';
import {createSuspensionSchematic,suspensionSchematicDescriptor} from './suspension-schematic.js?v=1';
import {knownAircraft, flownEvidence} from './aircraft-selection.js?v=1';
import {missionDeparture} from './mission-departure.js?v=20261116-start';
import {startupFrameReady} from './startup-visibility.js?v=20261116-start';
import {cockpitTelemetry} from './cockpit-telemetry.js?v=1';
import {isCockpitObstruction,setCockpitVisibility} from './cockpit-visibility.js?v=20261117-clear-sight-4';
import {isArgonRotorHousing} from './argon-cutaway.js?v=3';
// Vader's Taxis environment (visual only; physics collision comes from world.py).
import {buildSky} from './vtx-env/sky.js?v=1';
import {buildTerrain,makeHills,makeSkyline,makeFarForest,makeWater} from './vtx-env/landscape.js?v=1';
import {buildVaderland} from './vtx-env/vaderland/landscape.js';
import {buildBuildings} from './vtx-env/buildings.js?v=3';
import {buildAirfield} from './vtx-env/airfield.js?v=20261116-runway-1';
import {buildHarbour,createHarbourControls,harbourOverviewView,setBoatCockpit,setBoatLighting} from './vtx-env/harbour.js?v=20261118-selector';
import {boatCameraView} from './vtx-env/harbour-camera.js?v=3';
import {createVehicleWorkspace} from './vehicle-workspace.js';
import {loadPinnedGltf,verifiedVisualAssets} from './visual-identity.js';
import {createPhantomAvionics} from './phantom-avionics.js?v=3';
import {updateBoatAvionics} from './boat-avionics.js?v=4';
import {buildTrees,buildForecourt} from './vtx-env/vegetation.js?v=1';
import {enhanceAircraft} from './vtx-env/aircraft-look.js?v=20261117-cutaway';
import {preparePhysicalVisual} from './vtx-env/physical-visual.js?v=1';
import {buildVolcanoBasement} from './vtx-env/volcano-basement.js?v=1';
import {TacticalMinimap, liveMapObservation} from './vtx-env/tactical-minimap.js?v=20261117-scale-zoom';
import {buildServiceRoads} from './vtx-env/service-roads.js?v=2';
import {createFreeCamera} from './free-camera.js?v=20261116-runway-1';
import {createVisualAirTraffic,clearOfPhysicalAircraft} from './vtx-env/visual-air-traffic.js?v=3';
import {RIDE_JOURNEYS,buildRideJourney} from './vtx-env/visual-ride-journeys.js?v=3';
import {buildRideTrajectory,sampleRideTrajectory,inspectRideClearance} from './vtx-env/ride-trajectory.js?v=1';
import {attachVisualPhantom,animateVisualPhantom} from './vtx-env/visual-phantom-animation.js?v=2';
import {createAirportOperations} from './vtx-env/airport-operations.js?v=20261117-traffic-10';
import {VEHICLE_MODELS,DEFAULT_VISUAL_MODEL} from './vtx-env/vehicle-registry.js?v=2';
import {makeAirportModel} from './vtx-env/airport-models.js?v=1';
import {airportViewSelection,sceneryPoseAt,sceneryPassengerSeat,sceneryPassengerSight} from './scenery-view.js?v=20261117-traffic-10';
import {attachAirportEnergyEffects} from './vtx-env/airport-energy-effects.js?v=1';
import {attachPhantom,updatePhantom,detachPhantomEffects} from './vtx-env/phantom-look.js?v=20261118-a10d';import {createPhantomPanel} from './phantom-controls.js?v=20261118-selector-a10d';let phantomRig=null,phantomPanel=null; // Phantom hooks (render + phantom-fbw-1 panel)

const $=id=>document.getElementById(id);
const phantomMissionNote=document.createElement('p');
phantomMissionNote.className='muted small';
phantomMissionNote.textContent='Phantom inspection uses its own power plant, fuel, and fly-by-wire controls. Start a mission to enable them; the R4–R6 drive settings do not apply.';
$('airframe').closest('label').after(phantomMissionNote);
const windOptions=$('wind-east').closest('.coordinates');
const legacyMissionOptions=[$('initial-fuel').closest('.coordinates'),$('fuel-note'),$('drive').closest('label'),$('power-limit').closest('label'),$('gear').closest('label'),$('atmosphere-model').closest('label'),windOptions,windOptions.nextElementSibling];
function setMissionOptions(variant){
 const phantom=variant.startsWith('phantom');
 for(const node of legacyMissionOptions)node.style.display=phantom?'none':'';
 phantomMissionNote.style.display=phantom?'':'none';
 $('phantom-start-label').style.display=phantom?'':'none';
}
setMissionOptions($('airframe').value);
function showRevision(view) {
 if(view.inspection_selection_known===false && !view.active){const node=$('revision');node.textContent='No aircraft selected';node.title='Choose a vehicle to load its physical model.';node.style.color='';return;}
 const provenance=view.rendering_truth?.provenance||{};
 const config=view.observation?.configuration?.config_sha256||provenance.config_sha256;
 const physics=provenance.physics_revision||(config?`config ${config.slice(0,12)}`:'physics identity unavailable');
 const runtime=view.runtime_source_sha256;
 const node=$('revision');
 const id=view.observation?.configuration?.identity;
 const badge=id?(id.verified?' · IDENTITY VERIFIED':id.experimental?' · EXPERIMENTAL CONFIG':id.pinned?' · IDENTITY MISMATCH':' · not pinned'):'';
 const visualPin=verifiedVisualAssets.has(provenance.render_asset?.split('?')[0])?' · VISUAL PIN VERIFIED':'';
 const visual=id?.render_asset_sha256?` · visual ${id.render_asset_sha256.slice(0,8)}`:'';
 const commit=id?.git_commit?` · git ${id.git_commit.slice(0,7)}`:'';
 node.textContent=`${provenance.revision||'unknown model'} · ${physics}${visual}${commit}${runtime?' · code '+runtime.slice(0,8):''}${badge}${visualPin}`;
 node.style.color=id&&id.pinned&&!id.verified&&!id.experimental?'#ff7a6b':'';
 node.title=`Model: ${provenance.revision||'unknown'}; physics: ${provenance.physics_revision||'parameter configuration'}; config SHA-256: ${config||'not supplied'}; model XML SHA-256: ${provenance.model_xml_sha256||'not supplied'}; runtime SHA-256: ${runtime||'not supplied'}${id?`; parameter file SHA-256: ${id.parameter_file_sha256}; visual asset: ${id.render_asset} SHA-256 ${id.render_asset_sha256}; git commit: ${id.git_commit||'not a git checkout'}; identity: ${id.status}`:''}`;
}
import {sceneryClock} from './vtx-env/vaderland/scenery-clock.js';
const cityClock=sceneryClock();
let last=null,world=null,model=null,pick='a',cameraMode='chase',replayFrames=null,replayFrame=0,replayContext=null;
let departure=[-700,0],destination=[-50,20],track=[],lastDecision='',lastRun=null;
let departureExplicit=false,inspectionDepartureSynced=false,missionTransition=null,visualOnlyOffline=false;
let trackRun=null;
const bodyNodes={},pitchMeshes=[];
const rotorSpinAxis=new THREE.Vector3(0,0,1),rotorSpinQ=new THREE.Quaternion();
let latestTruthReceivedMs=0,lastHudUpdateMs=0,panelWasStale=false;
const command={engine:1,collective_deg:[0,0,0,0],tilt_deg:[[0,0],[0,0],[0,0],[0,0]],cabin_deg:[0,0,0],cabin_level:true};
let dirty=false,manualBeat=0,manualOwned=false,manualRunId=null;
const tiltSpin=[0,0,0,0],tiltSpinAngle=[0,0,0,0];
const manualChannel=new BroadcastChannel('vtx-manual-authority');
manualChannel.onmessage=()=>{manualOwned=false;tiltSpin.fill(0);keys.clear();};
async function api(path,body){
 const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;
}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,6500);}
function guard(fn){return async(...args)=>{try{await fn(...args);}catch(e){toast(e.message);}};}
let checkpointRecovery=null,checkpointRecoveryReason=null;
function updateCheckpointOffer(view){
 if(!view.error||view.active){checkpointRecovery=null;checkpointRecoveryReason=null;$('fork-checkpoint').hidden=true;return;}
 if(view.error===checkpointRecoveryReason)return;
 checkpointRecoveryReason=view.error;$('fork-checkpoint').hidden=true;
 api('/api/checkpoint-recovery').then(info=>{
  if(last?.error!==view.error||last?.active)return;
  checkpointRecovery=info.fork_available&&Number.isFinite(info.checkpoint_time_s)?info:null;
  $('fork-checkpoint').hidden=!checkpointRecovery;
 }).catch(()=>{checkpointRecovery=null;$('fork-checkpoint').hidden=true;});
}
$('fork-checkpoint').onclick=()=>{
 if(!checkpointRecovery)return;
 $('fork-checkpoint-detail').textContent=`Flight ${checkpointRecovery.run_id}, checkpoint at ${checkpointRecovery.checkpoint_time_s.toFixed(2)} s. This continues from that earlier state; the later recorded evidence belongs to the original flight.`;
 $('fork-checkpoint-dialog').showModal();
};
$('fork-checkpoint-confirm').onclick=guard(async()=>{
 if(!checkpointRecovery)return;
 const button=$('fork-checkpoint-confirm');button.disabled=true;
 try{
  const result=await api('/api/fork-checkpoint',{run_id:checkpointRecovery.run_id,checkpoint_sha256:checkpointRecovery.checkpoint_sha256});
  manualOwned=false;dirty=false;keys.clear();phantomPanel?.disengage();stopReplay(false);
  checkpointRecovery=null;$('fork-checkpoint').hidden=true;$('fork-checkpoint-dialog').close();
  toast(`Continuation ${result.run_id} restored paused. Take control and resume when ready.`);
 }finally{button.disabled=false;}
});
function selectedFuel(){const value=Number($('initial-fuel').value);if(!Number.isFinite(value)||value<1||value>110)throw Error('Use total fuel loading between 1 and 110 kg.');return value;}
function selectedWind(){return ['wind-east','wind-north','wind-up'].map(id=>{const value=Number($(id).value);if(!Number.isFinite(value))throw Error('Enter finite wind components.');return value;});}

console.log('VTX: module ready');
const viewport=$('viewport'),scene=new THREE.Scene();const mobile=matchMedia('(pointer:coarse)').matches||innerWidth<800;
const mobileView=mobile;
// Phones default to the lighter display path. The physics and model are unchanged.
const lightweightView=mobile||new URLSearchParams(location.search).has('lite');
// ?fps=N caps the browser's frame rate (for example on a shared or battery-powered machine); otherwise desktop High draws every display frame.
const frameCapMs=(n=>Number.isFinite(n)&&n>0?1000/n:null)(Number(new URLSearchParams(location.search).get('fps')));
// Rendering quality tier (visual only; physics unaffected): phone low, ?lite lite, desktop high, ?quality= overrides.
import {resolveQuality} from './vtx-env/quality.js?v=gfx-20261111-ultra';import {createGround} from './vtx-env/ground.js?v=gfx-20261103-1';import {createLightPool} from './vtx-env/light-pool.js?v=gfx-20261103-1';import {dressWorld} from './vtx-env/world-dressing.js?v=gfx-20261103-1';
import {createPost} from './vtx-env/post.js?v=2';import {createTimeOfDay} from './vtx-env/time-of-day.js?v=2';import {buildAirfieldKit} from './vtx-env/airfield-kit.js?v=1';
import {createGameAudio} from './vtx-env/game-audio.js';
const quality=resolveQuality({mobile,search:location.search});scene.userData.quality=quality.name;
// On phones keep retained-flight actions and indicator bar directly below the flight view.
if (innerWidth <= 800) {
 document.querySelector('header').after($('retry-bar'));
 $('viewport').after(document.querySelector('footer'));
}
const camera=new THREE.PerspectiveCamera(48,1,.1,6000);camera.up.set(0,0,1);camera.position.set(9,-11,8);
const renderer=new THREE.WebGLRenderer({antialias:quality.antialias,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,quality.pixelRatio));renderer.shadowMap.enabled=quality.shadows;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=quality.toneMapping;renderer.toneMappingExposure=quality.exposure;renderer.domElement.style.visibility='hidden';viewport.appendChild(renderer.domElement);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.target.set(0,0,1.4);orbit.enableDamping=true;orbit.enablePan=false;orbit.maxPolarAngle=Math.PI*.49;orbit.minDistance=2;orbit.maxDistance=600;
// Keep pinch gestures on the renderer and avoid two-finger panning fighting the chase target.
orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';
const freeCam=createFreeCamera(camera,renderer,viewport,m=>setCameraMode(m),()=>world);
const sky=buildSky(scene,renderer,{quality}),environment={};
// Desktop-app tier only: post-processing. Day/night is presentation only and never touches the physics.
const post=createPost(renderer,scene,camera,quality);
let irisFeedback='';
document.getElementById('district-view')?.addEventListener('change',event=>{
 const views={tower:[[116.78,-231.08,91.67],[116,-232.63,91.37]],records:[[1002.12,-340.43,11.96],[1003.23,-342.09,11.56]],
  engineering:[[-7,-360,2.1],[28,-302,6.5]],approach:[[923,-325,18],[1050,-325,18]],plaza:[[-151,2257,40],[-183,2325,66]]};
 const view=views[event.target.value];if(!view)return;
 setCameraMode('free');freeCam.teleport(...view);event.target.value='';
});
for(const [id,open] of [['iris-open',true],['iris-close',false]]){
 document.getElementById(id)?.addEventListener('click',async()=>{
  try{const r=await api('/api/scenery/iris',{environment:world?.environment,door:document.getElementById('iris-side').value,open});
   if(last)last.iris=r.iris;irisFeedback='';
  }catch(err){irisFeedback=err.message;}
 });
}
const timeOfDay=createTimeOfDay({scene,sky,renderer,getPost:()=>post,environment});
function audioControl(id,label,title){
 const button=document.createElement('button');
 button.id=id;button.type='button';button.textContent=label;
 button.setAttribute('aria-pressed','false');button.title=title;
 return button;
}
const audioButton=audioControl('game-audio','Audio off','Toggle vehicles and environment sounds');
const musicButton=audioControl('game-music','Music off','Toggle the adaptive race soundtrack');
const gameAudio=createGameAudio(audioButton,musicButton,error=>toast(error.message));
const listenerRight=new THREE.Vector3();
let lightingChoice=new URLSearchParams(location.search).get('time');
function updateLightingButton(){
 const button=document.getElementById('time-of-day');if(!button)return;
 const next=timeOfDay.nextMode;button.textContent=next[0].toUpperCase()+next.slice(1);
 button.title='Current lighting: '+timeOfDay.mode+'. Switch to '+next+'.';
}
const rideCgLocal=[-0.15156246846624952,0.00004531509472356366,0.5529781802070567];
let visualTraffic=null,airportOperations=null,rideRoute=null,rideTime=0,rideLastFrame=0,ridePaused=false,ridePose=null,rideActor=null,ridePlan=null;
let sceneTime=0,sceneScale=1,selectedVehicleId='physical-plant',passengerRide=false;
let pendingRideExteriorMode=null;
let rideEnabled=false;
const trafficPreviewEnabled=true;
{
 const panel=document.createElement('div');panel.id='ride-controls';
 panel.innerHTML=`<label>View <select id="airport-aircraft"><optgroup label="Piloted aircraft"><option value="physical-plant">Your aircraft · physical</option></optgroup><optgroup label="Scenic flights · visual only"><option value="a10-primary">Phantom A10 · scenery</option><option value="r6-flight">Argon R6 · holding scenery</option><option value="r6-training">Argon R6 · training scenery</option><option value="r6-teardrop">Argon R6 · teardrop scenery</option><option value="r6-go-around">Argon R6 · go-around scenery</option><option value="a10-training">Phantom A10 · training scenery</option><option value="r6-holiday">Argon R6 · holiday scenery</option><option value="a10-teardrop">Phantom A10 · teardrop scenery</option><option value="r6-circuit">Argon R6 · circuit scenery</option><option value="a10-holiday">Phantom A10 · holiday scenery</option></optgroup></select></label><label>Camera <select id="airport-camera"><option value="chase">Chase</option><option value="cockpit">Cockpit</option><option value="free">Exterior / free</option><option value="orbit">Top</option></select></label><details id="airport-ops"><summary>Scenic flights</summary><div class="airport-menu"><p class="muted small">Scenery follows visual flight paths. Pilot controls stay with your physical aircraft.</p><label>Journey <select id="ride-route">${RIDE_JOURNEYS.map(r=>`<option value="${r.id}">${r.label}</option>`).join('')}</select></label><label>Direction <select id="ride-direction"><option value="left">Left-hand</option><option value="right">Right-hand</option></select></label><button id="ride-start" type="button">Watch passenger ride</button><label>Traffic <select id="traffic-density"><option value="0">0 scenic aircraft</option><option value="1">1 scenic aircraft</option><option value="2">2 scenic aircraft</option><option value="3">3 scenic aircraft</option><option value="4">4 scenic aircraft</option><option value="5">5 scenic aircraft</option><option value="6">6 scenic aircraft</option><option value="7">7 scenic aircraft</option><option value="8">8 scenic aircraft</option><option value="9">9 scenic aircraft</option><option value="10">10 scenic aircraft</option></select></label><label>Scenery speed <select id="airport-speed"><option value="1">1×</option><option value="2">2×</option><option value="0.5">0.5×</option></select></label><div class="airport-menu-actions"><button id="ride-pause" type="button">Pause scenery</button><button id="ride-restart" type="button">Restart scenery</button></div><span id="ride-progress" aria-live="polite">Loading scenery...</span><div class="airport-menu-actions" id="airport-extra"></div></div></details>`;
 // Airport view controls remain independent of the live aircraft controls.
 document.getElementById('airport-drawer').append(panel);
 // Engineering and flight records remain in the header.
  const cameraTools=$('view-tools');
  const exterior=document.createElement('button');
  exterior.id='ride-exterior';exterior.type='button';exterior.textContent='Show aircraft';
  exterior.title='Pin 360° exterior camera onto the active vehicle';
  const locate=document.createElement('button');
  locate.id='ride-locate';locate.type='button';locate.textContent='Find A10';
  locate.title='Reposition the independent free camera to look at the A10';locate.hidden=true;
  cameraTools.prepend(exterior,locate);
  const nightButton=document.createElement('button');
  nightButton.id='time-of-day';nightButton.type='button';nightButton.textContent='Night';
  nightButton.title='Switch the scene between day and night lighting (visual only)';
  nightButton.onclick=()=>{lightingChoice=timeOfDay.toggle();updateLightingButton();};
  cameraTools.append(nightButton,audioButton,musicButton);
  if(lightingChoice==='night'){timeOfDay.set('night');updateLightingButton();}
  function recenterPhysicalVehicle(){
   if(boatViewId){
    const body=harbourLayer?.boats.get(boatViewId)?.bodies.get('airframe'),q=body?.quaternion;
    const view=q?boatCameraView({position:body.position.toArray(),quaternion_wxyz:[q.w,q.x,q.y,q.z]},{mode:'chase'}):null;
    setCameraMode('chase');
    if(view){camera.position.set(...view.position);orbit.target.set(...view.target);camera.up.set(0,0,1);orbit.update();}
    return;
   }
   const truth=replayFrames?.[replayFrame]||last?.rendering_truth,target=physicalCameraTarget(truth);
   setCameraMode('chase');
   if(target)orbit.target.set(...target);
   camera.up.set(0,0,1);
   camera.position.copy(orbit.target).add(new THREE.Vector3(8.5,-9.5,4.2));
   orbit.update();
  }
  window.addEventListener('vtx-recenter-vehicle',()=>{if(rideEnabled)showRideAircraft('chase');else recenterPhysicalVehicle();});
  exterior.onclick=()=>rideEnabled?showRideAircraft('chase'):recenterPhysicalVehicle();
  locate.onclick=()=>showRideAircraft(cameraMode==='free'?'free':'chase');
 document.getElementById('ride-pause').onclick=()=>{ridePaused=!ridePaused;document.getElementById('ride-pause').textContent=ridePaused?'Resume scenery':'Pause scenery';};
 document.getElementById('ride-restart').onclick=()=>{sceneTime=0;rideTime=0;ridePaused=false;rideLastFrame=performance.now();document.getElementById('ride-pause').textContent='Pause scenery';};
  const changeJourney=()=>{
    const plan=buildRideJourney($('ride-route').value,$('ride-direction').value,rideCgLocal[2]);
    const nextRoute=buildRideTrajectory(plan.points,{cruiseSpeed:plan.speed});
    if(world){const audit=inspectRideClearance(nextRoute,world);if(!audit.ok){toast('Flight route refused: '+audit.failures[0].reason);return;}}
    if(world&&!plan.waypoints.every(p=>Math.abs(p.position[0])<world.half_m&&Math.abs(p.position[1])<world.half_m)){
      toast('Route exceeds this simulation terrain');return;
    }
    ridePlan=plan;rideRoute=nextRoute;
    rideTime=0;rideLastFrame=performance.now();ridePaused=false;
    $('ride-pause').textContent='Pause scenery';
    $('ride-progress').textContent=plan.label+' · '+plan.direction+' circuit · starting at runway';
  };
  $('ride-route').onchange=changeJourney;
  $('ride-direction').onchange=changeJourney;
 function selectAirportView(id,options){
  const choice=airportViewSelection(id,options);
  leaveBoatView();vehicleWorkspace.show(choice.scenery?'passenger':'aircraft');
  selectedVehicleId=choice.id;rideEnabled=choice.scenery;passengerRide=choice.passenger;
  $('airport-aircraft').value=choice.id;
  if(rideEnabled)showRideAircraft('chase');else setCameraMode('chase');
  $('view-mode').textContent=rideEnabled?'SCENERY VIEW · PHYSICAL INSTRUMENTS & CONTROLS':'PHYSICAL STATE · LIVE';
 }
 document.addEventListener('vtx-aircraft-selected',event=>{
  stopReplay(false);
  selectAirportView('physical-plant');
  clearAircraftInput();
  const selected=event.detail, movedWorld=last?.environment?.key!==selected.environment.key;
  updateView(selected);
  if(!selected.active){
   const c=selected.observation.configuration;
   if(!selected.rendering_truth.phantom){
    $('drive').value=c.reference_rpm;$('gear').value=c.gear_variant;$('initial-fuel').value=c.initial_fuel_kg;
    $('power-limit').value=c.engine_power_limit_kw;$('atmosphere-model').value=c.atmosphere_model;
    c.wind_world_mps.forEach((v,i)=>$(['wind-east','wind-north','wind-up'][i]).value=v);
   }
   if(movedWorld)departureExplicit=false;
   const xy=physicalAircraftPosition(selected.rendering_truth)?.slice(0,2);
   if(xy){departure=xy;$('dep').value=xy.join(', ');syncEnvironmentControls(selected.environment.key);}
   if(movedWorld){destination=[...selected.environment.default_destination];$('dest').value=destination.join(', ');}
   updateMarkers();drawMaps(true);
  }
  const target=physicalCameraTarget(selected.rendering_truth);
  if(target){orbit.target.set(...target);camera.up.set(0,0,1);camera.position.copy(orbit.target).add(new THREE.Vector3(8.5,-9.5,4.2));orbit.update();}
 });
 document.addEventListener('vtx-selection-settled',event=>updateView(event.detail));
 document.addEventListener('vtx-ride-scenery',event=>{
  event.preventDefault();
  try{
   if(currentEnvironment!=='airport'||!airportOperations||!visualTraffic)throw Error('Passenger flights are available at Main Airport.');
   const id=event.detail.vehicleId;
   if(!airportOperations.actors.some(actor=>actor.id===id))throw Error('That passenger flight is unavailable.');
   stopReplay(false);selectAirportView(id);
   pendingRideExteriorMode='cockpit';
   setCameraMode('cockpit');
   $('view-mode').textContent='PASSENGER VIEW · SCHEDULED SCENERY';
   toast('Passenger aboard. Your physical aircraft continues independently.');
   event.detail.resolve();
  }catch(error){toast(error.message);event.detail.reject(error);}
 });
 $('ride-start').onclick=()=>{changeJourney();selectAirportView('a10-primary',{passenger:true});$('airport-ops').open=false;};
 $('airport-aircraft').onchange=()=>selectAirportView($('airport-aircraft').value);
 $('airport-aircraft').value='physical-plant';
  $('traffic-density').value=mobile?'3':'5';
 $('traffic-density').onchange=()=>{airportOperations?.setDensity($('traffic-density').value);if(rideEnabled&&!airportOperations?.isVisible(selectedVehicleId))selectAirportView('physical-plant');};
 $('airport-speed').onchange=()=>{sceneScale=Number($('airport-speed').value);};
$('airport-camera').onchange=()=>{const mode=$('airport-camera').value;if(mode==='orbit')$('view-top').click();else if(rideEnabled&&mode==='chase')showRideAircraft('chase');else setCameraMode(mode);saveCameraPreference();};
  $('view-mode').textContent='PHYSICAL STATE - LIVE';
}
const lightPool=createLightPool(scene,quality.localLights);scene.onBeforeRender=(r,s,cam)=>lightPool.update(cam);
const resize=()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);post?.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(viewport);
const worldGroup=new THREE.Group();worldGroup.name='vtx-world';scene.add(worldGroup);
const phantomAvionics=createPhantomAvionics();scene.add(phantomAvionics.root);
let harbourLayer=null,harbourOverviewState=null,harbourViewActive=false,boatViewId=null;
let harbourEnvironment=null,helmRequest=0;
function setBoatFocus(id){
 boatViewId=id;document.documentElement.dataset.boatFocus=id||'';
 try{if(id)sessionStorage.setItem('vtx-helm',id);else sessionStorage.removeItem('vtx-helm');}catch{}
 document.dispatchEvent(new CustomEvent('vtx-vehicle-focus',{detail:{boatId:id}}));
}
function leaveBoatView(){
 ++helmRequest;harbourEnvironment=null;setBoatFocus(null);worldSynchronizer.reconcile();
}
function showHelmStatus(){
 const state=harbourControls.state, boat=state?.boats.find(b=>b.id===boatViewId);
 $('state').textContent=boat?.name||'Waiting for helm';
 $('clock').textContent=boat?state.t_s.toFixed(1)+' s':'—';
 $('view-sync').textContent=boat?boat.variant+' · '+boat.speed_mps.toFixed(2)+' m/s':'Waiting for boat data';
}
function clearAircraftInput(){
 manualOwned=false;dirty=false;keys.clear();tiltSpin.fill(0);phantomPanel?.disengage();
}
function restoreHarbourOverview(){
 harbourViewActive=false;
 if(!harbourOverviewState)return;
 const saved=harbourOverviewState;harbourOverviewState=null;
 if(saved.fog)Object.assign(saved.fog,saved.fogValues);
 camera.near=saved.near;camera.far=saved.far;camera.updateProjectionMatrix();
}
const harbourControls=createHarbourControls({host:document.querySelector('.mission-panel'),api:(path,body)=>api(path+'?airport=true',body),toast,
 onState:(state,options)=>{if(boatViewId&&state?.selectedId&&boatViewId!==state.selectedId)setBoatFocus(state.selectedId);harbourLayer?.update(state,options);drawMaps();},
 onRoutes:visible=>harbourLayer?.setRoutesVisible(visible),
 onFocus:(point,kind,boatId)=>{
  if(!point?.every(Number.isFinite))return;
  if(boatId)setBoatFocus(boatId);
  if(boatId){
   rideEnabled=false;passengerRide=false;pendingRideExteriorMode=null;selectedVehicleId='physical-plant';
   if($('airport-aircraft'))$('airport-aircraft').value=selectedVehicleId;
   vehicleWorkspace.show('boat');cockpitYaw=0;cockpitPitch=0;
   setCameraMode(kind==='boat-cockpit'?'cockpit':'chase');
   $('view-mode').textContent='RICOCHET · LIVE HELM';
   return;
  }
  setCameraMode('free');
  harbourViewActive=true;
  const [x,y,z]=point;
  if(kind==='harbour'&&world?.harbour){
   const view=harbourOverviewView(world.harbour,camera),fog=scene.fog;
   harbourOverviewState={fog,fogValues:fog?.isFog?{near:fog.near,far:fog.far}:{density:fog?.density},near:camera.near,far:camera.far};
   // Fit the complete lake and retain depth precision above its shallow bed.
   // Other camera choices restore the normal airport projection and haze.
   camera.near=view.near;camera.far=Math.max(camera.far,view.far);camera.updateProjectionMatrix();
   if(fog)Object.assign(fog,fog.isFog?{near:view.fogNear,far:view.far}:{density:view.fogDensity});
   freeCam.teleport(view.position,view.target);
  }else{
   freeCam.teleport([x+24,y-30,z+18],point);
  }
 }
});
const vehicleWorkspace=createVehicleWorkspace({host:document.querySelector('.controls-panel'),harbourPanel:harbourControls.panel,
 onAircraft:()=>{
  leaveBoatView();rideEnabled=false;passengerRide=false;selectedVehicleId='physical-plant';
  if($('airport-aircraft'))$('airport-aircraft').value=selectedVehicleId;
  vehicleWorkspace.show('aircraft');setCameraMode('chase');$('view-mode').textContent='PHYSICAL STATE · LIVE';
 },
 onHarbour:()=>{const id=harbourControls.state?.selectedId;if(id)void openBoat(id).catch(error=>toast(error.message));else $('models').click();},
 onChange:clearAircraftInput
});
async function openBoat(id,restoreFocus=false){
 const request=++helmRequest;
 stopReplay(false);
 const airport=world?.harbour&&!worldUnavailable?world:await api('/api/harbour/world');
 if(request!==helmRequest)throw Error('Vehicle selection changed.');
 harbourEnvironment={key:airport.environment,id:airport.id,version:airport.version,seed:airport.seed,displayed_world_sha256:airport.displayed_world_sha256};
 if(world!==airport)buildWorld(airport);
 worldSynchronizer.reconcile();harbourControls.setEnabled(true);
 try{return await harbourControls.chooseBoat(id,restoreFocus,()=>request===helmRequest);}
 catch(error){if(!boatViewId && request===helmRequest)leaveBoatView();throw error;}
}
document.addEventListener('vtx-choose-boat', async event => {
 event.preventDefault();
 try {
  const boat = await openBoat(event.detail.boatId);
  const workspace = document.getElementById('cockpit-workspace');
  if (workspace && !workspace.classList.contains('controls-open')) document.querySelector('button[aria-controls="controls-drawer"]')?.click();
  harbourControls.panel.scrollIntoView({block:'nearest'});
  toast(boat.dockedAt ? 'Ricochet selected. Release mooring to leave the berth.' : 'Ricochet selected.');
  event.detail.resolve();
 } catch (error) {
  toast(error.message);
  event.detail.reject(error);
 }
});
function plane(w,h,color,x,y,z,parent=worldGroup){const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({color,roughness:.95}));m.position.set(x,y,z);m.receiveShadow=true;parent.add(m);return m;}
function makeLabel(text,color='#7cdfcb'){
 const c=document.createElement('canvas');c.width=128;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.beginPath();ctx.arc(64,64,49,0,Math.PI*2);ctx.fill();ctx.fillStyle='#143934';ctx.font='bold 62px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,64,67);const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:true}));sprite.scale.set(1.8,1.8,1.8);scene.add(sprite);return sprite;
}
const markerA=makeLabel('A'),markerB=makeLabel('B','#ffc88b');
 const START_PRESETS={
 airport:[
  ['-700,0','Established runway takeoff point'],
  ['-3885,0','Runway 08 west threshold'],
  ['3885,0','Runway 26 east threshold'],
  ['300,0','Runway station +300 m'],
  ['0,0','Central stand'],
  ['205,-85','South test apron'],
  ['custom','Custom point'],
 ],
 sandbox:[
  ['-700,0','Sandbox Runway 09 threshold'],
  ['0,0','Central test pad'],
  ['400,0','Sandbox Runway East / mid-strip'],
  ['85,45','Hangar roof pad'],
  ['150,-95','Workshop roof pad'],
  ['-100,105','Freight roof pad'],
  ['custom','Custom point'],
 ],
 'r6-valley-20261103':[
  ['0,0','Recorded R6 departure'],
  ['custom','Custom point'],
 ],
};
let currentEnvironment='airport';
function timeTrials(){
 return world?.environment===currentEnvironment ? world.vaderland?.time_trials??[] : [];
}
function showTimeTrial(){
 const output=$('time-trial-status');
 const trials=timeTrials();
 const trial=trials.find(t=>t.spawn.every((v,i)=>v===departure[i]));
 const timed=world?.environment===last?.environment?.key && last?.active;
 const active=trial??(timed ? trials.find(t=>last.course_timing?.[t.course]?.start!=null) : null);
 output.hidden=!active;
 if(!active)return;
 const result=timed ? last.course_timing?.[active.course] : null;
 const marks=[];
 if(result?.last!=null)marks.push('Last '+result.last.toFixed(2)+' s');
 if(result?.best!=null)marks.push('Best '+result.best.toFixed(2)+' s');
 if(result?.splits?.length)marks.push('Split '+result.splits.at(-1).toFixed(2)+' s');
 if(active.format==='air'&&result?.start!=null)marks.push('Gate '+(result.next+1)+' of '+active.gates);
 if(!marks.length)marks.push(result?.start==null?'Cross the start gate to begin':'Lap in progress');
 const text=active.zone+' · '+(active.length_m/1000).toFixed(2)+' km · '+marks.join(' · ');
 if(output.textContent!==text)output.textContent=text;
}
function syncEnvironmentControls(envKey){
 currentEnvironment=[...$('environment-select').options].some(o=>o.value===envKey)?envKey:'airport';
 const select=$('environment-select');
 if(select)select.value=currentEnvironment;
 for(const [id,key] of [['env-airport','airport'],['env-sandbox','sandbox']]){
  const btn=$(id);
  if(!btn)continue;
  const active=currentEnvironment===key;
  btn.classList.toggle('selected',active);
  btn.setAttribute('aria-pressed',String(active));
 }
 const preset=$('start-preset');
 if(preset){
  const opts=currentEnvironment.startsWith('vaderland-') ? [
    ['-3885,0','Runway 08 west threshold'],['3885,0','Runway 26 east threshold'],
    ...(Number(world?.version)>=3?[['2845,-4350','Lantern Gallery · west entrance'],['4900,-4890','Proving ground apron']]:[]),
    ...(world?.environment===currentEnvironment ? (world.vaderland?.vertical_loops??[]).map(track=>[
      track.spawn.join(','),track.name+' access']) : []),
    ...(world?.environment===currentEnvironment ? (world.vaderland?.departure_presets??[]).map(({name,point})=>[
      point.join(','),name]) : []),
    ['custom','Custom point']] : START_PRESETS[currentEnvironment]||START_PRESETS.airport;
  const depKey=departure.join(',');
  function option(val,label){
   const item=document.createElement('option');item.value=val;item.textContent=label;return item;
  }
  const apply=opts.map(([val,label])=>option(val,label));
  const trials=timeTrials();
  if(trials.length){
   const group=document.createElement('optgroup');group.label='Time trial starts';
   group.append(...trials.map(t=>option(t.spawn.join(','),t.course+' · '+t.zone)));
   apply.unshift(group);
  }
  preset.replaceChildren(...apply);
  preset.value=[...preset.options].some(o=>o.value===depKey)?depKey:'custom';
  showTimeTrial();
 }
 const rwyBtn=$('runway-start');
 if(rwyBtn){
  rwyBtn.hidden=currentEnvironment==='r6-valley-20261103';
  rwyBtn.textContent=currentEnvironment==='sandbox'?'Set A: sandbox runway 09 start':'Set A: runway west start';
  rwyBtn.title=currentEnvironment==='sandbox'?'Sandbox runway 09 threshold at X -700 m, Y 0 m (1,650 m takeoff roll along +X)':'Extended runway west threshold at X -3885 m, Y 0 m';
 }
 const caption=$('scene-caption');
 if(caption){
  caption.innerHTML=currentEnvironment.startsWith('vaderland-')
   ?'<span>VADERLAND / ALPINE COAST</span><p>16 × 16 km · Runway 08/26 · western sound and northern divide</p>'
   :currentEnvironment==='r6-valley-20261103'
   ?'<span>HISTORICAL R6 / VALLEY</span><p>1,000 × 1,000 m · recovered terrain and obstacles · floor depends on aircraft</p>'
   :currentEnvironment==='sandbox'
   ?'<span>STAGE 1 / VALLEY TEST RANGE</span><p>2,000 × 2,000 m · 1,900 m east-west runway, terrain and ground contact</p>'
   :'<span>VTX / EXTENDED AIRFIELD</span><p>7,800 m runway · broad level approaches · surrounding hills retained</p>';
 }
}
function clearWorldGroup(){
 restoreHarbourOverview();
 environment.vaderland?.dispose();environment.vaderland=null;
 harbourLayer?.dispose();harbourLayer=null;
 const keepTextures=new Set([markerA.material?.map,markerB.material?.map].filter(Boolean));
 for(const child of [...worldGroup.children]){
  worldGroup.remove(child);
  const geometries=new Set(),materials=new Set(),textures=new Set();
  child.traverse(n=>{if(!n.isMesh&&!n.isLineSegments&&!n.isPoints)return;if(n.geometry)geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture&&!keepTextures.has(v))textures.add(v);}});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
 }
 environment.buildings=null;environment.kit=null;environment.volcano=null;environment.serviceRoads=null;environment.dressing=null;
 lightPool.clear?.();
}
function surfaceZ(x,y){if(!world)return 0;const n=world.heights_m.length,half=world.half_m,u=THREE.MathUtils.clamp((x+half)/(2*half)*(n-1),0,n-1.00001),v=THREE.MathUtils.clamp((y+half)/(2*half)*(n-1),0,n-1.00001),i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,h=world.heights_m;let z=a>b?(1-a)*h[j][i]+(a-b)*h[j][i+1]+b*h[j+1][i+1]:(1-b)*h[j][i]+(b-a)*h[j+1][i]+a*h[j+1][i+1];for(const o of world.obstacles){if(o.kind==='box'&&Math.abs(x-o.center[0])<=o.half[0]&&Math.abs(y-o.center[1])<=o.half[1])z=Math.max(z,o.center[2]+o.half[2]);}return z;}
function updateMarkers(){markerA.position.set(departure[0]-5,departure[1]+4,surfaceZ(...departure)+1.5);markerB.position.set(destination[0]-5,destination[1]+4,surfaceZ(...destination)+1.5);}
function buildSandboxWorld(w,historical=false){
 const n=w.heights_m.length,g=new THREE.PlaneGeometry(w.half_m*2,w.half_m*2,n-1,n-1),p=g.attributes.position,colors=[];
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){
  const idx=(n-1-j)*n+i,z=w.heights_m[j][i];p.setZ(idx,z);
  const c=new THREE.Color().setHSL(.34-.08*Math.min(1,z/45),.27,.29+.17*Math.min(1,z/48));colors.push(c.r,c.g,c.b);
 }
 g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();
 const terrain=new THREE.Mesh(g,new THREE.MeshStandardMaterial({vertexColors:true,roughness:.92,metalness:.03}));terrain.name='terrain-visual';terrain.receiveShadow=true;worldGroup.add(terrain);
 const hills=makeHills(w);worldGroup.add(hills.mesh,makeSkyline(hills.heightAt),makeFarForest(hills.heightAt,quality.forest,w.half_m));
 // Primary east-west Sandbox Runway 09/27 (1,900 m × 42 m along +X) aligned with A10-B heading, plus cross apron
 if(!historical){
  plane(1900,42,0x383e42,0,0,.03,worldGroup);plane(1840,1.2,0xd8ddd4,0,0,.05,worldGroup);
  for(let rx=-880;rx<=880;rx+=40)plane(18,.55,0xf0f4ee,rx,0,.055,worldGroup);
  plane(36,320,0x5c6668,0,0,.025,worldGroup);
  const grid=new THREE.GridHelper(360,36,0xc3d4ca,0x71897c);grid.rotation.x=Math.PI/2;grid.position.z=.04;grid.material.opacity=.24;grid.material.transparent=true;worldGroup.add(grid);
 }
 const water=new THREE.Mesh(new THREE.PlaneGeometry(w.water.half_x*2,w.water.half_y*2),new THREE.MeshStandardMaterial({color:0x669cb2,roughness:.2,metalness:.35}));water.position.set(w.water.x,w.water.y,surfaceZ(w.water.x,w.water.y)+.06);water.receiveShadow=true;worldGroup.add(water);
 for(const o of w.obstacles){
  if(o.kind==='cylinder'){
   const trunk=new THREE.Mesh(new THREE.CylinderGeometry(o.half[0]*.32,o.half[0]*.45,o.half[2]*.9,10),new THREE.MeshStandardMaterial({color:0x6d5846,roughness:.9}));
   trunk.rotation.x=Math.PI/2;trunk.position.set(o.center[0],o.center[1],o.half[2]*.45);trunk.castShadow=true;worldGroup.add(trunk);
   const crown=new THREE.Mesh(new THREE.ConeGeometry(o.half[0]*1.35,o.half[2]*1.45,12),new THREE.MeshStandardMaterial({color:o.color,roughness:.85}));
   crown.rotation.x=Math.PI/2;crown.position.set(o.center[0],o.center[1],o.half[2]*1.15);crown.castShadow=true;worldGroup.add(crown);continue;
  }
  const b=new THREE.Mesh(new THREE.BoxGeometry(o.half[0]*2,o.half[1]*2,o.half[2]*2),new THREE.MeshStandardMaterial({color:o.color,roughness:.76,metalness:.08}));
  b.position.set(...o.center);b.castShadow=true;b.receiveShadow=true;worldGroup.add(b);
  if(o.landable){
   plane((o.half[0]-4)*2,(o.half[1]-4)*2,0x95a89d,o.center[0],o.center[1],o.center[2]+o.half[2]+.02,worldGroup);
   const ring=new THREE.Mesh(new THREE.RingGeometry(3.2,3.65,36),new THREE.MeshBasicMaterial({color:0xecf4ee,side:THREE.DoubleSide}));
   ring.position.set(o.center[0],o.center[1],o.center[2]+o.half[2]+.035);worldGroup.add(ring);
  }
 }
}
function buildWorld(w){
 console.log('VTX: terrain building',w.id);
 const restoreLighting=timeOfDay.mode!=='day' && (world?.vaderland || w.vaderland);
 if(restoreLighting)timeOfDay.set('day');
 world=w;
 const historical=w.environment==='r6-valley-20261103';
 const isSandbox=historical||w.environment==='sandbox';
 clearWorldGroup();
 if(!isSandbox&&!w.vaderland&&trafficPreviewEnabled&&!visualTraffic){
  airportOperations=createAirportOperations(w,{maxAircraft:10});
  airportOperations.setDensity($('traffic-density').value);
  const plan=buildRideJourney($('ride-route').value,$('ride-direction').value,rideCgLocal[2]);
  ridePlan=plan;rideRoute=buildRideTrajectory(plan.points,{cruiseSpeed:plan.speed});
  // Scenery has separate identities and transforms from the piloted ownship.
  const specs=airportOperations.actors.map(actor=>{
   const modelSpec=VEHICLE_MODELS[actor.modelId],isA10=modelSpec.animation==='a10-28-joint',isRotor=modelSpec.animation==='rotor';
   const poseAt=time=>sceneryPoseAt({actorId:actor.id,time,sceneTime,passengerRide,rideRoute,rideTime,sampleRide:sampleRideTrajectory,sampleOperations:airportOperations.sample});
   return {id:actor.id,kind:modelSpec.kind,asset:modelSpec.asset,assetSha256:modelSpec.sha256,cgLocal:modelSpec.cgLocal,rotateToZUp:modelSpec.rotateToZUp,
    prepareSource:actor.modelId==='r6'?root=>enhanceAircraft(root,scene.environment):undefined,
    validate:actor.modelId==='r6'?root=>{
     let meshes=0;root.traverse(node=>{if(node.isMesh)meshes++;});
     return meshes>=691&&[1,2,3,4].every(i=>root.getObjectByName('rotor'+i))&&[1,2,3,4,5,6].every(i=>root.getObjectByName('gear'+i));
    }:undefined,
    makeModel:modelSpec.asset?undefined:THREE=>makeAirportModel(THREE,modelSpec.kind==='ground'?'ground':modelSpec.kind==='rotorcraft'?'rotorcraft':'fixed-wing',actor.color),
    visible:()=>{
     if(replayFrames||(world?.environment||currentEnvironment)!=='airport')return false;
     if(!(airportOperations.isVisible(actor.id)||selectedVehicleId===actor.id))return false;
     const physical=physicalAircraftPosition(last?.rendering_truth);
     return clearOfPhysicalAircraft(poseAt(sceneTime).position,physical);
    },
    poseAt,
    onLoad:root=>{
     const rig=isA10?attachVisualPhantom(root):null;
     if(isA10){
      $('ride-controls').dataset.a10Joints=String(rig.joints.length);
      if(rig.joints.length!==28)toast('A10 articulation unavailable: expected 28 joints');
     }
     if(selectedVehicleId===actor.id)requestAnimationFrame(()=>showRideAircraft(pendingRideExteriorMode||cameraMode));
     if(isA10)return {rig,effects:attachAirportEnergyEffects(root,THREE)};
     if(isRotor){
      const rotors=(actor.modelId==='r6'?[1,2,3,4].map(i=>root.getObjectByName('rotor'+i)):[root.getObjectByName('airport-rotor')]).filter(Boolean);
      const blur=actor.modelId==='r6'?rotors.map(rotor=>{
       const disc=new THREE.Mesh(new THREE.CircleGeometry(1.04,32),new THREE.MeshBasicMaterial({color:0xaad8de,transparent:true,opacity:.13,depthWrite:false,side:THREE.DoubleSide}));
       disc.position.z=.015;disc.visible=false;rotor.add(disc);return disc;
      }):[];
      return {rotors,blur};
     }
     return null;
    },
    onError:error=>toast((isA10?'Scenery Phantom':'Scenery Argon')+' unavailable: '+(error?.message||'asset unavailable')),
    onUpdate:(control,pose,att)=>{if(isRotor&&control?.rotors){
      const active=!['stand','hold short'].includes(pose.operation);
      for(let i=0;i<control.rotors.length;i++)control.rotors[i].rotation.z=active?sceneTime*(i%2?-87:87):0;
      for(const disc of control.blur)disc.visible=active;
      if(actor.id==='r6-flight'){
       $('ride-controls').dataset.r6RotorAngle=String(control.rotors[0]?.rotation.z??0);
       $('ride-controls').dataset.r6RotorsActive=String(active);
      }
     }if(isA10){
     const time=passengerRide?pose.time:pose.animationTime;
     const flightEnd=passengerRide?rideRoute?.duration:actor.route.duration+18;
     animateVisualPhantom(control?.rig,pose,{...att,time:time??0,duration:flightEnd+22,flightStart:passengerRide?0:18,flightEnd,retractStart:flightEnd+3});
     control?.effects.update(pose,sceneTime);
     $('ride-controls').dataset.a10AnimationTime=String(time??0);
     $('ride-controls').dataset.a10WingSlide=control?.rig.joints.find(j=>j.name==='wing_left')?.node.position.toArray().map(v=>v.toFixed(3)).join(',')||'';
    }}
   };
  });
  visualTraffic=createVisualAirTraffic({THREE,GLTFLoader,scene,aircraft:specs});
 }
 if(isSandbox||w.vaderland){
  if(visualTraffic)for(const actor of visualTraffic.actors)actor.root.visible=false;
  if(rideEnabled){
   selectedVehicleId='physical-plant';rideEnabled=false;passengerRide=false;pendingRideExteriorMode=null;$('airport-aircraft').value='physical-plant';
   if(model)model.visible=modelReady;setCameraMode('chase');$('view-mode').textContent='PHYSICAL STATE · LIVE';
  }
  if(w.vaderland){
   harbourLayer=buildHarbour(w,{fetchModel:boatId=>api('/api/harbour/model?airport=true&boatId='+encodeURIComponent(boatId))});
   environment.vaderland=buildVaderland(worldGroup,w,scene,camera,sky,harbourLayer);
  }else buildSandboxWorld(w,historical);
 }else{
  // Ground uses the same heightfield samples as the physics terrain; the distant landscape lies outside the +/-500 m test area.
  worldGroup.add(buildTerrain(w));
  const hills=makeHills(w);worldGroup.add(hills.mesh,makeSkyline(hills.heightAt),makeFarForest(hills.heightAt,quality.forest,w.half_m));const ground=createGround(w,hills.mesh);
  const groundZ=(x,y)=>Math.max(Math.abs(x),Math.abs(y))<=w.half_m?surfaceZ(x,y):ground.heightAt(x,y);
  // Buildings are dressed onto the physical obstacle boxes; airfield markings are flush paint.
  environment.buildings=buildBuildings(worldGroup,w,{ppm:quality.facadePpm,quality});environment.kit=buildAirfieldKit(worldGroup,w,{quality});buildAirfield(worldGroup,{ppm:quality.airfieldPpm,quality,world:w});buildTrees(worldGroup,w,{quality});buildForecourt(worldGroup,w);environment.volcano=buildVolcanoBasement(worldGroup,w);environment.serviceRoads=buildServiceRoads(worldGroup,w,groundZ);
  worldGroup.add(makeWater(w,surfaceZ(w.water.x,w.water.y)+.1));
  environment.dressing=dressWorld(worldGroup,w,ground,{quality,lightPool,extraTextures:[markerA.material.map,markerB.material.map]});
  harbourLayer=buildHarbour(w,{fetchModel:boatId=>api('/api/harbour/model?airport=true&boatId='+encodeURIComponent(boatId)),onError:(boatId,error)=>console.warn('Harbour model unavailable',boatId,error.message)});
  if(harbourLayer)worldGroup.add(harbourLayer.root);
 }
 harbourControls.setWorld(w);
 harbourControls.setEnabled(!!w.harbour&&!replayFrames&&!worldUnavailable);
 const chosen=lightingChoice??(w.vaderland?.city_lights?'dusk':'day');
 if(timeOfDay.mode===chosen)timeOfDay.refresh();else timeOfDay.set(chosen);
 updateLightingButton();
 syncEnvironmentControls(w.environment);
 for(const c of [$('map'),$('large-map')]){
  const mm=getMinimap(c);
  if(mm){
   mm.tacticalMode=!!w.vaderland;
   mm.zoom=w.vaderland?1000/(2*w.half_m*Math.max(1,c.width/c.height)):isSandbox?1.0:w.runway?0.12:0.5;
   mm.center=(isSandbox||w.vaderland)?[0,0]:[0,100];
  }
 }
 if($('map-mode'))$('map-mode').textContent='World';
 if($('grid-label'))$('grid-label').textContent=w.runway?'1 km grid':'200 m grid';
 updateMarkers();drawMaps(true);console.log('VTX: terrain ready',w.id);
}
let worldUnavailable=false;
const worldSynchronizer=createWorldSynchronizer({
 getExpected:()=>replayFrames?replayContext?.environment:(harbourEnvironment||last?.environment),getRendered:()=>world,fetchWorld:()=>api(harbourEnvironment?'/api/harbour/world':'/api/world'),applyWorld:buildWorld,
 setUnavailable:missing=>{worldUnavailable=missing;worldGroup.visible=!missing;document.documentElement.dataset.vtxWorldUnavailable=missing?'1':'0';},
});
let aircraftFx=null,loadedAsset=null,assetRetryAfter=0,modelReady=false;
function disposeModel(root){
 setCockpitVisibility(root,false);
 const geometries=new Set(),materials=new Set(),textures=new Set();
 root.traverse(n=>{if(!n.isMesh)return;if(n.geometry)geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});
 geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}
const suspensionSchematic=createSuspensionSchematic({
 loadAsset:async descriptor=>{
  const response=await fetch(descriptor.asset,{cache:'no-store'});
  if(!response.ok)throw Error('Suspension schematic asset unavailable');
  const bytes=await response.arrayBuffer();
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
  if(digest!==descriptor.sha256)throw Error('Suspension schematic asset does not match this revision');
  const gltf=await new Promise((resolve,reject)=>new GLTFLoader().parse(bytes,'/assets/',resolve,reject));
  const root=gltf.scene.getObjectByName('VTX_A10C_SUSPENSION_SCHEMATIC');
  if(!root){disposeModel(gltf.scene);throw Error('Suspension schematic binding unavailable');}
  return root;
 },
 dispose:disposeModel,
});
let suspensionSchematicEnabled=false;
const suspensionSchematicToggle=$('suspension-schematic-toggle');
suspensionSchematicToggle.onclick=()=>{
 suspensionSchematicEnabled=!suspensionSchematicEnabled;
 suspensionSchematicToggle.setAttribute('aria-pressed',String(suspensionSchematicEnabled));
};
// Render the asset identified by the physical snapshot, including during replay.
function visualAsset(a){return typeof a==='string'&&a.startsWith('/assets/')?a:null;}
function loadAirframe(asset){
 if(asset===loadedAsset||performance.now()<assetRetryAfter)return;loadedAsset=asset;
 modelReady=false;if(model)model.visible=false;
 $('loading').hidden=false;$('loading').textContent='Loading physical revision…';
 loadPinnedGltf(new GLTFLoader(),asset).then(async g=>{
 if(asset!==loadedAsset){disposeModel(g.scene);return;}
 if(model){suspensionSchematic.clear();detachPhantomEffects(phantomRig);scene.remove(model);disposeModel(model);}
 for(const key of Object.keys(bodyNodes))delete bodyNodes[key];pitchMeshes.length=0;
 model=g.scene;
 // Prepared Blendstra GLBs are visual-only: they do not contain the CAD airframe pose node.
 // Bind the complete visual scene to the MuJoCo free body's world pose rather than leaving it at world origin.
 if(!model.getObjectByName('airframe')){
  // Prepared Blendstra mesh is glTF Y-up with no airframe pose node; parent it under
  // a physics-owned Z-up airframe node. Keep the model's native mesh/joint metadata.
  model.rotation.x=Math.PI/2;
  const visualBody=new THREE.Group();visualBody.name='airframe';visualBody.userData.visualPoseBinding='mujoco-free-body';visualBody.add(model);model=visualBody;
 }
 modelReady=false;model.visible=false;scene.add(model);if(!quality.glow)model.traverse(n=>{if(n.isLight)n.visible=false;});model.traverse(n=>{if(n.userData.physical_body&&n.type==='Object3D')bodyNodes[n.userData.physical_body]=n;if(n.isMesh){n.castShadow=true;n.receiveShadow=true;if(n.userData.pitch_axis)pitchMeshes.push(n);if(n.material){n.material.side=THREE.DoubleSide;}}});
 // Blender exports empty groups as Object3D or Group depending on loader.
 for(const name of ['airframe','cabin',...Array.from({length:4},(_,i)=>`nacelle${i+1}`),...Array.from({length:4},(_,i)=>`rotor${i+1}`),...Array.from({length:6},(_,i)=>`gear${i+1}`),...Array.from({length:4},(_,i)=>`shaft${i+1}`)]){const n=model.getObjectByName(name);if(n)bodyNodes[name]=n;}
  aircraftFx=enhanceAircraft(model,scene.environment,{phantom:asset.includes('phantom')});phantomRig=asset.includes('phantom')?attachPhantom(model):null;
 aircraftFx?.setCockpitMode?.(!rideEnabled&&!boatViewId&&cameraMode==='cockpit');aircraftFx?.updateAvionics?.(replayFrames?null:last?.observation,!!replayFrames);
 setCockpitVisibility(model,!rideEnabled&&!boatViewId&&cameraMode==='cockpit');
 // Show the correctly bound aircraft before the display-only mesh batching finishes.
 // Batching yields between groups and never changes the physical model.
 const sourceModel=model;
 modelReady=true;if(!missionTransition)$('loading').hidden=true;
 await new Promise(resolve=>requestAnimationFrame(resolve));
 if(model!==sourceModel||loadedAsset!==asset)return;
 // Display-only batching retains every triangle and the source IDs; the mass
 // ledger/colliders remain per-part. Keep independently pitched blades separate.
 const geometryRefs=new Map();
 sourceModel.traverse(n=>{if(n.isMesh)geometryRefs.set(n.geometry,(geometryRefs.get(n.geometry)||0)+1);});
 let batchStarted=performance.now();
 for(const body of Object.values(bodyNodes)){
  const batches=new Map();
  for(const n of [...body.children])if(n.isMesh&&!n.userData.pitch_axis&&!isCockpitObstruction(n)&&!isArgonRotorHousing(n)&&!Array.isArray(n.material)){
   const key=n.material.uuid+Object.keys(n.geometry.attributes).sort().join(',');
   if(!batches.has(key))batches.set(key,[]);batches.get(key).push(n);
  }
  for(const meshes of batches.values())if(meshes.length>1){
   const copies=meshes.map(n=>{n.updateMatrix();return n.geometry.clone().applyMatrix4(n.matrix);});
   const merged=mergeGeometries(copies);copies.forEach(geometry=>geometry.dispose());
   if(merged){const n=new THREE.Mesh(merged,meshes[0].material);n.castShadow=true;n.receiveShadow=true;n.userData.source_ids=meshes.map(m=>m.userData.blendstra_id);meshes.forEach(m=>{m.removeFromParent();const left=geometryRefs.get(m.geometry)-1;geometryRefs.set(m.geometry,left);if(!left)m.geometry.dispose();});body.add(n);}
   if(performance.now()-batchStarted>10){await new Promise(resolve=>setTimeout(resolve,0));batchStarted=performance.now();if(model!==sourceModel||loadedAsset!==asset)return;}
  }
 }
 }).catch(e=>{if(asset===loadedAsset){loadedAsset=null;assetRetryAfter=performance.now()+5000;$('loading').textContent=`Aircraft visual unavailable: ${e.message}`;}console.error(e);});
}

function limitFanTilt(i){const v=command.tilt_deg[i],r=Math.hypot(...v);if(r>20){v[0]*=20/r;v[1]*=20/r;}for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=v[j];$(k+'val-'+i).value=v[j].toFixed(1)+'°';}syncPolar(i);}
function syncPolar(i){const [x,y]=command.tilt_deg[i],r=Math.min(20,Math.hypot(x,y));if(r>.001)$('az-'+i).value=THREE.MathUtils.euclideanModulo(THREE.MathUtils.radToDeg(Math.atan2(y,x)),360);$('rad-'+i).value=r;$('azval-'+i).value=(+$('az-'+i).value).toFixed(0)+'°';$('radval-'+i).value=r.toFixed(1)+'°';}
function applyPolar(i,r,az){command.tilt_deg[i]=tiltFromDirection(r,az);for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=command.tilt_deg[i][j];$(k+'val-'+i).value=command.tilt_deg[i][j].toFixed(1)+'°';}$('az-'+i).value=az;$('rad-'+i).value=r;$('azval-'+i).value=az.toFixed(0)+'°';$('radval-'+i).value=r.toFixed(1)+'°';}
for(let i=0;i<4;i++){
 const div=document.createElement('div');div.className='rotor';div.innerHTML=`<div class="rotor-top"><b>F${i+1} / ${['EAST','NORTH','WEST','SOUTH'][i]}</b><span id="rpm-${i}">0 rpm</span></div><label class="range-label">Collective <output id="pval-${i}">0.0°</output><input type="range" id="p-${i}" min="0" max="30" step="0.1" value="0" aria-label="Rotor ${i+1} collective"></label><div class="vector-controls"><label class="range-label">Tilt X <output id="xval-${i}">0°</output><input id="x-${i}" type="range" min="-20" max="20" step="0.1" value="0" aria-label="Rotor ${i+1} tilt X"></label><label class="range-label">Tilt Y <output id="yval-${i}">0°</output><input id="y-${i}" type="range" min="-20" max="20" step="0.1" value="0" aria-label="Rotor ${i+1} tilt Y"></label></div><label class="range-label">Tilt direction <output id="azval-${i}">0°</output><input id="az-${i}" type="range" min="0" max="360" step="1" value="0" aria-label="Rotor ${i+1} tilt direction"></label><label class="range-label">Tilt magnitude <output id="radval-${i}">0°</output><input id="rad-${i}" type="range" min="0" max="20" step="0.1" value="0" aria-label="Rotor ${i+1} tilt magnitude"></label><div class="vector-controls"><button type="button" class="tilt-spin" id="ccw-${i}">↺ Spin</button><button type="button" class="tilt-spin" id="stop-${i}">Stop</button><button type="button" class="tilt-spin" id="cw-${i}">Spin ↻</button></div>`;$('rotors').appendChild(div);
 for(const key of ['p','x','y'])$(key+'-'+i).oninput=()=>{const val=Number($(key+'-'+i).value);if(key==='p')command.collective_deg[i]=val;else{command.tilt_deg[i][key==='x'?0:1]=val;limitFanTilt(i);}if(key==='p')$(key+'val-'+i).value=val.toFixed(1)+'°';dirty=true;};
 for(const key of ['az','rad'])$(key+'-'+i).oninput=()=>{applyPolar(i,+$('rad-'+i).value,+$('az-'+i).value);dirty=true;};
 for(const [key,sign] of [['ccw',1],['stop',0],['cw',-1]])$(key+'-'+i).onclick=()=>{if(sign&&+$('rad-'+i).value<.1){toast('Set this fan’s tilt magnitude before rotating its direction.');return;}tiltSpinAngle[i]=+$('az-'+i).value;tiltSpin[i]=sign;};
}
$('engine').oninput=()=>{command.engine=+$('engine').value;$('engine-value').value=Math.round(command.engine*100)+'%';dirty=true;};
$('assist').oninput=()=>{$('assist-value').value=$('assist').value+'%';};
$('assist').onchange=guard(async()=>{if(last?.active)await api('/api/operator',{stability_assist:+$('assist').value/100});});
$('common').oninput=()=>{command.collective_deg.fill(+$('common').value);$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';}dirty=true;};
for(const [key,axis] of [['common-x',0],['common-y',1]])$(key).oninput=()=>{for(let i=0;i<4;i++){command.tilt_deg[i][axis]=+$(key).value;$(axis?'y-'+i:'x-'+i).value=+$(key).value;$(axis?'yval-'+i:'xval-'+i).value=(+$(key).value).toFixed(1)+'°';limitFanTilt(i);}dirty=true;};
for(const id of ['common-azimuth','common-radius'])$(id).oninput=()=>{const a=+$('common-azimuth').value,r=+$('common-radius').value;$('common-azimuth-value').value=a.toFixed(0)+'°';$('common-radius-value').value=r.toFixed(1)+'°';for(let i=0;i<4;i++)applyPolar(i,r,a);dirty=true;};
for(const [id,axis] of [['cabin-x',0],['cabin-y',1],['cabin-yaw',2]])$(id).oninput=()=>{command.cabin_deg[axis]=+$(id).value;if(axis===2)$('cabin-yaw-value').value=command.cabin_deg[2].toFixed(0)+'°';dirty=true;};
$('cabin-level').onchange=()=>{if(last?.active&&(last.authority!=='manual'||!manualOwned)){$('cabin-level').checked=command.cabin_level;toast('Take manual authority explicitly before changing cabin controls.');return;}command.cabin_level=$('cabin-level').checked;dirty=true;};
$('cabin-face-travel').onclick=()=>{const o=last?.observation;if(!o){toast('Flight instruments are not available.');return;}const [vx,vy]=o.gnss_velocity_mps;if(Math.hypot(vx,vy)<.5){toast('Direction of travel is unavailable at this speed.');return;}const heading=THREE.MathUtils.radToDeg(Math.atan2(vx,-vy));const yaw=THREE.MathUtils.euclideanModulo(heading-o.attitude_xyz_deg[2]+180,360)-180;command.cabin_deg[2]=yaw;$('cabin-yaw').value=yaw;$('cabin-yaw-value').value=yaw.toFixed(0)+'°';dirty=true;};
let miniMap=null,largeMinimap=null;
function getMinimap(canvas){
  if(!canvas)return null;
  if(canvas===$('map')){
    if(!miniMap)miniMap=new TacticalMinimap(canvas,{isLarge:false});
    return miniMap;
  }
  if(canvas===$('large-map')){
    if(!largeMinimap)largeMinimap=new TacticalMinimap(canvas,{isLarge:true});
    return largeMinimap;
  }
  return null;
}
const onMap=async(event,canvas)=>{
  // Map B remains editable throughout a sortie; A only sets the next departure.
  const rect=canvas.getBoundingClientRect();
  const mm=getMinimap(canvas);
  let x,y;
  if(mm){
    const proj=mm.getProjection(world?.half_m||500);
    const sx=((event.clientX-rect.left)/rect.width)*canvas.width;
    const sy=((event.clientY-rect.top)/rect.height)*canvas.height;
    x=proj.unpx(sx);
    y=proj.unpy(sy);
  } else {
    x=((event.clientX-rect.left)/rect.width-.5)*world.half_m*2;
    y=(.5-(event.clientY-rect.top)/rect.height)*world.half_m*2;
  }
  await choosePoint([Math.round(x*10)/10,Math.round(y*10)/10]);
};
async function choosePoint(p){
 if(worldUnavailable){toast('Matching terrain is unavailable; wait before selecting a point.');return;}
 if(document.documentElement.dataset.vtxPreviewPending==='1')return;
 const target=pick;
 const variant=$('airframe').value;
 const verdict=await api(`/api/validate?x=${p[0]}&y=${p[1]}&variant=${encodeURIComponent(variant)}`);
 const valid=verdict.valid ?? verdict.ok;
 $('validation').textContent=`${pick.toUpperCase()} (${p.join(', ')}): ${verdict.reason}`;
 $('large-validation').textContent=$('validation').textContent;
 if(target==='a'){
  if(!valid){toast(verdict.reason);return;}
  if(!variant){toast('Choose an aircraft first.');return;}
  await new Promise((resolve,reject)=>document.dispatchEvent(new CustomEvent('vtx-preview-start',{detail:{position:p,resolve,reject}})));
  departure=p;departureExplicit=true;$('dep').value=p.join(', ');
  const preset=$('start-preset');const key=p.join(',');
  preset.value=[...preset.options].some(o=>o.value===key)?key:'custom';

 }else{
  if(last?.active){const result=await api('/api/destination',{run_id:last.run_id,destination:p});toast(result.landing_valid?'Target B changed in flight':'Target B changed; landing clearance not certified');}
  else if(Math.max(...p.map(Math.abs))>world.half_m-8){toast('Outside surveyed map');return;}
  destination=p;$('dest').value=p.join(', ');
 }
 updateMarkers();drawMaps();
}
document.addEventListener('vtx-aircraft-departure-request',event=>{
 const detail=event.detail;
 detail.departure=[...departure];
 if((last?.environment?.key||currentEnvironment)==='airport' && detail.variant.startsWith('phantom') && !departureExplicit && departure[0]===-700 && departure[1]===0){
  detail.original=[...departure];detail.departure=[-3885,0];
 }
});
async function switchEnvironment(envKey){
 if(envKey===last?.environment?.key || !last?.inspection_selection_known){
  syncEnvironmentControls(currentEnvironment);
  if(!last?.inspection_selection_known)toast('Choose an aircraft before changing its environment.');
  return;
 }
 try{
  await new Promise((resolve,reject)=>document.dispatchEvent(new CustomEvent('vtx-preview-start',{detail:{environment:envKey,resolve,reject}})));
 }catch(error){syncEnvironmentControls(last.environment.key);throw error;}
}
if($('env-airport'))$('env-airport').onclick=guard(()=>switchEnvironment('airport'));
if($('env-sandbox'))$('env-sandbox').onclick=guard(()=>switchEnvironment('sandbox'));
if($('environment-select'))$('environment-select').onchange=guard(()=>switchEnvironment($('environment-select').value));
function showDeparture(){
 $('dep').value=departure.join(', ');
 const key=departure.join(',');
 $('start-preset').value=[...$('start-preset').options].some(o=>o.value===key)?key:'custom';
 showTimeTrial();
}
$('start-preset').onchange=guard(async()=>{const value=$('start-preset').value;if(value==='custom')return;pick='a';try{await choosePoint(value.split(',').map(Number));}finally{showDeparture();}});
$('map').onclick=guard(e=>onMap(e,$('map')));$('large-map').onclick=guard(e=>onMap(e,$('large-map')));
function setPick(p){pick=p;$('pick-a').classList.toggle('selected',p==='a');$('pick-b').classList.toggle('selected',p==='b');$('large-pick').textContent=p.toUpperCase();}
$('runway-start').onclick=guard(async()=>{pick='a';const pt=currentEnvironment==='sandbox'?[-700,0]:[-3885,0];await choosePoint(pt);toast(currentEnvironment==='sandbox'?'Departure set at sandbox runway 09 threshold: X -700 m, Y 0 m.':'Departure set at the west runway threshold: X -3885 m, Y 0 m.');});
$('pick-a').onclick=()=>setPick('a');$('pick-b').onclick=()=>setPick('b');
for(const [id,p] of [['dep','a'],['dest','b']])$(id).onchange=guard(async()=>{
 try{
  const fields=$(id).value.split(',').map(v=>v.trim()), vals=fields.map(Number);
  if(fields.length!==2||fields.some(v=>!v)||vals.some(v=>!Number.isFinite(v)))throw Error('Enter east and north coordinates in metres.');
  setPick(p);await choosePoint(vals);
 }finally{if(p==='a')showDeparture();else $('dest').value=destination.join(', ');}
});
$('map-zoom').onclick=()=>{$('map-dialog').showModal();drawMaps(true);};
document.querySelectorAll('[data-map-zoom]').forEach(button=>button.onclick=()=>{getMinimap($(button.dataset.mapTarget))?.zoomBy(Number(button.dataset.mapZoom));drawMaps(true);});
const mapModeBtn=$('map-mode');
if(mapModeBtn){
  mapModeBtn.onclick=()=>{
    const mm=getMinimap($('map'));
    if(mm){
      const isSandbox=currentEnvironment==='sandbox';
      mm.tacticalMode=!mm.tacticalMode;
      mm.zoom=mm.tacticalMode?1000/(world.half_m*2*Math.max(1,$('map').width/$('map').height)):(isSandbox?1.0:world.runway?0.12:0.5);
      mm.center=mm.tacticalMode?[0,0]:(isSandbox?[0,0]:[0,100]);
      mapModeBtn.textContent=mm.tacticalMode?(isSandbox?'Sandbox':'Airport'):'World';
      $('grid-label').textContent=mm.zoom<0.3?'1 km grid':'200 m grid';
      drawMaps(true);
    }
  };
}
$('objective-form').addEventListener('submit',guard(async(e)=>{
 e.preventDefault();const text=$('objective-input').value.trim();if(!text||!last?.active)return;
 const run=last.run_id;await api('/api/objective',{run_id:run,text});
 if($('objective-input').value.trim()===text)$('objective-input').value='';
 toast('Objective saved for this flight.');
}));
function resetRotorInputs(){
 dirty=false;keys.clear();tiltSpin.fill(0);
 command.engine=1;command.collective_deg.fill(0);command.cabin_deg=[0,0,0];command.cabin_level=true;
 $('engine').value=1;$('engine-value').value='100%';$('common').value=0;$('common-value').value='0.0°';
 for(const id of ['common-x','common-y','common-radius','common-azimuth','cabin-x','cabin-y','cabin-yaw'])$(id).value=0;
 $('cabin-level').checked=true;$('cabin-yaw-value').value='0°';
 for(let i=0;i<4;i++){
  $('p-'+i).value=0;$('pval-'+i).value='0.0°';applyPolar(i,0,0);
 }
}
$('start').onclick=guard(async()=>{if(worldUnavailable){toast('Matching terrain is unavailable; wait before starting.');return;}stopReplay(false);const variant=$('airframe').value,phantom=variant.startsWith('phantom');departure=missionDeparture({departure,explicit:departureExplicit,variant,environment:currentEnvironment,runway:world?.runway});$('dep').value=departure.join(', ');const departureKey=departure.join(',');$('start-preset').value=[...$('start-preset').options].some(option=>option.value===departureKey)?departureKey:'custom';updateMarkers();drawMaps();const request={environment:currentEnvironment,departure,destination,ignore_scenery_collisions:$('ignore-scenery').checked,landing_precision_m:$('landing-precision').value===''?null:Number($('landing-precision').value),authority:$('pilot').value,time_scale:+$('scale').value,airframe_variant:variant,label:'Map-selected live ground-to-ground attempt'};if(phantom)request.phantom={start_configuration:$('phantom-start').value};if(!phantom)Object.assign(request,{stability_assist:+$('assist').value/100,reference_rpm:+$('drive').value,gear_variant:$('gear').value,fuel_kg:selectedFuel(),engine_power_limit_kw:+$('power-limit').value,atmosphere_model:$('atmosphere-model').value,wind_world_mps:selectedWind()});missionTransition={previousRunId:last?.run_id};renderer.domElement.style.visibility='hidden';$('loading').hidden=false;$('loading').textContent='Starting mission…';let r;try{r=await api('/api/mission',request);}catch(error){missionTransition=null;renderer.domElement.style.visibility='visible';$('loading').hidden=modelReady;throw error;}manualRunId=r.run_id;manualOwned=$('pilot').value==='manual';if(manualOwned)manualChannel.postMessage('takeover');track=[];if(!phantom)resetRotorInputs();toast('Sortie '+r.run_id+' started on the landing gear.');});
$('end').onclick=guard(async()=>{const r=await api('/api/stop',{reason:'Operator ended the live attempt'});toast(`Recorded: ${r.outcome}. Every failed attempt is retained.`);});
$('restart-flight').onclick=guard(async()=>{
 const run=last?.run_id;
 if(!last?.active||!vehicleWorkspace.aircraftInput)return;
 clearAircraftInput();
 const next=await api('/api/restart-flight',{run_id:run});
 if(!next.observation.configuration.airframe_variant.startsWith('phantom'))resetRotorInputs();
 manualRunId=next.run_id;manualOwned=next.observation.authority==='manual';
 if(manualOwned)manualChannel.postMessage('takeover');
 updateView(await api('/api/view'));
 toast('Flight '+run+' saved. Restarted as '+next.run_id+'.');
});
$('save-flight').onclick=guard(async()=>{const r=await api('/api/save-flight',{run_id:last?.run_id});manualOwned=false;dirty=false;keys.clear();phantomPanel?.disengage();toast(`Flight ${r.run_id} saved. Restore it from Flight records.`);});
for(const authority of ['manual','colin'])$('retry-'+authority).onclick=guard(async()=>{
 stopReplay(false);
 const r=await api('/api/retry',{expected_previous_run_id:last?.end_summary?.run_id,authority,time_scale:authority==='colin'?.02:.1,stability_assist:+$('assist').value/100});
 manualRunId=r.run_id;manualOwned=authority==='manual';if(manualOwned)manualChannel.postMessage('takeover');
 resetRotorInputs();
 toast(authority==='colin'?'New sortie '+r.run_id+'. Waiting for Colin to issue live commands; retry does not start an automatic pilot.':'New sortie '+r.run_id+'. The previous run and pilot checkpoint are preserved.');
});
$('pause').onclick=guard(async()=>{await api('/api/operator',{paused:!last.paused});});
$('takeover').onclick=guard(async()=>{
 if(last){const o=last.observation,issued=last.recent_decisions.at(-1)?.issued;
  command.engine=issued?.engine??(Math.max(...o.rotor_rpm)>300?1:0);
  command.collective_deg=[...o.collective_feedback_deg];command.tilt_deg=o.tilt_feedback_deg.map(v=>[...v]);
  command.cabin_deg=[...(issued?.cabin_deg??o.cabin_feedback_deg??[0,0,0])];if(command.cabin_deg.length===2)command.cabin_deg.push(0);command.cabin_level=issued?.cabin_level??o.cabin_level_enabled??true;$('cabin-level').checked=command.cabin_level;for(const [id,axis] of [['cabin-x',0],['cabin-y',1],['cabin-yaw',2]])$(id).value=command.cabin_deg[axis];$('cabin-yaw-value').value=command.cabin_deg[2].toFixed(0)+'°';
  $('engine').value=command.engine;$('engine-value').value=Math.round(command.engine*100)+'%';
  for(let i=0;i<4;i++){$('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';}
 }
 const run=last?.run_id;await api('/api/operator',{authority:'manual'});if(last?.run_id!==run)return;manualRunId=run;manualChannel.postMessage('takeover');manualOwned=true;$('pilot').value='manual';dirty=true;toast('Manual authority acquired with the current actuator settings.');
});
$('scale').onchange=guard(async()=>{await api('/api/operator',{time_scale:+$('scale').value});});
$('feather').onclick=()=>{command.engine=0;command.collective_deg.fill(0);$('engine').value=0;$('engine').oninput();$('common').value=0;$('common').oninput();dirty=true;};
let cockpitYaw=0,cockpitPitch=0,cockpitPointer=null,savedChaseOffset=null;
let viewStorage=null;
try{viewStorage=window.localStorage;}catch{}
const cameraPreferences=createViewPreferenceStore(viewStorage);
let cameraPreferenceIdentity=null,restoringCameraPreference=false,cameraPreferencesSuspended=false;

function saveCameraPreference(){
  if(restoringCameraPreference||cameraPreferencesSuspended||rideEnabled||boatViewId||vehicleWorkspace.mode!=='aircraft'||replayFrames||!cameraPreferenceIdentity)return;
  const offset=(cameraMode==='chase'||cameraMode==='orbit')?camera.position.clone().sub(orbit.target):savedChaseOffset;
  const state={mode:cameraMode,cockpitYaw,cockpitPitch};
  if(offset)state.chaseOffset=offset.toArray();
  if(cameraMode==='free'){
    state.freePosition=freeCam.position.toArray();
    const cp=Math.cos(freeCam.pitch),p=state.freePosition;
    state.freeAim=[p[0]+Math.sin(freeCam.yaw)*cp,p[1]+Math.cos(freeCam.yaw)*cp,p[2]+Math.sin(freeCam.pitch)];
  }
  cameraPreferences.save(cameraPreferenceIdentity.variant,cameraPreferenceIdentity.environment,state);
}

function syncCameraPreference(view){
  // Visual traffic and recorded replay have their own cameras; they must not
  // overwrite the physical aircraft's remembered view.
  if(rideEnabled||boatViewId||vehicleWorkspace.mode!=='aircraft'||replayFrames){cameraPreferencesSuspended=true;return;}
  const variant=view.inspection_selection_known===false?null:view.observation?.configuration?.airframe_variant;
  const environment=view.environment?.key;
  const next=variant&&environment?{variant,environment}:null;
  if(!cameraPreferencesSuspended&&next?.variant===cameraPreferenceIdentity?.variant&&next?.environment===cameraPreferenceIdentity?.environment)return;
  if(!cameraPreferencesSuspended)saveCameraPreference();
  cameraPreferencesSuspended=false;cameraPreferenceIdentity=next;
  if(!next)return;
  const state=cameraPreferences.load(next.variant,next.environment);
  if(!state)return;
  restoringCameraPreference=true;
  try{
    cockpitYaw=state.cockpitYaw;cockpitPitch=state.cockpitPitch;
    setCameraMode(state.mode);
    if(state.chaseOffset)savedChaseOffset=new THREE.Vector3(...state.chaseOffset);
    if((state.mode==='chase'||state.mode==='orbit')&&state.chaseOffset){
      const target=physicalCameraTarget(view.rendering_truth);
      if(target)orbit.target.set(...target);
      camera.up.set(0,0,1);camera.position.copy(orbit.target).add(savedChaseOffset);orbit.update();
    }else if(state.mode==='free')freeCam.teleport(state.freePosition,state.freeAim);
  }finally{restoringCameraPreference=false;}
}
// Ride cameras have independent transforms. The free camera never follows the
// aircraft and the chase camera preserves its own orbit offset.
const rideChaseOffset=new THREE.Vector3(-13,7,6);
let rideChaseInitialised=false;
// A predictable one-click way to see the actual A10 model from outside.
function showRideAircraft(mode='chase'){
  if(!rideEnabled)return;
  const actor=visualTraffic?.getActor(selectedVehicleId)?.root;
  const a10=actor?.children?.[0]?.children?.[0];
  if(!a10){
    pendingRideExteriorMode=mode;
    toast('Selected vehicle still loading; exterior view will open when ready.');
    return;
  }
  pendingRideExteriorMode=null;
  actor.visible=true;
  if(mode==='cockpit'){setCameraMode('cockpit');return;}
  setCockpitVisibility(a10,false);
  const h=ridePose?.heading||0;
  const direction=new THREE.Vector3(Math.cos(h),Math.sin(h),0);
  const left=new THREE.Vector3(-direction.y,direction.x,0);
  const aim=actor.position.clone().add(new THREE.Vector3(0,0,1.2));
  // The exterior position is set explicitly, never inherited from a cockpit
  // camera inside the hull. Framing is re-established at any circuit point.
  if(mode==='free'){
    setCameraMode('free');
    const here=aim.clone().addScaledVector(direction,-16).addScaledVector(left,8).add(new THREE.Vector3(0,0,6));
    freeCam.teleport(here.toArray(),aim.toArray());
  }else{
    rideChaseOffset.copy(direction).multiplyScalar(mobile?-10:-13).addScaledVector(left,mobile?4:7).add(new THREE.Vector3(0,0,mobile?5:6));
    rideChaseInitialised=false;
    setCameraMode('chase');
    orbit.target.copy(aim);
    camera.up.set(0,0,1);
    camera.position.copy(aim).add(rideChaseOffset);
    orbit.update();
    rideChaseInitialised=true;
  }
}
function setCameraMode(mode){
  restoreHarbourOverview();
  const previous=cameraMode;
  const actor=rideEnabled?visualTraffic?.getActor(selectedVehicleId)?.root:null;
  if(boatViewId){
    freeCam.deactivate();orbit.enabled=mode==='chase'||mode==='orbit';
  }
  if(rideEnabled){
    if(previous==='chase'&&actor&&rideChaseInitialised)rideChaseOffset.copy(camera.position).sub(orbit.target);
  }else if(!boatViewId&&previous==='chase'&&mode==='cockpit'){
    savedChaseOffset=camera.position.clone().sub(orbit.target);
  }
  cameraMode=mode;
  setCockpitVisibility(model,!rideEnabled&&!boatViewId&&mode==='cockpit');
  if(rideEnabled)setCockpitVisibility(actor?.children?.[0]?.children?.[0],mode==='cockpit');
  aircraftFx?.setCockpitMode?.(!rideEnabled&&mode==='cockpit');
  orbit.enabled=mode==='chase'||mode==='orbit';
  if(mode==='free'){
    orbit.enabled=false;
    freeCam.activate();
    if(rideEnabled&&actor){
      // An external viewpoint looking at the visible A10, not a camera left
      // inside its hull or bound to the moving cockpit.
      const p=actor.position;
      const here=[p.x-25,p.y-20,p.z+14],aim=[p.x,p.y,p.z+1.3];
      freeCam.teleport(here,aim);
    }
  }else{
    freeCam.deactivate();
  }
  if(rideEnabled&&actor&&(mode==='chase'||mode==='orbit')){
    if(mode==='chase')rideChaseInitialised=true;
    const aim=actor.position.clone().add(new THREE.Vector3(0,0,1.4));
    orbit.target.copy(aim);
    camera.up.set(0,0,1);
    camera.position.copy(aim).add(mode==='chase'?rideChaseOffset:new THREE.Vector3(0,-.01,Math.max(55,rideChaseOffset.length())));
    orbit.update();
  }else if(!rideEnabled&&!boatViewId&&mode==='chase'&&previous==='cockpit'){
    const target=physicalCameraTarget(last?.rendering_truth);
    if(target)orbit.target.set(...target);
    camera.up.set(0,0,1);
    camera.position.copy(orbit.target).add(savedChaseOffset||new THREE.Vector3(9,-11,8));
    orbit.update();
  }
  renderer.domElement.style.touchAction='none';
 $('cockpit-look').hidden=mode!=='cockpit';$('cockpit-instruments').hidden=mode!=='cockpit'||rideEnabled||!!boatViewId;$('cockpit-frame').hidden=mode!=='cockpit'||!!boatViewId||!!last?.rendering_truth?.phantom;
 $('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';
 $('camera').textContent=mode==='free'?'Exit free roam':'Free roam camera';
 const cameraSelect=$('airport-camera');if(cameraSelect)cameraSelect.value=mode;
  if(rideEnabled){
    $('ride-locate').hidden=mode!=='free';
    $('ride-exterior').textContent=mode==='chase'?'Recenter aircraft':'Show aircraft';
  }
}
$('camera').onclick=()=>{if(rideEnabled)showRideAircraft(cameraMode==='free'?'chase':'free');else setCameraMode(cameraMode==='free'?'chase':'free');saveCameraPreference();};
$('cockpit').onclick=()=>{if(rideEnabled&&cameraMode==='cockpit')showRideAircraft('chase');else setCameraMode(cameraMode==='cockpit'?'chase':'cockpit');saveCameraPreference();};
function zoomCamera(factor){
 if(cameraMode==='cockpit'){toast('Zoom is available in the external camera.');return;}
 if(cameraMode==='free'){freeCam.zoom(factor);saveCameraPreference();return;}
 const offset=camera.position.clone().sub(orbit.target),distance=offset.length();
 if(distance<1e-9)return;
 camera.position.copy(orbit.target).add(offset.multiplyScalar(zoomDistance(distance,factor,orbit.minDistance,orbit.maxDistance)/distance));
 orbit.update();
 saveCameraPreference();
}
$('zoom-in').onclick=()=>zoomCamera(.8);$('zoom-out').onclick=()=>zoomCamera(1.25);
$('view-top').onclick=()=>{
 const truth=replayFrames?.[replayFrame]||last?.rendering_truth,target=physicalCameraTarget(truth);
 if(boatViewId){
    const body=harbourLayer?.boats.get(boatViewId)?.bodies.get('airframe');
    if(body)orbit.target.copy(body.position).add(new THREE.Vector3(0,0,1));
  }else if(rideEnabled){
    const actor=visualTraffic?.getActor(selectedVehicleId)?.root;
    if(actor)orbit.target.copy(actor.position).add(new THREE.Vector3(0,0,1.5));
  }else if(target)orbit.target.set(...target);
 const distance=rideEnabled?65:THREE.MathUtils.clamp(camera.position.distanceTo(orbit.target),18,orbit.maxDistance);
 setCameraMode('orbit');camera.up.set(0,0,1);camera.position.copy(orbit.target).add(new THREE.Vector3(0,-.01,distance));orbit.update();saveCameraPreference();
};
$('look-left').onclick=()=>{cockpitYaw=THREE.MathUtils.clamp(cockpitYaw+Math.PI/12,-Math.PI/2,Math.PI/2);saveCameraPreference();};
$('look-right').onclick=()=>{cockpitYaw=THREE.MathUtils.clamp(cockpitYaw-Math.PI/12,-Math.PI/2,Math.PI/2);saveCameraPreference();};
$('look-center').onclick=()=>{cockpitYaw=0;cockpitPitch=0;saveCameraPreference();};
renderer.domElement.addEventListener('pointerdown',e=>{if(cameraMode!=='cockpit')return;cockpitPointer={id:e.pointerId,x:e.clientX,y:e.clientY};renderer.domElement.setPointerCapture(e.pointerId);});
renderer.domElement.addEventListener('pointermove',e=>{if((cameraMode!=='cockpit')||!cockpitPointer||e.pointerId!==cockpitPointer.id)return;cockpitYaw=THREE.MathUtils.clamp(cockpitYaw-(e.clientX-cockpitPointer.x)*.006,-Math.PI/2,Math.PI/2);cockpitPitch=THREE.MathUtils.clamp(cockpitPitch-(e.clientY-cockpitPointer.y)*.006,-Math.PI/3,Math.PI/3);cockpitPointer.x=e.clientX;cockpitPointer.y=e.clientY;});
for(const event of ['pointerup','pointercancel','lostpointercapture'])renderer.domElement.addEventListener(event,()=>{cockpitPointer=null;requestAnimationFrame(saveCameraPreference);});
renderer.domElement.addEventListener('wheel',()=>requestAnimationFrame(saveCameraPreference),{passive:true});
renderer.domElement.addEventListener('dblclick',()=>{if(cameraMode==='cockpit'){cockpitYaw=0;cockpitPitch=0;saveCameraPreference();}});
addEventListener('keyup',()=>{if(cameraMode==='free')saveCameraPreference();});
addEventListener('pagehide',saveCameraPreference);
// Keyboard mixing is an explicitly disclosed mapping to the same raw channels.
// It reads keys only: no position, attitude, velocity or navigation feedback.
const keys=new Set();
function typing(e){return /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);}
addEventListener('keydown',e=>{
 if(typing(e)||document.querySelector('dialog[open]'))return;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code))e.preventDefault();
 if(e.code==='KeyC'&&!e.repeat)$('cockpit').click();
 if(!vehicleWorkspace.aircraftInput||rideEnabled||last?.rendering_truth?.phantom)return;
 if(last?.authority!=='manual'||!last.active||!manualOwned)return;
 if(e.code==='KeyX'&&!e.repeat){$('engine').value=command.engine>.5?0:1;$('engine').oninput();}
 if(e.code==='Space'){$('feather').click();keys.clear();}
 keys.add(e.code);
});
addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>keys.clear());
setInterval(()=>{
 if(!vehicleWorkspace.aircraftInput||!last?.active||last.rendering_truth?.phantom||last.authority!=='manual'||!manualOwned||last.paused||replayFrames||!keys.size)return;
 const down=k=>keys.has(k)?1:0,delta=.12;
 const lift=(down('KeyR')-down('KeyF'))*delta;
 let pitch=(down('KeyW')-down('KeyS'))*.06,roll=(down('KeyD')-down('KeyA'))*.06;
 const yaw=(down('KeyE')-down('KeyQ'))*.15;
 let tx=(down('ArrowUp')-down('ArrowDown'))*.15;
 let ty=(down('ArrowRight')-down('ArrowLeft'))*.15;
  // In the cockpit the pilot looks along cabin -Y: map pilot-relative keys to body axes (audit F14).
 if(cameraMode==='cockpit'){
  const heading=last.observation.cabin_heading_body_deg;
  if(!Number.isFinite(heading))return;
  [tx,ty]=cockpitAxes(tx,ty,heading);
  [pitch,roll]=cockpitAxes(pitch,roll,heading);
 }
 // Collective torque mix: north/south produce body X torque; east/west Y.
 const differential=[-roll,pitch,roll,-pitch];
 const yawX=[-yaw,0,yaw,0],yawY=[0,-yaw,0,yaw];
 for(let i=0;i<4;i++){
  command.collective_deg[i]=THREE.MathUtils.clamp(command.collective_deg[i]+lift+differential[i],0,30);
  command.tilt_deg[i][0]=THREE.MathUtils.clamp(command.tilt_deg[i][0]+tx+yawX[i],-20,20);
  command.tilt_deg[i][1]=THREE.MathUtils.clamp(command.tilt_deg[i][1]+ty+yawY[i],-20,20);
  $('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';
  limitFanTilt(i);
 }
 $('common').value=command.collective_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';
 dirty=true;
},50);
// A user-selected articulation sweep changes the same raw tilt targets. It does not fly the aircraft.
let tiltSpinTick=performance.now();
setInterval(()=>{const now=performance.now(),dt=Math.min(.1,(now-tiltSpinTick)/1000);tiltSpinTick=now;if(!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames)return;for(let i=0;i<4;i++){if(!tiltSpin[i])continue;tiltSpinAngle[i]=THREE.MathUtils.euclideanModulo(tiltSpinAngle[i]+tiltSpin[i]*30*dt*last.time_scale,360);applyPolar(i,+$('rad-'+i).value,tiltSpinAngle[i]);dirty=true;}},50);
// Start closed, including a page restored from the browser's back/forward cache.
const closeKeyboardGuide=()=>{$('keyboard-help').close();};
closeKeyboardGuide();addEventListener('pageshow',closeKeyboardGuide);
$('keyboard-open').onclick=()=>{$('keyboard-help').showModal();keys.clear();};
for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>b.closest('dialog').close();
$('engineering').onclick=()=>{$('engineering-dialog').showModal();updateEngineering();};
function describeFlightEvent(event){
 const d=event.detail||{};
 switch(event.kind){
  case 'objective_changed': return `Objective: ${d.objective?.text||'—'}`;
  case 'objective_completed': return `Objective completed: ${d.objective?.text||'—'}`;
  case 'pilot_decision': return `${d.pilot_id||d.authority||'Pilot'}: ${d.decision||'Decision recorded'}`;
  case 'pilot_handover': return `Pilot handover: ${d.previous||'unassigned'} → ${d.pilot_id||'unassigned'}`;
  case 'pilot_takeover_pending': return `Pilot awaiting control: ${d.pilot_id||'unknown'}`;
  case 'pilot_takeover_applied': return `Pilot took control: ${d.pilot_id||'unknown'}`;
  case 'pilot_provider_failed': return `Pilot ${d.previous||'unknown'} failed; fallback ${d.fallback?.state||'unknown'}${d.fallback?.reason?`: ${d.fallback.reason}`:''}`;
  case 'pending_pilot_failed': return `Replacement pilot ${d.pilot_id||'unknown'} failed: ${d.reason||'no reason given'}`;
  case 'authority_change': return `Authority: ${d.before||'unknown'} → ${d.after||'unknown'}`;
  case 'supported_landing_observed': return `Supported landing; ${Number.isFinite(d.destination_distance_m)?d.destination_distance_m.toFixed(2)+' m from destination':'distance unavailable'}; precision ${d.precision==='not_specified'?'not specified':d.precision||'unknown'}`;
  case 'sortie_end': return `Flight ended: ${d.outcome||'unknown'}${d.reason?` · ${d.reason}`:''}`;
  default: return 'Event recorded';
 }
}
$('history').onclick=guard(async()=>{
 if(!$('history-dialog').open)$('history-dialog').showModal();
 $('runs').textContent='Loading flight records…';
 const [records,savedFlights]=await Promise.all([api('/api/runs'),api('/api/saved-flights')]);$('runs').replaceChildren();$('timeline').hidden=true;
 if(savedFlights.length){const heading=document.createElement('h3');heading.textContent='Saved flights';$('runs').appendChild(heading);}
 for(const saved of savedFlights){
  const row=document.createElement('article'),button=document.createElement('button');
  button.textContent='Restore paused flight';button.disabled=!saved.available||!!last?.active;
  button.onclick=guard(async()=>{const result=await api('/api/restore-flight',{run_id:saved.run_id});document.dispatchEvent(new CustomEvent('vtx-aircraft-selected',{detail:await api('/api/view')}));$('replay-controls').hidden=true;$('history-dialog').close();toast(`Restored ${result.run_id} paused. Take control and resume when ready.`);});
  const detail=saved.available?`${saved.variant||'identity unavailable'} · ${saved.environment||'environment unavailable'} · ${Number.isFinite(saved.t_s)?saved.t_s.toFixed(1)+' s':'time unavailable'}`:'Checkpoint unavailable; retained for inspection';
  row.append(button,document.createTextNode(`${saved.run_id} · ${detail}`));$('runs').appendChild(row);
 }
 for(const r of records){
  const article=document.createElement('article'),replayButton=document.createElement('button'),timelineButton=document.createElement('button');
  replayButton.textContent='Inspect recorded states';
  replayButton.onclick=guard(async()=>{
   if(last?.active){toast('End or save the active flight before inspecting recorded states.');return;}
   const replay=await api('/api/replay/'+r.run_id);
   if(last?.active){toast('A flight became active; recorded inspection was not opened.');return;}
   if(!Array.isArray(replay.frames)||!replay.frames.length){toast('No recorded physical states are available for this flight.');return;}
   replayContext=replay.recorded_context||{};replayFrames=replay.frames;replayFrame=0;
   document.documentElement.dataset.vtxReplay='1';
   leaveBoatView();vehicleWorkspace.show('aircraft');
   if(rideEnabled){rideEnabled=false;passengerRide=false;$('airport-aircraft').value='physical-plant';}
   if(visualTraffic)for(const actor of visualTraffic.actors)actor.root.visible=false;
   $('replay-time').value=0;$('replay-time').max=Math.max(0,replayFrames.length-1);$('replay-controls').hidden=false;
   $('view-mode').textContent='RECORDED STATE · NO CONTROL · BROWSER CACHE UNVERIFIED';
   aircraftFx?.updateAvionics?.(null,true);worldSynchronizer.reconcile();updateReplayReadings();
   toast(replay.downsampled?`Inspection uses ${replay.frames.length} of ${replay.total_frames} recorded states; full log is retained.`:'Inspection only. The live physical plant remains separate.');
  });
  timelineButton.textContent='Review decisions and events';
  timelineButton.onclick=guard(async()=>{const result=await api('/api/timeline/'+r.run_id),container=$('timeline-events');container.replaceChildren();
   for(const event of result.events){const line=document.createElement('p'),label=document.createElement('strong'),detail=document.createElement('span');
    label.textContent=`${Number.isFinite(event.t_s)?event.t_s.toFixed(2)+' s':'—'} · `;
    detail.textContent=describeFlightEvent(event);line.append(label,detail);container.appendChild(line);}
   if(!result.events.length)container.textContent='No decisions or events recorded.';
   if(result.truncated){const note=document.createElement('p');note.textContent=`Showing the most recent ${result.events.length} of ${result.total_events} events; the full log is retained.`;container.prepend(note);}
   $('timeline').hidden=false;
  });
  const findingsButton=document.createElement('button');
  findingsButton.textContent='Pilot summary & engineering findings';
  findingsButton.onclick=guard(async()=>{try{const result=await api('/api/runs/'+encodeURIComponent(r.run_id)+'/findings');const box=$('timeline-events');box.replaceChildren();const detail=document.createElement('pre');detail.textContent=JSON.stringify(result,null,2);detail.style.whiteSpace='pre-wrap';box.appendChild(detail);$('timeline').hidden=false;}catch(e){toast(e.message||'No failure summary for this run.');}});
  article.append(findingsButton);
  const envTag=r.environment_label||r.environment_key||r.mission?.environment_label||r.mission?.environment_key||r.environment||r.mission?.environment||'airport';
  const lineage=r.continuation?` · continuation of ${r.continuation.parent_run_id} at ${Number(r.continuation.checkpoint_time_s).toFixed(2)} s`:'';
  const duration=Number.isFinite(r.simulated_seconds)?`${r.simulated_seconds.toFixed(1)} s`:'duration unknown';
  const decisions=Number.isInteger(r.decisions)?`${r.decisions} decisions`:'decision count unknown';
  article.append(replayButton,timelineButton,document.createTextNode(`${r.run_id} · ${envTag} · ${r.outcome} · ${duration} · ${decisions}${lineage}`));$('runs').appendChild(article);
 }
 try{const archive=await api('/api/archive/runs');const heading=document.createElement('h3');heading.textContent='Historical PC flight summaries (read only)';$('runs').appendChild(heading);if(!archive.records.length){const empty=document.createElement('p');empty.textContent='No historical summaries found in the configured PC archives.';$('runs').appendChild(empty);}for(const r of archive.records){const row=document.createElement('p');row.textContent=`${r.run_id} · ${r.source} · recorded outcome: ${r.recorded_outcome||'unknown'} · ${Number.isFinite(r.simulated_seconds)?r.simulated_seconds.toFixed(1)+' s':'duration unknown'}`;$('runs').appendChild(row);}}catch(e){const notice=document.createElement('p');notice.textContent='Historical archive unavailable: '+e.message;$('runs').appendChild(notice);}
});
$('open-records').onclick=()=>$('history').click();
function updateReplayReadings(){
 harbourControls.setEnabled(false);
 drawMaps(true);
 const r=replayCockpitReadings(replayFrames?.[replayFrame]);
 $('cockpit-alt').textContent=r.altitude;$('cockpit-vs').textContent=r.verticalSpeed;
 $('cockpit-speed').textContent=r.speed;$('cockpit-fuel').textContent=r.fuel;
 if($('engineering-dialog').open)updateEngineering();
}
function stopReplay(refresh=true){
 if(!replayFrames)return;
 replayFrames=null;replayContext=null;delete document.documentElement.dataset.vtxReplay;
 $('replay-controls').hidden=true;$('view-mode').textContent='PHYSICAL STATE · LIVE';
 worldSynchronizer.reconcile();
 if(refresh&&last)updateView(last);
}
$('replay-time').oninput=()=>{replayFrame=+$('replay-time').value;updateReplayReadings();};
$('return-live').onclick=()=>stopReplay();
function drawMap(canvas){
  if(!world||!canvas)return;
  if(worldUnavailable){canvas.getContext('2d')?.clearRect(0,0,canvas.width,canvas.height);return;}
  const mm=getMinimap(canvas);
  if(mm){
    if(canvas===$('map'))$('grid-label').textContent=mm.zoom<0.3?'1 km grid':'200 m grid';
    const observation=liveMapObservation(last,performance.now()-latestTruthReceivedMs,!!replayFrames);
    mm.render(world,{observation,track:observation?track:[],departure,destination,harbourState:replayFrames?null:harbourControls.state});
  }
}
// Legacy map replaced by TacticalMinimap

let lastMapMs=0;
function drawMaps(force=false){if(!force&&performance.now()-lastMapMs<400)return;lastMapMs=performance.now();drawMap($('map'));if($('map-dialog').open)drawMap($('large-map'));}
function updateEngineering(){
 if(boatViewId&&!replayFrames){
  const state=harbourControls.state;
  $('engineering-content').textContent=JSON.stringify({boat:state?.boats.find(b=>b.id===boatViewId),physics:state?.physics,environment:world?.id},null,2);
  return;
 }
 if(replayFrames){$('engineering-content').textContent=JSON.stringify({mode:'recorded state',run_context:replayContext,frame:replayFrames[replayFrame],suspension_schematic:{enabled:suspensionSchematicEnabled,...suspensionSchematic.status},wheel_visual_fit:phantomRig?.wheels?.map(w=>({pod:['FL','FR','RL','RR'][w.idx],...w.fit}))||[]},null,2);return;}
 if(!last)return;
 const t=last.rendering_truth,o=last.observation;
 if(t.phantom){
  $('engineering-content').textContent=JSON.stringify({
   identity:{variant:o.configuration?.airframe_variant,config_sha256:o.configuration?.config_sha256,
    model_xml_sha256:t.provenance?.model_xml_sha256,runtime_source_sha256:last.runtime_source_sha256,
    physics_characteristics_uri:t.provenance?.physics_characteristics_uri,
    physics_model_doc_uri:t.provenance?.physics_model_doc_uri,flight_revision:t.provenance?.flight_revision},
   physics_characteristics:t.phantom.physics_data||null,
   instruments:o,mass_cg_inertia:t.mass,body_poses:t.body_poses,joints:t.phantom.joints,
   nose_lift:{spring_seat_setting_m:t.phantom.nose_lift_m,
    front_suspension_joint_m:{FL:t.phantom.joints?.pod_FL_susp,FR:t.phantom.joints?.pod_FR_susp},
    note:'Spring-seat setting and measured wheel suspension travel are different quantities; actuator rod travel is not modelled.'},
   suspension_schematic:{enabled:suspensionSchematicEnabled,...suspensionSchematic.status},
   wheel_visual_fit:{note:'Authored wheel dimensions and attachment datums are preserved. Measured articulation is applied; collision dimensions and anchor offsets are reported separately and do not resize or relocate the visual assembly.',
    wheels:phantomRig?.wheels?.map(w=>({pod:['FL','FR','RL','RR'][w.idx],...w.fit}))||[]},
   wing_state:t.phantom.wing_state,aerodynamics:t.aero,propulsion:t.propulsors,energy:t.energy,
   control_law:t.fcc,commands:t.command,contacts:t.contact,events:t.events
  },null,2);
  return;
 }
 $('engineering-content').textContent=JSON.stringify({live:{simulation_time_s:o.t_s,observation_id:o.observation_id,clock_scale:last.time_scale,active:last.active,paused:last.paused,authority:last.authority,command_warnings:o.warning_lamps,rotor_rpm:o.rotor_rpm,shaft_torque_nm:o.shaft_torque_nm,shaft_power_kw:o.engine_shaft_kw,collective_deg:o.collective_feedback_deg,fan_tilt_deg:o.tilt_feedback_deg,cabin_gimbal_deg:o.cabin_feedback_deg,attitude_deg:o.attitude_xyz_deg,angular_rate_world_deg_s:o.gyro_world_deg_s,angular_rate_body_deg_s:o.gyro_body_deg_s,velocity_world_m_s:o.gnss_velocity_mps,velocity_body_m_s:o.velocity_body_mps,clearance_m:o.radar_clearance_m,fuel_kg:o.fuel_kg,scheduler_backlog_s:o.scheduler_backlog_s},engineering:{revision:t.provenance.revision,physics_revision:t.provenance.physics_revision,runtime_source_sha256:last.runtime_source_sha256,status:t.provenance.status,mass:t.mass,power:t.power,energy:t.energy,flags:t.flags,contact_events:t.events,hypotheses:t.provenance.hypotheses}},null,2);
}
function showAttitude(snapshot, mode){
 renderAttitudeIndicator({indicator:$('attitude'),horizon:$('horizon'),angles:$('angles'),status:$('attitude-status')},snapshot,mode);
}
function updateView(v){
 if(manualOwned && (!v.active||v.run_id!==manualRunId))clearAircraftInput();
 document.dispatchEvent(new CustomEvent('vtx-aircraft-state',{detail:v}));
 if(replayFrames&&v.active)stopReplay(false);
 if(replayFrames){last=v;latestTruthReceivedMs=performance.now();worldSynchronizer.reconcile();return;}
 $('r6-pilot-record').hidden=v.observation?.configuration?.airframe_variant!=='r6-argon-20261103';
 if(v.observation){
  const instruments=cockpitTelemetry(v.observation);
  $('cockpit-alt').textContent=instruments.altitude;
  $('cockpit-vs').textContent=instruments.verticalSpeed;
  $('cockpit-speed').textContent=instruments.speed;
  $('cockpit-fuel').textContent=instruments.fuel;
 }
 const nextAsset=visualAsset(v.rendering_truth?.provenance?.render_asset);
 if(model?.visible && nextAsset && loadedAsset!==nextAsset){model.visible=false;renderer.clear();}
 last=v;showTimeTrial();syncCameraPreference(v);latestTruthReceivedMs=performance.now();poseInterpolator.receive(v.rendering_truth,latestTruthReceivedMs);cityClock.receive(v,latestTruthReceivedMs);panelWasStale=false;aircraftFx?.updateAvionics?.(v.observation);
 if(!replayFrames)showAttitude(v.rendering_truth,'LIVE');
 const envLocked=!!harbourEnvironment||document.documentElement.dataset.vtxPreviewPending==='1';
 $('restart-flight').hidden=!v.active;
 $('dep').disabled=$('start-preset').disabled=$('runway-start').disabled=document.documentElement.dataset.vtxPreviewPending==='1';
 $('save-flight').disabled=!v.active;
 $('retry-bar').hidden=!v.retry_available||v.active;
 $('retry-status').textContent='Retry the retained mission from its departure.';
 for(const id of ['environment-select','env-airport','env-sandbox']){const el=$(id);if(el)el.disabled=envLocked;}
 if(!harbourEnvironment&&v.environment?.key&&v.environment.key!==currentEnvironment){
  syncEnvironmentControls(v.environment.key);
 }
 // Phantom and Argon both need the authoritative mission/preview position.
 // This must run before the Phantom-specific early return below.
 const t=v.rendering_truth;
 if(!inspectionDepartureSynced && v.inspection_selection_known!==false && !departureExplicit){
  const position=t?.body_poses?.airframe?.position;
  if(!v.active && !v.mission && Array.isArray(position) && position.length>=2 && position.slice(0,2).every(Number.isFinite)){
   departure=position.slice(0,2);$('dep').value=departure.join(', ');
   const key=departure.join(',');$('start-preset').value=[...$('start-preset').options].some(option=>option.value===key)?key:'custom';updateMarkers();
  }
  inspectionDepartureSynced=true;
 }
 if(v.run_id!==lastRun){lastRun=v.run_id;if(v.mission){departure=[...v.mission.departure];$('dep').value=departure.join(', ');const key=departure.join(',');$('start-preset').value=[...$('start-preset').options].some(option=>option.value===key)?key:'custom';updateMarkers();}}
 if(v.mission&&(destination[0]!==v.mission.destination[0]||destination[1]!==v.mission.destination[1])){destination=[...v.mission.destination];$('dest').value=destination.join(', ');updateMarkers();}
 worldSynchronizer.reconcile();
 if(boatViewId){
  showHelmStatus();
  if($('engineering-dialog').open)updateEngineering();
  return;
 }
 const truth=v.rendering_truth||{};
 if(truth.crashed||v.error||v.recovery_notice){$('consequence').hidden=false;$('consequence').textContent=v.error?'Runtime stopped: '+v.error:truth.crashed?'IMPACT RECORDED · '+(truth.events?.[0]?.body||'aircraft')+'. Physical consequences remain active; no automatic rescue.':v.recovery_notice;}else{$('consequence').hidden=true;}
 updateCheckpointOffer(v);
 if(v.active&&v.mission?.destination&&document.activeElement!==$('dest')){const target=v.mission.destination;if(destination[0]!==target[0]||destination[1]!==target[1]){destination=[...target];$('dest').value=destination.join(', ');updateMarkers();drawMaps(true);}}
 const objective=v.objective; $('objective-current').textContent=objective?`Current objective (${objective.status}): ${objective.text}`:'No objective set.';
 const owner=v.pilot_owner;const fallback=v.fallback?.state;
 $('objective-pilot').textContent=`Pilot ownership: ${owner||'none assigned'}${fallback?` · fallback ${fallback}`:''}${v.pending_pilot?` · awaiting ${v.pending_pilot}`:''}.`;
 $('objective-submit').disabled=!v.active;

 const landing=v.landing_assessment; $('landing-evidence').textContent=landing?`Supported landing recorded at ${landing.t_s.toFixed(1)} s; ${landing.destination_distance_m.toFixed(2)} m from destination. Precision: ${landing.precision==='not_specified'?'not specified':landing.precision}.`:'No landing recorded yet.';
 if(v.run_id!==trackRun){track=[];trackRun=v.run_id;}
 const point=v.observation?.gnss_xy_m;
 if(v.active&&Number.isFinite(point?.[0])&&Number.isFinite(point?.[1])&&
    (!track.length||Math.hypot(point[0]-track.at(-1)[0],point[1]-track.at(-1)[1])>.2)){
  track.push(point);
  if(track.length>3000)track.shift();
 }
 drawMaps();
 if(v.rendering_truth?.phantom){
  phantomPanel??=createPhantomPanel({api,toast,canControl:()=>vehicleWorkspace.aircraftInput&&!rideEnabled&&!replayFrames});phantomPanel.show(true);phantomPanel.update(v);
  document.querySelector('.controls-panel').classList.add('phantom-active');
  const o=v.observation,t=v.rendering_truth,velocity=o.velocity_world_m_s||[0,0,0];
  $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE EXPERIMENT · PHANTOM'):'PHANTOM INSPECTION';
  $('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';
  $('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
  $('start').disabled=v.active||worldUnavailable||document.documentElement.dataset.vtxPreviewPending==='1'||!knownAircraft($('airframe'),v);$('end').disabled=!v.active;$('pause').disabled=!v.active;
  $('aircraft-evidence').textContent=flownEvidence(v);$('aircraft-evidence').hidden=!$('aircraft-evidence').textContent;
  $('pause').textContent=v.paused?'Resume existing mission':'Pause physics';
  $('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';showRevision(v);
  if(v.inspection_selection_known===false)$('airframe').value='';else if(document.documentElement.dataset.vtxPreviewPending!=='1')$('airframe').value=o.configuration.airframe_variant;
  setMissionOptions($('airframe').value);
  for(const id of ['dest','drive','gear','phantom-start','initial-fuel','power-limit','pilot','atmosphere-model','wind-east','wind-north','wind-up'])$(id).disabled=v.active||(document.documentElement.dataset.vtxPreviewPending==='1'&&(id==='airframe'||id==='phantom-start'));
  const clearance=cockpitTelemetry(o).altitude;
  $('alt').innerHTML=clearance==='—'?'—':clearance+'<small>m</small>';
  $('vs').innerHTML=velocity[2].toFixed(2)+'<small>m/s</small>';
  $('speed').innerHTML=Math.hypot(...velocity.slice(0,2)).toFixed(2)+'<small>m/s</small>';
  $('power').innerHTML=(o.generator_kw||0).toFixed(1)+'<small>kW</small>';
  $('fuel').innerHTML=(o.fuel_kg||[]).reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
  if($('engineering-dialog').open)updateEngineering();
  return;
 }
 phantomPanel?.show(false);document.querySelector('.controls-panel').classList.remove('phantom-active');
 // Always ingest the latest physical pose; avoid repainting the entire HUD at
 // the websocket rate on low-powered phones. 3D rendering is independent.
 if(lightweightView&&latestTruthReceivedMs-lastHudUpdateMs<500&&v.run_id===lastRun)return;
 lastHudUpdateMs=latestTruthReceivedMs;const o=v.observation;if(v.inspection_selection_known===false)$('airframe').value='';else if(document.documentElement.dataset.vtxPreviewPending!=='1')$('airframe').value=o.configuration.airframe_variant;setMissionOptions($('airframe').value);
 $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE FLIGHT'):'INSPECTION';$('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';$('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
 const latestPilot=v.recent_decisions.at(-1),pilotWaiting=v.active&&v.authority==='colin'&&(!latestPilot||o.warning_lamps.includes('COMMAND_LEASE_EXPIRED')||o.t_s-latestPilot.issued_t_s>1);$('colin-wait').hidden=!pilotWaiting;$('colin-wait').textContent=pilotWaiting?'Waiting for live Colin commands. The retry button does not start an automatic pilot.':'';
 $('authority').textContent=v.authority.toUpperCase();$('start').disabled=v.active||worldUnavailable||document.documentElement.dataset.vtxPreviewPending==='1'||!knownAircraft($('airframe'),v);$('aircraft-evidence').textContent=flownEvidence(v);$('aircraft-evidence').hidden=!$('aircraft-evidence').textContent;$('end').disabled=!v.active;$('pause').disabled=!v.active;$('pause').textContent=v.paused?'Resume existing mission':'Pause physics';showRevision(v);$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';

 $('power-label').textContent='SHAFT POWER';$('alt').innerHTML=o.radar_clearance_m==null?'—':o.radar_clearance_m.toFixed(2)+'<small>m</small>';$('vs').innerHTML=o.gnss_velocity_mps[2].toFixed(2)+'<small>m/s</small>';$('speed').innerHTML=Math.hypot(...o.gnss_velocity_mps.slice(0,2)).toFixed(2)+'<small>m/s</small>';$('power').innerHTML=o.engine_shaft_kw.toFixed(1)+'<small>kW</small>';$('fuel').innerHTML=o.fuel_kg.reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
 for(let i=0;i<4;i++)$('rpm-'+i).textContent=o.rotor_rpm[i].toFixed(0)+' rpm';
 if(o.assisted_collective_deg)$('assist-feedback').textContent=(o.assistance_applied?'Experimental collective targets: ':'Shadow requests: ')+o.assisted_collective_deg.map(x=>x.toFixed(2)+'°').join(' / ')+(o.assistance_applied?' · applied':' · not applied');
 for(const el of document.querySelectorAll('.controls-panel input[type=range]:not(#assist):not([data-command]),#feather'))el.disabled=v.authority!=='manual'||!manualOwned;
 const cabinLocked=v.authority!=='manual'||!manualOwned;for(const el of document.querySelectorAll('.tilt-spin'))el.disabled=cabinLocked;if(cabinLocked)tiltSpin.fill(0);$('cabin-level').disabled=cabinLocked;$('cabin-face-travel').disabled=cabinLocked;$('cabin-x').disabled=cabinLocked||command.cabin_level;$('cabin-y').disabled=cabinLocked||command.cabin_level;if(o.cabin_feedback_deg)$('cabin-feedback').textContent='Actual gimbal X / Y / yaw: '+o.cabin_feedback_deg.map(x=>x.toFixed(1)+'°').join(' / ')+(o.cabin_level_enabled?(o.cabin_level_powered?' · powered level control':' · passive damping only'):' · manual cabin control')+(o.cabin_level_limited?' · travel limit reached':'');
 for(const id of ['drive','gear','initial-fuel','power-limit','pilot','atmosphere-model','wind-east','wind-north','wind-up','ignore-scenery','landing-precision'])$(id).disabled=v.active||(document.documentElement.dataset.vtxPreviewPending==='1'&&(id==='airframe'||id==='phantom-start'));
 if(v.active){$('landing-precision').value=v.mission?.landing_precision_m??'';$('ignore-scenery').checked=!!v.mission?.ignore_scenery_collisions;$('power-limit').value=t.provenance.engine_power_limit_kw??469.8;$('initial-fuel').value=t.provenance.initial_fuel_kg??o.configuration.initial_fuel_kg;$('pilot').value=v.authority;$('scale').value=String(v.time_scale);$('drive').value=String(t.provenance.reference_rpm);$('gear').value=t.provenance.gear_variant;$('airframe').value=o.configuration.airframe_variant;$('atmosphere-model').value=o.configuration.atmosphere_model??'constant';(o.configuration.wind_world_mps??[0,0,0]).forEach((value,i)=>$( ['wind-east','wind-north','wind-up'][i]).value=value);}
 if(v.authority==='colin'||!manualOwned){const issued=v.recent_decisions.at(-1)?.issued;$('engine').value=issued?.engine??0;$('engine-value').value=Math.round((issued?.engine??0)*100)+'%';$('common').value=o.collective_feedback_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=o.collective_feedback_deg[i];$('pval-'+i).value=o.collective_feedback_deg[i].toFixed(1)+'°';for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=o.tilt_feedback_deg[i][j];$(k+'val-'+i).value=o.tilt_feedback_deg[i][j].toFixed(1)+'°';}}}
 const key=v.recent_decisions.map(a=>a.sequence).join(',');if(key!==lastDecision){lastDecision=key;$('decisions').replaceChildren();for(const d of [...v.recent_decisions].reverse()){const a=document.createElement('article'),tm=document.createElement('time'),p=document.createElement('p'),code=document.createElement('code');tm.textContent=`${d.issued_t_s.toFixed(3)} s / ${d.issued.authority.toUpperCase()}`;p.textContent=d.decision;code.textContent=`Collective ${d.issued.collective_deg.join(' / ')}° · engine ${d.issued.engine}`;a.append(tm,p,code);$('decisions').appendChild(a);}}
 if($('engineering-dialog').open)updateEngineering();
}
let manualRequestPending=false;
setInterval(guard(async()=>{if(!vehicleWorkspace.aircraftInput||manualRequestPending||last?.rendering_truth?.phantom||!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames)return;manualBeat++;if(dirty){dirty=false;manualRequestPending=true;try{await api('/api/action',{...command,authority:'manual',expected_run_id:last.run_id,observation_id:last.observation.observation_id,reason:'Manual operator controls'});}catch(e){dirty=true;throw e;}finally{manualRequestPending=false;}}}),50);
let wsActive=false,wsPollTimer=null,wsToastTimer=null;
function connect(){
 const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);
 ws.onopen=()=>{
  wsActive=true;
  if(wsPollTimer){clearInterval(wsPollTimer);wsPollTimer=null;}
  if(wsToastTimer){clearTimeout(wsToastTimer);wsToastTimer=null;}
 };
 ws.onmessage=e=>{try{updateView(JSON.parse(e.data));}catch(err){console.error(err);}};
 ws.onclose=()=>{
  wsActive=false;
  if(!wsPollTimer){
   wsPollTimer=setInterval(()=>{if(!wsActive)api('/api/view').then(v=>updateView(v)).catch(()=>{});},250);
  }
  if(!wsToastTimer){
   wsToastTimer=setTimeout(()=>{if(!wsActive)toast('Live connection lost; reconnecting. Last accepted controls remain held.');wsToastTimer=null;},3500);
  }
  setTimeout(connect,1000);
 };
}
api('/api/world').then(w=>{if(!last?.active&&Array.isArray(w.default_departure)&&w.default_departure.length===2){departure=[...w.default_departure];$('dep').value=departure.join(', ');}buildWorld(w);connect();let helm;try{helm=sessionStorage.getItem('vtx-helm');}catch{}if(helm)void openBoat(helm,true).catch(error=>toast(error.message));}).catch(error=>{console.warn('Unable to load selected environment',error);return fetch('/vtx-env/ride-world.json?v=1').then(response=>{if(!response.ok)throw Error('Airport terrain unavailable: HTTP '+response.status);return response.json();}).then(w=>{visualOnlyOffline=true;buildWorld(w);$('view-sync').textContent= 'SCRIPTED TRAFFIC - PHYSICAL BACKEND OFFLINE';});}).catch(e=>{$('loading').textContent='Unable to load airport: '+e.message;console.error('Airport world',e);});
const q=new THREE.Quaternion(),pos=new THREE.Vector3(),cameraTarget=new THREE.Vector3();
let lastFrameMs=0;
function audibleTraffic(){
 const traffic=[];
 for(const actor of visualTraffic?.actors??[]){
  if(!actor.ready||!actor.root.visible||!actor.pose||actor.pose.speed<.2)continue;
  const [idle,slope,level]=({ground:[580,55,.052],rotorcraft:[1120,6,.045]})[actor.spec.kind]??[2150,15,.064];
  traffic.push({id:actor.spec.id,position:actor.pose.position,rpm:idle+actor.pose.speed*slope,level,type:actor.spec.kind});
 }
 const fleet=harbourControls.state;
 if(fleet?.available&&!replayFrames){
  for(const boat of fleet.boats??[]){
   const rig=harbourLayer?.boats.get(boat.id),hull=rig?.bodies.get('airframe');
   const thrust=Math.max(0,Number(boat.command?.throttle)||0);
   if(!rig?.root.visible||!hull||boat.crashed||boat.dockedAt||boat.speed_mps<.25&&thrust<.02)continue;
   traffic.push({id:boat.id,position:hull.position.toArray(),rpm:460+1500*thrust,
     level:.021+.035*Math.min(1,boat.speed_mps/14)+.025*thrust,speed:boat.speed_mps,type:'boat'});
  }
 }
 return traffic;
}
if(new URLSearchParams(location.search).has('debug'))window.__vtx={post,timeOfDay,scene,worldGroup,camera,renderer,orbit,freeCam,THREE,sky,environment,setCameraMode,switchEnvironment,get currentEnvironment(){return currentEnvironment;},get model(){return model;},get loadedAsset(){return loadedAsset;},get modelReady(){return modelReady;},get last(){return last;},get world(){return world;},get harbourState(){return harbourControls.state;},get harbourLayer(){return harbourLayer;},bodyNodes,setReplay(frames,index){replayFrames=frames;replayFrame=index;},setRideTime(t){if(!rideEnabled||!rideRoute)return false;rideTime=Math.min(rideRoute.duration,Math.max(0,Number(t)||0));rideLastFrame=performance.now();ridePaused=true;return true;}};
function animate(){
 requestAnimationFrame(animate);
 if(document.hidden)return;
 const now=performance.now();
 const frameMs=lightweightView?67:frameCapMs??quality.frameMs??(quality.name==='high'?0:50);
 if(now-lastFrameMs<frameMs)return;
 lastFrameMs=now;
 // Between 10 Hz telemetry samples the airframe is drawn between its two latest true poses (presentation only).
 const truth=replayFrames?replayFrames[replayFrame]:(poseInterpolator.present(now,{frozen:!last?.active||!!last?.paused})??last?.rendering_truth);
 harbourControls.setEnabled(!!world?.harbour&&!replayFrames&&!worldUnavailable);
 if(!replayFrames)harbourLayer?.animate(now);
 if(replayFrames)showAttitude(truth,'REPLAY');
 const frameDt=rideLastFrame?Math.min(.25,(now-rideLastFrame)/1000):0;
 rideLastFrame=now;
 if(!ridePaused)sceneTime+=frameDt*sceneScale;
 if(passengerRide&&!ridePaused&&rideRoute&&!replayFrames)rideTime=Math.min(rideRoute.duration+22,rideTime+frameDt*sceneScale);
 if(replayFrames){if(visualTraffic)for(const actor of visualTraffic.actors)actor.root.visible=false;}else visualTraffic?.update(sceneTime);
 const unselected=!replayFrames && last?.inspection_selection_known===false && !last?.active;
 const requestedAsset=harbourEnvironment&&!worldMatches(world,last?.environment)?null:replayFrames?replayFrameAsset(truth,replayContext):truth&&!unselected?visualAsset(truth.provenance?.render_asset):null;
 if(boatViewId||unselected){$('loading').hidden=true;}
 else if(truth&&!requestedAsset){$('loading').hidden=false;$('loading').textContent=replayFrames?'Recorded aircraft visual unavailable or does not match.':'Aircraft visual identity unavailable.';}
 if(requestedAsset)loadAirframe(requestedAsset);
 if(model)model.visible=modelReady&&loadedAsset===requestedAsset;
 const schematicFresh=!!replayFrames||now-latestTruthReceivedMs<=2000;
 const schematicStatus=$('suspension-schematic-status'),hasSchematic=!!suspensionSchematicDescriptor(truth);
 if(!hasSchematic){suspensionSchematicEnabled=false;suspensionSchematicToggle.setAttribute('aria-pressed','false');}
 suspensionSchematicToggle.hidden=!hasSchematic||rideEnabled;
 const showSchematic=hasSchematic&&suspensionSchematicEnabled&&!rideEnabled;
 suspensionSchematic.update(model,truth,showSchematic&&modelReady&&loadedAsset===requestedAsset&&schematicFresh);
 schematicStatus.hidden=!showSchematic;
 if(showSchematic)schematicStatus.textContent=!schematicFresh?'SUSPENSION SCHEMATIC · DATA STALE':suspensionSchematic.status.status==='measured'?'PHYSICAL SUSPENSION REFERENCE · SCHEMATIC':suspensionSchematic.status.status==='loading'?'SUSPENSION SCHEMATIC · LOADING':'SUSPENSION SCHEMATIC · MEASUREMENT OR ASSET UNAVAILABLE';
 if(truth&&model){for(const [name,pose] of Object.entries(truth.body_poses)){const n=bodyNodes[name];if(!n)continue;n.position.set(...pose.position);const a=pose.quaternion_wxyz;n.quaternion.set(a[1],a[2],a[3],a[0]);
   // The authoritative rotor pose is sampled at 20 Hz. At 1200 RPM one full
   // revolution occurs between samples, so drawing snapshots alone looks static.
   // Use measured signed angular velocity solely for sub-frame presentation.
   if(!replayFrames&&name.startsWith('rotor')&&/^rotor[1-4]$/.test(name)){
    const i=Number(name.slice(-1))-1;
    const angle=rotorVisualOffset(truth.rotor_spin_rad_s?.[i],now-latestTruthReceivedMs,last?.time_scale,last?.active,last?.paused);
    if(angle)n.quaternion.multiply(rotorSpinQ.setFromAxisAngle(rotorSpinAxis,angle));
   }
  }if(phantomRig){
   const offsets=(truth.phantom?.wheel_rad_s||[]).map(omega=>rotorVisualOffset(omega,now-latestTruthReceivedMs,last?.time_scale,!!last?.active&&!replayFrames,last?.paused));
   updatePhantom(phantomRig,truth,false,offsets,true);
  }if(truth.pitch_deg)for(const mesh of pitchMeshes){const i=Number(mesh.userData.physical_body?.slice(-1))-1;if(i>=0&&i<4)mesh.quaternion.setFromAxisAngle(new THREE.Vector3(...mesh.userData.pitch_axis).normalize(),THREE.MathUtils.degToRad(truth.pitch_deg[i]));}
 }
 if(truth&&!rideEnabled&&!boatViewId){
  const physicalTarget=physicalCameraTarget(truth);if(physicalTarget)pos.set(...physicalTarget);
  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);camera.up.set(0,0,1);orbit.update();}
  else if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position);if(truth.phantom)camera.position.add(new THREE.Vector3(0,.15,.30).applyQuaternion(q));if(!truth.phantom)camera.position.add(new THREE.Vector3(-.30,.02,.25).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));const cp=Math.cos(cockpitPitch);const sight=truth.phantom?new THREE.Vector3(Math.cos(cockpitYaw)*cp,Math.sin(cockpitYaw)*cp,Math.sin(cockpitPitch)):new THREE.Vector3(Math.sin(cockpitYaw)*cp,-Math.cos(cockpitYaw)*cp,Math.sin(cockpitPitch));cameraTarget.copy(camera.position).add(sight.applyQuaternion(q));camera.lookAt(cameraTarget);}
  else if(cameraMode==='free'){freeCam.update(0.08);}
  else{camera.up.set(0,0,1);orbit.update();}
  sky.follow(pos);
 }
 if(rideEnabled&&rideRoute){
  ridePose=visualTraffic?.getActor(selectedVehicleId)?.pose;
  rideActor=visualTraffic?.getActor(selectedVehicleId)?.root;
  if(rideActor){
   const p=rideActor.position,rot=rideActor.children[0].quaternion;
   if(cameraMode==='cockpit'){
    const sight=new THREE.Vector3(...sceneryPassengerSight(selectedVehicleId,cockpitYaw,cockpitPitch)).applyQuaternion(rot);
    camera.position.copy(new THREE.Vector3(...sceneryPassengerSeat(selectedVehicleId)).applyQuaternion(rot).add(p));
    camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(rot));
    camera.lookAt(camera.position.clone().add(sight));
    }else if(cameraMode==='chase'){
      const target=p.clone().add(new THREE.Vector3(0,0,1.5));
      const delta=target.clone().sub(orbit.target);
      camera.position.add(delta);orbit.target.copy(target);
      camera.up.set(0,0,1);orbit.update();
    }else if(cameraMode==='free'){
      freeCam.update(frameDt); // Independent camera, no automatic follow.
    }else if(cameraMode==='orbit'){
      const target=p.clone().add(new THREE.Vector3(0,0,1.5));
      const delta=target.clone().sub(orbit.target);
      camera.position.add(delta);orbit.target.copy(target);orbit.update();
    }
    sky.follow(cameraMode==='free'?camera.position:p);
   setCockpitVisibility(rideActor.children?.[0]?.children?.[0],cameraMode==='cockpit');
  }
  if(ridePose){
   const velocity=ridePose.velocity||[ridePose.speed*Math.cos(ridePose.heading),ridePose.speed*Math.sin(ridePose.heading),ridePose.speed*Math.sin(ridePose.pitch)];
   const speed=Math.hypot(velocity[0],velocity[1]);
   if(now-(animate.hudLast||0)>350){animate.hudLast=now;
    $('ride-progress').textContent=(ridePose.operation||'scripted')+' · '+Math.floor(sceneTime)+' s';
    $('view-sync').textContent=(VEHICLE_MODELS[airportOperations?.actors.find(a=>a.id===selectedVehicleId)?.modelId]?.label||selectedVehicleId)+' · SCENERY · '+speed.toFixed(1)+' m/s';
   }
  }
 }else if(visualTraffic&&now-(animate.progressLast||0)>500){animate.progressLast=now;$('ride-progress').textContent='Traffic active · '+Math.floor(sceneTime)+' s';}
 for(const [id,rig] of harbourLayer?.boats||[]){
  const cockpit=id===boatViewId&&cameraMode==='cockpit'&&!replayFrames;
  setBoatCockpit(rig,cockpit);
  setBoatLighting(rig,timeOfDay.mode==='night');
  if(cockpit){const state=harbourControls.state,boat=state?.boats?.find(b=>b.id===id);if(boat)updateBoatAvionics(rig,boat,state,now);}
 }
 if(boatViewId&&!replayFrames){
  const rig=harbourLayer?.boats.get(boatViewId),body=rig?.bodies.get('airframe');
  if(rig?.root.visible&&body?.visible){
   const q=body.quaternion;
   const view=boatCameraView({position:body.position.toArray(),quaternion_wxyz:[q.w,q.x,q.y,q.z]},{mode:cameraMode,yaw:cockpitYaw,pitch:cockpitPitch});
   if(view){
    if(cameraMode==='cockpit'){camera.position.set(...view.position);camera.up.set(...view.up);camera.lookAt(...view.target);}
    else if(cameraMode==='chase'||cameraMode==='orbit'){
     const target=new THREE.Vector3(...view.target),delta=target.clone().sub(orbit.target);
     if(orbit.target.distanceTo(target)>100)camera.position.set(...view.position);else camera.position.add(delta);
     orbit.target.copy(target);camera.up.set(0,0,1);orbit.update();
    }else if(cameraMode==='free')freeCam.update(frameDt);
    sky.follow(camera.position);
   }
  }
 }
 phantomAvionics.update(truth?.body_poses?.cabin,last?.observation,!!truth?.phantom&&!rideEnabled&&!boatViewId&&cameraMode==='cockpit'&&modelReady&&!replayFrames,now-latestTruthReceivedMs>2000);
 const doorState=boatViewId?harbourControls.state?.iris??last?.iris:last?.iris;
 const portalControls=document.getElementById('iris-controls');portalControls.hidden=!world?.vaderland?.operations||!!replayFrames||worldUnavailable;
 if(!portalControls.hidden){document.querySelector('#district-view option[value="plaza"]').hidden=!world.vaderland.civic_district;const side=document.getElementById('iris-side').value,travel=doorState?.[side]??1;
  document.getElementById('iris-state').textContent=irisFeedback||(travel>=.999?'Open':travel<=.001?'Closed':Math.round(travel*100)+'% open');}
 const sceneryTime=boatViewId?harbourControls.state?.t_s:(!last?.active&&!replayFrames?last?.scenery_time_s:undefined)??truth?.t_s;
 const cityTime=world?.vaderland?.quarter&&!boatViewId&&!replayFrames?cityClock.at(now,sceneryTime):sceneryTime;
 sky.update(camera,now/1000);environment.vaderland?.update(camera,now/1000,timeOfDay.mode,cityTime??0,doorState,last?.course_timing,last?.active?last.observation?.gnss_xy_m:null);environment.buildings?.update(now/1000);environment.volcano?.update(now/1000);environment.serviceRoads?.update(now/1000,last?.observation?.gnss_xy_m);
 gameAudio.update({clock:now,world,listener:camera.position,
  right:listenerRight.setFromMatrixColumn(camera.matrixWorld,0),
  cockpit:cameraMode==='cockpit',water:!!boatViewId,truth:requestedAsset?truth:null,
  observation:replayFrames?null:last?.observation,timing:last?.course_timing,
  active:!replayFrames&&!!last?.active&&!last?.paused,doors:doorState,neighbours:audibleTraffic});
  aircraftFx?.update(replayFrames?null:last?.observation?.rotor_rpm,now/1000);
 // Never reveal an initial origin frame or the prior mission's frame.
 const physicalFix=boatViewId?harbourLayer?.boats.get(boatViewId)?.bodies.get('airframe')?.position:physicalAircraftPosition(truth);
 const revealReady=startupFrameReady({worldReady:!!world,offline:visualOnlyOffline,physicalPosition:physicalFix,transition:missionTransition,view:last});
 if(revealReady&&!window.__vtxNoRender){
  if(post)post.render();else renderer.render(scene,camera);
  renderer.domElement.style.visibility='visible';
  if(missionTransition){missionTransition=null;if(modelReady)$('loading').hidden=true;}
 }
 const age=now-latestTruthReceivedMs;
 if(last&&!replayFrames&&age>2000&&!panelWasStale){aircraftFx?.updateAvionics?.(last.observation,true);panelWasStale=true;showAttitude(last.rendering_truth,'STALE');drawMaps(true);}
 const status=$('view-sync');if(status&&!rideEnabled&&!boatViewId&&now-(status._last||0)>400){status._last=now;
  status.textContent=replayFrames&&worldUnavailable?'REPLAY · RECORDED TERRAIN UNAVAILABLE':worldUnavailable?'TERRAIN UNAVAILABLE · WAITING FOR MATCHING WORLD':replayFrames?`REPLAY · t ${truth?.t_s?.toFixed(1)??'--'}s`:!last?'WAITING FOR DATA':age>2000?'DISPLAY STALE':!modelReady?'LOADING AIRCRAFT':`LIVE VIEW · ${Math.round(age)} ms · ${Math.round(last?.observation?.rotor_rpm?.[0]||0)} RPM · t ${last?.observation?.t_s?.toFixed(1)??'--'}s`;
  status.style.color=(worldUnavailable||(!replayFrames&&age>2000))?'#ffb19d':'#b6f6d8';
 }
}animate();
