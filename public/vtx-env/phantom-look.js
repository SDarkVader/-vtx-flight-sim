// Phantom render hook: drives the CAD joint empties from
// rendering_truth.phantom.joints (MuJoCo joint values). Render only; no physics here.
// Each driven node carries glTF extras: phantom_joint, joint_type (hinge|slide), axis_parent, q_rest.
import * as THREE from 'three';

// Appearance only: reuse the A10's existing surfaces and articulated geometry.
// Values are linear RGB, matching the glTF material factors. No lights, thrust
// effects, geometry, joints or simulation properties are added or changed.
const exteriorPalette={
  'A6 sharp graphite armour facet': {color:[.105,.12,.14],metalness:.76,roughness:.3},
  'A6 VTX Phantom satin gunmetal armour': {color:[.075,.085,.105],metalness:.72,roughness:.32},
  'A6 dark carbon structural CFRP': {color:[.035,.04,.05],metalness:.42,roughness:.4},
  'A6 dark wheel face and thrust cover': {color:[.035,.04,.05],metalness:.65,roughness:.3},
  'A6 amber accent light': {color:[1,.48,.025],emissive:[1,.35,.012],emissiveIntensity:1.15},
  'Vaders amber luminescent edge': {color:[1,.48,.025],emissive:[1,.35,.012],emissiveIntensity:1.15},
};

function stylePhantom(model){
  const variants=new Map();
  model.traverse(node=>{
    if(!node.isMesh||!node.material)return;
    const headlamp=/^FACE_[LR]_AMBER_CHEVRON_LAMP/.test(node.name);
    const style=material=>{
      const preset=headlamp?{color:[.8,.9,1],emissive:[.65,.8,1],emissiveIntensity:1.5}:exteriorPalette[material.name];
      if(!preset)return material;
      let pair=variants.get(material);
      if(!pair){pair={};variants.set(material,pair);}
      const key=headlamp?'headlamp':'exterior';
      if(pair[key])return pair[key];
      const copy=material.clone();
      if(preset.color)copy.color.setRGB(...preset.color);
      if(preset.emissive&&copy.emissive)copy.emissive.setRGB(...preset.emissive);
      if(preset.emissiveIntensity!==undefined)copy.emissiveIntensity=preset.emissiveIntensity;
      if(preset.metalness!==undefined)copy.metalness=preset.metalness;
      if(preset.roughness!==undefined)copy.roughness=preset.roughness;
      return pair[key]=copy;
    };
    node.material=Array.isArray(node.material)?node.material.map(style):style(node.material);
  });
}

// An exposed, faceted rear-deck detail, attached to the rendered airframe only.
// It is deliberately separate from the sliding wings and all simulation bodies.
function addRearDeckDetail(model){
  const airframe=model.getObjectByName('airframe');
  if(!airframe)return;
  const deck=new THREE.Group();
  deck.name='phantom_visual_rear_deck';
  const dark=new THREE.MeshStandardMaterial({color:0x111923,metalness:.72,roughness:.34});
  const edge=new THREE.MeshStandardMaterial({color:0xd09224,metalness:.75,roughness:.3});
  const ribGeometry=new THREE.BoxGeometry(.055,.56,.035);
  const trimGeometry=new THREE.BoxGeometry(.012,.54,.008);
  for(let i=0;i<5;i++){
    const rib=new THREE.Mesh(ribGeometry,dark);
    rib.position.set(-1.45-i*.105,0,.91+i*.008);
    deck.add(rib);
    const trim=new THREE.Mesh(trimGeometry,edge);
    trim.position.set(-1.424-i*.105,0,.93+i*.008);
    deck.add(trim);
  }
  airframe.add(deck);
}

export function attachPhantom(model){
  if(model.getObjectByName('A10_WING_L_PANEL_CFRP_TORSION_BOX')){
    stylePhantom(model);
    addRearDeckDetail(model);
  }
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
