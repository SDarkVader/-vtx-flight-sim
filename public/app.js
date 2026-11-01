import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {mergeGeometries} from './vendor/BufferGeometryUtils.js';
import {tiltFromDirection} from './tilt-direction.js?v=fan-direction-5';
import {zoomDistance} from './camera-zoom.js?v=1';
import {rotorVisualOffset} from './rotor-visual.js?v=1';

const $=id=>document.getElementById(id);
let last=null,world=null,model=null,pick='a',cameraMode='chase',replayFrames=null,replayFrame=0;
let departure=[0,0],destination=[-50,20],track=[],lastDecision='',lastRun=null;
const bodyNodes={},pitchMeshes=[];
const rotorSpinAxis=new THREE.Vector3(0,0,1),rotorSpinQ=new THREE.Quaternion();
let latestTruthReceivedMs=0,lastHudUpdateMs=0;
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

console.log('VTX: module ready');
const viewport=$('viewport'),scene=new THREE.Scene();scene.background=new THREE.Color('#a9c1ca');scene.fog=new THREE.Fog('#b3c7c9',240,1000);
const camera=new THREE.PerspectiveCamera(48,1,.05,2000);camera.up.set(0,0,1);camera.position.set(9,-11,8);
const mobileView=matchMedia('(pointer: coarse)').matches;
// Optional display-only lightweight mode. No simulation or collision changes.
const lightweightView=mobileView||new URLSearchParams(location.search).has('lite');
const renderer=new THREE.WebGLRenderer({antialias:!mobileView,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,mobileView ? 0.7 : 1.2));renderer.shadowMap.enabled=false;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;viewport.appendChild(renderer.domElement);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.target.set(0,0,1.4);orbit.enableDamping=true;orbit.maxPolarAngle=Math.PI*.49;orbit.minDistance=2;orbit.maxDistance=600;
// Keep pinch gestures on the renderer and avoid two-finger panning fighting the chase target.
orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';
const hemi=new THREE.HemisphereLight('#e4f5ff','#65745a',2.3);hemi.position.set(0,0,100);scene.add(hemi);
const sun=new THREE.DirectionalLight('#fff1d6',3.2);sun.position.set(-70,-90,140);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-70;sun.shadow.camera.right=70;sun.shadow.camera.top=70;sun.shadow.camera.bottom=-70;sun.shadow.camera.near=1;sun.shadow.camera.far=350;sun.shadow.bias=-.0004;scene.add(sun);scene.add(sun.target);
const resize=()=>{const w=viewport.clientWidth,h=viewport.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(viewport);
function plane(w,h,color,x,y,z){const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({color,roughness:.95}));m.position.set(x,y,z);m.receiveShadow=true;scene.add(m);return m;}
function makeLabel(text,color='#7cdfcb'){
 const c=document.createElement('canvas');c.width=128;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.beginPath();ctx.arc(64,64,49,0,Math.PI*2);ctx.fill();ctx.fillStyle='#143934';ctx.font='bold 62px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,64,67);const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),depthTest:true}));sprite.scale.set(1.8,1.8,1.8);scene.add(sprite);return sprite;
}
const markerA=makeLabel('A'),markerB=makeLabel('B','#ffc88b');
function surfaceZ(x,y){if(!world)return 0;const n=world.heights_m.length,half=world.half_m,u=THREE.MathUtils.clamp((x+half)/(2*half)*(n-1),0,n-1.00001),v=THREE.MathUtils.clamp((y+half)/(2*half)*(n-1),0,n-1.00001),i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,h=world.heights_m;let z=a>b?(1-a)*h[j][i]+(a-b)*h[j][i+1]+b*h[j+1][i+1]:(1-b)*h[j][i]+(b-a)*h[j+1][i]+a*h[j+1][i+1];for(const o of world.obstacles){if(o.kind==='box'&&Math.abs(x-o.center[0])<=o.half[0]&&Math.abs(y-o.center[1])<=o.half[1])z=Math.max(z,o.center[2]+o.half[2]);}return z;}
function updateMarkers(){markerA.position.set(departure[0]-5,departure[1]+4,surfaceZ(...departure)+1.5);markerB.position.set(destination[0]-5,destination[1]+4,surfaceZ(...destination)+1.5);}
// Artwork is mounted on the existing physical hangar face. It is visual only;
// no new obstacles or landing surfaces are implied by these decorations.
function addCompanyGallery(w){
 const hangar=w.obstacles.find(o=>o.id==='hangar'&&o.kind==='box');if(!hangar)return;
 const [cx,cy,cz]=hangar.center,[hx,hy,hz]=hangar.half,face=cy-hy-.035;
 function panel(width,height,x,z,material,depth=0){const mesh=new THREE.Mesh(new THREE.PlaneGeometry(width,height),material);mesh.rotation.x=Math.PI/2;mesh.position.set(x,face-depth,z);scene.add(mesh);return mesh;}
 function sign(message,width,height,x,z,bg,fg){
  const c=document.createElement('canvas');c.width=1024;c.height=128;const g=c.getContext('2d');
  g.fillStyle=bg;g.fillRect(0,0,c.width,c.height);g.strokeStyle='#d6a960';g.lineWidth=5;g.strokeRect(4,4,c.width-8,c.height-8);
  g.fillStyle=fg;g.font='bold 50px Georgia, serif';g.textAlign='center';g.textBaseline='middle';g.fillText(message,512,66,980);
  const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
  return panel(width,height,x,z,new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}),.02);
 }
 sign("VADER'S TAXIS  •  THE PEOPLE BEHIND THE JOURNEY",Math.min(43,hx*2-2),2.3,cx,cz+hz-2.2,'#172927','#f4d39c');
 sign('SAME PEOPLE  •  DIFFERENT PROBLEMS',32,1.1,cx,cz-hz+2.7,'#243c38','#e1c391');
 const pictures=[
  ['1-68021.jpg','THE INTERN'],['2-67362.jpg','FIELD TESTING'],['3-67194.jpg','THE HEARING'],
  ['4-66709.jpg','STRATEGY ROOM'],['5-67766.jpg','THE TEAM']
 ];
 const loader=new THREE.TextureLoader();
 pictures.forEach(([file,label],i)=>{
  const x=cx-16+i*8,z=cz+.5;
  panel(7.6,6.3,x,z,new THREE.MeshBasicMaterial({color:'#172927',side:THREE.DoubleSide}),.01);
  loader.load('/assets/company/'+file,texture=>{
   texture.colorSpace=THREE.SRGBColorSpace;
   const aspect=texture.image.width/texture.image.height, width=Math.min(7.1,5.15*aspect),height=width/aspect;
   panel(width,height,x,z+.25,new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}),.03);
  },undefined,e=>console.warn('Company artwork unavailable',file,e));
  sign(label,7.2,.62,x,z-2.75,'#172927','#e6c68e');
 });
}
// The structures are the same obstacle boxes used by the physics engine;
// signs, window panes and ground paint are surface details only.
function addDistrictDetails(w){
 const labels={dispatch:'VADER’S TAXIS  /  DISPATCH',arcade:'THE STRATEGY ROOM',operations:'FLIGHT OPERATIONS',terminal:'PEOPLE  •  PLACES  •  A BRIGHTER TOMORROW',tower:'VTX  /  CONTROL',workshop:'VTX  /  ENGINEERING',freight:'VADER’S TAXIS  /  CARGO'};
 const windowMaterial=new THREE.MeshBasicMaterial({color:'#87c5c1',side:THREE.DoubleSide});
 const pane=new THREE.PlaneGeometry(2.3,1.45),matrix=new THREE.Matrix4(),rot=new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI/2,0,0));
 for(const o of w.obstacles){
  const label=labels[o.id];if(!label)continue;
  const [x,y,z]=o.center,[hx,hy,hz]=o.half,front=y-hy-.04;
  const rows=Math.min(5,Math.max(1,Math.floor((hz*2-4)/3.2))),cols=Math.min(8,Math.max(1,Math.floor((hx*2-2)/3.6)));
  const inst=new THREE.InstancedMesh(pane,windowMaterial,rows*cols);let n=0;
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
   const px=x+(col-(cols-1)/2)*3.5,pz=z-hz+2.2+row*3.1;
   matrix.compose(new THREE.Vector3(px,front,pz),rot,new THREE.Vector3(1,1,1));inst.setMatrixAt(n++,matrix);
  }
  scene.add(inst);
  const c=document.createElement('canvas');c.width=1024;c.height=128;const ctx=c.getContext('2d');
  ctx.fillStyle='#162c2b';ctx.fillRect(0,0,1024,128);ctx.strokeStyle='#d8a965';ctx.lineWidth=5;ctx.strokeRect(4,4,1016,120);
  ctx.fillStyle='#f1d4a0';ctx.font='bold 48px Georgia,serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label,512,66,980);
  const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
  const plate=new THREE.Mesh(new THREE.PlaneGeometry(Math.min(hx*2-1,27),1.8),new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}));
  plate.rotation.x=Math.PI/2;plate.position.set(x,front-.02,z+hz-1.2);scene.add(plate);
 }
 // A painted apron and taxiway help navigation without adding physical objects.
 plane(54,24,'#576766',25,-32,.022);
 plane(2,85,'#d5c189',25,-9,.029);
 for(let y=-47;y<=27;y+=10)plane(1.1,5,'#e5d7a7',25,y,.033);
}
function buildWorld(w){
 console.log('VTX: terrain building');
 world=w;const n=w.heights_m.length,vertices=[],indices=[],colors=[];
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){const x=-w.half_m+i/(n-1)*w.half_m*2,y=-w.half_m+j/(n-1)*w.half_m*2,z=w.heights_m[j][i];vertices.push(x,y,z);const col=new THREE.Color(z>25?'#8a9273':'#7b9674');col.multiplyScalar(.96+.04*Math.sin(x/27)*Math.cos(y/33));colors.push(col.r,col.g,col.b);}
 for(let j=0;j<n-1;j++)for(let i=0;i<n-1;i++){const a=j*n+i;indices.push(a,a+1,a+n+1,a,a+n+1,a+n);}
 const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geom.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geom.setIndex(indices);geom.computeVertexNormals();const terrain=new THREE.Mesh(geom,new THREE.MeshStandardMaterial({vertexColors:true,roughness:1}));terrain.receiveShadow=true;scene.add(terrain);
 for(const o of w.obstacles){let geometry;if(o.kind==='box')geometry=new THREE.BoxGeometry(...o.half.map(v=>v*2));else{geometry=new THREE.CylinderGeometry(o.half[0],o.half[0],o.half[2]*2,10);geometry.rotateX(Math.PI/2);}const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:o.color,roughness:.86}));mesh.position.set(...o.center);mesh.castShadow=true;mesh.receiveShadow=true;scene.add(mesh);
  if(o.kind==='cylinder'){const crown=new THREE.Mesh(new THREE.ConeGeometry(o.half[0]*2.2,o.half[2]*1.2,7),new THREE.MeshStandardMaterial({color:'#405f4c',roughness:1}));crown.rotation.x=Math.PI/2;crown.position.set(o.center[0],o.center[1],o.center[2]+o.half[2]*.7);crown.castShadow=true;scene.add(crown);}else if(o.landable){const roof=plane(8,8,'#9cb4aa',o.center[0],o.center[1],o.center[2]+o.half[2]+.015);const ring=new THREE.Mesh(new THREE.RingGeometry(2.7,2.9,48),new THREE.MeshBasicMaterial({color:'#c1d4c7',side:THREE.DoubleSide}));ring.position.copy(roof.position);ring.position.z+=.01;scene.add(ring);}
 }
 // Survey paint and service strips are visual markings on the same physical ground.
 plane(95,16,'#626d6a',-42,-65,.015);plane(2,320,'#a9ad96',-27,0,.012);
 for(let x=-80;x<10;x+=12)plane(5,.15,'#c7ccb8',x,-65,.021);
 const grid=new THREE.GridHelper(180,18,'#a9b5a5','#a8b3a1');grid.rotation.x=Math.PI/2;grid.position.z=.025;grid.material.transparent=true;grid.material.opacity=.2;scene.add(grid);
 const water=plane(w.water.half_x*2,w.water.half_y*2,'#6f9fa8',w.water.x,w.water.y,surfaceZ(w.water.x,w.water.y)+.1);water.material.metalness=.3;water.material.roughness=.3;
 if(!lightweightView){addDistrictDetails(w);addCompanyGallery(w);}updateMarkers();drawMaps();console.log('VTX: terrain ready');
}
let loadedAsset=null,assetRetryAfter=0,modelReady=false;
function disposeModel(root){
 const geometries=new Set(),materials=new Set(),textures=new Set();
 root.traverse(n=>{if(!n.isMesh)return;if(n.geometry)geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});
 geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}
function loadAirframe(asset){
 if(asset===loadedAsset||performance.now()<assetRetryAfter)return;loadedAsset=asset;
 $('loading').hidden=false;$('loading').textContent='Loading physical revision…';
 new GLTFLoader().load(asset,async g=>{
 if(asset!==loadedAsset){disposeModel(g.scene);return;}
 if(model){scene.remove(model);disposeModel(model);}
 for(const key of Object.keys(bodyNodes))delete bodyNodes[key];pitchMeshes.length=0;
 model=g.scene;modelReady=false;scene.add(model);model.traverse(n=>{if(n.userData.physical_body&&n.type==='Object3D')bodyNodes[n.userData.physical_body]=n;if(n.isMesh){n.castShadow=true;n.receiveShadow=true;if(n.userData.pitch_axis)pitchMeshes.push(n);if(n.material){n.material.side=THREE.DoubleSide;}}});
 // Blender exports empty groups as Object3D or Group depending on loader.
 for(const name of ['airframe','cabin',...Array.from({length:4},(_,i)=>`nacelle${i+1}`),...Array.from({length:4},(_,i)=>`rotor${i+1}`),...Array.from({length:6},(_,i)=>`gear${i+1}`),...Array.from({length:4},(_,i)=>`shaft${i+1}`)]){const n=model.getObjectByName(name);if(n)bodyNodes[name]=n;}
 // Display-only batching retains every triangle and the source IDs; the mass
 // ledger/colliders remain per-part. Keep independently pitched blades separate.
 const sourceModel=model,geometryRefs=new Map();
 sourceModel.traverse(n=>{if(n.isMesh)geometryRefs.set(n.geometry,(geometryRefs.get(n.geometry)||0)+1);});
 let batchStarted=performance.now();
 for(const body of Object.values(bodyNodes)){
  const batches=new Map();
  for(const n of [...body.children])if(n.isMesh&&!n.userData.pitch_axis&&!Array.isArray(n.material)){
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
$('cabin-level').onchange=()=>{command.cabin_level=$('cabin-level').checked;dirty=true;};
$('cabin-face-travel').onclick=()=>{const o=last?.observation;if(!o){toast('Flight instruments are not available.');return;}const [vx,vy]=o.gnss_velocity_mps;if(Math.hypot(vx,vy)<.5){toast('Direction of travel is unavailable at this speed.');return;}const heading=THREE.MathUtils.radToDeg(Math.atan2(vx,-vy));const yaw=THREE.MathUtils.euclideanModulo(heading-o.attitude_xyz_deg[2]+180,360)-180;command.cabin_deg[2]=yaw;$('cabin-yaw').value=yaw;$('cabin-yaw-value').value=yaw.toFixed(0)+'°';dirty=true;};
const onMap=async(event,canvas)=>{if(last?.active){toast('End the current sortie before selecting the next mission.');return;}const rect=canvas.getBoundingClientRect(),x=((event.clientX-rect.left)/rect.width-.5)*world.half_m*2,y=(.5-(event.clientY-rect.top)/rect.height)*world.half_m*2;await choosePoint([Math.round(x*10)/10,Math.round(y*10)/10]);};
async function choosePoint(p){const verdict=await api(`/api/validate?x=${p[0]}&y=${p[1]}`);$('validation').textContent=`${pick.toUpperCase()} (${p.join(', ')}): ${verdict.reason}`;$('large-validation').textContent=$('validation').textContent;if(!verdict.valid){toast(verdict.reason);return;}if(pick==='a'){departure=p;$('dep').value=p.join(', ');}else{destination=p;$('dest').value=p.join(', ');}updateMarkers();drawMaps();}
$('map').onclick=guard(e=>onMap(e,$('map')));$('large-map').onclick=guard(e=>onMap(e,$('large-map')));
function setPick(p){pick=p;$('pick-a').classList.toggle('selected',p==='a');$('pick-b').classList.toggle('selected',p==='b');$('large-pick').textContent=p.toUpperCase();}
$('pick-a').onclick=()=>setPick('a');$('pick-b').onclick=()=>setPick('b');
for(const [id,p] of [['dep','a'],['dest','b']])$(id).onchange=guard(async()=>{const vals=$(id).value.split(',').map(Number);if(vals.length!==2||vals.some(v=>!Number.isFinite(v)))throw Error('Use two finite coordinates: east, north');setPick(p);await choosePoint(vals);});
$('map-zoom').onclick=()=>{$('map-dialog').showModal();drawMaps();};
$('start').onclick=guard(async()=>{replayFrames=null;const r=await api('/api/mission',{departure,destination,authority:$('pilot').value,time_scale:+$('scale').value,stability_assist:+$('assist').value/100,reference_rpm:+$('drive').value,gear_variant:$('gear').value,airframe_variant:$('airframe').value,fuel_kg:selectedFuel(),engine_power_limit_kw:+$('power-limit').value,label:'Map-selected live ground-to-ground attempt'});manualOwned=$('pilot').value==='manual';if(manualOwned)manualChannel.postMessage('takeover');track=[];toast('Sortie '+r.run_id+' started on the landing gear.');});
$('end').onclick=guard(async()=>{const r=await api('/api/stop',{reason:'Operator ended the live attempt'});toast(`Recorded: ${r.outcome}. Every failed attempt is retained.`);});
for(const authority of ['manual','colin'])$('retry-'+authority).onclick=guard(async()=>{
 replayFrames=null;
 const r=await api('/api/retry',{authority,time_scale:authority==='colin'?.02:.1,stability_assist:+$('assist').value/100,airframe_variant:$('airframe').value,fuel_kg:selectedFuel(),engine_power_limit_kw:+$('power-limit').value});
 manualOwned=authority==='manual';if(manualOwned)manualChannel.postMessage('takeover');
 command.engine=0;command.collective_deg.fill(0);command.tilt_deg=[[0,0],[0,0],[0,0],[0,0]];dirty=false;
 toast(authority==='colin'?'New sortie '+r.run_id+'. Waiting for Colin to issue live commands; retry does not start an automatic pilot.':'New sortie '+r.run_id+'. The previous run and pilot checkpoint are preserved.');
});
$('pause').onclick=guard(async()=>{await api('/api/operator',{paused:!last.paused});});
$('takeover').onclick=guard(async()=>{
 if(last){const o=last.observation,issued=last.recent_decisions.at(-1)?.issued;
  command.engine=issued?.engine??(Math.max(...o.rotor_rpm)>300?1:0);
  command.collective_deg=[...o.collective_feedback_deg];command.tilt_deg=o.tilt_feedback_deg.map(v=>[...v]);
  command.cabin_deg=[...(issued?.cabin_deg??o.cabin_feedback_deg??[0,0,0])];if(command.cabin_deg.length===2)command.cabin_deg.push(0);command.cabin_level=issued?.cabin_level??true;$('cabin-level').checked=command.cabin_level;for(const [id,axis] of [['cabin-x',0],['cabin-y',1],['cabin-yaw',2]])$(id).value=command.cabin_deg[axis];$('cabin-yaw-value').value=command.cabin_deg[2].toFixed(0)+'°';
  $('engine').value=command.engine;$('engine-value').value=Math.round(command.engine*100)+'%';
  for(let i=0;i<4;i++){$('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';}
 }
 await api('/api/operator',{authority:'manual'});manualChannel.postMessage('takeover');manualOwned=true;$('pilot').value='manual';dirty=true;toast('Manual authority acquired with the current actuator settings.');
});
$('scale').onchange=guard(async()=>{await api('/api/operator',{time_scale:+$('scale').value});});
$('feather').onclick=()=>{command.engine=0;command.collective_deg.fill(0);$('engine').value=0;$('engine').oninput();$('common').value=0;$('common').oninput();dirty=true;};
let cockpitYaw=0,cockpitPitch=0,cockpitPointer=null;
function setCameraMode(mode){cameraMode=mode;orbit.enabled=mode!=='cockpit';renderer.domElement.style.touchAction='none';$('cockpit-look').hidden=mode!=='cockpit';$('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';$('camera').textContent=mode==='chase'?'Chase camera':'Free orbit';}
$('camera').onclick=()=>setCameraMode(cameraMode==='chase'?'orbit':'chase');
$('cockpit').onclick=()=>setCameraMode(cameraMode==='cockpit'?'chase':'cockpit');
function zoomCamera(factor){
 if(cameraMode==='cockpit'){toast('Zoom is available in the external camera.');return;}
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
 const pitch=(down('KeyW')-down('KeyS'))*.06,roll=(down('KeyD')-down('KeyA'))*.06;
 const yaw=(down('KeyE')-down('KeyQ'))*.15;
 const tx=(down('ArrowUp')-down('ArrowDown'))*.15;
 const ty=(down('ArrowRight')-down('ArrowLeft'))*.15;
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
const mapBackgrounds=new WeakMap();
function drawMap(canvas){if(!world)return;const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,n=world.heights_m.length;const px=x=>(x/(2*world.half_m)+.5)*w,py=y=>(.5-y/(2*world.half_m))*h;
 let bg=mapBackgrounds.get(canvas);
 if(!bg||bg.width!==w||bg.height!==h||bg.world!==world){
 const layer=document.createElement('canvas');layer.width=w;layer.height=h;const ctx=layer.getContext('2d');ctx.fillStyle='#2c4845';ctx.fillRect(0,0,w,h);
 for(let j=0;j<n-1;j++)for(let i=0;i<n-1;i++){const v=world.heights_m[j][i],shade=Math.round(55+v*1.0);ctx.fillStyle=`rgb(${shade},${shade+27},${shade+17})`;ctx.fillRect(i/(n-1)*w,h-(j+1)/(n-1)*h,w/(n-1)+1,h/(n-1)+1);}
 ctx.strokeStyle='#adcec420';ctx.lineWidth=1;for(let x=-500;x<=500;x+=100){ctx.beginPath();ctx.moveTo(px(x),0);ctx.lineTo(px(x),h);ctx.stroke();ctx.beginPath();ctx.moveTo(0,py(x));ctx.lineTo(w,py(x));ctx.stroke();}
 for(const o of world.obstacles){ctx.fillStyle=o.landable?'#abbcac':'#b08d72';const [x,y]=o.center,[hx,hy]=o.half;ctx.fillRect(px(x-hx),py(y+hy),hx/world.half_m*w,hy/world.half_m*h);}
 const water=world.water;ctx.fillStyle='#6c9baf';ctx.fillRect(px(water.x-water.half_x),py(water.y+water.half_y),water.half_x/world.half_m*w,water.half_y/world.half_m*h);
 bg={width:w,height:h,world,layer};mapBackgrounds.set(canvas,bg);
 }
 ctx.drawImage(bg.layer,0,0);
 if(track.length>1){ctx.strokeStyle='#d9f0eaa0';ctx.lineWidth=2;ctx.beginPath();track.forEach((p,i)=>i?ctx.lineTo(px(p[0]),py(p[1])):ctx.moveTo(px(p[0]),py(p[1])));ctx.stroke();}
 for(const [p,label,col] of [[departure,'A','#7cdfcb'],[destination,'B','#ffc88b']]){const x=px(p[0]),y=py(p[1]);ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,Math.max(6,w/85),0,Math.PI*2);ctx.fill();ctx.fillStyle='#15342e';ctx.font=`bold ${Math.max(9,w/65)}px system-ui`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label,x,y+.5);}
 if(last){const p=last.observation.gnss_xy_m;ctx.strokeStyle='#fff';ctx.lineWidth=1.7;const x=px(p[0]),y=py(p[1]);ctx.beginPath();ctx.moveTo(x,y-5);ctx.lineTo(x+4,y+4);ctx.lineTo(x-4,y+4);ctx.closePath();ctx.stroke();}
 ctx.fillStyle='#ddede6';ctx.font=`${Math.max(9,w/60)}px system-ui`;ctx.textAlign='left';ctx.fillText('N ↑',10,17);ctx.fillText('0',w/2+4,h/2+12);
}
let lastMapMs=0;
function drawMaps(force=false){if(!force&&performance.now()-lastMapMs<400)return;lastMapMs=performance.now();drawMap($('map'));if($('map-dialog').open)drawMap($('large-map'));}
function updateEngineering(){if(!last)return;const t=last.rendering_truth;$('engineering-content').textContent=JSON.stringify({revision:t.provenance.revision,status:t.provenance.status,mass:t.mass,power:t.power,energy:t.energy,flags:t.flags,contact_events:t.events,hypotheses:t.provenance.hypotheses},null,2);}
function updateView(v){last=v;latestTruthReceivedMs=performance.now();
 // Always ingest the latest physical pose; avoid repainting the entire HUD at
 // the websocket rate on low-powered phones. 3D rendering is independent.
 if(lightweightView&&latestTruthReceivedMs-lastHudUpdateMs<500&&v.run_id===lastRun)return;
 lastHudUpdateMs=latestTruthReceivedMs;const o=v.observation,t=v.rendering_truth;if(v.run_id!==lastRun){lastRun=v.run_id;track=[];if(v.mission){departure=[...v.mission.departure];destination=[...v.mission.destination];$('dep').value=departure.join(', ');$('dest').value=destination.join(', ');updateMarkers();}}
 $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE EXPERIMENT'):'INSPECTION';$('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';$('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
 const latestPilot=v.recent_decisions.at(-1),pilotWaiting=v.active&&v.authority==='colin'&&(!latestPilot||o.warning_lamps.includes('COMMAND_LEASE_EXPIRED')||o.t_s-latestPilot.issued_t_s>1);$('colin-wait').hidden=!pilotWaiting;$('colin-wait').textContent=pilotWaiting?'Waiting for live Colin commands. The retry button does not start an automatic pilot.':'';
 $('authority').textContent=v.authority.toUpperCase();$('start').disabled=v.active;$('end').disabled=!v.active;$('pause').disabled=!v.active;$('pause').textContent=v.paused?'Resume physics':'Pause physics';$('revision').textContent=t.provenance.revision.toUpperCase();$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';
 $('retry-bar').hidden=!(v.retry_available&&(!v.active||t.crashed));
 $('retry-status').textContent=t.crashed?'Crash recorded · retry starts a new aircraft at A.':'Retained mission · retry preserves the pilot checkpoint.';
 $('alt').innerHTML=o.radar_clearance_m.toFixed(2)+'<small>m</small>';$('vs').innerHTML=o.gnss_velocity_mps[2].toFixed(2)+'<small>m/s</small>';$('speed').innerHTML=Math.hypot(...o.gnss_velocity_mps.slice(0,2)).toFixed(2)+'<small>m/s</small>';$('power').innerHTML=o.engine_shaft_kw.toFixed(1)+'<small>kW</small>';$('fuel').innerHTML=o.fuel_kg.reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
 for(let i=0;i<4;i++)$('rpm-'+i).textContent=o.rotor_rpm[i].toFixed(0)+' rpm';
 if(o.assisted_collective_deg)$('assist-feedback').textContent='Shadow requests: '+o.assisted_collective_deg.map(x=>x.toFixed(2)+'°').join(' / ')+' · not applied';
 for(const el of document.querySelectorAll('.controls-panel input[type=range]:not(#assist),#feather'))el.disabled=v.authority!=='manual'||!manualOwned;
 const cabinLocked=v.authority!=='manual'||!manualOwned;for(const el of document.querySelectorAll('.tilt-spin'))el.disabled=cabinLocked;if(cabinLocked)tiltSpin.fill(0);$('cabin-level').disabled=cabinLocked;$('cabin-face-travel').disabled=cabinLocked;$('cabin-x').disabled=cabinLocked||command.cabin_level;$('cabin-y').disabled=cabinLocked||command.cabin_level;if(o.cabin_feedback_deg)$('cabin-feedback').textContent='Actual gimbal X / Y / yaw: '+o.cabin_feedback_deg.map(x=>x.toFixed(1)+'°').join(' / ');
 for(const id of ['dep','dest','drive','gear','airframe','initial-fuel','power-limit','pilot'])$(id).disabled=v.active;
 if(v.active){$('power-limit').value=t.provenance.engine_power_limit_kw??469.8;$('initial-fuel').value=t.provenance.initial_fuel_kg??o.configuration.initial_fuel_kg;$('pilot').value=v.authority;$('scale').value=String(v.time_scale);$('drive').value=String(t.provenance.reference_rpm);$('gear').value=t.provenance.gear_variant;$('airframe').value=t.provenance.revision.endsWith('r4')?'baseline':'light';}
 if(v.authority==='colin'||!manualOwned){const issued=v.recent_decisions.at(-1)?.issued;$('engine').value=issued?.engine??0;$('engine-value').value=Math.round((issued?.engine??0)*100)+'%';$('common').value=o.collective_feedback_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=o.collective_feedback_deg[i];$('pval-'+i).value=o.collective_feedback_deg[i].toFixed(1)+'°';for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=o.tilt_feedback_deg[i][j];$(k+'val-'+i).value=o.tilt_feedback_deg[i][j].toFixed(1)+'°';}}}
 $('angles').textContent=o.attitude_xyz_deg.map((x,i)=>`${'XYZ'[i]} ${x.toFixed(1)}°`).join(' · ');$('horizon').style.transform=`translateY(${o.attitude_xyz_deg[1]*1.2}px) rotate(${-o.attitude_xyz_deg[0]}deg)`;
 if(t.crashed||v.error){$('consequence').hidden=false;$('consequence').textContent=v.error?'Solver stopped: '+v.error:'IMPACT RECORDED · '+(t.events[0]?.body||'aircraft')+'. Physical consequences remain active; no automatic rescue.';}else{$('consequence').hidden=true;}
 const key=v.recent_decisions.map(a=>a.sequence).join(',');if(key!==lastDecision){lastDecision=key;$('decisions').replaceChildren();for(const d of [...v.recent_decisions].reverse()){const a=document.createElement('article'),tm=document.createElement('time'),p=document.createElement('p'),code=document.createElement('code');tm.textContent=`${d.issued_t_s.toFixed(3)} s / ${d.issued.authority.toUpperCase()}`;p.textContent=d.decision;code.textContent=`Collective ${d.issued.collective_deg.join(' / ')}° · engine ${d.issued.engine}`;a.append(tm,p,code);$('decisions').appendChild(a);}}
 if(v.active&&(!track.length||Math.hypot(o.gnss_xy_m[0]-track.at(-1)[0],o.gnss_xy_m[1]-track.at(-1)[1])>.2)){track.push(o.gnss_xy_m);if(track.length>3000)track.shift();}drawMaps();if($('engineering-dialog').open)updateEngineering();
}
let manualRequestPending=false;
setInterval(guard(async()=>{if(manualRequestPending||!last?.active||last.authority!=='manual'||!manualOwned||last.paused||replayFrames)return;manualBeat++;if(dirty||manualBeat%10===0){dirty=false;manualRequestPending=true;try{await api('/api/action',{...command,authority:'manual',observation_id:last.observation.observation_id,reason:'Manual operator controls and command heartbeat'});}catch(e){dirty=true;throw e;}finally{manualRequestPending=false;}}}),50);
function connect(){const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);ws.onmessage=e=>updateView(JSON.parse(e.data));ws.onclose=()=>{toast('Live connection lost; physical command lease still applies.');setTimeout(connect,2000);};}
api('/api/world').then(buildWorld).catch(e=>toast(e.message));connect();
const q=new THREE.Quaternion(),pos=new THREE.Vector3(),cameraTarget=new THREE.Vector3();
let lastFrameMs=0;
function animate(){requestAnimationFrame(animate);const now=performance.now();if(now-lastFrameMs<(lightweightView?67:50))return;lastFrameMs=now;const truth=replayFrames?.[replayFrame]||last?.rendering_truth;
 if(truth)loadAirframe(truth.provenance.render_asset||(truth.provenance.revision.endsWith('r4')?'/assets/airframe-r4.glb':'/assets/airframe-live.glb'));
 if(truth&&model){for(const [name,pose] of Object.entries(truth.body_poses)){const n=bodyNodes[name];if(!n)continue;n.position.set(...pose.position);const a=pose.quaternion_wxyz;n.quaternion.set(a[1],a[2],a[3],a[0]);
   // The authoritative rotor pose is sampled at 20 Hz. At 1200 RPM one full
   // revolution occurs between samples, so drawing snapshots alone looks static.
   // Use measured signed angular velocity solely for sub-frame presentation.
   if(!replayFrames&&name.startsWith('rotor')&&/^rotor[1-4]$/.test(name)){
    const i=Number(name.slice(-1))-1;
    const angle=rotorVisualOffset(truth.rotor_spin_rad_s?.[i],now-latestTruthReceivedMs,last?.time_scale,last?.active,last?.paused);
    if(angle)n.quaternion.multiply(rotorSpinQ.setFromAxisAngle(rotorSpinAxis,angle));
   }
  }for(const mesh of pitchMeshes){const i=Number(mesh.userData.physical_body?.slice(-1))-1;if(i>=0&&i<4)mesh.quaternion.setFromAxisAngle(new THREE.Vector3(...mesh.userData.pitch_axis).normalize(),THREE.MathUtils.degToRad(truth.pitch_deg[i]));}
  const base=truth.body_poses.airframe,posArray=base.position;pos.set(posArray[0],posArray[1],posArray[2]+1.5);
  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);}
  if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position).add(new THREE.Vector3(-.30,.02,.25).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));const cp=Math.cos(cockpitPitch);cameraTarget.copy(camera.position).add(new THREE.Vector3(Math.sin(cockpitYaw)*cp,-Math.cos(cockpitYaw)*cp,Math.sin(cockpitPitch)).applyQuaternion(q));camera.lookAt(cameraTarget);}else{camera.up.set(0,0,1);orbit.update();}
  sun.target.position.copy(pos);sun.position.copy(pos).add(new THREE.Vector3(-70,-90,140));
 }
 if(model&&modelReady&&!window.__vtxNoRender)renderer.render(scene,camera);
 const status=$('view-sync');if(status&&now-(status._last||0)>400){status._last=now;
  const age=now-latestTruthReceivedMs;
  status.textContent=!last?'WAITING FOR DATA':age>2000?'DISPLAY STALE':!modelReady?'LOADING AIRCRAFT':`LIVE VIEW · ${Math.round(age)} ms · ${Math.round(last?.observation?.rotor_rpm?.[0]||0)} RPM · t ${last?.observation?.t_s?.toFixed(1)??'--'}s`;
  status.style.color=age>2000?'#ffb19d':'#b6f6d8';
 }
}animate();
