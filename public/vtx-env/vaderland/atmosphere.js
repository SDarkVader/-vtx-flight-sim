// Meridian atmosphere: render-only weather over the city. Deterministic in the presentation
// clock; it never touches physics, wind or the world fingerprint.
//
// Broody rather than bright: a charcoal haze dome over the city, lit from below only where
// people are (the same floor-area density that places street light), so the core glows warm
// through the murk and the outskirts sink into ground fog. The fog clears around the viewer,
// so streets come alive on approach. Sparse motes drift in lit areas and rain cells wander.
import * as THREE from 'three';
import {cityDensity,DENSITY_BOUNDS as LB} from './city-density.js';

const B={x0:-3300,x1:3100,y0:500,y1:5800};
const DOME={c:new THREE.Vector3(-100,3050,20),r:new THREE.Vector3(3700,3050,430)};

// ---- the city's light, from population density: sodium amber, a whiter core ---------------
function cityLightMap(density){
  const {nx,ny,level}=density,scale=4,W=nx*scale,H=ny*scale;
  const raw=document.createElement('canvas');raw.width=nx;raw.height=ny;
  const g=raw.getContext('2d'),img=g.createImageData(nx,ny);
  const smooth=(a,b,x)=>{const t=Math.min(1,Math.max(0,(x-a)/(b-a)));return t*t*(3-2*t);};
  for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
    const d=level[j*nx+i],k=((ny-1-j)*nx+i)*4,core=smooth(.72,.97,d);
    const warm=Math.pow(d,1.5)*.85;
    let r=warm*1.0+core*.30,gr=warm*.50+core*.27,b=warm*.18+core*.24;
    const x=LB.x0+(i+.5)*LB.cell,y=LB.y0+(j+.5)*LB.cell,par=Math.exp(-((x-90)**2+(y-2383)**2)/(2*260*260));
    r+=par*.04;gr+=par*.10;b+=par*.14;                                  // a faint cool trace at Parallax only
    img.data[k]=Math.min(255,r*255);img.data[k+1]=Math.min(255,gr*255);img.data[k+2]=Math.min(255,b*255);img.data[k+3]=255;
  }
  g.putImageData(img,0,0);
  const out=document.createElement('canvas');out.width=W;out.height=H;
  const c=out.getContext('2d');c.imageSmoothingEnabled=true;c.filter='blur(3px)';c.drawImage(raw,0,0,W,H);
  const tex=new THREE.CanvasTexture(out);tex.colorSpace=THREE.NoColorSpace;tex.minFilter=THREE.LinearFilter;tex.magFilter=THREE.LinearFilter;
  return tex;
}

const shared=`
uniform sampler2D cityLight;uniform float time,weather,glowGain,flash,density;uniform vec3 hazeColour;
float h1(vec2 a){vec3 p=fract(vec3(a.xyx)*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
float n2(vec2 a){vec2 i=floor(a),f=fract(a);f=f*f*(3.-2.*f);
  return mix(mix(h1(i),h1(i+vec2(1,0)),f.x),mix(h1(i+vec2(0,1)),h1(i+1.),f.x),f.y);}
float fog2(vec2 xy){vec2 d=vec2(time*3.1,time*1.4);
  return .55*n2((xy+d)/900.)+.30*n2((xy-d*1.7)/330.+7.)+.15*n2((xy+d*2.3)/120.+3.);}
vec3 lightAt(vec2 xy){vec2 uv=(xy-vec2(${LB.x0}.,${LB.y0}.))/vec2(${LB.x1-LB.x0}.,${LB.y1-LB.y0}.);
  if(any(lessThan(uv,vec2(0.)))||any(greaterThan(uv,vec2(1.))))return vec3(0.);return texture2D(cityLight,uv).rgb;}
`;

// ---- the haze dome ------------------------------------------------------------------------------
function hazeDome(u){
  const m=new THREE.ShaderMaterial({uniforms:u,transparent:true,depthWrite:false,side:THREE.FrontSide,fog:false,toneMapped:false,
    vertexShader:`varying vec3 world;void main(){vec4 p=modelMatrix*vec4(position,1.);world=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,
    fragmentShader:shared+`uniform vec3 domeC,domeR;uniform float inside,clearM;varying vec3 world;
    void main(){
      vec3 dir=normalize(world-cameraPosition);
      vec3 o=(cameraPosition-domeC)/domeR,d=dir/domeR;
      float a=dot(d,d),b=dot(o,d),c=dot(o,o)-1.,disc=b*b-a*c;if(disc<0.)discard;
      float s=sqrt(disc),t0=(-b-s)/a,t1=(-b+s)/a;
      t0=max(t0,clearM);
      if(dir.z<0.)t1=min(t1,(domeC.z-cameraPosition.z)/dir.z);   // stop at the ground datum
      if(t1<=t0)discard;
      // March the chord in 8 steps: a single midpoint jumps in height where rays stop meeting the
      // ground inside the dome, which drew a hard-edged band across the city.
      float seg=(t1-t0)/8.,tau=0.,wsum=1e-4;vec3 litSum=vec3(0.);
      for(int k=0;k<8;k++){
        vec3 q=cameraPosition+dir*(t0+(float(k)+.5)*seg);
        float h=max(0.,q.z-domeC.z);
        float edge=smoothstep(0.,.55,1.-length((q-domeC)/domeR));
        float dens=(.20+.80*fog2(q.xy))*exp(-h/170.)*(.45+.75*weather)*edge;
        tau+=dens*seg;
        vec3 l=lightAt(q.xy)*glowGain*exp(-h/330.);
        litSum+=l*dens;wsum+=dens;
      }
      float alpha=1.-exp(-tau*.00055*density);
      vec3 col=hazeColour*(1.+flash*2.5)+litSum/wsum;
      gl_FragColor=vec4(col,alpha*.92);
    }`});
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(1,64,32),m);
  mesh.scale.copy(DOME.r);mesh.position.copy(DOME.c);mesh.renderOrder=5;mesh.frustumCulled=false;mesh.name='Meridian haze dome';
  return mesh;
}

// ---- layered fog banks inside the city (depth-tested against buildings) -------------------------
function fogBanks(u){
  const group=new THREE.Group();group.name='Meridian fog banks';
  const heights=[14,32,58,92,136,190];
  heights.forEach((z,i)=>{
    const m=new THREE.ShaderMaterial({uniforms:{...u,layer:{value:i/heights.length}},transparent:true,depthWrite:false,side:THREE.DoubleSide,fog:false,toneMapped:false,
      vertexShader:`varying vec3 world;void main(){vec4 p=modelMatrix*vec4(position,1.);world=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,
      fragmentShader:shared+`uniform float layer,inside,clearM;varying vec3 world;
      void main(){
        float d=length(world-cameraPosition);
        float near=smoothstep(clearM,clearM*3.2,d);
        float far=1.-smoothstep(5200.,7800.,d);
        float bank=fog2(world.xy*(1.+layer*.6)+layer*4000.);
        vec3 below=lightAt(world.xy);float busy=smoothstep(.05,.55,dot(below,vec3(.5,.35,.15)));
        float dens=smoothstep(.36-.18*weather,.85,bank)*(1.-layer*.55)*near*far*inside*mix(1.2,.5,busy);
        vec3 V=normalize(cameraPosition-world);float grazing=1.-abs(V.z);
        vec2 edge=min(world.xy-vec2(${B.x0}.,${B.y0}.),vec2(${B.x1}.,${B.y1}.)-world.xy);
        float alpha=dens*(.08+.14*grazing)*smoothstep(.07,.26,abs(V.z))*(.55+.6*weather)*density*smoothstep(0.,900.,min(edge.x,edge.y));
        vec3 lit=below*glowGain*(1.15-layer)*(1.+.6*bank);
        gl_FragColor=vec4(hazeColour*(1.+flash*2.)+lit,alpha);
        if(alpha<.003)discard;
      }`});
    const plane=new THREE.Mesh(new THREE.PlaneGeometry(B.x1-B.x0,B.y1-B.y0),m);
    plane.position.set((B.x0+B.x1)/2,(B.y0+B.y1)/2,DOME.c.z+z);plane.renderOrder=4;plane.frustumCulled=false;
    group.add(plane);
  });
  return group;
}

// ---- drifting light motes and wandering rain cells around the viewer ---------------------------
function particles(u,count,rain){
  const seeds=new Float32Array(count*4);
  let state=rain?90211:40961;const next=()=>((state=Math.imul(state,1664525)+1013904223>>>0)/4294967296);
  for(let i=0;i<count*4;i++)seeds[i]=next();
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(count*3),3));
  g.setAttribute('seed',new THREE.Float32BufferAttribute(seeds,4));
  const box=rain?new THREE.Vector3(420,420,240):new THREE.Vector3(900,900,260);
  const m=new THREE.ShaderMaterial({uniforms:{...u,box:{value:box}},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,fog:false,toneMapped:false,
    vertexShader:shared+`attribute vec4 seed;uniform vec3 box;varying vec3 tint;varying float fade;
    void main(){
      vec3 drift=${rain?'vec3(2.,1.,-17.-seed.w*6.)':'vec3(3.1,1.4,.35+seed.w*.6)'}*time;
      vec3 rel=fract(seed.xyz+(drift-cameraPosition)/box)-.5;
      vec3 p=cameraPosition+rel*box;
      ${rain?'':'p.z=max(p.z,'+DOME.c.z.toFixed(1)+'+4.+seed.w*230.);'}
      float d=length(p-cameraPosition);
      float edge=1.-smoothstep(.36,.5,max(abs(rel.x),max(abs(rel.y),abs(rel.z))));
      float cell=${rain?'smoothstep(.58,.70,n2(p.xy/1600.+vec2(time*.004,-time*.003)))*(.4+.6*weather)':'(.35+.65*fog2(p.xy))*(.5+.6*weather)'};
      vec3 l=lightAt(p.xy);
      tint=${rain?'vec3(.30,.33,.38)+l*.7':'l*2.0+vec3(.02,.02,.025)*(.5+.5*sin(time*2.+seed.w*40.))'};
      fade=edge*cell*smoothstep(2.,25.,d);
      vec4 view=viewMatrix*vec4(p,1.);
      gl_Position=projectionMatrix*view;
      gl_PointSize=clamp(${rain?'320.':'260.'}/max(1.,-view.z),${rain?'1.2,6.':'1.2,7.'});
    }`,
    fragmentShader:`varying vec3 tint;varying float fade;
    void main(){vec2 q=gl_PointCoord-.5;
      float shape=${rain?'(1.-smoothstep(.02,.06,abs(q.x)))*(1.-smoothstep(.35,.5,abs(q.y)))':'exp(-dot(q,q)*14.)'};
      gl_FragColor=vec4(tint*shape*fade*${rain?'.28':'1.'},1.);}`});
  const pts=new THREE.Points(g,m);pts.frustumCulled=false;pts.renderOrder=6;pts.name=rain?'Rain cells':'Light motes';
  return pts;
}

export function buildAtmosphere(group,w,density=cityDensity(w)){
  const u={cityLight:{value:cityLightMap(density)},time:{value:0},weather:{value:.7},glowGain:{value:1},flash:{value:0},
    hazeColour:{value:new THREE.Color(.20,.17,.32)},density:{value:1},domeC:{value:DOME.c},domeR:{value:DOME.r},inside:{value:0},clearM:{value:420}};
  const root=new THREE.Group();root.name='Meridian atmosphere';group.add(root);
  const dome=hazeDome(u),banks=fogBanks(u),motes=particles(u,9000,false),rain=particles(u,14000,true);
  root.add(dome,banks,motes,rain);
  const looks={day:{haze:[.50,.53,.58],glow:.06,density:.28},dusk:{haze:[.10,.10,.135],glow:.80,density:1},night:{haze:[.028,.030,.042],glow:1.0,density:1}};
  return {update(cam,seconds,mode){
    const t=seconds;u.time.value=t;
    u.weather.value=.55+.45*Math.sin(t*2*Math.PI/900+1.3);
    const look=looks[mode]??looks.day;u.hazeColour.value.setRGB(...look.haze);u.glowGain.value=look.glow;u.density.value=look.density;
    const k=Math.floor(t*9),r=Math.sin(k*12.9898)*43758.5453;
    u.flash.value=mode!=='day'&&(r-Math.floor(r))>.9975?.35:0;
    const q=cam.position.clone().sub(DOME.c).divide(DOME.r);
    const inside=q.lengthSq()<1&&cam.position.z>DOME.c.z;
    u.inside.value=inside?1:0;dome.material.side=inside?THREE.BackSide:THREE.FrontSide;
  }};
}
