// Phantom render hook: drives the CAD joint empties of /assets/phantom-a9.glb from
// rendering_truth.phantom.joints (MuJoCo joint values). Render only; no physics here.
// Each driven node carries glTF extras: phantom_joint, joint_type (hinge|slide), axis_parent, q_rest.
import * as THREE from 'three';

export function attachPhantom(model){
  const joints=[];
  model.traverse(n=>{const u=n.userData;if(u&&u.phantom_joint){joints.push({node:n,name:u.phantom_joint,type:u.joint_type,
    axis:new THREE.Vector3(...u.axis_parent).normalize(),q0:+u.q_rest,pos:n.position.clone(),quat:n.quaternion.clone()});}});
  return {joints};
}

const tmp=new THREE.Quaternion();
export function updatePhantom(rig,truth){
  const q=truth?.phantom?.joints;if(!rig||!q)return;
  for(const j of rig.joints){const v=q[j.name];if(v===undefined)continue;const d=v-j.q0;
    if(j.type==='slide'){j.node.position.copy(j.pos).addScaledVector(j.axis,d);}
    else{tmp.setFromAxisAngle(j.axis,d);j.node.quaternion.copy(tmp).multiply(j.quat);}}
}
