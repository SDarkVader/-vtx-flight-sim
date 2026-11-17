import * as THREE from '../public/vendor/three.module.js';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {setCockpitVisibility} from '../public/cockpit-visibility.js';
const rootPath=new URL('../',import.meta.url);
const b=readFileSync(new URL('public/assets/phantom-a10b-visual.glb',rootPath)),n=b.readUInt32LE(12),j=JSON.parse(b.subarray(20,20+n)),bin=b.subarray(28+n);
const components={5121:Uint8Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array},sizes={SCALAR:1,VEC2:2,VEC3:3,VEC4:4};
function accessor(id){const a=j.accessors[id],v=j.bufferViews[a.bufferView],T=components[a.componentType];return new T(bin.buffer,bin.byteOffset+(v.byteOffset||0)+(a.byteOffset||0),a.count*sizes[a.type]);}
const nodes=j.nodes.map(spec=>{
 const node=new THREE.Group();node.name=spec.name||'';node.userData=spec.extras||{};
 if(spec.matrix){node.matrix.fromArray(spec.matrix);node.matrix.decompose(node.position,node.quaternion,node.scale);}else{if(spec.translation)node.position.fromArray(spec.translation);if(spec.rotation)node.quaternion.fromArray(spec.rotation);if(spec.scale)node.scale.fromArray(spec.scale);}
 if(spec.mesh!==undefined)for(const p of j.meshes[spec.mesh].primitives){
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(accessor(p.attributes.POSITION),3));if(p.indices!==undefined)geometry.setIndex(new THREE.BufferAttribute(accessor(p.indices),1));
  const material=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});material.name=j.materials[p.material]?.name||'';
  const mesh=new THREE.Mesh(geometry,material);mesh.name=spec.name||'';mesh.userData={...(spec.extras||{})};node.add(mesh);
 }
 return node;
});
j.nodes.forEach((s,i)=>s.children?.forEach(c=>nodes[i].add(nodes[c])));
const scene=new THREE.Group();j.scenes[j.scene||0].nodes.forEach(id=>scene.add(nodes[id]));setCockpitVisibility(scene,true);scene.updateMatrixWorld(true);
const origin=new THREE.Vector3(.25,-.20,.85);
const transforms=nodes.map(node=>node.matrix.toArray());
for(const degrees of [-90,-75,0,12,25,75,90]){
 const r=degrees*Math.PI/180,ray=new THREE.Raycaster(origin,new THREE.Vector3(Math.cos(r),Math.sin(r),0),.001,1.2);
 const hits=ray.intersectObject(scene,true).filter(h=>h.object.visible);
 assert.equal(hits.length,0,`cockpit sightline ${degrees} degrees must clear the opaque inner hull and side glazing`);
}
const hidden=[];scene.traverse(node=>{if(node.isMesh&&!node.visible)hidden.push(node);});assert.ok(hidden.length>0);
setCockpitVisibility(scene,false);assert.ok(hidden.every(node=>node.visible),'exterior source appearance must return');
nodes.forEach((node,i)=>assert.deepEqual(node.matrix.toArray(),transforms[i],'visibility must not alter model transforms'));
console.log('Pinned Phantom forward and both side sightlines clear; exterior visibility and model transforms retained');
