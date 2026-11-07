// Render-only energy cues attached to the authored A10 wheel and nozzle meshes.
// No lights, forces or actuator commands are sent to the flight simulation.
export function attachAirportEnergyEffects(root,THREE){
 const canvas=document.createElement('canvas');canvas.width=64;canvas.height=64;
 const g=canvas.getContext('2d'),gradient=g.createRadialGradient(32,32,1,32,32,31);
 gradient.addColorStop(0,'rgba(255,244,191,.95)');
 gradient.addColorStop(.25,'rgba(255,167,46,.65)');
 gradient.addColorStop(1,'rgba(255,103,15,0)');
 g.fillStyle=gradient;g.fillRect(0,0,64,64);
 const texture=new THREE.CanvasTexture(canvas),wheels=[],nozzles=[];
 root.traverse(node=>{
  if(!node.isMesh)return;
  const wheel=/^WHEEL_(FL|FR|RL|RR)_AMBER_RING$/.test(node.name);
  const nozzle=/^POWER_[LR]_REAR_THRUST_NOZZLE$/.test(node.name);
  if(!wheel&&!nozzle)return;
  node.geometry.computeBoundingBox();
  const center=node.geometry.boundingBox.getCenter(new THREE.Vector3());
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,color:wheel?0xffb949:0xff8b36,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,opacity:0}));
  sprite.position.copy(center);sprite.scale.setScalar(wheel ? .95 : 1.25);
  sprite.visible=false;node.add(sprite);
  const material=Array.isArray(node.material)?node.material.map(m=>m.clone()):node.material.clone();
  node.material=material;
  (wheel?wheels:nozzles).push({sprite,material});
 });
 return {wheels,nozzles,update(pose,time){
  const phase=pose.operation||'stand',speed=pose.speed||0;
  const active=/takeoff|climb|circuit|approach|landing|passenger ride|go-around/.test(phase);
  const wheelPower=phase==='stand'?0:Math.min(.7,.12+speed/45);
  const thrustPower=active?Math.min(.9,.35+speed/55):/taxi|runway entry/.test(phase)?.3:0;
  const pulse=.9+.1*Math.sin(time*8);
  for(const {sprite,material} of wheels){sprite.visible=wheelPower>.03;sprite.material.opacity=wheelPower*pulse;
   for(const m of Array.isArray(material)?material:[material])if(m.emissive){m.emissive.setHex(0xff9a28);m.emissiveIntensity=.2+wheelPower*1.6;}}
  for(const {sprite,material} of nozzles){sprite.visible=thrustPower>.03;sprite.material.opacity=thrustPower*pulse;
   for(const m of Array.isArray(material)?material:[material])if(m.emissive){m.emissive.setHex(0xff7424);m.emissiveIntensity=.2+thrustPower*1.8;}}
 }};
}
