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
const {heartbeatDue}=await load('phantom-controls.js');
const {cockpitToBody}=await load('tilt-direction.js');
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
