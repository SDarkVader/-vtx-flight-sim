import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const threeUrl = new URL('../public/vendor/three.module.js', import.meta.url).href;
const THREE = await import(threeUrl);
const source = (await readFile(new URL('../public/suspension-schematic.js', import.meta.url), 'utf8')).replace("from 'three'", `from '${threeUrl}'`);
const {attachSuspensionSchematic, updateSuspensionSchematic, createSuspensionSchematic, suspensionSchematicDescriptor} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

const descriptor = {schema:1, asset:'/assets/phantom-a10c-suspension-schematic.glb', sha256:'a'.repeat(64)};
function truth() {
  return {variant:'phantom-a10c-runway-20261112', config_sha256:'2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f',
    provenance:{flight_revision:{suspension_schematic:{...descriptor}}},
    body_poses:{airframe:{position:[12,5,3],quaternion_wxyz:[1,0,0,0]},
      pod_FL:{position:[13.54,6.25,3.61],quaternion_wxyz:[1,0,0,0]},
      pod_FR:{position:[13.54,3.75,3.61],quaternion_wxyz:[1,0,0,0]},
      pod_FL_wheel:{position:[13.54,6.25,3.40895]},pod_FR_wheel:{position:[13.54,3.75,3.408987]}},
    phantom:{nose_lift_m:.2,joints:{pod_FL_susp:-.20105,pod_FR_susp:-.201013}}};
}
function parts() {
  const root = new THREE.Group(); root.name='VTX_A10C_SUSPENSION_SCHEMATIC';
  for (const side of ['FL','FR']) {
    const pod = new THREE.Group(); pod.name=`VTX_SCHEMATIC_${side}_POD`;pod.userData.schematic=true;
    const carrier = new THREE.Group(); carrier.name=`VTX_SCHEMATIC_${side}_CARRIER`;carrier.userData={schematic:true,source_joint:`pod_${side}_susp`};
    const connector = new THREE.Group(); connector.name=`VTX_SCHEMATIC_${side}_CONNECTOR`;connector.position.set(.12,side==='FL'?.127:-.127,0);
    pod.add(carrier,connector);root.add(pod);
  }
  return root;
}
function model() {const root=new THREE.Group(),airframe=new THREE.Group();airframe.name='airframe';root.add(airframe);return root;}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('schematic follows measured front slides and pod frames while spring-seat setting changes independently', () => {
  const rig=attachSuspensionSchematic(parts(),new THREE.Group()), t=truth();
  updateSuspensionSchematic(rig,t);
  assert.equal(rig.root.visible,true);
  for (const c of rig.corners) {
    assert.ok(c.pod.position.distanceTo(new THREE.Vector3(1.54,c.side==='FL'?1.25:-1.25,.61))<1e-12);
    assert.ok(Math.abs(c.carrier.position.z-t.phantom.joints[`pod_${c.side}_susp`])<1e-12);
    assert.equal(c.connector.position.z,c.carrier.position.z);
    assert.equal(c.connector.scale.z,-c.carrier.position.z);
  }
  const before=rig.corners.map(c=>c.carrier.position.z);t.phantom.nose_lift_m=0;
  updateSuspensionSchematic(rig,t);
  assert.deepEqual(rig.corners.map(c=>c.carrier.position.z),before);
});

test('rotated aircraft and tilted pod retain physical coordinate frames and +Z bump direction', () => {
  const rig=attachSuspensionSchematic(parts(),new THREE.Group()),t=truth();
  const yaw=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),Math.PI/2);
  const tilt=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),Math.PI/2);
  t.body_poses.airframe.quaternion_wxyz=[yaw.w,yaw.x,yaw.y,yaw.z];
  for(const c of rig.corners){const local=new THREE.Vector3(1.54,c.side==='FL'?1.25:-1.25,.61).applyQuaternion(yaw).add(new THREE.Vector3(12,5,3));const q=yaw.clone().multiply(tilt);
    t.body_poses[`pod_${c.side}`]={position:local.toArray(),quaternion_wxyz:[q.w,q.x,q.y,q.z]};t.body_poses[`pod_${c.side}_wheel`]={position:new THREE.Vector3(0,0,.04).applyQuaternion(q).add(local).toArray()};t.phantom.joints[`pod_${c.side}_susp`]=.04;}
  updateSuspensionSchematic(rig,t);
  for(const c of rig.corners){assert.ok(c.pod.quaternion.angleTo(tilt)<1e-7);assert.ok(Math.abs(c.carrier.position.z-.04)<1e-12);assert.equal(c.connector.position.z,0);}
});

test('missing and nonfinite measured state hides affected presentation and recovers without a fabricated value', () => {
  const rig=attachSuspensionSchematic(parts(),new THREE.Group()),t=truth();updateSuspensionSchematic(rig,t);
  t.phantom.joints.pod_FL_susp=NaN;updateSuspensionSchematic(rig,t);
  assert.equal(rig.corners[0].pod.visible,false);assert.equal(rig.corners[0].measured_slide_m,null);assert.equal(rig.status,'partially-unavailable');
  t.phantom.joints.pod_FL_susp=-.1;t.body_poses.pod_FL_wheel.position[2]=3.51;updateSuspensionSchematic(rig,t);assert.equal(rig.corners[0].pod.visible,true);assert.ok(Math.abs(rig.corners[0].carrier.position.z+.1)<1e-12);
  delete t.body_poses.airframe;updateSuspensionSchematic(rig,t);assert.equal(rig.root.visible,false);
});

test('historical or incompatible snapshots never acquire an added schematic', () => {
  for(const change of [t=>delete t.provenance.flight_revision.suspension_schematic,t=>t.variant='phantom-a10c',t=>t.config_sha256='0'.repeat(64),t=>t.provenance.flight_revision.suspension_schematic.sha256='wrong']){
    const t=truth();change(t);assert.equal(suspensionSchematicDescriptor(t),null);
  }
});

test('recorded body-pose displacement stays aligned when the measured joint belongs to a later solver step', () => {
  const airframe=new THREE.Group(),rig=attachSuspensionSchematic(parts(),airframe),t=truth();
  t.body_poses.airframe={position:[-700.00326,-.0001,.04504],quaternion_wxyz:[.999485,.000007,-.03208,.000007]};
  t.body_poses.pod_FL={position:[-698.50557,1.24991,.75256],quaternion_wxyz:[.999485,.000059,-.03208,.000008]};
  t.body_poses.pod_FL_wheel={position:[-698.49267,1.24993,.55189]};
  const a=t.body_poses.airframe.quaternion_wxyz;airframe.position.fromArray(t.body_poses.airframe.position);airframe.quaternion.set(a[1],a[2],a[3],a[0]).normalize();
  updateSuspensionSchematic(rig,t);airframe.updateMatrixWorld(true);
  const corner=rig.corners[0],before=corner.carrier.position.z;
  assert.equal(corner.pod.visible,true);
  assert.ok(corner.carrier.getWorldPosition(new THREE.Vector3()).distanceTo(new THREE.Vector3().fromArray(t.body_poses.pod_FL_wheel.position))<.0002);
  t.phantom.joints.pod_FL_susp=-.18;updateSuspensionSchematic(rig,t);
  assert.equal(corner.carrier.position.z,before);assert.equal(corner.joint_slide_m,-.18);
});

test('generated asset exposes the same measured-pose binding contract', async () => {
  const bytes=await readFile(new URL('../public/assets/phantom-a10c-suspension-schematic.glb',import.meta.url));
  const doc=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
  const groups=doc.nodes.map(n=>{const g=new THREE.Group();g.name=n.name||'';g.userData=n.extras||{};if(n.translation)g.position.fromArray(n.translation);if(n.rotation)g.quaternion.fromArray(n.rotation);if(n.scale)g.scale.fromArray(n.scale);return g;});
  doc.nodes.forEach((n,i)=>{for(const c of n.children||[])groups[i].add(groups[c]);});
  const root=groups.find(n=>n.name==='VTX_A10C_SUSPENSION_SCHEMATIC'),rig=attachSuspensionSchematic(root,new THREE.Group());
  assert.equal(rig.status,'attached');updateSuspensionSchematic(rig,truth());assert.equal(rig.root.visible,true);
  for(const c of rig.corners){assert.equal(c.pod.userData.source_body,`pod_${c.side}`);assert.ok(c.connector.scale.z>0);assert.equal(c.carrier.userData.q_rest,0);}
});

test('late asset loads are discarded when aircraft changes or descriptor is removed', async () => {
  const deferred=[],disposed=[];const controller=createSuspensionSchematic({loadAsset:()=>new Promise(resolve=>deferred.push(resolve)),dispose:root=>disposed.push(root)});
  const first=model(),second=model(),t=truth();controller.update(first,t);await settle();
  controller.update(second,t);await settle();const old=parts();deferred[0](old);await settle();assert.equal(old.parent,null);assert.ok(disposed.includes(old));
  const current=parts();deferred[1](current);await settle();controller.update(second,t);assert.equal(current.parent,second.getObjectByName('airframe'));assert.equal(current.visible,true);
  const historical=truth();delete historical.provenance.flight_revision.suspension_schematic;controller.update(second,historical);
  assert.equal(current.parent,null);assert.ok(disposed.includes(current));assert.equal(controller.status.status,'not-selected');
});

test('asset verification failures stay explicit without replacing the aircraft', async () => {
  const physical=model();const controller=createSuspensionSchematic({loadAsset:async()=>{throw Error('hash mismatch');},dispose:()=>{}});
  controller.update(physical,truth());await settle();assert.deepEqual(controller.status,{status:'unavailable',reason:'hash mismatch'});assert.equal(physical.children.length,1);
});
