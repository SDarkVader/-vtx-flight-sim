import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {visualPhantomTargets} from '../public/vtx-env/visual-phantom-targets.js';
// Read real A10 glTF authored joint metadata rather than invented test joints.
const file=readFileSync(new URL('../public/assets/phantom-a10.glb',import.meta.url));
assert.equal(file.readUInt32LE(0),0x46546c67,'expected binary glTF');
assert.equal(file.readUInt32LE(16),0x4e4f534a,'expected JSON chunk');
const gltf=JSON.parse(file.subarray(20,20+file.readUInt32LE(12)).toString());
const joints=gltf.nodes.filter(n=>n.extras?.phantom_joint).map(n=>({
 name:n.extras.phantom_joint,q0:n.extras.q_rest,type:n.extras.joint_type
}));
assert.equal(joints.length,28,'A10 exported joints unexpectedly changed');
const rig={joints},duration=83;
const sample=(time,bank=0)=>visualPhantomTargets(rig,{time},{bank,duration});
const start=sample(0),unlocked=sample(3.5),extended=sample(13.5),locked=sample(16);
assert.ok(joints.some(j=>j.name.startsWith('wing_')&&j.q0!==0),'missing wing slides');
assert.ok(joints.some(j=>j.name.startsWith('pin_')&&j.q0!==0),'missing locking pins');
assert.ok(joints.some(j=>j.name.endsWith('_fold')&&j.q0!==0),'missing canard folds');
assert.ok(joints.some(j=>j.name.startsWith('hatch_')&&j.q0!==0),'missing wing hatches');
for(const joint of joints){
 const n=joint.name,q=joint.q0;
 if(n.startsWith('wing_')||n.startsWith('hatch_')||n.startsWith('pin_')||n.endsWith('_fold')){
  assert.ok(Math.abs(start.joints[n]-q)<1e-8,n+' jumps at runway start');
  assert.ok(Math.abs(locked.joints[n])<1e-8,n+' fails to deploy before takeoff');
 }
 if(n.startsWith('wing_')||n.endsWith('_fold')){
  assert.ok(Math.abs(unlocked.joints[n]-q)<1e-8,n+' starts before hatch clears');
  assert.ok(Math.abs(extended.joints[n])<1e-8,n+' fails to extend');
 }
 if(n.startsWith('pin_')){
  assert.ok(Math.abs(extended.joints[n]-q)<1e-8,n+' locks before full wing travel');
 }
}
// All active joints must remain within their staged authored endpoints,
// with no steps at any phase boundary, including takeoff and final landing.
for(let t=0;t<=duration;t+=.025){
 const curr=sample(t),next=sample(Math.min(duration,t+.025));
 for(const j of joints){
  const a=curr.joints[j.name],b=next.joints[j.name];
  if(a===undefined)continue;
  assert.ok(Number.isFinite(a)&&Number.isFinite(b),j.name+' nonfinite');
  assert.ok(Math.abs(a-b)<.055,j.name+' snaps at t='+t.toFixed(3));
  if(j.name.startsWith('wing_')||j.name.startsWith('pin_')||j.name.startsWith('hatch_')||j.name.endsWith('_fold'))
   assert.ok(a>=Math.min(0,j.q0)-1e-8&&a<=Math.max(0,j.q0)+1e-8,j.name+' overshoots authored travel');
 }
}
const takeoff=sample(14),cruise=sample(35),approach=sample(65),landed=sample(duration);
for(const j of joints.filter(j=>j.name.startsWith('flap_'))){
 assert.ok(takeoff.joints[j.name]>.15,'flaps must deflect during departure');
 assert.ok(Math.abs(cruise.joints[j.name])<1e-8,'flaps remain extended during cruise');
 assert.ok(approach.joints[j.name]>.15,'flaps fail to deploy for approach');
 assert.ok(Math.abs(landed.joints[j.name])<1e-8,'flaps remain down after stop');
}
for(const j of joints.filter(j=>j.name.startsWith('wing_'))){
 assert.ok(Math.abs(landed.joints[j.name])<1e-8,'wing unexpectedly retracts at landing');
}
assert.ok(Math.abs(sample(35,.45).joints.aileron_left)<.16,'aileron travel exceeded bounds');
assert.ok(sample(35,.45).joints.aileron_left<0&&sample(35,.45).joints.aileron_right>0,
 'left/right ailerons must move oppositely during an aircraft bank');
assert.ok(Math.abs(sample(35,.45).joints.aileron_left+sample(35,.45).joints.aileron_right)<1e-8,
 'aileron commands must remain symmetric');
assert.deepEqual(sample(35).joints,sample(35).joints,'joint animation is not deterministic');
console.log('A10 28-joint staged hatch/wing/canard/pin/flap/aileron animation passed');
