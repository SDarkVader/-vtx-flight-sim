import * as THREE from 'three';

// Commuters use the same paths, surveyed foot heights and clock as their native contact bodies.
// All visible coats, heads and limbs share seven instanced meshes.
export function marketPedestrians(group,people){
  const skin=['#6e4330','#a06c4e','#c28d69','#d3a081','#e3b894','#8f5b42'];
  const coats=['#c28a43','#4a7682','#6f3845','#b7b8a7','#566f63','#6c7494','#bd6640','#bdad8d','#427b88','#9d6157','#73724f','#4e5665'];
  const pants=['#323c47','#514b42','#454453','#324d5e','#504551'];
  const hair=['#27272b','#554034','#76553b','#353238','#a99d89'];
  const vec=(x,y,z)=>new THREE.Vector3(x,y,z);
  const sphere=new THREE.SphereGeometry(1,12,9),body=new THREE.LatheGeometry(
    [[.61,-.50],[.81,-.45],[.80,-.23],[.73,.11],[.99,.32],[.94,.41],[.56,.50]].map(([x,y])=>new THREE.Vector2(x,y)),16).rotateX(Math.PI/2);
  const limb=new THREE.CylinderGeometry(.76,.60,1,9).rotateX(Math.PI/2);
  const shapes=[sphere,body,limb,limb,sphere,sphere,sphere];
  const capacity=[3,1,4,4,2,1,1],meshes=shapes.map((geo,k)=>{
    const m=new THREE.InstancedMesh(geo,new THREE.MeshStandardMaterial({roughness:.82,metalness:.015}),capacity[k]*people.length);
    m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);m.frustumCulled=false;m.count=0;m.name='Meridian commuters';group.add(m);return m;
  });
  const dummy=new THREE.Object3D(),quaternion=new THREE.Quaternion(),axisZ=vec(0,0,1),color=new THREE.Color();
  meshes[0].userData.pedestrianHeads=new Map();
  const tile=new Map();
  for(const [i,p] of people.entries()){
    const key=Math.floor(p.center[0]/200)+'/'+Math.floor(p.center[1]/200);
    if(!tile.has(key))tile.set(key,[]);tile.get(key).push([i,p]);
  }
  function update(camera,t){
    const counts=capacity.map(()=>0);
    const heads=meshes[0].userData.pedestrianHeads;heads.clear();
    function emit(k,position,scale,rotation,tint){
      const m=meshes[k],j=counts[k]++;
      dummy.position.copy(position);dummy.scale.copy(scale);dummy.quaternion.copy(rotation);dummy.updateMatrix();
      m.setMatrixAt(j,dummy.matrix);m.setColorAt(j,color.set(tint));
    }
    function bone(k,p,q,r,tint){
      const delta=q.clone().sub(p),length=delta.length();
      quaternion.setFromUnitVectors(axisZ,delta.multiplyScalar(1/Math.max(.0001,length)));
      emit(k,p.clone().lerp(q,.5),vec(r,r,length),quaternion,tint);
    }
    const px=Math.floor(camera.position.x/200),py=Math.floor(camera.position.y/200);
    for(let tx=px-2;tx<=px+2;tx++)for(let ty=py-2;ty<=py+2;ty++){
      for(const [i,p] of tile.get(tx+'/'+ty)??[]){
        const theta=p.phase+t*Math.PI*2/p.period_s,c=Math.cos(theta),s=Math.sin(theta);
        const x=p.center[0]+p.a[0]*c+p.b[0]*s,y=p.center[1]+p.a[1]*c+p.b[1]*s;
        if(Math.hypot(x-camera.position.x,y-camera.position.y)>390)continue;
        const u=((theta/(2*Math.PI)%1+1)%1)*p.heights.length,j=Math.floor(u),f=u-j;
        const z=p.heights[j]*(1-f)+p.heights[(j+1)%p.heights.length]*f;
        const dx=-p.a[0]*s+p.b[0]*c,dy=-p.a[1]*s+p.b[1]*c,L=Math.hypot(dx,dy);
        const fx=dx/L,fy=dy/L,angle=Math.atan2(fy,fx),att=new THREE.Quaternion().setFromAxisAngle(axisZ,angle);
        const h=p.height_m,H=(a,b,e)=>vec(x+h*(fx*a-fy*b),y+h*(fy*a+fx*b),z+h*e);
        const step=t*(5.1+i%4*.28)+i*1.63,speed=L*2*Math.PI/p.period_s;
        const stride=Math.min(1,speed/1.33),bob=Math.abs(Math.cos(step))*.010*stride;
        const coat=coats[p.look],trouser=pants[(i*7)%pants.length],face=skin[(i*5+p.look)%skin.length],dark=hair[(i+p.look)%hair.length];
        emit(1,H(.008,0,.593+bob),vec(h*.098,h*.144,h*(i%5===0?.39:.31)),att,coat);
        heads.set(p.name,counts[0]);
        emit(0,H(.015,0,.837+bob),vec(h*.054,h*.052,h*.065),att,face);
        emit(5,H(.011,0,.878+bob),vec(h*.058,h*.053,h*.041),att,dark);
        if(i%4===0)emit(6,H(-.031,0,.810+bob),vec(h*.047,h*.049,h*.065),att,dark);
        for(const side of [-1,1]){
          const phase=step+(side<0?Math.PI:0),swing=Math.sin(phase)*stride;
          const hip=H(0,side*.055,.48+bob),knee=H(.037+swing*.091,side*.055,.262+bob);
          const foot=H(swing*.151,side*.054,.043+Math.max(0,-Math.cos(phase))*.055*stride);
          bone(2,hip,knee,h*.071,trouser);bone(2,knee,foot,h*.055,trouser);
          emit(4,foot.clone().add(vec(fx*.045,fy*.045,-.011)),vec(h*.077,h*.037,h*.030),att,'#323339');
          const shoulder=H(0,side*.123,.706+bob),elbow=H(-.032-swing*.058,side*.139,.56+bob);
          const hand=H(.022-swing*.097,side*.145,.442+bob);
          bone(3,shoulder,elbow,h*.059,coat);bone(3,elbow,hand,h*.038,coat);
          emit(0,hand,vec(.033,.034,.064),att,face);
        }
      }
    }
    meshes.forEach((m,k)=>{m.count=counts[k];m.instanceMatrix.needsUpdate=true;if(m.instanceColor)m.instanceColor.needsUpdate=true;});
  }
  return {update};
}
