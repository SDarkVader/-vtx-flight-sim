// Meridian atmosphere: render-only weather over the city. Deterministic in the presentation
// clock; it never touches physics, wind or the world fingerprint.
//
// Lit streets create a diffuse sky glow. The opaque sky shader uses this function,
// so foreground scenery keeps its own contrast and depth.
import * as THREE from 'three';
import {cityDensity,DENSITY_BOUNDS as LB} from './city-density.js';

export const citySkyGlow=`
float meridianSkyGlow(vec3 ray){
  const vec3 spread=vec3(1450.,1350.,260.);
  vec3 origin=(cameraPosition-vec3(440.,2760.,70.))/spread;
  vec3 direction=ray/spread;
  float distance=max(0.,-dot(origin,direction)/dot(direction,direction));
  vec3 closest=origin+direction*distance;
  float horizon=smoothstep(-.18,.04,ray.z)*exp(-max(0.,ray.z-.02)*3.8);
  return exp(-dot(closest,closest))*smoothstep(0.,160.,distance)*horizon;
}`;

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
uniform sampler2D cityLight;uniform float time,weather;
float h1(vec2 a){vec3 p=fract(vec3(a.xyx)*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
float n2(vec2 a){vec2 i=floor(a),f=fract(a);f=f*f*(3.-2.*f);
  return mix(mix(h1(i),h1(i+vec2(1,0)),f.x),mix(h1(i+vec2(0,1)),h1(i+1.),f.x),f.y);}
float fog2(vec2 xy){vec2 d=vec2(time*3.1,time*1.4);
  return .55*n2((xy+d)/900.)+.30*n2((xy-d*1.7)/330.+7.)+.15*n2((xy+d*2.3)/120.+3.);}
vec3 lightAt(vec2 xy){vec2 uv=(xy-vec2(${LB.x0}.,${LB.y0}.))/vec2(${LB.x1-LB.x0}.,${LB.y1-LB.y0}.);
  if(any(lessThan(uv,vec2(0.)))||any(greaterThan(uv,vec2(1.))))return vec3(0.);return texture2D(cityLight,uv).rgb;}
`;

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
      ${rain?'':'p.z=max(p.z,24.+seed.w*230.);'}
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
  const u={cityLight:{value:cityLightMap(density)},time:{value:0},weather:{value:.7}};
  const root=new THREE.Group();root.name='Meridian atmosphere';group.add(root);
  root.add(particles(u,9000,false),particles(u,14000,true));
  return {update(seconds){
    u.time.value=seconds;
    u.weather.value=.55+.45*Math.sin(seconds*2*Math.PI/900+1.3);
  }};
}
