import * as THREE from 'three';

// The render of each navigation pile uses the native cylinder's centre and extent.
export function buildLanternMarks(root,world){
  const trial=world.harbour.timeTrial;
  if(!trial)return null;
  const known=new Map(world.obstacles.filter(o=>o.role==='race-mark').map(o=>[o.id,o]));
  const base=world.harbour.waterLevelM;
  const indicators=[];
  const metal=new THREE.MeshStandardMaterial({color:'#263940',roughness:.48,metalness:.48});
  const band=new THREE.MeshStandardMaterial({color:'#e9e0b8',roughness:.52,metalness:.25});
  for(const [i,gate] of trial.gates.entries()){
    const gateLamps=[];
    for(const key of gate.marks){
      const post=known.get(key);
      const [x,y,z]=post.center;
      const [r,,half]=post.half,top=z+half;
      const accent=new THREE.Color(post.color);
      const cut=(lo,hi,radius,mat,name)=>{
        const mesh=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,hi-lo,22),mat);
        mesh.rotation.x=Math.PI/2;
        mesh.position.set(x,y,(lo+hi)*.5);
        mesh.name=name;
        root.add(mesh);
        return mesh;
      };
      const strut=cut(z-half,top,r,metal,post.id);
      strut.userData.surveySpans=[{end:strut.geometry.index.count/3,id:post.id}];
      for(const level of [base+.72,base+1.87]){
        cut(level,level+.17,r+.005,band,post.id+' marker band');
      }
      const inner=new THREE.MeshBasicMaterial({color:accent.clone().multiplyScalar(1.85),toneMapped:false});
      cut(top-.64,top-.26,r+.008,inner,post.id+' navigation light');
      const crown=new THREE.MeshBasicMaterial({color:accent.clone().multiplyScalar(3.4),toneMapped:false});
      cut(top-.16,top,r-.03,crown,post.id+' gate light');
      gateLamps.push({inner,crown,accent});
    }
    indicators.push(gateLamps);
  }
  // Vaderland 33 Lantern Race: piles for every line, the shared start and finish built once.
  const races=world.harbour.races||[],racePiles=new Map();
  for(const race of races)for(const gate of race.gates)for(const key of gate.marks){
    if(racePiles.has(key))continue;
    const post=known.get(key),[x,y,z]=post.center,[r,,half]=post.half,top=z+half,accent=new THREE.Color(post.color);
    const cut=(lo,hi,radius,mat,name)=>{
      const mesh=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,hi-lo,18),mat);
      mesh.rotation.x=Math.PI/2;mesh.position.set(x,y,(lo+hi)*.5);mesh.name=name;root.add(mesh);return mesh;
    };
    cut(z-half,top,r,metal,post.id);
    for(const level of [base+.72,base+1.87])cut(level,level+.17,r+.005,band,post.id+' marker band');
    const inner=new THREE.MeshBasicMaterial({color:accent.clone().multiplyScalar(1.15),toneMapped:false});
    cut(top-.64,top-.26,r+.008,inner,post.id+' navigation light');
    const crown=new THREE.MeshBasicMaterial({color:accent.clone().multiplyScalar(1.66),toneMapped:false});
    cut(top-.16,top,r-.03,crown,post.id+' gate light');
    racePiles.set(key,{inner,crown,accent});
  }
  let current=-1,lit='';
  return state=>{
    if(races.length){
      // Light each running line's next gate; before a start, light the shared start gate.
      const runs=state?.lantern_races?.runs?.[state?.selectedId]||{},running=races.filter(r=>runs[r.name]?.start!=null);
      const keys=new Set((running.length?running:races).flatMap(r=>r.gates[runs[r.name]?.next??0].marks));
      const key=[...keys].sort().join();
      if(key!==lit){
        lit=key;
        for(const [id,{inner,crown,accent}] of racePiles){
          const on=keys.has(id);
          inner.color.copy(accent).multiplyScalar(on?2.6:1.15);crown.color.copy(accent).multiplyScalar(on?4.0:1.66);
        }
      }
    }
    const next=state?.lantern_trial?.runs?.[state.selectedId]?.next??0;
    if(next===current)return;
    current=next;
    for(const [i,lamps] of indicators.entries()){
      const active=i===next;
      for(const {inner,crown,accent} of lamps){
        inner.color.copy(accent).multiplyScalar(active?2.6:1.15);
        crown.color.copy(accent).multiplyScalar(active?4.0:1.66);
      }
    }
  };
}