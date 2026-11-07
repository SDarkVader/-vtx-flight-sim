// Dumps the rendered world's geometry for the physics-coincidence check.
// Usage: node sample.mjs <out.json> [query]   e.g. query "&quality=low"
// Output is compared against src/vtx/world.py by coincidence_check.py.
import {spawn} from 'node:child_process';
import {writeFileSync, rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';

const [out, q=''] = process.argv.slice(2);
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9343;
const profile = join(tmpdir(),'vtx-gfx-sample-'+process.pid);
const edge = spawn(EDGE,['--headless=new',`--remote-debugging-port=${PORT}`,`--user-data-dir=${profile}`,'--no-first-run','--use-angle=d3d11','--enable-gpu','--ignore-gpu-blocklist','about:blank'],{stdio:'ignore'});
const sleep = ms=>new Promise(r=>setTimeout(r,ms));
let ver; for(let i=0;i<80;i++){try{ver=await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();break;}catch{await sleep(250);}}
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0; const pending=new Map();
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);}});
const send=(method,params={},sessionId)=>new Promise((res,rej)=>{const i=++id;pending.set(i,{res,rej});ws.send(JSON.stringify({id:i,method,params,sessionId}));});
const {targetId}=await send('Target.createTarget',{url:'about:blank'});
const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
const S=(m,p)=>send(m,p,sessionId);
await S('Runtime.enable');
await S('Emulation.setDeviceMetricsOverride',{width:1600,height:900,deviceScaleFactor:1,mobile:false});
const evaluate=async(expr)=>{const r=await S('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails).slice(0,1500));return r.result.value;};
await S('Page.navigate',{url:`http://127.0.0.1:8767/?debug${q}&cb=${Date.now()}`});
let ok=false;for(let i=0;i<240;i++){await sleep(500);try{ok=await evaluate(`!!(window.__vtx&&__vtx.model&&document.getElementById('loading').hidden&&__vtx.environment.buildings)`);}catch{}if(ok)break;}
if(!ok){console.error('page not ready');process.exit(2);}
await sleep(2000);
const data = await evaluate(`(()=>{
const V=__vtx,T=V.THREE,scene=V.scene,W=V.world;scene.updateMatrixWorld(true);
const model=V.model;const isAircraft=o=>{for(let p=o;p;p=p.parent)if(p===model)return true;return false;};
const top=o=>{let p=o,n=o.name;while(p.parent&&p.parent!==scene){p=p.parent;if(p.name)n=p.name+'/'+n;}return (p.name||p.type)+'|'+(o.name||o.type);};
const res={quality:scene.userData.quality||null};
// 1. terrain mesh
const terr=scene.getObjectByName('terrain-visual');
res.terrain={positions:Array.from(terr.geometry.attributes.position.array),index:Array.from(terr.geometry.index.array),matrix:terr.matrixWorld.elements};
// 2. raycasts at mission points (centre + 4.1 m swept footprint grid)
const skip=o=>isAircraft(o)||o.isSprite||o.isPoints||o.isLine||o.name==='sky'||(o.material&&o.material.isShaderMaterial&&o.geometry?.boundingSphere?.radius>4000)||!o.visible;
const targets=[];scene.traverseVisible(o=>{if((o.isMesh||o.isInstancedMesh)&&!skip(o))targets.push(o);});
const rc=new T.Raycaster();rc.far=1000;
const pts=${JSON.stringify([
  ['stand-1',0,0],['spawn-13.7,-28.4',13.7,-28.4],['pad-b',-50,20],['dest-45,18',-45,18],['dest-30,20',30,20],['dest-100,100',100,100],
  ['roof-hangar',85,45],['roof-workshop',150,-95],['roof-freight',-100,105],['roof-dispatch',45,110],['roof-arcade',185,45],['roof-operations',50,-145],['roof-terminal',-145,100],
  ['stand-A-40,0',40,0],['stand-70,-8',70,-8],['stand--30,-4',-30,-4],
  ['exp-stand-2',-470,285],['exp-stand-3',-340,285],['exp-stand-4',-210,285],
  ['runway-east-300',300,0],['runway-west--400',-400,0],['rwy0321-300,92',300,92],['taxi-A',-45,-36],['road-west',-72,50],['road-north',20,60],['portal',-30,43]])};
res.rays=[];
for(const [name,x,y] of pts){
  const hits=[];
  for(let dx=-4;dx<=4;dx+=2)for(let dy=-4;dy<=4;dy+=2){if(dx*dx+dy*dy>4.1*4.1+0.01)continue;
    rc.set(new T.Vector3(x+dx,y+dy,400),new T.Vector3(0,0,-1));
    const h=rc.intersectObjects(targets,false)[0];
    hits.push({dx,dy,z:h?h.point.z:null,obj:h?top(h.object):null});}
  res.rays.push({name,x,y,hits});
}
// 3. building shells vs collider boxes: all non-instanced meshes near each box
const boxes=W.obstacles.filter(o=>o.kind!=='cylinder');res.boxes=[];
const meshes=[];scene.traverse(o=>{if(o.isMesh&&!o.isInstancedMesh&&!isAircraft(o)&&o.name!=='terrain-visual'&&o.name!=='distant-hills'){o.geometry.computeBoundingBox&&o.geometry.computeBoundingBox();meshes.push(o);}});
const bb=new T.Box3();
for(const b of boxes){const lo=[b.center[0]-b.half[0],b.center[1]-b.half[1],b.center[2]-b.half[2]],hi=[b.center[0]+b.half[0],b.center[1]+b.half[1],b.center[2]+b.half[2]];
  const near=[];
  for(const m of meshes){bb.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld);
    if(bb.max.x<lo[0]-3||bb.min.x>hi[0]+3||bb.max.y<lo[1]-3||bb.min.y>hi[1]+3||bb.max.z<0.25||bb.min.z>hi[2]+12)continue;
    const prot=Math.max(lo[0]-bb.min.x,bb.max.x-hi[0],lo[1]-bb.min.y,bb.max.y-hi[1],bb.max.z-hi[2]);
    near.push({obj:top(m),min:[bb.min.x,bb.min.y,bb.min.z],max:[bb.max.x,bb.max.y,bb.max.z],prot:+prot.toFixed(4),visible:m.visible});}
  res.boxes.push({id:b.id,lo,hi,near});}
// 4. trees: world-space vertices of every instance in vtx-trees vs cylinders
const trees=W.obstacles.filter(o=>o.kind==='cylinder');res.trees=[];
const tg=scene.getObjectByName('vtx-trees');const m4=new T.Matrix4(),v=new T.Vector3();
tg&&tg.traverse(o=>{if(!o.isInstancedMesh)return;const p=o.geometry.attributes.position;
  for(let i=0;i<o.count;i++){o.getMatrixAt(i,m4);m4.premultiply(o.matrixWorld);let cx=0,cy=0,best=null,bd=1e9;
    v.set(0,0,0).applyMatrix4(m4);for(const t of trees){const d=Math.hypot(t.center[0]-v.x,t.center[1]-v.y);if(d<bd){bd=d;best=t;}}
    let maxR=0,maxZ=-1e9,minZ=1e9;for(let k=0;k<p.count;k++){v.fromBufferAttribute(p,k).applyMatrix4(m4);maxR=Math.max(maxR,Math.hypot(v.x-best.center[0],v.y-best.center[1]));maxZ=Math.max(maxZ,v.z);minZ=Math.min(minZ,v.z);}
    res.trees.push({mesh:o.name||o.geometry.type,i,tree:best.id,offset:bd,maxR,radius:best.half[0],maxZ,minZ,top:best.center[2]+best.half[2]});}});
// 5. painted / draped vertices (airfield + service roads + water), sampled
res.paint=[];const groups=['vtx-airfield','vtx-service-roads','water'];
for(const gname of groups){const g=scene.getObjectByName(gname);if(!g)continue;
  g.traverse(o=>{if(!o.isMesh||!o.visible)return;const mat=Array.isArray(o.material)?o.material[0]:o.material;
    const p=o.geometry.attributes.position;if(!p)return;o.geometry.computeBoundingBox();const ext=o.geometry.boundingBox;
    const flat=(ext.max.z-ext.min.z)<0.6||o.name==='water'||o.isInstancedMesh;if(!flat)return;
    const step=Math.max(1,Math.floor(p.count/400));
    if(o.isInstancedMesh){for(let i=0;i<o.count;i+=Math.max(1,Math.floor(o.count/200))){o.getMatrixAt(i,m4);m4.premultiply(o.matrixWorld);v.set(0,0,0).applyMatrix4(m4);res.paint.push([gname,o.name||'inst',v.x,v.y,v.z,mat.depthTest?1:0]);}return;}
    for(let k=0;k<p.count;k+=step){v.fromBufferAttribute(p,k).applyMatrix4(o.matrixWorld);res.paint.push([gname,o.name||mat.type,v.x,v.y,v.z,mat.depthTest?1:0]);}});}
// 6. inventory of raised visual objects inside the physics area that are not inside any collider
res.inventory=[];const inBox=(b,x,y,z,pad)=>x>=b.center[0]-b.half[0]-pad&&x<=b.center[0]+b.half[0]+pad&&y>=b.center[1]-b.half[1]-pad&&y<=b.center[1]+b.half[1]+pad&&z<=b.center[2]+b.half[2]+pad;
const allColl=W.obstacles;
scene.traverse(o=>{if(!(o.isMesh)||o.isInstancedMesh||isAircraft(o)||!o.visible)return;let vis=true;for(let p=o;p;p=p.parent)if(!p.visible)vis=false;if(!vis)return;
  const n=o.name;if(n==='terrain-visual'||n==='distant-hills'||n==='water')return;
  bb.copy(o.geometry.boundingBox||(o.geometry.computeBoundingBox(),o.geometry.boundingBox)).applyMatrix4(o.matrixWorld);
  if(bb.max.x<-500||bb.min.x>500||bb.max.y<-500||bb.min.y>500)return;if(bb.max.z-bb.min.z<0.3&&bb.max.z<0.6)return;
  const c=bb.getCenter(new T.Vector3());if(allColl.some(b=>b.kind!=='cylinder'&&inBox(b,c.x,c.y,bb.max.z,0.81)))return;
  if(bb.max.x-bb.min.x>2000)return;
  res.inventory.push({obj:top(o),min:[+bb.min.x.toFixed(2),+bb.min.y.toFixed(2),+bb.min.z.toFixed(2)],max:[+bb.max.x.toFixed(2),+bb.max.y.toFixed(2),+bb.max.z.toFixed(2)]});});
// 7. local lights in scene
res.lights=[];scene.traverse(o=>{if(o.isLight)res.lights.push({type:o.type,name:o.name,visible:o.visible,intensity:o.intensity,pos:o.getWorldPosition(new T.Vector3()).toArray().map(x=>+x.toFixed(2))});});
// 8. follow-me cab route samples (vehicle positions over time)
res.vehicles=[];const sr=V.environment.serviceRoads;
if(sr&&sr.update){let t=5000;for(let k=0;k<9000;k++){t+=0.1;sr.update(t,null);if(k%15)continue;for(const nm of ['vtx-gsv-follow-me-cab','vtx-gsv-baggage-train','vtx-gsv-fuel-bowser','vtx-gsv-fire-crash-tender','vtx-gsv-pushback-tug']){const g=scene.getObjectByName(nm);if(!g)continue;g.updateMatrixWorld(true);const b=new T.Box3().setFromObject(g);res.vehicles.push([nm,k*0.1,b.min.x,b.min.y,b.min.z,b.max.x,b.max.y,b.max.z,g.visible?1:0]);}}}
return res;})()`);
writeFileSync(out,JSON.stringify(data));
console.log('wrote',out,'quality',data.quality,'paint',data.paint.length,'inventory',data.inventory.length);
await send('Browser.close').catch(()=>{});edge.kill();await sleep(800);try{rmSync(profile,{recursive:true,force:true});}catch{}
process.exit(0);
