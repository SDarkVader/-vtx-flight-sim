// Distinct lightweight originals for assets without an authored GLB.
// Local coordinates: X forward, Y left, Z up, metres.
export function makeAirportModel(THREE,kind,color=0xe4e9e6){
 const root=new THREE.Group(),paint=new THREE.MeshStandardMaterial({color,metalness:.35,roughness:.45}),dark=new THREE.MeshStandardMaterial({color:0x182b35,metalness:.2,roughness:.7});
 const mesh=(geometry,material,x=0,y=0,z=0)=>{const m=new THREE.Mesh(geometry,material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;root.add(m);return m;};
 if(kind==='ground'){
  mesh(new THREE.BoxGeometry(3.8,1.9,.8),paint,0,0,.85);
  mesh(new THREE.BoxGeometry(1.8,1.7,.8),paint,.65,0,1.55);
  mesh(new THREE.BoxGeometry(1.3,1.72,.5),dark,.7,0,1.7);
  for(const x of [-1.15,1.15])for(const y of [-1.02,1.02]){
   const wheel=mesh(new THREE.CylinderGeometry(.36,.36,.16,10),dark,x,y,.38);wheel.rotation.x=Math.PI/2;
  }
 }else if(kind==='rotorcraft'){
  mesh(new THREE.SphereGeometry(1.25,12,8),paint,.3,0,1.25).scale.set(1.8,.85,.65);
  mesh(new THREE.BoxGeometry(3.4,.16,.2),dark,-2.1,0,1.1);
  mesh(new THREE.BoxGeometry(.2,1.3,.9),paint,-3.6,0,1.45);
  const rotor=new THREE.Group();rotor.name='airport-rotor';rotor.position.set(0,0,2.28);root.add(rotor);
  rotor.add(new THREE.Mesh(new THREE.BoxGeometry(.18,5.8,.08),dark));
  rotor.add(new THREE.Mesh(new THREE.BoxGeometry(5.8,.18,.08),dark));
  for(const y of [-.65,.65])mesh(new THREE.BoxGeometry(3.2,.1,.1),dark,.2,y,.22);
 }else{
  const fuselage=mesh(new THREE.CylinderGeometry(.48,.62,6.7,12),paint,0,0,1.1);fuselage.rotation.z=Math.PI/2;
  mesh(new THREE.BoxGeometry(1.6,9.2,.16),paint,-.15,0,1.25);
  mesh(new THREE.BoxGeometry(1.05,3.2,.12),paint,-2.6,0,1.45);
  mesh(new THREE.BoxGeometry(.8,.12,1.1),paint,-2.8,0,1.88);
  mesh(new THREE.SphereGeometry(.42,10,6),dark,1.2,0,1.48).scale.set(2.1,1,.45);
  for(const y of [-.85,.85])mesh(new THREE.CylinderGeometry(.26,.26,.14,8),dark,0,y,.35).rotation.x=Math.PI/2;
 }
 root.name='original-'+kind;
 return root;
}
