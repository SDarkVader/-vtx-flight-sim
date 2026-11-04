import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {mergeGeometries} from './vendor/BufferGeometryUtils.js';
import {tiltFromDirection} from './tilt-direction.js?v=fan-direction-6';
import {zoomDistance} from './camera-zoom.js?v=1';
import {rotorVisualOffset} from './rotor-visual.js?v=1';
import {cockpitAxes,cockpitHorizon} from './cockpit-axes.js?v=1';
import {isCockpitObstruction,setCockpitVisibility} from './cockpit-visibility.js?v=3';
// Vader's Taxis environment (visual only; physics collision comes from world.py).
import {buildSky} from './vtx-env/sky.js?v=1';
import {buildTerrain,makeHills,makeSkyline,makeFarForest,makeWater} from './vtx-env/landscape.js?v=1';
import {buildBuildings} from './vtx-env/buildings.js?v=3';
import {buildAirfield} from './vtx-env/airfield.js?v=6';
import {buildTrees,buildForecourt} from './vtx-env/vegetation.js?v=1';
import {enhanceAircraft} from './vtx-env/aircraft-look.js?v=6';
import {buildVolcanoBasement} from './vtx-env/volcano-basement.js?v=1';
import {TacticalMinimap} from './vtx-env/tactical-minimap.js?v=2';
import {buildServiceRoads} from './vtx-env/service-roads.js?v=1';
import {createFreeCamera} from './free-camera.js?v=4';
import {attachPhantom,updatePhantom} from './vtx-env/phantom-look.js?v=2';import {createPhantomPanel} from './phantom-controls.js?v=1';let phantomRig=null,phantomPanel=null; // Phantom hooks (render + phantom-fbw-1 panel)

const $=id=>document.getElementById(id);
let last=null,world=null,model=null,pick='a',cameraMode='chase',replayFrames=null,replayFrame=0;
let departure=[0,0],destination=[-50,20],track=[],lastDecision='',lastRun=null;
const bodyNodes={},pitchMeshes=[];
const rotorSpinAxis=new THREE.Vector3(0,0,1),rotorSpinQ=new THREE.Quaternion();
let latestTruthReceivedMs=0,lastHudUpdateMs=0,panelWasStale=false;
const command={engine:0,collective_deg:[0,0,0,0],tilt_deg:[[0,0],[0,0],[0,0],[0,0]],cabin_deg:[0,0,0],cabin_level:true};
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
import {resolveQuality} from './vtx-env/quality.js?v=gfx-20261103-1';import {createGround} from './vtx-env/ground.js?v=gfx-20261103-1';import {createLightPool} from './vtx-env/light-pool.js?v=gfx-20261103-1';import {dressWorld} from './vtx-env/world-dressing.js?v=gfx-20261103-1';
const quality=resolveQuality({mobile,search:location.search});scene.userData.quality=quality.name;
// On phones keep retained-flight actions and indicator bar directly below the flight view.
if (innerWidth <= 800) {
 document.querySelector('header').after($('retry-bar'));
 $('viewport').after(document.querySelector('footer'));
}
const camera=new THREE.PerspectiveCamera(48,1,.1,6000);camera.up.set(0,0,1);camera.position.set(9,-11,8);
const renderer=new THREE.WebGLRenderer({antialias:quality.antialias,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,quality.pixelRatio));renderer.shadowMap.enabled=quality.shadows;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=quality.toneMapping;renderer.toneMappingExposure=quality.exposure;viewport.appendChild(renderer.domElement);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.target.set(0,0,1.4);orbit.enableDamping=true;orbit.maxPolarAngle=Math.PI*.49;orbit.minDistance=2;orbit.maxDistance=600;
// Keep pinch gestures on the renderer and avoid two-finger panning fighting the chase target.
orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';
const freeCam=createFreeCamera(camera,renderer,viewport,m=>setCameraMode(m));
const sky=buildSky(scene,renderer,{quality}),environment={};
const lightPool=createLightPool(scene,quality.localLights);scene.onBeforeRender=(r,s,cam)=>lightPool.update(cam);
const resize=()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(viewport);
function plane(w,h,color,x,y,z){const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({color,roughness:.95}));m.position.set(x,y,z);m.receiveShadow=true;scene.add(m);return m;}
function makeLabel(text,color='#7cdfcb'){
 const c=document.createElement('canvas');c.width=128;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.beginPath();ctx.arc(64,64,49,0,Math.PI*2);ctx.fill();ctx.fillStyle='#143934';ctx.font='bold 62px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,64,67);const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:true}));sprite.scale.set(1.8,1.8,1.8);scene.add(sprite);return sprite;
}
const markerA=makeLabel('A'),markerB=makeLabel('B','#ffc88b');
function surfaceZ(x,y){if(!world)return 0;const n=world.heights_m.length,half=world.half_m,u=THREE.MathUtils.clamp((x+half)/(2*half)*(n-1),0,n-1.00001),v=THREE.MathUtils.clamp((y+half)/(2*half)*(n-1),0,n-1.00001),i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,h=world.heights_m;let z=a>b?(1-a)*h[j][i]+(a-b)*h[j][i+1]+b*h[j+1][i+1]:(1-b)*h[j][i]+(b-a)*h[j+1][i]+a*h[j+1][i+1];for(const o of world.obstacles){if(o.kind==='box'&&Math.abs(x-o.center[0])<=o.half[0]&&Math.abs(y-o.center[1])<=o.half[1])z=Math.max(z,o.center[2]+o.half[2]);}return z;}
function updateMarkers(){markerA.position.set(departure[0]-5,departure[1]+4,surfaceZ(...departure)+1.5);markerB.position.set(destination[0]-5,destination[1]+4,surfaceZ(...destination)+1.5);}
function buildWorld(w){
 console.log('VTX: terrain building');
 world=w;
 // Ground uses the same heightfield samples as the physics terrain; the distant landscape lies outside the +/-500 m test area.
 scene.add(buildTerrain(w));
 const hills=makeHills(w);scene.add(hills.mesh,makeSkyline(hills.heightAt),makeFarForest(hills.heightAt,quality.forest));const ground=createGround(w,hills.mesh);
 const groundZ=(x,y)=>Math.max(Math.abs(x),Math.abs(y))<=w.half_m?surfaceZ(x,y):ground.heightAt(x,y);
 // Buildings are dressed onto the physical obstacle boxes; airfield markings are flush paint.
 environment.buildings=buildBuildings(scene,w,{ppm:quality.facadePpm,quality});buildAirfield(scene,{ppm:quality.airfieldPpm,quality});buildTrees(scene,w,{quality});buildForecourt(scene,w);environment.volcano=buildVolcanoBasement(scene,w);environment.serviceRoads=buildServiceRoads(scene,w,groundZ);
 scene.add(makeWater(w,surfaceZ(w.water.x,w.water.y)+.1));
 environment.dressing=dressWorld(scene,w,ground,{quality,lightPool,extraTextures:[markerA.material.map,markerB.material.map]});
 updateMarkers();drawMaps();console.log('VTX: terrain ready');
}
let aircraftFx=null,loadedAsset=null,assetRetryAfter=0,modelReady=false;
function disposeModel(root){
 const geometries=new Set(),materials=new Set(),textures=new Set();
 root.traverse(n=>{if(!n.isMesh)return;if(n.geometry)geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});
 geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}
// Render-only visual pass (tools/phantom/refine_phantom_visual.py): smooth shell, livery, rivets, exposed wing bay.
// Same nodes/joints/extras as the CAD export; ?cad=1 shows the raw CAD GLB instead.
const VISUAL_ASSET={'/assets/phantom-a10.glb':'/assets/phantom-a10-visual.glb'};
function visualAsset(a){return a&&!new URLSearchParams(location.search).has('cad')?(VISUAL_ASSET[a]||a):a;}
function loadAirframe(asset){
 if(asset===loadedAsset||performance.now()<assetRetryAfter)return;loadedAsset=asset;
 $('loading').hidden=false;$('loading').textContent='Loading physical revision…';
 new GLTFLoader().load(asset+(asset.includes('?')?'&':'?')+'v=r6-20261101-2',async g=>{
 if(asset!==loadedAsset){disposeModel(g.scene);return;}
 if(model){scene.remove(model);disposeModel(model);}
 for(const key of Object.keys(bodyNodes))delete bodyNodes[key];pitchMeshes.length=0;
 model=g.scene;modelReady=false;scene.add(model);if(!quality.glow)model.traverse(n=>{if(n.isLight)n.visible=false;});model.traverse(n=>{if(n.userData.physical_body&&n.type==='Object3D')bodyNodes[n.userData.physical_body]=n;if(n.isMesh){n.castShadow=true;n.receiveShadow=true;if(n.userData.pitch_axis)pitchMeshes.push(n);if(n.material){n.material.side=THREE.DoubleSide;}}});
 // Blender exports empty groups as Object3D or Group depending on loader.
 for(const name of ['airframe','cabin',...Array.from({length:4},(_,i)=>`nacelle${i+1}`),...Array.from({length:4},(_,i)=>`rotor${i+1}`),...Array.from({length:6},(_,i)=>`gear${i+1}`),...Array.from({length:4},(_,i)=>`shaft${i+1}`)]){const n=model.getObjectByName(name);if(n)bodyNodes[name]=n;}
  aircraftFx=enhanceAircraft(model,scene.environment);phantomRig=asset.includes('phantom')?attachPhantom(model):null;
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
  if(last?.active){toast('End the current sortie before selecting the next mission.');return;}
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
async function choosePoint(p){const verdict=await api(`/api/validate?x=${p[0]}&y=${p[1]}`);$('validation').textContent=`${pick.toUpperCase()} (${p.join(', ')}): ${verdict.reason}`;$('large-validation').textContent=$('validation').textContent;if(!verdict.valid){toast(verdict.reason);return;}if(pick==='a'){departure=p;$('dep').value=p.join(', ');}else{destination=p;$('dest').value=p.join(', ');}updateMarkers();drawMaps();}
$('map').onclick=guard(e=>onMap(e,$('map')));$('large-map').onclick=guard(e=>onMap(e,$('large-map')));
function setPick(p){pick=p;$('pick-a').classList.toggle('selected',p==='a');$('pick-b').classList.toggle('selected',p==='b');$('large-pick').textContent=p.toUpperCase();}
$('pick-a').onclick=()=>setPick('a');$('pick-b').onclick=()=>setPick('b');
for(const [id,p] of [['dep','a'],['dest','b']])$(id).onchange=guard(async()=>{const vals=$(id).value.split(',').map(Number);if(vals.length!==2||vals.some(v=>!Number.isFinite(v)))throw Error('Use two finite coordinates: east, north');setPick(p);await choosePoint(vals);});
$('map-zoom').onclick=()=>{$('map-dialog').showModal();drawMaps(true);};
const mapModeBtn=$('map-mode');
if(mapModeBtn){
  mapModeBtn.onclick=()=>{
    const mm=getMinimap($('map'));
    if(mm){
      mm.tacticalMode=!mm.tacticalMode;
      mm.zoom=mm.tacticalMode?2.4:0.88;
      mm.center=mm.tacticalMode?[0,40]:[20,110];
      mapModeBtn.textContent=mm.tacticalMode?'Valley':'Tactical';
      drawMaps(true);
    }
  };
}
$('start').onclick=guard(async()=>{replayFrames=null;const r=await api('/api/mission',{departure,destination,authority:$('pilot').value,time_scale:+$('scale').value,stability_assist:+$('assist').value/100,reference_rpm:+$('drive').value,gear_variant:$('gear').value,airframe_variant:$('airframe').value,fuel_kg:selectedFuel(),engine_power_limit_kw:+$('power-limit').value,atmosphere_model:$('atmosphere-model').value,wind_world_mps:selectedWind(),label:'Map-selected live ground-to-ground attempt'});manualOwned=$('pilot').value==='manual';if(manualOwned)manualChannel.postMessage('takeover');track=[];toast('Sortie '+r.run_id+' started on the landing gear.');});
$('end').onclick=guard(async()=>{const r=await api('/api/stop',{reason:'Operator ended the live attempt'});toast(`Recorded: ${r.outcome}. Every failed attempt is retained.`);});
for(const authority of ['manual','colin'])$('retry-'+authority).onclick=guard(async()=>{
 replayFrames=null;
 const r=await api('/api/retry',{authority,time_scale:authority==='colin'?.02:.1,stability_assist:+$('assist').value/100});
 manualOwned=authority==='manual';if(manualOwned)manualChannel.postMessage('takeover');
 command.engine=0;command.collective_deg.fill(0);command.tilt_deg=[[0,0],[0,0],[0,0],[0,0]];dirty=false;
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
function setCameraMode(mode){
 const previous=cameraMode;
 if(previous==='chase'&&mode==='cockpit')savedChaseOffset=camera.position.clone().sub(orbit.target);
 cameraMode=mode;
 setCockpitVisibility(model,mode==='cockpit');
 aircraftFx?.setCockpitMode?.(mode==='cockpit');
 orbit.enabled=(mode==='chase');
 if(mode==='free'){orbit.enabled=false;freeCam.activate(orbit.target);}
 else{freeCam.deactivate();}
 if(mode==='chase'&&previous==='cockpit'){
  const position=last?.rendering_truth?.body_poses?.airframe?.position;
  if(position)orbit.target.set(position[0],position[1],position[2]+1.5);
  camera.up.set(0,0,1);camera.position.copy(orbit.target).add(savedChaseOffset||new THREE.Vector3(9,-11,8));orbit.update();
 }
 renderer.domElement.style.touchAction='none';
 $('cockpit-look').hidden=mode!=='cockpit';
 $('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';
 $('camera').textContent=mode==='free'?'Chase camera':'Free roam camera';
}
$('camera').onclick=()=>setCameraMode(cameraMode==='free'?'chase':'free');
$('cockpit').onclick=()=>setCameraMode(cameraMode==='cockpit'?'chase':'cockpit');
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
 const truth=replayFrames?.[replayFrame]||last?.rendering_truth,air=truth?.body_poses?.airframe?.position;
 if(air)orbit.target.set(air[0],air[1],air[2]+1.5);
 const distance=THREE.MathUtils.clamp(camera.position.distanceTo(orbit.target),18,orbit.maxDistance);
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
$('history').onclick=guard(async()=>{const records=await api('/api/runs');$('runs').replaceChildren();for(const r of records){const a=document.createElement('article'),button=document.createElement('button');button.textContent='Inspect recorded states';button.onclick=guard(async()=>{const replay=await api('/api/replay/'+r.run_id);replayFrames=replay.frames;replayFrame=0;$('replay-time').max=Math.max(0,replayFrames.length-1);$('replay-controls').hidden=false;$('view-mode').textContent='POST-FLIGHT AUDIT · NO CONTROL';toast(replay.downsampled?`Inspection uses ${replay.frames.length} of ${replay.total_frames} recorded states; full log is retained.`:'Inspection only. The live physical plant remains separate.');});a.append(button,document.createTextNode(`${r.run_id} · ${r.outcome} · ${r.simulated_seconds.toFixed(1)} s · ${r.decisions} decisions`));$('runs').appendChild(a);}$('history-dialog').showModal();});
$('replay-time').oninput=()=>replayFrame=+$('replay-time').value;
$('return-live').onclick=()=>{replayFrames=null;$('replay-controls').hidden=true;$('view-mode').textContent='PHYSICAL STATE · LIVE';};
function drawMap(canvas){
  if(!world||!canvas)return;
  const mm=getMinimap(canvas);
  if(mm){
    mm.render(world,{last,track,departure,destination});
  }
}
// Legacy map replaced by TacticalMinimap

let lastMapMs=0;
function drawMaps(force=false){if(!force&&performance.now()-lastMapMs<400)return;lastMapMs=performance.now();drawMap($('map'));if($('map-dialog').open)drawMap($('large-map'));}
function updateEngineering(){if(!last)return;const t=last.rendering_truth,o=last.observation;$('engineering-content').textContent=JSON.stringify({live:{simulation_time_s:o.t_s,observation_id:o.observation_id,clock_scale:last.time_scale,active:last.active,paused:last.paused,authority:last.authority,command_warnings:o.warning_lamps,rotor_rpm:o.rotor_rpm,shaft_torque_nm:o.shaft_torque_nm,shaft_power_kw:o.engine_shaft_kw,collective_deg:o.collective_feedback_deg,fan_tilt_deg:o.tilt_feedback_deg,cabin_gimbal_deg:o.cabin_feedback_deg,attitude_deg:o.attitude_xyz_deg,angular_rate_world_deg_s:o.gyro_world_deg_s,angular_rate_body_deg_s:o.gyro_body_deg_s,velocity_world_m_s:o.gnss_velocity_mps,velocity_body_m_s:o.velocity_body_mps,clearance_m:o.radar_clearance_m,fuel_kg:o.fuel_kg,scheduler_backlog_s:o.scheduler_backlog_s},engineering:{revision:t.provenance.revision,status:t.provenance.status,mass:t.mass,power:t.power,energy:t.energy,flags:t.flags,contact_events:t.events,hypotheses:t.provenance.hypotheses}},null,2);}
function updateView(v){last=v;latestTruthReceivedMs=performance.now();panelWasStale=false;aircraftFx?.updateAvionics?.(v.observation);
 if(v.rendering_truth?.phantom){phantomPanel??=createPhantomPanel({api,toast});phantomPanel.show(true);phantomPanel.update(v);$('start').disabled=v.active;$('end').disabled=!v.active;$('pause').disabled=!v.active;$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';$('state').textContent=v.active?'LIVE EXPERIMENT · PHANTOM':'INSPECTION';return;}phantomPanel?.show(false);
 // Always ingest the latest physical pose; avoid repainting the entire HUD at
 // the websocket rate on low-powered phones. 3D rendering is independent.
 if(lightweightView&&latestTruthReceivedMs-lastHudUpdateMs<500&&v.run_id===lastRun)return;
 lastHudUpdateMs=latestTruthReceivedMs;const o=v.observation,t=v.rendering_truth;if(v.run_id!==lastRun){lastRun=v.run_id;track=[];if(v.mission){departure=[...v.mission.departure];destination=[...v.mission.destination];$('dep').value=departure.join(', ');$('dest').value=destination.join(', ');updateMarkers();}}
 $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE EXPERIMENT'):'INSPECTION';$('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';$('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
 const latestPilot=v.recent_decisions.at(-1),pilotWaiting=v.active&&v.authority==='colin'&&(!latestPilot||o.warning_lamps.includes('COMMAND_LEASE_EXPIRED')||o.t_s-latestPilot.issued_t_s>1);$('colin-wait').hidden=!pilotWaiting;$('colin-wait').textContent=pilotWaiting?'Waiting for live Colin commands. The retry button does not start an automatic pilot.':'';
 $('authority').textContent=v.authority.toUpperCase();$('start').disabled=v.active;$('end').disabled=!v.active;$('pause').disabled=!v.active;$('pause').textContent=v.paused?'Resume existing mission':'Pause physics';$('revision').textContent=t.provenance.revision.toUpperCase();$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';
 $('retry-bar').hidden=!(v.retry_available&&(!v.active||t.crashed));
 $('retry-status').textContent=t.crashed?'Crash recorded · retry starts a new aircraft at A.':'Retained mission · retry preserves the pilot checkpoint.';
 $('alt').innerHTML=o.radar_clearance_m==null?'—':o.radar_clearance_m.toFixed(2)+'<small>m</small>';$('vs').innerHTML=o.gnss_velocity_mps[2].toFixed(2)+'<small>m/s</small>';$('speed').innerHTML=Math.hypot(...o.gnss_velocity_mps.slice(0,2)).toFixed(2)+'<small>m/s</small>';$('power').innerHTML=o.engine_shaft_kw.toFixed(1)+'<small>kW</small>';$('fuel').innerHTML=o.fuel_kg.reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
 for(let i=0;i<4;i++)$('rpm-'+i).textContent=o.rotor_rpm[i].toFixed(0)+' rpm';
 if(o.assisted_collective_deg)$('assist-feedback').textContent=(o.assistance_applied?'Experimental collective targets: ':'Shadow requests: ')+o.assisted_collective_deg.map(x=>x.toFixed(2)+'°').join(' / ')+(o.assistance_applied?' · applied':' · not applied');
 for(const el of document.querySelectorAll('.controls-panel input[type=range]:not(#assist),#feather'))el.disabled=v.authority!=='manual'||!manualOwned;
 const cabinLocked=v.authority!=='manual'||!manualOwned;for(const el of document.querySelectorAll('.tilt-spin'))el.disabled=cabinLocked;if(cabinLocked)tiltSpin.fill(0);$('cabin-level').disabled=cabinLocked;$('cabin-face-travel').disabled=cabinLocked;$('cabin-x').disabled=cabinLocked||command.cabin_level;$('cabin-y').disabled=cabinLocked||command.cabin_level;if(o.cabin_feedback_deg)$('cabin-feedback').textContent='Actual gimbal X / Y / yaw: '+o.cabin_feedback_deg.map(x=>x.toFixed(1)+'°').join(' / ')+(o.cabin_level_enabled?(o.cabin_level_powered?' · powered level control':' · passive damping only'):' · manual cabin control')+(o.cabin_level_limited?' · travel limit reached':'');
 for(const id of ['dep','dest','drive','gear','airframe','initial-fuel','power-limit','pilot','atmosphere-model','wind-east','wind-north','wind-up'])$(id).disabled=v.active;
 if(v.active){$('power-limit').value=t.provenance.engine_power_limit_kw??469.8;$('initial-fuel').value=t.provenance.initial_fuel_kg??o.configuration.initial_fuel_kg;$('pilot').value=v.authority;$('scale').value=String(v.time_scale);$('drive').value=String(t.provenance.reference_rpm);$('gear').value=t.provenance.gear_variant;$('airframe').value=o.configuration.airframe_variant;$('atmosphere-model').value=o.configuration.atmosphere_model??'constant';(o.configuration.wind_world_mps??[0,0,0]).forEach((value,i)=>$( ['wind-east','wind-north','wind-up'][i]).value=value);}
 if(v.authority==='colin'||!manualOwned){const issued=v.recent_decisions.at(-1)?.issued;$('engine').value=issued?.engine??0;$('engine-value').value=Math.round((issued?.engine??0)*100)+'%';$('common').value=o.collective_feedback_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=o.collective_feedback_deg[i];$('pval-'+i).value=o.collective_feedback_deg[i].toFixed(1)+'°';for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=o.tilt_feedback_deg[i][j];$(k+'val-'+i).value=o.tilt_feedback_deg[i][j].toFixed(1)+'°';}}}
 $('angles').textContent=o.attitude_xyz_deg.map((x,i)=>`${'XYZ'[i]} ${x.toFixed(1)}°`).join(' · ');const h=cockpitHorizon(o.cabin_attitude_xyz_deg??o.attitude_xyz_deg);$('horizon').style.transform=`translateY(${h.pitchDegrees*1.2}px) rotate(${-h.bankDegrees}deg)`;
 if(t.crashed||v.error){$('consequence').hidden=false;$('consequence').textContent=v.error?'Solver stopped: '+v.error:'IMPACT RECORDED · '+(t.events[0]?.body||'aircraft')+'. Physical consequences remain active; no automatic rescue.';}else{$('consequence').hidden=true;}
 const key=v.recent_decisions.map(a=>a.sequence).join(',');if(key!==lastDecision){lastDecision=key;$('decisions').replaceChildren();for(const d of [...v.recent_decisions].reverse()){const a=document.createElement('article'),tm=document.createElement('time'),p=document.createElement('p'),code=document.createElement('code');tm.textContent=`${d.issued_t_s.toFixed(3)} s / ${d.issued.authority.toUpperCase()}`;p.textContent=d.decision;code.textContent=`Collective ${d.issued.collective_deg.join(' / ')}° · engine ${d.issued.engine}`;a.append(tm,p,code);$('decisions').appendChild(a);}}
 if(v.active&&(!track.length||Math.hypot(o.gnss_xy_m[0]-track.at(-1)[0],o.gnss_xy_m[1]-track.at(-1)[1])>.2)){track.push(o.gnss_xy_m);if(track.length>3000)track.shift();}drawMaps();if($('engineering-dialog').open)updateEngineering();
}
let manualRequestPending=false;
setInterval(guard(async()=>{if(manualRequestPending||last?.rendering_truth?.phantom||!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames)return;manualBeat++;if(dirty||manualBeat%10===0){dirty=false;manualRequestPending=true;try{await api('/api/action',{...command,authority:'manual',observation_id:last.observation.observation_id,reason:'Manual operator controls and command heartbeat'});}catch(e){dirty=true;throw e;}finally{manualRequestPending=false;}}}),50);
function connect(){const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);ws.onmessage=e=>updateView(JSON.parse(e.data));ws.onclose=()=>{toast('Live connection lost; physical command lease still applies.');setTimeout(connect,2000);};}
api('/api/world').then(buildWorld).catch(e=>toast(e.message));connect();
const q=new THREE.Quaternion(),pos=new THREE.Vector3(),cameraTarget=new THREE.Vector3();
let lastFrameMs=0;
if(new URLSearchParams(location.search).has('debug'))window.__vtx={scene,camera,renderer,orbit,freeCam,THREE,sky,environment,setCameraMode,get model(){return model;},get world(){return world;},bodyNodes,setReplay(frames,index){replayFrames=frames;replayFrame=index;}};
function animate(){requestAnimationFrame(animate);if(document.hidden)return;const now=performance.now();if(now-lastFrameMs<(lightweightView?67:50))return;lastFrameMs=now;const truth=replayFrames?.[replayFrame]||last?.rendering_truth;
 if(truth)loadAirframe(visualAsset(truth.provenance.render_asset)||(truth.provenance.revision.endsWith('r4')?'/assets/airframe-r4.glb':'/assets/airframe-live.glb'));
 if(truth&&model){for(const [name,pose] of Object.entries(truth.body_poses)){const n=bodyNodes[name];if(!n)continue;n.position.set(...pose.position);const a=pose.quaternion_wxyz;n.quaternion.set(a[1],a[2],a[3],a[0]);
   // The authoritative rotor pose is sampled at 20 Hz. At 1200 RPM one full
   // revolution occurs between samples, so drawing snapshots alone looks static.
   // Use measured signed angular velocity solely for sub-frame presentation.
   if(!replayFrames&&name.startsWith('rotor')&&/^rotor[1-4]$/.test(name)){
    const i=Number(name.slice(-1))-1;
    const angle=rotorVisualOffset(truth.rotor_spin_rad_s?.[i],now-latestTruthReceivedMs,last?.time_scale,last?.active,last?.paused);
    if(angle)n.quaternion.multiply(rotorSpinQ.setFromAxisAngle(rotorSpinAxis,angle));
   }
  }if(phantomRig)updatePhantom(phantomRig,truth);for(const mesh of pitchMeshes){const i=Number(mesh.userData.physical_body?.slice(-1))-1;if(i>=0&&i<4)mesh.quaternion.setFromAxisAngle(new THREE.Vector3(...mesh.userData.pitch_axis).normalize(),THREE.MathUtils.degToRad(truth.pitch_deg[i]));}
  const base=truth.body_poses.airframe,posArray=base.position;pos.set(posArray[0],posArray[1],posArray[2]+1.5);
  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);camera.up.set(0,0,1);orbit.update();}
  else if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position).add(new THREE.Vector3(-.30,.02,.25).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));const cp=Math.cos(cockpitPitch);cameraTarget.copy(camera.position).add(new THREE.Vector3(Math.sin(cockpitYaw)*cp,-Math.cos(cockpitYaw)*cp,Math.sin(cockpitPitch)).applyQuaternion(q));camera.lookAt(cameraTarget);}
  else if(cameraMode==='free'){freeCam.update(0.08);}
  else{camera.up.set(0,0,1);orbit.update();}
  sky.follow(pos);
 }
 sky.update(camera,now/1000);environment.buildings?.update(now/1000);environment.volcano?.update(now/1000);environment.serviceRoads?.update(now/1000,last?.observation?.gnss_xy_m);
  aircraftFx?.update(last?.observation?.rotor_rpm,now/1000);
 if(model&&modelReady&&!window.__vtxNoRender)renderer.render(scene,camera);
 const status=$('view-sync');if(status&&now-(status._last||0)>400){status._last=now;
  const age=now-latestTruthReceivedMs;
  if(last&&age>2000&&!panelWasStale){aircraftFx?.updateAvionics?.(last.observation,true);panelWasStale=true;}
  status.textContent=!last?'WAITING FOR DATA':age>2000?'DISPLAY STALE':!modelReady?'LOADING AIRCRAFT':`LIVE VIEW · ${Math.round(age)} ms · ${Math.round(last?.observation?.rotor_rpm?.[0]||0)} RPM · t ${last?.observation?.t_s?.toFixed(1)??'--'}s`;
  status.style.color=age>2000?'#ffb19d':'#b6f6d8';
 }
}animate();
