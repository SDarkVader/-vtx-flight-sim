import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {missionDeparture} from '../public/mission-departure.js';
import {startupFrameReady} from '../public/startup-visibility.js';
import {worldMatches} from '../public/world-sync.js';

// Exercise the actual start-button handler and inspect its outgoing mission,
// including a deliberately selected old position and the separate sandbox.
const source=await readFile(new URL('../public/app.js',import.meta.url),'utf8');
const start=source.indexOf("$('start').onclick=guard(async()=>{");
const end=source.indexOf("$('end').onclick",start);
assert.ok(start>=0 && end>start);
const handler=source.slice(start,end);

async function startMission({variant='phantom-a10c',environment='airport',departure=[-700,0],explicit=false,fail=false,heading='',parked=true}={}){
 const els=Object.fromEntries(['start','dep','start-preset','airframe','ignore-scenery','landing-precision','pilot','scale','phantom-start','departure-heading','assist','drive','gear','power-limit','atmosphere-model','engine','engine-value','loading','sortie-loading','view-sync'].map(id=>[id,{value:'',checked:false,hidden:true}]));
 els['view-sync'].hidden=false;
 Object.assign(els.airframe,{value:variant});
 els['departure-heading'].value=heading;
 Object.assign(els['start-preset'],{options:[{value:'-700,0'},{value:'-3885,0'}]});
 Object.assign(els.pilot,{value:'manual'});Object.assign(els.scale,{value:'1'});Object.assign(els['phantom-start'],{value:'road'});
 const sent=[],asset='/assets/parked-phantom.glb';
 const identity={id:'fixture-world',version:'33.1',seed:7,displayed_world_sha256:'a'.repeat(64)};
 const world={...identity,environment,runway:{x0:-3900}};
 const last={run_id:'old',active:false,environment:{...identity,key:environment},
  rendering_truth:{provenance:{render_asset:asset}}};
 let finish;
 const receipt=new Promise(resolve=>{finish=resolve;});
 const ctx={worldUnavailable:false,world,departure:[...departure],departureExplicit:explicit,destination:[-50,20],currentEnvironment:environment,last,
  missionTransition:null,renderedParkedAircraft:parked?{world,asset,runId:last.run_id}:null,model:{visible:parked},
  renderer:{domElement:{style:{visibility:parked?'visible':'hidden'}},render(){}},modelReady:parked,
  $:id=>els[id],guard:fn=>fn,missionDeparture,worldMatches,visualAsset:uri=>uri,stopReplay(){},updateMarkers(){},drawMaps(){},toast(){},
  api:async(url,body)=>{sent.push({url,body});await receipt;if(fail)throw Error('offline refusal');return {run_id:'offline-test'};},
  resetRotorInputs(){},manualRunId:null,manualChannel:{postMessage(){}},manualOwned:false,track:[],command:{},dirty:false,
  selectedFuel:()=>10,selectedWind:()=>[0,0,0]};
 vm.runInNewContext(handler,ctx);
 const result=els.start.onclick();
 assert.equal(els['sortie-loading'].hidden,false,'show the startup overlay during the request');
 assert.equal(els['view-sync'].hidden,true,'hide the telemetry diagnostic during the request');
 assert.equal(ctx.renderer.domElement.style.visibility,parked?'visible':'hidden');
 await els.start.onclick();
 assert.equal(sent.length,1,'a second click while pending does not start another request');
 finish();
 if(fail)await assert.rejects(result,/offline refusal/);else await result;
 return {sent,els,ctx};
}
const normal=await startMission();
assert.deepEqual(normal.sent[0].body.departure,[-3885,0]);
assert.equal(normal.els.dep.value,'-3885, 0');
assert.equal(normal.els['start-preset'].value,'-3885,0');
assert.equal(normal.ctx.renderer.domElement.style.visibility,'visible','keep a valid parked view while the new mission starts');
assert.equal(normal.ctx.missionTransition.previousRunId,'old');
assert.equal(normal.els['sortie-loading'].hidden,false,'the receipt alone does not remove the overlay');
const refused=await startMission({fail:true});
assert.equal(refused.ctx.renderer.domElement.style.visibility,'visible','a refused mission returns to the previous view');
assert.equal(refused.ctx.missionTransition,null);
assert.equal(refused.els['sortie-loading'].hidden,true);
assert.equal(refused.els['view-sync'].hidden,false);
const coldRefused=await startMission({fail:true,parked:false});
assert.equal(coldRefused.ctx.renderer.domElement.style.visibility,'hidden','a failed cold start cannot reveal an unvalidated canvas');
assert.equal(coldRefused.els['sortie-loading'].hidden,true);

// Exercise the actual animation checks around the rendering call without a live cockpit.
const frameGateStart=source.indexOf(' const matchingAircraft=',source.indexOf('function animate()'));
const frameGateEnd=source.indexOf(' if(!harbourOverviewState){',frameGateStart);
const frameShowStart=source.indexOf(' if((revealReady||keepParkedView)',frameGateEnd);
const frameShowEnd=source.indexOf(' const age=now-',frameShowStart);
assert.ok(frameGateStart>0&&frameGateEnd>frameGateStart&&frameShowStart>frameGateEnd&&frameShowEnd>frameShowStart);
const showFrame=source.slice(frameGateStart,frameGateEnd)+source.slice(frameShowStart,frameShowEnd);
const ctx=Object.assign(normal.ctx,{physicalFix:[-3885,0,0],startupFrameReady,visualOnlyOffline:false,
 requestedAsset:'/assets/parked-phantom.glb',replayFrames:null,boatViewId:null,rideEnabled:false,
 window:{},post:null,scene:{},camera:{}});
let renders=0;
ctx.renderer.render=()=>{renders++;};
const frame=()=>vm.runInNewContext('{'+showFrame+'}',ctx);
frame();
assert.equal(renders,1,'redraw the parked aircraft while still awaiting the new run');
assert.equal(normal.els['sortie-loading'].hidden,false);
ctx.last={...ctx.last,active:true,run_id:'offline-test'};
ctx.physicalFix=null;
frame();
assert.equal(renders,1,'the new run must have a physical position');
assert.equal(ctx.renderer.domElement.style.visibility,'visible','the previous frame remains visible until the same-world pose arrives');
ctx.physicalFix=[-3885,0,0];
ctx.model.visible=false;
frame();
assert.equal(renders,1,'the new run needs its matching visible asset');
assert.equal(ctx.renderer.domElement.style.visibility,'hidden');
ctx.model.visible=true;
ctx.worldUnavailable=true;
frame();
assert.equal(renders,1,'the new run needs its matching world');
ctx.worldUnavailable=false;
frame();
assert.equal(renders,2);
assert.equal(ctx.renderer.domElement.style.visibility,'visible');
assert.equal(ctx.missionTransition,null);
assert.equal(normal.els['sortie-loading'].hidden,true);
assert.equal(normal.els['view-sync'].hidden,false);
assert.deepEqual((await startMission({explicit:true})).sent[0].body.departure,[-700,0]);
assert.deepEqual((await startMission({departure:[205,-85],explicit:true})).sent[0].body.departure,[205,-85]);
assert.deepEqual((await startMission({environment:'sandbox'})).sent[0].body.departure,[-700,0]);
assert.deepEqual((await startMission({variant:'r6'})).sent[0].body.departure,[-700,0]);
assert.equal((await startMission({heading:'212.3'})).sent[0].body.departure_heading_deg,212.3);
assert.equal((await startMission({heading:'0'})).sent[0].body.departure_heading_deg,0);
assert.equal((await startMission({variant:'r6',heading:'212.3'})).sent[0].body.departure_heading_deg,undefined);
assert.equal(startupFrameReady({worldReady:true,physicalPosition:null,view:null}),false);
assert.equal(startupFrameReady({worldReady:true,physicalPosition:[-700,0,0],transition:{previousRunId:'old'},view:{active:true,run_id:'old'}}),false);
assert.equal(startupFrameReady({worldReady:true,physicalPosition:[-3885,0,0],transition:{previousRunId:'old'},view:{active:true,run_id:'new'}}),true);
assert.equal(startupFrameReady({worldReady:true,offline:true}),true);
assert.equal(startupFrameReady({worldReady:false,offline:true}),false);
const syncStart=source.indexOf(' const t=v.rendering_truth;',source.indexOf('function updateView(v)'));
const syncEnd=source.indexOf(' worldSynchronizer.reconcile();',syncStart);
assert.ok(syncStart>0 && syncEnd>syncStart && syncEnd<source.indexOf('if(v.rendering_truth?.phantom){'), 'Phantom departure synchronization runs before its branch returns');
function syncView(view){
 const elements={dep:{value:''},dest:{value:''},'start-preset':{value:'',options:[{value:'-700,0'},{value:'-3885,0'}]}};
 const ctx={v:view,inspectionDepartureSynced:false,departureExplicit:false,departure:[-700,0],destination:[-50,20],lastRun:null,$:id=>elements[id],updateMarkers(){}};
 vm.runInNewContext(source.slice(syncStart,syncEnd),ctx);
 return elements;
}
const phantomView={active:true,run_id:'new',inspection_selection_known:true,rendering_truth:{phantom:{},body_poses:{airframe:{position:[-3885,0,0]}}},mission:{departure:[-3885,0],destination:[-50,20]}};
assert.equal(syncView(phantomView).dep.value,'-3885, 0');
assert.equal(syncView(phantomView)['start-preset'].value,'-3885,0');
assert.equal(syncView({...phantomView,active:false,run_id:null,mission:null}).dep.value,'-3885, 0');
console.log('Mission start sends the extended Phantom runway threshold while retaining explicit and sandbox departures');
