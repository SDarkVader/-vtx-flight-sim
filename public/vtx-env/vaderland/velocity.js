import * as THREE from 'three';
import {meridianRain} from './parallax-court.js';

// Arc length and cross-track position follow the same centreline as the native timer.
// Clipping each section against the actual terrain keeps the racing surface continuous over crests.
export function buildNightVelocity(group, world, ground, uniforms) {
  const course = world.vaderland.speedway;
  const route = world.vaderland.routes.find(road => road.name === course.road);
  const points = route.points.slice(0, -1), half = route.width_m / 2;
  const sections = [], lengths = [0], count = points.length;
  for (let i = 0; i < count; i++) {
    const a = points[i], b = points[(i + 1) % count];
    const distance = Math.hypot(b[0] - a[0], b[1] - a[1]);
    sections.push([(b[0] - a[0]) / distance, (b[1] - a[1]) / distance]);
    lengths.push(lengths[i] + distance);
  }
  const edges = points.map(([x, y], i) => {
    const a = sections[(i + count - 1) % count], b = sections[i];
    const denom = 1 + a[0] * b[0] + a[1] * b[1];
    const nx = -(a[1] + b[1]) / denom, ny = (a[0] + b[0]) / denom;
    return [-half, half].map(u => ({x: x + u * nx, y: y + u * ny, u}));
  });
  const surface = [];
  const lamps = [-1,1].map(sign => course.lights.filter(l => l.sign===sign));
  for (let i = 0; i < count; i++) {
    const mid=(lengths[i]+lengths[i+1])*.5;
    const local=lamps.flatMap(side=>{
      let next=side.findIndex(l=>l.station_m>=mid);
      if(next<0)next=0;
      return [...side[(next+side.length-1)%side.length].xyz,...side[next].xyz];
    });
    const at = (j, station) => edges[j % count].map(p => ({x:p.x, y:p.y, a:[p.u,station,...local]}));
    const [a,b] = at(i,lengths[i]), [c,d] = at(i+1,lengths[i+1]);
    surface.push([a,c,b],[c,d,b]);
  }
  const baked = ground.drapeTriangles(surface, {offset:.049});
  const geo = new THREE.BufferGeometry();
  const interleaved=new THREE.InterleavedBuffer(new Float32Array(baked.att),14);
  geo.setAttribute('alignment',new THREE.InterleavedBufferAttribute(interleaved,2,0));
  for(let j=0;j<4;j++)geo.setAttribute('lamp'+j,new THREE.InterleavedBufferAttribute(interleaved,3,2+j*3));
  for (const [key, values, size] of [['position',baked.pos,3],['normal',baked.nor,3]]) {
    geo.setAttribute(key,new THREE.Float32BufferAttribute(values,size));
  }
  const court=world.vaderland.parallax_court;
  const materialUniforms=court?{...uniforms,avenueStorefronts:{value:court.storefronts.map(p=>new THREE.Vector3(...p))}}:uniforms;
  const mat = new THREE.ShaderMaterial({uniforms:materialUniforms,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-3,polygonOffsetUnits:-6,
    vertexShader:`attribute vec2 alignment;attribute vec3 lamp0,lamp1,lamp2,lamp3;varying vec3 lights[4];varying vec2 road;varying vec3 wp,up;
      void main(){road=alignment;lights[0]=lamp0;lights[1]=lamp1;lights[2]=lamp2;lights[3]=lamp3;wp=position;up=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform sampler2D asphaltColor,asphaltNormal,asphaltRough,daySky,nightSky;
      uniform sampler2D cityDayReflection,cityNightReflection;
      uniform float night,blueHour,cityReflectionReady;varying vec3 lights[4];varying vec2 road;varying vec3 wp,up;
      ${court?meridianRain(court.storefronts.length):''}
      float stripe(float d,float halfWidth){float w=max(.006,fwidth(d));return 1.-smoothstep(halfWidth-w*.48,halfWidth+w*.52,abs(d));}
      void main(){
        vec2 uv=wp.xy/4.04;vec3 V=normalize(cameraPosition-wp);
        float rough=texture2D(asphaltRough,uv).r;
        vec3 n=texture2D(asphaltNormal,uv).rgb*2.-1.;
        vec3 N=normalize(up+vec3(n.xy*.31,0.));vec3 R=reflect(-V,N);
        vec2 sky=vec2(fract(atan(R.y,R.x)/6.2831853),clamp(asin(max(0.,R.z))*.63662,.001,.999));
        vec2 ds=dFdx(sky),dt=dFdy(sky);ds.x-=floor(ds.x+.5);dt.x-=floor(dt.x+.5);
        vec3 reflected=mix(textureGrad(daySky,sky,ds,dt).rgb,textureGrad(nightSky,sky,ds,dt).rgb,night);
        vec3 c=texture2D(asphaltColor,uv).rgb*mix(vec3(.66,.71,.81),vec3(.105,.135,.19),night);
        if(cityReflectionReady>.5){
          float district=1.-smoothstep(500.,1550.,distance(wp.xy,vec2(-12.,2328.)));
          vec2 uvCity=vec2(atan(R.y,R.x)/6.2831853+.5,asin(clamp(R.z,-1.,1.))/3.14159265+.5);
          vec2 dx=dFdx(uvCity),dy=dFdy(uvCity);dx.x-=floor(dx.x+.5);dy.x-=floor(dy.x+.5);
          vec3 skyline=mix(textureGrad(cityDayReflection,uvCity,dx,dy).rgb,
                           textureGrad(cityNightReflection,uvCity,dx,dy).rgb,night);
          reflected=mix(reflected,skyline*(1.+blueHour*.16),district*(.88-rough*.18));
        }
        c+=reflected*pow(1.-max(0.,dot(N,V)),3.)*(.64-.36*rough);
        for(int j=0;j<4;j++){
          vec3 delta=lights[j]-wp,L=normalize(delta),H=normalize(V+L);
          vec3 color=j<2?vec3(.64,.30,.82):vec3(.22,.76,.99);
          float lobe=pow(max(0.,dot(N,H)),mix(120.,39.,rough));
          c+=(color*mix(.34,1.7,night)+vec3(.14))*lobe/(1.+dot(delta,delta)*.0018);
        }
        ${court?`c=meridianAfterRain(c,wp,V,n,reflected,rough,night);`:''}
        float u=abs(road.x),s=road.y;
        vec3 edge=road.x>0.?vec3(.05,.78,.93):vec3(.64,.23,.91);
        float fade=1.-smoothstep(.6,2.3,fwidth(road.x));
        float lip=stripe(u-12.90,.12), outer=stripe(u-13.28,.045);
        float inlay=stripe(u-12.53,.062);
        float band=exp(-abs(u-12.85)*2.6)*(1.-rough*.53);
        float stud=stripe(mod(s+6.,12.)-6.,.37)*stripe(u-12.79,.205);
        float skip=stripe(mod(s+10.,20.)-10.,2.6)*(1.-smoothstep(1.,6.,fwidth(s)));
        float lane=(stripe(u-6.35,.090)+stripe(u,.075))*skip;
        c=mix(c,vec3(.56,.58,.56)*mix(1.,.38,night),lane*fade*.86);
        c+=edge*(lip*mix(.19,1.72,night)+inlay*.37+band*night*.31+stud*mix(.22,1.72,night))*fade;
        c+=vec3(.60,.66,.72)*outer*fade;
        float haze=1.-exp(-distance(wp,cameraPosition)*.000090);
        gl_FragColor=vec4(mix(c,mix(vec3(.13,.16,.21),vec3(.016,.028,.052),night),haze),1.);
        #include <colorspace_fragment>
      }`});
  const mesh = new THREE.Mesh(geo,mat);
  mesh.name='Night Velocity running surface';
  group.add(mesh);
}
