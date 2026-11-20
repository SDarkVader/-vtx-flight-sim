import * as THREE from 'three';

// Keep the chart triangles, including island holes. Only the areas covered by
// solver samples need a finer mesh. The remainder keeps the original sea level.
function clip(poly,axis,edge,sign){
  const out=[];
  for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length];
    const da=(a[axis]-edge)*sign,db=(b[axis]-edge)*sign;
    if(da>=0)out.push(a);
    if(da*db<0){
      const t=da/(da-db);out.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);
    }
  }
  return out;
}

function refine(chart,origins,n,step){
  const pos=[],indices=[],vertices=new Map(),bindings=[];
  const span=step*(n-1);
  function vertex(p){
    const key=Math.round(p[0]*1e5)+','+Math.round(p[1]*1e5);
    if(vertices.has(key))return vertices.get(key);
    const id=vertices.size;vertices.set(key,id);pos.push(...p,0);
    let best=0,bind=null;
    origins.forEach(([ox,oy],patch)=>{
      const u=(p[0]-ox)/step,v=(p[1]-oy)/step;
      const edge=Math.min(u,v,n-1-u,n-1-v,1);
      if(edge<=best)return;
      const i=Math.min(n-2,Math.floor(u)),j=Math.min(n-2,Math.floor(v));
      best=edge;bind={patch,k:j*n+i,u:u-i,v:v-j,edge};
    });
    bindings.push(bind);return id;
  }
  function emit(poly){
    if(poly.length<3)return;
    for(let i=1;i<poly.length-1;i++){
      const [a,b,c]=[poly[0],poly[i],poly[i+1]];
      if(Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))>1e-8)
        indices.push(vertex(a),vertex(b),vertex(c));
    }
  }
  function region(poly,k){
    if(poly.length<3)return;
    if(k===origins.length){emit(poly);return;}
    const [x,y]=origins[k];
    if(poly.every(p=>p[0]<=x)||poly.every(p=>p[0]>=x+span)||poly.every(p=>p[1]<=y)||poly.every(p=>p[1]>=y+span)){
      region(poly,k+1);return;
    }
    for(const [axis,edge,sign] of [[0,x,1],[0,x+span,-1],[1,y,1],[1,y+span,-1]]){
      region(clip(poly,axis,edge,-sign),k+1);
      poly=clip(poly,axis,edge,sign);if(poly.length<3)return;
    }
    const row0=Math.max(0,Math.floor((Math.min(...poly.map(p=>p[1]))-y)/step));
    const row1=Math.min(n-1,Math.ceil((Math.max(...poly.map(p=>p[1]))-y)/step));
    for(let j=row0;j<row1;j++){
      const row=clip(clip(poly,1,y+j*step,1),1,y+(j+1)*step,-1);
      if(row.length<3)continue;
      const col0=Math.max(0,Math.floor((Math.min(...row.map(p=>p[0]))-x)/step));
      const col1=Math.min(n-1,Math.ceil((Math.max(...row.map(p=>p[0]))-x)/step));
      for(let i=col0;i<col1;i++)emit(clip(clip(row,0,x+i*step,1),0,x+(i+1)*step,-1));
    }
  }
  const xy=chart.attributes.position,index=chart.index;
  for(let i=0;i<index.count;i+=3){
    region([0,1,2].map(j=>{const k=index.getX(i+j);return [xy.getX(k),xy.getY(k)];}),0);
  }
  const mesh=new THREE.BufferGeometry();
  mesh.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  mesh.setIndex(indices);return {mesh,bindings};
}

export function followTide(water,survey){
  const chart=water.geometry,n=survey.samples,step=survey.spacing_m;
  let current,layout='',generation,seconds;
  function reset(){
    if(current){current.mesh.dispose();current=null;}
    water.geometry=chart;layout='';seconds=undefined;
  }
  return {
    get time(){return seconds??0;},
    update(state){
      const surface=state?.water_surface;
      if(!state?.available || surface?.samples!==n || surface.spacing_m!==step || !surface.patches?.length){
        reset();return;
      }
      if(state.generation===generation && state.t_s<=seconds)return;
      const patches=surface.patches;
      if(patches.some(p=>!Array.isArray(p.origin)||p.origin.length!==2||!p.origin.every(Number.isFinite)||
        typeof p.offset_f32le!=='string'||p.offset_f32le.length!==Math.ceil(n*n*4/3)*4)){reset();return;}
      const origins=patches.map(p=>p.origin);
      const key=JSON.stringify(origins);
      if(key!==layout){
        reset();current=refine(chart,origins,n,step);
        water.geometry=current.mesh;layout=key;
      }
      const data=patches.map(p=>{
        const bytes=Uint8Array.from(atob(p.offset_f32le),c=>c.charCodeAt(0));
        return new Float32Array(bytes.buffer);
      });
      const position=current.mesh.attributes.position;
      current.bindings.forEach((b,i)=>{
        if(!b)return;
        const a=data[b.patch],k=b.k;
        const z=(1-b.v)*((1-b.u)*a[k]+b.u*a[k+1])+b.v*((1-b.u)*a[k+n]+b.u*a[k+n+1]);
        position.setZ(i,z*b.edge);
      });
      position.needsUpdate=true;current.mesh.computeVertexNormals();current.mesh.computeBoundingSphere();
      generation=state.generation;seconds=state.t_s;
    },
    dispose:reset,
  };
}
