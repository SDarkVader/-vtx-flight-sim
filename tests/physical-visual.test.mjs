import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from '../public/vendor/three.module.js';
import {preparePhysicalVisual} from '../public/vtx-env/physical-visual.js';
import {VEHICLE_MODELS} from '../public/vtx-env/vehicle-registry.js';

function loadManifest(path) {
  const b=readFileSync(new URL(path,import.meta.url));
  return JSON.parse(b.subarray(20,20+b.readUInt32LE(12)).toString());
}
function sceneFromManifest(doc) {
  const nodes=doc.nodes.map(n=>{
    const o=new THREE.Object3D();o.name=n.name||'';o.userData=n.extras||{};
    if(n.translation)o.position.fromArray(n.translation);
    if(n.rotation)o.quaternion.fromArray(n.rotation);
    if(n.scale)o.scale.fromArray(n.scale);
    if(n.matrix){o.matrix.fromArray(n.matrix);o.matrix.decompose(o.position,o.quaternion,o.scale);}
    return o;
  });
  doc.nodes.forEach((n,i)=>(n.children||[]).forEach(j=>nodes[i].add(nodes[j])));
  const root=new THREE.Group();for(const i of doc.scenes[doc.scene||0].nodes)root.add(nodes[i]);
  return {root,nodes};
}
const old=sceneFromManifest(loadManifest('../public/assets/phantom-a10.glb'));
const latest=sceneFromManifest(loadManifest('../public/assets/phantom-a10-blendstra-81c823e2.glb'));
const asset=VEHICLE_MODELS['phantom-a10-81c823e2'].asset;
const root=preparePhysicalVisual(THREE,latest.root,asset,asset);
assert.equal(root.name,'airframe');assert.equal(root.userData.physical_body,'airframe');
root.updateMatrixWorld(true);old.root.updateMatrixWorld(true);
const oldJoints=new Map(old.nodes.filter(n=>n.userData.phantom_joint).map(n=>[n.userData.phantom_joint,n]));
const newJoints=latest.nodes.filter(n=>n.userData.phantom_joint);
assert.equal(newJoints.length,28);assert.equal(oldJoints.size,28);
for(const joint of newJoints){
  const prior=oldJoints.get(joint.userData.phantom_joint);assert.ok(prior,joint.name);
  assert.equal(joint.userData.joint_type,prior.userData.joint_type);
  assert.ok(Math.abs(joint.userData.q_rest-prior.userData.q_rest)<1e-5,joint.name);
  const delta=joint.getWorldPosition(new THREE.Vector3()).distanceTo(prior.getWorldPosition(new THREE.Vector3()));
  assert.ok(delta<1e-4,`${joint.name} rest position differs ${delta}m`);
}
assert.equal(preparePhysicalVisual(THREE,old.root,'other',asset),old.root);
