import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {mergeGeometries} from './vendor/BufferGeometryUtils.js';

const $=id=>document.getElementById(id);
let last=null,world=null,model=null,pick='a',cameraMode='chase',replayFrames=null,replayFrame=0;
let departure=[0,0],destination=[-50,20],track=[],lastDecision='',lastRun=null;
const bodyNodes={},pitchMeshes=[];
const command={engine:0,collective_deg:[0,0,0,0],tilt_deg:[[0,0],[0,0],[0,0],[0,0]],cabin_deg:[0,0]};
let dirty=false,manualBeat=0;
async function api(path,body){
 const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;
}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,6500);}
function guard(fn){return async(...args)=>{try{await fn(...args);}catch(e){toast(e.message);}};}

console.log('VTX: module ready');
const viewport=$('viewport'),scene=new THREE.Scene();scene.background=new THREE.Color('#a9c1ca');scene.fog=new THREE.Fog('#b3c7c9',240,1000);
const camera=new THREE.PerspectiveCamera(48,1,.05,2000);camera.up.set(0,0,1);camera.position.set(9,-11,8);
const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.2));renderer.shadowMap.enabled=false;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;viewport.appendChild(renderer.domElement);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.target.set(0,0,1.4);orbit.enableDamping=true;orbit.maxPolarAngle=Math.PI*.49;orbit.minDistance=2;orbit.maxDistance=600;
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
 updateMarkers();drawMaps();console.log('VTX: terrain ready');
}
new GLTFLoader().load('/assets/airframe-live.glb',g=>{
 console.log('VTX: aircraft received');
 model=g.scene;scene.add(model);model.traverse(n=>{if(n.userData.physical_body&&n.type==='Object3D')bodyNodes[n.userData.physical_body]=n;if(n.isMesh){n.castShadow=true;n.receiveShadow=true;if(n.userData.pitch_axis)pitchMeshes.push(n);if(n.material){n.material.side=THREE.DoubleSide;}}});
 // Blender exports empty groups as Object3D or Group depending on loader.
 for(const name of ['airframe','cabin',...Array.from({length:4},(_,i)=>`nacelle${i+1}`),...Array.from({length:4},(_,i)=>`rotor${i+1}`),...Array.from({length:6},(_,i)=>`gear${i+1}`),...Array.from({length:4},(_,i)=>`shaft${i+1}`)]){const n=model.getObjectByName(name);if(n)bodyNodes[name]=n;}
 // Display-only batching retains every triangle and the source IDs; the mass
 // ledger/colliders remain per-part. Keep independently pitched blades separate.
 for(const body of Object.values(bodyNodes)){
  const batches=new Map();
  for(const n of [...body.children])if(n.isMesh&&!n.userData.pitch_axis&&!Array.isArray(n.material)){
   const key=n.material.uuid+Object.keys(n.geometry.attributes).sort().join(',');
   if(!batches.has(key))batches.set(key,[]);batches.get(key).push(n);
  }
  for(const meshes of batches.values())if(meshes.length>1){
   const merged=mergeGeometries(meshes.map(n=>{n.updateMatrix();return n.geometry.clone().applyMatrix4(n.matrix);}));
   if(merged){const n=new THREE.Mesh(merged,meshes[0].material);n.castShadow=true;n.receiveShadow=true;n.userData.source_ids=meshes.map(m=>m.userData.blendstra_id);meshes.forEach(m=>m.removeFromParent());body.add(n);}
  }
 }
 $('loading').hidden=true;console.log('VTX: aircraft ready');toast('Recovered source assembly loaded. No motion animation is used.');
},undefined,e=>{$('loading').textContent='Aircraft asset failed to load';console.error(e);});

for(let i=0;i<4;i++){
 const div=document.createElement('div');div.className='rotor';div.innerHTML=`<div class="rotor-top"><b>F${i+1} / ${['EAST','NORTH','WEST','SOUTH'][i]}</b><span id="rpm-${i}">0 rpm</span></div><label class="range-label">Collective <output id="pval-${i}">0.0°</output><input type="range" id="p-${i}" min="0" max="30" step="0.1" value="0" aria-label="Rotor ${i+1} collective"></label><div class="vector-controls"><label class="range-label">Tilt X <output id="xval-${i}">0°</output><input id="x-${i}" type="range" min="-20" max="20" step="0.1" value="0" aria-label="Rotor ${i+1} tilt X"></label><label class="range-label">Tilt Y <output id="yval-${i}">0°</output><input id="y-${i}" type="range" min="-20" max="20" step="0.1" value="0" aria-label="Rotor ${i+1} tilt Y"></label></div>`;$('rotors').appendChild(div);
 for(const key of ['p','x','y'])$(key+'-'+i).oninput=()=>{const val=Number($(key+'-'+i).value);if(key==='p')command.collective_deg[i]=val;else command.tilt_deg[i][key==='x'?0:1]=val;$(key+'val-'+i).value=val.toFixed(1)+'°';dirty=true;};
}
$('engine').oninput=()=>{command.engine=+$('engine').value;$('engine-value').value=Math.round(command.engine*100)+'%';dirty=true;};
$('common').oninput=()=>{command.collective_deg.fill(+$('common').value);$('common-value').value=(+$('common').value).toFixed(1)+'°';for(let i=0;i<4;i++){$('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';}dirty=true;};
for(const [key,axis] of [['common-x',0],['common-y',1]])$(key).oninput=()=>{for(let i=0;i<4;i++){command.tilt_deg[i][axis]=+$(key).value;$(axis?'y-'+i:'x-'+i).value=+$(key).value;$(axis?'yval-'+i:'xval-'+i).value=(+$(key).value).toFixed(1)+'°';}dirty=true;};
const onMap=async(event,canvas)=>{const rect=canvas.getBoundingClientRect(),x=((event.clientX-rect.left)/rect.width-.5)*world.half_m*2,y=(.5-(event.clientY-rect.top)/rect.height)*world.half_m*2;await choosePoint([Math.round(x*10)/10,Math.round(y*10)/10]);};
async function choosePoint(p){const verdict=await api(`/api/validate?x=${p[0]}&y=${p[1]}`);$('validation').textContent=`${pick.toUpperCase()} (${p.join(', ')}): ${verdict.reason}`;$('large-validation').textContent=$('validation').textContent;if(!verdict.valid){toast(verdict.reason);return;}if(pick==='a'){departure=p;$('dep').value=p.join(', ');}else{destination=p;$('dest').value=p.join(', ');}updateMarkers();drawMaps();}
$('map').onclick=guard(e=>onMap(e,$('map')));$('large-map').onclick=guard(e=>onMap(e,$('large-map')));
function setPick(p){pick=p;$('pick-a').classList.toggle('selected',p==='a');$('pick-b').classList.toggle('selected',p==='b');$('large-pick').textContent=p.toUpperCase();}
$('pick-a').onclick=()=>setPick('a');$('pick-b').onclick=()=>setPick('b');
for(const [id,p] of [['dep','a'],['dest','b']])$(id).onchange=guard(async()=>{const vals=$(id).value.split(',').map(Number);if(vals.length!==2||vals.some(v=>!Number.isFinite(v)))throw Error('Use two finite coordinates: east, north');setPick(p);await choosePoint(vals);});
$('map-zoom').onclick=()=>{$('map-dialog').showModal();drawMaps();};
$('start').onclick=guard(async()=>{replayFrames=null;const r=await api('/api/mission',{departure,destination,authority:$('pilot').value,time_scale:+$('scale').value,reference_rpm:+$('drive').value,gear_variant:$('gear').value,label:'Map-selected live ground-to-ground attempt'});track=[];toast('Sortie '+r.run_id+' started on the landing gear.');});
$('end').onclick=guard(async()=>{const r=await api('/api/stop',{reason:'Operator ended the live attempt'});toast(`Recorded: ${r.outcome}. Every failed attempt is retained.`);});
$('pause').onclick=guard(async()=>{await api('/api/operator',{paused:!last.paused});});
$('takeover').onclick=guard(async()=>{await api('/api/operator',{authority:'manual'});$('pilot').value='manual';dirty=true;toast('Manual authority acquired. Same fly-by-wire channels.');});
$('scale').onchange=guard(async()=>{await api('/api/operator',{time_scale:+$('scale').value});});
$('feather').onclick=()=>{command.engine=0;command.collective_deg.fill(0);$('engine').value=0;$('engine').oninput();$('common').value=0;$('common').oninput();dirty=true;};
$('camera').onclick=()=>{cameraMode=cameraMode==='chase'?'orbit':'chase';$('camera').textContent=cameraMode==='chase'?'Chase camera':'Free orbit';orbit.enabled=true;};
$('cockpit').onclick=()=>{cameraMode=cameraMode==='cockpit'?'chase':'cockpit';orbit.enabled=cameraMode!=='cockpit';};
// Keyboard mixing is an explicitly disclosed mapping to the same raw channels.
// It reads keys only: no position, attitude, velocity or navigation feedback.
const keys=new Set();
function typing(e){return /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);}
addEventListener('keydown',e=>{
 if(typing(e))return;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code))e.preventDefault();
 if(e.code==='KeyC'&&!e.repeat)$('cockpit').click();
 if(last?.authority!=='manual'||!last.active)return;
 if(e.code==='KeyX'&&!e.repeat){$('engine').value=command.engine>.5?0:1;$('engine').oninput();}
 if(e.code==='Space'){$('feather').click();keys.clear();}
 keys.add(e.code);
});
addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>keys.clear());
setInterval(()=>{
 if(!last?.active||last.authority!=='manual'||last.paused||replayFrames||!keys.size)return;
 const down=k=>keys.has(k)?1:0,delta=.12;
 const lift=(down('KeyR')-down('KeyF'))*delta;
 const pitch=(down('KeyW')-down('KeyS'))*.06,roll=(down('KeyD')-down('KeyA'))*.06;
 const yaw=(down('KeyE')-down('KeyQ'))*.15;
 const tx=(down('ArrowLeft')-down('ArrowRight'))*.15;
 const ty=(down('ArrowUp')-down('ArrowDown'))*.15;
 // Collective torque mix: north/south produce body X torque; east/west Y.
 const differential=[-pitch,roll,pitch,-roll];
 const yawX=[-yaw,0,yaw,0],yawY=[0,-yaw,0,yaw];
 for(let i=0;i<4;i++){
  command.collective_deg[i]=THREE.MathUtils.clamp(command.collective_deg[i]+lift+differential[i],0,30);
  command.tilt_deg[i][0]=THREE.MathUtils.clamp(command.tilt_deg[i][0]+tx+yawX[i],-20,20);
  command.tilt_deg[i][1]=THREE.MathUtils.clamp(command.tilt_deg[i][1]+ty+yawY[i],-20,20);
  $('p-'+i).value=command.collective_deg[i];$('pval-'+i).value=command.collective_deg[i].toFixed(1)+'°';
  for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=command.tilt_deg[i][j];$(k+'val-'+i).value=command.tilt_deg[i][j].toFixed(1)+'°';}
 }
 $('common').value=command.collective_deg.reduce((a,b)=>a+b,0)/4;$('common-value').value=(+$('common').value).toFixed(1)+'°';
 dirty=true;
},50);
for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>b.closest('dialog').close();
$('engineering').onclick=()=>{$('engineering-dialog').showModal();updateEngineering();};
$('history').onclick=guard(async()=>{const records=await api('/api/runs');$('runs').replaceChildren();for(const r of records){const a=document.createElement('article'),button=document.createElement('button');button.textContent='Inspect recorded states';button.onclick=guard(async()=>{const replay=await api('/api/replay/'+r.run_id);replayFrames=replay.frames;replayFrame=0;$('replay-time').max=Math.max(0,replayFrames.length-1);$('replay-controls').hidden=false;$('view-mode').textContent='POST-FLIGHT AUDIT · NO CONTROL';toast('Inspection only. The live physical plant remains separate.');});a.append(button,document.createTextNode(`${r.run_id} · ${r.outcome} · ${r.simulated_seconds.toFixed(1)} s · ${r.decisions} decisions`));$('runs').appendChild(a);}$('history-dialog').showModal();});
$('replay-time').oninput=()=>replayFrame=+$('replay-time').value;
$('return-live').onclick=()=>{replayFrames=null;$('replay-controls').hidden=true;$('view-mode').textContent='PHYSICAL STATE · LIVE';};
function drawMap(canvas){if(!world)return;const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,n=world.heights_m.length;ctx.fillStyle='#2c4845';ctx.fillRect(0,0,w,h);const px=x=>(x/(2*world.half_m)+.5)*w,py=y=>(.5-y/(2*world.half_m))*h;
 for(let j=0;j<n-1;j++)for(let i=0;i<n-1;i++){const v=world.heights_m[j][i],shade=Math.round(55+v*1.0);ctx.fillStyle=`rgb(${shade},${shade+27},${shade+17})`;ctx.fillRect(i/(n-1)*w,h-(j+1)/(n-1)*h,w/(n-1)+1,h/(n-1)+1);}
 ctx.strokeStyle='#adcec420';ctx.lineWidth=1;for(let x=-500;x<=500;x+=100){ctx.beginPath();ctx.moveTo(px(x),0);ctx.lineTo(px(x),h);ctx.stroke();ctx.beginPath();ctx.moveTo(0,py(x));ctx.lineTo(w,py(x));ctx.stroke();}
 for(const o of world.obstacles){ctx.fillStyle=o.landable?'#abbcac':'#b08d72';const [x,y]=o.center,[hx,hy]=o.half;ctx.fillRect(px(x-hx),py(y+hy),hx/world.half_m*w,hy/world.half_m*h);}
 const water=world.water;ctx.fillStyle='#6c9baf';ctx.fillRect(px(water.x-water.half_x),py(water.y+water.half_y),water.half_x/world.half_m*w,water.half_y/world.half_m*h);
 if(track.length>1){ctx.strokeStyle='#d9f0eaa0';ctx.lineWidth=2;ctx.beginPath();track.forEach((p,i)=>i?ctx.lineTo(px(p[0]),py(p[1])):ctx.moveTo(px(p[0]),py(p[1])));ctx.stroke();}
 for(const [p,label,col] of [[departure,'A','#7cdfcb'],[destination,'B','#ffc88b']]){const x=px(p[0]),y=py(p[1]);ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,Math.max(6,w/85),0,Math.PI*2);ctx.fill();ctx.fillStyle='#15342e';ctx.font=`bold ${Math.max(9,w/65)}px system-ui`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label,x,y+.5);}
 if(last){const p=last.observation.gnss_xy_m;ctx.strokeStyle='#fff';ctx.lineWidth=1.7;const x=px(p[0]),y=py(p[1]);ctx.beginPath();ctx.moveTo(x,y-5);ctx.lineTo(x+4,y+4);ctx.lineTo(x-4,y+4);ctx.closePath();ctx.stroke();}
 ctx.fillStyle='#ddede6';ctx.font=`${Math.max(9,w/60)}px system-ui`;ctx.textAlign='left';ctx.fillText('N ↑',10,17);ctx.fillText('0',w/2+4,h/2+12);
}
function drawMaps(){drawMap($('map'));if($('map-dialog').open)drawMap($('large-map'));}
function updateEngineering(){if(!last)return;const t=last.rendering_truth;$('engineering-content').textContent=JSON.stringify({revision:t.provenance.revision,status:t.provenance.status,mass:t.mass,power:t.power,energy:t.energy,flags:t.flags,contact_events:t.events,hypotheses:t.provenance.hypotheses},null,2);}
function updateView(v){last=v;const o=v.observation,t=v.rendering_truth;if(v.run_id!==lastRun){lastRun=v.run_id;track=[];}
 $('state').textContent=v.active?(v.paused?'PHYSICS PAUSED':'LIVE EXPERIMENT'):'INSPECTION';$('lamp').style.background=v.active?'#7cdfcb':'#8a9a9d';$('clock').textContent=`${Math.floor(o.t_s/60).toString().padStart(2,'0')}:${(o.t_s%60).toFixed(2).padStart(5,'0')} / ${v.time_scale}×`;
 $('authority').textContent=v.authority.toUpperCase();$('start').disabled=v.active;$('end').disabled=!v.active;$('pause').disabled=!v.active;$('pause').textContent=v.paused?'Resume physics':'Pause physics';$('revision').textContent=t.provenance.revision.toUpperCase();$('run-id').textContent=v.run_id||'NO SORTIE ACTIVE';
 $('alt').innerHTML=o.radar_clearance_m.toFixed(2)+'<small>m</small>';$('vs').innerHTML=o.gnss_velocity_mps[2].toFixed(2)+'<small>m/s</small>';$('speed').innerHTML=Math.hypot(...o.gnss_velocity_mps.slice(0,2)).toFixed(2)+'<small>m/s</small>';$('power').innerHTML=o.engine_shaft_kw.toFixed(1)+'<small>kW</small>';$('fuel').innerHTML=o.fuel_kg.reduce((a,b)=>a+b,0).toFixed(2)+'<small>kg</small>';
 for(let i=0;i<4;i++)$('rpm-'+i).textContent=o.rotor_rpm[i].toFixed(0)+' rpm';
 for(const el of document.querySelectorAll('.controls-panel input[type=range],#feather'))el.disabled=v.authority!=='manual';
 if(v.authority==='colin'){for(let i=0;i<4;i++){$('p-'+i).value=o.collective_feedback_deg[i];$('pval-'+i).value=o.collective_feedback_deg[i].toFixed(1)+'°';for(let j=0;j<2;j++){const k=j?'y':'x';$(k+'-'+i).value=o.tilt_feedback_deg[i][j];$(k+'val-'+i).value=o.tilt_feedback_deg[i][j].toFixed(1)+'°';}}}
 $('angles').textContent=o.attitude_xyz_deg.map((x,i)=>`${'XYZ'[i]} ${x.toFixed(1)}°`).join(' · ');$('horizon').style.transform=`translateY(${o.attitude_xyz_deg[1]*1.2}px) rotate(${-o.attitude_xyz_deg[0]}deg)`;
 if(t.crashed||v.error){$('consequence').hidden=false;$('consequence').textContent=v.error?'Solver stopped: '+v.error:'IMPACT RECORDED · '+(t.events[0]?.body||'aircraft')+'. Physical consequences remain active; no automatic rescue.';}else{$('consequence').hidden=true;}
 const key=v.recent_decisions.map(a=>a.sequence).join(',');if(key!==lastDecision){lastDecision=key;$('decisions').replaceChildren();for(const d of [...v.recent_decisions].reverse()){const a=document.createElement('article'),tm=document.createElement('time'),p=document.createElement('p'),code=document.createElement('code');tm.textContent=`${d.issued_t_s.toFixed(3)} s / ${d.issued.authority.toUpperCase()}`;p.textContent=d.decision;code.textContent=`Collective ${d.issued.collective_deg.join(' / ')}° · engine ${d.issued.engine}`;a.append(tm,p,code);$('decisions').appendChild(a);}}
 if(v.active&&(!track.length||Math.hypot(o.gnss_xy_m[0]-track.at(-1)[0],o.gnss_xy_m[1]-track.at(-1)[1])>.2)){track.push(o.gnss_xy_m);if(track.length>3000)track.shift();}drawMaps();if($('engineering-dialog').open)updateEngineering();
}
setInterval(guard(async()=>{if(!last?.active||last.authority!=='manual'||last.paused||replayFrames)return;manualBeat++;if(dirty||manualBeat%10===0){dirty=false;await api('/api/action',{...command,authority:'manual',observation_id:last.observation.observation_id,reason:'Manual operator controls and command heartbeat'});}}),50);
function connect(){const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);ws.onmessage=e=>updateView(JSON.parse(e.data));ws.onclose=()=>{toast('Live connection lost; physical command lease still applies.');setTimeout(connect,2000);};}
api('/api/world').then(buildWorld).catch(e=>toast(e.message));connect();
const q=new THREE.Quaternion(),pos=new THREE.Vector3(),cameraTarget=new THREE.Vector3();
let lastFrameMs=0;
function animate(){requestAnimationFrame(animate);const now=performance.now();if(now-lastFrameMs<80)return;lastFrameMs=now;const truth=replayFrames?.[replayFrame]||last?.rendering_truth;
 if(truth&&model){for(const [name,pose] of Object.entries(truth.body_poses)){const n=bodyNodes[name];if(!n)continue;n.position.set(...pose.position);const a=pose.quaternion_wxyz;n.quaternion.set(a[1],a[2],a[3],a[0]);}for(const mesh of pitchMeshes){const i=Number(mesh.userData.physical_body?.slice(-1))-1;if(i>=0&&i<4)mesh.quaternion.setFromAxisAngle(new THREE.Vector3(...mesh.userData.pitch_axis).normalize(),THREE.MathUtils.degToRad(truth.pitch_deg[i]));}
  const base=truth.body_poses.airframe,posArray=base.position;pos.set(posArray[0],posArray[1],posArray[2]+1.5);
  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);}
  if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position).add(new THREE.Vector3(0,-.18,.05).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));cameraTarget.copy(camera.position).add(new THREE.Vector3(0,-1,.02).applyQuaternion(q));camera.lookAt(cameraTarget);}else{camera.up.set(0,0,1);orbit.update();}
  sun.target.position.copy(pos);sun.position.copy(pos).add(new THREE.Vector3(-70,-90,140));
 }
 if(!window.__vtxNoRender)renderer.render(scene,camera);
}animate();
