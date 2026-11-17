import * as THREE from 'three';

// Fit only the existing visual lettering to the outer skin. The retained GLB,
// structural meshes and physics are unchanged. Artwork inherits its body pose.
export function attachVehicleLivery(root){
  const airframe=root.getObjectByName('airframe')||root.getObjectByName('VTX_VISUAL_ZUP_ROOT');if(!airframe)return;
  const marks=[],skin=[];
  root.traverse(node=>{
    if(node.name==='VTX_VISUAL_LIVERY_FLANK_WORDMARK'&&node.parent?.name!=='VTX_VISUAL_LIVERY_FLANK_WORDMARK')marks.push(node);
    if(node.isMesh&&node.name.startsWith('PHANTOM_A8_')&&node.material?.name==='A6 VTX Phantom satin gunmetal armour')skin.push(node);
  });
  for(const mark of marks){
    if(mark.userData.liveryAttached)continue;
    root.updateMatrixWorld(true);airframe.attach(mark);root.updateMatrixWorld(true);
    let hits=0;
    mark.traverse(mesh=>{
      if(!mesh.isMesh||!mesh.geometry?.attributes.position)return;
      const original=mesh.geometry;mesh.geometry=original.clone();
      const p=mesh.geometry.attributes.position,q=mesh.getWorldQuaternion(new THREE.Quaternion());
      const inverse=mesh.matrixWorld.clone().invert(),ray=new THREE.Raycaster();
      for(let i=0;i<p.count;i++){
        const v=new THREE.Vector3().fromBufferAttribute(p,i),side=Math.sign(v.y);if(!side)continue;
        const origin=new THREE.Vector3(v.x,side*4,v.z).applyMatrix4(mesh.matrixWorld);
        const direction=new THREE.Vector3(0,-side,0).applyQuaternion(q).normalize();
        ray.set(origin,direction);const hit=ray.intersectObjects(skin,false)[0];if(!hit)continue;
        const surface=hit.point.clone().applyMatrix4(inverse);
        if(Math.sign(surface.y)!==side||Math.abs(surface.y)>1.4)continue;
        p.setY(i,surface.y+side*.003);hits++;
      }
      p.needsUpdate=true;mesh.geometry.computeBoundingBox();mesh.geometry.computeBoundingSphere();
    });
    mark.userData.liveryAttached=true;mark.userData.liverySurfaceHits=hits;
  }
}
