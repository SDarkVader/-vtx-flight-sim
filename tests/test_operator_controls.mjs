// Regressions: flight campaign D-1 (Phantom panel must not take control silently) and
// audit F14 (cockpit keyboard left/right). Pure functions only; no server, no DOM.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
// Browser modules are loaded as data: URLs (no package.json marks public/*.js as ES modules). A data: module cannot
// resolve relative imports, so inline them the same way, recursively (phantom-controls.js imports voice-pilot.js).
const dataUrl=async f=>{
  let src=await readFile(new URL('../public/'+f,import.meta.url),'utf8');
  for(const m of [...src.matchAll(/from '\.\/([\w\-\/]+\.js)(?:\?[^']*)?'/g)])src=src.replace(m[0],`from '${await dataUrl(m[1])}'`);
  return 'data:text/javascript;base64,'+Buffer.from(src).toString('base64');
};
const load=async f=>import(await dataUrl(f));
const {heartbeatDue,heldControlToggles}=await load('phantom-controls.js');
const {cockpitToBody}=await load('tilt-direction.js');
const {createPatchQueue,editArrayCommand}=await load('phantom-command-queue.js');
const {renderReadout}=await load('phantom-readouts.js');
const view={active:true,paused:false,authority:'manual',run_id:'r1'};

test('an open panel that the operator never touched sends nothing',()=>{
  for(let beat=0;beat<50;beat++)assert.equal(heartbeatDue({engaged:false,pending:false,view,dirty:true,beat,engagedRun:'r1'}),false);
});
test('an engaged panel sends changes only for its own run and manual authority',()=>{
  assert.equal(heartbeatDue({engaged:true,pending:false,view,dirty:true,beat:1,engagedRun:'r1'}),true);
  assert.equal(heartbeatDue({engaged:true,pending:false,view,dirty:false,beat:10,engagedRun:'r1'}),false);
  assert.equal(heartbeatDue({engaged:true,pending:false,view,dirty:false,beat:3,engagedRun:'r1'}),false);
  assert.equal(heartbeatDue({engaged:true,pending:false,view:{...view,run_id:'r2'},dirty:true,beat:1,engagedRun:'r1'}),false);
  assert.equal(heartbeatDue({engaged:true,pending:false,view:{...view,authority:'colin'},dirty:true,beat:1,engagedRun:'r1'}),false);
});
test('cockpit ArrowRight tilts toward the pilot right (-X) at zero cabin yaw',()=>{
  const [x,y]=cockpitToBody(0,1,0);assert.ok(Math.abs(x)<1e-12&&Math.abs(y+1)<1e-12);
  const [fx,fy]=cockpitToBody(1,0,0);assert.ok(Math.abs(fx-1)<1e-12&&Math.abs(fy)<1e-12);
  const [rx,ry]=cockpitToBody(0,1,90);assert.ok(Math.abs(rx-1)<1e-12&&Math.abs(ry)<1e-12);
});

test('operator sends only changed fields and holds the other side of an array',()=>{
  const queue=createPatchQueue(), held=[12,23];
  const changed=editArrayCommand(undefined,held,0,8,2);
  queue.add({flap_deg:changed});
  assert.deepEqual(queue.take().patch,{flap_deg:[8,23]});
  assert.deepEqual(held,[12,23]);
  queue.add({yaw:.3});
  assert.deepEqual(queue.take().patch,{yaw:.3});
  assert.equal(queue.dirty,false);
});

test('in-flight failure preserves newer edits and cannot resurrect after disengagement',()=>{
  const queue=createPatchQueue();
  queue.add({flap_deg:[8,23],yaw:.1});
  const first=queue.take();
  queue.add({yaw:.4,engine:.7});
  queue.retry(first);
  assert.deepEqual(queue.take().patch,{flap_deg:[8,23],yaw:.4,engine:.7});
  queue.add({yaw:.5});
  const oldRun=queue.take();
  queue.clear(); // run or authority changes disengage the panel
  queue.add({collective:.2});
  queue.retry(oldRun);
  assert.deepEqual(queue.take().patch,{collective:.2});
});

test('readouts clear unavailable values and distinguish zero from missing',()=>{
  const meter={tagName:'METER',hidden:false,value:7};
  const output={tagName:'OUTPUT',textContent:'7.00'};
  renderReadout(meter,null,{unit:' m'});renderReadout(output,null,{unit:' m'});
  assert.equal(meter.hidden,true);assert.equal(output.textContent,'—');
  renderReadout(meter,0,{unit:' m'});renderReadout(output,0,{unit:' m'});
  assert.equal(meter.hidden,false);assert.equal(meter.value,0);assert.equal(output.textContent,'0.00 m');
});

test('restored held commands determine toggle actions without sending new commands',()=>{
  const command={wing:'deploy',canard_fold:'deployed',brake:[1,1,1,1],pod_tilt_deg:[0,0,0,0],leg_extension_m:[.52,.52,.52,.52]};
  const before=structuredClone(command),state=heldControlToggles(command);
  assert.deepEqual(state.wing,{value:true,label:'Wing stow'});
  assert.deepEqual(state.can,{value:true,label:'Canards fold'});
  assert.deepEqual(state.brakes,{value:true,label:'Brakes on'});
  assert.deepEqual(state.vtol,{value:false,label:'Pods / wheels: 0°'});
  assert.deepEqual(state.legsExtended,{value:true,label:'Legs: extended'});
  assert.deepEqual(command,before);
  assert.deepEqual(heldControlToggles({wing:'stow',canard_fold:'folded'}),{
    wing:{value:false,label:'Wing deploy'},can:{value:false,label:'Canards deploy'}});
});

test('unacknowledged edits and unavailable commands cannot be replaced by an old snapshot',()=>{
  const state=heldControlToggles({wing:'stow',brake:[0,0,0,0],pod_tilt_deg:[90,90,90,90]},new Set(['wing','brake']));
  assert.equal(state.wing,undefined);assert.equal(state.brakes,undefined);
  assert.deepEqual(state.vtol,{value:true,label:'Pods / wheels: 90°'});
  assert.deepEqual(heldControlToggles({wing:'unknown',brake:[NaN,1,1,1]}),{});
  assert.equal(heldControlToggles({brake:[0,1,0,1]}).brakes.label,'Brakes mixed');
});
