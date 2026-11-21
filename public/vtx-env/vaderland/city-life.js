// Meridian city life: render-only light, traffic and silhouette layer.
// Nothing here is a collider or part of the world fingerprint. It reads the surveyed
// road polylines and building boxes and draws what a pilot uses to read a city at
// speed: lamp-lit street grids, moving traffic streams, lit roof edges, obstruction
// beacons and Vader's Taxis air lanes. Everything is deterministic in (seconds).
import * as THREE from 'three';
import {heightfieldZ} from '../landscape.js';

const LIT_KINDS = new Set(['street','arterial','boulevard','local','arrivals','marina-link']);
const MERIDIAN = {x0:-3300, x1:3100, y0:500, y1:5800};
const inMeridian = (x,y) => x>MERIDIAN.x0 && x<MERIDIAN.x1 && y>MERIDIAN.y0 && y<MERIDIAN.y1;

function rng(seed){let s=seed>>>0||1;return()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;};}

// Haze that keeps emissive light legible: lights attenuate with distance far less than
// lit surfaces do, which is what separates a city from its haze at blue hour.
const lightHaze = `
vec3 lightHaze(vec3 c,vec3 world){
  float d=length(cameraPosition-world);
  float fade=exp(-d*.000045);
  return c*mix(.35,1.,fade);
}`;

// Walk a polyline at fixed spacing and return samples with tangent and terrain height.
function walk(points, spacing, w){
  const out=[];let carry=0;
  for(let i=1;i<points.length;i++){
    const [ax,ay]=points[i-1],[bx,by]=points[i];
    const dx=bx-ax,dy=by-ay,len=Math.hypot(dx,dy);if(len<1e-6)continue;
    const tx=dx/len,ty=dy/len;
    for(let s=carry;s<len;s+=spacing){
      const x=ax+tx*s,y=ay+ty*s;out.push({x,y,z:heightfieldZ(w,x,y),tx,ty});
    }
    carry=(carry-len)%spacing;if(carry<0)carry+=spacing;
  }
  return out;
}

export function buildCityLife(group, w, uniforms){
  const root=new THREE.Group();root.name='Meridian city life';group.add(root);
  const time={value:0}, lit={value:0}, day={value:1};
  const shared={time,lit,day,night:uniforms.night};
  const routes=(w.vaderland.routes||[]).filter(r=>LIT_KINDS.has(r.kind));

  // ---- 1. Street lamps and their light pools -------------------------------------------
  const lamps=[], pools=[];
  for(const r of routes){
    const arterial=r.kind!=='street', spacing=arterial?38:30;
    const samples=walk(r.points,spacing,w);
    for(let k=0;k<samples.length;k++){
      const s=samples[k];
      if(k>0 && Math.abs(s.z-samples[k-1].z)>spacing*.16)continue;   // bridges, cuttings: no lamp on the slope
      const reach=r.width_m/2+1.2;
      for(const side of [-1,1]){
        if(arterial && side===1 && k%2)continue;                     // staggered on wider roads
        const x=s.x-s.ty*reach*side,y=s.y+s.tx*reach*side,z=heightfieldZ(w,x,y);
        const warm=inMeridian(x,y)?(r.width_m>=40?0:1):0;          // sodium side streets, white LED avenues
        lamps.push(x,y,z+9.5,warm);
        pools.push(x-s.ty*2.2*-side,y+s.tx*2.2*-side,z+.45,warm);
      }
    }
  }
  root.add(lampHeads(lamps,shared), lampPools(pools,shared), lampPosts(lamps,w));

  // ---- 2. Traffic light streams --------------------------------------------------------
  const cars=[];const random=rng(48611);
  for(const r of routes){
    if(r.kind==='arrivals'||r.kind==='local')continue;
    const density=r.width_m>=40?.034:.020;                              // vehicles per metre per direction
    const lanes=r.width_m>=40?2:1;
    for(let i=1;i<r.points.length;i++){
      const [ax,ay]=r.points[i-1],[bx,by]=r.points[i];
      const len=Math.hypot(bx-ax,by-ay);if(len<8)continue;
      const az=heightfieldZ(w,ax,ay),bz=heightfieldZ(w,bx,by);
      if(Math.abs(bz-az)>len*.16)continue;
      const tx=(bx-ax)/len,ty=(by-ay)/len,count=Math.max(1,Math.round(len*density));
      for(const dir of [1,-1])for(let lane=0;lane<lanes;lane++)for(let c=0;c<count;c++){
        const off=(1.9+lane*3.4)*dir;
        const sx=dir>0?ax:bx, sy=dir>0?ay:by, sz=dir>0?az:bz;
        cars.push(sx-ty*off,sy+tx*off,sz+.75, tx*dir*len,ty*dir*len,(dir>0?bz-az:az-bz),
                  random(), (11+random()*9)/len, dir);              // phase, speed in segment-lengths per second, heading class
      }
    }
  }
  root.add(traffic(cars,shared));

  // ---- 3. Roof edges and obstruction beacons --------------------------------------------
  const tops=roofTops(w);
  root.add(roofEdges(tops,shared), beacons(tops,shared));

  // ---- 4. Vader's Taxis air lanes --------------------------------------------------------
  root.add(airTaxis(shared));

  return {
    stats:{lamps:lamps.length/4,cars:cars.length/9,roofs:tops.length},
    update(seconds,mode){
      time.value=seconds;
      const n=uniforms.night.value, dusk=uniforms.blueHour?.value??0;
      lit.value=mode==='night'?1:mode==='dusk'?.92:Math.max(n,dusk*.9,.0);
      day.value=1-lit.value;
    }
  };
}

// --------------------------------------------------------------------------------------------
function instancedQuad(count,attributes){
  const g=new THREE.InstancedBufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute([-1,-1,0, 1,-1,0, 1,1,0, -1,1,0],3));
  g.setIndex([0,1,2,0,2,3]);g.instanceCount=count;
  for(const [name,size,data] of attributes)g.setAttribute(name,new THREE.InstancedBufferAttribute(new Float32Array(data),size));
  return g;
}
function additive(vertexShader,fragmentShader,uniforms){
  return new THREE.ShaderMaterial({uniforms,vertexShader,fragmentShader,transparent:true,depthWrite:false,
    blending:THREE.AdditiveBlending,fog:false,toneMapped:false});
}

// Camera-facing lamp heads, size-clamped in pixels so the grid reads from altitude.
function lampHeads(data,u){
  const n=data.length/4;
  const g=instancedQuad(n,[['lamp',4,data]]);
  const m=additive(`
    attribute vec4 lamp;uniform float lit;varying vec2 q;varying float warm;varying vec3 world;
    void main(){
      q=position.xy;warm=lamp.w;world=lamp.xyz;
      vec4 view=viewMatrix*vec4(lamp.xyz,1.);
      float d=-view.z;
      float size=max(.55,d*.0021);                                   // >= ~1.2 px at any range
      view.xy+=position.xy*size*lit;
      gl_Position=projectionMatrix*view;
    }`,`
    uniform float lit;varying vec2 q;varying float warm;varying vec3 world;${lightHaze}
    void main(){
      float r=dot(q,q);if(r>1.)discard;
      vec3 c=mix(vec3(.82,.86,1.),vec3(1.,.58,.22),warm)*exp(-r*3.2)*2.4;
      gl_FragColor=vec4(lightHaze(c,world)*lit,1.);
    }`,{lit:u.lit});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Street lamps';return mesh;
}

// Slim dark posts so lamp heads stand on something at street level (render-only, < 0.3 m wide).
function lampPosts(data,w){
  const n=data.length/4;
  const geometry=new THREE.CylinderGeometry(.08,.13,1,6).rotateX(Math.PI/2);
  const mesh=new THREE.InstancedMesh(geometry,new THREE.MeshStandardMaterial({color:0x1d2128,roughness:.55,metalness:.6}),n);
  const m=new THREE.Matrix4(),q=new THREE.Quaternion(),s=new THREE.Vector3(),v=new THREE.Vector3();
  for(let i=0;i<n;i++){
    const x=data[i*4],y=data[i*4+1],top=data[i*4+2]-.25,ground=heightfieldZ(w,x,y)-.3;
    v.set(x,y,(top+ground)/2);s.set(1,1,top-ground);m.compose(v,q,s);mesh.setMatrixAt(i,m);
  }
  mesh.name='Street lamp posts';return mesh;
}

// Flat additive light pools on the road surface: the lit grid seen from the air.
function lampPools(data,u){
  const n=data.length/4;
  const g=instancedQuad(n,[['pool',4,data]]);
  const m=additive(`
    attribute vec4 pool;varying vec2 q;varying float warm;varying vec3 world;
    void main(){
      q=position.xy;warm=pool.w;
      world=pool.xyz+vec3(position.xy*8.5,0.);
      gl_Position=projectionMatrix*viewMatrix*vec4(world,1.);
    }`,`
    uniform float lit;varying vec2 q;varying float warm;varying vec3 world;${lightHaze}
    void main(){
      float r=dot(q,q);if(r>1.)discard;
      vec3 V=normalize(cameraPosition-world);
      float facing=smoothstep(.05,.45,V.z);                       // grazing pools would smear along the road
      vec3 c=mix(vec3(.30,.33,.42),vec3(.62,.30,.09),warm)*pow(1.-r,2.4)*.34*facing;
      gl_FragColor=vec4(lightHaze(c,world)*lit,1.);
    }`,{lit:u.lit});
  m.polygonOffset=true;m.polygonOffsetFactor=-4;m.polygonOffsetUnits=-8;
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Street light pools';return mesh;
}

// Each vehicle is a short light streak travelling along one surveyed road segment:
// white headlights towards the camera's side of the road, red tail lights away.
function traffic(data,u){
  const n=data.length/9;
  const start=[],span=[],motion=[];
  for(let i=0;i<n;i++){const o=i*9;start.push(data[o],data[o+1],data[o+2]);span.push(data[o+3],data[o+4],data[o+5]);motion.push(data[o+6],data[o+7],data[o+8]);}
  const g=instancedQuad(n,[['start',3,start],['span',3,span],['motion',3,motion]]);
  const m=additive(`
    attribute vec3 start,span,motion;uniform float time,lit;
    varying vec2 q;varying vec3 world;varying float edge,front;
    void main(){
      q=position.xy;
      float f=fract(motion.x+time*motion.y);
      edge=smoothstep(0.,.06,f)*(1.-smoothstep(.94,1.,f));
      vec3 dir=normalize(span),side=normalize(vec3(-dir.y,dir.x,0.));
      vec3 centre=start+span*f;
      vec3 toCam=normalize(cameraPosition-centre);
      front=dot(dir,toCam);                                          // >0: approaching the camera
      float d=length(cameraPosition-centre);
      float grow=max(1.,d*.0016);
      world=centre+dir*position.x*(2.6+1.4*grow)+side*position.y*.7*grow+vec3(0.,0.,.15*grow);
      gl_Position=projectionMatrix*viewMatrix*vec4(world,1.);
    }`,`
    uniform float lit;varying vec2 q;varying vec3 world;varying float edge,front;${lightHaze}
    void main(){
      float core=exp(-q.y*q.y*5.)*(1.-smoothstep(.55,1.,abs(q.x)));
      vec3 head=vec3(1.,.93,.80)*1.9, tail=vec3(1.,.07,.05)*1.35;
      vec3 c=mix(tail,head,smoothstep(-.15,.15,front))*core*edge;
      gl_FragColor=vec4(lightHaze(c,world)*(.18+.82*lit),1.);
    }`,{time:u.time,lit:u.lit});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Traffic streams';return mesh;
}

// Topmost axis-aligned roof boxes of Meridian buildings taller than 14 m.
function roofTops(w){
  const boxes=w.obstacles.filter(o=>(o.kind==='box'||o.kind==='mesh'||o.kind==='cylinder')&&inMeridian(o.center[0],o.center[1])
    && o.half[0]>3 && o.half[1]>3 && o.half[0]<80 && o.half[1]<80 && (o.kind!=='mesh'||o.city||o.role==='architecture'));
  const cells=new Map(),key=(x,y)=>Math.floor(x/60)+','+Math.floor(y/60);
  for(const o of boxes){const k=key(o.center[0],o.center[1]);(cells.get(k)??cells.set(k,[]).get(k)).push(o);}
  const tops=[];
  for(const o of boxes){
    const [cx,cy,cz]=o.center,[hx,hy,hz]=o.half,top=cz+hz;
    const ground=heightfieldZ(w,cx,cy);if(top-ground<14)continue;
    let covered=false;
    for(let i=-1;i<=1&&!covered;i++)for(let j=-1;j<=1&&!covered;j++){
      for(const b of cells.get((Math.floor(cx/60)+i)+','+(Math.floor(cy/60)+j))??[]){
        if(b!==o&&b.center[2]-b.half[2]>=top-.6&&b.center[2]-b.half[2]<top+3&&Math.abs(b.center[0]-cx)<hx&&Math.abs(b.center[1]-cy)<hy){covered=true;break;}
      }
    }
    if(!covered)tops.push({x:cx,y:cy,z:top,hx,hy,height:top-ground,round:o.kind==='cylinder',id:o.id});
  }
  return tops;
}

const PALETTE=[[1.,.55,.16],[.62,.25,1.],[1.,.55,.16],[.95,.20,.55],[.25,.85,1.],[1.,.55,.16],[.62,.25,1.]];
function seedOf(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);return (h>>>0)/4294967296;}

// Parapet light lines: thin emissive bars on the roof edge of about half the buildings.
function roofEdges(tops,u){
  const a=[],b=[],col=[];
  for(const t of tops){
    const s=seedOf(t.id);if(s>.58 && t.height<55)continue;           // quieter blocks stay dark
    const c=PALETTE[Math.floor(s*997)%PALETTE.length];
    const z=t.z+.35;
    if(t.round){
      const r=Math.min(t.hx,t.hy)+.05,N=24;
      for(let i=0;i<N;i++){const a0=i/N*Math.PI*2,a1=(i+1)/N*Math.PI*2;
        a.push(t.x+Math.cos(a0)*r,t.y+Math.sin(a0)*r,z);b.push(t.x+Math.cos(a1)*r,t.y+Math.sin(a1)*r,z);col.push(...c);}
    }else{
      const x0=t.x-t.hx-.05,x1=t.x+t.hx+.05,y0=t.y-t.hy-.05,y1=t.y+t.hy+.05;
      for(const [p,q] of [[[x0,y0],[x1,y0]],[[x1,y0],[x1,y1]],[[x1,y1],[x0,y1]],[[x0,y1],[x0,y0]]]){
        a.push(p[0],p[1],z);b.push(q[0],q[1],z);col.push(...c);}
    }
  }
  const g=instancedQuad(a.length/3,[['a',3,a],['b',3,b],['tint',3,col]]);
  const m=additive(`
    attribute vec3 a,b,tint;uniform float lit;varying vec3 c,world;varying float v;
    void main(){
      float t=position.x*.5+.5;v=position.y;
      vec3 p=mix(a,b,t);
      vec4 view=viewMatrix*vec4(p,1.);
      vec4 va=viewMatrix*vec4(a,1.),vb=viewMatrix*vec4(b,1.);
      vec2 dir=normalize((vb.xy/max(.1,-vb.z))-(va.xy/max(.1,-va.z))+1e-5);
      float width=max(.22,-view.z*.0017);                            // >= ~1 px band at range
      view.xy+=vec2(-dir.y,dir.x)*position.y*width;
      c=tint;world=p;gl_Position=projectionMatrix*view;
    }`,`
    uniform float lit;varying vec3 c,world;varying float v;${lightHaze}
    void main(){
      vec3 col=c*exp(-v*v*2.5)*(1.25+.0*v);
      gl_FragColor=vec4(lightHaze(col,world)*(.22+.78*lit),1.);
    }`,{lit:u.lit});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Roof edge lights';return mesh;
}

// Red obstruction beacons on towers over 45 m, slow synchronised pulse by city sector.
function beacons(tops,u){
  const d=[];
  for(const t of tops){
    if(t.height<45)continue;
    const corners=t.round?[[0,0]]:[[-1,-1],[1,1]];
    for(const [i,j] of corners)d.push(t.x+i*(t.hx-.6),t.y+j*(t.hy-.6),t.z+1.4,Math.floor((t.x+4000)/900)*.37);
  }
  const g=instancedQuad(d.length/4,[['beacon',4,d]]);
  const m=additive(`
    attribute vec4 beacon;uniform float time;varying vec2 q;varying float pulse;varying vec3 world;
    void main(){
      q=position.xy;world=beacon.xyz;
      pulse=pow(max(0.,sin((time*.75+beacon.w)*6.2831853)),6.)*.85+.15;
      vec4 view=viewMatrix*vec4(beacon.xyz,1.);
      view.xy+=position.xy*max(.9,-view.z*.0034);
      gl_Position=projectionMatrix*view;
    }`,`
    varying vec2 q;varying float pulse;varying vec3 world;${lightHaze}
    void main(){float r=dot(q,q);if(r>1.)discard;
      gl_FragColor=vec4(lightHaze(vec3(1.,.05,.03)*exp(-r*3.)*2.6*pulse,world),1.);}`,{time:u.time});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Obstruction beacons';return mesh;
}

// Vader's Taxis: render-only air traffic on elliptical lanes above the city. Each taxi is a
// warm body glow with port/starboard nav lights and a soft landing-light cone below.
function airTaxis(u){
  const lanes=[ // centre x,y, radii, altitude, speed (rad/s), count
    [-180,2600,1500,900,260,.018,14],[600,3300,1100,700,330,-.022,10],[-1600,3700,900,600,210,.026,8],
    [-200,2300,520,380,170,-.034,6],[1500,2200,800,1100,290,.020,8],[-2300,4400,700,500,240,-.03,6]];
  const d=[];
  for(const [x,y,rx,ry,z,sp,count] of lanes)for(let i=0;i<count;i++)d.push(x,y,rx,ry,z+((i%3)-1)*18,sp,i/count*6.2831853,0);
  const n=d.length/8;
  const l0=[],l1=[],slot=[];                                         // 3 sprites per taxi: body, port, starboard
  for(let i=0;i<n;i++)for(let k=0;k<3;k++){l0.push(...d.slice(i*8,i*8+4));l1.push(...d.slice(i*8+4,i*8+8));slot.push(k);}
  const g=instancedQuad(n*3,[['laneA',4,l0],['laneB',4,l1],['slot',1,slot]]);
  const m=additive(`
    attribute vec4 laneA,laneB;attribute float slot;uniform float time;
    varying vec2 q;varying vec3 col,world;varying float cone;
    void main(){
      q=position.xy;
      float a=laneB.z+time*laneB.y;
      vec3 c=vec3(laneA.x+cos(a)*laneA.z,laneA.y+sin(a)*laneA.w,laneB.x+sin(a*3.+laneB.z)*6.);
      vec3 fwd=normalize(vec3(-sin(a)*laneA.z,cos(a)*laneA.w,0.)*sign(laneB.y));
      vec3 right=vec3(fwd.y,-fwd.x,0.);
      vec3 p=c;float size=1.;cone=0.;
      if(slot<.5){col=vec3(1.,.70,.25)*1.4;size=1.1;}
      else if(slot<1.5){p-=right*3.2;col=vec3(1.,.05,.05)*1.8;size=.8;}
      else if(slot<2.5){p+=right*3.2;col=vec3(.05,1.,.25)*1.6;size=.8;}
      else{p-=vec3(0.,0.,14.);col=vec3(.55,.75,1.)*.22;size=10.;cone=1.;}
      world=p;
      vec4 view=viewMatrix*vec4(p,1.);
      view.xy+=position.xy*(cone>.5?size*vec2(.6,1.6):vec2(max(size,-view.z*.0028*size)));
      gl_Position=projectionMatrix*view;
    }`,`
    uniform float lit;varying vec2 q;varying vec3 col,world;varying float cone;${lightHaze}
    void main(){
      float r=dot(q,q);if(r>1.)discard;
      float shape=cone>.5?(1.-abs(q.x))*smoothstep(-1.,1.,q.y)*(1.-r):exp(-r*3.);
      gl_FragColor=vec4(lightHaze(col*shape,world)*(.45+.55*lit),1.);
    }`,{time:u.time,lit:u.lit});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name="Vader's Taxis air lanes";return mesh;
}
