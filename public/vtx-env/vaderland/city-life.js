// Meridian city life: render-only street light, traffic and obstruction lights.
// Nothing here is a collider or part of the world fingerprint. Light follows where people are:
// lamp spacing, brightness, light pools and traffic all scale with the floor-area density of
// the surveyed buildings, so the core and its avenues are bright, the wards are dim and open
// land stays dark. Colour is restrained: sodium amber, cool white on the main avenues, red
// obstruction beacons. Everything is deterministic in (seconds).
import * as THREE from 'three';
import {heightfieldZ} from '../landscape.js';
import {cityDensity,hash2} from './city-density.js';

const LIT_KINDS = new Set(['street','arterial','boulevard','local','arrivals','marina-link','lane','track','viaduct']);
const MERIDIAN = {x0:-3300, x1:3100, y0:500, y1:5800};
const inMeridian = (x,y) => x>MERIDIAN.x0 && x<MERIDIAN.x1 && y>MERIDIAN.y0 && y<MERIDIAN.y1;
const smooth=(a,b,x)=>{const t=Math.min(1,Math.max(0,(x-a)/(b-a)));return t*t*(3-2*t);};

function rng(seed){let s=seed>>>0||1;return()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;};}

// Distant lights fade with the air rather than staying full strength into the haze.
const lightHaze = `
vec3 lightHaze(vec3 c,vec3 world){
  float d=length(cameraPosition-world);
  return c*mix(.18,1.,exp(-d*.00007));
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

export function buildCityLife(group, w, uniforms, density=cityDensity(w)){
  const root=new THREE.Group();root.name='Meridian city life';group.add(root);
  const time={value:0}, lit={value:0}, day={value:1};
  const shared={time,lit,day,night:uniforms.night};
  const routes=(w.vaderland.routes||[]).filter(r=>LIT_KINDS.has(r.kind)&&(r.kind!=='track'||inMeridian(...r.points[0])));

  // ---- 1. Street lamps: kept and brightened by density; open land stays unlit ------------
  const lamps=[], levels=[], pools=[], poolLevels=[], bases=[];
  for(const r of routes){
    if(r.kind==='viaduct'){                                             // bridge lighting is constant, at deck height
      for(const s of walk(r.points,46,w)){
        const reach=r.width_m/2+.6,deck=r.deck_z_m;
        for(const side of [-1,1]){
          const x=s.x-s.ty*reach*side,y=s.y+s.tx*reach*side;
          lamps.push(x,y,deck+8.5,1);levels.push(.62);bases.push(deck);
          pools.push(x+s.ty*2.*side,y-s.tx*2.*side,deck+.35,1);poolLevels.push(.42);
        }
      }
      continue;
    }
    const avenue=r.width_m>=40, spacing=avenue?34:28;
    const samples=walk(r.points,spacing,w);
    for(let k=0;k<samples.length;k++){
      const s=samples[k];
      if(k>0 && Math.abs(s.z-samples[k-1].z)>spacing*.16)continue;   // bridges, cuttings: no lamp on the slope
      const d=density.sample(s.x,s.y);
      const keep=d<.035?0:.12+.88*smooth(.06,.55,d);
      const reach=r.width_m/2+1.2;
      for(const side of [-1,1]){
        if(!avenue && side===1 && k%2)continue;                         // one side only on minor streets
        const x=s.x-s.ty*reach*side,y=s.y+s.tx*reach*side;
        if(hash2(x,y)>keep)continue;
        const z=heightfieldZ(w,x,y),level=.30+.70*smooth(.05,.85,d);
        const white=avenue&&d>.55?1:0;
        lamps.push(x,y,z+9.5,white?0:1);levels.push(level);bases.push(z);
        if(d>.22){pools.push(x+s.ty*2.2*side,y-s.tx*2.2*side,z+.45,white?0:1);poolLevels.push(level*smooth(.22,.8,d));}
      }
    }
  }
  root.add(lampHeads(lamps,levels,shared), lampPools(pools,poolLevels,shared), lampPosts(lamps,bases));

  // ---- 2. Traffic: volume follows density; empty roads at night are empty -----------------
  const cars=[];const random=rng(48611);
  for(const r of routes){
    if(r.kind==='arrivals'||r.kind==='local'||r.kind==='track'||r.kind==='lane'||r.kind==='viaduct')continue;
    const base=r.width_m>=40?.030:.016;                                // vehicles per metre per direction at full density
    const lanes=r.width_m>=40?2:1;
    for(let i=1;i<r.points.length;i++){
      const [ax,ay]=r.points[i-1],[bx,by]=r.points[i];
      const len=Math.hypot(bx-ax,by-ay);if(len<8)continue;
      const az=heightfieldZ(w,ax,ay),bz=heightfieldZ(w,bx,by);
      if(Math.abs(bz-az)>len*.16)continue;
      const d=density.sample((ax+bx)/2,(ay+by)/2);
      const count=Math.round(len*base*(.04+.96*smooth(.05,.8,d)));
      if(!count)continue;
      const tx=(bx-ax)/len,ty=(by-ay)/len;
      for(const dir of [1,-1])for(let lane=0;lane<lanes;lane++)for(let c=0;c<count;c++){
        const off=(1.9+lane*3.4)*dir;
        const sx=dir>0?ax:bx, sy=dir>0?ay:by, sz=dir>0?az:bz;
        cars.push(sx-ty*off,sy+tx*off,sz+.75, tx*dir*len,ty*dir*len,(dir>0?bz-az:az-bz),
                  random(), (11+random()*9)/len, dir);              // phase, speed in segment-lengths per second, heading class
      }
    }
  }
  root.add(traffic(cars,shared));

  // ---- 3. Red obstruction beacons on tall towers only -----------------------------------
  const tops=roofTops(w);
  root.add(beacons(tops,shared));

  // ---- 4. A few air-taxi lanes over the core ---------------------------------------------
  root.add(airTaxis(shared));

  return {
    density,
    stats:{lamps:lamps.length/4,cars:cars.length/9,beacons:tops.filter(t=>t.height>=60).length},
    update(seconds,mode){
      time.value=seconds;
      const n=uniforms.night.value, dusk=uniforms.blueHour?.value??0;
      lit.value=mode==='night'?1:mode==='dusk'?.85:Math.max(n,dusk*.8,0);
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
function lampHeads(data,levels,u){
  const n=data.length/4;
  const g=instancedQuad(n,[['lamp',4,data],['level',1,levels]]);
  const m=additive(`
    attribute vec4 lamp;attribute float level;uniform float lit;varying vec2 q;varying float warm,glow;varying vec3 world;
    void main(){
      q=position.xy;warm=lamp.w;world=lamp.xyz;glow=level;
      vec4 view=viewMatrix*vec4(lamp.xyz,1.);
      float d=-view.z;
      float size=max(.55,d*.0021);                                   // >= ~1.2 px at any range
      view.xy+=position.xy*size*lit;
      gl_Position=projectionMatrix*view;
    }`,`
    uniform float lit;varying vec2 q;varying float warm,glow;varying vec3 world;${lightHaze}
    void main(){
      float r=dot(q,q);if(r>1.)discard;
      vec3 c=mix(vec3(.80,.84,.92),vec3(1.,.56,.20),warm)*exp(-r*3.2)*1.9*glow;
      gl_FragColor=vec4(lightHaze(c,world)*lit,1.);
    }`,{lit:u.lit});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Street lamps';return mesh;
}

// Slim dark posts so lamp heads stand on something at street level (render-only, < 0.3 m wide).
function lampPosts(data,bases){
  const n=data.length/4;
  const geometry=new THREE.CylinderGeometry(.08,.13,1,6).rotateX(Math.PI/2);
  const mesh=new THREE.InstancedMesh(geometry,new THREE.MeshStandardMaterial({color:0x1d2128,roughness:.55,metalness:.6}),n);
  const m=new THREE.Matrix4(),q=new THREE.Quaternion(),s=new THREE.Vector3(),v=new THREE.Vector3();
  for(let i=0;i<n;i++){
    const x=data[i*4],y=data[i*4+1],top=data[i*4+2]-.25,ground=bases[i]-.3;
    v.set(x,y,(top+ground)/2);s.set(1,1,top-ground);m.compose(v,q,s);mesh.setMatrixAt(i,m);
  }
  mesh.name='Street lamp posts';return mesh;
}

// Flat additive light pools on the road surface: the lit grid seen from the air.
function lampPools(data,levels,u){
  const n=data.length/4;
  const g=instancedQuad(n,[['pool',4,data],['level',1,levels]]);
  const m=additive(`
    attribute vec4 pool;attribute float level;varying vec2 q;varying float warm,glow;varying vec3 world;
    void main(){
      q=position.xy;warm=pool.w;glow=level;
      world=pool.xyz+vec3(position.xy*8.5,0.);
      gl_Position=projectionMatrix*viewMatrix*vec4(world,1.);
    }`,`
    uniform float lit;varying vec2 q;varying float warm,glow;varying vec3 world;${lightHaze}
    void main(){
      float r=dot(q,q);if(r>1.)discard;
      vec3 V=normalize(cameraPosition-world);
      float facing=smoothstep(.05,.45,V.z);                       // grazing pools would smear along the road
      vec3 c=mix(vec3(.26,.28,.33),vec3(.55,.27,.08),warm)*pow(1.-r,2.4)*.30*facing*glow;
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
      vec3 head=vec3(1.,.90,.74)*1.3, tail=vec3(.9,.06,.04)*1.0;
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

// Red obstruction beacons on towers of 60 m and more, slow synchronised pulse by city sector.
function beacons(tops,u){
  const d=[];
  for(const t of tops){
    if(t.height<60)continue;
    const corners=t.round?[[0,0]]:[[-1,-1],[1,1]];
    for(const [i,j] of corners)d.push(t.x+i*(t.hx-.6),t.y+j*(t.hy-.6),t.z+1.4,Math.floor((t.x+4000)/900)*.37);
  }
  const g=instancedQuad(d.length/4,[['beacon',4,d]]);
  const m=additive(`
    attribute vec4 beacon;uniform float time;varying vec2 q;varying float pulse;varying vec3 world;
    void main(){
      q=position.xy;world=beacon.xyz;
      pulse=pow(max(0.,sin((time*.5+beacon.w)*6.2831853)),8.)*.9+.1;
      vec4 view=viewMatrix*vec4(beacon.xyz,1.);
      view.xy+=position.xy*max(.6,-view.z*.0022);
      gl_Position=projectionMatrix*view;
    }`,`
    varying vec2 q;varying float pulse;varying vec3 world;${lightHaze}
    void main(){float r=dot(q,q);if(r>1.)discard;
      gl_FragColor=vec4(lightHaze(vec3(.85,.04,.02)*exp(-r*3.)*1.6*pulse,world),1.);}`,{time:u.time});
  const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name='Obstruction beacons';return mesh;
}

// Vader's Taxis: render-only air traffic on elliptical lanes above the city. Each taxi is a
// warm body glow with port/starboard nav lights and a soft landing-light cone below.
function airTaxis(u){
  const lanes=[ // centre x,y, radii, altitude, speed (rad/s), count: a few quiet lanes over the core
    [-180,2600,1300,800,280,.016,6],[300,2500,700,500,210,-.022,4],[-200,2300,450,350,170,.03,3]];
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
      if(slot<.5){col=vec3(1.,.86,.66)*.9;size=.9;}
      else if(slot<1.5){p-=right*3.2;col=vec3(.9,.05,.04)*1.1;size=.6;}
      else if(slot<2.5){p+=right*3.2;col=vec3(.05,.8,.2)*1.0;size=.6;}
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
