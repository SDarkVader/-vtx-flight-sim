// Reproducible visual capture for the VTX world (graphics work, 2026-11-03).
// Usage: node capture.mjs <outDir> <label> [configs]
//   configs: comma list of desktop, phone, lite, low, medium, high
//   (desktop/phone use the page's default tier for that device).
// Drives headless Edge through CDP; the page must be served on 127.0.0.1:8767.
// Set VTX_SWIFTSHADER=1 to force the software rasteriser.
import {spawn} from 'node:child_process';
import {mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';

const [outDir, label, cfgArg='desktop,phone,lite'] = process.argv.slice(2);
const BASE = 'http://127.0.0.1:8767/';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9341;
const CONFIGS = {
  desktop:{w:1600,h:900,dpr:1,mobile:false,q:''},
  lite:{w:1600,h:900,dpr:1,mobile:false,q:'&lite'},
  low:{w:1600,h:900,dpr:1,mobile:false,q:'&quality=low'},
  medium:{w:1600,h:900,dpr:1,mobile:false,q:'&quality=medium'},
  high:{w:1600,h:900,dpr:1,mobile:false,q:'&quality=high'},
  phone:{w:390,h:844,dpr:3,mobile:true,q:''},
};
const VIEWS = [
  ['chase-stand1',[9,-11,8.8],[0,0,2.2]],
  ['apron-hangar',[-25,-40,14],[85,45,6]],
  ['runway-grazing-east',[-120,-8,3.5],[220,0,0]],
  ['overview-sw',[-260,-430,170],[0,60,0]],
  ['pad-b',[-36,4,10],[-50,20,0.5]],
  ['dispatch-tower',[10,55,22],[80,112,14]],
  ['trees-south',[60,-120,9],[140,-170,4]],
  ['top-stand1',[0,-0.01,140],[0,0,0]],
  ['stands-north',[-60,180,40],[40,300,10]],
  ['water-west',[-200,-40,20],[-265,30,20]],
];
const only = process.env.VTX_VIEWS ? process.env.VTX_VIEWS.split(',') : null;
mkdirSync(outDir,{recursive:true});
const profile = join(tmpdir(),'vtx-gfx-edge-'+process.pid);
const gpuFlags = process.env.VTX_SWIFTSHADER ? ['--use-angle=swiftshader','--enable-unsafe-swiftshader'] : ['--use-angle=d3d11','--enable-gpu','--ignore-gpu-blocklist'];
const edge = spawn(EDGE,['--headless=new',`--remote-debugging-port=${PORT}`,`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows',...gpuFlags,'about:blank'],{stdio:'ignore'});
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
await S('Page.enable');await S('Runtime.enable');
const evaluate=async(expr)=>{const r=await S('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails).slice(0,1200));return r.result.value;};
const results={label,date:new Date().toISOString(),configs:{}};
for(const name of cfgArg.split(',')){
  const c=CONFIGS[name];
  await S('Emulation.setDeviceMetricsOverride',{width:c.w,height:c.h,deviceScaleFactor:c.dpr,mobile:c.mobile});
  await S('Emulation.setTouchEmulationEnabled',{enabled:c.mobile,maxTouchPoints:c.mobile?5:1});
  await S('Emulation.setUserAgentOverride',{userAgent:c.mobile?'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0'});
  await S('Page.navigate',{url:'about:blank'});await sleep(3000);
  await S('Page.navigate',{url:`${BASE}?debug${c.q}${process.env.VTX_EXTRA_Q||""}&cb=${Date.now()}`});
  let ok=false;
  for(let i=0;i<240;i++){await sleep(500);if(i===60||i===120){await S('Page.reload',{ignoreCache:true});}try{ok=await evaluate(`!!(window.__vtx&&__vtx.model&&document.getElementById('loading').hidden&&__vtx.environment.buildings)`);}catch{}if(ok)break;}
  if(!ok){let diag='';try{diag=await evaluate(`JSON.stringify({vtx:!!window.__vtx,model:!!window.__vtx?.model,loading:document.getElementById('loading')?.hidden,loadingText:document.getElementById('loading')?.textContent,b:!!window.__vtx?.environment?.buildings,sync:document.getElementById('view-sync')?.textContent})`);}catch(e){diag=String(e);}console.error('page not ready for',name,diag);continue;}
  await sleep(2500);
  const gpu=await evaluate(`(()=>{const gl=__vtx.renderer.getContext();const e=gl.getExtension('WEBGL_debug_renderer_info');return e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);})()`);
  const cfgRes={viewport:[c.w,c.h,c.dpr],gpu,quality:await evaluate(`__vtx.scene.userData.quality||'(none)'`),pixelRatio:await evaluate(`__vtx.renderer.getPixelRatio()`),antialias:await evaluate(`__vtx.renderer.getContext().getContextAttributes().antialias`),shadows:await evaluate(`__vtx.renderer.shadowMap.enabled`),views:{}};
  for(const [vn,p,t] of VIEWS){
    if(only&&!only.includes(vn))continue;
    const r=await evaluate(`(async()=>{const V=__vtx,T=V.THREE;window.__vtxNoRender=true;
      await new Promise(r=>setTimeout(r,200));
      const cam=V.camera;cam.up.set(0,0,1);cam.position.set(${p});cam.lookAt(new T.Vector3(${t}));cam.updateMatrixWorld();
      const ap=new T.Vector3(0,0,1.5);if(V.model){const b=new T.Box3().setFromObject(V.model);if(!b.isEmpty())b.getCenter(ap);}
      V.sky.follow&&V.sky.follow(ap);V.sky.update(cam,1000);V.environment.buildings?.update(1000);V.environment.volcano?.update(1000);V.environment.serviceRoads?.update(1000,null);
      cam.position.set(${p});cam.up.set(0,0,1);cam.lookAt(new T.Vector3(${t}));cam.updateMatrixWorld();
      const R=V.renderer,gl=R.getContext(),px=new Uint8Array(4);
      for(let i=0;i<5;i++){R.render(V.scene,cam);gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);}
      const times=[];for(let i=0;i<30;i++){const t0=performance.now();R.render(V.scene,cam);gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);times.push(performance.now()-t0);}
      times.sort((a,b)=>a-b);
      R.render(V.scene,cam);const info={calls:R.info.render.calls,triangles:R.info.render.triangles,points:R.info.render.points,lines:R.info.render.lines,geometries:R.info.memory.geometries,textures:R.info.memory.textures,programs:R.info.programs?.length};
      const img=R.domElement.toDataURL('image/jpeg',0.88);
      return {info,median_ms:+times[15].toFixed(2),p90_ms:+times[27].toFixed(2),img};})()`);
    writeFileSync(join(outDir,`${label}_${name}_${vn}.jpg`),Buffer.from(r.img.split(',')[1],'base64'));
    delete r.img; cfgRes.views[vn]=r;
    console.log(label,name,vn,JSON.stringify(r));
  }
  results.configs[name]=cfgRes;
}
writeFileSync(join(outDir,`${label}_perf.json`),JSON.stringify(results,null,1));
await send('Browser.close').catch(()=>{});
edge.kill();await sleep(800);try{rmSync(profile,{recursive:true,force:true});}catch{}
process.exit(0);
