import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {missionDeparture} from '../public/mission-departure.js';
import {startupFrameReady} from '../public/startup-visibility.js';

// Exercise the actual start-button handler and inspect its outgoing mission,
// including a deliberately selected old position and the separate sandbox.
const source=await readFile(new URL('../public/app.js',import.meta.url),'utf8');
const start=source.indexOf("$('start').onclick=guard(async()=>{");
const end=source.indexOf("$('end').onclick",start);
assert.ok(start>=0 && end>start);
const handler=source.slice(start,end);

async function startMission({variant='phantom-a10c',environment='airport',departure=[-700,0],explicit=false,fail=false}={}){
 const els=Object.fromEntries(['start','dep','start-preset','airframe','ignore-scenery','landing-precision','pilot','scale','phantom-start','assist','drive','gear','power-limit','atmosphere-model','engine','engine-value','loading'].map(id=>[id,{value:'',checked:false}]));
 Object.assign(els.airframe,{value:variant});
 Object.assign(els['start-preset'],{options:[{value:'-700,0'},{value:'-3885,0'}]});
 Object.assign(els.pilot,{value:'manual'});Object.assign(els.scale,{value:'1'});Object.assign(els['phantom-start'],{value:'road'});
 const sent=[];
 const ctx={worldUnavailable:false,world:{runway:{x0:-3900}},departure:[...departure],departureExplicit:explicit,destination:[-50,20],currentEnvironment:environment,last:{run_id:'old'},missionTransition:null,renderer:{domElement:{style:{visibility:'visible'}}},modelReady:true,
  $:id=>els[id],guard:fn=>fn,missionDeparture,stopReplay(){},updateMarkers(){},drawMaps(){},toast(){},
  api:async(url,body)=>{sent.push({url,body});if(fail)throw Error('offline refusal');return {run_id:'offline-test'};},
  manualChannel:{postMessage(){}},manualOwned:false,track:[],command:{},dirty:false,
  selectedFuel:()=>10,selectedWind:()=>[0,0,0]};
 vm.runInNewContext(handler,ctx);
 if(fail)await assert.rejects(els.start.onclick(),/offline refusal/);else await els.start.onclick();
 return {sent,els,ctx};
}
const normal=await startMission();
assert.deepEqual(normal.sent[0].body.departure,[-3885,0]);
assert.equal(normal.els.dep.value,'-3885, 0');
assert.equal(normal.els['start-preset'].value,'-3885,0');
assert.equal(normal.ctx.renderer.domElement.style.visibility,'hidden','the old view stays hidden while the new mission starts');
assert.equal(normal.ctx.missionTransition.previousRunId,'old');
const refused=await startMission({fail:true});
assert.equal(refused.ctx.renderer.domElement.style.visibility,'visible','a refused mission returns to the previous view');
assert.equal(refused.ctx.missionTransition,null);
assert.deepEqual((await startMission({explicit:true})).sent[0].body.departure,[-700,0]);
assert.deepEqual((await startMission({departure:[205,-85],explicit:true})).sent[0].body.departure,[205,-85]);
assert.deepEqual((await startMission({environment:'sandbox'})).sent[0].body.departure,[-700,0]);
assert.deepEqual((await startMission({variant:'r6'})).sent[0].body.departure,[-700,0]);
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
