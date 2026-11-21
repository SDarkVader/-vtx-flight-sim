// Vaderland 33 · the Lantern Race in the Needle narrows (render only).
// Rocks, floating ramps, slipway, trail tabletop, the overlook deck with banners, the Lantern Rock
// beacon, bank lanterns, spray, and the whitewater the harbour water shader draws from the same
// rapid the physics uses (src/vtx/water/rapids.py).
import * as THREE from 'three';

export const lanternRaceSolid=id=>id.startsWith('lr-')&&!id.startsWith('lr-fir-');   // firs join the island forests

const G=9.80665;
const smooth=(a,b,x)=>{const t=Math.min(1,Math.max(0,(x-a)/(b-a)));return t*t*(3-2*t);};
const AMBER=new THREE.Color('#ffb35c');

// A port of rapids_overlay: reach coordinates, current, eddies, standing waves and rock flow.
export function rapidSampler(rapid){
  const st=rapid.stations,m=st.length-1,seg=[];let total=0;
  for(let i=0;i<m;i++){
    const dx=st[i+1][0]-st[i][0],dy=st[i+1][1]-st[i][1],L=Math.hypot(dx,dy);
    seg.push({x:st[i][0],y:st[i][1],tx:dx/L,ty:dy/L,L,c:total});total+=L;
  }
  const cum=[...seg.map(s=>s.c),total];
  const interp=(s,col)=>{
    if(s<=0)return st[0][col];if(s>=total)return st[m][col];
    let i=0;while(i<m-1&&cum[i+1]<s)i++;
    const f=(s-cum[i])/(cum[i+1]-cum[i]);return st[i][col]*(1-f)+st[i+1][col]*f;
  };
  const margin=rapid.margin_m??12,endMargin=rapid.reach_margin_m??margin,ef=rapid.eddy_fraction??.25,wave=rapid.waves;
  let phase=null;
  if(wave){
    const n=Math.max(2,Math.floor((wave.to_m-wave.from_m)/.5)+1),step=(wave.to_m-wave.from_m)/(n-1),v=new Float32Array(n);
    let k0=G/Math.max(interp(wave.from_m,3),1.2)**2;
    for(let i=1;i<n;i++){const k=G/Math.max(interp(wave.from_m+i*step,3),1.2)**2;v[i]=v[i-1]+.5*(k+k0)*step;k0=k;}
    phase={step,v};
  }
  const rocks=rapid.rocks||[];
  return (x,y)=>{
    let best=Infinity,k=0,al=0,raw=0;
    for(let i=0;i<m;i++){
      const s=seg[i],rx=x-s.x,ry=y-s.y,r=rx*s.tx+ry*s.ty,a=Math.min(s.L,Math.max(0,r)),fx=rx-a*s.tx,fy=ry-a*s.ty,d=fx*fx+fy*fy;
      if(d<best){best=d;k=i;al=a;raw=r;}
    }
    const S=seg[k];
    if(k===0&&raw<0)al=raw;if(k===m-1&&raw>S.L)al=raw;
    const s=S.c+al,ox=x-(S.x+al*S.tx),oy=y-(S.y+al*S.ty),n=S.tx*oy-S.ty*ox;
    const hw=interp(s,2),u=interp(s,3),q=Math.abs(n)/hw;
    const bank=1-smooth(1,1+margin/Math.max(hw,1),q);
    const taper=smooth(-endMargin,0,s)*(1-smooth(total,total+endMargin,s))*bank;
    if(taper<=0)return null;
    const core=Math.pow(Math.max(0,1-q*q),.7),eddy=smooth(.7,.98,q)*bank;
    const speed=u*(core-ef*eddy)*taper;
    let eta=0;
    if(phase&&s>wave.from_m&&s<wave.to_m){
      const x01=(s-wave.from_m)/(wave.to_m-wave.from_m),idx=(s-wave.from_m)/phase.step,i0=Math.floor(idx),f=idx-i0;
      const ph=phase.v[i0]*(1-f)+phase.v[Math.min(i0+1,phase.v.length-1)]*f;
      eta=wave.amplitude_m*core*taper*Math.sin(Math.PI*x01)*Math.cos(ph);
    }
    let along=speed,lat=0;
    for(const r of rocks){
      const R=Math.max(r.r_m,.5),dx=x-r.x,dy=y-r.y;
      if(Math.abs(dx)>14*R||Math.abs(dy)>14*R)continue;
      const ra=dx*S.tx+dy*S.ty,rl=-dx*S.ty+dy*S.tx,uu=Math.max(speed,0);
      eta+=uu*uu/(2*G)*.8*Math.exp(-(((ra+1.3*R)/(.6*R))**2))*Math.exp(-((rl/R)**2));
      const width=R*(1+Math.max(ra-R,0)/(5*R));
      const wake=ra>R?Math.exp(-(ra-R)/(4*R))*Math.exp(-((rl/width)**2)):0,recirc=ra>R?Math.exp(-(ra-R)/(1.5*R))*Math.exp(-((rl/R)**2)):0;
      lat+=Math.sign(rl)*.5*Math.exp(-(((ra+.5*R)/(1.2*R))**2))*Math.exp(-((rl/(1.3*R))**2))*uu;
      along=along*(1-.9*wake)-.3*uu*recirc;
    }
    return {s,n,q,u,core,eddy,taper,speed,eta,tx:S.tx,ty:S.ty,vx:S.tx*along-S.ty*lat,vy:S.ty*along+S.tx*lat};
  };
}

// Whitewater, current and surface height on a 1.25 m grid, plus the lantern light that falls on the water.
function raceFields(w,ground){
  const rapid=w.harbour.rapids[0],level=w.harbour.waterLevelM,race=w.vaderland.lantern_race;
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  for(const [x,y,hw] of rapid.stations){x0=Math.min(x0,x-hw);x1=Math.max(x1,x+hw);y0=Math.min(y0,y-hw);y1=Math.max(y1,y+hw);}
  for(const r of w.harbour.races)for(const g of r.gates){x0=Math.min(x0,g.center[0]);x1=Math.max(x1,g.center[0]);y0=Math.min(y0,g.center[1]);y1=Math.max(y1,g.center[1]);}
  for(const [x,y] of race.lanterns){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}
  x0-=70;x1+=70;y0-=70;y1+=70;                              // every light pool fades out inside the field
  const cell=1.25,nx=Math.ceil((x1-x0)/cell),ny=Math.ceil((y1-y0)/cell);
  const flow=new Uint8Array(nx*ny*4),light=new Uint8Array(nx*ny*4);
  const sample=rapidSampler(rapid);
  const rocks=w.obstacles.filter(o=>o.role==='rock'&&o.rock&&o.id.startsWith('lr-')&&o.rock.top_m>-.6)
    .map(o=>({x:o.center[0],y:o.center[1],r:o.rock.radius_m,top:o.rock.top_m}));
  const marks=w.obstacles.filter(o=>o.role==='race-mark'&&o.id.startsWith('lr-'));
  const lights=[...race.lanterns.map(([x,y])=>({x,y,c:AMBER,I:.8,R:6})),
    ...marks.map(o=>({x:o.center[0],y:o.center[1],c:new THREE.Color(o.color),I:.45,R:4})),
    {x:race.beacon[0],y:race.beacon[1],c:AMBER,I:1.6,R:18}];
  const bins=new Map();                                     // lights by 40 m cell, so each texel visits only its neighbours
  for(const L of lights){const key=Math.floor(L.x/40)+','+Math.floor(L.y/40);(bins.get(key)||bins.set(key,[]).get(key)).push(L);}
  const emitters=[];let seed=7707;const rnd=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296);
  for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
    const x=x0+(i+.5)*cell,y=y0+(j+.5)*cell,o=(j*nx+i)*4,f=sample(x,y);
    let white=0,vx=0,vy=0,eta=0;
    if(f){
      vx=f.vx;vy=f.vy;eta=f.eta;
      white=smooth(.16,.40,eta)*smooth(2.2,3.4,f.speed)+.22*smooth(2.6,4.,f.speed)+1.4*f.core*f.eddy*f.taper*smooth(1.5,3.,f.u);
      for(const r of rocks){
        const dx=x-r.x,dy=y-r.y;if(Math.abs(dx)>r.r*10||Math.abs(dy)>r.r*10)continue;
        const d=Math.hypot(dx,dy),ra=dx*f.tx+dy*f.ty,rl=-dx*f.ty+dy*f.tx,uu=smooth(.6,2.2,f.u*f.taper);
        if(r.top>-.15){
          const width=r.r*(1+Math.max(ra-r.r,0)/(5*r.r));
          white+=uu*(Math.exp(-(((d-r.r)/1.3)**2))+.8*Math.exp(-(((ra+1.2*r.r)/(.7*r.r))**2))*Math.exp(-((rl/r.r)**2))
            +(ra>r.r?.5*Math.exp(-(ra-r.r)/(5*r.r))*Math.exp(-((rl/width)**2)):0));
        }else white+=uu*(.55*Math.exp(-((d/(1.4*r.r))**2))+(ra>0?.3*Math.exp(-ra/(4*r.r))*Math.exp(-((rl/r.r)**2)):0));
      }
      white=Math.min(1,white);
    }
    const byte=v=>Math.round(THREE.MathUtils.clamp(v,0,1)*255);
    flow[o]=byte(white);flow[o+1]=byte(.5+vx/12);flow[o+2]=byte(.5+vy/12);flow[o+3]=byte(.5+eta/1.6);
    let r=0,g=0,b=0;
    const cx=Math.floor(x/40),cy=Math.floor(y/40);
    for(let a=-1;a<=1;a++)for(let c=-1;c<=1;c++)for(const L of bins.get((cx+a)+','+(cy+c))||[]){
      const d2=(x-L.x)**2+(y-L.y)**2;if(d2>12*L.R*L.R)continue;
      const k=L.I/(1+d2/(L.R*L.R));r+=L.c.r*k;g+=L.c.g*k;b+=L.c.b*k;
    }
    light[o]=Math.min(1,r/(1+r))*255;light[o+1]=Math.min(1,g/(1+g))*255;light[o+2]=Math.min(1,b/(1+b))*255;light[o+3]=255;
    if(white>.5&&emitters.length<420&&rnd()<white*.06&&ground.terrainZ(x,y)<level-.5)emitters.push([x,y,white,vx,vy]);
  }
  const texture=data=>{const t=new THREE.DataTexture(data,nx,ny,THREE.RGBAFormat);t.magFilter=t.minFilter=THREE.LinearFilter;
    t.wrapS=t.wrapT=THREE.ClampToEdgeWrapping;t.needsUpdate=true;return t;};
  return {flow:texture(flow),light:texture(light),area:new THREE.Vector4(x0,y0,nx*cell,ny*cell),texel:new THREE.Vector2(1/nx,1/ny),cell,emitters};
}

// Indexed icosphere, so rocks get smooth normals.
function icosphere(detail){
  const t=(1+Math.sqrt(5))/2;
  let v=[[-1,t,0],[1,t,0],[-1,-t,0],[1,-t,0],[0,-1,t],[0,1,t],[0,-1,-t],[0,1,-t],[t,0,-1],[t,0,1],[-t,0,-1],[-t,0,1]].map(p=>{const l=Math.hypot(...p);return p.map(c=>c/l);});
  let f=[[0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],[1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],[3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],[4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]];
  for(let d=0;d<detail;d++){
    const cache=new Map(),next=[];
    const mid=(a,b)=>{const key=a<b?a+'_'+b:b+'_'+a;if(cache.has(key))return cache.get(key);
      const p=[0,1,2].map(i=>(v[a][i]+v[b][i])/2),l=Math.hypot(...p);v.push(p.map(c=>c/l));cache.set(key,v.length-1);return v.length-1;};
    for(const [a,b,c] of f){const ab=mid(a,b),bc=mid(b,c),ca=mid(c,a);next.push([a,ab,ca],[b,bc,ab],[c,ca,bc],[ab,bc,ca]);}
    f=next;
  }
  return {v,f};
}

// Rocks: an icosphere shrink-wrapped onto each collision hull, lumped slightly inwards, never outside it.
function rockGeometry(rocks){
  const P=[],I=[];
  for(const o of rocks){
    const planes=o.planes,verts=o.vertices,c=[0,0,0];
    for(const p of verts)for(let i=0;i<3;i++)c[i]+=p[i]/verts.length;
    const R=o.rock?.radius_m??Math.max(o.half[0],o.half[1]);
    const {v,f}=icosphere(R>2.5?3:2),base=P.length/3;
    let h=0;for(const ch of o.id)h=(h*31+ch.charCodeAt(0))>>>0;
    const lump=(d)=>{const a=Math.sin(d[0]*3.1+h%7)+Math.sin(d[1]*4.3+h%11)*.8+Math.sin(d[2]*5.7+d[0]*2.+h%13)*.6;return a/2.4;};
    for(const d of v){
      let t=Infinity;
      for(const [nx,ny,nz,off] of planes){const nd=nx*d[0]+ny*d[1]+nz*d[2];if(nd>1e-9)t=Math.min(t,-(nx*c[0]+ny*c[1]+nz*c[2]+off)/nd);}
      const s=t*(.955+.035*lump(d));
      P.push(o.center[0]+c[0]+d[0]*s,o.center[1]+c[1]+d[1]*s,o.center[2]+c[2]+d[2]*s);
    }
    for(const [a,b,cc] of f)I.push(base+a,base+b,base+cc);
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(P,3));g.setIndex(I);g.computeVertexNormals();
  return g;
}

function hullGeometry(list,extra){
  const P=[],A=[];
  for(const o of list){
    for(const face of o.faces)for(const k of face){const v=o.vertices[k];P.push(v[0]+o.center[0],v[1]+o.center[1],v[2]+o.center[2]);A.push(...extra(o));}
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(P,3));
  g.setAttribute('info',new THREE.Float32BufferAttribute(A,2));g.computeVertexNormals();return g;
}

const lightAt=`
uniform sampler2D raceLight;uniform vec4 raceArea;
vec3 raceGlow(vec2 xy){vec2 uv=(xy-raceArea.xy)/raceArea.zw;
  if(any(lessThan(uv,vec2(0.)))||any(greaterThan(uv,vec2(1.))))return vec3(0.);
  vec3 c=texture2D(raceLight,uv).rgb;return c/max(vec3(1e-3),1.-c);}`;

export function buildLanternRace(group,w,uniforms,common,ground){
  const race=w.vaderland.lantern_race;
  if(!race||!w.harbour?.rapids?.length||!ground)return null;
  const level=w.harbour.waterLevelM,root=new THREE.Group();root.name='Lantern Race';group.add(root);
  const fields=raceFields(w,ground);
  const raceUniforms={raceMap:{value:fields.flow},raceLight:{value:fields.light},raceArea:{value:fields.area},
    raceTexel:{value:fields.texel},raceCell:{value:fields.cell},raceLevel:{value:level},raceDeck:{value:race.overlook.center[2]}};
  const U={...uniforms,...raceUniforms};
  const solids=w.obstacles.filter(o=>lanternRaceSolid(o.id));
  const vtx=`varying vec3 p;varying vec3 n;attribute vec2 info;varying vec2 inf;
    void main(){inf=info;p=(modelMatrix*vec4(position,1.)).xyz;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`;

  // Basalt: dark, wet and glossy at the waterline, lichen on the dry tops, warm where lanterns reach.
  const rocks=solids.filter(o=>o.role==='rock');
  const rockMesh=new THREE.Mesh(rockGeometry(rocks),new THREE.ShaderMaterial({uniforms:U,
    vertexShader:`varying vec3 p;varying vec3 n;void main(){p=(modelMatrix*vec4(position,1.)).xyz;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:common+lightAt+`uniform float raceLevel;
    void main(){
      vec3 N=normalize(n),V=normalize(cameraPosition-p);
      float grain=fbm(p.xy*1.9+p.z*.7),vein=fbm(vec2(p.x+p.y,p.z*2.3)*.8);
      vec3 base=mix(vec3(.085,.085,.095),vec3(.16,.155,.15),grain)*(.85+.3*vein);
      float lichen=smoothstep(.58,.76,fbm(p.xy*.55+p.z*.25+7.))*smoothstep(.35,.85,N.z)*smoothstep(raceLevel+.7,raceLevel+1.4,p.z);
      base=mix(base,mix(vec3(.30,.30,.15),vec3(.46,.30,.10),fbm(p.xy*2.1)),lichen*.55);
      float wet=1.-smoothstep(raceLevel+.15,raceLevel+.9,p.z),under=1.-smoothstep(raceLevel-.6,raceLevel+.05,p.z);
      base=mix(base,base*.45,wet);base=mix(base,vec3(.035,.07,.06),under*.7);
      float diffuse=max(dot(N,sun),0.);
      vec3 c=base*(vec3(.30,.33,.40)+vec3(1.,.88,.72)*diffuse*1.15);
      c+=wet*(1.-under)*pow(max(dot(reflect(-V,N),sun),0.),30.)*.35*mix(1.,.2,night);
      c*=mix(1.,.30,night);
      c+=(base*.7+.02)*raceGlow(p.xy)*night*(.35+.65*max(N.z,0.))*.9;
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`}));
  rockMesh.name='Lantern Race rocks';rockMesh.userData.sceneryIds=rocks.map(o=>o.id);root.add(rockMesh);

  // Ramps: chevron decks on the floating ramps and trail tabletop, grooved concrete on the slipway, a lit lip.
  const kinds={waterRamp:0,trailRamp:1,slipway:2};
  const ramps=solids.filter(o=>o.role==='ramp');
  const rampMesh=new THREE.Mesh(hullGeometry(ramps,o=>[o.ramp.heading,kinds[o.skin]??1]),new THREE.ShaderMaterial({uniforms:U,vertexShader:vtx,
    fragmentShader:common+lightAt+`uniform float raceLevel;varying vec2 inf;
    void main(){
      vec3 N=normalize(n);vec2 d=vec2(cos(inf.x),sin(inf.x));float u=dot(p.xy,d),v=dot(p.xy,vec2(-d.y,d.x));
      float kind=inf.y,top=step(.2,N.z);
      vec3 deck;
      if(kind>1.5){
        float groove=smoothstep(.0,.08,abs(fract(u*2.2)-.5)-.38);
        deck=mix(vec3(.30,.29,.27),vec3(.20,.19,.18),groove)*(.8+.3*fbm(p.xy*1.3));
        deck=mix(deck,vec3(.06,.10,.08),1.-smoothstep(raceLevel-.2,raceLevel+.35,p.z));
      }else{
        float chevron=step(.80,fract((u+abs(v)*.8)*.32));
        vec3 accent=kind<.5?vec3(.62,.36,.10):vec3(.55,.32,.08);
        deck=mix(vec3(.045,.045,.052),accent,chevron);
        if(kind<.5)deck=mix(deck,vec3(.02,.05,.05),1.-smoothstep(raceLevel-.1,raceLevel+.1,p.z));
      }
      vec3 c=mix(vec3(.07,.07,.08),deck,top)*(vec3(.30,.33,.42)+vec3(.95,.82,.66)*max(dot(N,sun),0.));
      c*=mix(1.,.32,night);c+=mix(vec3(.07,.07,.08),deck,top)*raceGlow(p.xy)*night*2.5;
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`}));
  rampMesh.name='Lantern Race ramps';rampMesh.userData.sceneryIds=ramps.map(o=>o.id);root.add(rampMesh);

  // Pontoon floats under the floating ramps and amber lip lamps along each launch edge.
  const floats=[],lips=[];
  for(const o of ramps.filter(o=>o.ramp?.floating)){
    const h=o.ramp.heading,ca=Math.cos(h),sa=Math.sin(h),L=o.ramp.length_m,W=o.ramp.width_m,[cx,cy]=o.center;
    for(const s of [-1,1]){const v=s*(W/2-.45);floats.push([cx-v*sa,cy+v*ca,level-.12,h,L+1.2]);}
    for(let k=0;k<=6;k++){const v=(k/6-.5)*W*.92;lips.push([cx+L/2*ca-v*sa,cy+L/2*sa+v*ca,level+o.ramp.height_m+.08]);}
  }
  const floatMat=new THREE.MeshStandardMaterial({color:'#1b1d22',roughness:.55,metalness:.35});
  const floatMesh=new THREE.InstancedMesh(new THREE.CylinderGeometry(.45,.45,1,14).rotateZ(Math.PI/2),floatMat,floats.length);
  const M=new THREE.Matrix4(),Q=new THREE.Quaternion(),Z=new THREE.Vector3(0,0,1),S=new THREE.Vector3(),T=new THREE.Vector3();
  floats.forEach(([x,y,z,h,L],k)=>floatMesh.setMatrixAt(k,M.compose(T.set(x,y,z),Q.setFromAxisAngle(Z,h),S.set(L,1,1))));
  floatMesh.name='Lantern Race ramp floats';root.add(floatMesh);
  const glowMat=new THREE.MeshBasicMaterial({color:AMBER.clone().multiplyScalar(2.2),toneMapped:false});
  const lipMesh=new THREE.InstancedMesh(new THREE.SphereGeometry(.09,8,6),glowMat,lips.length);
  lips.forEach(([x,y,z],k)=>lipMesh.setMatrixAt(k,M.makeTranslation(x,y,z)));lipMesh.name='Lantern Race lip lamps';root.add(lipMesh);

  // Overlook: a basalt shelf with columnar faces and a weathered flat top, a landing ring and V, edge lamps, four banners.
  const overlook=solids.find(o=>o.id==='lr-overlook'),ov=race.overlook;
  const plinth=new THREE.Mesh(hullGeometry([overlook],()=>[0,0]),new THREE.ShaderMaterial({uniforms:U,vertexShader:vtx,
    fragmentShader:common+lightAt+`uniform float raceDeck;varying vec2 inf;
    void main(){
      vec3 N=normalize(n);float top=smoothstep(.55,.75,N.z);
      vec2 t=normalize(vec2(-N.y,N.x)+1e-5);float u=dot(p.xy,t)/1.7,id=floor(u);
      float joint=smoothstep(.84,.97,abs(fract(u)-.5)*2.);
      float crack=smoothstep(.90,.98,abs(fract(p.z/2.4+hash(vec2(id,7.)))-.5)*2.);
      float streak=fbm(vec2(u*2.1,p.z*.35));
      vec3 side=mix(vec3(.085,.085,.095),vec3(.17,.165,.16),hash(vec2(id,3.))*.6+streak*.4)*(1.-.55*max(joint,crack));
      float moss=smoothstep(.55,.78,fbm(p.xy*.45+3.))*smoothstep(-6.,-1.,p.z-raceDeck);
      side=mix(side,vec3(.20,.24,.12),moss*.35);
      vec3 shelfTop=mix(vec3(.13,.13,.135),vec3(.20,.195,.18),fbm(p.xy*.7))*(1.-.35*smoothstep(.62,.80,fbm(p.xy*.23+9.)));
      vec3 base=mix(side,shelfTop,top);
      vec3 c=base*(vec3(.30,.33,.42)+vec3(.95,.82,.66)*max(dot(N,sun),0.)*1.1);
      c*=mix(1.,.30,night);c+=(base*.7+.02)*raceGlow(p.xy)*night*.8;
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`}));
  plinth.name='Lantern Race basalt shelf';plinth.userData.sceneryIds=['lr-overlook'];root.add(plinth);
  const deckMat=new THREE.ShaderMaterial({uniforms:{night:uniforms.night,clock:uniforms.clock},transparent:true,depthWrite:false,
    vertexShader:`varying vec2 q;void main(){q=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night,clock;varying vec2 q;
    void main(){
      vec2 a=abs(q);if(a.x>14.||a.y>10.)discard;
      float r=length(q)/9.;
      float ring=smoothstep(.88,.90,r)*(1.-smoothstep(.95,.97,r));
      vec2 s=q/9.;float vee=step(abs(s.x*.9-abs(s.y)*1.6+.18),.06)*step(s.x,.40)*step(-.36,s.x);
      float edge=step(13.55,a.x)+step(9.55,a.y);
      float lamps=edge*step(.9,fract((q.x+q.y)*.25));
      vec3 c=vec3(.94,.90,.80)*(ring+vee*.85)*mix(.32,.8,night)+vec3(1.,.72,.38)*lamps*(.5+1.6*night);
      gl_FragColor=vec4(c,clamp(ring+vee+lamps,0.,1.)*.92);
    }`});
  const deck=new THREE.Mesh(new THREE.PlaneGeometry(28.2,20.2),deckMat);
  deck.position.set(ov.center[0],ov.center[1],ov.center[2]+.03);deck.rotation.z=ov.heading;deck.renderOrder=3;deck.name='Overlook landing ring';root.add(deck);
  const banners=new THREE.BufferGeometry(),BP=[],BU=[];
  solids.filter(o=>o.id.startsWith('lr-banner-pole-')).forEach((o,k)=>{
    const [x,y]=o.center,top=o.center[2]+o.half[2]-.25,ca=Math.cos(ov.heading+Math.PI/2),sa=Math.sin(ov.heading+Math.PI/2);
    const quad=[[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]];
    for(const [s,t] of quad){BP.push(x+ca*(.15+s*.95),y+sa*(.15+s*.95),top-3.1*(1-t));BU.push(s,t,k%2);}
  });
  banners.setAttribute('position',new THREE.Float32BufferAttribute(BP,3));banners.setAttribute('uvk',new THREE.Float32BufferAttribute(BU,3));
  const bannerMesh=new THREE.Mesh(banners,new THREE.ShaderMaterial({uniforms:{night:uniforms.night,clock:uniforms.clock},side:THREE.DoubleSide,
    vertexShader:`attribute vec3 uvk;varying vec3 b;uniform float clock;
      void main(){b=uvk;vec3 q=position;float sway=uvk.x*(.18*sin(clock*1.7+uvk.y*2.+position.x)+.06*sin(clock*4.1+uvk.x*5.));
        q.xy+=vec2(sway,-sway*.6);gl_Position=projectionMatrix*viewMatrix*vec4(q,1.);}`,
    fragmentShader:`uniform float night;varying vec3 b;
      void main(){
        vec3 cloth=b.z<.5?vec3(.62,.30,.07):vec3(.30,.16,.46);
        vec2 s=vec2(b.x-.5,b.y-.55);float vee=step(abs(s.y-abs(s.x)*1.5+.12),.05)*step(s.y,.25)*step(-.25,s.y);
        vec3 c=mix(cloth,vec3(.95,.90,.78),vee)*mix(1.,.45,night)+cloth*night*.35;
        gl_FragColor=vec4(c,1.);
      }`}));
  bannerMesh.name='Overlook banners';root.add(bannerMesh);
  const poles=solids.filter(o=>o.kind==='cylinder'&&o.role==='architecture');
  const poleMesh=new THREE.InstancedMesh(new THREE.CylinderGeometry(1,1,1,10).rotateX(Math.PI/2),new THREE.MeshStandardMaterial({color:'#17181c',roughness:.5,metalness:.6}),poles.length);
  poles.forEach((o,k)=>poleMesh.setMatrixAt(k,M.compose(T.set(...o.center),Q.identity(),S.set(o.half[0],o.half[1],o.half[2]*2))));
  poleMesh.name='Lantern Race masts and poles';poleMesh.userData.sceneryIds=poles.map(o=>o.id);root.add(poleMesh);

  // The Lantern Rock beacon: a lantern housing that breathes slowly, with a halo after dusk.
  const [bx,by,bz]=race.beacon;
  const housing=new THREE.Mesh(new THREE.CylinderGeometry(.55,.7,1.1,8).rotateX(Math.PI/2),new THREE.MeshStandardMaterial({color:'#1a1b1f',roughness:.4,metalness:.7}));
  housing.position.set(bx,by,bz-.4);root.add(housing);
  const lampMat=new THREE.MeshBasicMaterial({color:AMBER.clone().multiplyScalar(3),toneMapped:false});
  const lamp=new THREE.Mesh(new THREE.SphereGeometry(.42,16,12),lampMat);lamp.position.set(bx,by,bz+.35);lamp.name='Lantern Rock beacon';root.add(lamp);
  const haloMat=new THREE.ShaderMaterial({uniforms:{night:uniforms.night,clock:uniforms.clock},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`varying vec2 q;void main(){q=uv*2.-1.;vec4 c=modelViewMatrix*vec4(0.,0.,0.,1.);c.xy+=position.xy;gl_Position=projectionMatrix*c;}`,
    fragmentShader:`uniform float night,clock;varying vec2 q;
      void main(){float r=length(q);float breathe=.75+.25*sin(clock*1.57);
        gl_FragColor=vec4(vec3(1.,.64,.28)*exp(-r*r*5.)*(.08+.55*night)*breathe,1.);}`});
  const halo=new THREE.Mesh(new THREE.PlaneGeometry(14,14),haloMat);halo.position.set(bx,by,bz+.35);halo.renderOrder=5;halo.frustumCulled=false;root.add(halo);

  // Bank and trail lanterns: short dark posts, warm heads, and pools of light draped on the ground.
  const posts=new THREE.InstancedMesh(new THREE.CylinderGeometry(.06,.08,1,6).rotateX(Math.PI/2),new THREE.MeshStandardMaterial({color:'#16171a',roughness:.6,metalness:.5}),race.lanterns.length);
  const heads=new THREE.InstancedMesh(new THREE.BoxGeometry(.26,.26,.34),new THREE.MeshBasicMaterial({color:AMBER.clone().multiplyScalar(1.6),toneMapped:false}),race.lanterns.length);
  race.lanterns.forEach(([x,y,z],k)=>{posts.setMatrixAt(k,M.compose(T.set(x,y,z+.8),Q.identity(),S.set(1,1,1.6)));heads.setMatrixAt(k,M.makeTranslation(x,y,z+1.75));});
  posts.name='Lantern posts';heads.name='Lantern heads';root.add(posts,heads);
  const tris=[];
  for(const [x,y] of race.lanterns){
    const ring=[];for(let k=0;k<10;k++){const a=k/10*Math.PI*2;ring.push({x:x+7*Math.cos(a),y:y+7*Math.sin(a),a:[Math.cos(a),Math.sin(a)]});}
    for(let k=0;k<10;k++)tris.push([{x,y,a:[0,0]},ring[k],ring[(k+1)%10]]);
  }
  const draped=ground.drapeTriangles(tris,{offset:.07});
  const pools=new THREE.BufferGeometry();pools.setAttribute('position',new THREE.Float32BufferAttribute(draped.pos,3));
  pools.setAttribute('local',new THREE.Float32BufferAttribute(draped.att,2));
  const poolMesh=new THREE.Mesh(pools,new THREE.ShaderMaterial({uniforms:{night:uniforms.night,clock:uniforms.clock},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute vec2 local;varying vec2 l;varying vec3 wp;void main(){l=local;wp=position;gl_Position=projectionMatrix*viewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night,clock;varying vec2 l;varying vec3 wp;
      void main(){float r=length(l);float flicker=.92+.08*sin(clock*7.+wp.x*1.3)*sin(clock*3.1+wp.y);
        gl_FragColor=vec4(vec3(1.,.62,.26)*pow(max(0.,1.-r),2.2)*.30*night*flicker,1.);}`}));
  poolMesh.name='Lantern light pools';poolMesh.renderOrder=2;root.add(poolMesh);

  // Spray thrown up where the race breaks over rocks and wave crests.
  const per=7,count=fields.emitters.length*per,SP=new Float32Array(count*3),SA=new Float32Array(count*4);
  let seed=901;const rnd=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296);
  fields.emitters.forEach(([x,y,white,vx,vy],e)=>{
    for(let k=0;k<per;k++){const i=e*per+k;
      SP.set([x+(rnd()-.5)*2.2,y+(rnd()-.5)*2.2,level],i*3);
      SA.set([rnd(),.6+rnd()*.8,white,Math.atan2(vy,vx)+(rnd()-.5)*1.2],i*4);}
  });
  const spray=new THREE.BufferGeometry();spray.setAttribute('position',new THREE.BufferAttribute(SP,3));spray.setAttribute('seed',new THREE.BufferAttribute(SA,4));
  const sprayMesh=new THREE.Points(spray,new THREE.ShaderMaterial({uniforms:{...U},transparent:true,depthWrite:false,
    vertexShader:lightAt+`attribute vec4 seed;uniform float clock;varying float a;varying vec3 glow;
      void main(){
        float life=fract(clock/seed.y+seed.x),t=life*seed.y;
        vec3 q=position;vec2 dir=vec2(cos(seed.w),sin(seed.w));
        q.xy+=dir*t*(1.2+1.6*seed.z);q.z+=(1.4+2.2*seed.z*seed.x)*t-4.9*t*t;
        a=smoothstep(0.,.12,life)*(1.-smoothstep(.55,1.,life))*smoothstep(-.2,.1,q.z-position.z);
        glow=raceGlow(q.xy);
        vec4 mv=viewMatrix*vec4(q,1.);gl_Position=projectionMatrix*mv;
        gl_PointSize=clamp((.35+.9*seed.z)*900./-mv.z,1.,40.);
      }`,
    fragmentShader:`uniform float night;varying float a;varying vec3 glow;
      void main(){vec2 c=gl_PointCoord*2.-1.;float r=dot(c,c);if(r>1.)discard;
        vec3 col=vec3(.86,.90,.90)*mix(1.,.14,night)+glow*night*.8;
        gl_FragColor=vec4(col,a*(1.-r)*.42);}`}));
  sprayMesh.name='Lantern Race spray';sprayMesh.frustumCulled=false;root.add(sprayMesh);

  // Water: current-advected foam, aerated colour and the standing-wave relief, for the harbour shader.
  const water={
    uniforms:raceUniforms,
    declarations:'uniform sampler2D raceMap;uniform sampler2D raceLight;uniform vec4 raceArea;uniform vec2 raceTexel;uniform float raceCell;',
    normal:`
      vec4 raceTex=vec4(0.,.5,.5,.5);float raceIn=0.,raceEdge=0.;
      vec2 raceUV=(p.xy-raceArea.xy)/raceArea.zw;
      if(all(greaterThan(raceUV,vec2(0.)))&&all(lessThan(raceUV,vec2(1.)))){
        raceIn=1.;raceTex=texture2D(raceMap,raceUV);
        float ex=texture2D(raceMap,raceUV+vec2(raceTexel.x,0.)).a-texture2D(raceMap,raceUV-vec2(raceTexel.x,0.)).a;
        float ey=texture2D(raceMap,raceUV+vec2(0.,raceTexel.y)).a-texture2D(raceMap,raceUV-vec2(0.,raceTexel.y)).a;
        raceEdge=smoothstep(0.,.05,min(min(raceUV.x,1.-raceUV.x),min(raceUV.y,1.-raceUV.y)));
        vec2 raceGrad=vec2(ex,ey)*1.6/(2.*raceCell);
        vec2 raceVel=(raceTex.gb-.5)*12.;
        float chop=smoothstep(.8,3.5,length(raceVel))*raceEdge;
        float rt=mix(clock,waterClock,physicalTide);
        vec2 jitter=vec2(noise2(p.xy*2.7-raceVel*rt*.8)-.5,noise2(p.xy*2.7+31.-raceVel*rt*.8)-.5)*.16*chop;
        norm=normalize(norm+vec3(-raceGrad*raceEdge+jitter,0.));
      }`,
    colour:`
      if(raceIn>.5){
        vec2 vel=(raceTex.gb-.5)*12.;float spd=length(vel),white=raceTex.r*raceEdge;
        vec2 along=spd>.05?vel/spd:vec2(1.,0.),across=vec2(-along.y,along.x);
        float rt=mix(clock,waterClock,physicalTide);
        // Foam is advected with the current in two phases and stretched along the flow.
        float ph0=fract(rt*.22),ph1=fract(rt*.22+.5),blend=abs(ph0-.5)*2.;
        vec2 q0=p.xy-vel*ph0*4.5,q1=p.xy-vel*ph1*4.5;
        float f0=fbm(vec2(dot(q0,along)*.30,dot(q0,across)*1.15)),f1=fbm(vec2(dot(q1,along)*.30,dot(q1,across)*1.15)+17.);
        float tex=mix(f0,f1,blend)+.30*(noise2((p.xy-vel*rt*.6)*1.9)-.5);
        float foam=smoothstep(.70-.44*white,.84-.36*white,tex)*smoothstep(.05,.25,white);
        float lace=smoothstep(.60,.66,fbm((p.xy-vel*rt*.45)*2.4))*smoothstep(.2,.65,white)*.45;
        vec3 glow;{vec3 lc=texture2D(raceLight,raceUV).rgb;glow=lc/max(vec3(1e-3),1.-lc)*raceEdge;}
        surfaceColor=mix(surfaceColor,vec3(.10,.24,.23)*mix(1.,.20,night),smoothstep(.1,.7,white)*.28);
        surfaceColor+=glow*night*.05;
        vec3 foamCol=vec3(.84,.88,.87)*(.45+.55*max(dot(norm,sun),0.))*mix(1.,.09,night)+glow*night*.40;
        surfaceColor=mix(surfaceColor,foamCol,clamp(foam+lace,0.,1.)*.90);
      }`,
  };
  return {water,stats:{rocks:rocks.length,ramps:ramps.length,lanterns:race.lanterns.length,spray:count},
    dispose(){fields.flow.dispose();fields.light.dispose();}};
}
