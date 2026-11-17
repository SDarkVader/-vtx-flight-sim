import * as THREE from 'three';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {attachVehicleLivery} from '../public/vehicle-livery.js';
for(const file of ['phantom-a10b-visual.glb','phantom-a10-blendstra-81c823e2.glb']){
 const b=readFileSync(new URL('../public/assets/'+file,import.meta.url)),n=b.readUInt32LE(12),j=JSON.parse(b.subarray(20,20+n)),bin=b.subarray(28+n);
 const types={5121:Uint8Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array},sizes={SCALAR:1,VEC2:2,VEC3:3,VEC4:4};
 const accessor=id=>{const a=j.accessors[id],v=j.bufferViews[a.bufferView],T=types[a.componentType];return new T(bin.buffer,bin.byteOffset+(v.byteOffset||0)+(a.byteOffset||0),a.count*sizes[a.type]);};
 const nodes=j.nodes.map(s=>{
  const node=new THREE.Group();node.name=s.name||'';node.userData=s.extras||{};
  if(s.matrix){node.matrix.fromArray(s.matrix);node.matrix.decompose(node.position,node.quaternion,node.scale);}else{if(s.translation)node.position.fromArray(s.translation);if(s.rotation)node.quaternion.fromArray(s.rotation);if(s.scale)node.scale.fromArray(s.scale);}
  if(s.mesh!==undefined)for(const p of j.meshes[s.mesh].primitives){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(accessor(p.attributes.POSITION),3));if(p.indices!==undefined)g.setIndex(new THREE.BufferAttribute(accessor(p.indices),1));const m=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});m.name=j.materials[p.material]?.name||'';const mesh=new THREE.Mesh(g,m);mesh.name=s.name||'';node.add(mesh);}
  return node;
 });
 j.nodes.forEach((s,i)=>s.children?.forEach(c=>nodes[i].add(nodes[c])));const root=new THREE.Group();j.scenes[j.scene||0].nodes.forEach(i=>root.add(nodes[i]));
 const skin=[];root.traverse(n=>{if(n.isMesh&&n.name.startsWith('PHANTOM_A8_'))skin.push({node:n,geometry:n.geometry,vertices:[...n.geometry.attributes.position.array]});});
 attachVehicleLivery(root);const body=root.getObjectByName('airframe')||root.getObjectByName('VTX_VISUAL_ZUP_ROOT'),mark=root.getObjectByName('VTX_VISUAL_LIVERY_FLANK_WORDMARK');assert.equal(mark.parent,body);assert.ok(mark.userData.liverySurfaceHits>0,file+' lettering must reach the body skin');
 for(const s of skin){assert.equal(s.node.geometry,s.geometry);assert.deepEqual([...s.node.geometry.attributes.position.array],s.vertices,'structural geometry unchanged');}
 const point=mark.getWorldPosition(new THREE.Vector3());body.position.x+=10;root.updateMatrixWorld(true);assert.ok(Math.abs(mark.getWorldPosition(new THREE.Vector3()).x-point.x-10)<1e-6,'lettering follows its body');
 console.log(file,mark.userData.liverySurfaceHits,'lettering vertices fitted');
}
