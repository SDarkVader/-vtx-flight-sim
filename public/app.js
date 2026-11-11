import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {mergeGeometries} from './vendor/BufferGeometryUtils.js';
import {tiltFromDirection} from './tilt-direction.js?v=fan-direction-6';
import {zoomDistance} from './camera-zoom.js?v=1';
import {rotorVisualOffset} from './rotor-visual.js?v=1';
import {physicalCameraTarget} from './physical-camera-target.js?v=1';
import {cockpitAxes,cockpitHorizon} from './cockpit-axes.js?v=1';
import {cockpitTelemetry} from './cockpit-telemetry.js?v=1';
import {isCockpitObstruction,setCockpitVisibility} from './cockpit-visibility.js?v=4';
// Vader's Taxis environment (visual only; physics collision comes from world.py).
import {buildSky} from './vtx-env/sky.js?v=1';
import {buildTerrain,makeHills,makeSkyline,makeFarForest,makeWater} from './vtx-env/landscape.js?v=1';
import {buildBuildings} from './vtx-env/buildings.js?v=3';
import {buildAirfield} from './vtx-env/airfield.js?v=6';
import {buildTrees,buildForecourt} from './vtx-env/vegetation.js?v=1';
import {enhanceAircraft} from './vtx-env/aircraft-look.js?v=phantom-beacon-20261107';
import {preparePhysicalVisual} from './vtx-env/physical-visual.js?v=1';
import {buildVolcanoBasement} from './vtx-env/volcano-basement.js?v=1';
import {TacticalMinimap} from './vtx-env/tactical-minimap.js?v=airport-scale-20261107';
import {buildServiceRoads} from './vtx-env/service-roads.js?v=2';
import {createFreeCamera} from './free-camera.js?v=4';
import {createVisualAirTraffic,clearOfPhysicalAircraft} from './vtx-env/visual-air-traffic.js?v=3';
import {RIDE_JOURNEYS,buildRideJourney} from './vtx-env/visual-ride-journeys.js?v=3';
import {buildRideTrajectory,sampleRideTrajectory,inspectRideClearance} from './vtx-env/ride-trajectory.js?v=1';
import {attachVisualPhantom,animateVisualPhantom} from './vtx-env/visual-phantom-animation.js?v=2';
import {createAirportOperations} from './vtx-env/airport-operations.js?v=1';
import {VEHICLE_MODELS,DEFAULT_VISUAL_MODEL} from './vtx-env/vehicle-registry.js?v=2';
import {makeAirportModel} from './vtx-env/airport-models.js?v=1';
import {attachAirportEnergyEffects} from './vtx-env/airport-energy-effects.js?v=1';
import {attachPhantom,updatePhantom,detachPhantomEffects} from './vtx-env/phantom-look.js?v=20261110-wheel-axle-y';import {createPhantomPanel} from './phantom-controls.js?v=4-pilot-command';let phantomRig=null,phantomPanel=null; // Phantom hooks (render + phantom-fbw-1 panel)

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
 const provenance=view.rendering_truth?.provenance||{};
 const config=view.observation?.configuration?.config_sha256||provenance.config_sha256;
 const physics=provenance.physics_revision||(config?`config ${config.slice(0,12)}`:'physics identity unavailable');
 const runtime=view.runtime_source_sha256;
 const node=$('revision');
 const id=view.observation?.configuration?.identity;
 const badge=id?(id.verified?' · IDENTITY VERIFIED':id.experimental?' · EXPERIMENTAL CONFIG':id.pinned?' · IDENTITY MISMATCH':' · not pinned'):'';
 const visual=id?.render_asset_sha256?` · visual ${id.render_asset_sha256.slice(0,8)}`:'';
 const commit=id?.git_commit?` · git ${id.git_commit.slice(0,7)}`:'';
 node.textContent=`${provenance.revision||'unknown model'} · ${physics}${visual}${commit}${runtime?' · code '+runtime.slice(0,8):''}${badge}`;
 node.style.color=id&&id.pinned&&!id.verified&&!id.experimental?'#ff7a6b':'';
 node.title=`Model: ${provenance.revision||'unknown'}; physics: ${provenance.physics_revision||'parameter configuration'}; config SHA-256: ${config||'not supplied'}; model XML SHA-256: ${provenance.model_xml_sha256||'not supplied'}; runtime SHA-256: ${runtime||'not supplied'}${id?`; parameter file SHA-256: ${id.parameter_file_sha256}; visual asset: ${id.render_asset} SHA-256 ${id.render_asset_sha256}; git commit: ${id.git_commit||'not a git checkout'}; identity: ${id.status}`:''}`;
}
let last=null,world=null,model=null,pick='a',cameraMode='chase',replayFrames=null,replayFrame=0;
let departure=[-700,0],destination=[-50,20],track=[],lastDecision='',lastRun=null;
const bodyNodes={},pitchMeshes=[];
const rotorSpinAxis=new THREE.Vector3(0,0,1),rotorSpinQ=new THREE.Quaternion();
let latestTruthReceivedMs=0,lastHudUpdateMs=0,panelWasStale=false;
const command={engine:1,collective_deg:[0,0,0,0],tilt_deg:[[0,0],[0,0],[0,0],[0,0]],cabin_deg:[0,0,0],cabin_level:true};
let dirty=false,manualBeat=0,manualOwned=false;
const tiltSpin=[0,0,0,0],tiltSpinAngle=[0,0,0,0];
const manualChannel=new BroadcastChannel('vtx-manual-authority');
manualChannel.onmessage=()=>{manualOwned=false;tiltSpin.fill(0);keys.clear();};
async function api(path,body){
 const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;
}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,6500);}
function guard(fn){return async(...args)=>{try{await fn(...args);}catch(e){toast(e.message);}};}
function selectedFuel(){const value=Number($('initial-fuel').value);if(!Number.isFinite(value)||value<1||value>110)throw Error('Use total fuel loading between 1 and 110 kg.');return value;}
function selectedWind(){return ['wind-east','wind-north','wind-up'].map(id=>{const value=Number($(id).value);if(!Number.isFinite(value))throw Error('Enter finite wind components.');return value;});}

console.log('VTX: module ready');
const viewport=$('viewport'),scene=new THREE.Scene();const mobile=matchMedia('(pointer:coarse)').matches||innerWidth<800;
const mobileView=mobile;
// Phones default to the lighter display path. The physics and model are unchanged.
const lightweightView=mobile||new URLSearchParams(location.search).has('lite');
// Rendering quality tier (visual only; physics unaffected): phone low, ?lite lite, desktop high, ?quality= overrides.
import {resolveQuality} from './vtx-env/quality.js?v=gfx-20261111-ultra';import {createGround} from './vtx-env/ground.js?v=gfx-20261103-1';import {createLightPool} from './vtx-env/light-pool.js?v=gfx-20261103-1';import {dressWorld} from './vtx-env/world-dressing.js?v=gfx-20261103-1';
import {createPost} from './vtx-env/post.js?v=1';import {createTimeOfDay} from './vtx-env/time-of-day.js?v=1';import {buildAirfieldKit} from './vtx-env/airfield-kit.js?v=1';
const quality=resolveQuality({mobile,search:location.search});scene.userData.quality=quality.name;
// On phones keep retained-flight actions and indicator bar directly below the flight view.
if (innerWidth <= 800) {
 document.querySelector('header').after($('retry-bar'));
 $('viewport').after(document.querySelector('footer'));
}
const camera=new THREE.PerspectiveCamera(48,1,.1,6000);camera.up.set(0,0,1);camera.position.set(9,-11,8);
const renderer=new THREE.WebGLRenderer({antialias:quality.antialias,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,quality.pixelRatio));renderer.shadowMap.enabled=quality.shadows;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=quality.toneMapping;renderer.toneMappingExposure=quality.exposure;viewport.appendChild(renderer.domElement);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.target.set(0,0,1.4);orbit.enableDamping=true;orbit.enablePan=false;orbit.maxPolarAngle=Math.PI*.49;orbit.minDistance=2;orbit.maxDistance=600;
// Keep pinch gestures on the renderer and avoid two-finger panning fighting the chase target.
orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';
const freeCam=createFreeCamera(camera,renderer,viewport,m=>setCameraMode(m));
const sky=buildSky(scene,renderer,{quality}),environment={};
// Desktop-app tier only: post-processing. Day/night is presentation only and never touches the physics.
const post=createPost(renderer,scene,camera,quality);
const timeOfDay=createTimeOfDay({scene,sky,renderer,getPost:()=>post,environment});
const rideCgLocal=[-0.15156246846624952,0.00004531509472356366,0.5529781802070567];
let visualTraffic=null,airportOperations=null,rideRoute=null,rideTime=0,rideLastFrame=0,ridePaused=false,ridePose=null,rideActor=null,ridePlan=null;
let sceneTime=0,sceneScale=1,selectedVehicleId='physical-plant',passengerRide=new URLSearchParams(location.search).has('trafficRide');
let pendingRideExteriorMode=null;
let rideEnabled=false;
const trafficPreviewEnabled=true;
{
 const panel=document.createElement('div');panel.id='ride-controls';
 panel.innerHTML=`<label>Aircraft <select id="airport-aircraft"><option value="a10-primary">Phantom A10</option><option value="r6-flight">Argon R6 · holding</option><option value="r6-training">Argon R6 · training</option><option value="r6-teardrop">Argon R6 · teardrop</option><option value="r6-go-around">Argon R6 · go around</option><option value="physical-plant">Colin · physical</option></select></label><label>Camera <select id="airport-camera"><option value="chase">Chase</option><option value="cockpit">Cockpit</option><option value="free">Exterior / free</option><option value="orbit">Top</option></select></label><details id="airport-ops"><summary>Flight ops</summary><div class="airport-menu"><label>Journey <select id="ride-route">${RIDE_JOURNEYS.map(r=>`<option value="${r.id}">${r.label}</option>`).join('')}</select></label><label>Direction <select id="ride-direction"><option value="left">Left-hand</option><option value="right">Right-hand</option></select></label><button id="ride-start" type="button">Start passenger ride</button><label>Traffic <select id="traffic-density"><option value="5">Full · 5 aircraft</option><option value="4">Standard · 4</option><option value="3">Mobile · 3</option><option value="2">Light · 2</option></select></label><label>Speed <select id="airport-speed"><option value="1">1×</option><option value="2">2×</option><option value="0.5">0.5×</option></select></label><div class="airport-menu-actions"><button id="ride-pause" type="button">Pause</button><button id="ride-restart" type="button">Restart</button></div><span id="ride-progress" aria-live="polite">Loading airport...</span><div class="airport-menu-actions" id="airport-extra"></div></div></details>`;
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
  nightButton.onclick=()=>{nightButton.textContent=timeOfDay.toggle()==='night'?'Day':'Night';};
  cameraTools.append(nightButton);
  if(new URLSearchParams(location.search).get('time')==='night'){timeOfDay.set('night');nightButton.textContent='Day';}
  function recenterPhysicalVehicle(){
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
 document.getElementById('ride-pause').onclick=()=>{ridePaused=!ridePaused;document.getElementById('ride-pause').textContent=ridePaused?'Resume':'Pause';};
 document.getElementById('ride-restart').onclick=()=>{sceneTime=0;rideTime=0;ridePaused=false;rideLastFrame=performance.now();document.getElementById('ride-pause').textContent='Pause';};
  const changeJourney=()=>{
    const plan=buildRideJourney($('ride-route').value,$('ride-direction').value,rideCgLocal[2]);
    const nextRoute=buildRideTrajectory(plan.points,{cruiseSpeed:plan.speed});
    if(world){const audit=inspectRideClearance(nextRoute,world);if(!audit.ok){toast('Flight route refused: '+audit.failures[0].reason);return;}}
    if(world&&!plan.waypoints.every(p=>Math.abs(p.position[0])<world.half_m&&Math.abs(p.position[1])<world.half_m)){
      toast('Route exceeds this simulation terrain');return;
    }
    ridePlan=plan;rideRoute=nextRoute;
    rideTime=0;rideLastFrame=performance.now();ridePaused=false;
    $('ride-pause').textContent='Pause';
    $('ride-progress').textContent=plan.label+' · '+plan.direction+' circuit · starting at runway';
  };
  $('ride-route').onchange=changeJourney;
  $('ride-direction').onchange=changeJourney;
 $('ride-start').onclick=()=>{changeJourney();passengerRide=true;selectedVehicleId='a10-primary';rideEnabled=true;$('airport-aircraft').value=selectedVehicleId;$('airport-ops').open=false;showRideAircraft('chase');};
 $('airport-aircraft').onchange=()=>{selectedVehicleId=$('airport-aircraft').value;rideEnabled=selectedVehicleId!=='physical-plant';if(rideEnabled)showRideAircraft('chase');else {if(model)model.visible=true;setCameraMode('chase');} $('view-mode').textContent=rideEnabled?'SCRIPTED VISUAL TRAFFIC · NO COLLISION PHYSICS':'PHYSICAL STATE · LIVE';};
 $('airport-aircraft').value='physical-plant';
  $('traffic-density').value=mobile?'3':'5';
 $('traffic-density').onchange=()=>airportOperations?.setDensity($('traffic-density').value);
 $('airport-speed').onchange=()=>{sceneScale=Number($('airport-speed').value);};
 $('airport-camera').onchange=()=>{const mode=$('airport-camera').value;if(mode==='orbit')$('view-top').click();else if(rideEnabled&&mode==='chase')showRideAircraft('chase');else setCameraMode(mode);};
  $('view-mode').textContent='PHYSICAL STATE - LIVE';
}
const lightPool=createLightPool(scene,quality.localLights);scene.onBeforeRender=(r,s,cam)=>lightPool.update(cam);
const resize=()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);post?.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(viewport);
const worldGroup=new THREE.Group();worldGroup.name='vtx-world';scene.add(worldGroup);
function plane(w,h,color,x,y,z,parent=worldGroup){const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({color,roughness:.95}));m.position.set(x,y,z);m.receiveShadow=true;parent.add(m);return m;}
function makeLabel(text,color='#7cdfcb'){
 const c=document.createElement('canvas');c.width=128;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.beginPath();ctx.arc(64,64,49,0,Math.PI*2);ctx.fill();ctx.fillStyle='#143934';ctx.font='bold 62px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,64,67);const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:true}));sprite.scale.set(1.8,1.8,1.8);scene.add(sprite);return sprite;
}
const markerA=makeLabel('A'),markerB=makeLabel('B','#ffc88b');
 const START_PRESETS={
 airport:[
  ['-700,0','Runway 08 threshold'],
  ['3800,0','Runway 26 threshold'],
  ['300,0','Runway centre'],
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
};
let currentEnvironment='airport';
function syncEnvironmentControls(envKey){
 currentEnvironment=envKey==='sandbox'?'sandbox':'airport';
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
  const opts=START_PRESETS[currentEnvironment]||START_PRESETS.airport;
  const depKey=departure.join(',');
  preset.replaceChildren(...opts.map(([val,label])=>{const o=document.createElement('option');o.value=val;o.textContent=label;return o;}));
  preset.value=opts.some(([v])=>v===depKey)?depKey:'custom';
 }
 const rwyBtn=$('runway-start');
 if(rwyBtn){
  rwyBtn.textContent=currentEnvironment==='sandbox'?'Set A: sandbox runway 09 start':'Set A: runway 08 start';
  rwyBtn.title=currentEnvironment==='sandbox'?'Sandbox runway 09 threshold at X -700 m, Y 0 m (1,650 m takeoff roll along +X)':'Runway 08 start, 15 m inside the marked threshold';
 }
 const caption=$('scene-caption');
 if(caption){
  caption.innerHTML=currentEnvironment==='sandbox'
   ?'<span>STAGE 1 / VALLEY TEST RANGE</span><p>2,000 × 2,000 m · 1,900 m east-west runway, terrain and ground contact</p>'
   :'<span>VTX / EXTENDED AIRFIELD</span><p>8,000 × 8,000 m · terrain, extended runway and ground contact</p>';
 }
}
function clearWorldGroup(){
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
function buildSandboxWorld(w){
 const n=w.heights_m.length,g=new THREE.PlaneGeometry(w.half_m*2,w.half_m*2,n-1,n-1),p=g.attributes.position,colors=[];
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){
  const idx=(n-1-j)*n+i,z=w.heights_m[j][i];p.setZ(idx,z);
  const c=new THREE.Color().setHSL(.34-.08*Math.min(1,z/45),.27,.29+.17*Math.min(1,z/48));colors.push(c.r,c.g,c.b);
 }
 g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();
 const terrain=new THREE.Mesh(g,new THREE.MeshStandardMaterial({vertexColors:true,roughness:.92,metalness:.03}));terrain.name='terrain-visual';terrain.receiveShadow=true;worldGroup.add(terrain);
 const hills=makeHills(w);worldGroup.add(hills.mesh,makeSkyline(hills.heightAt),makeFarForest(hills.heightAt,quality.forest,w.half_m));
 // Primary east-west Sandbox Runway 09/27 (1,900 m × 42 m along +X) aligned with A10-B heading, plus cross apron
 plane(1900,42,0x383e42,0,0,.03,worldGroup);plane(1840,1.2,0xd8ddd4,0,0,.05,worldGroup);
 for(let rx=-880;rx<=880;rx+=40)plane(18,.55,0xf0f4ee,rx,0,.055,worldGroup);
 plane(36,320,0x5c6668,0,0,.025,worldGroup);
 const grid=new THREE.GridHelper(360,36,0xc3d4ca,0x71897c);grid.rotation.x=Math.PI/2;grid.position.z=.04;grid.material.opacity=.24;grid.material.transparent=true;worldGroup.add(grid);
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
 world=w;
 const isSandbox=w.environment==='sandbox'||w.id==='stage1-valley';
 clearWorldGroup();
 if(!isSandbox&&trafficPreviewEnabled&&!visualTraffic){
  airportOperations=createAirportOperations(w);
  airportOperations.setDensity($('traffic-density').value);
  const plan=buildRideJourney($('ride-route').value,$('ride-direction').value,rideCgLocal[2]);
  ridePlan=plan;rideRoute=buildRideTrajectory(plan.points,{cruiseSpeed:plan.speed});
  // Only the physical A10 is shown. A second scripted A10 can look like
  // the active aircraft and rotate about its separate trajectory pivot.
  const specs=airportOperations.actors.filter(actor=>actor.id!=='a10-primary').map(actor=>{
   const modelSpec=VEHICLE_MODELS[actor.modelId],isA10=actor.id==='a10-primary',isRotor=modelSpec.animation==='rotor';
   return {id:actor.id,asset:modelSpec.asset,cgLocal:modelSpec.cgLocal,rotateToZUp:modelSpec.rotateToZUp,
    prepareSource:actor.modelId==='r6'?root=>enhanceAircraft(root,scene.environment):undefined,
    validate:actor.modelId==='r6'?root=>{
     let meshes=0;root.traverse(node=>{if(node.isMesh)meshes++;});
     return meshes>=691&&[1,2,3,4].every(i=>root.getObjectByName('rotor'+i))&&[1,2,3,4,5,6].every(i=>root.getObjectByName('gear'+i));
    }:undefined,
    makeModel:modelSpec.asset?undefined:THREE=>makeAirportModel(THREE,modelSpec.kind==='ground'?'ground':modelSpec.kind==='rotorcraft'?'rotorcraft':'fixed-wing',actor.color),
    visible:()=>{
     if(world?.environment==='sandbox'||world?.id==='stage1-valley')return false;
     if(!(airportOperations.isVisible(actor.id)||selectedVehicleId===actor.id))return false;
     const physical=!rideEnabled&&last?.rendering_truth?.body_poses?.airframe?.position;
     return clearOfPhysicalAircraft(airportOperations.sample(actor.id,sceneTime).position,physical);
    },
    poseAt:t=>isA10&&passengerRide&&rideRoute?{...sampleRideTrajectory(rideRoute,rideTime),operation:'passenger ride',mode:'scripted'}:airportOperations.sample(actor.id,t),
    onLoad:root=>{
     const rig=isA10?attachVisualPhantom(root):null;
     if(isA10){
      $('ride-controls').dataset.a10Joints=String(rig.joints.length);
      if(rig.joints.length!==28)toast('A10 articulation unavailable: expected 28 joints');
      $('loading').hidden=true;$('view-sync').textContent='A10 READY · SCRIPTED TRAFFIC';
     }
     if(selectedVehicleId===actor.id)requestAnimationFrame(()=>showRideAircraft(cameraMode));
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
    onProgress:event=>{if(isA10)$('loading').textContent=event.total?'Loading latest A10: '+Math.round(100*event.loaded/event.total)+'%':'Loading latest A10: '+Math.round(event.loaded/1024)+' KB';},
    onError:error=>{if(isA10){$('loading').hidden=false;$('loading').textContent='A10 model failed: '+(error?.message||'asset unavailable');$('view-sync').textContent='A10 MODEL LOAD ERROR';}else if(actor.modelId==='r6')toast('R6 model failed to load: '+(error?.message||'asset unavailable'));},
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
 if(isSandbox){
  if(rideEnabled){
   selectedVehicleId='physical-plant';rideEnabled=false;$('airport-aircraft').value='physical-plant';
   if(model)model.visible=modelReady;setCameraMode('chase');$('view-mode').textContent='PHYSICAL STATE · LIVE';
  }
  buildSandboxWorld(w);
 }else{
  // Ground uses the same heightfield samples as the physics terrain; the distant landscape lies outside the +/-500 m test area.
  worldGroup.add(buildTerrain(w));
  const hills=makeHills(w);worldGroup.add(hills.mesh,makeSkyline(hills.heightAt),makeFarForest(hills.heightAt,quality.forest,w.half_m));const ground=createGround(w,hills.mesh);
  const groundZ=(x,y)=>Math.max(Math.abs(x),Math.abs(y))<=w.half_m?surfaceZ(x,y):ground.heightAt(x,y);
  // Buildings are dressed onto the physical obstacle boxes; airfield markings are flush paint.
  environment.buildings=buildBuildings(worldGroup,w,{ppm:quality.facadePpm,quality});environment.kit=buildAirfieldKit(worldGroup,w,{quality});buildAirfield(worldGroup,{ppm:quality.airfieldPpm,quality,world:w});buildTrees(worldGroup,w,{quality});buildForecourt(worldGroup,w);environment.volcano=buildVolcanoBasement(worldGroup,w);environment.serviceRoads=buildServiceRoads(worldGroup,w,groundZ);
  worldGroup.add(makeWater(w,surfaceZ(w.water.x,w.water.y)+.1));
  environment.dressing=dressWorld(worldGroup,w,ground,{quality,lightPool,extraTextures:[markerA.material.map,markerB.material.map]});
 }
 timeOfDay.refresh();
 syncEnvironmentControls(isSandbox?'sandbox':'airport');
 for(const c of [$('map'),$('large-map')]){
  const mm=getMinimap(c);
  if(mm){
   mm.tacticalMode=false;
   mm.zoom=isSandbox?1.0:0.5;
   mm.center=isSandbox?[0,0]:[0,100];
  }
 }
 if($('map-mode'))$('map-mode').textContent='World';
 updateMarkers();drawMaps(true);console.log('VTX: terrain ready',w.id);
}
let aircraftFx=null,loadedAsset=null,assetRetryAfter=0,modelReady=false;
function disposeModel(root){
 const geometries=new Set(),materials=new Set(),textures=new Set();
 root.traverse(n=>{if(!n.isMesh)return;if(n.geometry)geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});
 geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}
// Render-only visual pass (tools/phantom/refine_phantom_visual.py): smooth shell, livery, rivets, exposed wing bay.
// Approved Blendstra mesh with restored, independently byte-verified joint metadata.
// The preserved GLB has the same mesh, accessor, texture, animation and BIN bytes as the approved export.
// ?cad=1 selects the separate raw CAD source for engineering inspection only.
const VISUAL_ASSET={'/assets/phantom-a10.glb':'/assets/phantom-a10-blendstra-81c823e2.glb'};
function visualAsset(a){return a&&!new URLSearchParams(location.search).has('cad')?(VISUAL_ASSET[a]||a):a;}
function loadAirframe(asset){
 if(asset===loadedAsset||performance.now()<assetRetryAfter)return;loadedAsset=asset;
 modelReady=false;if(model)model.visible=false;
 $('loading').hidden=false;$('loading').textContent='Loading physical revision…';
 new GLTFLoader().load(asset+(asset.includes('?')?'&':'?')+'v=20261106-zup-pose-bound-1',async g=>{
 if(asset!==loadedAsset){disposeModel(g.scene);return;}
 if(model){detachPhantomEffects(phantomRig);scene.remove(model);disposeModel(model);}
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
 aircraftFx?.setCockpitMode?.(cameraMode==='cockpit');aircraftFx?.updateAvionics?.(last?.observation);
 setCockpitVisibility(model,cameraMode==='cockpit');
 // Display-only batching retains every triangle and the source IDs; the mass
 // ledger/colliders remain per-part. Keep independently pitched blades separate.
 const sourceModel=model,geometryRefs=new Map();
 sourceModel.traverse(n=>{if(n.isMesh)geometryRefs.set(n.geometry,(geometryRefs.get(n.geometry)||0)+1);});
 let batchStarted=performance.now();
 for(const body of Object.values(bodyNodes)){
  const batches=new Map();
  for(const n of [...body.children])if(n.isMesh&&!n.userData.pitch_axis&&!isCockpitObstruction(n)&&!Array.isArray(n.material)){
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
modelReady=true;$('loading').hidden=true;
 },undefined,e=>{if(asset===loadedAsset){loadedAsset=null;assetRetryAfter=performance.now()+5000;$('loading').textContent='Aircraft asset failed to load; retrying…';}console.error(e);});
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
 const variant=$('airframe').value;
 const verdict=await api(`/api/validate?x=${p[0]}&y=${p[1]}&variant=${encodeURIComponent(variant)}`);
 const valid=verdict.valid ?? verdict.ok;
 $('validation').textContent=`${pick.toUpperCase()} (${p.join(', ')}): ${verdict.reason}`;
 $('large-validation').textContent=$('validation').textContent;
 if(pick==='a'){
  if(!valid){toast(verdict.reason);return;}
  departure=p;$('dep').value=p.join(', ');
  const preset=$('start-preset');const key=p.join(',');
  preset.value=[...preset.options].some(o=>o.value===key)?key:'custom';
  if(!last?.active)document.dispatchEvent(new CustomEvent('vtx-preview-start'));
 }else{
  if(last?.active){const result=await api('/api/destination',{run_id:last.run_id,destination:p});toast(result.landing_valid?'Target B changed in flight':'Target B changed; landing clearance not certified');}
  else if(Math.max(...p.map(Math.abs))>world.half_m-8){toast('Outside surveyed map');return;}
  destination=p;$('dest').value=p.join(', ');
 }
 updateMarkers();drawMaps();
}
async function switchEnvironment(envKey){
 const target=envKey==='sandbox'?'sandbox':'airport';
 if(last?.active){
  syncEnvironmentControls(currentEnvironment);
  toast('End and retain the current sortie before switching environments.');
  return;
 }
 const cockpit=$('cockpit-workspace');
 if(cockpit?.hidden){
  const btn=document.querySelector('.workspace-pages button[aria-controls="cockpit-workspace"]');
  btn?.click();
 }
 const variant=$('airframe').value;
 const startCfg=$('phantom-start').value;
 const res=await api('/api/environment',{environment:target,airframe_variant:variant,start_configuration:startCfg});
 if(res.world){
  departure=[...(res.world.default_departure||[-700,0])];
  destination=[...(res.world.default_destination||[-50,20])];
  $('dep').value=departure.join(', ');
  $('dest').value=destination.join(', ');
  buildWorld(res.world);
 }
 if(res.view){
  updateView(res.view);
  const camTarget=physicalCameraTarget(res.view.rendering_truth);
  if(camTarget){
   const nextPos=new THREE.Vector3(...camTarget);
   const delta=nextPos.clone().sub(orbit.target);
   camera.position.add(delta);
   orbit.target.copy(nextPos);
   camera.up.set(0,0,1);
   orbit.update();
  }
 }
 toast(target==='sandbox'
  ?`Switched to Test Sandbox (${departure.join(', ')} m).`
  :`Switched to Main Airport (${departure.join(', ')} m).`);
}
if($('env-airport'))$('env-airport').onclick=guard(()=>switchEnvironment('airport'));
if($('env-sandbox'))$('env-sandbox').onclick=guard(()=>switchEnvironment('sandbox'));
if($('environment-select'))$('environment-select').onchange=guard(()=>switchEnvironment($('environment-select').value));
$('start-preset').onchange=guard(async()=>{const value=$('start-preset').value;if(value==='custom')return;pick='a';await choosePoint(value.split(',').map(Number));});
$('map').onclick=guard(e=>onMap(e,$('map')));$('large-map').onclick=guard(e=>onMap(e,$('large-map')));
function setPick(p){pick=p;$('pick-a').classList.toggle('selected',p==='a');$('pick-b').classList.toggle('selected',p==='b');$('large-pick').textContent=p.toUpperCase();}
$('runway-start').onclick=guard(async()=>{pick='a';const pt=[-700,0];await choosePoint(pt);toast(currentEnvironment==='sandbox'?'Departure set at sandbox runway 09 threshold: X -700 m, Y 0 m.':'Departure set near runway 08 threshold: X -700 m, Y 0 m.');});
$('pick-a').onclick=()=>setPick('a');$('pick-b').onclick=()=>setPick('b');
for(const [id,p] of [['dep','a'],['dest','b']])$(id).onchange=guard(async()=>{const vals=$(id).value.split(',').map(Number);if(vals.length!==2||vals.some(v=>!Number.isFinite(v)))throw Error('Use two finite coordinates: east, north');setPick(p);await choosePoint(vals);});
$('map-zoom').onclick=()=>{$('map-dialog').showModal();drawMaps(true);};
const mapModeBtn=$('map-mode');
if(mapModeBtn){
  mapModeBtn.onclick=()=>{
    const mm=getMinimap($('map'));
    if(mm){
      const isSandbox=currentEnvironment==='sandbox';
      mm.tacticalMode=!mm.tacticalMode;
      mm.zoom=mm.tacticalMode?1000/(world.half_m*2*Math.max(1,$('map').width/$('map').height)):(isSandbox?1.0:0.5);
      mm.center=mm.tacticalMode?[0,0]:(isSandbox?[0,0]:[0,100]);
      mapModeBtn.textContent=mm.tacticalMode?(isSandbox?'Sandbox':'Airport'):'World';
      $('grid-label').textContent=mm.tacticalMode?'1 km grid':'200 m grid';
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
$('start').onclick=guard(async()=>{replayFrames=null;const variant=$('airframe').value,phantom=variant.startsWith('phantom');const request={environment:currentEnvironment,departure,destination,ignore_scenery_collisions:$('ignore-scenery').checked,landing_precision_m:$('landing-precision').value===''?null:Number($('landing-precision').value),authority:$('pilot').value,time_scale:+$('scale').value,airframe_variant:variant,label:'Map-selected live ground-to-ground attempt'};if(phantom)request.phantom={start_configuration:$('phantom-start').value};if(!phantom)Object.assign(request,{stability_assist:+$('assist').value/100,reference_rpm:+$('drive').value,gear_variant:$('gear').value,fuel_kg:selectedFuel(),engine_power_limit_kw:+$('power-limit').value,atmosphere_model:$('atmosphere-model').value,wind_world_mps:selectedWind()});const r=await api('/api/mission',request);manualOwned=$('pilot').value==='manual';if(manualOwned)manualChannel.postMessage('takeover');track=[];if(!phantom){command.engine=1;$('engine').value=1;$('engine-value').value='100%';dirty=manualOwned;}toast('Sortie '+r.run_id+' started on the landing gear.');});
$('end').onclick=guard(async()=>{const r=await api('/api/stop',{reason:'Operator ended the live attempt'});toast(`Recorded: ${r.outcome}. Every failed attempt is retained.`);});
for(const authority of ['manual','colin'])$('retry-'+authority).onclick=guard(async()=>{
 replayFrames=null;
 const r=await api('/api/retry',{authority,time_scale:authority==='colin'?.02:.1,stability_assist:+$('assist').value/100});
 manualOwned=authority==='manual';if(manualOwned)manualChannel.postMessage('takeover');
 command.engine=1;command.collective_deg.fill(0);command.tilt_deg=[[0,0],[0,0],[0,0],[0,0]];$('engine').value=1;$('engine-value').value='100%';dirty=manualOwned;
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
 await api('/api/operator',{authority:'manual'});manualChannel.postMessage('takeover');manualOwned=true;$('pilot').value='manual';dirty=true;toast('Manual authority acquired with the current actuator settings.');
});
$('scale').onchange=guard(async()=>{await api('/api/operator',{time_scale:+$('scale').value});});
$('feather').onclick=()=>{command.engine=0;command.collective_deg.fill(0);$('engine').value=0;$('engine').oninput();$('common').value=0;$('common').oninput();dirty=true;};
let cockpitYaw=0,cockpitPitch=0,cockpitPointer=null,savedChaseOffset=null;
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
  const previous=cameraMode;
  const actor=rideEnabled?visualTraffic?.getActor(selectedVehicleId)?.root:null;
  if(rideEnabled){
    if(previous==='chase'&&actor&&rideChaseInitialised)rideChaseOffset.copy(camera.position).sub(orbit.target);
  }else if(previous==='chase'&&mode==='cockpit'){
    savedChaseOffset=camera.position.clone().sub(orbit.target);
  }
  cameraMode=mode;
  setCockpitVisibility(rideEnabled?actor?.children?.[0]?.children?.[0]:model,mode==='cockpit');
  if(!rideEnabled)aircraftFx?.setCockpitMode?.(mode==='cockpit');
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
  }else if(!rideEnabled&&mode==='chase'&&previous==='cockpit'){
    const target=physicalCameraTarget(last?.rendering_truth);
    if(target)orbit.target.set(...target);
    camera.up.set(0,0,1);
    camera.position.copy(orbit.target).add(savedChaseOffset||new THREE.Vector3(9,-11,8));
    orbit.update();
  }
  renderer.domElement.style.touchAction='none';
 $('cockpit-look').hidden=mode!=='cockpit';$('cockpit-instruments').hidden=mode!=='cockpit';$('cockpit-frame').hidden=mode!=='cockpit';
 $('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';
 $('camera').textContent=mode==='free'?'Exit free roam':'Free roam camera';
  if(rideEnabled){
    $('ride-locate').hidden=mode!=='free';
    $('ride-exterior').textContent=mode==='chase'?'Recenter aircraft':'Show aircraft';
  }
}
$('camera').onclick=()=>rideEnabled
  ?showRideAircraft(cameraMode==='free'?'chase':'free')
  :setCameraMode(cameraMode==='free'?'chase':'free');
$('cockpit').onclick=()=>rideEnabled&&cameraMode==='cockpit'
  ?showRideAircraft('chase')
  :setCameraMode(cameraMode==='cockpit'?'chase':'cockpit');
function zoomCamera(factor){
 if(cameraMode==='cockpit'){toast('Zoom is available in the external camera.');return;}
 if(cameraMode==='free'){freeCam.zoom(factor);return;}
 const offset=camera.position.clone().sub(orbit.target),distance=offset.length();
 if(distance<1e-9)return;
 camera.position.copy(orbit.target).add(offset.multiplyScalar(zoomDistance(distance,factor,orbit.minDistance,orbit.maxDistance)/distance));
 orbit.update();
}
$('zoom-in').onclick=()=>zoomCamera(.8);$('zoom-out').onclick=()=>zoomCamera(1.25);
$('view-top').onclick=()=>{
 const truth=replayFrames?.[replayFrame]||last?.rendering_truth,target=physicalCameraTarget(truth);
 if(rideEnabled){
    const actor=visualTraffic?.getActor(selectedVehicleId)?.root;
    if(actor)orbit.target.copy(actor.position).add(new THREE.Vector3(0,0,1.5));
  }else if(target)orbit.target.set(...target);
 const distance=rideEnabled?65:THREE.MathUtils.clamp(camera.position.distanceTo(orbit.target),18,orbit.maxDistance);
 setCameraMode('orbit');camera.up.set(0,0,1);camera.position.copy(orbit.target).add(new THREE.Vector3(0,-.01,distance));orbit.update();
};
$('look-left').onclick=()=>{cockpitYaw=THREE.MathUtils.clamp(cockpitYaw-Math.PI/12,-Math.PI/2,Math.PI/2);};
$('look-right').onclick=()=>{cockpitYaw=THREE.MathUtils.clamp(cockpitYaw+Math.PI/12,-Math.PI/2,Math.PI/2);};
$('look-center').onclick=()=>{cockpitYaw=0;cockpitPitch=0;};
renderer.domElement.addEventListener('pointerdown',e=>{if(cameraMode!=='cockpit')return;cockpitPointer={id:e.pointerId,x:e.clientX,y:e.clientY};renderer.domElement.setPointerCapture(e.pointerId);});
renderer.domElement.addEventListener('pointermove',e=>{if(cameraMode!=='cockpit'||!cockpitPointer||e.pointerId!==cockpitPointer.id)return;cockpitYaw=THREE.MathUtils.clamp(cockpitYaw-(e.clientX-cockpitPointer.x)*.006,-Math.PI/2,Math.PI/2);cockpitPitch=THREE.MathUtils.clamp(cockpitPitch-(e.clientY-cockpitPointer.y)*.006,-Math.PI/3,Math.PI/3);cockpitPointer.x=e.clientX;cockpitPointer.y=e.clientY;});
for(const event of ['pointerup','pointercancel','lostpointercapture'])renderer.domElement.addEventListener(event,()=>{cockpitPointer=null;});
renderer.domElement.addEventListener('dblclick',()=>{if(cameraMode==='cockpit'){cockpitYaw=0;cockpitPitch=0;}});
// Keyboard mixing is an explicitly disclosed mapping to the same raw channels.
// It reads keys only: no position, attitude, velocity or navigation feedback.
const keys=new Set();
function typing(e){return /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);}
addEventListener('keydown',e=>{
 if(typing(e)||document.querySelector('dialog[open]'))return;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code))e.preventDefault();
 if(e.code==='KeyC'&&!e.repeat)$('cockpit').click();
 if(last?.authority!=='manual'||!last.active||!manualOwned)return;
 if(e.code==='KeyX'&&!e.repeat){$('engine').value=command.engine>.5?0:1;$('engine').oninput();}
 if(e.code==='Space'){$('feather').click();keys.clear();}
 keys.add(e.code);
});
addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>keys.clear());
setInterval(()=>{
 if(!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames||!keys.size)return;
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
 const records=await api('/api/runs');$('runs').replaceChildren();$('timeline').hidden=true;
 for(const r of records){
  const article=document.createElement('article'),replayButton=document.createElement('button'),timelineButton=document.createElement('button');
  replayButton.textContent='Inspect recorded states';
  replayButton.onclick=guard(async()=>{const replay=await api('/api/replay/'+r.run_id);replayFrames=replay.frames;replayFrame=0;$('replay-time').max=Math.max(0,replayFrames.length-1);$('replay-controls').hidden=false;$('view-mode').textContent='POST-FLIGHT AUDIT · NO CONTROL';toast(replay.downsampled?`Inspection uses ${replay.frames.length} of ${replay.total_frames} recorded states; full log is retained.`:'Inspection only. The live physical plant remains separate.');});
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
  article.append(replayButton,timelineButton,document.createTextNode(`${r.run_id} · ${envTag} · ${r.outcome} · ${r.simulated_seconds.toFixed(1)} s · ${r.decisions} decisions`));$('runs').appendChild(article);
 }
 try{const archive=await api('/api/archive/runs');const heading=document.createElement('h3');heading.textContent='Historical PC flight summaries (read only)';$('runs').appendChild(heading);if(!archive.records.length){const empty=document.createElement('p');empty.textContent='No historical summaries found in the configured PC archives.';$('runs').appendChild(empty);}for(const r of archive.records){const row=document.createElement('p');row.textContent=`${r.run_id} · ${r.source} · recorded outcome: ${r.recorded_outcome||'unknown'} · ${Number.isFinite(r.simulated_seconds)?r.simulated_seconds.toFixed(1)+' s':'duration unknown'}`;$('runs').appendChild(row);}}catch(e){const notice=document.createElement('p');notice.textContent='Historical archive unavailable: '+e.message;$('runs').appendChild(notice);}
});
$('open-records').onclick=()=>$('history').click();
$('replay-time').oninput=()=>replayFrame=+$('replay-time').value;
$('return-live').onclick=()=>{replayFrames=null;$('replay-controls').hidden=true;$('view-mode').textContent='PHYSICAL STATE · LIVE';};
function drawMap(canvas){
  if(!world||!canvas)return;
  const mm=getMinimap(canvas);
  if(mm){
    if(canvas===$('map'))$('grid-label').textContent=mm.zoom<0.3?'1 km grid':'200 m grid';
    mm.render(world,{last,track,departure,destination});
  }
}
// Legacy map replaced by TacticalMinimap

let lastMapMs=0;
function drawMaps(force=false){if(!force&&performance.now()-lastMapMs<400)return;lastMapMs=performance.now();drawMap($('map'));if($('map-dialog').open)drawMap($('large-map'));}
function updateEngineering(){
 if(!last)return;
 const t=last.rendering_truth,o=last.observation;
 if(t.phantom){
  $('engineering-content').textContent=JSON.stringify({
   identity:{variant:o.configuration?.airframe_variant,config_sha256:o.configuration?.config_sha256,
    model_xml_sha256:t.provenance?.model_xml_sha256,runtime_source_sha256:last.runtime_source_sha256,
    physics_characteristics_uri:t.provenance?.physics_characteristics_uri,
    physics_model_doc_uri:t.provenance?.physics_model_doc_uri},
   physics_characteristics:t.phantom.physics_data||null,
   instruments:o,mass_cg_inertia:t.mass,body_poses:t.body_poses,joints:t.phantom.joints,
   wing_state:t.phantom.wing_state,aerodynamics:t.aero,propulsion:t.propulsors,energy:t.energy,
   control_law:t.fcc,commands:t.command,contacts:t.contact,events:t.events
  },null,2);
  return;
 }
 $('engineering-content').textContent=JSON.stringify({live:{simulation_time_s:o.t_s,observation_id:o.observation_id,clock_scale:last.time_scale,active:last.active,paused:last.paused,authority:last.authority,command_warnings:o.warning_lamps,rotor_rpm:o.rotor_rpm,shaft_torque_nm:o.shaft_torque_nm,shaft_power_kw:o.engine_shaft_kw,collective_deg:o.collective_feedback_deg,fan_tilt_deg:o.tilt_feedback_deg,cabin_gimbal_deg:o.cabin_feedback_deg,attitude_deg:o.attitude_xyz_deg,angular_rate_world_deg_s:o.gyro_world_deg_s,angular_rate_body_deg_s:o.gyro_body_deg_s,velocity_world_m_s:o.gnss_velocity_mps,velocity_body_m_s:o.velocity_body_mps,clearance_m:o.radar_clearance_m,fuel_kg:o.fuel_kg,scheduler_backlog_s:o.scheduler_backlog_s},engineering:{revision:t.provenance.revision,physics_revision:t.provenance.physics_revision,runtime_source_sha256:last.runtime_source_sha256,status:t.provenance.status,mass:t.mass,power:t.power,energy:t.energy,flags:t.flags,contact_events:t.events,hypotheses:t.provenance.hypotheses}},null,2);
}
function updateView(v){
 if(!rideEnabled && v.observation){
  const instruments=cockpitTelemetry(v.observation);
  $('cockpit-alt').textContent=instruments.altitude;
  $('cockpit-vs').textContent=instruments.verticalSpeed;
  $('cockpit-speed').textContent=instruments.speed;
  $('cockpit-fuel').textContent=instruments.fuel;
 }
 const nextAsset=visualAsset(v.rendering_truth?.provenance?.render_asset);
 if(model && nextAsset && loadedAsset!==nextAsset){model.visible=false;modelReady=false;renderer.clear();}
 last=v;latestTruthReceivedMs=performance.now();panelWasStale=false;aircraftFx?.updateAvionics?.(v.observation);
 const envLocked=v.active||document.documentElement.dataset.vtxPreviewPending==='1';
 for(const id of ['environment-select','env-airport','env-sandbox']){const el=$(id);if(el)el.disabled=envLocked;}
 if(v.environment?.key&&v.environment.key!==currentEnvironment){
  syncEnvironmentControls(v.environment.key);
  if(world&&world.id!==v.environment.id&&!updateView._fetchingWorld){
   updateView._fetchingWorld=true;
   api('/api/world').then(w=>buildWorld(w)).catch(()=>{}).finally(()=>{updateView._fetchingWorld=false;});
  }
 }
 const truth=v.rendering_truth||{};
 if(truth.crashed||v.error||v.recovery_notice){$('consequence').hidden=false;$('consequence').textContent=v.error?'Runtime stopped: '+v.error:truth.crashed?'IMPACT RECORDED · '+(truth.events?.[0]?.body||'aircraft')+'. Physical consequences remain active; no automatic rescue.':v.recovery_notice;}else{$('consequence').hidden=true;}
 if(v.active&&v.mission?.destination&&document.activeElement!==$('dest')){const target=v.mission.destination;if(destination[0]!==target[0]||destination[1]!==target[1]){destination=[...target];$('dest').value=destination.join(', ');updateMarkers();drawMaps(true);}}
 const objective=v.objective; $('objective-current').textContent=objective?`Current objective (${objective.status}): ${objective.text}`:'No objective set.';
 const owner=v.pilot_owner;const fallback=v.fallback?.state;
 $('objective-pilot').textContent=`Pilot ownership: ${owner||'none assigned'}${fallback?` · fallback ${fallback}`:''}${v.pending_pilot?` · awaiting ${v.pending_pilot}`:''}.`;
 $('objective-submit').disabled=!v.active;

 const landing=v.landing_assessment; $('landing-evidence').textContent=landing?`Supported landing recorded at ${landing.t_s.toFixed(1)} s; ${landing.destination_distance_m.toFixed(2)} m from destination. Precision: ${landing.precision==='not_specified'?'not specified':landing.precision}.`:'No landing recorded yet.';
 if(v.rendering_truth?.phantom){
  phantomPanel??=createPhantomPanel({api,toast});phantomPanel.show(true);phantomPanel.update(v);
  document.querySelector('.controls-panel').classList.add('phantom-active');
  const o=v.observation,t=v.rendering_truth,velocity=o.velocity_world_m_s||[0,0,0];
  $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE EXPERIMENT · PHANTOM'):'PHANTOM INSPECTION';
  $('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';
  $('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
  $('start').disabled=v.active||document.documentElement.dataset.vtxPreviewPending==='1';$('end').disabled=!v.active;$('pause').disabled=!v.active;
  $('pause').textContent=v.paused?'Resume existing mission':'Pause physics';
  $('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';showRevision(v);
  if(document.documentElement.dataset.vtxPreviewPending!=='1'||v.active)$('airframe').value=o.configuration.airframe_variant;
  setMissionOptions($('airframe').value);
  for(const id of ['dep','dest','drive','gear','airframe','phantom-start','initial-fuel','power-limit','pilot','atmosphere-model','wind-east','wind-north','wind-up'])$(id).disabled=v.active||(document.documentElement.dataset.vtxPreviewPending==='1'&&(id==='airframe'||id==='phantom-start'));
  $('alt').innerHTML=o.radar_altimeter_m==null?'—':Math.max(0,o.radar_altimeter_m-(o.radar_altimeter_ground_reference_m||0)).toFixed(2)+'<small>m</small>';
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
 lastHudUpdateMs=latestTruthReceivedMs;const o=v.observation,t=v.rendering_truth;if(document.documentElement.dataset.vtxPreviewPending!=='1'||v.active)$('airframe').value=o.configuration.airframe_variant;setMissionOptions($('airframe').value);if(v.run_id!==lastRun){lastRun=v.run_id;track=[];if(v.mission){departure=[...v.mission.departure];$('dep').value=departure.join(', ');}}if(v.mission&&(destination[0]!==v.mission.destination[0]||destination[1]!==v.mission.destination[1])){destination=[...v.mission.destination];$('dest').value=destination.join(', ');updateMarkers();}
 $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE FLIGHT'):'INSPECTION';$('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';$('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
 const latestPilot=v.recent_decisions.at(-1),pilotWaiting=v.active&&v.authority==='colin'&&(!latestPilot||o.warning_lamps.includes('COMMAND_LEASE_EXPIRED')||o.t_s-latestPilot.issued_t_s>1);$('colin-wait').hidden=!pilotWaiting;$('colin-wait').textContent=pilotWaiting?'Waiting for live Colin commands. The retry button does not start an automatic pilot.':'';
 $('authority').textContent=v.authority.toUpperCase();$('start').disabled=v.active||document.documentElement.dataset.vtxPreviewPending==='1';$('end').disabled=!v.active;$('pause').disabled=!v.active;$('pause').textContent=v.paused?'Resume existing mission':'Pause physics';showRevision(v);$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';
 $('retry-bar').hidden=!(v.retry_available&&(!v.active||t.crashed));
 $('retry-status').textContent=t.crashed?'Crash recorded · retry starts a new aircraft at A.':'Retained mission · retry preserves the pilot checkpoint.';
 $('power-label').textContent='SHAFT POWER';$('alt').innerHTML=o.radar_clearance_m==null?'—':o.radar_clearance_m.toFixed(2)+'<small>m</small>';$('vs').innerHTML=o.gnss_velocity_mps[2].toFixed(2)+'<small>m/s</small>';$('speed').innerHTML=Math.hypot(...o.gnss_velocity_mps.slice(0,2)).toFixed(2)+'<small>m/s</small>';$('power').innerHTML=o.engine_shaft_kw.toFixed(1)+'<small>kW</small>';$('fuel').innerHTML=o.fuel_kg.reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
 for(let i=0;i<4;i++)$('rpm-'+i).textContent=o.rotor_rpm[i].toFixed(0)+' rpm';
 if(o.assisted_collective_deg)$('assist-feedback').textContent=(o.assistance_applied?'Experimental collective targets: ':'Shadow requests: ')+o.assisted_collective_deg.map(x=>x.toFixed(2)+'°').join(' / ')+(o.assistance_applied?' · applied':' · not applied');
 for(const el of document.querySelectorAll('.controls-panel input[type=range]:not(#assist),#feather'))el.disabled=v.authority!=='manual'||!manualOwned;
 const cabinLocked=v.authority!=='manual'||!manualOwned;for(const el of document.querySelectorAll('.tilt-spin'))el.disabled=cabinLocked;if(cabinLocked)tiltSpin.fill(0);$('cabin-level').disabled=cabinLocked;$('cabin-face-travel').disabled=cabinLocked;$('cabin-x').disabled=cabinLocked||command.cabin_level;$('cabin-y').disabled=cabinLocked||command.cabin_level;if(o.cabin_feedback_deg)$('cabin-feedback').textContent='Actual gimbal X / Y / yaw: '+o.cabin_feedback_deg.map(x=>x.toFixed(1)+'°').join(' / ')+(o.cabin_level_enabled?(o.cabin_level_powered?' · powered level control':' · passive damping only'):' · manual cabin control')+(o.cabin_level_limited?' · travel limit reached':'');
 for(const id of ['dep','drive','gear','airframe','initial-fuel','power-limit','pilot','atmosphere-model','wind-east','wind-north','wind-up','ignore-scenery','landing-precision'])$(id).disabled=v.active||(document.documentElement.dataset.vtxPreviewPending==='1'&&(id==='airframe'||id==='phantom-start'));
 if(v.active){$('landing-precision').value=v.mission?.landing_precision_m??'';$('ignore-scenery').checked=!!v.mission?.ignore_scenery_collisions;$('power-limit').value=t.provenance.engine_power_limit_kw??469.8;$('initial-fuel').value=t.provenance.initial_fuel_kg??o.configuration.initial_fuel_kg;$('pilot').value=v.authority;$('scale').value=String(v.time_scale);$('drive').value=String(t.provenance.reference_rpm);$('gear').value=t.provenance.gear_variant;$('airframe').value=o.configuration.airframe_variant;$('atmosphere-model').value=o.configuration.atmosphere_model??'constant';(o.configuration.wind_world_mps??[0,0,0]).forEach((value,i)=>$( ['wind-east','wind-north','wind-up'][i]).value=value);}
 if(v.authority==='colin'||!manualOwned){const issued=v.recent_decisions.at(-1)?.issued;$('engine').value=issued?.engine??0;$('engine-value').value=Math.round((issued?.engine??0)*100)+'%';$('common').value=o.collective_feedback_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=o.collective_feedback_deg[i];$('pval-'+i).value=o.collective_feedback_deg[i].toFixed(1)+'°';for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=o.tilt_feedback_deg[i][j];$(k+'val-'+i).value=o.tilt_feedback_deg[i][j].toFixed(1)+'°';}}}
 $('angles').textContent=o.attitude_xyz_deg.map((x,i)=>`${'XYZ'[i]} ${x.toFixed(1)}°`).join(' · ');const h=cockpitHorizon(o.cabin_attitude_xyz_deg??o.attitude_xyz_deg);$('horizon').style.transform=`translateY(${h.pitchDegrees*1.2}px) rotate(${-h.bankDegrees}deg)`;
 const key=v.recent_decisions.map(a=>a.sequence).join(',');if(key!==lastDecision){lastDecision=key;$('decisions').replaceChildren();for(const d of [...v.recent_decisions].reverse()){const a=document.createElement('article'),tm=document.createElement('time'),p=document.createElement('p'),code=document.createElement('code');tm.textContent=`${d.issued_t_s.toFixed(3)} s / ${d.issued.authority.toUpperCase()}`;p.textContent=d.decision;code.textContent=`Collective ${d.issued.collective_deg.join(' / ')}° · engine ${d.issued.engine}`;a.append(tm,p,code);$('decisions').appendChild(a);}}
 if(v.active&&(!track.length||Math.hypot(o.gnss_xy_m[0]-track.at(-1)[0],o.gnss_xy_m[1]-track.at(-1)[1])>.2)){track.push(o.gnss_xy_m);if(track.length>3000)track.shift();}drawMaps();if($('engineering-dialog').open)updateEngineering();
}
let manualRequestPending=false;
setInterval(guard(async()=>{if(manualRequestPending||last?.rendering_truth?.phantom||!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames)return;manualBeat++;if(dirty){dirty=false;manualRequestPending=true;try{await api('/api/action',{...command,authority:'manual',expected_run_id:last.run_id,observation_id:last.observation.observation_id,reason:'Manual operator controls'});}catch(e){dirty=true;throw e;}finally{manualRequestPending=false;}}}),50);
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
api('/api/world').then(w=>{if(!last?.active&&Array.isArray(w.default_departure)&&w.default_departure.length===2){departure=[...w.default_departure];$('dep').value=departure.join(', ');}buildWorld(w);connect();}).catch(()=>fetch('/vtx-env/ride-world.json?v=1').then(response=>{if(!response.ok)throw Error('Airport terrain unavailable: HTTP '+response.status);return response.json();}).then(w=>{buildWorld(w);$('view-sync').textContent='SCRIPTED TRAFFIC - PHYSICAL BACKEND OFFLINE';})).catch(e=>{$('loading').textContent='Unable to load airport: '+e.message;console.error('Airport world',e);});
const q=new THREE.Quaternion(),pos=new THREE.Vector3(),cameraTarget=new THREE.Vector3();
let lastFrameMs=0;
if(new URLSearchParams(location.search).has('debug'))window.__vtx={post,timeOfDay,scene,worldGroup,camera,renderer,orbit,freeCam,THREE,sky,environment,setCameraMode,switchEnvironment,get currentEnvironment(){return currentEnvironment;},get model(){return model;},get loadedAsset(){return loadedAsset;},get modelReady(){return modelReady;},get last(){return last;},get world(){return world;},bodyNodes,setReplay(frames,index){replayFrames=frames;replayFrame=index;},setRideTime(t){if(!rideEnabled||!rideRoute)return false;rideTime=Math.min(rideRoute.duration,Math.max(0,Number(t)||0));rideLastFrame=performance.now();ridePaused=true;return true;}};
function animate(){requestAnimationFrame(animate);if(document.hidden)return;const now=performance.now();if(now-lastFrameMs<(lightweightView?67:(quality.frameMs??50)))return;lastFrameMs=now;const truth=replayFrames?.[replayFrame]||last?.rendering_truth;
 const frameDt=rideLastFrame?Math.min(.25,(now-rideLastFrame)/1000):0;
 rideLastFrame=now;
 if(!ridePaused)sceneTime+=frameDt*sceneScale;
 if(passengerRide&&!ridePaused&&rideRoute&&!last?.active)rideTime=Math.min(rideRoute.duration+22,rideTime+frameDt*sceneScale);
 visualTraffic?.update(sceneTime);
 const requestedAsset=truth?(visualAsset(truth.provenance.render_asset)||(truth.provenance.revision.endsWith('r4')?'/assets/airframe-r4.glb':'/assets/airframe-live.glb')):null;
 if(requestedAsset)loadAirframe(requestedAsset);
 if(model)model.visible=!rideEnabled&&modelReady&&loadedAsset===requestedAsset;
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
   updatePhantom(phantomRig,truth,false,offsets);
  }if(truth.pitch_deg)for(const mesh of pitchMeshes){const i=Number(mesh.userData.physical_body?.slice(-1))-1;if(i>=0&&i<4)mesh.quaternion.setFromAxisAngle(new THREE.Vector3(...mesh.userData.pitch_axis).normalize(),THREE.MathUtils.degToRad(truth.pitch_deg[i]));}
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
    const sight=new THREE.Vector3(Math.cos(cockpitYaw)*Math.cos(cockpitPitch),Math.sin(cockpitYaw)*Math.cos(cockpitPitch),Math.sin(cockpitPitch)).applyQuaternion(rot);
    camera.position.copy(new THREE.Vector3(.9,0,1.48).applyQuaternion(rot).add(p));
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
   const speed=Math.hypot(velocity[0],velocity[1]),clearance=Math.max(0,ridePose.position[2]-surfaceZ(...ridePose.position));
   $('cockpit-speed').textContent=speed.toFixed(1);$('cockpit-alt').textContent=clearance.toFixed(1);$('cockpit-vs').textContent=velocity[2].toFixed(1);$('cockpit-fuel').textContent='—';
   if(now-(animate.hudLast||0)>350){animate.hudLast=now;
    $('alt').innerHTML=clearance.toFixed(1)+'<small>m</small>';$('vs').innerHTML=velocity[2].toFixed(1)+'<small>m/s</small>';$('speed').innerHTML=speed.toFixed(1)+'<small>m/s</small>';
    $('power-label').textContent='SHAFT POWER · UNAVAILABLE';$('power').textContent='—';$('fuel').textContent='—';
    $('angles').textContent='HDG '+((90-ridePose.heading*180/Math.PI+360)%360).toFixed(0)+'° · PITCH '+(ridePose.pitch*180/Math.PI).toFixed(1)+'° · BANK '+((ridePose.bank||0)*180/Math.PI).toFixed(1)+'°';
    $('ride-progress').textContent=(ridePose.operation||'scripted')+' · '+Math.floor(sceneTime)+' s';
    $('view-sync').textContent=(VEHICLE_MODELS[airportOperations?.actors.find(a=>a.id===selectedVehicleId)?.modelId]?.label||selectedVehicleId)+' · SCRIPTED · '+speed.toFixed(1)+' m/s';
   }
  }
 }else if(visualTraffic&&now-(animate.progressLast||0)>500){animate.progressLast=now;$('ride-progress').textContent='Traffic active · '+Math.floor(sceneTime)+' s';}
 sky.update(camera,now/1000);environment.buildings?.update(now/1000);environment.volcano?.update(now/1000);environment.serviceRoads?.update(now/1000,last?.observation?.gnss_xy_m);
  aircraftFx?.update(last?.observation?.rotor_rpm,now/1000);
 if(world&&!window.__vtxNoRender){if(post)post.render();else renderer.render(scene,camera);}
 const status=$('view-sync');if(status&&!rideEnabled&&now-(status._last||0)>400){status._last=now;
  const age=now-latestTruthReceivedMs;
  if(last&&age>2000&&!panelWasStale){aircraftFx?.updateAvionics?.(last.observation,true);panelWasStale=true;}
  status.textContent=!last?'WAITING FOR DATA':age>2000?'DISPLAY STALE':!modelReady?'LOADING AIRCRAFT':`LIVE VIEW · ${Math.round(age)} ms · ${Math.round(last?.observation?.rotor_rpm?.[0]||0)} RPM · t ${last?.observation?.t_s?.toFixed(1)??'--'}s`;
  status.style.color=age>2000?'#ffb19d':'#b6f6d8';
 }
}animate();
