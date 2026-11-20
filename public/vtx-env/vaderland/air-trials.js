import * as THREE from 'three';

export function buildAirTrialMarkers(group,courses){
  const all=courses.map((course,index)=>{
    const tint=new THREE.Color(index?'#ffb367':'#70dae9');
    const active=new THREE.MeshBasicMaterial({color:tint.clone().multiplyScalar(2.6),toneMapped:false});
    const idle=new THREE.MeshBasicMaterial({color:tint,toneMapped:false});
    const gates=course.gates.map((gate,i)=>{
      const marker=new THREE.Group();
      marker.name=course.name+' gate '+(i+1);
      const center=new THREE.Vector3(...gate.center);
      const right=new THREE.Vector3(...gate.right);
      const up=new THREE.Vector3(...gate.up);
      const scale=Math.min(gate.height_m,gate.width_m);
      const thickness=scale*.036;
      const arm=scale*.25;
      const add=(a,b)=>{
        const edge=b.clone().sub(a);
        const piece=new THREE.Mesh(new THREE.BoxGeometry(thickness,thickness,edge.length()),idle);
        piece.position.copy(a.clone().lerp(b,.5));
        piece.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),edge.normalize());
        marker.add(piece);
      };
      for(const side of [-1,1])for(const high of [-1,1]){
        const corner=center.clone().addScaledVector(right,side*gate.width_m/2)
          .addScaledVector(up,high*gate.height_m/2);
        add(corner,corner.clone().addScaledVector(right,-side*arm));
        add(corner,corner.clone().addScaledVector(up,-high*arm));
      }
      group.add(marker);
      return marker;
    });
    return {course,gates,active,idle,next:-1};
  });
  const update=timing=>{
    for(const row of all){
      const next=timing?.[row.course.name]?.next??0;
      if(row.next===next)continue;
      row.next=next;
      for(const [i,gate] of row.gates.entries())for(const piece of gate.children){
        piece.material=i===next?row.active:row.idle;
      }
    }
  };
  update();
  return update;
}